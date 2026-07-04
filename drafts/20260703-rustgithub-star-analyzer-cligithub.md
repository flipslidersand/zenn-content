---
title: "RustでGitHub Star Analyzer CLIを作ってみた：自作ツールでGitHubの星を追う！"
emoji: "🌟"
type: "tech"
topics: ["rust"]
published: false
---

# RustでGitHub Star Analyzer CLIを作ってみた：自作ツールでGitHubの星を追う！

皆さん、こんにちは！普段からGitHubを眺めていて「このリポジトリ、最近スター数伸びてるな」「自分のリポジトリのスター数の推移ってどうなってるんだろう？」と感じたことはありませんか？私はいつもそうでした。しかし、それを手動で追いかけるのは、正直なところ「面倒」の一言に尽きます。

そんな私の長年の「面倒」を解決すべく、今回Rustを使ってGitHubのスター数を追跡・分析するCLIツールを作成してみました。この記事は、まさに私が「読みたかった」と思うような、開発の動機から、技術選定、実装のポイント、そしてぶつかった壁とその乗り越え方まで、私の経験を余すところなくお伝えします。Rustでの開発の喜びや難しさ、そして最終的に得られた成果を、ぜひ皆さんと共有できたら嬉しいです。

---

### なぜ作ったか？GitHubの星を追い続ける「面倒」を解決したかった

私は日頃からオープンソースの動向や、興味のある技術スタックのリポジトリの成長をウォッチしています。GitHubのスター数というのは、そのリポジトリの人気や注目度を測る一つの重要な指標です。例えば、

*   **自分が貢献している、または作成したリポジトリの成長を定点観測したい**
*   **特定の技術分野で今一番勢いのあるリポジトリはどれか知りたい**
*   **お気に入りのライブラリがどれくらいのペースでスターを増やしているのか、そのトレンドを把握したい**

といったニーズが常にありました。

しかし、これらの情報を得るには、毎日GitHubのページを開いてスター数を確認し、Excelやスプレッドシートに手動で記録していく、という非常にアナログで非効率な方法しかありませんでした。数個のリポジトリならまだしも、追いたいリポジトリが増えれば増えるほど、この作業は膨大な時間と労力を消費します。

「これではいけない！もっとスマートに、自動で、必要な情報を手に入れたい！」

そう強く思ったのが、このCLIツール開発のきっかけです。手軽にターミナルからコマンドを叩くだけで、複数のリポジトリのスター数を一覧表示したり、過去の推移を追跡できたら、どんなに素晴らしいだろう。そんな「自分が本当に欲しかったツール」を作ることを決意しました。

---

### プロジェクト設計と技術選定：Rustのエコシステムをフル活用する！

ツールの開発にあたり、まず考えたのはどのプログラミング言語を選ぶかでした。候補としてはPythonやGoなども挙がりましたが、最終的に私は**Rust**を選びました。その意思決定プロセスは以下の通りです。

#### なぜRustを選んだか？

1.  **パフォーマンスと安全性**: CLIツールとして、高速に動作し、かつ堅牢であることが重要です。Rustはその両方を高いレベルで実現できます。特に、GitHub APIから大量のデータを取得する際に、メモリ安全性を確保しながら最大限のパフォーマンスを発揮できる点が魅力的でした。
2.  **バイナリ配布の容易さ**: Rustで書かれたプログラムは、単一の静的リンクされたバイナリとしてコンパイルできるため、インストールが非常に簡単です。ユーザーは単一のファイルをダウンロードするだけで、すぐにツールを使い始められます。これはCLIツールにとって大きなメリットです。
3.  **所有権とライフタイムの学習機会**: 最近Rustを本格的に学び始めたばかりの私にとって、実践的なプロジェクトを通して所有権システムやライフタイム、非同期処理といったRustの強力な特徴を深く理解する絶好の機会だと考えました。
4.  **充実したエコシステム**: Rustのエコシステムは非常に成熟しており、CLIツール開発に必要なクレートが豊富に揃っています。

