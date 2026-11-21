# Architecture Conference 2026 ハンズオン: Workcation & Smart Travel Concierge (Google ADK 2.0)

本リポジトリは、Architecture Conference 2026 ワークショップ向けのハンズオン教材です。
Python 3.13 と **Google Agent Development Kit (ADK) 2.0 (`v2.15.0`)** および **`google-agents-cli` (`v1.15.0`)** を用い、単一 LLM エージェントによるプロトタイプ（Step 1）から、決定論的な Python ノード・並列実行・Human-in-the-Loop (HITL) 承認ゲートを統合したハイブリッド `Workflow` アーキテクチャ（Step 2）、そして評価とデプロイ（Step 3）までを段階的に構築・検証します。

システムアーキテクチャの詳細設計やシーケンス図については [doc/design.md](doc/design.md) を参照してください。

---

## 1. ディレクトリ構成

`uv run adk web .` をリポジトリルートで実行した際に各ステップのエージェントがそのまま検出されるよう、トップレベルにエージェントパッケージを配置しています。

```text
.
├── .env_example                         # Vertex AI ADC 環境変数テンプレート
├── LICENSE                              # Apache 2.0 ライセンス
├── pyproject.toml                       # Python 3.13 / uv / ruff / pytest / ty 設定
├── README.md                            # ハンズオン手順・リポジトリ概要（本ファイル）
├── doc/
│   └── design.md                        # アーキテクチャ設計書・Mermaid 図・状態契約
├── docs/
│   ├── index.html                       # Web 公開用インタラクティブ ハンズオンガイド (Codelab 形式)
│   └── qwiklabs_setup_guide.md          # Qwiklabs クラスルーム構築・運営ガイド
├── skills/
│   └── travel-policy/
│       └── SKILL.md                     # 社内出張・ワーケーション規定スキル (SkillToolset 用)
├── src/
│   └── workcation_concierge/
│       ├── __init__.py
│       ├── schemas.py                   # Pydantic v2 入出力スキーマ (TripRequest 等)
│       ├── mcp_server.py                # Travel SaaS MCP サーバー & カタログ計算関数
│       ├── guardrails.py                # before_tool_callback による決定論的ガードレール
│       └── skill_loader.py              # ADK SkillToolset ローダー
├── step1_basic_agent/
│   ├── __init__.py
│   └── agent.py                         # Step 1: 単一 LlmAgent + SkillToolset + Callback
├── step2_starter/
│   ├── __init__.py
│   └── agent.py                         # Step 2 ハンズオン用スターターテンプレート (TODO 付き)
├── step2_workflow_agent/
│   ├── __init__.py
│   └── agent.py                         # Step 2 完成版: ADK 2.0 Hybrid Workflow
├── eval/
│   └── workcation_eval.json             # Step 3: agents-cli eval 用評価データセット
└── tests/
    ├── unit/
    │   ├── test_mcp_catalog.py          # フライト・ホテル検索・精算計算の単体テスト
    │   ├── test_guardrails.py           # before_tool_callback ガードレールの単体テスト
    │   └── test_workflow_nodes.py       # Workflow 関数ノード・HITL 承認ゲートの単体テスト
    └── integration/
        └── test_agents_wiring.py        # Step 1 / Step 2 エージェント統合・配線テスト
```

---

## 2. クイックスタート (Vertex AI ADC & uv)

本ハンズオンでは、Gemini API キーではなく **Google Cloud Vertex AI の Application Default Credentials (ADC)** を使用します。また、モデルには高度な推論を担う `gemini-4-neon`（Step 1 単一エージェントおよび Step 2 対話ヒアリング）と、高速・高効率なエージェント実行を担う `gemini-4-hydrogen`（候補検索・予約実行）を使用します。

### 2.1 Google Cloud 認証と環境変数の設定

```bash
gcloud auth application-default login
cp .env_example .env
```

`.env` ファイルをエディタで開き、ご自身の Google Cloud プロジェクト ID を設定してください（`gemini-4-hydrogen` / `gemini-4-neon` は Vertex AI の `global` エンドポイントを使用します）。

```ini
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=global
```

### 2.2 依存関係のインストールとテスト実行

Python 3.13 と `uv`（明示的な PyPI インデックス指定）を使用して仮想環境を同期します。

```bash
uv sync --dev --index https://pypi.org/simple --python /usr/bin/python3.13
```

単体テスト・結合テスト、および静的解析（`ruff` / `ty`）を実行して環境が正常であることを確認します。

```bash
uv run --no-sync --python /usr/bin/python3.13 pytest
uv run --no-sync --python /usr/bin/python3.13 ruff format --check .
uv run --no-sync --python /usr/bin/python3.13 ruff check .
uv run --no-sync --python /usr/bin/python3.13 ty check
```

---

## 3. ハンズオン ステップ別コマンド

### Step 1: 単一エージェント + Skills + 決定論的 Callback ガードレール

