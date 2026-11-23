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

"""Unit tests verifying real stdio MCP connection via McpToolset."""

from __future__ import annotations

import pytest
from google.adk.tools.mcp_tool import StreamableHTTPConnectionParams

from workcation_concierge.mcp_client import create_travel_mcp_toolset


async def test_mcp_toolset_discovers_filtered_tools_over_stdio() -> None:
    # McpToolset が実際に mcp_server サブプロセスへ stdio 接続してツール一覧を取得することを検証
    toolset = create_travel_mcp_toolset(tool_filter=["search_flights", "reserve_itinerary"])
    try:
        tools = await toolset.get_tools()
        names = {t.name for t in tools}
        assert names == {"search_flights", "reserve_itinerary"}
    finally:
        await toolset.close()


def test_mcp_toolset_switches_to_streamable_http_when_url_env_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # MCP_SERVER_URL 指定時は Cloud Run 等の StreamableHTTP 接続へ切り替わることを検証
    monkeypatch.setenv("MCP_SERVER_URL", "https://travel-mcp.example.run.app/mcp")
    toolset = create_travel_mcp_toolset(tool_filter=["search_flights"])
    params = toolset._connection_params
    assert isinstance(params, StreamableHTTPConnectionParams)
    assert params.url == "https://travel-mcp.example.run.app/mcp"
