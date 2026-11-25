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

"""Unit tests for Step 2 deterministic workflow nodes and conversational approval routing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

from google.adk import Context
from google.adk.events import Event
from google.adk.workflow import DEFAULT_ROUTE
from step2_workflow_agent.agent import (
    apply_approval_decision,
    calculate_and_route,
    fetch_workcation_metrics_node,
)

from workcation_concierge.schemas import ApprovalDecision


@dataclass
class _FakeContext:
    state: dict[str, Any] = field(default_factory=dict)


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


def test_apply_approval_decision_updates_limit_or_routes_to_default() -> None:
    # タスクノードの上長承認結果に応じて Session.state の上限更新と分岐が行われることを検証
    calculated_plan = {
        "city": "hawaii",
        "nights": 4,
        "flight_class": "economy",
        "room_type": "standard",
        "total_jpy": 242000,
    }
    ctx_ok = _FakeContext(state={"approved_limit_jpy": 150000, "calculated_cost": calculated_plan})
    ev_ok = apply_approval_decision(
        _as_ctx(ctx_ok),
        ApprovalDecision(
            approved=True,
            approved_limit_jpy=250000,
            approver_comment="ハワイ開発合宿のため承認",
        ),
    )
    assert ev_ok.actions.route == "approved"
    assert ev_ok.actions.state_delta["approved_limit_jpy"] == 250000
    out_ok = cast(dict[str, Any], ev_ok.output)
    assert out_ok["city"] == "hawaii"
    assert out_ok["total_jpy"] == 242000

    ctx_ng = _FakeContext(state={"approved_limit_jpy": 150000, "calculated_cost": calculated_plan})
    ev_ng = apply_approval_decision(
        _as_ctx(ctx_ng),
        ApprovalDecision(approved=False, approved_limit_jpy=150000, approver_comment="予算超過"),
    )
    assert ev_ng.actions.route == DEFAULT_ROUTE
    assert ev_ng.actions.state_delta["approved_limit_jpy"] == 150000


def test_cost_uses_trip_request_not_llm_relayed_candidate() -> None:
    # search_agent (LLM) が泊数を落としても、intake の TripRequest の値で計算することを検証
    trip = {"city": "hawaii", "nights": 4, "flight_class": "economy", "room_type": "standard"}
    joined_input = {
        "fetch_workcation_metrics": fetch_workcation_metrics_node(trip),
        "search_agent": {"city": "hawaii"},
    }
    event = calculate_and_route(_as_ctx(_FakeContext(state={})), joined_input)
    assert cast(dict[str, Any], event.output)["total_jpy"] == 242000
    assert event.actions.route == "needs_approval"


def test_previous_approval_does_not_carry_over_to_next_trip() -> None:
    # 前の旅程で引き上げた上限が残っていても、新しい見積もりは既定上限で判定することを検証
    trip = {"city": "hawaii", "nights": 4, "flight_class": "economy", "room_type": "standard"}
    joined_input = {
        "fetch_workcation_metrics": fetch_workcation_metrics_node(trip),
        "search_agent": trip,
    }
    event = calculate_and_route(
        _as_ctx(_FakeContext(state={"approved_limit_jpy": 250000})), joined_input
    )
    assert event.actions.route == "needs_approval"
    assert event.actions.state_delta["approved_limit_jpy"] == 150000


def test_approval_below_trip_total_is_not_silently_raised() -> None:
    # 承認者の上限額が合計金額に満たない場合、上限を書き換えず再計画へ進むことを検証
    ctx = _FakeContext(state={"calculated_cost": {"city": "hawaii", "total_jpy": 242000}})
    event = apply_approval_decision(
        _as_ctx(ctx), ApprovalDecision(approved=True, approved_limit_jpy=200000)
    )
    assert event.actions.route == DEFAULT_ROUTE
    assert event.actions.state_delta["approved_limit_jpy"] == 150000
