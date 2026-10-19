# spedas-plugin

PySPEDAS **tplot** for coding agents: an MCP server plus a skill, packaged per agent system.

```
skill/spedas-tplot/      the skill (SKILL.md + reference/): how to drive tplot well
server/                  the MCP server (spedas-tplot-mcp): tplot in one long-lived process
packaging/build.py       builds plugins/ from the two sources above
plugins/claude-code/     Claude Code plugin  (generated, committed)
plugins/codex/           Codex plugin        (generated, committed)
plugins/generic/         any MCP client: config snippets + the skill folder (generated)
.claude-plugin/marketplace.json, .agents/plugins/marketplace.json   marketplaces (generated)
```

The server and the skill are separate on purpose. The server is the capability: tools that load
data and keep tplot variables in memory between calls. The skill carries the know-how: the
analysis loop, tplot conventions, verified loader calls, the operation catalog and the plot
options. Each agent package bundles both in the layout that agent expects.

Trying it for the first time? Start with [TRIAL.md](TRIAL.md): install, three prompts to try,
and how to report what you find.

## Install

| Agent | Steps |
|---|---|
| Claude Code | `/plugin marketplace add spedas/spedas-plugin` then `/plugin install spedas-tplot@spedas-plugin`. For one session only: `claude --plugin-dir plugins/claude-code/spedas-tplot` |
| Codex | `codex plugin marketplace add spedas/spedas-plugin` then `codex plugin add spedas-tplot@spedas-plugin` |
| (either, from a checkout) | use the checkout path instead of `spedas/spedas-plugin` |
| Anything else | `plugins/generic/README.md`: an MCP config snippet plus the skill folder to copy |

Needs [`uv`](https://docs.astral.sh/uv/). The first start installs PySPEDAS into the plugin's
`server/.venv` (about 35 s); later starts take about 2 s.

## Web workbench

The server also serves a page on the same tplot session, at http://127.0.0.1:8765/ by default
(`status` gives the actual URL). It shows the variables in memory, stacks them as interactive
Plotly panels with one shared time axis (zoom refetches the window at full detail), streams what
the agent does, and has forms to load data, run catalogued functions, read metadata, copy the
session script and save a tplot PNG. With "Follow the agent" on, each agent `plot` call is
redrawn there. It binds to 127.0.0.1 only, refuses other Host/Origin headers, and never exposes
`run_python`. Without an agent: `uv run --project server spedas-tplot-web`.

## Tools

| Tool | What it does |
|---|---|
| `status` | versions, data/output directories, number of variables |
| `set_output_dir` | send plots, exports and the script to a directory in the user's project |
| `list_loaders`, `describe_function` | find a mission loader and read its keywords (introspected: ~290 loaders, ~40 missions) |
| `load_data` | `pyspedas.projects.<mission>.<instrument>(trange, **options)` into tplot variables |
| `list_variables`, `describe_variable`, `get_values` | inspect: shape, span, cadence, gaps, units, coords, CDF attributes, stats, decimated values |
| `create_variable` | store small JSON arrays as a tplot variable |
| `list_operations`, `call_function` | run a curated catalog of tplot functions (tinterpol, avg_data, cotrans, join_vec, tdpwrspc, fac/minvar/LMN, Tsyganenko models, ...) |
| `set_options` | per-variable plot options |
| `plot` | stacked tplot panels to PNG/PDF/SVG; the PNG is returned so the agent can check it |
| `export_variables`, `restore_file` | .pytplot / .csv / .nc out; .pytplot / .cdf / .nc in |
| `get_script` | every state-changing call so far, as a replayable PySPEDAS script |
| `run_python` | only when `SPEDAS_TPLOT_ALLOW_EXEC=1`: run code in the server process |

Settings: `SPEDAS_DATA_DIR` (downloads; default `~/spedas_data` unless a PySPEDAS preferences
file sets one), `SPEDAS_TPLOT_OUTPUT_DIR` (default `./spedas_tplot_output`, or
`~/spedas_tplot_output` when the server starts outside a workspace, as it does under Codex),
`SPEDAS_TPLOT_ALLOW_EXEC`, `SPEDAS_TPLOT_WEB` (`0` turns the workbench off),
`SPEDAS_TPLOT_WEB_PORT` (default 8765).

## Develop

```bash
cd server && uv sync && uv run pytest -q          # offline tests (in-memory MCP client)
uv run python tests/smoke_live.py                 # live: downloads one day of OMNI
cd .. && python3 packaging/build.py               # regenerate plugins/ after any change
python3 packaging/build.py --check                # fails if plugins/ is stale
uv run --project server python packaging/smoke_stdio.py   # start each plugin as its .mcp.json says
claude plugin validate plugins/claude-code/spedas-tplot && claude plugin validate .
```

Never edit `plugins/` by hand: change `server/` or `skill/`, then rebuild.
