---
title: "メモリ爆発だと思ったら計測バグだった — ru_maxrss と VmRSS の罠"
emoji: "🧠"
type: "tech"
topics: ["python", "pytorch", "qdrant", "rag", "linux"]
published: false
---

RAG 用の知識ベースを作るため、Web 記事をクロール → チャンク分割 → embedding → Qdrant 投入するパイプラインを回していたときの話です。

投入処理の RSS（メモリ使用量）ログがこうなりました。

```text
  50/1287 投入済み... (RSS 1594MB)
  ⚠️  RSS 1594MB が上限 1024MB を超過 — 中断します
```

その後も処理を続けるたびに RSS の数字は上がる一方。「embedding のループでメモリリークしている」と思い込み、`gc.collect()` を挟んだり `del` を増やしたりしましたが、数字は一度も下がりませんでした。

結論から言うと、**リークしていたのはメモリではなく計測方法**でした。

## 原因: ru_maxrss は「ピーク値」

最初の実装はこうでした。

```python
import resource

def rss_mb() -> int:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
```

`ru_maxrss` は **プロセス開始からの最大 RSS（ピーク値）** です。現在値ではありません。

つまり、一瞬でもメモリを多く使えば、その後どれだけ解放しても数字は下がらない。`gc.collect()` が効いていても**ログ上は単調増加にしか見えない**ので、「リークしている」ように錯覚します。

- どれだけ解放しても数字が下がらない → リークと誤診
- 上限チェックに使うと、一度ピークを踏んだだけで以降ずっと「超過」判定

## 修正: /proc/self/status の VmRSS を読む

Linux なら `/proc/self/status` の `VmRSS` が現在値です。

```python
def rss_mb() -> int:
    # VmRSS = 現在の RSS。ru_maxrss はピーク値なので監視には不適切
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) // 1024  # kB → MB
    except OSError:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
    return 0
```

修正後のログはこうなりました。

```text
  850/1105 投入済み... (RSS 1974MB)
  900/1105 投入済み... (RSS 1809MB)   ← 下がる
  950/1105 投入済み... (RSS 1811MB)
  1000/1105 投入済み... (RSS 1862MB)
```

数字が上下するようになり、実態は **モデルロード後 ~1.8GB 前後で安定** していたことが分かりました。爆発などしていなかったのです。

ちなみに「モデルロード直後で 1.6GB」の内訳はほぼ sentence-transformers のモデル本体（multilingual-e5-base）です。上限を 1GB に設定していたこと自体が、そもそも成立しない条件でした。

## ついでに直した: 1件ずつ encode をバッチ encode に

調査中にもう一つ非効率を見つけました。チャンクを 1 件ずつ `model.encode()` していた部分です。

```python
# Before: 1件ずつ
for r in batch:
    vector = model.encode(prefix + r["text"], normalize_embeddings=True)
```

```python
# After: 50件バッチで一括
import gc, torch

PUSH_BATCH = 50
prefix = "passage: "  # e5 系モデルは必須

for batch_start in range(0, len(rows), PUSH_BATCH):
    batch = rows[batch_start : batch_start + PUSH_BATCH]
    texts = [prefix + r["text"] for r in batch]

    with torch.no_grad():
        vectors = model.encode(texts, normalize_embeddings=True, batch_size=PUSH_BATCH)

    for r, vector in zip(batch, vectors):
        upsert(collection, vector.tolist(), payload_of(r))

    del vectors, texts
    gc.collect()
    if rss_mb() > RSS_LIMIT_MB:
        print("RSS 超過 — 中断（未投入分は次回継続）")
        break
```

ポイント:

- **`torch.no_grad()`**: 推論に勾配バッファは不要。付け忘れると本当にメモリが増え続けます（こちらは実在するリーク要因）
- **バッチ encode**: tokenize / forward のオーバーヘッドが償却され、スループットが大きく改善
- **e5 系のプレフィックス**: `intfloat/multilingual-e5-*` は投入側 `passage: ` / 検索側 `query: ` を付けないと精度が落ちます
- **中断→再開可能な設計**: 投入済みチャンクに ID を記録しておき、`qdrant_id IS NULL` のものだけ再処理

## まとめ

| 症状 | 真因 | 対処 |
| --- | --- | --- |
| RSS が単調増加、gc が効かない | `ru_maxrss` はピーク値 | `/proc/self/status` の `VmRSS` を読む |
| 推論ループでメモリが実際に増える | 勾配バッファの蓄積 | `torch.no_grad()` で囲む |
| embedding が遅い | 1件ずつ encode | バッチ encode + `batch_size` 指定 |

「メモリリークだ」と思ったら、まず**計測している値が現在値なのかピーク値なのか**を確認する。`getrusage` の man ページには `ru_maxrss (maximum resident set size)` と明記されているのに、名前の雰囲気で現在値だと思い込んでいました。

最終的にこのパイプラインで 8 タグ・約 8,700 チャンクを RSS ~2GB 安定のまま投入できました。
