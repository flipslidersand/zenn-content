---
title: "Goと標準ライブラリだけでWeb APIクライアントCLIツールを作ってみたら、データ連携が爆速になった話"
emoji: "⚙️"
type: "tech"
topics: ["go"]
published: false
---

## Goと標準ライブラリだけでWeb APIクライアントCLIツールを作ってみたら、データ連携が爆速になった話

皆さん、日々の業務で「これ、手作業でやってるの無駄じゃないか？」と感じる瞬間はありませんか？
私はまさにその渦中にいました。複数のWeb APIからデータを取得し、整形して、別のシステムに流し込む。この一連の作業が、毎日、毎時間、手動で行われていたのです。膨大な時間を浪費し、ヒューマンエラーのリスクに怯える日々。そんな状況を打破すべく、私はGo言語と標準ライブラリの力を借りて、Web APIクライアントCLIツール開発に踏み切りました。その結果、データ連携は文字通り「爆速」になり、私の業務は劇的に改善されました。

この記事では、私がどのようにしてこのCLIツールを開発したのか、その設計思想、実装のポイント、そしてハマった落とし穴と解決策を、Goの標準ライブラリの魅力と共にお伝えしたいと思います。

---

### 1. 「あの手作業、Goで自動化できないかな？」僕がCLIツール開発に踏み切ったワケ

私の業務では、複数のSaaSプロダクトや社内システムが提供するWeb APIからデータを収集し、それらを組み合わせてレポートを作成したり、別のシステムに登録したりする作業が日常的に発生していました。具体的には、

1.  サービスAのAPIからユーザーリストを取得
2.  サービスBのAPIから特定のユーザーの行動ログを取得
3.  サービスCのAPIから決済情報を取得
4.  これらを突合し、必要な情報を抽出し、CSV形式で出力
5.  そのCSVファイルを別のシステムにアップロード

…といった具合です。この一連の作業は、APIキーを貼り付け、認証トークンを取得し、PostmanやブラウザのDeveloper ToolsでAPIエンドポイントを叩き、返ってきたJSONを手動でコピー＆ペーストし、Excelで整形するという、非常に地道で時間のかかるものでした。

一度の作業で数時間かかることも珍しくなく、毎日繰り返されるこの作業に、私は疑問を抱かずにはいられませんでした。「これ、絶対自動化できるはずだ。もっと効率的にできないものか？」

そこで白羽の矢が立ったのが、Go言語です。これまでも簡単なスクリプトはPythonなどで書いていましたが、より本格的なツールとして、高速性、堅牢性、そして何よりも「手軽な配布」を考慮すると、Goが最適だと感じました。特に、CLIツールとして単一バイナリで配布できる点は、チーム内で共有する上で非常に大きなメリットです。

---

### 2. 設計思想と技術選定：Goの「標準ライブラリ最強説」を信じてみる

CLIツール開発にGoを採用することは決まりましたが、次に考えたのは「どのように作るか」です。私の設計思想はシンプルでした。

*   **単一バイナリでどこでも動く**: 依存関係を最小限に抑え、簡単に配布・実行できるようにする。
*   **高速に動作する**: 複数APIからの同時データ取得など、並行処理を積極的に活用する。
*   **堅牢性**: エラーハンドリングをしっかり行い、予期せぬ中断を防ぐ。
*   **学習コストの低減**: チームメンバーがコードを理解しやすいように、複雑な外部ライブラリは極力避ける。

この思想を支えるべく、技術選定においてはGoの「標準ライブラリ最強説」を信じることにしました。

**なぜ外部ライブラリを避けたのか？**

Goには、HTTPクライアントやJSONパースなど、Web APIクライアントに必要な機能が標準ライブラリにほぼ全て揃っています。外部ライブラリを使えば、より簡潔に書けたり、便利な機能が提供されたりすることもありますが、今回は以下の理由から標準ライブラリを優先しました。

