---
title: "PythonとLangChainで自分だけのAIアシスタントを開発して、業務を爆速化した話"
emoji: "🤖"
type: "tech"
topics: ["python"]
published: false
---

# PythonとLangChainで自分だけのAIアシスタントを開発して、業務を爆速化した話

## 1. はじめに: 繰り返しの業務にうんざり！自分だけのAIアシスタントが欲しかった理由

「またこの作業か…」

私の業務は、データ分析、レポート作成、情報収集など多岐にわたります。その中で、特に時間を消費していたのが「定型的な情報収集と整理」「会議の議事録要約」「簡単なデータの前処理スクリプト作成」といった、ある程度パターン化された作業でした。これらは確かに重要な業務なのですが、毎日毎週繰り返されるたびに、もっと創造的で、人間にしかできない仕事に集中したいというフラストレーションが募っていきました。

特に、新しいプロジェクトが始まるたびに、関連する技術トレンドや市場動向をWebで検索し、複数の情報を比較検討し、要点をまとめて資料に落とし込む作業は、毎回数時間を要していました。ChatGPTのような大規模言語モデル（LLM）が登場したとき、「これだ！」と直感しました。もし、この強力なAIを自分だけの秘書のように使いこなし、日々の定型業務を任せることができれば、私の生産性は劇的に向上するはず。そう考えた私は、PythonとLangChainを使って、自分だけのAIアシスタントを開発することを決意しました。

このプロジェクトを通して、私は単に業務を効率化しただけでなく、LLM開発の面白さ、難しさ、そして可能性を深く体験することになります。この経験が、同じように日々の業務に追われている誰かのヒントになれば幸いです。

## 2. プロジェクト設計と技術選定: 何をどう組み合わせるか？

### 目標設定

まず、私はAIアシスタントに何をさせたいのか、具体的な目標を設定しました。
1.  **情報収集の自動化**: 指定されたキーワードでWeb検索を行い、主要な情報を要約する。
2.  **ドキュメントの要約**: 長いドキュメントや議事録を読み込ませ、重要なポイントを簡潔にまとめる。
3.  **簡単なデータ処理スクリプトの生成**: 「CSVファイルの特定カラムを読み込んで平均を計算するPythonスクリプトを書いて」といった指示でコードを生成する。
4.  **チャット形式での対話**: 自然言語で指示を出し、結果を受け取れる使いやすいインターフェース。

### 技術選定の意思決定プロセス

この目標を達成するために、どのような技術スタックを選ぶべきか、熟考しました。

#### Python (プログラミング言語)
これは私にとって最も自然な選択でした。普段からデータ分析やスクリプト作成でPythonを多用しており、豊富なライブラリと活発なコミュニティはLLM開発においても大きな強みです。学習コストも低く、迅速なプロトタイピングに適しています。

#### LangChain (LLMアプリケーションフレームワーク)
LLMを使ったアプリケーションを開発する上で、LLMの呼び出し、プロンプト管理、外部ツールとの連携、Agentの構築などをゼロから実装するのは非常に骨が折れます。そこで目をつけたのがLangChainです。

*   **なぜLangChainか？**: LangChainは、LLMを「思考するエンジン」とし、様々な「ツール」を組み合わせて複雑なタスクを自動化するAgentの概念を強力にサポートしています。特に、Web検索、計算、ファイル操作など、複数のステップを踏むタスクをLLMに自律的に実行させたい場合に、その設計思想が非常にフィットすると感じました。他のフレームワーク（例: LlamaIndex）も検討しましたが、Agent機能の成熟度と柔軟性からLangChainを選びました。
*   **何ができるか**: プロンプトテンプレートの管理、LLMとの連携（OpenAI, Anthropicなど）、外部APIやデータベースとの接続を抽象化してくれるため、開発者はビジネスロジックに集中できます。

#### OpenAI API (LLMプロバイダー)
高性能なLLMは、AIアシスタントの頭脳そのものです。現状、汎用性と性能のバランスを考えると、OpenAIのGPTシリーズが最適解でした。特にGPT-4は推論能力が高く、複雑な指示にも対応できると期待しました。最初はコストを抑えるためにGPT-3.5-turboから始め、必要に応じてGPT-4に切り替える戦略をとりました。

