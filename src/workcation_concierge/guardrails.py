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

"""Client-side deterministic guardrails (before_tool_callback) for Travel SaaS MCP."""

from __future__ import annotations

from typing import Any

from google.adk.tools import BaseTool, ToolContext

# デフォルトの自己承認予算上限 (150,000円)
DEFAULT_APPROVED_LIMIT_JPY = 150_000


def enforce_booking_guardrail(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
) -> dict[str, Any] | None:
    """Deterministic `before_tool_callback` blocking policy-violating reservations.

    Why this callback is required at the client trust boundary:
    The external Travel SaaS MCP (`reserve_itinerary`) knows inventory and prices,
    but has zero visibility into internal corporate grades (`user_role`) or dynamic
    session approval limits (`Session.state["approved_limit_jpy"]`).

    Rules enforced 100% deterministically before tool execution:
    1. Only `reserve_itinerary` calls are inspected; read-only search tools pass through.
    2. For `user_role == "member"` (default), `flight_class == "business"` or
       `room_type == "suite"` is strictly blocked.
    3. If `total_jpy > state.get("approved_limit_jpy", 150000)`, the booking is blocked
       until the manager approval gate raises `state["approved_limit_jpy"]`.

    Returns:
        `None` to allow the tool call to proceed, or a structured `{"status": "BLOCKED", ...}`
        dictionary to short-circuit execution.
    """
    # 予約確定ツール以外はそのまま通過
    if not tool.name.endswith("reserve_itinerary"):
        return None

    state = tool_context.state
    user_role = str(state.get("user_role", "member")).strip().lower()
    approved_limit_jpy = int(state.get("approved_limit_jpy", DEFAULT_APPROVED_LIMIT_JPY))

    flight_class = str(args.get("flight_class", "economy")).strip().lower()
    room_type = str(args.get("room_type", "standard")).strip().lower()
    total_jpy = int(args.get("total_jpy", 0))

    # 1. 役職グレード規定の検証 (一般社員はビジネスクラス・スイートルーム不可)
    if user_role != "executive" and (flight_class == "business" or room_type == "suite"):
        return {
            "status": "BLOCKED",
            "violation_type": "GRADE_POLICY_VIOLATION",
            "user_role": user_role,
            "requested_flight_class": flight_class,
            "requested_room_type": room_type,
            "message": (
                "Booking blocked by corporate policy guardrail: "
                f"role '{user_role}' is only permitted to book 'economy' flights "
                "and 'standard' rooms (requested: "
                f"flight_class='{flight_class}', room_type='{room_type}')."
            ),
        }

    # 2. 承認予算上限の検証 (上限超過時は上長承認ゲートによる引き上げが必須)
    if total_jpy > approved_limit_jpy:
        return {
            "status": "BLOCKED",
            "violation_type": "BUDGET_LIMIT_EXCEEDED",
            "total_jpy": total_jpy,
            "approved_limit_jpy": approved_limit_jpy,
            "message": (
                "Booking blocked by corporate budget guardrail: "
                f"total_jpy ({total_jpy:,} JPY) exceeds current approved_limit_jpy "
                f"({approved_limit_jpy:,} JPY). Manager approval is required to raise "
                "Session.state['approved_limit_jpy']."
            ),
        }

    # すべてのガードレール条件を満たした場合は None を返してツール実行を許可
    return None