[step1_basic_agent/agent.py](step1_basic_agent/agent.py) では、`gemini-4-neon` を用いた単一エージェントに以下の3つを組み合わせています。
1. **SkillToolset** ([skills/travel-policy/SKILL.md](skills/travel-policy/SKILL.md)): 社内の出張・ワーケーション規定（通信速度 50 Mbps 以上、一般社員のスイート・ビジネスクラス禁止、150,000 円上限など）をオンデマンドで注入。
2. **Travel SaaS MCP ツール群** ([src/workcation_concierge/mcp_server.py](src/workcation_concierge/mcp_server.py)): フライト検索・ホテル検索・予約実行ツール。
3. **`before_tool_callback`** ([src/workcation_concierge/guardrails.py](src/workcation_concierge/guardrails.py)): 外部 SaaS である MCP サーバーにリクエストが送信される直前に、クライアント側でグレード違反や予算超過（`total_jpy > state["approved_limit_jpy"]`）を 100% ブロック。

#### Web UI で体験する
```bash
uv run --no-sync --python /usr/bin/python3.13 adk web .
```
ブラウザで `step1_basic_agent` を選択し、以下のプロンプトを試してください。
- 通常予算内（札幌 2泊 = 59,000 円）: `札幌で2泊のワーケーションをエコノミー・スタンダードルームで予約して`
- 規定違反ブロック（スイートルーム指定）: `沖縄で3泊、スイートルームに泊まるワーケーションを予約して`
- 予算超過ブロック（ハワイ 4泊 = 242,000 円 > 150,000 円）: `ハワイで4泊のワーケーションを予約して`

#### CLI デモスクリプトで体験する
```bash
uv run --no-sync --python /usr/bin/python3.13 -m step1_basic_agent.agent
```

---

### Step 2: ADK 2.0 Hybrid `Workflow` による確定制御と Human-in-the-Loop 承認

Step 1 の単一エージェントでは、ハワイ（242,000 円）のような予算超過プランを柔軟に上長承認へ回し、`Session.state["approved_limit_jpy"]` を動的に引き上げて予約を完了させるフローを確率的なプロンプトだけで制御するのは困難です。

Step 2 では、ADK 2.0 の `Workflow` グラフを用いて以下を実装します。
- ハンズオン作業用スターター: [step2_starter/agent.py](step2_starter/agent.py)
- 完成版リファレンス実装: [step2_workflow_agent/agent.py](step2_workflow_agent/agent.py)

#### ワークフロー構成
1. **`intake_agent`** (`mode="task"`, `output_schema=TripRequest`, `gemini-4-neon`): ユーザーの要望から都市・泊数・クラスを高度な推論で構造化抽出。
2. **並列 Fan-Out + `JoinNode("join_research")`**:
   - `fetch_workcation_metrics`: Python 関数ノードで対象都市の Wi-Fi 速度とコワーキング環境を取得（0 LLM トークン）。
   - `search_agent` (`mode="single_turn"`, `output_schema=CandidatePlan`, `gemini-4-hydrogen`): 最安のフライト・ホテル候補を高速抽出。
3. **`calculate_and_route`** (決定論的 Python `FunctionNode`): LLM に計算を任せず Python で正確な合計金額を算出し、`<= 150,000 JPY` なら `route="auto_book"`、`> 150,000 JPY` なら `route="needs_approval"` へ分岐。
4. **`manager_approval_gate`** (`RequestInput` HITL ゲート): 予算超過時にワークフローを一時停止し、上長が承認すると `Session.state["approved_limit_jpy"]` を新しい承認額（例: 250,000 円）に更新して `booking_agent` へルーティング。
5. **`booking_agent`** (`gemini-4-hydrogen` + `enforce_booking_guardrail`): 更新された `approved_limit_jpy` の範囲内で安全に `reserve_itinerary` を実行。

#### Web UI で Step 2 ワークフローを実行する
```bash
uv run --no-sync --python /usr/bin/python3.13 adk web .
```
ブラウザで `step2_workflow_agent`（または実装後の `step2_starter`）を選択し、札幌（自動予約ルート）とハワイ（上長承認 HITL ルート）の両方を試してください。

---

### Step 3: 継続的評価 (`eval`) と Reasoning Engine / Cloud Run デプロイ

[eval/workcation_eval.json](eval/workcation_eval.json) には、予算内の自動予約シナリオ、グレード違反のブロックシナリオ、および予算超過時の上長承認エスカレーションシナリオが含まれています。

#### 1. ADK CLI / agents-cli による評価の実行
```bash
uv run --no-sync --python /usr/bin/python3.13 adk eval step2_workflow_agent eval/workcation_eval.json
uv run --no-sync --python /usr/bin/python3.13 agents-cli eval run --app-name step2_workflow_agent --dataset eval/workcation_eval.json
```

#### 2. Vertex AI Agent Runtime (Agent Engine) / Cloud Run へのデプロイ（参考コマンド）
```bash
uv run --no-sync --python /usr/bin/python3.13 agents-cli deploy \
  --deployment-target agent_runtime \
  --project "${GOOGLE_CLOUD_PROJECT}" \
  --region us-central1 \
  --env-vars "GOOGLE_CLOUD_LOCATION=global" \
  --service-name "workcation-concierge-workflow"
```
