"""tplot variables as browser-ready panels: decimated lines or spectrogram grids plus the plot
options that matter for drawing them (labels, log axes, ranges, colors, legends)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from .runtime import data_quants, is_pseudo, iso, jsonable, pyspedas

# matplotlib single-letter colors used by tplot options
_MPL = {"b": "#1f4fd1", "g": "#16803c", "r": "#d0312d", "c": "#0e9aa7", "m": "#b0399b",
        "y": "#c9a400", "k": "#1d232a", "w": "#ffffff"}
_DEFAULT_COLORS = {1: ["k"], 2: ["b", "r"], 3: ["b", "g", "r"], 4: ["b", "g", "r", "k"]}
_COLORMAPS = {"spedas": "Jet", "jet": "Jet", "viridis": "Viridis", "plasma": "Plasma", "inferno": "Inferno",
              "magma": "Magma", "cividis": "Cividis", "turbo": "Turbo", "rainbow": "Rainbow", "gray": "Greys",
              "greys": "Greys", "bwr": "RdBu", "seismic": "RdBu", "coolwarm": "RdBu"}

# Option keys the user set explicitly (set_options / the web), per variable. Loader-supplied
# y_range is just the data range, and applying it would stop the browser from rescaling on zoom.
explicit: dict[str, set[str]] = {}


def note_explicit(names: list[str], options: dict) -> None:
    for n in names:
        explicit.setdefault(n, set()).update(k.lower() for k in options)


def _color(c: Any) -> str:
    if isinstance(c, str):
        return _MPL.get(c, c)
    if isinstance(c, (list, tuple)) and len(c) in (3, 4):
        vals = [int(round(float(x) * 255)) if float(x) <= 1 else int(x) for x in c[:3]]
        return "#%02x%02x%02x" % tuple(vals)
    return "#1d232a"


def _opts(name: str) -> dict:
    da = data_quants()[name]
    po = da.attrs.get("plot_options", {})
    y, z, ex = po.get("yaxis_opt", {}), po.get("zaxis_opt", {}), po.get("extras", {})
    mine = explicit.get(name, set())
    out = {
        "ytitle": y.get("axis_label") or name,
        "ysubtitle": y.get("axis_subtitle") or "",
        "ylog": y.get("y_axis_type") == "log",
        "legend": y.get("legend_names"),
        "colors": [_color(c) for c in ex["line_color"]] if ex.get("line_color") else None,
        "ztitle": z.get("axis_label") or "",
        "zlog": z.get("z_axis_type") == "log",
        "colormap": _COLORMAPS.get(str((ex.get("colormap") or ["spedas"])[0]).lower(), "Jet"),
        "panel_size": ex.get("panel_size", 1),
    }
    if {"yrange", "y_range"} & mine and y.get("y_range"):
        out["yrange"] = jsonable(y["y_range"])
    if z.get("z_range"):
        out["zrange"] = jsonable(z["z_range"])
    return out


def _window(da, trange):
    if not trange:
        return da
    t0, t1 = (np.datetime64(round(pyspedas().time_double(x) * 1e9), "ns") for x in trange)
    return da.sel(time=slice(t0, t1))


def _minmax(t: np.ndarray, y: np.ndarray, max_points: int) -> tuple[np.ndarray, np.ndarray]:
    """Keep each bucket's min and max so spikes survive decimation."""
    n = y.size
    if n <= max_points:
        return t, y
    b = math.ceil(n / (max_points // 2))
    m = (n // b) * b
    yy = y[:m].reshape(-1, b)
    tt = t[:m].reshape(-1, b)
    good = np.isfinite(yy)
    lo = np.where(good, yy, np.inf).argmin(axis=1)
    hi = np.where(good, yy, -np.inf).argmax(axis=1)
    rows = np.arange(yy.shape[0])
    first, second = np.minimum(lo, hi), np.maximum(lo, hi)
    allnan = ~good.any(axis=1)
    ys = np.stack([yy[rows, first], yy[rows, second]], axis=1)
    ys[allnan] = np.nan
    ts = np.stack([tt[rows, first], tt[rows, second]], axis=1)
    return ts.ravel(), ys.ravel()


def _line(name: str, da, opts: dict, max_points: int) -> dict:
    t = da.coords["time"].values
    vals = np.asarray(da.values, dtype=float)
    if vals.ndim == 1:
        vals = vals[:, None]
    vals = vals.reshape(vals.shape[0], -1)
    k = vals.shape[1]
    colors = opts["colors"] or [_color(c) for c in _DEFAULT_COLORS.get(k, [])]
    legend = opts["legend"]
    traces = []
    for i in range(min(k, 16)):
        ts, ys = _minmax(t, vals[:, i], max_points)
        traces.append({
            "name": (legend[i] if legend and i < len(legend) else (name if k == 1 else f"{name}[{i}]")),
            "x": jsonable(ts), "y": jsonable(ys),
            "color": colors[i % len(colors)] if colors else None,
        })
    return {"kind": "line", "traces": traces, "n_points": int(t.size), "show_legend": k > 1 or bool(legend)}


def _spec(name: str, da, opts: dict, max_cols: int = 1000) -> dict:
    vals = np.asarray(da.values, dtype=float)
    if vals.ndim != 2:
        raise ValueError(f"{name}: spectrogram with {vals.ndim} dimensions; reduce it to [time, bins] first")
    t = da.coords["time"].values
    v = None
    for c in ("v", "spec_bins", "v1"):
        if c in da.coords:
            v = np.asarray(da.coords[c].values, dtype=float)
            break
    if v is None:
        v = np.arange(vals.shape[1], dtype=float)
    if v.ndim == 2:
        v = np.nanmedian(v, axis=0)
    n = vals.shape[0]
    if n > max_cols:  # block-average in time
        b = math.ceil(n / max_cols)
        m = (n // b) * b
        with np.errstate(all="ignore"):
            vals = np.nanmean(vals[:m].reshape(-1, b, vals.shape[1]), axis=1)
        t = t[:m].reshape(-1, b)[:, b // 2]
    order = np.argsort(v)
    v, vals = v[order], vals[:, order]
    z = vals.T
    if opts["zlog"]:
        with np.errstate(all="ignore"):
            z = np.where(z > 0, np.log10(z), np.nan)
    zr = opts.get("zrange")
    if zr and opts["zlog"]:
        zr = [math.log10(x) if x and x > 0 else None for x in zr]
    if not zr or None in zr:
        finite = z[np.isfinite(z)]
        zr = [float(np.percentile(finite, 2)), float(np.percentile(finite, 99.5))] if finite.size else [0, 1]
    return {"kind": "spec", "x": jsonable(t), "y": jsonable(v), "z": jsonable(np.round(z, 4)),
            "zrange": jsonable(zr), "n_points": int(n)}


def panel(name: str, trange: list | None = None, max_points: int = 4000) -> dict:
    dq = data_quants()
    if name not in dq:
        raise KeyError(f"no tplot variable named {name!r}")
    if is_pseudo(name):
        comps = list(dq[name].attrs["plot_options"].get("overplots_mpl", []))
        parts = [panel(c, trange, max_points) for c in comps if c in dq]
        traces, spec = [], None
        for p in parts:
            if p["kind"] == "spec" and spec is None:
                spec = p
            elif p["kind"] == "line":
                traces += p["traces"]
        o = _opts(name)
        first = parts[0]["options"] if parts else {}
        if o["ytitle"] == name and first:
            o["ytitle"], o["ysubtitle"] = first["ytitle"], first["ysubtitle"]
        out = {"name": name, "options": o, "kind": "line", "traces": traces, "show_legend": True}
        if spec:
            out.update(kind="spec", x=spec["x"], y=spec["y"], z=spec["z"], zrange=spec["zrange"], overlay=traces)
        return out
    da = _window(dq[name], trange)
    if da.sizes.get("time", 0) == 0:
        return {"name": name, "options": _opts(name), "kind": "empty"}
    o = _opts(name)
    spec = bool(dq[name].attrs.get("plot_options", {}).get("extras", {}).get("spec"))
    body = _spec(name, da, o) if spec else _line(name, da, o, max_points)
    return {"name": name, "options": o, **body}


def full_range(names: list[str]) -> list[str] | None:
    t0, t1 = None, None
    for n in names:
        da = data_quants().get(n)
        if da is None or not hasattr(da, "coords") or "time" not in da.coords or da.sizes.get("time", 0) == 0:
            continue
        a, b = da.coords["time"].values[0], da.coords["time"].values[-1]
        t0 = a if t0 is None or a < t0 else t0
        t1 = b if t1 is None or b > t1 else t1
    return [iso(t0), iso(t1)] if t0 is not None else None