1.  **依存関係の最小化**: 外部ライブラリが増えるほど、依存関係の管理が複雑になり、セキュリティリスクやビルド時間の増加に繋がります。標準ライブラリのみであれば、Goのバージョンアップに追従するだけで済みます。
2.  **バイナリサイズ**: 不要な外部ライブラリを含まないことで、生成される実行ファイルのサイズを小さく保てます。
3.  **パフォーマンス**: 標準ライブラリはGoの開発チームによって最適化されており、非常に高いパフォーマンスを発揮します。
4.  **安定性**: 言語に付属するものであるため、その安定性と信頼性は非常に高いです。

**選定した標準ライブラリ**

*   `net/http`: HTTPリクエストの送信、レスポンスの受信
*   `encoding/json`: JSONデータのエンコード、デコード
*   `sync`: 並行処理の同期（`WaitGroup`、`Mutex`など）
*   `fmt`: 入出力、フォーマット
*   `os`: 環境変数、コマンドライン引数、ファイル操作
*   `io`: 入出力インターフェース
*   `time`: タイムアウト設定など

これらの標準ライブラリだけで、私が求めていたCLIツールは十分に構築可能だと判断しました。

---

### 3. 実装のポイント：goroutineとchannelで「待たない」APIコールを実現する

いよいよ実装です。複数のAPIからデータを取得するという要件を満たすため、Goの真骨頂である並行処理、つまり`goroutine`と`channel`をフル活用することにしました。これにより、各APIからの応答を**同時に待つ**ことができ、「待たない」APIコールを実現します。

具体的な処理の流れは以下の通りです。

1.  **APIエンドポイントリストの定義**: 取得したいAPIのURLや認証情報などを構造体として定義。
2.  **goroutineの起動**: 各APIエンドポイントごとに`goroutine`を起動し、それぞれが独立してAPIコールを実行。
3.  **結果の収集**: `channel`を使って、各`goroutine`が取得したデータ（またはエラー）をメインの`goroutine`に送信。
4.  **処理の待機**: `sync.WaitGroup`を使って、全ての`goroutine`が完了するまでメインの`goroutine`は待機。
5.  **データ整形**: 収集したデータを加工し、最終的な出力形式にまとめる。

以下に、複数のAPIから並行してデータを取得し、結果を結合する簡単な例を示します。

