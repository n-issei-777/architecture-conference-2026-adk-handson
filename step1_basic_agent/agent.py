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

"""Step 1: Single LlmAgent + SkillToolset + Deterministic before_tool_callback."""

from __future__ import annotations

import asyncio

from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from workcation_concierge.guardrails import (
    DEFAULT_APPROVED_LIMIT_JPY,
    enforce_booking_guardrail,
)
from workcation_concierge.mcp_server import (
    calculate_itinerary_cost,
    fetch_workcation_metrics,
    get_reservations,
    reserve_itinerary,
    search_flights,
    search_hotels,
)
from workcation_concierge.skill_loader import create_travel_policy_skill_toolset

# 社内規定スキルを管理する SkillToolset の構築
travel_policy_skill_toolset = create_travel_policy_skill_toolset()

# Step 1 の単一コンシェルジュエージェント定義
root_agent = Agent(
    name="step1_basic_concierge",
    model="gemini-4-neon",
    description=(
        "Workcation and corporate travel concierge agent with Travel Policy Skill "
        "and deterministic client-side booking guardrails."
    ),
    instruction=(
        "You are the Workcation & Smart Travel Concierge.\n"
        "1. First load or consult the 'travel-policy' skill to verify corporate rules "
        "(Wi-Fi >= 50 Mbps, economy flight & standard room for members, "
        "150,000 JPY default limit).\n"
        "2. Use `fetch_workcation_metrics`, `search_flights`, `search_hotels`, and "
        "`calculate_itinerary_cost` to inspect options and compute exact total JPY.\n"
        "3. Call `reserve_itinerary` to book the trip. If `enforce_booking_guardrail` blocks "
        "the tool call due to grade violation or budget limit exceeded, clearly explain the "
        "reason to the user and suggest a compliant alternative."
    ),
    tools=[
        travel_policy_skill_toolset,
        search_flights,
        search_hotels,
        fetch_workcation_metrics,
        calculate_itinerary_cost,
        reserve_itinerary,
        get_reservations,
    ],
    before_tool_callback=enforce_booking_guardrail,
)


async def _run_demo() -> None:
    # Step 1 のローカルCLIデモ実行 (InMemorySessionService + Runner)
    session_service = InMemorySessionService()
    runner = Runner(
        app_name="step1_basic_agent_demo",
        agent=root_agent,
        session_service=session_service,
    )
    session = await session_service.create_session(
        app_name="step1_basic_agent_demo",
        user_id="demo_user",
        state={
            "user_role": "member",
            "approved_limit_jpy": DEFAULT_APPROVED_LIMIT_JPY,
        },
    )
    prompt = "札幌で2泊のワーケーションをエコノミー・スタンダードルームで予約して。"
    print(f"[User]: {prompt}")
    msg = types.Content(role="user", parts=[types.Part(text=prompt)])
    async for event in runner.run_async(
        user_id="demo_user",
        session_id=session.id,
        new_message=msg,
    ):
        if event.content and event.content.parts:
            text_parts = [p.text for p in event.content.parts if p.text]
            if text_parts:
                print(f"[{event.author}]: {' '.join(text_parts)}")


def main() -> None:
    """CLI entrypoint for Step 1 Basic Agent demo."""
    asyncio.run(_run_demo())


if __name__ == "__main__":
    main()
