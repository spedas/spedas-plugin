# set_options keys

`set_options(variables, {key: value, ...})` calls `pyspedas.options(names, opt_dict=...)`. Keys are
case-insensitive. Aliases listed after a slash do the same thing.

## Axes and titles

| Key | Value | Effect |
|---|---|---|
| `ytitle`, `ysubtitle` | str | panel y label and the smaller line under it (units) |
| `ztitle`, `zsubtitle` | str | colorbar label (spectrograms) |
| `xtitle`, `xsubtitle` | str | x label (bottom panel) |
| `yrange` / `y_range` | [lo, hi] | fixed y range |
| `zrange` / `z_range` | [lo, hi] | fixed color range |
| `ylog`, `zlog` | bool | log axis / log color scale |
| `y_major_ticks` | list | explicit y tick positions |
| `y_minor_tick_interval` | float | minor tick spacing |
| `ytitle_color`, `ztitle_color` | color | label colors |
| `right_axis` | bool | draw this variable against a right-hand axis (in a pseudovariable) |

## Lines

| Key | Value | Effect |
|---|---|---|
| `color` / `colors` | str or list | one color per component, e.g. `["b", "g", "r"]` |
| `linestyle` / `line_style` | str or list | `solid`, `dashed`, `dotted`, `dashdot` |
| `thick` / `line_width` | float | line width |
| `marker`, `marker_size`, `symbols` | | scatter-style markers |
| `alpha` | 0–1 | transparency |
| `data_gap` / `datagap` | seconds | break lines across gaps longer than this |

## Legend

`legend_names` (list of labels, one per component), `legend_location`, `legend_size`,
`legend_ncols`, `legend_frameon`, `legend_title`.

## Spectrograms

| Key | Value | Effect |
|---|---|---|
| `spec` | bool | draw as a spectrogram instead of lines |
| `Colormap` | str | matplotlib colormap name (`spedas`, `jet`, `viridis`, ...) |
| `zlog`, `zrange`, `ztitle` | | color scale |
| `ylog`, `yrange` | | bin axis |
| `y_interp`, `y_interp_points` | bool, int | smooth the bin axis |
| `spec_dim_to_plot` | int | which dimension to use for multi-dim spectra |

## Panel layout

| Key | Value | Effect |
|---|---|---|
| `panel_size` | float | relative panel height (default 1) |
| `char_size` / `charsize` | float | font size in this panel |
| `border`, `grid` | bool | frame and grid lines |
| `annotations` | dict | text annotations (see `describe_function("options")`) |

## Global options (not per variable)

`call_function("tplot_options", [option, value])`: `title`, `title_size`, `axis_font_size`,
`charsize`, `xmargin`, `ymargin`, `xsize`, `ysize` (inches), `data_gap`, `background`,
`foreground`, `grid`, `style` (matplotlib style name), `var_label`.
`call_function("timebar", [time_or_list], {"color": "red", "dash": true})` draws vertical
event markers; `call_function("highlight", [var, [t0, t1]])` shades an interval.

The full list, with every alias, is in `describe_function("options", max_doc=20000)`.
