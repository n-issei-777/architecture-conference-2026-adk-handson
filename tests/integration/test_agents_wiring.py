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

"""Integration tests verifying Step 0-2 agents, MCP wiring, and ADK 2.0 Workflow execution."""

from __future__ import annotations

from typing import Any

from google.adk import Workflow
from google.adk.agents import LlmAgent
from google.adk.apps import App, ResumabilityConfig
from google.adk.models import Gemini
from google.adk.runners import InMemoryRunner
from google.adk.tools.mcp_tool import McpToolset
from google.adk.workflow import DEFAULT_ROUTE
from google.genai import types
from step0_minimal_agent.agent import get_city_workcation_info
from step0_minimal_agent.agent import root_agent as step0_root_agent
from step1_basic_agent.agent import root_agent as step1_root_agent
from step2_starter.agent import root_agent as step2_starter_agent
from step2_workflow_agent.agent import (
    apply_approval_decision,
    booking_agent,
    calculate_and_route,
    fetch_workcation_metrics_node,
    intake_agent,
    join_research,
    manager_approval_task,
    replan_notice,
    search_agent,
)
from step2_workflow_agent.agent import (
    root_agent as step2_workflow_root_agent,
)


def test_step0_step1_and_step2_agents_construct_with_japanese_prompts_and_mcp() -> None:
    # Step 0-2 の各エージェント構築・日本語プロンプト・リトライ設定・McpToolset 配線を検証
    def _assert_gemini_with_retry(agent: LlmAgent, expected_model: str) -> None:
        assert isinstance(agent.model, Gemini)
        assert agent.model.model == expected_model
        assert agent.model.retry_options is not None
        assert (agent.model.retry_options.attempts or 0) >= 5
        assert 429 in (agent.model.retry_options.http_status_codes or [])

    assert isinstance(step0_root_agent, LlmAgent)
    _assert_gemini_with_retry(step0_root_agent, "gemini-4-hydrogen")
    assert "ワーケーション" in str(step0_root_agent.instruction)
    assert get_city_workcation_info("札幌")["city"] == "sapporo"

    assert isinstance(step1_root_agent, LlmAgent)
    _assert_gemini_with_retry(step1_root_agent, "gemini-3.8-flash")
    assert "150,000" in str(step1_root_agent.instruction) or "15万円" in str(
        step1_root_agent.instruction
    )
    assert any(isinstance(t, McpToolset) for t in step1_root_agent.tools)

    assert isinstance(step2_starter_agent, Workflow)
    assert step2_starter_agent.name == "step2_starter_workflow"

    assert isinstance(step2_workflow_root_agent, Workflow)
    assert step2_workflow_root_agent.name == "workcation_concierge_workflow"
    _assert_gemini_with_retry(intake_agent, "gemini-4-hydrogen")
    _assert_gemini_with_retry(search_agent, "gemini-4-hydrogen")
    assert manager_approval_task.mode == "task"
    _assert_gemini_with_retry(manager_approval_task, "gemini-4-hydrogen")
    _assert_gemini_with_retry(booking_agent, "gemini-4-hydrogen")
    assert booking_agent.before_tool_callback is not None
    assert any(isinstance(t, McpToolset) for t in search_agent.tools)
    assert any(isinstance(t, McpToolset) for t in booking_agent.tools)


async def test_workflow_deterministic_auto_book_and_approval_via_runner() -> None:
    # ADK 2.0 Workflow + InMemoryRunner で並列Join・確定計算分岐・上長承認後の上限引き上げを検証
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

    def fake_approval_task(node_input: dict[str, Any]) -> dict[str, Any]:
        return {
            "approved": True,
            "approved_limit_jpy": 250000,
            "approver_comment": "ハワイ開発合宿のため承認",
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
                    "needs_approval": fake_approval_task,
                },
            ),
            (fake_approval_task, apply_approval_decision),
            (
                apply_approval_decision,
                {
                    "approved": fake_booking_agent,
                    DEFAULT_ROUTE: replan_notice,
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

    # 2. ハワイ4泊 (242,000円) は承認タスク経由で上限 250,000円に更新されて予約完了
    s2 = await runner.session_service.create_session(app_name="workcation_test_app", user_id="u1")
    msg_hawaii = types.Content(role="user", parts=[types.Part(text="hawaii 4 nights")])
    events_hawaii = [
        e async for e in runner.run_async(user_id="u1", session_id=s2.id, new_message=msg_hawaii)
    ]
    outputs_hawaii = [e.output for e in events_hawaii if e.output]
    assert any(
        isinstance(o, dict) and o.get("status") == "CONFIRMED" and o.get("total_jpy") == 242000
        for o in outputs_hawaii
    )
    updated_session = await runner.session_service.get_session(
        app_name="workcation_test_app", user_id="u1", session_id=s2.id
    )
    assert updated_session is not None
    assert updated_session.state.get("approved_limit_jpy") == 250000


async def test_agent_runtime_playground_adapter_creates_and_lists_sessions() -> None:
    # Agent Runtime のクラウドコンソール プレイグラウンド用エンドポイントが動作することを検証
    import httpx
    from step2_workflow_agent.fast_api_app import app as fastapi_app

    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/reasoning_engine",
            json={"class_method": "async_create_session", "input": {"user_id": "playground_user"}},
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert "output" in payload
        out_user = payload["output"].get("userId") or payload["output"].get("user_id")
        assert out_user == "playground_user"
