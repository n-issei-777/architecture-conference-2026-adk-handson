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

"""Unit tests for client-side before_tool_callback booking guardrails."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

from google.adk.tools import BaseTool, ToolContext

from workcation_concierge.guardrails import (
    DEFAULT_APPROVED_LIMIT_JPY,
    enforce_booking_guardrail,
)


@dataclass
class _StubTool:
    name: str


@dataclass
class _StubToolContext:
    state: dict[str, Any] = field(default_factory=dict)


def _as_tool(stub: _StubTool) -> BaseTool:
    return cast(BaseTool, stub)


def _as_ctx(stub: _StubToolContext) -> ToolContext:
    return cast(ToolContext, stub)


def test_non_booking_tools_pass_through() -> None:
    # 予約以外のツール呼び出しはそのまま通過することを検証
    ctx = _StubToolContext(state={})
    result = enforce_booking_guardrail(
        tool=_as_tool(_StubTool(name="search_flights")),
        args={"city": "hawaii"},
        tool_context=_as_ctx(ctx),
    )
    assert result is None


def test_suite_or_business_blocked_for_member() -> None:
    # 一般社員 (member) によるスイートルームおよびビジネスクラス予約が100%ブロックされることを検証
    ctx = _StubToolContext(
        state={"user_role": "member", "approved_limit_jpy": DEFAULT_APPROVED_LIMIT_JPY}
    )
    tool = _as_tool(_StubTool(name="reserve_itinerary"))

    suite_res = enforce_booking_guardrail(
        tool=tool,
        args={
            "city": "sapporo",
            "nights": 2,
            "flight_class": "economy",
            "room_type": "suite",
            "total_jpy": 115000,
        },
        tool_context=_as_ctx(ctx),
    )
    assert suite_res is not None
    assert suite_res["status"] == "BLOCKED"
    assert suite_res["violation_type"] == "GRADE_POLICY_VIOLATION"

    business_res = enforce_booking_guardrail(
        tool=tool,
        args={
            "city": "sapporo",
            "nights": 1,
            "flight_class": "business",
            "room_type": "standard",
            "total_jpy": 92000,
        },
        tool_context=_as_ctx(ctx),
    )
    assert business_res is not None
    assert business_res["status"] == "BLOCKED"
    assert business_res["violation_type"] == "GRADE_POLICY_VIOLATION"


def test_budget_exceeded_blocked_at_default_limit() -> None:
    # デフォルト承認上限 (150,000円) を超えるハワイ4泊 (242,000円) が100%ブロックされることを検証
    ctx = _StubToolContext(state={"user_role": "member"})
    tool = _as_tool(_StubTool(name="reserve_itinerary"))

    over_budget_res = enforce_booking_guardrail(
        tool=tool,
        args={
            "city": "hawaii",
            "nights": 4,
            "flight_class": "economy",
            "room_type": "standard",
            "total_jpy": 242000,
        },
        tool_context=_as_ctx(ctx),
    )
    assert over_budget_res is not None
    assert over_budget_res["status"] == "BLOCKED"
    assert over_budget_res["violation_type"] == "BUDGET_LIMIT_EXCEEDED"
    assert over_budget_res["approved_limit_jpy"] == 150000


def test_booking_succeeds_after_approved_limit_raised() -> None:
    # 上長承認ゲートで approved_limit_jpy が250,000円に更新された後は予約許可されることを検証
    ctx = _StubToolContext(state={"user_role": "member", "approved_limit_jpy": 250000})
    tool = _as_tool(_StubTool(name="reserve_itinerary"))

    allowed_res = enforce_booking_guardrail(
        tool=tool,
        args={
            "city": "hawaii",
            "nights": 4,
            "flight_class": "economy",
            "room_type": "standard",
            "total_jpy": 242000,
        },
        tool_context=_as_ctx(ctx),
    )
    assert allowed_res is None
