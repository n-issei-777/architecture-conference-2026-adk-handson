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

"""Reusable deterministic nodes and Event helpers for Step 2 ADK 2.0 Workflow."""

from __future__ import annotations

from typing import Any

from google.adk import Context, Event
from google.adk.events import EventActions
from google.adk.models import Gemini
from google.adk.workflow import DEFAULT_ROUTE, FunctionNode
from google.genai import types

from workcation_concierge.guardrails import DEFAULT_APPROVED_LIMIT_JPY
from workcation_concierge.mcp_server import (
    calculate_itinerary_cost,
    fetch_workcation_metrics,
)
from workcation_concierge.schemas import ApprovalDecision

# 60 名同時実行時の 429/503 対策として指数バックオフ＋ジッター付きリトライを設定
DEFAULT_RETRY_OPTIONS = types.HttpRetryOptions(
    attempts=5,
    initial_delay=1.0,
    max_delay=16.0,
    exp_base=2.0,
    jitter=1.0,
    http_status_codes=[429, 500, 503, 504],
)


def gemini_model(model_name: str = "gemini-4-hydrogen") -> Gemini:
    """429/503 リトライ設定付きの Gemini モデルオブジェクトを生成."""
    return Gemini(model=model_name, retry_options=DEFAULT_RETRY_OPTIONS)


def text_event(
    text: str,
    *,
    output: Any = None,
    route: str | None = None,
    state_delta: dict[str, Any] | None = None,
) -> Event:
    """日本語テキストとルーティング・state_delta をまとめて Event 化するヘルパー."""
    actions_kwargs: dict[str, Any] = {}
    if route is not None:
        actions_kwargs["route"] = route
    if state_delta is not None:
        actions_kwargs["state_delta"] = state_delta
    return Event(
        content=types.Content(role="model", parts=[types.Part(text=text)]),
        output=output,
        actions=EventActions(**actions_kwargs),
    )


def fetch_workcation_metrics_node(node_input: dict[str, Any]) -> dict[str, Any]:
    """指定都市の Wi-Fi 速度とコワーキングスペース数を確定取得."""
    city = str(node_input.get("city", "sapporo"))
    # 後段の確定計算が LLM を経由しない値を使えるよう、TripRequest をそのまま引き継ぐ
    return {**fetch_workcation_metrics(city), "trip_request": dict(node_input)}


fetch_workcation_metrics_step = FunctionNode(
    func=fetch_workcation_metrics_node,
    name="fetch_workcation_metrics",
)


def build_cost_plan(ctx: Context, node_input: dict[str, Any]) -> tuple[dict[str, Any], int, int]:
    """並列リサーチ結果を集約し、確定合計金額と承認上限額を返す."""
    metrics = (
        node_input.get("fetch_workcation_metrics")
        or node_input.get("fetch_workcation_metrics_node")
        or {}
    )
    candidate = node_input.get("search_agent") or node_input.get("fake_search_agent") or {}
    # 泊数・クラス・部屋は intake の TripRequest を優先 (search_agent の出力は便名等の補足のみ)
    trip = {**candidate, **(metrics.get("trip_request") or {})}

    city = str(trip.get("city") or metrics.get("city") or "sapporo")
    nights = int(trip.get("nights", 2))
    flight_class = str(trip.get("flight_class", "economy"))
    room_type = str(trip.get("room_type", "standard"))

    cost_breakdown = calculate_itinerary_cost(
        city=city,
        nights=nights,
        flight_class=flight_class,
        room_type=room_type,
    )
    total_jpy = int(cost_breakdown.get("total_jpy", 0))
    # 承認は旅程ごと。過去の承認で引き上げた上限は引き継がず、既定上限で判定
    approved_limit = DEFAULT_APPROVED_LIMIT_JPY
    merged_plan = {
        **cost_breakdown,
        "total_jpy": total_jpy,
        "wifi_mbps": int(metrics.get("wifi_mbps", cost_breakdown.get("wifi_mbps", 100))),
        "coworking_spaces": int(metrics.get("coworking_spaces", 0)),
        "approved_limit_jpy": approved_limit,
    }
    return merged_plan, total_jpy, approved_limit


def apply_approval_decision(ctx: Context, node_input: ApprovalDecision | dict[str, Any]) -> Event:
    """上長の判断結果に基づき Session.state['approved_limit_jpy'] を更新して分岐."""
    decision = (
        node_input.model_dump() if isinstance(node_input, ApprovalDecision) else dict(node_input)
    )
    plan = dict(ctx.state.get("calculated_cost") or {})
    requested_total = int(plan.get("total_jpy", 0))
    new_limit = int(decision.get("approved_limit_jpy") or 0)
    # 承認者の上限額が合計金額に満たない場合は、上限を書き換えず未承認として扱う
    is_approved = bool(decision.get("approved", False)) and new_limit >= requested_total

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
        else "合計金額以上の上限額での上長承認が得られなかったため、予約せず再計画へ進みます。"
    )
    return text_event(
        msg,
        output=updated_plan,
        route=route,
        state_delta={
            "approved_limit_jpy": updated_limit,
            "approval_decision": decision,
        },
    )


def replan_notice(node_input: dict[str, Any]) -> Event:
    """上長承認が却下された場合の代替案案内ノード."""
    city = str(node_input.get("city", "unknown"))
    total_jpy = int(node_input.get("total_jpy", 0))
    msg = (
        f"上長承認が見送られたため、{city}（合計 {total_jpy:,} 円）の予約を中止しました。"
        "150,000 円以内の国内プラン（例: 札幌2泊 59,000 円、沖縄3泊 93,000 円）をご検討ください。"
    )
    return text_event(
        msg,
        output={"status": "NEEDS_REPLAN", "city": city, "total_jpy": total_jpy, "message": msg},
    )
