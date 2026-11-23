# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Step 2 スターター: 2 つの TODO をエディタで実装して ADK 2.0 Workflow を完成させる.

完成版のリファレンス実装は `step2_workflow_agent/agent.py` を参照。
"""

from __future__ import annotations

from typing import Any

from google.adk import Agent, Context, Event, Workflow
from google.adk.apps import App, ResumabilityConfig
from google.adk.workflow import DEFAULT_ROUTE, JoinNode  # noqa: F401

from workcation_concierge.guardrails import enforce_booking_guardrail
from workcation_concierge.mcp_client import create_travel_mcp_toolset
from workcation_concierge.schemas import ApprovalDecision, CandidatePlan, TripRequest
from workcation_concierge.workflow_nodes import (
    apply_approval_decision,  # noqa: F401
    build_cost_plan,
    fetch_workcation_metrics_step,  # noqa: F401
    replan_notice,  # noqa: F401
    text_event,
)

# 1. 要件ヒアリング・タスクノード (mode="task", gemini-4-neon)
intake_agent = Agent(
    name="intake_agent",
    model="gemini-4-neon",
    mode="task",
    output_schema=TripRequest,
    description="ユーザーとの対話から出張・ワーケーションの希望条件を収集するタスクノード",
    instruction=(
        "# タスク\n"
        "ユーザーの入力から行き先都市（'sapporo', 'okinawa', 'hawaii', 'san_francisco'）、"
        "宿泊数（nights）、航空機クラス（既定 'economy'）、客室グレード（既定 'standard'）を"
        "抽出してください。\n"
        "- 行き先や泊数がまだ不明な場合は、丁寧な日本語で質問してください。\n"
        "- 必要な情報が揃ったら TripRequest にセットして finish_task を呼んでください。"
    ),
)

# 2. 並列ブランチB: MCP 経由でフライト・ホテルを検索する高速エージェント (gemini-4-hydrogen)
search_agent = Agent(
    name="search_agent",
    model="gemini-4-hydrogen",
    mode="single_turn",
    output_schema=CandidatePlan,
    description="MCP サーバー経由でフライトとホテルを1ターン検索する高速エージェントノード",
    instruction=(
        "入力された TripRequest の都市について、MCP ツールの `search_flights` と "
        "`search_hotels` を呼び出し、希望の flight_class と room_type に合致する便名と"
        "ホテル名を選定して CandidatePlan を出力してください。"
    ),
    tools=[create_travel_mcp_toolset(tool_filter=["search_flights", "search_hotels"])],
)

# 並列リサーチの合流ノード (JoinNode)
join_research = JoinNode(name="join_research")


# 3. 0-LLM 確定金額計算 & 条件分岐ルーティング関数ノード
def calculate_and_route(ctx: Context, node_input: dict[str, Any]) -> Event:
    """Python で正確な合計金額を算出し、15万円以下は自動予約、超過は上長承認へ分岐."""
    merged_plan, total_jpy, approved_limit = build_cost_plan(ctx, node_input)

    # TODO (Step 2 課題1): total_jpy <= approved_limit なら "auto_book"、
    # 超過なら "needs_approval" へ分岐するよう下の 1 行を修正
    route = "auto_book"

    status = (
        "上限内のため自動予約へ進みます。"
        if route == "auto_book"
        else f"自己承認上限（{approved_limit:,} 円）を超えるため、上長承認ゲートへ進みます。"
    )
    msg = (
        f"見積もり結果: {merged_plan.get('display_name')} {merged_plan.get('nights')}泊 "
        f"（Wi-Fi {merged_plan['wifi_mbps']} Mbps）合計 {total_jpy:,} 円 — {status}"
    )
    return text_event(
        msg,
        output=merged_plan,
        route=route,
        state_delta={"calculated_cost": merged_plan},
    )


# 4. Human-in-the-Loop 上長承認タスクノード (mode="task")
manager_approval_task = Agent(
    name="manager_approval_task",
    model="gemini-4-hydrogen",
    mode="task",
    output_schema=ApprovalDecision,
    description="予算超過プランについて上長の承認可否と新しい予算上限額を対話で確認するタスクノード",
    instruction=(
        "# タスク\n"
        "入力された見積もりプランは自己承認上限（150,000 円）を超過しています。\n"
        "1. 行き先・泊数・合計金額を簡潔に提示し、「上長としてこの予算超過プランを承認しますか？"
        "承認する場合は新しい予算上限額（円）もあわせて教えてください」と日本語で質問してください。\n"
        "2. ユーザーが承認する旨を答えたら `approved=True` と承認上限額（未指定なら 250000）を、"
        "却下・見送りの旨を答えたら `approved=False` をセットして finish_task を呼んでください。"
    ),
)

# 5. 最終予約確定エージェント (McpToolset + enforce_booking_guardrail)
booking_agent = Agent(
    name="booking_agent",
    model="gemini-4-hydrogen",
    mode="single_turn",
    description="enforce_booking_guardrail の保護下で MCP 予約ツールを実行する最終エージェント",
    instruction=(
        "受け取った確定プラン（city, nights, flight_class, room_type, total_jpy）を使って、"
        "MCP ツールの `reserve_itinerary` を1回呼び出して予約を確定してください。\n"
        "その後、予約番号（reservation_id）・都市・泊数・合計金額・Wi-Fi速度を、"
        "わかりやすい日本語のマークダウン箇条書きでユーザーに報告してください。"
    ),
    tools=[create_travel_mcp_toolset(tool_filter=["reserve_itinerary"])],
    before_tool_callback=enforce_booking_guardrail,
)

# TODO (Step 2 課題2): 下のコメントアウト (#) を解除して ADK 2.0 Workflow のエッジを配線
root_agent = Workflow(
    name="step2_starter_workflow",
    description="Starter ADK 2.0 Hybrid Workflow for Workcation & Smart Travel Concierge.",
    edges=[
        ("START", intake_agent),
        # (intake_agent, (fetch_workcation_metrics_step, search_agent)),
        # ((fetch_workcation_metrics_step, search_agent), join_research),
        # (join_research, calculate_and_route),
        # (
        #     calculate_and_route,
        #     {"auto_book": booking_agent, "needs_approval": manager_approval_task},
        # ),
        # (manager_approval_task, apply_approval_decision),
        # (apply_approval_decision, {"approved": booking_agent, DEFAULT_ROUTE: replan_notice}),
    ],
)

app = App(
    name="step2_starter",
    root_agent=root_agent,
    resumability_config=ResumabilityConfig(is_resumable=True),
)