```go
package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"sync"
	"time"
)

// APIから取得するデータ構造を定義
type User struct {
	ID   int    `json:"id"`
	Name string `json:"name"`
}

type Order struct {
	OrderID   string `json:"order_id"`
	UserID    int    `json:"user_id"`
	Amount    int    `json:"amount"`
	Timestamp string `json:"timestamp"`
}

// ユーザーデータと注文データを結合した構造体
type UserOrder struct {
	User
	Orders []Order
}

// 複数のAPIエンドポイントからデータを取得する関数
func fetchAPI(url string, client *http.Client) ([]byte, error) {
	resp, err := client.Get(url)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch %s: %w", url, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API request failed with status %d for %s", resp.StatusCode, url)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response body for %s: %w", url, err)
	}
	return body, nil
}

func main() {
	// 実際にはAPIキーや認証トークンなどをここで設定する
	// 今回はダミーのJSONを返す簡易Webサーバーを想定

	httpClient := &http.Client{
		Timeout: 10 * time.Second, // タイムアウト設定は重要！
	}

	userAPIURL := "http://localhost:8080/users"
	orderAPIURL := "http://localhost:8080/orders"

	var wg sync.WaitGroup
	// ユーザーデータを格納するチャネル
	userChan := make(chan struct {
		data []User
		err  error
	}, 1) // バッファ付きチャネル

	// 注文データを格納するチャネル
	orderChan := make(chan struct {
		data []Order
		err  error
	}, 1) // バッファ付きチャネル

	wg.Add(1)
	go func() {
		defer wg.Done()
		body, err := fetchAPI(userAPIURL, httpClient)
		if err != nil {
			userChan <- struct {
				data []User
				err  error
			}{nil, err}
			return
		}
		var users []User
		err = json.Unmarshal(body, &users)
		userChan <- struct {
			data []User
			err  error
		}{users, err}
	}()

	wg.Add(1)
	go func() {
		defer wg.Done()
		body, err := fetchAPI(orderAPIURL, httpClient)
		if err != nil {
			orderChan <- struct {
				data []Order
				err  error
			}{nil, err}
			return
		}
		var orders []Order
		err = json.Unmarshal(body, &orders)
		orderChan <- struct {
			data []Order
			err  error
		}{orders, err}
	}()

	// すべてのgoroutineの完了を待つ
	wg.Wait()
	close(userChan) // チャネルを閉じる
	close(orderChan)

	// 結果の収集
	userResult := <-userChan
	orderResult := <-orderChan

	if userResult.err != nil {
		fmt.Printf("Error fetching users: %v\n", userResult.err)
		return
	}
	if orderResult.err != nil {
		fmt.Printf("Error fetching orders: %v\n", orderResult.err)
		return
	}

	users := userResult.data
	orders := orderResult.data

	// データを結合する
	userOrdersMap := make(map[int]UserOrder)
	for _, u := range users {
		userOrdersMap[u.ID] = UserOrder{User: u, Orders: []Order{}}
	}
	for _, o := range orders {
		if uo, ok := userOrdersMap[o.UserID]; ok {
			uo.Orders = append(uo.Orders, o)
			userOrdersMap[o.UserID] = uo // mapに構造体を代入し直す必要がある
		}
	}

	// 最終結果の出力
	fmt.Println("--- Combined Data ---")
	for _, uo := range userOrdersMap {
		fmt.Printf("User ID: %d, Name: %s\n", uo.ID, uo.Name)
		for _, order := range uo.Orders {
			fmt.Printf("  - Order ID: %s, Amount: %d, Timestamp: %s\n", order.OrderID, order.Amount, order.Timestamp)
		}
	}
}

// 簡易Webサーバー（テスト用）
// このコードとは別に実行してください
/*
package main

import (
	"encoding/json"
	"log"
	"net/http"
	"time"
)

type User struct {
	ID   int    `json:"id"`
	Name string `json:"name"`
}

type Order struct {
	OrderID   string `json:"order_id"`
	UserID    int    `json:"user_id"`
	Amount    int    `json:"amount"`
	Timestamp string `json:"timestamp"`
}

func main() {
	http.HandleFunc("/users", func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(500 * time.Millisecond) // APIの遅延をシミュレート
		users := []User{
			{ID: 1, Name: "Alice"},
			{ID: 2, Name: "Bob"},
			{ID: 3, Name: "Charlie"},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(users)
	})

	http.HandleFunc("/orders", func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(800 * time.Millisecond) // APIの遅延をシミュレート
		orders := []Order{
			{OrderID: "A001", UserID: 1, Amount: 1000, Timestamp: "2023-01-01"},
			{OrderID: "A002", UserID: 2, Amount: 2500, Timestamp: "2023-01-02"},
			{OrderID: "A003", UserID: 1, Amount: 500, Timestamp: "2023-01-03"},
			{OrderID: "A004", UserID: 3, Amount: 3000, Timestamp: "2023-01-04"},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(orders)
	})

	log.Println("Starting server on :8080")
	log.Fatal(http.ListenAndServe(":8080", nil))
}
*/
```

このコードでは、`userAPIURL`と`orderAPIURL`へのリクエストを別々の`goroutine`で並行して実行しています。各`goroutine`は`channel`を通じて結果を返し、メインルーチンは`WaitGroup`で全ての`goroutine`が完了するのを待ってから結果を処理します。これにより、直列にAPIを叩くよりも圧倒的に早くデータ取得が完了します。

---

### 4. 「あれ、データ来ないぞ…？」Go開発でハマった落とし穴と解決策

Goでの並行処理は非常に強力ですが、いくつかハマりやすいポイントがありました。私が経験した「あれ、データ来ないぞ…？」という事態と、その解決策を共有します。

#### 落とし穴1: goroutineが完了する前にメインルーチンが終わってしまう

**現象**: 複数の`goroutine`を起動したのに、期待するデータが一部しか表示されない、あるいは全く表示されずにプログラムが終了してしまう。

