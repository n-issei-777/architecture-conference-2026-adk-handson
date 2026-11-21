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

"""Unit tests for Step 2 deterministic workflow nodes and RequestInput gate."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

from google.adk import Context
from google.adk.events import Event, RequestInput
from step2_workflow_agent.agent import (
    _manager_approval_gate_fn as manager_approval_gate,
)
from step2_workflow_agent.agent import (
    calculate_and_route,
    fetch_workcation_metrics_node,
)


@dataclass
class _FakeContext:
    state: dict[str, Any] = field(default_factory=dict)
    resume_inputs: dict[str, Any] = field(default_factory=dict)


def _as_ctx(fake: _FakeContext) -> Context:
    return cast(Context, fake)


def test_fetch_workcation_metrics_node() -> None:
    # 構造化されたTripRequest入力から対象都市のワーケーション指標を取得することを検証
    result = fetch_workcation_metrics_node(
        {"city": "sapporo", "nights": 2, "flight_class": "economy", "room_type": "standard"}
    )
    assert result["status"] == "ok"
    assert result["city"] == "sapporo"
    assert result["wifi_mbps"] >= 50


def test_calculate_and_route_auto_book_under_150k() -> None:
    # 150,000円以下の旅程 (札幌2泊=59,000円) で route="auto_book" が返ることを検証
    ctx = _FakeContext(state={"approved_limit_jpy": 150000})
    joined_input = {
        "fetch_workcation_metrics": {"city": "sapporo", "wifi_mbps": 120},
        "search_agent": {
            "city": "sapporo",
            "nights": 2,
            "flight_class": "economy",
            "room_type": "standard",
        },
    }
    event = calculate_and_route(_as_ctx(ctx), joined_input)
    assert isinstance(event, Event)
    assert event.actions.route == "auto_book"
    output = cast(dict[str, Any], event.output)
    assert output["total_jpy"] == 59000


def test_calculate_and_route_needs_approval_over_150k() -> None:
    # 150,000円超過の旅程 (ハワイ4泊=242,000円) で route="needs_approval" が返ることを検証
    ctx = _FakeContext(state={"approved_limit_jpy": 150000})
    joined_input = {
        "fetch_workcation_metrics": {"city": "hawaii", "wifi_mbps": 95},
        "search_agent": {
            "city": "hawaii",
            "nights": 4,
            "flight_class": "economy",
            "room_type": "standard",
        },
    }
    event = calculate_and_route(_as_ctx(ctx), joined_input)
    assert isinstance(event, Event)
    assert event.actions.route == "needs_approval"
    output = cast(dict[str, Any], event.output)
    assert output["total_jpy"] == 242000


async def test_manager_approval_gate_pauses_then_updates_limit() -> None:
    # 初回実行時に RequestInput を yield し、承認再開時に approved_limit_jpy を更新することを検証
    plan_payload = {
        "city": "hawaii",
        "nights": 4,
        "flight_class": "economy",
        "room_type": "standard",
        "total_jpy": 242000,
    }

    # 1. 未承認状態では RequestInput を生成して一時停止
    ctx_initial = _FakeContext(state={"approved_limit_jpy": 150000}, resume_inputs={})
    emitted_initial = [
        item async for item in manager_approval_gate(_as_ctx(ctx_initial), plan_payload)
    ]
    assert len(emitted_initial) == 1
    assert isinstance(emitted_initial[0], RequestInput)
    assert emitted_initial[0].interrupt_id == "manager_approval"

    # 2. 上長承認レスポンス到着時は state["approved_limit_jpy"] を引き上げて route="approved" を送出
    ctx_resumed = _FakeContext(
        state={"approved_limit_jpy": 150000},
        resume_inputs={
            "manager_approval": {
                "approved": True,
                "approved_limit_jpy": 250000,
                "approver_comment": "Approved for Q4 customer workshop in Hawaii",
            }
        },
    )
    emitted_resumed = [
        item async for item in manager_approval_gate(_as_ctx(ctx_resumed), plan_payload)
    ]
    assert len(emitted_resumed) == 1
    resumed_event = emitted_resumed[0]
    assert isinstance(resumed_event, Event)
    assert resumed_event.actions.route == "approved"
    assert resumed_event.actions.state_delta["approved_limit_jpy"] == 250000
