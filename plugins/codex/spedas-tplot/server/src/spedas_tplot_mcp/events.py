"""Activity log shared by the MCP tools and the web workbench.

Every tool call, from the agent or from the browser, is recorded here. The web page polls it to
show what happened and to notice when the set of tplot variables may have changed.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any

# Tools that only read; anything else may change variables, so it bumps the state version.
READ_ONLY_TOOLS = {"status", "list_loaders", "describe_function", "list_variables", "describe_variable",
                   "get_values", "list_operations", "get_script"}

_lock = threading.Lock()
_events: deque[dict] = deque(maxlen=500)
_seq = 0
_version = 0


def _brief(args: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for k, v in args.items():
        r = repr(v)
        out[k] = v if len(r) <= 200 else r[:200] + "..."
    return out


def record(source: str, tool: str, args: dict[str, Any], ok: bool, summary: str = "",
           result: dict | None = None) -> None:
    global _seq, _version
    with _lock:
        _seq += 1
        if tool not in READ_ONLY_TOOLS:
            _version += 1
        _events.append({"seq": _seq, "time": time.time(), "source": source, "tool": tool,
                        "args": _brief(args), "ok": ok, "summary": summary[:500], "result": result or {}})


def since(seq: int) -> tuple[list[dict], int, int]:
    with _lock:
        return [e for e in _events if e["seq"] > seq], _seq, _version


def version() -> int:
    with _lock:
        return _version