**原因**: `goroutine`はバックグラウンドで実行されるため、メインルーチンは`goroutine`の完了を待たずに次の処理（あるいはプログラム終了）に進んでしまいます。

**解決策**: `sync.WaitGroup`を使う。
`WaitGroup`は、複数の`goroutine`の完了を待機するための仕組みです。

*   `wg.Add(n)`: 待機する`goroutine`の数を指定します。
*   `wg.Done()`: `goroutine`が完了したときに呼び出します（`defer`で呼び出すのが一般的）。
*   `wg.Wait()`: 全ての`goroutine`が`Done()`を呼び出すまで、メインルーチンをブロックします。

```go
// 解決策の例（上記コードから抜粋）
var wg sync.WaitGroup // WaitGroupを宣言

wg.Add(1) // ユーザーAPI取得のgoroutineを待つ
go func() {
    defer wg.Done() // goroutine終了時にDone()を呼ぶ
    // ... APIコール処理 ...
}()

wg.Add(1) // 注文API取得のgoroutineを待つ
go func() {
    defer wg.Done() // goroutine終了時にDone()を呼ぶ
    // ... APIコール処理 ...
}()

wg.Wait() // 全てのgoroutineが完了するまで待機
```

これで「データが来る前にプログラムが終了する」という事態は避けられます。

#### 落とし穴2: HTTPクライアントのタイムアウト設定を忘れてハングアップ

**現象**: 特定のAPIが応答しない、あるいはネットワークが不安定なときに、CLIツールが永遠に待ち続けてしまう。

**原因**: `net/http`のデフォルトの`http.Client`は、リクエストに対するタイムアウトが設定されていません。つまり、サーバーが無応答の場合、いつまでも接続を試み続けるか、応答を待ち続けます。

**解決策**: `http.Client`に`Timeout`を設定する。

```go
// 解決策の例（上記コードから抜粋）
httpClient := &http.Client{
    Timeout: 10 * time.Second, // 10秒でタイムアウトするように設定
}

// あるいは、DialerやTLSHandshakeTimeoutなど、より詳細なタイムアウト設定も可能
// httpClient := &http.Client{
//     Transport: &http.Transport{
//         DialContext: (&net.Dialer{
//             Timeout:   5 * time.Second,
//             KeepAlive: 30 * time.Second,
//         }).DialContext,
//         TLSHandshakeTimeout: 5 * time.Second,
//         ResponseHeaderTimeout: 10 * time.Second,
//         ExpectContinueTimeout: 1 * time.Second,
//     },
//     Timeout: 20 * time.Second, // 全体のタイムアウト
// }
```
これにより、無応答のAPI呼び出しによってツールがフリーズすることを防ぎ、適切なエラーハンドリングを行うことができます。

#### 落とし穴3: JSONの構造体マッピングで型が合わない

**現象**: APIからJSONデータが返ってきているはずなのに、Goの構造体に`Unmarshal`すると値が空になったり、エラーが発生したりする。

**原因**:
*   JSONフィールド名とGoの構造体のフィールド名（または`json:"..."`タグ）が一致していない。
*   JSONの値の型とGoの構造体のフィールドの型が一致していない（例: JSONでは数値だが、Goでは文字列型で受け取ろうとしている）。
*   JSONデータが配列なのに、単一の構造体で受け取ろうとしている。

