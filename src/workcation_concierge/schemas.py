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

"""Pydantic v2 data contracts for the Workcation & Smart Travel Concierge."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TripRequest(BaseModel):
    """ユーザー入力から抽出する出張・ワーケーション希望条件."""

    city: str = Field(description="行き先都市 ('sapporo', 'okinawa', 'hawaii', 'san_francisco')")
    nights: int = Field(
        default=2,
        ge=1,
        le=30,
        description="宿泊数 (泊)",
    )
    flight_class: Literal["economy", "business"] = Field(
        default="economy",
        description="航空機クラス ('economy' または 'business')",
    )
    room_type: Literal["standard", "suite"] = Field(
        default="standard",
        description="客室グレード ('standard' または 'suite')",
    )
    purpose: str = Field(
        default="workcation",
        description="出張・合宿の目的",
    )


class CandidatePlan(BaseModel):
    """検索エージェントが選定したフライト・ホテル候補."""

    city: str = Field(description="正規化済みの都市コード")
    nights: int = Field(default=2, ge=1, description="宿泊数 (泊)")
    flight_code: str = Field(default="NH-051", description="選定した便名")
    flight_class: Literal["economy", "business"] = Field(
        default="economy",
        description="選定した航空機クラス",
    )
    hotel_name: str = Field(
        default="Workcation Hub Hotel",
        description="選定したホテル名",
    )
    room_type: Literal["standard", "suite"] = Field(
        default="standard",
        description="選定した客室グレード",
    )
    notes: str = Field(default="", description="候補プランの補足メモ")


class ApprovalDecision(BaseModel):
    """上長承認タスクノードで受け取る承認判断結果."""

    approved: bool = Field(description="予算超過プランを承認する場合は True、却下する場合は False")
    approved_limit_jpy: int = Field(
        default=250000,
        ge=0,
        description="上長が承認した新しい予算上限額 (円)。承認時は合計金額以上 (例: 250000) を指定",
    )
    approver_comment: str = Field(
        default="",
        description="上長からの承認・却下コメント",
    )


class BookingResult(BaseModel):
    """最終的な予約実行結果."""

    status: Literal["CONFIRMED", "BLOCKED", "NEEDS_REPLAN"] = Field(description="最終ステータス")
    reservation_id: str = Field(default="", description="予約確定時の予約番号")
    city: str = Field(description="行き先都市コード")
    nights: int = Field(description="宿泊数 (泊)")
    flight_class: str = Field(default="economy", description="予約した航空機クラス")
    room_type: str = Field(default="standard", description="予約した客室グレード")
    total_jpy: int = Field(description="合計金額 (円)")
    wifi_mbps: int = Field(default=100, description="Wi-Fi 通信速度 (Mbps)")
    summary: str = Field(default="", description="ユーザー向けの日本語完了サマリー")