#### 主要な技術スタック

Rustを選んだからには、その強力なエコシステムを最大限に活用しようと考え、以下のクレート（ライブラリ）を選定しました。

*   **`reqwest`**: 非同期HTTPクライアント。GitHub APIへのリクエスト送信に利用します。`tokio` との統合が容易で、非常に使いやすいです。
*   **`tokio`**: 非同期ランタイム。Rustにおける非同期処理のデファクトスタンダードであり、高いパフォーマンスで並行処理を実現します。
*   **`serde` + `serde_json`**: JSONのシリアライズ・デシリアライズ。GitHub APIから返されるJSONデータをRustの構造体に簡単にマッピングできます。
*   **`clap`**: コマンドライン引数パーサー。柔軟かつ強力にCLIの引数を定義・解析できます。ヘルプメッセージの自動生成機能も充実しており、CLIツールには必須のクレートです。
*   **`chrono`**: 日付と時刻の処理。スター数の推移を追跡する際に、タイムスタンプの管理や比較に利用します。
*   **`anyhow` / `thiserror`**: エラーハンドリング。堅牢なアプリケーションを開発するためには、エラー処理が非常に重要です。`anyhow` はシンプルにエラーを伝播させるのに便利で、`thiserror` は独自のエラー型を定義する際に役立ちます。

これらのクレートを組み合わせることで、効率的かつ安全に、そして高機能なCLIツールを開発できると確信しました。

---

### Rustならではの実装のポイント：所有権と非同期処理で堅牢に、高速に

Rustで開発を進める中で、特にその強みを感じたのが「所有権システム」と「非同期処理」です。これらはCLIツールの堅牢性と高速性を担保する上で不可欠な要素となりました。

#### 所有権システムでメモリ安全性を確保

Rustの所有権システムは、コンパイル時にメモリ安全性を保証するという点で、他の言語にはない強力な特徴です。最初は学習コストが高いと感じるかもしれませんが、一度理解してしまえば、実行時エラーの多くを未然に防ぐことができます。

例えば、文字列データを扱う際、その所有権をどこに置くか、または参照として渡すかを意識します。

```rust
// main.rs
use std::collections::HashMap;

fn analyze_stars(repo_name: &str, star_counts: &HashMap<String, u32>) {
    // `repo_name` は参照として渡されるため、この関数内で所有権を移動することなく利用できる
    // `star_counts` も同様に参照なので、マップのコピーは発生しない
    if let Some(stars) = star_counts.get(repo_name) {
        println!("Repository '{}' has {} stars.", repo_name, stars);
    } else {
        println!("Repository '{}' not found in analysis data.", repo_name);
    }
}

fn main() {
    let my_repo = String::from("my-awesome-project"); // String型は所有権を持つ
    let mut data_map: HashMap<String, u32> = HashMap::new();
    data_map.insert(my_repo.clone(), 1234); // analyze_starsに渡すためcloneしておく

    // `&str` 型の参照として関数に渡す
    analyze_stars(&my_repo, &data_map);

    // `my_repo` は引き続き `main` 関数で利用可能
    println!("Original repo name: {}", my_repo);
}
```

このように、所有権を移動させるのか（`String`）、それとも参照を渡すのか（`&str`）を明示的に指定することで、予期せぬデータの破壊やダブルフリーといったバグを防ぎます。これは特に、APIから取得したデータを加工して複数のモジュールに渡すような複雑な処理において、非常に大きな安心感を与えてくれました。

#### `tokio` と `reqwest` による非同期処理で高速化

GitHub APIを叩く際、複数のリポジトリのスター数を同時に取得したい場合があります。このようなI/Oバウンドな処理は、非同期処理の得意分野です。`tokio` と `reqwest` を組み合わせることで、効率的にAPIリクエストを並行して実行し、全体の処理時間を大幅に短縮できました。

