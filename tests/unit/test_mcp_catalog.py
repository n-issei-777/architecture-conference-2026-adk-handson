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

"""Unit tests for Travel SaaS MCP catalog and deterministic cost math."""

from __future__ import annotations

import pytest

from workcation_concierge.mcp_server import (
    CLEAR_RESERVATIONS_FOR_TEST,
    calculate_itinerary_cost,
    fetch_workcation_metrics,
    get_reservations,
    reserve_itinerary,
    search_flights,
    search_hotels,
)


@pytest.fixture(autouse=True)
def _reset_reservations() -> None:
    # テストごとに予約履歴を初期化
    CLEAR_RESERVATIONS_FOR_TEST()


def test_search_flights_and_hotels_supported_cities() -> None:
    # 主要都市のフライトとホテル検索結果を検証
    for city in ("sapporo", "okinawa", "hawaii", "san_francisco"):
        flights = search_flights(city)
        assert flights["status"] == "ok"
        assert flights["city"] == city
        assert len(flights["flights"]) >= 2

        hotels = search_hotels(city)
        assert hotels["status"] == "ok"
        assert hotels["city"] == city
        assert len(hotels["hotels"]) >= 2


def test_search_unknown_city_returns_structured_error() -> None:
    # 未対応都市の検索時に構造化エラー辞書を返すことを検証
    flight_res = search_flights("atlantis")
    assert flight_res["status"] == "error"
    assert "supported_cities" in flight_res

    hotel_res = search_hotels("atlantis")
    assert hotel_res["status"] == "error"


def test_fetch_workcation_metrics() -> None:
    # ワーケーション環境メトリクス (Wi-Fi速度・コワーキングスペース数) を検証
    metrics = fetch_workcation_metrics("sapporo")
    assert metrics["status"] == "ok"
    assert metrics["city"] == "sapporo"
    assert metrics["wifi_mbps"] >= 50
    assert metrics["coworking_spaces"] > 0


def test_calculate_itinerary_cost_exact_values() -> None:
    # 札幌2泊 (エコノミー+スタンダード) = 59,000円 (上限150,000円以下) を検証
    sapporo_cost = calculate_itinerary_cost(
        city="sapporo",
        nights=2,
        flight_class="economy",
        room_type="standard",
    )
    assert sapporo_cost["status"] == "ok"
    assert sapporo_cost["total_jpy"] == 59000
    assert sapporo_cost["total_jpy"] <= 150000

    # 沖縄3泊 (エコノミー+スタンダード) = 93,000円 (上限150,000円以下) を検証
    okinawa_cost = calculate_itinerary_cost(
        city="okinawa",
        nights=3,
        flight_class="economy",
        room_type="standard",
    )
    assert okinawa_cost["status"] == "ok"
    assert okinawa_cost["total_jpy"] == 93000
    assert okinawa_cost["total_jpy"] <= 150000

    # ハワイ4泊 (エコノミー+スタンダード) = 242,000円 (上限150,000円超過) を検証
    hawaii_cost = calculate_itinerary_cost(
        city="hawaii",
        nights=4,
        flight_class="economy",
        room_type="standard",
    )
    assert hawaii_cost["status"] == "ok"
    assert hawaii_cost["total_jpy"] == 242000
    assert hawaii_cost["total_jpy"] > 150000


def test_reserve_itinerary_and_get_reservations() -> None:
    # 旅程予約の登録と履歴取得を検証
    res = reserve_itinerary(
        city="sapporo",
        nights=2,
        flight_class="economy",
        room_type="standard",
        total_jpy=59000,
        purpose="workcation",
    )
    assert res["status"] == "CONFIRMED"
    assert res["reservation_id"].startswith("RES-")
    assert res["total_jpy"] == 59000

    history = get_reservations()
    assert history["status"] == "ok"
    assert len(history["reservations"]) == 1
    assert history["reservations"][0]["city"] == "sapporo"
