---
title: "Python の RSS 監視でハマった話 — ru_maxrss は現在メモリではなくピーク値"
emoji: "🧠"
type: "tech"
topics: ["python", "pytorch", "qdrant", "rag", "linux"]
published: true
---

RAG 用の知識ベースを作るために、Web 記事をクロールし、チャンク分割して、embedding を作成し、Qdrant に投入するパイプラインを回していました。

その途中で、メモリ使用量のログがこうなりました。

```text
  50/1287 投入済み... (RSS 1594MB)
  ⚠️ RSS 1594MB が上限 1024MB を超過 — 中断します
```

その後も処理を続けるたびに RSS の数字は上がる一方でした。

「embedding のループでメモリリークしているのでは？」と思い、`gc.collect()` を挟んだり、`del` を増やしたりしました。

しかし、数字は一度も下がりません。

結論から言うと、**リークしていたのはメモリではなく、計測方法でした。**

## 何が起きていたか

最初に使っていた RSS 計測コードはこれです。

```python
import resource

def rss_mb() -> int:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
```

一見すると、現在の RSS を取得しているように見えます。

しかし、`ru_maxrss` は **現在の RSS ではありません。**

これは、プロセス開始から現在までの **最大 RSS** です。つまりピーク値です。

そのため、一度でもメモリ使用量が大きくなれば、その後にメモリが解放されても値は下がりません。

## ru_maxrss を監視に使うと何がまずいか

`ru_maxrss` はピーク値なので、現在値の監視に使うと挙動を見誤ります。

たとえば、実際にはメモリが解放されていても、ログ上はこう見えます。

```text
RSS 1200MB
RSS 1500MB
RSS 1800MB
RSS 1800MB
RSS 1800MB
```

このログだけを見ると、メモリが増え続けているように見えます。

しかし、実際には「過去に 1800MB まで使ったことがある」というだけです。

そのため、次のような誤診につながります。

- `gc.collect()` が効いていないように見える
- `del` してもメモリが解放されていないように見える
- メモリリークしているように見える
- 上限チェックに使うと、一度ピークを超えただけで以後ずっと超過判定になる

今回もまさにこれでした。

## Linux で現在の RSS を見るなら VmRSS を読む

Linux で現在の RSS を見たい場合は、`/proc/self/status` の `VmRSS` を読むようにしました。

```python
def rss_mb() -> int:
    # VmRSS = 現在の RSS
    # ru_maxrss はピーク値なので、現在メモリ監視には使わない
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) // 1024  # kB -> MB
    except OSError:
        # Linux 以外など /proc が読めない場合のフォールバック
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024

    return 0
```

この変更後、ログはこうなりました。

```text
  850/1105 投入済み... (RSS 1974MB)
  900/1105 投入済み... (RSS 1809MB)
  950/1105 投入済み... (RSS 1811MB)
  1000/1105 投入済み... (RSS 1862MB)
```

RSS が上下するようになりました。

つまり、実際にはメモリが増え続けていたわけではなく、モデルロード後に **1.8GB 前後で安定** していたことが分かりました。

爆発などしていなかったのです。

## そもそも 1GB 上限が無理だった

もう一つ分かったことがあります。

モデルロード直後の時点で、すでに RSS は 1.6GB 前後になっていました。

今回使っていた embedding モデルは `intfloat/multilingual-e5-base` です。

この時点で、RSS 上限を 1GB に設定していたこと自体が無理筋でした。

つまり問題は二つありました。

1. `ru_maxrss` を現在値だと思っていた
2. モデルロード後の実メモリを見ずに、RSS 上限を 1GB にしていた

メモリリークを疑う前に、まずベースラインを見るべきでした。

## ついでに直した: 1件ずつ encode をやめる

調査中に、もう一つ非効率な部分を見つけました。

チャンクを 1 件ずつ `model.encode()` していた部分です。

```python
# Before: 1件ずつ encode
for r in batch:
    vector = model.encode(prefix + r["text"], normalize_embeddings=True)
```

これを、50 件単位のバッチ encode に変更しました。

```python
import gc
import torch

PUSH_BATCH = 50
prefix = "passage: "  # e5 系モデルでは投入側に付ける

for batch_start in range(0, len(rows), PUSH_BATCH):
    batch = rows[batch_start : batch_start + PUSH_BATCH]
    texts = [prefix + r["text"] for r in batch]

    with torch.no_grad():
        vectors = model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=PUSH_BATCH,
        )

    for r, vector in zip(batch, vectors):
        upsert(
            collection=collection,
            vector=vector.tolist(),
            payload=payload_of(r),
        )

    del vectors, texts
    gc.collect()

    if rss_mb() > RSS_LIMIT_MB:
        print("RSS 超過 — 中断します。未投入分は次回再開します。")
        break
```

バッチ化すると、tokenize や forward のオーバーヘッドをまとめられるため、スループットがかなり改善しました。

## e5 系モデルでは prefix も忘れない

今回使っていた `intfloat/multilingual-e5-base` は e5 系のモデルです。

e5 系では、embedding 対象のテキストに prefix を付ける前提になっています。

投入側は `"passage: "`。

```python
prefix = "passage: "
texts = [prefix + r["text"] for r in batch]
```

検索側は `"query: "`。

```python
query_vector = model.encode(
    "query: " + query,
    normalize_embeddings=True,
)
```

これを忘れると、embedding 自体は作れますが、検索精度が落ちます。

メモリ調査のつもりが、ついでにここも見直すことになりました。

## 中断しても再開できるようにする

RSS 上限を超えた場合、処理を完全に失敗させるのではなく、途中で止めて次回再開できるようにしました。

具体的には、投入済みチャンクに `qdrant_id` を記録しておきます。

次回実行時は、まだ投入されていないものだけを対象にします。

```sql
SELECT *
FROM chunks
WHERE qdrant_id IS NULL
ORDER BY id;
```

こうしておくと、途中で止まっても最初からやり直す必要がありません。

RAG 用の投入処理は件数が増えがちなので、最初から「止まる前提」で作っておくと楽です。

## まとめ

| 症状                                     | 真因                                 | 対処                                     |
| ---------------------------------------- | ------------------------------------ | ---------------------------------------- |
| RSS が単調増加しているように見える       | `ru_maxrss` は現在値ではなくピーク値 | `/proc/self/status` の `VmRSS` を読む    |
| `gc.collect()` しても数字が下がらない    | 見ている値がピーク値なので下がらない | 現在 RSS を別途取得する                  |
| モデルロード直後に RSS が高い            | embedding モデル本体のメモリ使用量   | ロード後のベースラインを確認する         |
| embedding が遅い                         | 1件ずつ `encode()` している          | バッチ encode にする                     |
| 処理途中で止まると最初からやり直しになる | 投入状態を保存していない             | `qdrant_id IS NULL` のものだけ再処理する |

## 教訓

メモリリークを疑う前に、まず **計測している値が現在値なのか、ピーク値なのか** を確認する。

今回の原因は、`ru_maxrss` という名前を見て「RSS の現在値」だと思い込んだことでした。

しかし、実際には `maximum resident set size`。

最大値です。

つまり、メモリが爆発していたのではなく、**ピーク値を現在値として見ていた**だけでした。

計測を間違えると、存在しないバグを追うことになります。

メモリより先に、まずメトリクスを疑う。

今回の一番の学びはそれでした。
