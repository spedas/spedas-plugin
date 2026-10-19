# Loader starting points (verified)

Each call below was run against PySPEDAS 2.2.1 on 2026-10-19. The variables listed are what
it created. Use `describe_function("<mission>.<loader>")` for the other keywords, and
`list_loaders()` for the ~40 missions not listed here.

`load_data(mission, instrument, trange, options)` maps to
`pyspedas.projects.<mission>.<instrument>(trange=trange, **options)`.

## Solar wind at L1 and indices

| Call | Main variables |
|---|---|
| `load_data("omni", "data", [t0, t1], {"datatype": "1min"})` (also `"5min"`, `"hourly"`) | `BX_GSE`, `BY_GSM`, `BZ_GSM`, `F` (|B|), `flow_speed`, `Vx`, `Vy`, `Vz`, `proton_density`, `T`, `Pressure`, `E`, `Beta`, `Mach_num`, `SYM_H`, `AE_INDEX`, `AL_INDEX`, `AU_INDEX`, `PC_N_INDEX` |
| `load_data("wind", "mfi", [t0, t1], {"datatype": "h0"})` | `BGSE`, `BGSM`, `BF1` (|B|), `PGSE` (position), plus `B1*`/`B3*` (1-min and 3-s averages) |
| `load_data("ace", "mfi", [t0, t1])` | `BGSEc`, `BRTN`, `Magnitude` |
| `load_data("kyoto", "dst", [t0, t1])` | `kyoto_dst` |

OMNI uses 1-min data with gaps (NaN) where no upstream monitor covered the time.

## THEMIS (probes a–e)

| Call | Main variables |
|---|---|
| `load_data("themis", "fgm", [t0, t1], {"probe": "a", "level": "l2"})` | `tha_fgs_gse`, `tha_fgs_gsm`, `tha_fgs_dsl`, `tha_fgs_btotal` (spin-res); `tha_fgl_*` (low), `tha_fgh_*` (high), `tha_fge_*` |
| `load_data("themis", "state", [t0, t1], {"probe": "a"})` | `tha_pos`, `tha_vel` (GEI), `tha_pos_gse`, `tha_pos_gsm`, `tha_vel_gse`, `tha_vel_gsm` |

Other THEMIS loaders: `esa`, `mom`, `gmom`, `efi`, `fbk`, `fft`, `fit`, `sst`, `scm`, `gmag`, `ask`.

## MMS (probes 1–4)

| Call | Main variables |
|---|---|
| `load_data("mms", "fgm", [t0, t1], {"probe": "1", "data_rate": "srvy"})` | `mms1_fgm_b_gse_srvy_l2` (4 columns: Bx, By, Bz, |B|), `..._bvec` (3 columns), `..._btot`, same for `gsm`, `dmpa`, `bcs`; `mms1_fgm_flag_srvy_l2` |
| `load_data("mms", "fpi", [t0, t1], {"probe": "1", "data_rate": "fast", "datatype": "dis-moms"})` | `mms1_dis_numberdensity_fast`, `mms1_dis_bulkv_gse_fast`, `mms1_dis_energyspectr_omni_fast` (spectrogram), `mms1_dis_temppara_fast`, `mms1_dis_tempperp_fast`, `mms1_dis_prestensor_*` |

`datatype` for FPI: `dis-moms`, `des-moms`, `dis-dist`, `des-dist`. `data_rate`: `fast`, `brst`.
Burst intervals are short; check them with `load_data("mms", "burst_intervals", ...)` before
loading `brst`. MMS FGM survey data is large: keep the range to hours.

## Parker Solar Probe

| Call | Main variables |
|---|---|
| `load_data("psp", "fields", [t0, t1], {"datatype": "mag_rtn_4_sa_per_cyc", "level": "l2"})` | `psp_fld_l2_mag_RTN_4_Sa_per_Cyc`, `psp_fld_l2_quality_flags` |
| `load_data("psp", "spi", [t0, t1], {"datatype": "spi_sf00_l3_mom", "level": "l3"})` | `psp_spi_DENS`, `psp_spi_VEL_RTN_SUN`, `psp_spi_TEMP`, `psp_spi_EFLUX_VS_ENERGY`, `psp_spi_SUN_DIST`, `psp_spi_QUALITY_FLAG`, `psp_spi_MAGF_SC` |

Full-resolution `mag_rtn` is large (hundreds of MB per day). Prefer `mag_rtn_4_sa_per_cyc` or
`mag_rtn_1min` unless the question needs high frequencies.

## Solar Orbiter

| Call | Main variables |
|---|---|
| `load_data("solo", "mag", [t0, t1], {"datatype": "rtn-normal"})` | `B_RTN` |

Other `solo` loaders: `swa`, `epd`, `rpw`. SolO variable names have no mission prefix, so a later
load can overwrite an earlier one: rename with `tplot_rename` if you load several intervals.

## Finding variable names for anything else

1. `describe_function("<mission>.<loader>")`: read `datatype`, `level`, `varformat`.
2. Load a short interval (an hour), then `list_variables("*")` and `describe_variable` on the
   likely candidates (CATDESC tells you what each one is).
3. Reload the full interval with `varformat` restricted to what you need.
