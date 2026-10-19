#!/usr/bin/env python3
"""Start a built plugin's MCP server exactly as its .mcp.json says, over real stdio, and check it.

    uv run --project server python packaging/smoke_stdio.py plugins/claude-code/spedas-tplot
    uv run --project server python packaging/smoke_stdio.py plugins/codex/spedas-tplot

Checks: the handshake, the tool list, status, and an offline create/plot round trip.
No network is needed once the plugin's server/.venv exists.
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED = {"status", "set_output_dir", "list_loaders", "describe_function", "load_data", "list_variables", "describe_variable",
            "get_values", "create_variable", "list_operations", "call_function", "set_options", "plot",
            "export_variables", "restore_file", "get_script"}


async def smoke(root: Path) -> None:
    cfg = json.loads((root / ".mcp.json").read_text())["mcpServers"]
    (name, server), = cfg.items()
    sub = lambda s: s.replace("${CLAUDE_PLUGIN_ROOT}", str(root)).replace("${PLUGIN_ROOT}", str(root))
    out = tempfile.mkdtemp(prefix="spedas_tplot_smoke_")
    cwd = (root / server["cwd"]).resolve() if "cwd" in server else None
    params = StdioServerParameters(command=server["command"], args=[sub(a) for a in server["args"]],
                                   env={**os.environ, "SPEDAS_TPLOT_OUTPUT_DIR": out}, cwd=cwd)
    async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
        init = await s.initialize()
        tools = {t.name for t in (await s.list_tools()).tools}
        missing = EXPECTED - tools
        assert not missing, f"missing tools: {missing}"
        st = await s.call_tool("status", {})
        assert not st.isError, st.content
        t0 = 1444953600.0
        made = await s.call_tool("create_variable", {"name": "x", "times": [t0 + i for i in range(50)],
                                                     "values": [float(i % 7) for i in range(50)]})
        assert not made.isError, made.content
        pl = await s.call_tool("plot", {"variables": "x"})
        assert not pl.isError and any(c.type == "image" for c in pl.content), pl.content
        print(f"OK {root}: server {init.serverInfo.name!r}, {len(tools)} tools, plot written under {out}")


if __name__ == "__main__":
    for arg in sys.argv[1:] or ["plugins/claude-code/spedas-tplot", "plugins/codex/spedas-tplot"]:
        asyncio.run(smoke(Path(arg).resolve()))
