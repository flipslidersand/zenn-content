---
title: "分散 Discord Bot のレース条件を追った話"
emoji: "🤖"
type: "tech"
topics: ["discord", "python", "asyncio", "concurrency"]
published: false
---

## TL;DR

本番（Docker）とローカルで Bot を同時起動すると、`#errors` チャンネルへのメッセージに両者が Thread を作ろうとして、後着が `400 error code 160004` を受けて WARNING ログを吐く。修正は1行——error code 160004 のみ WARNING → INFO に格下げ。

---

## 症状

Discord Bot の error_handler が `#errors` チャンネルのメッセージに Thread を作る仕組みを持っていた。ある日から WARNING が周期的に発生した。

```
WARNING: failed to create thread: 400 Bad Request (error code: 160004): Cannot create a thread without a message
```

ログだけ見ると「Thread 作成に失敗している」に見えるが、実際には Thread はちゃんと作られていた。

---

## 仮説と真因の差分

最初の Issue では「`thread_handler` と `error_handler` が両方 Thread を作ろうとしているのでは」と書いた。コードを追うと違った。

- `thread_handler` の `on_thread_create` は **Thread が作られたことを観測するだけ**で、作成者ではない
- `create_thread` の呼び出しは `error_handler` の1箇所のみ

実際のレースは **Bot インスタンス間**だった。

| インスタンス | 実行場所 |
|---|---|
| 本番 Bot | MINIPC の Docker コンテナ |
| テスト Bot | ローカル `main.py` |

同じ `#errors` チャンネルを両者が監視しているとき、同一メッセージに対して両者が `create_thread` を呼ぶ。先着が成功し、後着が 160004 を受ける。

`message.thread` の事前チェックでは防げない——キャッシュから読むため、もう一方のインスタンスが作成した Thread を即座に反映しないからだ。

---

## 修正

```python
# Before
except discord.HTTPException as exc:
    logger.warning("failed to create thread: %s", exc)

# After
except discord.HTTPException as exc:
    if exc.code == 160004:
        # 本番/テスト Bot 併走時に相手が先に作成した良性レース。
        # message.thread の事前チェックはキャッシュ依存でこの競合を防げない。
        logger.info(
            "thread already exists for message %d (created by another instance)",
            message.id,
        )
    else:
        logger.warning("failed to create thread: %s", exc)
```

160004 は「すでに Thread が存在する」を意味する良性エラー。目的（Thread の存在）は達成されているので INFO で十分。その他のエラーは引き続き WARNING。

---

## テスト

2ケースを追加した。

```python
@pytest.mark.asyncio
async def test_error_handler_treats_duplicate_thread_as_benign(caplog):
    """160004 → WARNING なし、INFO あり"""
    ...
    message.create_thread = AsyncMock(
        side_effect=discord.HTTPException(
            MagicMock(status=400), {"code": 160004, "message": "..."}
        )
    )
    with caplog.at_level(logging.INFO):
        await handler.on_message(message)

    assert not any(r.levelno == logging.WARNING for r in caplog.records)
    assert any("another instance" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_error_handler_warns_on_other_http_errors(caplog):
    """160004 以外 → WARNING あり"""
    ...
    message.create_thread = AsyncMock(
        side_effect=discord.HTTPException(
            MagicMock(status=403), {"code": 50001, "message": "Missing Access"}
        )
    )
    with caplog.at_level(logging.INFO):
        await handler.on_message(message)

    assert any(
        r.levelno == logging.WARNING and "failed to create thread" in r.getMessage()
        for r in caplog.records
    )
```

61 passed。

---

## 教訓

**1. WARNING ノイズは「失敗」とは限らない**
ログレベルの付け方が実態を誤解させることがある。結果が正常なら INFO で表現する。

**2. 同一リソースへの複数インスタンスは「レース」の予兆**
`message.thread` の事前チェックはキャッシュ依存——非同期・分散の文脈ではこういう「チェックしてから操作」パターンは TOCTOU になりやすい。

**3. 最小修正で済む場合がある**
真因は「2インスタンスが同じチャンネルを監視している運用形態」だが、それを変えるより「後着エラーを良性として扱う」のほうが変更範囲が小さく安全だった。
