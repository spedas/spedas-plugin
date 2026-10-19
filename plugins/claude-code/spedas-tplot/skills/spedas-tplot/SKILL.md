---
name: spedas-tplot
description: Load, inspect, transform and plot space-physics mission data with PySPEDAS tplot through the spedas-tplot MCP server. Use when the user wants heliophysics or magnetospheric time series (THEMIS, MMS, Wind, ACE, OMNI, PSP, Solar Orbiter, Van Allen Probes, GOES, Kyoto Dst/AE, and ~40 other missions), tplot variables, stacked tplot panels or spectrograms, coordinate transforms (GSE/GSM/SM/RTN, field-aligned, minimum variance), averaging, interpolation, or a reproducible PySPEDAS script.
---

# PySPEDAS tplot through the spedas-tplot MCP server

The `spedas-tplot` MCP server runs PySPEDAS in one long-lived process. **tplot variables persist
between tool calls**: a variable loaded in one call can be transformed in the next and plotted in
the one after. Think of it as an IDL/PySPEDAS command line you drive through tools.

If the tools are missing, the server is not connected: say so and point to the plugin's README
rather than writing PySPEDAS code the user has to run by hand (unless that is what they asked for).

## The loop

1. **Pin down the request**: mission, instrument, probe/spacecraft, time range, coordinate system,
   cadence, and what the final figure or number should show. Ask only if the mission or the time
   range is truly unknown. Otherwise choose sensible defaults and state them.
2. **Find the loader**: `list_loaders(mission)`, then `describe_function("<mission>.<loader>")`
   to read its keywords (`probe`, `level`, `datatype`, `data_rate`, `varformat`, ...). Do not guess
   `datatype` strings: they come from the docstring. See `reference/missions.md` for verified
   starting points.
3. **Load narrowly**: `load_data(mission, instrument, trange, options)`. Keep the interval to what
   the question needs (hours for burst/survey data, days for 1-min OMNI or Dst). `time_clip` is on
   by default. Use `varformat` to load only the variables you need from large products (MMS, PSP).
4. **Inspect before analysis**: `list_variables("<prefix>*")`, then `describe_variable(name)` for
   units, coordinate system, cadence, gaps, fill values and NaN fraction. Use
   `get_values(name, trange, max_points)` to read numbers. Never paste whole arrays into chat.
5. **Transform** with `call_function` (catalog: `list_operations`). See `reference/operations.md`.
   Name outputs explicitly (`newname`, `name_out`, `suffix`) so the session stays readable.
6. **Style** with `set_options` (ytitle, yrange, ylog, spec, zlog, legend_names, colors, ...;
   see `reference/options.md`).
7. **Plot** with `plot(variables, trange=..., title=...)`. Look at the returned image yourself
   before showing it: empty panels, all-NaN data, a fill-value spike (e.g. -1e31) or an unreadable
   axis mean something went wrong upstream. Fix it, then re-plot.
8. **Hand over**: give the plot path, a few-sentence physical reading of what it shows, caveats
   (gaps, quality flags, coordinate assumptions), and `get_script()` so the user can rerun the
   whole session in plain PySPEDAS. Use `export_variables` for data files (.csv, .nc, .pytplot).

## tplot conventions that matter

- **Time ranges** are `['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss']` (date-only works) in UTC.
- **Variable names** follow each mission's prefix: `tha_fgs_gse`, `mms1_fgm_b_gse_srvy_l2`,
  `psp_fld_l2_mag_RTN_4_Sa_per_Cyc`, `BZ_GSM` (OMNI). Wildcards work almost everywhere (`tha_*`).
- **Shapes**: `[n_times]` scalar, `[n_times, 3]` vector, `[n_times, n_bins]` spectrogram (with a
  `v` coordinate for the bins). Some vectors carry a 4th column (|B|); split or drop it as needed.
- **Coordinate metadata**: `cotrans` reads the variable's coordinate system. If
  `describe_variable` shows none, set it first: `call_function("set_coords", [name, "gse"])`.
- **Pseudovariables** overplot several variables in one panel:
  `call_function("store_data", ["combo"], {"data": ["var1", "var2"]})`.
- **Spectrograms** need `set_options(name, {"spec": true, "zlog": true, "ylog": true})` if the
  loader did not set them. Pick `zrange` from `describe_variable` stats, not by guessing.
- **Interpolation before arithmetic**: two variables at different cadences must share timestamps
  before `add`/`subtract`/`tdotp`/`tcrossp`. Use `tinterpol(source, target)` first.
- **Fill values**: CDF `FILLVAL` (often -1e31) is usually converted to NaN on load. If a panel
  shows huge spikes, `clip` or `deflag` them and say so.
- **Global plot options** (title, font size, background) go through
  `call_function("tplot_options", [option, value])`. The `plot` tool's `title` sets it for one plot.

## When the catalog is not enough

`run_python` exists only when the server was started with `SPEDAS_TPLOT_ALLOW_EXEC=1`. It runs
code in the same process (`pyspedas`, `np`, `plt` are imported, and all tplot variables are
reachable via `pyspedas.get_data` / `store_data`). Use it for custom math, then `store_data` the
result so the dedicated tools can plot it. If it is not enabled, tell the user what you would run
and that they can enable it, or give them the code to run against the exported `.pytplot` file.

## The web workbench

`status()` reports `workbench_url` (usually http://127.0.0.1:8765/): a browser view of this same
session. Tell the user about it the first time you plot in a conversation. Everything you load
and plot appears there live (with "Follow the agent" on, your `plot` calls are redrawn as
interactive, zoomable panels), and the user can load data, run functions and stack panels there.
Their actions change the shared session too: call `list_variables` before assuming you know what
is in memory, and treat variables you did not create as the user's.

## Data and files

- Downloads go to `SPEDAS_DATA_DIR` (default `~/spedas_data`, unless a PySPEDAS preferences file
  says otherwise). Files already there are reused, not downloaded again.
- Plots, exports and the session script go to the output directory reported by `status()`
  (default `./spedas_tplot_output`; `~/spedas_tplot_output` when the server was started outside
  a workspace, as Codex and desktop clients do). If that is not where the user works, call
  `set_output_dir("<absolute path in their project>/spedas_tplot_output")` before plotting.
  Relative paths given to `plot`/`export_variables` land in the output directory.
- MMS and some ERG/Cluster data need no login for public products. If a loader asks for
  credentials, stop and tell the user. Never enter credentials yourself.

## References

- `reference/missions.md`: verified loader calls and the variable names they produce.
- `reference/operations.md`: the call_function catalog with examples.
- `reference/options.md`: `set_options` keys.
