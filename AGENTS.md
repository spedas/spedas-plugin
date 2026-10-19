# spedas-plugin

Start here. PySPEDAS tplot for coding agents: one MCP server (`server/`) and one skill
(`skill/spedas-tplot/`), packaged per agent system into `plugins/` by `packaging/build.py`.
Parent index: `~/work/projects/spedas/AGENTS.md`. User-facing overview: `README.md`.

Repository: https://github.com/spedas/spedas-plugin (public). Started 2026-10-19 as a restart of
the earlier SPEDAS agent work (`spedas/spedas_agent_kit`, `spedas_claude`, `spedas_codex`,
`spedas-agent-gui`: a broad CDAWeb/PDS/SPICE data layer, archived on 2026-10-19). This project is
deliberately narrower: PySPEDAS tplot only, state kept in the server process.

| Path | What it is |
|---|---|
| `server/` | Python package `spedas-tplot-mcp` (FastMCP, `mcp<2`, Python 3.12 pinned by `.python-version`). `runtime.py` = pyspedas import, output capture, variable summaries; `catalog.py` = loader introspection + the call_function whitelist; `script.py` = session replay script; `server.py` = the tools, all run through `invoke()` (lock + capture + event); `events.py` = activity log; `panels.py` = variables as Plotly panels; `web.py` + `static/index.html` = the web workbench (stdlib HTTP on 127.0.0.1:8765, same process) |
| `server/tests/` | `test_server.py`, `test_web.py` offline (pytest); `smoke_live.py` live OMNI download |
| `skill/spedas-tplot/` | `SKILL.md` + `reference/{missions,operations,options}.md` (missions.md calls were run against PySPEDAS 2.2.1 on 2026-10-19) |
| `packaging/build.py` | builds `plugins/{claude-code,codex,generic}` and both marketplace files; `--check` for staleness |
| `packaging/smoke_stdio.py` | starts each built plugin's server from its `.mcp.json` over stdio |
| `plugins/` | generated, committed so the repo installs straight from git. Never edit by hand |

## Rules

- Edit `server/` or `skill/`, then run `python3 packaging/build.py`. Commit the rebuilt `plugins/`.
- stdout belongs to JSON-RPC on stdio: every pyspedas call goes through `runtime.capture()`, and the
  web server never logs to stdout.
- MCP tools and web requests run on different threads: all pyspedas state access holds `runtime.LOCK`.
- The workbench must never expose `run_python` (`web.WEB_TOOLS_EXCLUDED`).
- `call_function` only runs names in `catalog.OPERATIONS`, which takes tplot variable names, not arrays.
  Anything else goes through `run_python`, which is off unless `SPEDAS_TPLOT_ALLOW_EXEC=1`.
- Before claiming a loader call or variable name in the skill, run it (see `reference/missions.md`).
- netcdf4 is capped below 1.7.5 on macOS (`[tool.uv]` in `server/pyproject.toml`): 1.7.5 ships only
  macOS 15 wheels, and this Mac runs macOS 14.

## Verified (2026-10-19)

- 6 offline tests pass; live OMNI smoke passes; both plugins start over stdio from their `.mcp.json`
  (`packaging/smoke_stdio.py`).
- `claude plugin validate` passes for the plugin and the marketplace; a headless `claude -p
  --plugin-dir plugins/claude-code/spedas-tplot` session loaded OMNI and plotted it.
- Codex: marketplace add + plugin add work in an isolated `CODEX_HOME`; `codex mcp list` shows the
  server and `codex debug prompt-input` shows the skill as `spedas-tplot:spedas-tplot`. Not yet
  verified: a real Codex turn calling the tools. The Codex `.mcp.json` uses `"cwd": "."` plus
  a relative `--project ./server`, copied from OpenAI's own stdio plugins, so it does not rely on
  `${PLUGIN_ROOT}` expansion in args.
