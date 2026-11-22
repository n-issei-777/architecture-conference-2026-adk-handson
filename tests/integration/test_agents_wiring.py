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

"""Integration tests verifying agent construction and ADK 2.0 Workflow execution."""

from __future__ import annotations

from typing import Any

from google.adk import Workflow
from google.adk.agents import LlmAgent
from google.adk.apps import App, ResumabilityConfig
from google.adk.runners import InMemoryRunner
from google.genai import types
from step1_basic_agent.agent import root_agent as step1_root_agent
from step2_starter.agent import root_agent as step2_starter_agent
from step2_workflow_agent.agent import (
    booking_agent,
    calculate_and_route,
    fetch_workcation_metrics_node,
    intake_agent,
    join_research,
    manager_approval_gate,
    replan_notice,
    search_agent,
)
from step2_workflow_agent.agent import (
    root_agent as step2_workflow_root_agent,
)


def test_step1_and_step2_agents_construct_cleanly() -> None:
    # Step 1 (前後両状態), Step 2 Starter, Step 2 Workflow の構築とモデル割り当てを検証
    assert isinstance(step1_root_agent, LlmAgent)
    assert step1_root_agent.model == "gemini-4-neon"

    assert isinstance(step2_starter_agent, Workflow)
    assert step2_starter_agent.name == "step2_starter_workflow"

    assert isinstance(step2_workflow_root_agent, Workflow)
    assert step2_workflow_root_agent.name == "workcation_concierge_workflow"
    assert intake_agent.model == "gemini-4-neon"
    assert search_agent.model == "gemini-4-hydrogen"
    assert booking_agent.model == "gemini-4-hydrogen"
    assert booking_agent.before_tool_callback is not None


async def test_workflow_deterministic_auto_book_and_hitl_approval_via_runner() -> None:
    # ADK 2.0 Workflow + InMemoryRunner で並列Join・確定計算ルーティング・RequestInput承認再開を検証
    def fake_intake(node_input: str) -> dict[str, object]:
        city = "hawaii" if "hawaii" in node_input.lower() else "sapporo"
        nights = 4 if city == "hawaii" else 2
        return {
            "city": city,
            "nights": nights,
            "flight_class": "economy",
            "room_type": "standard",
            "purpose": "workcation",
        }

    def fake_search_agent(node_input: dict[str, Any]) -> dict[str, Any]:
        return {
            "city": str(node_input.get("city", "sapporo")),
            "nights": int(node_input.get("nights", 2)),
            "flight_class": "economy",
            "room_type": "standard",
        }

    def fake_booking_agent(ctx: object, node_input: dict[str, object]) -> dict[str, object]:
        return {
            "status": "CONFIRMED",
            "city": node_input.get("city"),
            "total_jpy": node_input.get("total_jpy"),
        }

    test_workflow = Workflow(
        name="deterministic_workflow_test",
        edges=[
            ("START", fake_intake),
            (fake_intake, (fetch_workcation_metrics_node, fake_search_agent)),
            ((fetch_workcation_metrics_node, fake_search_agent), join_research),
            (join_research, calculate_and_route),
            (
                calculate_and_route,
                {
                    "auto_book": fake_booking_agent,
                    "needs_approval": manager_approval_gate,
                },
            ),
            (
                manager_approval_gate,
                {
                    "approved": fake_booking_agent,
                    "rejected": replan_notice,
                },
            ),
        ],
    )
    app = App(
        name="workcation_test_app",
        root_agent=test_workflow,
        resumability_config=ResumabilityConfig(is_resumable=True),
    )
    runner = InMemoryRunner(app=app)

    # 1. 札幌2泊 (59,000円 <= 150,000円) は承認ゲートなしで自動予約完了
    s1 = await runner.session_service.create_session(app_name="workcation_test_app", user_id="u1")
    msg_sapporo = types.Content(role="user", parts=[types.Part(text="sapporo 2 nights")])
    events_sapporo = [
        e async for e in runner.run_async(user_id="u1", session_id=s1.id, new_message=msg_sapporo)
    ]
    outputs_sapporo = [e.output for e in events_sapporo if e.output]
    assert any(
        isinstance(o, dict) and o.get("status") == "CONFIRMED" and o.get("total_jpy") == 59000
        for o in outputs_sapporo
    )

    # 2. ハワイ4泊 (242,000円) は RequestInput で一時停止し、承認後に上限を更新して完了
    s2 = await runner.session_service.create_session(app_name="workcation_test_app", user_id="u1")
    msg_hawaii = types.Content(role="user", parts=[types.Part(text="hawaii 4 nights")])
    paused_events = [
        e async for e in runner.run_async(user_id="u1", session_id=s2.id, new_message=msg_hawaii)
    ]
    fc_events = [e for e in paused_events if e.get_function_calls()]
    assert fc_events, "Expected adk_request_input interrupt for over-budget Hawaii trip"
    fc = fc_events[-1].get_function_calls()[0]
    assert fc.name == "adk_request_input"

    approval_response = types.Content(
        role="user",
        parts=[
            types.Part(
                function_response=types.FunctionResponse(
                    id=fc.id,
                    name=fc.name,
                    response={
                        "approved": True,
                        "approved_limit_jpy": 250000,
                        "approver_comment": "Approved by manager",
                    },
                )
            )
        ],
    )
    resumed_events = [
        e
        async for e in runner.run_async(
            user_id="u1", session_id=s2.id, new_message=approval_response
        )
    ]
    outputs_hawaii = [e.output for e in resumed_events if e.output]
    assert any(
        isinstance(o, dict) and o.get("status") == "CONFIRMED" and o.get("total_jpy") == 242000
        for o in outputs_hawaii
    )
    updated_session = await runner.session_service.get_session(
        app_name="workcation_test_app", user_id="u1", session_id=s2.id
    )
    assert updated_session is not None
    assert updated_session.state.get("approved_limit_jpy") == 250000
