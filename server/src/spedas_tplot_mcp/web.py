"""The web workbench: a local HTTP server on the same tplot session as the MCP tools.

The agent works through MCP, the user through the browser; both go through server.invoke(), so
they see the same variables and one activity log. Binds to 127.0.0.1 only.
"""

from __future__ import annotations

import json
import mimetypes
import os
import sys
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from mcp.server.fastmcp.exceptions import ToolError

from . import events, panels, runtime
from .runtime import capture, jsonable, summarize

STATIC = Path(__file__).parent / "static"
DEFAULT_PORT = 8765
WEB_TOOLS_EXCLUDED = {"run_python"}  # never reachable from a browser


def _files_url(path: str) -> str | None:
    try:
        rel = Path(path).resolve().relative_to(runtime.output_dir().resolve())
    except ValueError:
        return None
    return "/files/" + rel.as_posix()


class Handler(BaseHTTPRequestHandler):
    server_version = "spedas-tplot-workbench"

    def log_message(self, *args):  # stdout/stderr stay quiet; stdout carries MCP JSON-RPC
        pass

    # ---- helpers -------------------------------------------------------------------------
    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, status: int = 200) -> None:
        self._send(status, json.dumps(jsonable(data)).encode(), "application/json")

    def _error(self, msg: str, status: int = 400) -> None:
        self._json({"error": msg}, status)

    # ---- GET -----------------------------------------------------------------------------
    def do_GET(self):
        if not self._host_ok():
            return self._error("bad host", 403)
        url = urlparse(self.path)
        q = {k: v[-1] for k, v in parse_qs(url.query).items()}
        try:
            if url.path in ("/", "/index.html"):
                return self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            if url.path == "/api/state":
                return self._json(self._state())
            if url.path == "/api/events":
                evs, seq, ver = events.since(int(q.get("since", 0)))
                return self._json({"events": evs, "seq": seq, "version": ver})
            if url.path == "/api/panels":
                names = [n for n in q.get("names", "").split(",") if n]
                trange = [q["t0"], q["t1"]] if q.get("t0") and q.get("t1") else None
                with runtime.LOCK, capture():
                    out = [panels.panel(n, trange, int(q.get("max_points", 4000))) for n in names]
                    full = panels.full_range(names)
                return self._json({"panels": out, "full_range": full})
            if url.path == "/api/variable":
                with runtime.LOCK, capture():
                    return self._json(summarize(q["name"], detail=True))
            if url.path.startswith("/files/"):
                return self._file(unquote(url.path[len("/files/"):]))
            return self._error("not found", 404)
        except KeyError as e:
            return self._error(f"missing or unknown: {e}", 404)
        except Exception as e:  # report, never crash the server thread
            return self._error(f"{type(e).__name__}: {e}", 500)

    def _state(self) -> dict:
        from .server import TOOLS

        with runtime.LOCK, capture():
            ps = runtime.pyspedas()
            names = ps.tnames()
            variables = [summarize(n) for n in names]
        _, seq, ver = events.since(10**12)
        return {
            "version": ver, "seq": seq, "variables": variables,
            "output_dir": str(runtime.output_dir()), "data_dir": os.environ.get("SPEDAS_DATA_DIR", ""),
            "tools": sorted(set(TOOLS) - WEB_TOOLS_EXCLUDED),
        }

    def _file(self, rel: str) -> None:
        root = runtime.output_dir().resolve()
        p = (root / rel).resolve()
        if root not in p.parents or not p.is_file():
            return self._error("not found", 404)
        ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        self._send(200, p.read_bytes(), ctype)

    # ---- POST /api/tool/<name> -------------------------------------------------------------
    def do_POST(self):
        if not self._host_ok():
            return self._error("bad host", 403)
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).hostname not in ("127.0.0.1", "localhost"):
            return self._error("cross-origin request refused", 403)
        if "application/json" not in (self.headers.get("Content-Type") or ""):
            return self._error("send JSON", 415)
        url = urlparse(self.path)
        if not url.path.startswith("/api/tool/"):
            return self._error("not found", 404)
        name = url.path[len("/api/tool/"):]
        from .server import TOOLS, invoke

        if name not in TOOLS or name in WEB_TOOLS_EXCLUDED:
            return self._error(f"no tool {name!r}", 404)
        try:
            length = int(self.headers.get("Content-Length") or 0)
            kwargs = json.loads(self.rfile.read(length) or b"{}")
            result, log = invoke(name, kwargs, "web")
        except ToolError as e:
            return self._error(str(e), 400)
        except Exception as e:
            return self._error(f"{type(e).__name__}: {e}", 400)
        if isinstance(result, list):  # plot: [meta, Image]
            result = dict(result[0])
            result["url"] = _files_url(result.get("path", ""))
        return self._json({"result": result, "log": log})


def start(port: int | None = None, tries: int = 20) -> str | None:
    """Serve the workbench on 127.0.0.1 in a daemon thread; return its URL (None if disabled)."""
    if os.environ.get("SPEDAS_TPLOT_WEB", "1").lower() in ("0", "false", "no", "off"):
        return None
    base = port or int(os.environ.get("SPEDAS_TPLOT_WEB_PORT") or DEFAULT_PORT)
    for p in range(base, base + tries):
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", p), Handler)
            break
        except OSError:
            continue
    else:
        print(f"spedas-tplot: no free port in {base}-{base + tries - 1}; workbench off", file=sys.stderr)
        return None
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, name="workbench", daemon=True).start()
    runtime.WEB_URL = f"http://127.0.0.1:{httpd.server_address[1]}/"
    print(f"spedas-tplot workbench: {runtime.WEB_URL}", file=sys.stderr)
    return runtime.WEB_URL


def main() -> None:
    """spedas-tplot-web: the workbench alone, without an agent."""
    import argparse

    from . import server  # noqa: F401  (registers the tools)

    ap = argparse.ArgumentParser(description="SPEDAS tplot workbench (no agent)")
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    os.environ["SPEDAS_TPLOT_WEB"] = "1"
    url = start(a.port)
    if not url:
        raise SystemExit("could not start the workbench")
    print(f"SPEDAS tplot workbench at {url} (Ctrl-C to stop)")
    if not a.no_browser:
        webbrowser.open(url)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
