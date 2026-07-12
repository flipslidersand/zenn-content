---
title: "AI生成コード 5軸採点を Rust で実装した — 責任の取り方"
emoji: "🧪"
type: "tech"
topics: ["AI", "Rust", "コード検証", "Wasm", "セキュリティ"]
published: true
---

## はじめに

「AI が 3 つコード案を出してくれた。どれを採用する？」

こういう状況が当たり前になったいま、**複数候補の中から「信頼できる」ものを選ぶ仕組み**がなければ、結局のところ勘で選んでいるのと変わらない。

このエッセイでは、AI 生成コードを**自動検証・採点・比較できるシステム** [SafeCode Arena](https://github.com/flipslidersand/safecode-arena) を Rust で実装した経験から、「責任を設計に組み込む」ことについて考えたことを書く。

## 問題: スコアのない判断

Cursor や Claude Code、GitHub Copilot を使っていると、対話のなかで「複数案から選ぶ」ことが頻繁に起こる。

```
（AI が 3 つの解法案を生成）
User: "どれがいい？"
AI: "使用例に応じてトレードオフがあります..."
```

回答は正しいんだけど、**「使用例」「トレードオフ」を数値化しないと、結局のところ感覚で選んでいる**。そして感覚で選んだコードを本番に出す。これでいいのか。

### 従来の解決策の限界

- **テストだけ**: 仕様を通すコードは合格。だが「セキュリティは？」「パフォーマンスは？」は見えない
- **コードレビュー**: 人の経験が頼り。スケールしない
- **静的解析**: clippy / ruff は有用。だが単一軸。複数軸のトレードオフは見えない
- **ベンチマーク**: 性能は測れるが、「正しさ」「セキュリティ」と一緒に見ない限り意味がない

つまり、**複数軸を同時に見て、スコアとして返すシステムがない**。

## 解決策: 5軸採点ルーブリック

SafeCode Arena で実装した採点は以下の 5 軸。

| 軸                                | 重み | 算出方法                                                |
| --------------------------------- | ---- | ------------------------------------------------------- |
| **正確性** (correctness)          | 50%  | コンパイル (40%) + テスト (40%) + property テスト (20%) |
| **セキュリティ** (security)       | 20%  | unsafe ヒューリスティック (50%) + clippy 警告 (50%)     |
| **性能** (performance)            | 15%  | 候補間のコンパイル・テスト時間の相対比較                |
| **保守性** (maintainability)      | 10%  | 関数長ヒューリスティック (60%) + clippy (40%)           |
| **リソース使用** (resource_usage) | 5%   | Wasm サンドボックス実行の成否                           |

### ルーブリック設計の思想

1. **正確性を主軸に**: プロダクションコードは「動く」が最優先。だから重み 50%
2. **セキュリティを可視化**: `unsafe` はコンパイルを通る。だから自分たちで検出する
3. **性能と保守性は相互チェック**: 高速だが読みにくい vs 遅いが明快。両方見る
4. **リソース制限を実測**: 採点スコアが 100 点でも、メモリ爆発したら本番NG。Wasm で検出

### 採点例

```
候補 A: 85 点
├─ correctness: 100 (all tests pass)
├─ security: 60 (2 unsafe blocks flagged)
├─ performance: 70 (10% slower than B)
├─ maintainability: 85 (avg function 25 lines)
└─ resource_usage: 80 (Wasm sandbox: 512MB, OK)

候補 B: 92 点（推奨）
├─ correctness: 95 (1 edge case warning)
├─ security: 95 (no unsafe)
├─ performance: 95 (fastest)
├─ maintainability: 88 (avg function 20 lines)
└─ resource_usage: 100 (Wasm sandbox: 200MB)
```

スコアだけでなく、各軸の詳細が見える。「B が上」という判断が**なぜそうなのか説明可能**になる。

## 実装のポイント

### 1. Wasm でコード実行を隔離

```rust
// 候補コードをコンパイル → Wasm に変換
// Wasm Runtime (wasmtime) でメモリ・CPU 時間制限付きで実行
let instance = linker.instantiate(&module)?;
let run_fn = instance.get_typed_func::<(), ()>(&mut store, "run")?;
run_fn.call(&mut store, ())?;  // fuel limit + memory limit が効いてる
```

**重要**: AI が生成したコードはバグ・無限ループ・メモリ爆発のリスクがある。直接実行は危険。Wasm サンドボックスなら「暴走したら fuel で kill」と決まっている。

### 2. SQLite で検査履歴を永続化

```rust
// 同じ仕様で複数回評価した場合、前回の結果と比較
db.execute(
    "INSERT INTO evaluation (spec_hash, candidate_hash, score, timestamp)
     VALUES (?, ?, ?, ?)",
    params![spec_hash, candidate_hash, score, now],
)?;

// リグレッション検出
let prev_score = db.query_row(
    "SELECT score FROM evaluation WHERE spec_hash = ? ORDER BY timestamp DESC LIMIT 1",
    [&spec_hash],
    |row| row.get::<_, i32>(0),
)?;
if score < prev_score - threshold { alert!("Regression!"); }
```

**なぜ履歴が必要か**: 同じ仕様で複数回評価するとき「新しい候補が前より悪くなった」を検出できる。「何が悪化したのか」が見える。

### 3. 複数言語対応（Rust + Python）

```rust
match candidate_path.extension().unwrap().to_str().unwrap() {
    "rs" => compile_and_evaluate_rust(candidate),
    "py" => compile_and_evaluate_python(candidate),
    _ => Err("Unsupported language"),
}
```

**利点**: 「Rust の最適解」と「Python の最適解」を同じルーブリックで比較できる。言語横断で採点順序が一貫している。

## 採点ルーブリックは「責任」

ここからが重要な話。

ルーブリックを作る＝ **「何を信頼するのか」を明示することだ**。

### 従来: 人の経験に委ねる

```
レビュアー A: 「これはセキュリティリスクがある」
（が、根拠は個人の直感）
```

**問題**: 次にコードを見た人がレビュアー A の判断を信じるかどうか、その人の経験次第。スケールしない。

### SafeCode Arena: ルーブリックを明示

```
「unsafe ブロックがあれば -10 点」
「property テストが全て通れば +15 点」
...（全て明記）
```

**利点**: 「なぜこのコードは 85 点なのか」が説明可能。異議申し立てもできる（「その unsafe は本当に危ないか？」と検証ルーブリック自体を改善）。

つまり、ルーブリック ＝ **チームの「信頼基準」を形式化したもの**。AI 時代には、この基準が可視化されていることが責任になる。

## 実装例: GitHub で使う

```bash
# GitHub Actions で自動実行
safecode evaluate pr-candidate.rs --tests tests/ --format json
# → JSON で返す → PR コメントに貼る

# Developer は PR コメントを見るだけ
# 「スコア 92 点」「リグレッションなし」を一目で判断
```

ベースの flow としては:

1. **AI が複数案を生成** (Cursor / Claude Code)
2. **safecode で自動採点** (CI)
3. **結果を PR コメントに** (GitHub Actions)
4. **マージ前に確認** (人間の判断)

## 教訓: スコア設計は選択の記録

最後に、このプロジェクトで学んだこと。

「完璧なスコアを作ろう」は無駄。大事なのは：

- **「何を選んだのか」を記録できる** こと
- **「なぜ選んだのか」を説明できる** こと
- **後から「その判断は間違ってなかった」を検証できる** こと

AI が生成したコードを本番に出すときの責任は、開発者にある。その責任をスコアというかたちで可視化する。それが SafeCode Arena のコンセプト。

---

## リソース

- GitHub: https://github.com/flipslidersand/safecode-arena
- 言語: Rust, Python
- ライセンス: MIT
- 実装: Phase 1–5 完了。次は Go/JS 対応