#### Streamlit (Web UIフレームワーク)
せっかく強力なAIアシスタントを作っても、コマンドラインでしか操作できないのでは、日々の業務で気軽に使うことはできません。直感的で使いやすいUIが必要です。

*   **なぜStreamlitか？**: StreamlitはPythonのコードだけでインタラクティブなWebアプリケーションを驚くほど簡単に作成できます。HTML/CSSやJavaScriptの知識がほとんど不要なため、UI開発に時間をかけたくない私にとって理想的でした。プロトタイプ開発のスピードを最優先する上で、FlaskやDjangoのようなフルスタックフレームワークよりも優位性があると感じました。
*   **何ができるか**: テキスト入力、ボタン、スライダーなどのウィジェットを簡単に配置でき、チャットUIの構築に必要な機能が揃っています。`st.session_state` を使えば、セッション間の状態管理も容易です。

これらの技術を組み合わせることで、私は「PythonでLangChain Agentを構築し、OpenAIのLLMを頭脳に据え、Streamlitで使いやすいチャットインターフェースを提供する」という開発方針を固めました。

## 3. 実装のポイント (1) - LangChainで業務を自動化するAgentを構築する

LangChainのAgentは、LLMに「思考」と「ツール使用」の能力を与えることで、複雑なタスクを自律的に解決させることができます。私のAIアシスタントの心臓部となるのがこのAgentです。

### Agentとは？

Agentは、ユーザーからのプロンプト（指示）を受け取ると、まず「次は何をすべきか？」を考えます。その思考の結果、情報が必要であればWeb検索ツールを使ったり、計算が必要であれば電卓ツールを使ったり、ファイル操作が必要であればファイルI/Oツールを使ったりと、利用可能なツールの中から最適なものを選んで実行します。ツールの実行結果をまた思考に使い、最終的な結論を導き出したり、次のツールを実行したりを繰り返します。

### 私がAgentに持たせたツール

私の業務に必要な機能を洗い出し、以下のツールをAgentに持たせることにしました。

1.  **Web Search Tool**: 特定のキーワードでインターネット上の情報を検索し、その結果を取得します。情報収集の核となるツールです。私はGoogle Serper APIを利用しました。
2.  **Calculator Tool**: 数値計算が必要な場合に利用します。Pythonの式を評価するツールとして実装しました。
3.  **File Reader Tool**: 指定されたパスのファイル内容を読み取ります。議事録やレポートの要約に必要です。
4.  **Python REPL Tool**: 簡単なPythonスクリプトを実行し、その結果を得ます。データ処理スクリプト生成の検証や、データの一時的な操作に便利です。

これらのツールをLangChainの `tools` リストとしてAgentに渡します。

### Agentの構築コード

以下に、基本的なAgentの構築と実行のサンプルコードを示します。今回はシンプルにWeb検索とPython REPL（計算用途）を組み込んだAgentを作成します。

