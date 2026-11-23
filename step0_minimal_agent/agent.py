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

"""Step 0: 最小構成のエージェントで Agent・SessionService・Runner の基本を学ぶ."""

from __future__ import annotations

import asyncio
from typing import Any

from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from workcation_concierge.mcp_server import (
    calculate_itinerary_cost,
    fetch_workcation_metrics,
)


def get_city_workcation_info(city: str, nights: int = 2) -> dict[str, Any]:
    """指定した都市の Wi-Fi 速度と、指定泊数での標準プラン合計料金を取得するツール関数.

    Args:
        city: 都市名 ('札幌', '沖縄', 'ハワイ', 'サンフランシスコ' など)
        nights: 宿泊数 (デフォルト 2 泊)
    """
    metrics = fetch_workcation_metrics(city)
    if metrics.get("status") != "ok":
        return metrics
    cost = calculate_itinerary_cost(city=city, nights=nights)
    return {
        "city": metrics["city"],
        "display_name": metrics["display_name"],
        "nights": nights,
        "wifi_mbps": metrics["wifi_mbps"],
        "coworking_spaces": metrics["coworking_spaces"],
        "total_jpy": cost["total_jpy"],
    }


# 最小構成の ADK エージェント定義 (Agent + ツール関数1個)
root_agent = Agent(
    name="step0_minimal_agent",
    model="gemini-4-hydrogen",
    description="都市ごとのワーケーション通信環境と概算費用を案内する最小エージェント",
    instruction=(
        "あなたは親切なワーケーション案内アシスタントです。\n"
        "- 都市や宿泊数の相談を受けたら、`get_city_workcation_info` を使って"
        "正確な Wi-Fi 速度と合計料金を調べてください。\n"
        "- 回答は簡潔でわかりやすい日本語のマークダウン形式で出力してください。"
    ),
    tools=[get_city_workcation_info],
)


async def _run_demo() -> None:
    # SessionService (記憶) と Runner (実行制御) を使った2ターンの会話デモ
    session_service = InMemorySessionService()
    runner = Runner(
        app_name="step0_demo",
        agent=root_agent,
        session_service=session_service,
    )
    session = await session_service.create_session(app_name="step0_demo", user_id="user_01")

    for prompt in [
        "札幌で2泊する場合のWi-Fi速度と費用を教えて",
        "もし3泊に延ばしたらいくらになる？",
    ]:
        print(f"\n[User]: {prompt}")
        msg = types.Content(role="user", parts=[types.Part(text=prompt)])
        async for event in runner.run_async(
            user_id="user_01", session_id=session.id, new_message=msg
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.function_call:
                        print(
                            f"  -> [Tool Call] {part.function_call.name}({part.function_call.args})"
                        )
                    if part.text:
                        print(f"[{event.author}]: {part.text}")


if __name__ == "__main__":
    asyncio.run(_run_demo())
