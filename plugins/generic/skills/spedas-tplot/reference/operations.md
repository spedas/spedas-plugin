# call_function catalog

`call_function(function, args=[...], kwargs={...})` runs `pyspedas.<function>(*args, **kwargs)`
on variables in memory. It returns the function's return value and the variables created,
replaced or deleted. `list_operations()` shows what the installed PySPEDAS provides. Read
`describe_function(name)` before using an unfamiliar keyword.

## Variables

| Function | Example |
|---|---|
| `tplot_rename(old, new)` | `args=["B_RTN", "solo_b_rtn"]` |
| `tplot_copy(old, new)` | `args=["tha_fgs_gse", "b_backup"]` |
| `del_data(pattern)` | `args=["mms1_dis_*err*"]` |
| `store_data(name, data=[...])` | pseudovariable: `args=["b_both"], kwargs={"data": ["BGSE", "BGSEc"]}` |
| `set_coords(name, coords)` / `set_units(name, units)` | `args=["BGSEc", "gse"]` |
| `split_vec(name)` | creates `name_x`, `name_y`, `name_z` |
| `join_vec(names, newname=...)` | `args=[["BX_GSE", "BY_GSE", "BZ_GSE"]], kwargs={"newname": "omni_b_gse"}` |
| `tres(name)` | cadence in seconds (read only) |

## Time

| Function | Example |
|---|---|
| `time_clip(names, t0, t1, newname=...)` | cut to an interval |
| `tinterpol(names, interp_to, newname=..., method=...)` | `args=["BGSE", "proton_density"]` puts the first variable on the second's timestamps (`-itrp` suffix by default) |
| `avg_data(names, res=seconds, newname=...)` | `args=["BGSE"], kwargs={"res": 60}` (`-avg` suffix) |
| `degap(name, dt=..., margin=...)` | insert NaN so lines break across gaps |
| `timespan(t0, duration, keyword=...)` | set the default plot range |

## Arithmetic

`add`, `subtract`, `multiply`, `divide` (two variables, interpolating if needed, `newname=`),
`add_across` (sum over components or bins), `tdotp`, `tcrossp`, `tnormalize`,
`tvectot(names, newname=...)` (magnitude; default output `<name>_tot` holds the 3 components plus |v|
as a 4th column, `join_component=False` gives |v| alone),
`spec_mult`, `tkm2re` (km to Earth radii).

## Cleaning

| Function | Use |
|---|---|
| `clip(name, ymin, ymax, newname=...)` | values outside become NaN |
| `deflag(name, flag=..., method="linear"/"repeat"/"remove_nan")` | replace a flag value |
| `clean_spikes(names, nsmooth=10, thresh=0.3)` | despike |
| `interp_nan(name, max_gap_time=...)` | fill short NaN runs |
| `subtract_average`, `subtract_median` | detrend (`-d` / `-m` suffix) |
| `tsmooth(names, width=points, median=...)` | running mean/median |

## Derivatives and spectra

`deriv_data(names, newname=...)` (d/dt), `pwr_spec(name, nbp=256, nsp=128)` and
`tdpwrspc(name, nboxpoints=..., nshiftpoints=...)` (dynamic power spectra, giving a spectrogram
variable), `wavelet(names, wavename="morl")` (`_pow` suffix), `twavpol(name)` (wave polarization).

## Coordinates

| Function | Example |
|---|---|
| `cotrans(name_in=, name_out=, coord_in=, coord_out=)` | gse, gseq, gsm, sm, gei, geo, mag, j2000, hee, hae, heeq. `kwargs={"name_in": "tha_fgs_gse", "name_out": "tha_fgs_gsm", "coord_in": "gse", "coord_out": "gsm"}` |
| `fac_matrix_make(mag_var_name, other_dim=..., pos_var_name=..., newname=...)` then `tvector_rotate(mat, vec, newname=...)` | field-aligned coordinates |
| `minvar_matrix_make(in_var_name, tstart=, tstop=, twindow=...)` then `tvector_rotate` | minimum variance |
| `lmn_matrix_make(pos_var_name, mag_var_name, ...)` then `tvector_rotate` | boundary-normal LMN (uses OMNI solar wind) |

`cotrans` needs the input's coordinate system set (see `set_coords`). RTN and HCI are not in
`cotrans`; use the RTN products the missions provide.

## Field models (geopack)

`tt89(pos_var, iopt=..., kp=...)`, `tt96`, `tt01`, `tts04(pos_var, parmod=...)`, `tigrf(pos_var)`,
`get_tsy_params(dst_tvar, imf_tvar, Np_tvar, Vp_tvar, model)` (builds the parmod input),
`calculate_lshell(pos_tvar, newname)`. Position must be in km or Re with its coordinate system set.

## Plot settings

`options` (same as set_options), `tplot_options(option, value)` (global), `xlim`/`ylim`/`zlim`,
`timebar(t, color=, dash=)`, `databar(var, value)`, `highlight(variables, range=[t0, t1])`,
`annotate`.