```python
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_community.tools import Tool
from langchain_community.utilities import SerpAPIWrapper
from langchain.chains.conversation.memory import ConversationBufferWindowMemory
from langchain_community.utilities import PythonREPL

# 環境変数の読み込み
load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
os.environ["SERPER_API_KEY"] = os.getenv("SERPER_API_KEY") # Web検索用APIキー

# 1. LLMの準備
llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo")

# 2. ツールの定義
# Web検索ツール
search = SerpAPIWrapper()
tools = [
    Tool(
        name="Search",
        func=search.run,
        description="useful for when you need to answer questions about current events or when you need to get information from the internet."
    )
]

# Python REPL（計算や簡単なスクリプト実行用）
python_repl = PythonREPL()
tools.append(
    Tool(
        name="Python_REPL",
        func=python_repl.run,
        description="useful for when you need to execute Python code. Input should be a valid Python command."
    )
)

# 3. プロンプトテンプレートの定義
# Agentがどのような役割を果たすかを定義する重要な部分です。
# memory_keyはチャット履歴をAgentに渡すために必要です。
prompt_template = PromptTemplate.from_template("""
あなたは、ユーザーの質問に答え、タスクを支援するAIアシスタントです。
必要に応じて以下のツールを使ってください。

{tools}

Human: {input}
Chat History: {chat_history}
{agent_scratchpad}
""")

# 4. メモリの準備 (チャット履歴を保持するため)
memory = ConversationBufferWindowMemory(
    memory_key="chat_history",
    return_messages=True,
    k=5 # 直近5ターン分の会話を保持
)

# 5. Agentの作成
# create_react_agentは、ReAct (Reasoning and Acting) パターンを使用するAgentを作成します。
# これにより、LLMは思考 (Thought) し、行動 (Action) を決定する能力を持ちます。
agent = create_react_agent(llm=llm, tools=tools, prompt=prompt_template)

# 6. AgentExecutorの作成
# AgentExecutorはAgentとツールの実行を管理します。
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    memory=memory, # memoryをagent_executorに渡す
    verbose=True, # 思考プロセスを表示する
    handle_parsing_errors=True # パースエラーをハンドルする
)

# 7. Agentの実行
print("AIアシスタントが起動しました。終了するには 'exit' と入力してください。")
while True:
    user_input = input("あなた: ")
    if user_input.lower() == 'exit':
        break
    try:
        response = agent_executor.invoke({"input": user_input})
        print(f"AIアシスタント: {response['output']}")
    except Exception as e:
        print(f"エラーが発生しました: {e}")

```

このコードを実行すると、`verbose=True` のおかげで、LLMがどのように思考し、どのツールを使い、どのような結果を得て、最終的な回答を生成するかのプロセスが詳細に表示されます。これにより、Agentの挙動をデバッグし、改善していくことができます。

例えば、「今日の日本の株価の終値は？」と質問すると、`Search` ツールを使って最新の情報を取得し、その結果に基づいて回答を生成します。また、「25 * 345 + (100 / 4) の結果は？」と質問すると、`Python_REPL` ツールを使って計算を実行します。

## 4. 実装のポイント (2) - Streamlitで使いやすいチャットUIを作成する

いくら強力なAgentを構築しても、使いにくければ意味がありません。Streamlitを使えば、Pythonの知識だけで直感的なチャットUIを簡単に作成できます。

### UIの要件とStreamlitの選択理由

私がUIに求めたのは、以下の点でした。
*   非技術者でも迷わず使えるシンプルさ
*   自然な対話ができるチャット形式
*   過去の会話履歴を保持できること

Streamlitは、これらの要件をほとんどコードを書かずに実現できるため、まさにうってつけでした。特に、`st.chat_message` や `st.chat_input` といったチャットUIに特化したコンポーネントが用意されている点が魅力的でした。

### チャット履歴の保持

Streamlitで最も重要な機能の一つが `st.session_state` です。これはユーザーセッションごとに状態を保持するための辞書のようなもので、これを使うことでチャット履歴を簡単に管理できます。

### LangChain Agentとの連携

StreamlitのUIからユーザーの入力を受け取り、それをLangChain Agentに渡して処理させ、結果をUIに表示するという流れになります。

以下に、StreamlitでチャットUIを構築し、LangChain Agentと連携させるコードの抜粋を示します。