GitHub APIはレートリミットがあるため、効率的なリクエスト管理が重要です。非同期処理を用いることで、待機中に他のリクエストを送信するなど、無駄なくリソースを利用できます。

以下に、複数のリポジトリのスター数を非同期で取得する簡略化したコード例を示します。

```rust
// src/main.rs
use reqwest::Client;
use serde::Deserialize;
use tokio::time::{sleep, Duration};
use std::collections::HashMap;

#[derive(Debug, Deserialize)]
struct GitHubRepo {
    stargazers_count: u32,
}

/// 指定されたリポジトリのスター数をGitHub APIから非同期で取得する
async fn fetch_repo_stars(
    owner: &str,
    repo: &str,
    client: &Client,
    github_token: Option<&str>,
) -> Result<(String, u32), anyhow::Error> {
    let url = format!("https://api.github.com/repos/{}/{}", owner, repo);
    let mut request = client.get(&url)
        .header(reqwest::header::USER_AGENT, "github-star-analyzer-cli (rust-lang/reqwest)")
        .header(reqwest::header::ACCEPT, "application/vnd.github.v3+json");

    if let Some(token) = github_token {
        request = request.bearer_auth(token);
    }

    let resp = request.send().await?;
    let resp_text = resp.text().await?;

    // エラーレスポンスの確認（レートリミットなど）
    if resp_text.contains("\"message\":\"API rate limit exceeded\"") {
        eprintln!("GitHub API rate limit exceeded. Waiting for a minute...");
        sleep(Duration::from_secs(60)).await; // 1分待機
        return Err(anyhow::anyhow!("GitHub API rate limit exceeded. Please retry."));
    }
    
    let repo_data: GitHubRepo = serde_json::from_str(&resp_text)?;
    Ok((format!("{}/{}", owner, repo), repo_data.stargazers_count))
}

#[tokio::main]
async fn main() -> Result<(), anyhow::Error> {
    // GitHub Personal Access Token を環境変数から取得
    let github_token = std::env::var("GITHUB_TOKEN").ok();
    if github_token.is_none() {
        eprintln!("Warning: GITHUB_TOKEN environment variable not set. API rate limits might be stricter.");
        eprintln!("         Consider setting it for better performance and higher rate limits.");
    }

    let client = Client::new();
    let repositories = vec![
        ("rust-lang", "rust"),
        ("tokio-rs", "tokio"),
        ("serde-rs", "serde"),
        ("clap-rs", "clap"),
        ("google", "go-github"), // 存在しないリポジトリでエラーハンドリングをテスト
    ];

    let mut handles = Vec::new();
    for (owner, repo) in repositories {
        let client_clone = client.clone();
        let github_token_clone = github_token.clone(); // Tokenもクローンして渡す
        let owner_str = owner.to_string(); // 所有権をmoveするためStringに変換
        let repo_str = repo.to_string();   // 所有権をmoveするためStringに変換

        let handle = tokio::spawn(async move {
            fetch_repo_stars(&owner_str, &repo_str, &client_clone, github_token_clone.as_deref())
                .await
        });
        handles.push(handle);
    }

    let mut results: HashMap<String, u32> = HashMap::new();
    for handle in handles {
        match handle.await? { // JoinErrorをResultで処理
            Ok((repo_path, stars)) => {
                results.insert(repo_path, stars);
            },
            Err(e) => {
                eprintln!("Error fetching stars: {:?}", e);
            }
        }
    }

    for (repo_path, stars) in results {
        println!("{} stars for {}", stars, repo_path);
    }

    Ok(())
}
```

このコードでは、`tokio::spawn` を使って複数の非同期タスクを並行して実行しています。各タスクは独立してGitHub APIにリクエストを送り、結果を待機します。`await` を適切に使うことで、I/Oの待機中にCPUがブロックされることなく、他のタスクの処理を進められるため、効率的なデータ取得が可能になります。また、GitHub APIの必須要件である `User-Agent` ヘッダーの設定と、レートリミット対策としての `GITHUB_TOKEN` の利用も考慮しています。

