# System Design: Workcation & Smart Travel Concierge (Architecture Conference 2026)

## 1. System Architecture Overview

- **Models** (`GOOGLE_GENAI_USE_VERTEXAI=TRUE`, `GOOGLE_CLOUD_LOCATION=global`, Vertex AI ADC, `thinking_level=LOW` via `gemini_model()` in `workflow_nodes.py` for low-latency workshop execution):
  - `gemini-4-hydrogen`: Step 0 and all Step 2 nodes (`step0_minimal_agent`, `intake_agent`, `search_agent`, `manager_approval_task`, `booking_agent`).
  - `gemini-3.8-flash`: Step 1 only (`step1_basic_agent`), chosen so the prompt-only guard bypass is easy to reproduce.
- **Progressive 4-Step Learning Architecture**:
  - **Step 0 (`step0_minimal_agent/agent.py`)**: Minimal ~25-line `Agent` + 1 Python function tool (`get_city_workcation_info`) demonstrating `Agent`, `InMemorySessionService`, `Runner`, and `Event` recording.
  - **Step 1 (`step1_basic_agent/agent.py`)**: Connects `SkillToolset` (`skills/travel-policy/SKILL.md`) and real stdio `McpToolset` (`src/workcation_concierge/mcp_client.py` -> `mcp_server.py`). Uses `gemini-3.8-flash` and starts with `before_tool_callback=None` (prompt-only guard that can be bypassed by role-spoofing), then attaches `enforce_booking_guardrail` (`src/workcation_concierge/guardrails.py`) for deterministic defense-in-depth with server-side cost recalculation.
  - **Step 2 (`step2_starter/agent.py`, `step2_workflow_agent/agent.py`, `src/workcation_concierge/workflow_nodes.py`)**: Declarative ADK 2.0 `Workflow` combining `mode="task"` intake, parallel fan-out/fan-in (`JoinNode`), 0-LLM Python cost math & routing (`calculate_and_route`), conversational HITL manager approval (`manager_approval_task` + `apply_approval_decision` with `DEFAULT_ROUTE`), and callback-guarded MCP booking returning natural Japanese Markdown.
  - **Step 3 (`agents-cli-manifest.yaml`, `Dockerfile`, `step2_workflow_agent/fast_api_app.py`)**: Evaluation (`agents-cli eval run`) and deployment to Agent Runtime in Gemini platform (`agents-cli deploy`), exposing `/api/reasoning_engine` and `/api/stream_reasoning_engine` for Google Cloud Console Playground (`VertexAiSessionService` auto-switch in `app_utils/services.py`).

```mermaid
flowchart LR
    START(["START"]) --> Intake["intake_agent\n(mode='task', gemini-4-hydrogen)"]
    Intake --> Metrics["fetch_workcation_metrics\n(0-LLM FunctionNode)"]
    Intake --> Search["search_agent\n(mode='single_turn' + McpToolset)"]
    Metrics --> Join(["join_research\n(JoinNode)"])
    Search --> Join
    Join --> Calc["calculate_and_route\n(0-LLM 確定金額計算・分岐)"]
    Calc -- "auto_book\n(<= 150,000円)" --> Book["booking_agent\n(+ before_tool_callback + McpToolset)"]
    Calc -- "needs_approval\n(> 150,000円)" --> Task["manager_approval_task\n(mode='task' 上長承認対話)"]
    Task --> Apply["apply_approval_decision\n(Session.state 上限更新)"]
    Apply -- "approved" --> Book
    Apply -- "DEFAULT_ROUTE\n(却下)" --> Replan["replan_notice\n(国内代替プラン案内)"]
```

## 2. End-to-End Sequence Diagram (Over-Budget Conversational Approval)

```mermaid
sequenceDiagram
    actor User as 社員 / 上長
    participant Runner as ADK Runner / Agent Runtime
    participant Intake as intake_agent (mode='task')
    participant Parallel as fetch_metrics + search_agent (McpToolset)
    participant Calc as calculate_and_route (0-LLM Python)
    participant Approval as manager_approval_task (mode='task')
    participant Apply as apply_approval_decision
    participant Book as booking_agent + enforce_booking_guardrail
    participant MCP as Travel SaaS MCP Server (stdio)

    User->>Runner: 「ハワイで4泊、standardルームで合宿を手配して」
    Runner->>Intake: 条件抽出
    Intake-->>Runner: TripRequest(city='hawaii', nights=4)
    par 並列リサーチ
        Runner->>Parallel: fetch_workcation_metrics('hawaii')
        Runner->>Parallel: search_agent -> MCP search_flights / search_hotels
    end
    Parallel-->>Runner: JoinNode で合流
    Runner->>Calc: 130,000 + 28,000 * 4 = 242,000 円 (> 150,000 円)
    Calc-->>Runner: Event(route='needs_approval', state_delta={'calculated_cost': ...})
    Runner->>Approval: 上長承認タスク起動
    Approval-->>User: 「合計 242,000 円は上限超過です。承認しますか？新しい上限額も教えてください」
    User->>Runner: 「承認します。上限を 250,000 円に引き上げてください」
    Approval-->>Runner: ApprovalDecision(approved=True, approved_limit_jpy=250000)
    Runner->>Apply: Session.state['approved_limit_jpy'] = 250000 に更新
    Apply-->>Runner: Event(route='approved')
    Runner->>Book: 予約確定実行
    Book->>Book: enforce_booking_guardrail (242,000 <= 250,000 OK)
    Book->>MCP: reserve_itinerary(...)
    MCP-->>Book: RES-HAW-0001
    Book-->>User: 予約完了サマリー表示
```

## 3. Production Hardening & Workshop Trade-offs

- **Server-side Cost Verification (`guardrails.py`)**: `enforce_booking_guardrail` does not trust LLM-supplied `args["total_jpy"]`; it recalculates the authoritative cost via `calculate_itinerary_cost(...)` and blocks if `max(claimed, recalculated) > approved_limit_jpy`. Arguments that cannot be recalculated (unknown city, invalid nights or grade) are blocked (fail-closed). `user_role` is read only from `Session.state` (never from chat text); the workshop does not populate it, so every caller is treated as `member`.
- **Per-trip Approval (`workflow_nodes.py`)**: `calculate_and_route` resets `approved_limit_jpy` to the default for each new estimate and computes cost from the intake `TripRequest` (not from the LLM-relayed `CandidatePlan`). `apply_approval_decision` treats an approval whose limit is below the trip total as not approved instead of raising the limit.
- **Remote MCP Separation (`mcp_client.py` / `mcp_server.py`)**: Uses local `stdio` by default for zero-friction workshop execution, and automatically switches to `StreamableHTTPConnectionParams` when `MCP_SERVER_URL` is configured (with `stateless_http=True` and Cloud Run `TransportSecuritySettings` in `mcp_server.py`).
- **HITL Separation of Duties**: The workshop uses conversational `mode="task"` (`manager_approval_task`) so attendees can complete the full approval loop solo in `adk web` and Cloud Console Playground. In production multi-tenant systems, pair ADK `RequestInput` with an authenticated external approval workflow (e.g., Slack / approval API with approver IAM verification) so the requester cannot self-approve.