```python
import streamlit as st
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_community.tools import Tool
from langchain_community.utilities import SerpAPIWrapper
from langchain.chains.conversation.memory import ConversationBufferWindowMemory
from langchain_community.utilities import PythonREPL

# 環境変数の読み込み
load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
os.environ["SERPER_API_KEY"] = os.getenv("SERPER_API_KEY")

# --- LangChain Agentのセットアップ（前述のコードを関数化） ---
@st.cache_resource
def setup_agent():
    llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo")
    search = SerpAPIWrapper()
    tools = [
        Tool(
            name="Search",
            func=search.run,
            description="useful for when you need to answer questions about current events or when you need to get information from the internet."
        )
    ]
    python_repl = PythonREPL()
    tools.append(
        Tool(
            name="Python_REPL",
            func=python_repl.run,
            description="useful for when you need to execute Python code. Input should be a valid Python command."
        )
    )

    prompt_template = PromptTemplate.from_template("""
    あなたは、ユーザーの質問に答え、タスクを支援するAIアシスタントです。
    必要に応じて以下のツールを使ってください。

    {tools}

    Human: {input}
    Chat History: {chat_history}
    {agent_scratchpad}
    """)

    memory = ConversationBufferWindowMemory(
        memory_key="chat_history",
        return_messages=True,
        k=5
    )

    agent = create_react_agent(llm=llm, tools=tools, prompt=prompt_template)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        memory=memory,
        verbose=False, # Streamlit上ではverboseは通常オフにする
        handle_parsing_errors=True
    )
    return agent_executor

# Agentの初期化 (Streamlitアプリの起動時に一度だけ実行されるようにキャッシュ)
agent_executor = setup_agent()

# --- Streamlit UIの構築 ---
st.set_page_config(page_title="私のAIアシスタント", page_icon="🤖")
st.title("🤖 私のAIアシスタント")

# チャット履歴を保持するsession_stateの初期化
if "messages" not in st.session_state:
    st.session_state.messages = []

# 過去のチャット履歴を表示
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ユーザーからの入力を受け取る
if prompt := st.chat_input("何をお手伝いしましょうか？"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("AIが思考中..."):
            try:
                # LangChain Agentを呼び出し
                response = agent_executor.invoke({"input": prompt})
                st.markdown(response["output"])
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")
                response_content = "申し訳ありません、処理中にエラーが発生しました。"
                st.markdown(response_content)
        st.session_state.messages.append({"role": "assistant", "content": response["output"] if 'output' in response else response_content})

```

このコードを `app.py` などのファイル名で保存し、`streamlit run app.py` コマンドで実行すると、ブラウザでチャットインターフェースが立ち上がります。

*   `st.cache_resource` デコレーターを使うことで、Streamlitアプリが再起動するたびにAgentが再初期化されるのを防ぎ、効率的にリソースを使えます。
*   `st.chat_message` を使うことで、ユーザーとAIアシスタントの吹き出しが自動的にスタイル付けされ、自然なチャット形式で表示されます。
*   `st.chat_input` で入力ボックスを提供し、ユーザーがメッセージを送信すると、その内容が `prompt` 変数に格納されます。
*   ユーザーの入力とAIアシスタントの応答は、`st.session_state.messages` に追加され、ページがリロードされても履歴が保持されます。

これにより、私は非常に短時間で、見た目も機能も十分なAIアシスタントのUIを構築することができました。

## 5. ハマったことと解決策: LLM開発は一筋縄ではいかない！

LLMを使った開発は、まさに「魔法」と「現実」の狭間を行き来するようなものでした。デモでは華麗に動くAIが、いざ自分のタスクを任せようとすると、途端に期待通りの動きをしてくれない…そんな壁に何度もぶつかりました。

### ハマったこと (1): プロンプトエンジニアリングの難しさ

**問題**: Agentが提供したツールを適切に使ってくれない、または意図しない挙動をする。
例えば、「最新の〇〇の情報を教えて」と尋ねても、Web検索ツールを使わずに知っている知識だけで答えようとしたり、計算ツールが必要な場面で無理やりテキストで回答しようとしたりすることがありました。

**当時の感情**: 「え、なんでそこでツールを使わないの？」「そこは検索するべきでしょ！」と、まるで新人の部下に指示を出す上司のような気分になりました。LLMの思考プロセスが不透明なため、どこが問題なのか特定するのが困難でした。