---

### ハマったこと、つまずいた壁：Rustの奥深さに挑む

Rustでの開発は非常に楽しく、多くの学びがありましたが、もちろんいくつかの壁にもぶつかりました。特に印象的だった3つのハマりポイントとその解決策を紹介します。

#### ハマりポイント1: GitHub APIのレートリミットと賢い利用法

**問題**: 開発当初、無邪気にループ内でGitHub APIを叩きまくったところ、すぐに「API rate limit exceeded」というエラーに遭遇しました。認証なしのAPIリクエストは1時間あたり60件という厳しい制限があります。

**解決策**:
1.  **`reqwest::Client` の使い回し**: HTTPクライアントのインスタンスを毎回生成するのではなく、一度作成した `Client` インスタンスを使い回すことで、コネクションプーリングが有効になり、オーバーヘッドを削減できます。
2.  **`User-Agent` ヘッダーの設定**: GitHub APIは `User-Agent` ヘッダーを必須としています。これを設定しないと、意図しないエラーやブロックに繋がることがあります。
3.  **Personal Access Token (PAT) の利用**: 最も効果的な解決策は、GitHubのPersonal Access Token（PAT）を使って認証済みのリクエストを送ることです。認証済みリクエストのレートリミットは1時間あたり5000件と大幅に緩和されます。私はPATを `GITHUB_TOKEN` という環境変数に設定し、プログラムから読み込むようにしました。

    ```rust
    // 環境変数からトークンを読み込む例
    let github_token = std::env::var("GITHUB_TOKEN").ok();
    // reqwestでBearerトークンとして設定
    // .bearer_auth(token)
    ```
4.  **リクエスト間の遅延**: それでもレートリミットが気になる場合や、大量のリポジトリを処理する場合は、`tokio::time::sleep` を使ってリクエスト間に短い遅延を入れることも有効です。ただし、非同期処理のメリットを損なわないよう、必要最低限に留めます。

#### ハマりポイント2: `async fn` 内での所有権とライフタイム地獄

**問題**: `tokio::spawn` で非同期タスクを生成する際、タスク内で使用する変数のライフタイムについて深く悩まされました。特に、ループ内で生成される変数（例: `String`）を `async move` ブロックに渡そうとすると、`captured variable may not outlive the current function` のようなライフタイムエラーに頻繁に遭遇しました。非同期タスクは `main` 関数のスコープよりも長く実行される可能性があるため、参照を渡すだけでは危険と判断されるのです。

```rust
// ハマった例 (擬似コード)
// async fn process_repo(name: &str) { /* ... */ }
//
// #[tokio::main]
// async fn main() {
//     let repo_names = vec![String::from("repo1"), String::from("repo2")];
//     for name in &repo_names { // &String -> &str への参照
//         tokio::spawn(process_repo(name)); // Error: `name` のライフタイムがタスクより短い可能性がある
//     }
// }
```

**解決策**:
1.  **所有権の移動 (`.to_string()`, `.clone()`)**: `async move` ブロックは、その中で使われるすべての変数の所有権をブロック内に移動させます。そのため、ループ内で `&str` などの参照を使いたい場合は、そのデータの所有権を `String` としてタスクに移動させる必要があります。

    ```rust
    // 解決策1: Stringをcloneして所有権を渡す
    let repo_names = vec![String::from("repo1"), String::from("repo2")];
    for name in &repo_names {
        let name_owned = name.clone(); // Stringをクローン
        tokio::spawn(async move {
            process_repo(name_owned).await; // name_owned の所有権がタスクに移動
        });
    }
    // `process_repo` のシグネチャも `async fn process_repo(name: String)` に変更
    ```
