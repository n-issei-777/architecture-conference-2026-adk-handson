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

"""Step 2 Hands-on Starter Template: Refactoring into an ADK 2.0 Hybrid Workflow.

ハンズオン参加者が agy と対話しながら完成させるスターターファイル。
完成版のリファレンス実装は `step2_workflow_agent/agent.py` を参照。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from google.adk import Agent, Context, Event, Workflow
from google.adk.apps import App, ResumabilityConfig
from google.adk.events import EventActions, RequestInput
from google.adk.workflow import FunctionNode, JoinNode

from workcation_concierge.guardrails import (
    DEFAULT_APPROVED_LIMIT_JPY,
    enforce_booking_guardrail,
)
from workcation_concierge.mcp_server import (
    calculate_itinerary_cost,
    fetch_workcation_metrics,
    reserve_itinerary,
    search_flights,
    search_hotels,
)
from workcation_concierge.schemas import (
    ApprovalDecision,
    BookingResult,
    CandidatePlan,
    TripRequest,
)
from workcation_concierge.skill_loader import create_travel_policy_skill_toolset

# 1. 要求ヒアリング・構造化抽出エージェント (mode="task", gemini-4-neon)
intake_agent = Agent(
    name="intake_agent",
    model="gemini-4-neon",
    mode="task",
    output_schema=TripRequest,
    description="Extracts structured TripRequest parameters from user travel prompts.",
    instruction=(
        "Extract the user's destination city ('sapporo', 'okinawa', 'hawaii', or "
        "'san_francisco'), number of nights, flight_class ('economy' or 'business'), "
        "and room_type ('standard' or 'suite'). "
        "When ready, call finish_task with the structured TripRequest."
    ),
)


# 2. 並列実行ブランチA: ワーケーション通信・コワーキング指標の確定取得 (0-LLM Python ノード)
def fetch_workcation_metrics_node(node_input: dict[str, Any]) -> dict[str, Any]:
    """Fetch deterministic Wi-Fi and coworking metrics for the requested city."""
    city = str(node_input.get("city", "sapporo"))
    return fetch_workcation_metrics(city)


fetch_workcation_metrics_step = FunctionNode(
    func=fetch_workcation_metrics_node,
    name="fetch_workcation_metrics",
)

# 3. 並列実行ブランチB: フライト・ホテル候補検索エージェント (single_turn, gemini-4-hydrogen)
search_agent = Agent(
    name="search_agent",
    model="gemini-4-hydrogen",
    mode="single_turn",
    output_schema=CandidatePlan,
    description="Searches flights and hotels in a single autonomous turn.",
    instruction=(
        "Given the TripRequest input, call `search_flights` and `search_hotels` "
        "for the target city. Select the matching flight_code and hotel_name "
        "for the requested flight_class and room_type, "
        "then call finish_task with CandidatePlan."
    ),
    tools=[search_flights, search_hotels],
)

# 並列ブランチの合流ノード (JoinNode)
join_research = JoinNode(name="join_research")


# 4. 確定計算 & 条件分岐ルーティングノード (0-LLM Python FunctionNode)
def calculate_and_route(ctx: Context, node_input: dict[str, Any]) -> Event:
    """Calculate exact itinerary cost in Python and route to auto_book or needs_approval."""
    # TODO: ハンズオン課題1 - JoinNode の出力から都市・泊数・クラスを取り出し、
    # calculate_itinerary_cost で正確な合計金額 (total_jpy) を算出して
    # 150,000円以下なら route="auto_book"、超過なら route="needs_approval" を返すよう確認・拡張
    candidate = node_input.get("search_agent") or {}
    metrics = node_input.get("fetch_workcation_metrics") or {}
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

    route = "auto_book" if total_jpy <= approved_limit else "needs_approval"
    merged_plan = {
        **cost_breakdown,
        "wifi_mbps": metrics.get("wifi_mbps", cost_breakdown.get("wifi_mbps", 100)),
        "coworking_spaces": metrics.get("coworking_spaces", 0),
        "approved_limit_jpy": approved_limit,
    }
    return Event(
        output=merged_plan,
        actions=EventActions(
            route=route,
            state_delta={"calculated_cost": merged_plan},
        ),
    )


# 5. Human-in-the-Loop (RequestInput) 上長承認ゲート
async def _manager_approval_gate_fn(
    ctx: Context,
    node_input: dict[str, Any],
) -> AsyncGenerator[RequestInput | Event]:
    """Pause with RequestInput when over budget, and raise approved_limit_jpy on approval."""
    # TODO: ハンズオン課題2 - ctx.resume_inputs に "manager_approval" がある場合は
    # state["approved_limit_jpy"] を更新して route="approved" を送出し、
    # 未回答の場合は RequestInput(interrupt_id="manager_approval", ...) を yield する動作を確認
    resume_payload = (ctx.resume_inputs or {}).get("manager_approval")
    if resume_payload is None:
        total_jpy = int(node_input.get("total_jpy", 0))
        city = str(node_input.get("city", "unknown"))
        yield RequestInput(
            interrupt_id="manager_approval",
            message=(
                f"Budget approval required for {city} workcation: "
                f"total {total_jpy:,} JPY exceeds 150,000 JPY limit. Approve budget override?"
            ),
            payload=node_input,
            response_schema=ApprovalDecision,
        )
        return

    if isinstance(resume_payload, ApprovalDecision):
        decision = resume_payload.model_dump()
    elif isinstance(resume_payload, dict):
        decision = dict(resume_payload.get("result", resume_payload))
    else:
        decision = {
            "approved": bool(resume_payload),
            "approved_limit_jpy": max(int(node_input.get("total_jpy", 250000)), 250000),
            "approver_comment": str(resume_payload),
        }

    is_approved = bool(decision.get("approved", False))
    new_limit = int(
        decision.get(
            "approved_limit_jpy",
            max(int(node_input.get("total_jpy", 250000)), 250000),
        )
    )
    updated_plan = {
        **node_input,
        "approved_limit_jpy": new_limit if is_approved else DEFAULT_APPROVED_LIMIT_JPY,
        "approval_decision": decision,
    }
    yield Event(
        output=updated_plan,
        actions=EventActions(
            route="approved" if is_approved else "rejected",
            state_delta={
                "approved_limit_jpy": new_limit if is_approved else DEFAULT_APPROVED_LIMIT_JPY,
                "approval_decision": decision,
            },
        ),
    )


manager_approval_gate = FunctionNode(
    func=_manager_approval_gate_fn,
    name="manager_approval_gate",
    rerun_on_resume=True,
)


def replan_notice(node_input: dict[str, Any]) -> dict[str, Any]:
    """Return a structured notice when manager approval is declined."""
    return {
        "status": "NEEDS_REPLAN",
        "city": str(node_input.get("city", "unknown")),
        "total_jpy": int(node_input.get("total_jpy", 0)),
        "message": (
            "Manager declined the budget override. Please select a domestic workcation "
            "destination within the 150,000 JPY limit (e.g., Sapporo or Okinawa)."
        ),
    }


# 6. 予約確定エージェント (gemini-4-hydrogen + enforce_booking_guardrail)
booking_agent = Agent(
    name="booking_agent",
    model="gemini-4-hydrogen",
    mode="single_turn",
    output_schema=BookingResult,
    description="Executes the final reservation guarded by enforce_booking_guardrail.",
    instruction=(
        "Receive the verified itinerary plan from node_input. "
        "Call `reserve_itinerary` with the exact city, nights, flight_class, "
        "room_type, and total_jpy. "
        "Then call finish_task with BookingResult summarizing the confirmed reservation."
    ),
    tools=[create_travel_policy_skill_toolset(), reserve_itinerary],
    before_tool_callback=enforce_booking_guardrail,
)

# TODO: ハンズオン課題3 - Workflow の edges 定義を確認し、`uv run adk web .` で動作を確認
root_agent = Workflow(
    name="step2_starter_workflow",
    description="Starter ADK 2.0 Hybrid Workflow for Workcation & Smart Travel Concierge.",
    edges=[
        ("START", intake_agent),
        (intake_agent, (fetch_workcation_metrics_step, search_agent)),
        ((fetch_workcation_metrics_step, search_agent), join_research),
        (join_research, calculate_and_route),
        (
            calculate_and_route,
            {
                "auto_book": booking_agent,
                "needs_approval": manager_approval_gate,
            },
        ),
        (
            manager_approval_gate,
            {
                "approved": booking_agent,
                "rejected": replan_notice,
            },
        ),
    ],
)

app = App(
    name="step2_starter",
    root_agent=root_agent,
    resumability_config=ResumabilityConfig(is_resumable=True),
)
