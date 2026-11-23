# Architecture Conference 2026 ハンズオン: Workcation & Smart Travel Concierge (Google ADK 2.0)

本リポジトリは、Architecture Conference 2026 ワークショップ **「Agent Development Kit（ADK）2.0 と Google Cloud で学ぶ！AI エージェント開発」** のハンズオン教材です。

Python 3.13 と **Google Agent Development Kit (ADK) 2.0 (`v2.15.0`)**、コーディングエージェント **Antigravity (`agy`)**、および **`google-agents-cli` (`v1.15.0`)** を用い、以下の 4 ステップで本番グレードの AI エージェント開発を段階的に体験します。

1. **Step 0 (`step0_minimal_agent`)**: 約 25 行の最小構成エージェントで `Agent`・`SessionService`・`Runner` の基本構造を学ぶ
2. **Step 1 (`step1_basic_agent`)**: 本物の `McpToolset`（stdio 接続）と `SkillToolset` を連携し、「プロンプトによる禁止が突破される失敗」を体験した上で 20 行の `before_tool_callback` による決定論的遮断を実装する
3. **Step 2 (`step2_starter` / `step2_workflow_agent`)**: `agy`（またはエディタ）で並列調査・0-LLM 確定金額分岐・日本語対話による上長承認タスク（`mode="task"` + `Session.state` 更新）を備えた ADK 2.0 `Workflow` を構築する
4. **Step 3 (`eval/` & `Dockerfile`)**: `agents-cli eval run` で経路評価を実行し、`agents-cli deploy` で Agent Runtime へデプロイして Google Cloud コンソールの **プレイグラウンド（Playground）** 画面からクラウド上のエージェントと対話する

システムアーキテクチャの詳細設計やシーケンス図は [doc/design.md](doc/design.md) を参照してください。

---

## 1. ディレクトリ構成

```text
.
├── .env_example                         # Vertex AI ADC 環境変数テンプレート
├── agents-cli-manifest.yaml             # agents-cli v1.15 デプロイ定義
├── Dockerfile                           # Agent Runtime コンテナビルド定義
├── pyproject.toml                       # Python 3.13 / uv / ruff / pytest / ty 設定
├── doc/
│   └── design.md                        # アーキテクチャ設計書・Mermaid 図
├── docs/
│   ├── index.html                       # Web 公開用ハンズオン手順書 (Codelab 形式)
│   └── images/                          # Cloud Shell / adk web / Workflow / Playground 図解
├── skills/
│   └── travel-policy/SKILL.md           # 社内旅費規定スキル (SkillToolset 用)
├── src/workcation_concierge/
│   ├── schemas.py                       # Pydantic v2 入出力スキーマ
│   ├── mcp_server.py                    # Travel SaaS MCP サーバー (FastMCP / stdio & StreamableHTTP)
│   ├── mcp_client.py                    # McpToolset (stdio / StreamableHTTP 切替) 接続ヘルパー
│   ├── guardrails.py                    # before_tool_callback 決定論的ガードレイル (再計算検証付)
│   └── skill_loader.py                  # ADK SkillToolset ローダー
├── step0_minimal_agent/                 # Step 0: 最小構成エージェント (基礎理解用)
├── step1_basic_agent/                   # Step 1: プロンプト突破体験 & Callback 配線演習
├── step2_starter/                       # Step 2: Workflow 実装スターター (TODO 2箇所)
├── step2_workflow_agent/                # Step 2 完成版 + Agent Runtime プレイグラウンド用アダプタ
├── eval/
│   └── workcation_eval.json             # Step 3: 自動評価データセット
└── tests/                               # 単体テスト・結合テスト (全 19 件)
```

---

## 2. セットアップ (Cloud Shell / ローカル共通)

本教材は API キーを使用せず、**Vertex AI Application Default Credentials (ADC)** と `global` エンドポイント上の `gemini-4-neon` / `gemini-4-hydrogen` を使用します。

```bash
export GOOGLE_CLOUD_PROJECT=$(gcloud config get-value project)
export GOOGLE_CLOUD_LOCATION=global
export GOOGLE_GENAI_USE_VERTEXAI=TRUE

cp .env_example .env
sed -i "s/your-gcp-project-id/${GOOGLE_CLOUD_PROJECT}/g" .env

uv sync --dev --index https://pypi.org/simple --python python3.13
uv run pytest -v
```

---

## 3. 各ステップの実行コマンド

### Step 0 & Step 1 & Step 2: ADK Web UI の起動
```bash
uv run adk web . --host 0.0.0.0 --port 8000 --allow_origins '*'
```
- **Step 0**: 左上のプルダウンで `step0_minimal_agent` を選択し、「札幌で2泊する場合のWi-Fi速度と費用を教えて」→「もし3泊に延ばしたらいくらになる？」と続けて質問して `Events` / `State` タブを確認します。
- **Step 1**: `step1_basic_agent` を選択し、口頭承認を装うスイートルーム予約プロンプトでプロンプト突破を確認した後、`step1_basic_agent/agent.py` 61 行目の `before_tool_callback=None` を `enforce_booking_guardrail` に変更して 100% ブロックを確認します。
- **Step 2**: `uv run agents-cli setup` 実行後、`step2_starter/agent.py` の 2 つの `TODO`（118 行目の分岐と 243 行目の `Workflow` 結線）を `agy` またはエディタで実装し、札幌 2 泊（自動予約）とハワイ 4 泊（日本語チャットでの上長承認 → `Session.state` 上限更新 → 予約完了）を確認します。

### Step 3: 自動評価と Agent Runtime デプロイ・プレイグラウンド確認
```bash
uv run pytest -v
uv run ruff check .
uv run ty check

# 経路 (Trajectory) 自動評価
uv run agents-cli eval run --app-name step2_workflow_agent --dataset eval/workcation_eval.json

# Agent Runtime へのデプロイ
uv run agents-cli deploy \
  --deployment-target agent_runtime \
  --project "${GOOGLE_CLOUD_PROJECT}" \
  --region us-central1 \
  --env-vars "GOOGLE_CLOUD_LOCATION=global" \
  --service-name "workcation-concierge-workflow"
```
デプロイ完了後、Google Cloud コンソール上部の検索バーで **`Deployments`** を検索し、対象リソースの **「プレイグラウンド」タブ** からクラウド上のエージェントと直接会話できます。

---

## 4. 発展: MCP サーバーを Cloud Run へ分離展開する (`StreamableHTTP`)

本編のハンズオンではゼロ設定で動作するローカル `stdio` 接続を使用していますが、`mcp_server.py` と `mcp_client.py` は本番向けの **リモート `StreamableHTTP` 接続** にも対応しています。

```bash
# 1. MCP サーバーを Cloud Run へ単体起動 (PORT 指定で自動的に streamable-http 起動)
MCP_TRANSPORT=streamable-http PORT=8080 uv run python -m workcation_concierge.mcp_server

# 2. 接続先 URL を環境変数に設定すると McpToolset が自動的に StreamableHTTP へ切替
export MCP_SERVER_URL="https://<your-cloud-run-service>.a.run.app/mcp"
```

本番運用では Cloud Run に `--no-allow-unauthenticated` で展開し、Agent Runtime のサービスアカウントへ `roles/run.invoker` を付与して ID Token 認証で接続します。
