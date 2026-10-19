# Trying spedas-plugin

Thanks for trying it. You ask your coding agent (Claude Code or Codex) for space-physics data
and plots in plain words; it drives PySPEDAS tplot through this plugin, and you can watch and
explore the same session in your browser. Ten minutes is enough for a first look.

## Before you start

- [uv](https://docs.astral.sh/uv/getting-started/installation/) on your `PATH`
  (`curl -LsSf https://astral.sh/uv/install.sh | sh`). It installs PySPEDAS for the plugin;
  you do not need to set up Python yourself.
- Claude Code or Codex, logged in.
- macOS or Linux. Windows has not been tested.

## Install

**Claude Code**, inside a session:

```
/plugin marketplace add spedas/spedas-plugin
/plugin install spedas-tplot@spedas-plugin
```

Then restart Claude Code (or run `/reload-plugins`). The first start installs PySPEDAS and takes
about 45 seconds; `/mcp` shows `spedas-tplot` as connected when it is ready. To stop being asked
before every tool call, allow the whole server once: `/permissions`, then add the allow rule
`mcp__plugin_spedas-tplot_spedas-tplot`.

**Codex**, in a terminal:

```
codex plugin marketplace add spedas/spedas-plugin
codex plugin add spedas-tplot@spedas-plugin
```

Then start `codex` as usual. The first start can take up to a minute while PySPEDAS installs.

## Things to ask

These all worked from a fresh install:

- "Plot OMNI IMF Bz, solar wind speed and SYM-H for the 17 March 2015 storm."
- "Load THEMIS-A FGM for 2015-10-16 08:00-09:00 and plot B in GSM."
- "Show the MMS1 ion energy spectrogram and ion density for 2015-10-16 13:00-13:10."

Then push it with your own events and follow-ups: "zoom to 13:04-13:06", "transform that to
GSE", "average to 1 minute", "add the electron spectrogram", "export it as CSV", "give me the
script". Each answer comes with the plot path and a short physical reading.

## The workbench

While the agent is connected, the same tplot session is open at http://127.0.0.1:8765/ (ask the
agent for `status` if that port was taken). Everything the agent loads and plots shows up there
live. Drag on a panel or on the overview strip to zoom (the data are refetched at full detail),
tick variables to add panels, and load data or run functions from the drawer. Your changes are
part of the same session, so the agent sees them too.

## Where things go

- Downloaded data: `~/spedas_data` (or your PySPEDAS preferences), reused across sessions.
- Plots, exports and the replay script: `./spedas_tplot_output` in your project (Claude Code) or
  `~/spedas_tplot_output` (Codex). Ask the agent to "save plots to <folder>" to change it.
- "Give me the script" returns plain PySPEDAS code that reruns the whole session without the
  agent.

## Tell us

Open an issue at https://github.com/spedas/spedas-plugin/issues with:

- which agent and version (`claude --version` or `codex --version`),
- what you asked, and what happened (paste the agent's reply, the plot if it looks wrong),
- the output of asking the agent for `status`.

Especially useful: a mission or instrument the agent could not load, a plot that looks wrong,
and anything you expected it to do that it did not try.

## Known limits

- It covers PySPEDAS tplot: mission loaders, tplot variables, the common analysis functions
  (interpolation, averaging, coordinate transforms, spectra, minimum variance, field models) and
  plotting. Arbitrary Python is off by default (`SPEDAS_TPLOT_ALLOW_EXEC=1` turns on `run_python`).
- Data that needs a login (some MMS or Cluster products) stops with a message; the agent will not
  enter credentials.
- Each agent session has its own tplot session; two sessions get two workbenches (8765, 8766, ...).
