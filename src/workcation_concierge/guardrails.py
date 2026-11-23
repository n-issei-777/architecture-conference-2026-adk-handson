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

"""Client-side deterministic guardrail (before_tool_callback) for Travel SaaS MCP."""

from __future__ import annotations

from typing import Any

from google.adk.tools import BaseTool, ToolContext

from workcation_concierge.mcp_server import calculate_itinerary_cost

# デフォルトの自己承認予算上限 (150,000円)
DEFAULT_APPROVED_LIMIT_JPY = 150_000


def enforce_booking_guardrail(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
) -> dict[str, Any] | None:
    """予約確定ツール (reserve_itinerary) の実行直前に社内規定を検証するコールバック."""
    if not tool.name.endswith("reserve_itinerary"):
        return None  # 検索系ツールはそのまま通過

    print(f"[Callback検査] tool={tool.name}, args={args}")
    role = str(tool_context.state.get("user_role", "member")).lower()
    limit = int(tool_context.state.get("approved_limit_jpy", DEFAULT_APPROVED_LIMIT_JPY))
    flight_class = str(args.get("flight_class", "economy")).lower()
    room_type = str(args.get("room_type", "standard")).lower()

    # 1. 一般社員によるスイートルーム・ビジネスクラス予約をブロック
    if role != "executive" and (room_type == "suite" or flight_class == "business"):
        return {
            "status": "BLOCKED",
            "violation_type": "GRADE_POLICY_VIOLATION",
            "message": "社内規定違反: 一般社員はエコノミー・スタンダードのみ予約可能。",
        }

    # 2. LLMの申告額を鵜呑みにせずサーバー側で再計算した金額で上限を検証
    claimed_total = int(args.get("total_jpy", 0))
    recalculated = calculate_itinerary_cost(
        city=str(args.get("city", "")),
        nights=int(args.get("nights", 0)),
        flight_class=flight_class,
        room_type=room_type,
    )
    verified_total = (
        max(claimed_total, int(recalculated["total_jpy"]))
        if recalculated.get("status") == "ok"
        else claimed_total
    )
    if verified_total > limit:
        return {
            "status": "BLOCKED",
            "violation_type": "BUDGET_LIMIT_EXCEEDED",
            "approved_limit_jpy": limit,
            "total_jpy": verified_total,
            "message": f"予算上限超過: 合計 {verified_total:,} 円が上限 {limit:,} 円を超過。",
        }

    return None  # None を返した場合のみ MCP 予約ツールを実行