**解決策**:
*   `json:"field_name"`タグを正確に記述する。
    *   例: `json:"snake_case_field"`とJSONにある場合、`SnakeCaseField string `json:"snake_case_field"`で受け取る。
*   `json.Unmarshal`がエラーを返さない場合でも、`log.Printf("%+v\n", yourStruct)`などで構造体の中身をデバッグ出力し、期待通りの値が入っているか確認する。
*   `interface{}`や`map[string]interface{}`で一度受け取り、その内容を`fmt.Printf("%#v\n", data)`などで確認してから、適切な構造体を設計する。
*   `json-to-go` (https://mholt.github.io/json-to-go/) のようなツールを使って、JSON文字列からGoの構造体を自動生成すると非常に便利です。

これらの落とし穴を乗り越えることで、Goの並行処理と標準ライブラリの力を最大限に引き出すことができました。

---

### 5. 成果と学び：「手動でのポチポチ」から「一発コマンド」へ、そしてGoの奥深さ

このCLIツールを開発して得られた成果は、私にとって非常に大きなものでした。

**手動でのポチポチ作業からの解放**
最も劇的な変化は、間違いなくこれです。毎日数時間かけて行っていたAPIからのデータ取得、整形、結合、出力、アップロードという一連の作業が、**たった一本のコマンド実行**で完了するようになりました。

```bash
$ my-api-tool fetch --report-type daily-summary > daily_report.csv
$ s3cmd put daily_report.csv s3://my-bucket/
```

こんな感じで、一連のタスクが自動化されたのです。

**データ連携の爆速化**
並行処理を取り入れたことで、複数のAPIからのデータ取得が同時に行われ、全体の処理時間が大幅に短縮されました。以前は直列に処理していたため、APIの数に比例して時間がかかっていましたが、今ではほとんど待ち時間を感じません。まさに「爆速」と呼ぶにふさわしい速度でデータが連携されるようになりました。

**ヒューマンエラーの激減**
手作業でのコピペやExcelでの加工は、どうしてもミスがつきものです。しかし、ツールとして自動化されたことで、このヒューマンエラーのリスクがほぼゼロになりました。常に正確で一貫性のあるデータが出力される安心感は、想像以上に大きかったです。

**Goと標準ライブラリの奥深さ**
このプロジェクトを通じて、Goの設計思想と標準ライブラリの質の高さを改めて実感しました。

*   **`goroutine`と`channel`**: これほど強力で、かつ手軽に使える並行処理の仕組みは他になかなかありません。複雑な同期処理も、Goの提供するプリミティブを使えば安全かつ簡潔に記述できることを学びました。
*   **`net/http`**: 高機能で使いやすいHTTPクライアントが標準で提供されていることに感動しました。リクエストヘッダーの操作、レスポンスの処理、タイムアウト設定など、Web APIクライアントに必要なあらゆる機能が詰まっています。
*   **`encoding/json`**: JSONのエンコード・デコードも非常に高速で、構造体へのマッピングも直感的です。
*   **単一バイナリ**: `go build`コマンド一つで実行可能なバイナリが生成され、これをどこにでもデプロイできる手軽さは、CLIツール開発において最高のメリットです。

### 次にやること、そして改善点

現状のツールでも十分な成果を得られましたが、さらに使いやすく、堅牢にするための改善点もいくつか見えています。

*   **設定ファイルの外部化**: 現在はGoのコード内にAPIエンドポイントや認証情報が記述されていますが、YAMLやTOML形式の設定ファイルを読み込むようにすることで、ツールの汎用性を高めます。`gopkg.in/yaml.v2`や`github.com/BurntSushi/toml`といった外部ライブラリを検討します。
*   **エラーリトライ処理**: APIが一時的に不安定な場合を考慮し、指数バックオフなどを利用したリトライ処理を導入します。
*   **出力形式の多様化**: 現在は標準出力にCSV形式で出力していますが、直接Excelファイル (`github.com/xuri/excelize/v2`) や別のデータベース (`database/sql`) に書き込む機能も追加したいと考えています。
*   **CLIフレームワークの導入**: 今回は`flag`パッケージで簡単なコマンドライン引数を処理しましたが、より複雑なサブコマンドやオプションを扱うには、`github.com/spf13/cobra`や`github.com/urfave/cli`といったCLIフレームワークの導入も視野に入れています。
*   **テストの拡充**: モックサーバーを使った単体テストや、E2Eテストを拡充し、ツールの品質をさらに高めていきます。

Goと標準ライブラリだけで、これほどまでに業務を改善できるCLIツールが作れるとは、開発を始める前は想像していませんでした。もし皆さんも「この手作業、Goで自動化できないかな？」と感じているなら、ぜひGoの標準ライブラリの扉を開いてみてください。きっと、新たな発見と効率化の道が待っているはずです。