2.  **`Arc` を使った共有**: 複数のタスク間でデータを共有したいが、それぞれがデータの所有権を持つ必要がない場合（例: `reqwest::Client` インスタンスなど）、`Arc<T>` (Atomically Reference Counted) を使って共有します。これにより、データは一度だけヒープに確保され、参照カウントがゼロになったときに解放されます。

    ```rust
    // 解決策2: ArcでClientを共有
    use std::sync::Arc;
    let client = Arc::new(Client::new());
    for (owner, repo) in repositories {
        let client_clone = Arc::clone(&client); // Arcの参照カウントを増やす
        let owner_str = owner.to_string();
        let repo_str = repo.to_string();

        tokio::spawn(async move {
            fetch_repo_stars(&owner_str, &repo_str, &client_clone, github_token_clone.as_deref())
                .await
        });
    }
    ```
    今回の `fetch_repo_stars` の例では `Client` は `&Client` で渡せるので `Arc` は必須ではありませんが、より複雑な共有リソースでは非常に有効です。`github_token` も同様に `clone()` で対処しています。

これらの方法で、`async` ブロックが「自分の面倒は自分で見る」ことができるように、必要なデータの所有権を適切に渡すことができ、ライフタイムエラーを解決しました。

#### ハマりポイント3: 堅牢なエラーハンドリングの実現

**問題**: Rustはエラーハンドリングに `Result<T, E>` を使用しますが、コードの規模が大きくなると、どこでどのようなエラーが発生しうるのか、その伝播をどう制御するかが課題になります。開発初期には安易に `unwrap()` や `expect()` を使っていましたが、これは本番環境では絶対に避けたい行為です。

**解決策**:
1.  **`?` 演算子の活用**: `Result` を返す関数内で `?` 演算子を使うことで、`Err` の場合は即座にその `Err` を呼び出し元に伝播させ、`Ok` の場合はその値を取り出す、という強力なイディオムです。これにより、大量の `match` 文を書くことなく、エラー処理を簡潔に記述できます。
2.  **`anyhow` クレートによるエラー伝播**: `anyhow::Result` は、エラーの種類を細かく定義する必要がない場合に非常に便利です。`dyn std::error::Error` を使うことで、様々なエラー型を簡単にラップして伝播させることができます。これはCLIツールのスクリプト的な用途で、エラーメッセージをユーザーに伝えるだけで十分な場合に特に有効です。

    ```rust
    // anyhow を使ったエラー伝播
    use anyhow::Result;

    async fn some_operation() -> Result<u32> {
        // reqwest::Error や serde_json::Error など、様々なエラーが発生しうる
        let resp = reqwest::get("https://example.com/api").await?.text().await?;
        let value: u32 = serde_json::from_str(&resp)?;
        Ok(value)
    }

    #[tokio::main]
    async fn main() -> Result<()> { // main関数もanyhow::Resultを返す
        match some_operation().await {
            Ok(val) => println!("Success: {}", val),
            Err(e) => eprintln!("Error: {:?}", e), // デバッグ情報も表示
        }
        Ok(())
    }
    ```
3.  **`thiserror` クレートによる独自エラー型**: アプリケーション固有のエラーや、より詳細なエラー情報をユーザーに伝えたい場合は、`thiserror` を使って独自のEnumエラー型を定義します。これにより、エラーの原因を明確にし、プログラムの制御フローをより細かく調整できます。

    ```rust
    // thiserror を使った独自エラー型 (イメージ)
    use thiserror::Error;

    #[derive(Error, Debug)]
    enum MyToolError {
        #[error("Failed to fetch repository data: {0}")]
        NetworkError(#[from] reqwest::Error),
        #[error("Failed to parse API response: {0}")]
        ParseError(#[from] serde_json::Error),
        #[error("Repository not found: {0}/{1}")]
        RepoNotFound(String, String),
        // ...その他
    }

    // `fetch_repo_stars` の戻り値を `Result<(String, u32), MyToolError>` に変更
    // エラーハンドリング時に `MyToolError::RepoNotFound` などを返すようにする
    ```

