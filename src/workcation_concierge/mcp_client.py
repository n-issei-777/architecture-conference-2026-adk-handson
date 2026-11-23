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

"""MCP client helper creating an ADK McpToolset over stdio or StreamableHTTP."""

from __future__ import annotations

import os
import sys

from google.adk.tools.mcp_tool import (
    McpToolset,
    StdioConnectionParams,
    StreamableHTTPConnectionParams,
)
from mcp import StdioServerParameters


def create_travel_mcp_toolset(tool_filter: list[str] | None = None) -> McpToolset:
    """Create an McpToolset using StreamableHTTP (if MCP_SERVER_URL is set) or stdio."""
    mcp_url = os.getenv("MCP_SERVER_URL", "").strip()
    if mcp_url:
        # 発展構成: Cloud Run 等へ分離展開したリモート MCP サーバーへ StreamableHTTP 接続
        return McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=mcp_url,
                timeout=15.0,
            ),
            tool_filter=tool_filter,
        )

    # 既定構成: ローカル MCP サーバープロセスを stdio (JSON-RPC) で起動してツール取得
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=sys.executable,
                args=["-m", "workcation_concierge.mcp_server"],
            ),
            timeout=15.0,
        ),
        tool_filter=tool_filter,
    )