**解決策**:
*   **System Messageの強化**: まず、プロンプトの冒頭にAIアシスタントの役割（「あなたはプロフェッショナルなAIアシスタントです」「常にツールを積極的に活用してください」など）を明確に記述し、`tools`の前に配置しました。
*   **ツールの説明を具体的に**: 各 `Tool` の `description` はLLMがツールを選択するための重要な情報源です。「useful for when you need to answer questions about current events or when you need to get information from the internet.」のように、どのような場合にそのツールを使うべきかを詳細かつ明確に記述しました。
*   **思考プロセスの可視化**: `AgentExecutor` の `verbose=True` を有効にして、LLMがどのような `Thought` (思考) を経て `Action` (行動) を決定しているのかを注意深く観察しました。これにより、「なぜこのツールを選んだのか（あるいは選ばなかったのか）」のヒントを得て、プロンプトやツールの説明を修正していきました。
*   **Few-shot Learning (適用外だが考慮)**: 今回は採用しませんでしたが、複雑なタスクの場合、いくつかの具体的な入出力例（Few-shot例）をプロンプトに含めることで、LLMの挙動を誘導できる場合があります。

### ハマったこと (2): APIコストと応答速度

**問題**: Agentが思考やツール使用を繰り返すたびに、何度もLLM APIが呼び出され、コストがかさんだり、応答速度が遅くなったりする。特に `verbose=True` でデバッグしていると顕著でした。

**当時の感情**: 「あれ、こんなにすぐAPIコールが積もるの！？」「応答が遅すぎてストレスだ…」と、使いすぎによる青天井の請求書と、ユーザー体験の悪化に怯えました。

**解決策**:
*   **LLMの選択**: 開発初期段階では `gpt-3.5-turbo` を積極的に利用し、より複雑な推論が必要な箇所や最終的な調整段階でのみ `gpt-4` を使用する運用に切り替えました。gpt-3.5-turboはgpt-4よりもはるかに高速かつ安価です。
*   **プロンプトの最適化**: 無駄な思考やツール呼び出しを減らすため、プロンプトをより簡潔かつ的確に調整しました。例えば、「Yes/No」で答えられる質問に対してLLMが延々と考察しないように、プロンプトで回答形式を制限するなども有効です。
*   **キャッシュの導入**: LangChainにはLLMの応答をキャッシュする機能があります。同じ入力に対してはキャッシュされた結果を返すことで、API呼び出し回数を減らすことができます。これは開発時のデバッグにも非常に役立ちました。
    ```python
    # キャッシュを有効にする例（コードには含めなかったが、重要な解決策）
    # from langchain.globals import set_llm_cache
    # from langchain_community.cache import InMemoryCache
    # set_llm_cache(InMemoryCache()) # インメモリキャッシュ
    # または、より永続的なSQLiteキャッシュ
    # from langchain_community.cache import SQLiteCache
    # set_llm_cache(SQLiteCache(database_path=".langchain.db"))
    ```
*   **`stream=True`の活用（Streamlit UIでのユーザー体験向上）**: Streamlitで応答を表示する際に、LLMの応答をストリーミングで受け取り、リアルタイムで画面に表示することで、体感的な待ち時間を短縮しました。これは完全な解決策ではありませんが、ユーザー体験を大きく改善しました。

### ハマったこと (3): 長文入力時のトークン制限

**問題**: ドキュメントの要約などで、非常に長いテキストをAgentに与えようとすると、LLMのコンテキストウィンドウ（一度に処理できるトークン数）の制限に引っかかる。

**当時の感情**: 「せっかくファイルリーダーツールを作ったのに、読める文字数に制限があるのか…」と、LLMの限界を突きつけられたような気分でした。

**解決策**:
*   **要約ツールの導入**: 長文をそのままLLMに渡すのではなく、まず別のLLMや`RecursiveCharacterTextSplitter`などのツールでテキストを分割し、それぞれのチャンクを要約、さらにそれらの要約を再要約する、といった多段階の要約プロセスをカスタムツールとして実装しました。これにより、長いドキュメント全体を扱えるようになりました。
*   **情報抽出ツールの検討（RAG）**: 今回は実装を見送りましたが、特定の質問に答えるために長文の中から関連する情報だけを効率的に抽出する Retrieval Augmented Generation (RAG) の導入も有効です。これは、文書をベクトルデータベースに格納し、質問に応じて関連性の高いチャンクだけをLLMに渡す手法です。

これらの「ハマったこと」と解決策は、LLM開発が単にAPIを呼び出すだけでなく、プロンプト、ツールの設計、コスト、ユーザー体験といった多角的な視点が必要であることを教えてくれました。

