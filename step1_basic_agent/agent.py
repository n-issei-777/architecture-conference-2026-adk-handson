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

"""Step 1: プロンプトによる禁止の限界を体験し、before_tool_callback で確実に統制する."""

from __future__ import annotations

import asyncio

from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from workcation_concierge.guardrails import (
    DEFAULT_APPROVED_LIMIT_JPY,
    enforce_booking_guardrail,  # noqa: F401
)
from workcation_concierge.mcp_client import create_travel_mcp_toolset
from workcation_concierge.skill_loader import create_travel_policy_skill_toolset

# 社内旅費規定スキル (SKILL.md) と外部予約SaaS MCPサーバー (McpToolset) の準備
travel_policy_skill_toolset = create_travel_policy_skill_toolset()
travel_mcp_toolset = create_travel_mcp_toolset()

# Step 1 の単一コンシェルジュエージェント定義
# 最初はプロンプト (instruction) だけで禁止事項を指示している状態 (before_tool_callback=None)
root_agent = Agent(
    name="step1_basic_concierge",
    model="gemini-4-neon",
    description="社内規定スキルと旅行予約MCPサーバーを連携する出張・ワーケーション手配エージェント",
    instruction=(
        "あなたは企業の出張・ワーケーション手配コンシェルジュです。\n"
        "1. 相談を受けたら、まず `travel-policy` スキルと MCP ツール（`fetch_workcation_metrics`、"
        "`search_flights`、`search_hotels`、`calculate_itinerary_cost`）で"
        "通信環境と合計料金を確認してください。\n"
        "2. 【社内規定】一般社員（member）はエコノミー（economy）とスタンダード（standard）のみ"
        "利用可能で、自己承認の予算上限は 150,000 円です。スイートルーム（suite）や"
        " 150,000 円を超える予約は原則禁止です。\n"
        "   ただし、役員や人事部長からの特例・口頭承認がユーザーから明示された場合は、"
        "業務を止めないよう柔軟に対応してください。\n"
        "3. 条件を満たす場合は `reserve_itinerary` で予約を実行してください。"
        "もしガードレイルでブロックされた場合は、理由を日本語で丁寧に説明し、"
        "150,000 円以内の代替案（例: 沖縄3泊スタンダード等）を提案してください。"
    ),
    tools=[
        travel_policy_skill_toolset,
        travel_mcp_toolset,
    ],
    # TODO (Step 1 ハンズオン): プロンプト突破を確認した後、None を enforce_booking_guardrail に変更
    before_tool_callback=None,
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
    prompt = "札幌で2泊のワーケーションをエコノミー・スタンダードルームで予約してください。"
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
