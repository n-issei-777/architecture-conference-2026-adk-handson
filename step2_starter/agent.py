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

"""Step 2 スターター: agy またはエディタで 2 つの TODO を実装して Workflow を完成させる.

完成版のリファレンス実装は `step2_workflow_agent/agent.py` を参照。
"""

from __future__ import annotations

from typing import Any

from google.adk import Agent, Context, Event, Workflow
from google.adk.apps import App, ResumabilityConfig
from google.adk.events import EventActions
from google.adk.workflow import DEFAULT_ROUTE, FunctionNode, JoinNode
from google.genai import types

from workcation_concierge.guardrails import (
    DEFAULT_APPROVED_LIMIT_JPY,
    enforce_booking_guardrail,
)
from workcation_concierge.mcp_client import create_travel_mcp_toolset
from workcation_concierge.mcp_server import (
    calculate_itinerary_cost,
    fetch_workcation_metrics,
)
from workcation_concierge.schemas import (
    ApprovalDecision,
    BookingResult,
    CandidatePlan,
    TripRequest,
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


# 2. 並列ブランチA: 通信環境・コワーキング拠点数の確定取得 (0-LLM Python 関数ノード)
def fetch_workcation_metrics_node(node_input: dict[str, Any]) -> dict[str, Any]:
    """指定都市の Wi-Fi 速度とコワーキングスペース数を確定取得."""
    city = str(node_input.get("city", "sapporo"))
    return fetch_workcation_metrics(city)


fetch_workcation_metrics_step = FunctionNode(
    func=fetch_workcation_metrics_node,
    name="fetch_workcation_metrics",
)

# 3. 並列ブランチB: MCP 経由でフライト・ホテルを検索するエージェント (gemini-4-hydrogen)
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


# 4. 0-LLM 確定金額計算 & 条件分岐ルーティング関数ノード
def calculate_and_route(ctx: Context, node_input: dict[str, Any]) -> Event:
    """Python で正確な合計金額を算出し、15万円以下は自動予約、超過は上長承認へ分岐."""
    metrics = node_input.get("fetch_workcation_metrics") or {}
    candidate = node_input.get("search_agent") or {}

    city = str(candidate.get("city") or metrics.get("city") or "sapporo")
    nights = int(candidate.get("nights", 2))
    flight_class = str(candidate.get("flight_class", "economy"))
    room_type = str(candidate.get("room_type", "standard"))

    cost_breakdown = calculate_itinerary_cost(
        city=city,
        nights=nights,
        flight_class=flight_class,
        room_type=room_type,
    )
    total_jpy = int(cost_breakdown.get("total_jpy", 0))
    approved_limit = int(ctx.state.get("approved_limit_jpy", DEFAULT_APPROVED_LIMIT_JPY))

    # TODO (Step 2 課題1): total_jpy <= approved_limit なら "auto_book"、
    # 超過なら "needs_approval" へ分岐するよう下の 1 行を修正
    route = "auto_book"
    merged_plan = {
        **cost_breakdown,
        "total_jpy": total_jpy,
        "wifi_mbps": int(metrics.get("wifi_mbps", cost_breakdown.get("wifi_mbps", 100))),
        "coworking_spaces": int(metrics.get("coworking_spaces", 0)),
        "approved_limit_jpy": approved_limit,
    }
    status_line = (
        "上限内のため自動予約へ進みます。"
        if route == "auto_book"
        else f"自己承認上限（{approved_limit:,} 円）を超えるため、上長承認ゲートへ進みます。"
    )
    summary_msg = (
        f"見積もり結果: {merged_plan.get('display_name', city)} {nights}泊 "
        f"（{flight_class} / {room_type}、Wi-Fi {merged_plan['wifi_mbps']} Mbps）"
        f" 合計 {total_jpy:,} 円 — {status_line}"
    )
    return Event(
        content=types.Content(role="model", parts=[types.Part(text=summary_msg)]),
        output=merged_plan,
        actions=EventActions(
            route=route,
            state_delta={"calculated_cost": merged_plan},
        ),
    )


# 5. Human-in-the-Loop 上長承認タスクノード (mode="task") + Session.state 更新関数ノード
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


def apply_approval_decision(ctx: Context, node_input: ApprovalDecision | dict[str, Any]) -> Event:
    """上長の判断結果に基づき Session.state['approved_limit_jpy'] を更新して分岐."""
    decision = (
        node_input.model_dump() if isinstance(node_input, ApprovalDecision) else dict(node_input)
    )
    plan = dict(ctx.state.get("calculated_cost") or {})
    is_approved = bool(decision.get("approved", False))
    requested_total = int(plan.get("total_jpy", 250_000))
    new_limit = int(decision.get("approved_limit_jpy") or max(requested_total, 250_000))
    if is_approved and new_limit < requested_total:
        new_limit = requested_total

    updated_limit = new_limit if is_approved else DEFAULT_APPROVED_LIMIT_JPY
    updated_plan = {
        **plan,
        "approved_limit_jpy": updated_limit,
        "approval_decision": decision,
    }
    route = "approved" if is_approved else DEFAULT_ROUTE
    msg = (
        f"上長承認を確認しました。承認上限額を {updated_limit:,} 円に更新し、予約を実行します。"
        if is_approved
        else "上長承認が見送られたため、予約を実行せず再計画へ進みます。"
    )
    return Event(
        content=types.Content(role="model", parts=[types.Part(text=msg)]),
        output=updated_plan,
        actions=EventActions(
            route=route,
            state_delta={
                "approved_limit_jpy": updated_limit,
                "approval_decision": decision,
            },
        ),
    )


def replan_notice(node_input: dict[str, Any]) -> Event:
    """上長承認が却下された場合の代替案案内ノード."""
    city = str(node_input.get("city", "unknown"))
    total_jpy = int(node_input.get("total_jpy", 0))
    msg = (
        f"上長承認が見送られたため、{city}（合計 {total_jpy:,} 円）の予約を中止しました。"
        "150,000 円以内の国内プラン（例: 札幌2泊 59,000 円、沖縄3泊 93,000 円）をご検討ください。"
    )
    return Event(
        content=types.Content(role="model", parts=[types.Part(text=msg)]),
        output={"status": "NEEDS_REPLAN", "city": city, "total_jpy": total_jpy, "message": msg},
    )


# 6. 最終予約確定エージェント (gemini-4-hydrogen + McpToolset + enforce_booking_guardrail)
booking_agent = Agent(
    name="booking_agent",
    model="gemini-4-hydrogen",
    mode="single_turn",
    output_schema=BookingResult,
    description="enforce_booking_guardrail の保護下で MCP 予約ツールを実行する最終エージェント",
    instruction=(
        "受け取った確定プラン（city, nights, flight_class, room_type, total_jpy）を使って、"
        "MCP ツールの `reserve_itinerary` を1回呼び出して予約を確定してください。\n"
        "その後、予約番号（reservation_id）・都市・泊数・合計金額・Wi-Fi速度を日本語でまとめた "
        "BookingResult を出力してください。"
    ),
    tools=[
        create_travel_mcp_toolset(tool_filter=["reserve_itinerary"]),
    ],
    before_tool_callback=enforce_booking_guardrail,
)

# TODO (Step 2 課題2): agy (またはエディタ編集) で以下のハイブリッドグラフを edges に配線
#   1. ("START", intake_agent)
#   2. (intake_agent, (fetch_workcation_metrics_step, search_agent))
#   3. ((fetch_workcation_metrics_step, search_agent), join_research)
#   4. (join_research, calculate_and_route)
#   5. (calculate_and_route, {"auto_book": booking_agent, "needs_approval": manager_approval_task})
#   6. (manager_approval_task, apply_approval_decision)
#   7. (apply_approval_decision, {"approved": booking_agent, DEFAULT_ROUTE: replan_notice})
root_agent = Workflow(
    name="step2_starter_workflow",
    description="Starter ADK 2.0 Hybrid Workflow for Workcation & Smart Travel Concierge.",
    edges=[
        ("START", intake_agent),
    ],
)

app = App(
    name="step2_starter",
    root_agent=root_agent,
    resumability_config=ResumabilityConfig(is_resumable=True),
)