## 6. 成果と今後の展望: 私の業務はこう変わった！

### 具体的な成果

このAIアシスタントを導入したことで、私の業務は劇的に変化しました。

*   **情報収集と資料作成の高速化**: 以前は数時間かかっていた市場動向のリサーチや競合分析が、AIアシスタントにキーワードを渡すだけで、数分で要点と参照元がまとまってくるようになりました。これにより、週に約3〜4時間もの時間短縮が実現しました。その結果、私は情報を「集める」時間よりも「分析し、考察する」時間に集中できるようになりました。
*   **議事録要約の手間削減**: 長い会議の議事録をファイルリーダーツールで読み込ませ、「この議事録の重要事項、決定事項、次のアクションアイテムを箇条書きでまとめて」と指示するだけで、すぐにサマリーが手に入ります。これにより、会議後のドキュメント作成にかかる時間が半減しました。
*   **簡単なスクリプト作成の補助**: データの前処理でちょっとしたPythonスクリプトが必要なとき、「このCSVファイルのカラムXとカラムYの相関係数を計算するPythonコードを書いて」と依頼すれば、すぐにコードの叩き台が生成されます。これにより、ゼロからコードを書き始める手間が省け、スクリプト作成にかかる時間が1/3程度になりました。

### 個人的な変化

単に業務が効率化されただけでなく、私自身の働き方や意識にもポジティブな変化がありました。

*   **創造的な仕事への集中**: 定型作業から解放されたことで、私はより戦略的な思考や、新しいアイデアの創出といった、人間にしかできない付加価値の高い業務に時間を割けるようになりました。
*   **新しいスキルの習得**: LLM開発は、プログラミングスキルだけでなく、プロンプトエンジニアリング、システム設計、デバッグといった多岐にわたるスキルを磨く機会となりました。これは私自身のキャリアアップにも繋がる貴重な経験です。
*   **仕事がもっと楽しくなった！**: 退屈な繰り返しの作業が減り、AIと協働して新しい価値を生み出すプロセスは、仕事に対するモチベーションを大きく向上させてくれました。

### 今後の展望と改善点

現状でも十分な効果が出ていますが、このAIアシスタントはまだまだ進化の余地があります。

*   **RAGによる知識基盤の強化**: 現状のWeb検索だけでは、社内ドキュメントや特定の専門知識には対応できません。社内共有ドキュメントや個人が作成した資料をベクトルデータベースに格納し、それをAgentのツールとして利用するRetrieval Augmented Generation (RAG) を導入することで、アシスタントの知識基盤を大幅に強化したいと考えています。
*   **より複雑なワークフローの自動化**: 現在は比較的単一のタスクに特化していますが、複数のツールを組み合わせて、より複雑な業務プロセス（例: 「特定の顧客データに基づいてパーソナライズされたメールのドラフトを作成し、承認を求める」など）を自動化するAgentの構築を目指します。
*   **マルチモーダル対応**: 将来的には画像や音声などのマルチモーダルな情報も処理できるように拡張し、例えば「このグラフについて分析して」といった指示にも対応できるようにしたいです。
*   **デプロイと共有**: 現在はローカル環境で動かしていますが、DockerizeしてAWS FargateやGoogle Cloud Runのようなクラウドサービスにデプロイし、チームメンバーとも簡単に共有できる形にしたいです。
*   **LLMの多様化とコスト最適化**: OpenAIだけでなく、OSSのLLM（Llama2, Mixtralなど）や他のLLMプロバイダー（Anthropic Claudeなど）も試してみて、タスクに応じた最適なLLMを選択することで、コストと性能のバランスをさらに最適化していきたいです。

「自分が本当に欲しかったもの」を自分の手で作る経験は、単なる技術学習を超えて、仕事のあり方そのものを見つめ直すきっかけとなりました。もしあなたが日々の業務にうんざりしているなら、ぜひ自分だけのAIアシスタント開発に挑戦してみてください。きっと、その一歩があなたの業務、そしてあなたの働き方を大きく変えるはずです。