私のツールでは、まず `anyhow` で全体的なエラー伝播をシンプルにし、特に重要で詳細な情報が必要なエラーに対しては、将来的に `thiserror` でカスタムエラー型を導入することを検討しています。

---

### 完成！そして得られた成果と学び：Rustで開発する喜び

数々の壁を乗り越え、ついに「GitHub Star Analyzer CLI」が完成しました！

#### 完成したCLIツールの機能

現在のバージョンでは、主に以下の機能を実現しています。

*   **単一リポジトリのスター数表示**: `star_analyzer rust-lang/rust` のようにコマンドを叩くだけで、現在のスター数を瞬時に表示します。
*   **複数リポジトリの一括表示**: 設定ファイル（YAML形式）で定義した複数のリポジトリのスター数を一括で取得し、リスト形式で表示します。
*   **スター数の日次変動**: 毎日自動実行されるように設定すれば、前日からのスター数の増減を表示できます。
*   **簡易的なグラフ表示**: ターミナル上で過去数日間のスター数の推移をアスキーアートのグラフで表現する機能も実装中です。

#### 得られた成果と学び

このツールを開発したことで、私自身に多くの成果と学びがありました。

1.  **「面倒」からの解放**: 何よりも、手動でスター数を追いかけるという「面倒」な作業から完全に解放されました。ワンコマンドで知りたい情報が手に入る喜びは、想像以上でした。
2.  **Rustへの深い理解**: 所有権、ライフタイム、借用チェッカー、非同期処理、そして強力な型システム。Rustの核心的な概念について、机上の学習だけでは得られなかった深い理解と実践的なスキルを身につけることができました。特に、なぜこれらの概念が必要なのか、どのように問題を解決するのかを体感できたのが大きいです。
3.  **Rustエコシステムの素晴らしさ**: `reqwest`、`tokio`、`serde`、`clap` といったクレート群の完成度の高さには目を見張るものがありました。これらが提供する抽象化は、複雑な処理を簡潔かつ安全に記述することを可能にし、開発効率を大いに高めてくれました。
4.  **CLIツール開発の楽しさ**: ユーザーインタフェースの設計（コマンドライン引数、出力形式）から、エラーハンドリング、パフォーマンス最適化まで、一連のCLIツール開発プロセスを体験できたのは大きな財産です。特に、自分が作ったツールが実際に動いて、日々の作業を助けてくれる瞬間は、何物にも代えがたい喜びがあります。

Rustでの開発は、確かに最初は厳しいですが、コンパイラの「愛あるお叱り」を乗り越えた先には、堅牢で高速、そして何より「動いて当然」という安心感のあるプログラムが待っています。この「Rustで開発する喜び」を、多くの人に体験してほしいと心から思います。

#### 次にやること、そして改善点

完成はしましたが、まだまだ改善の余地はあります。

*   **設定ファイルの強化**: 現在はシンプルなYAML形式ですが、より柔軟な設定（例: GitHub Enterprise Serverのサポート、表示する情報項目など）ができるようにしたいです。
*   **データの永続化**: SQLiteなどの軽量データベースにスター数の履歴を保存し、より長期的な推移分析やトレンド予測を可能にしたいと考えています。
*   **出力オプションの拡充**: CSV/JSON出力のサポートや、よりリッチなターミナルグラフ表示（`plotters` などのクレートも検討）も考えています。
*   **Web UIの追加**: 将来的には、CLIだけでなくWeb UIからもスター数を確認・分析できるような、よりリッチなサービスに発展させるのも面白いかもしれません。
*   **テストの充実**: 今後機能を追加していく上で、網羅的な単体テスト・結合テストを整備し、品質を維持していく必要があります。

このプロジェクトを通して、私はRustという言語の可能性と、プログラミングの楽しさを改めて実感しました。皆さんも、日々の「面倒」を解決する自分だけのツールを、Rustで作ってみませんか？きっと、新しい発見と喜びが待っているはずです！