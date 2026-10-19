"""Records every state-changing tool call as plain PySPEDAS Python, so a session can be replayed
without the MCP server."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .runtime import output_dir

HEADER = '''"""tplot session recorded by spedas-tplot-mcp ({started}).

Replays the state-changing tool calls of one MCP session in plain PySPEDAS.
"""
import pyspedas
'''


class Script:
    def __init__(self):
        self.started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.lines: list[str] = []

    @property
    def path(self) -> Path:
        """Follows the output directory, so set_output_dir moves the script too."""
        stamp = self.started.replace(":", "").replace("-", "")
        return output_dir() / f"session_{stamp}.py"

    def text(self) -> str:
        return HEADER.format(started=self.started) + "\n" + "\n".join(self.lines) + ("\n" if self.lines else "")

    def add(self, line: str) -> None:
        self.lines.append(line)
        self.path.write_text(self.text())


def call_src(func: str, args: list | tuple = (), kwargs: dict | None = None) -> str:
    parts = [repr(a) for a in args] + [f"{k}={v!r}" for k, v in (kwargs or {}).items()]
    return f"{func}({', '.join(parts)})"


script = Script()
