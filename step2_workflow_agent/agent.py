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

"""Step 2 Complete Reference: ADK 2.0 Hybrid Workflow with Parallel Join & HITL Gate."""

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
    description="Interactive intake agent that extracts structured TripRequest parameters.",
    instruction=(
        "Extract the user's destination city ('sapporo', 'okinawa', 'hawaii', or "
        "'san_francisco'), number of nights, flight_class ('economy' or 'business'), "
        "and room_type ('standard' or 'suite'). "
        "Default to 'economy' and 'standard' unless specified otherwise. "
        "Once extracted, call finish_task with the validated TripRequest."
    ),
)


# 2. 並列ブランチ1: ワーケーション通信環境・コワーキング拠点数の確定取得 (0-LLM Python ノード)
def fetch_workcation_metrics_node(node_input: dict[str, Any]) -> dict[str, Any]:
    """Fetch deterministic Wi-Fi speed and coworking metrics for the requested city."""
    city = str(node_input.get("city", "sapporo"))
    return fetch_workcation_metrics(city)


fetch_workcation_metrics_step = FunctionNode(
    func=fetch_workcation_metrics_node,
    name="fetch_workcation_metrics",
)

# 3. 並列ブランチ2: フライト・ホテル候補検索エージェント (mode="single_turn", gemini-4-hydrogen)
search_agent = Agent(
    name="search_agent",
    model="gemini-4-hydrogen",
    mode="single_turn",
    output_schema=CandidatePlan,
    description="High-speed single-turn flight and hotel search agent.",
    instruction=(
        "Inspect the TripRequest input, call `search_flights` and `search_hotels` "
        "for the destination city, and select the option matching the requested "
        "flight_class and room_type. Call finish_task with CandidatePlan."
    ),
    tools=[search_flights, search_hotels],
)

# 並列リサーチの合流ノード (JoinNode)
join_research = JoinNode(name="join_research")


# 4. 0-LLM 確定精算 & ルーティング関数ノード
def calculate_and_route(ctx: Context, node_input: dict[str, Any]) -> Event:
    """Deterministically calculate total JPY and route to auto_book or needs_approval."""
    # JoinNode の出力キー ("fetch_workcation_metrics" 等) からリサーチ結果を取得
    metrics = (
        node_input.get("fetch_workcation_metrics")
        or node_input.get("fetch_workcation_metrics_node")
        or {}
    )
    candidate = node_input.get("search_agent") or node_input.get("fake_search_agent") or {}

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

    # 150,000円 (または現在の承認上限) 以下なら自動予約、超過なら上長承認ゲートへ分岐
    route = "auto_book" if total_jpy <= approved_limit else "needs_approval"
    merged_plan = {
        **cost_breakdown,
        "wifi_mbps": int(metrics.get("wifi_mbps", cost_breakdown.get("wifi_mbps", 100))),
        "coworking_spaces": int(metrics.get("coworking_spaces", 0)),
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
    """Yield RequestInput when resume_inputs is empty; update approved_limit_jpy when approved."""
    resume_payload = (ctx.resume_inputs or {}).get("manager_approval")
    if resume_payload is None:
        total_jpy = int(node_input.get("total_jpy", 0))
        city = str(node_input.get("city", "unknown"))
        nights = int(node_input.get("nights", 1))
        yield RequestInput(
            interrupt_id="manager_approval",
            message=(
                f"Manager approval required: {city} ({nights} nights) costs "
                f"{total_jpy:,} JPY, exceeding the 150,000 JPY self-approval limit. "
                "Approve budget override?"
            ),
            payload=node_input,
            response_schema=ApprovalDecision,
        )
        return

    # 承認レスポンスの正規化 (Pydanticモデル・辞書・プリミティブ値のいずれにも対応)
    if isinstance(resume_payload, ApprovalDecision):
        decision = resume_payload.model_dump()
    elif isinstance(resume_payload, dict):
        if "result" in resume_payload and isinstance(resume_payload["result"], dict):
            decision = dict(resume_payload["result"])
        elif "result" in resume_payload and isinstance(resume_payload["result"], str):
            raw_text = resume_payload["result"].strip().lower()
            decision = {
                "approved": raw_text in ("yes", "true", "approved", "approve", "ok", "承認"),
                "approved_limit_jpy": max(int(node_input.get("total_jpy", 250000)), 250000),
                "approver_comment": resume_payload["result"],
            }
        else:
            decision = dict(resume_payload)
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
    updated_limit = new_limit if is_approved else DEFAULT_APPROVED_LIMIT_JPY
    updated_plan = {
        **node_input,
        "approved_limit_jpy": updated_limit,
        "approval_decision": decision,
    }
    yield Event(
        output=updated_plan,
        actions=EventActions(
            route="approved" if is_approved else "rejected",
            state_delta={
                "approved_limit_jpy": updated_limit,
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
    """Emit a deterministic replanning notice when manager approval is rejected."""
    return {
        "status": "NEEDS_REPLAN",
        "city": str(node_input.get("city", "unknown")),
        "total_jpy": int(node_input.get("total_jpy", 0)),
        "message": (
            "Manager approval was declined. Please replan with a destination "
            "under 150,000 JPY such as Sapporo (2 nights = 59,000 JPY) or "
            "Okinawa (3 nights = 93,000 JPY)."
        ),
    }


# 6. 最終予約実行エージェント (gemini-4-hydrogen + enforce_booking_guardrail)
booking_agent = Agent(
    name="booking_agent",
    model="gemini-4-hydrogen",
    mode="single_turn",
    output_schema=BookingResult,
    description="Executes the itinerary reservation guarded by enforce_booking_guardrail.",
    instruction=(
        "Receive the verified itinerary plan from node_input. "
        "Invoke `reserve_itinerary` using the exact city, nights, flight_class, "
        "room_type, and total_jpy. Then call finish_task with BookingResult "
        "containing the reservation_id, total_jpy, wifi_mbps, and summary."
    ),
    tools=[create_travel_policy_skill_toolset(), reserve_itinerary],
    before_tool_callback=enforce_booking_guardrail,
)

# Step 2 完成版 ADK 2.0 Hybrid Workflow
root_agent = Workflow(
    name="workcation_concierge_workflow",
    description=(
        "ADK 2.0 Hybrid Workflow combining task intake, parallel research fan-out/JoinNode, "
        "0-LLM deterministic cost calculation & routing, RequestInput HITL approval gate, "
        "and callback-guarded booking."
    ),
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
    name="step2_workflow_agent",
    root_agent=root_agent,
    resumability_config=ResumabilityConfig(is_resumable=True),
)
