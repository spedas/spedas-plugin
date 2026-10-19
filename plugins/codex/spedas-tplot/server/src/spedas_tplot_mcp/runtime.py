"""The in-process PySPEDAS session: import, output capture, and JSON views of tplot variables.

tplot variables live in ``pyspedas.tplot_tools.data_quants`` for the life of the server process,
so every tool call sees what earlier calls loaded or computed.
"""

from __future__ import annotations

import contextlib
import io
import logging
import math
import os
import threading
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # never open windows; plots are written to files

import numpy as np  # noqa: E402

_import_lock = threading.Lock()
_pyspedas = None

# One lock around all pyspedas state: MCP tool calls and web requests run on different threads.
LOCK = threading.RLock()
WEB_URL: str | None = None

LOG_LIMIT = 4000


DEFAULT_DATA_DIR = Path.home() / "spedas_data"


def _default_data_dir() -> None:
    """Without SPEDAS_DATA_DIR or a pyspedas preferences file, pyspedas downloads into
    ./<mission>_data under the current directory. Put downloads in one shared place instead."""
    if os.environ.get("SPEDAS_DATA_DIR") or os.environ.get("PYSPEDAS_CONFIG_FILE"):
        return
    from platformdirs import user_config_path

    if (user_config_path("pyspedas") / "preferences.toml").exists():
        return
    os.environ["SPEDAS_DATA_DIR"] = str(DEFAULT_DATA_DIR)


def pyspedas():
    """Import pyspedas once (lazily, so the MCP handshake is not delayed) and return the module."""
    global _pyspedas
    with _import_lock:
        if _pyspedas is None:
            _default_data_dir()
            with contextlib.redirect_stdout(io.StringIO()):
                import pyspedas as _ps
                from pyspedas.config import CONFIG

                CONFIG["plotting"]["global_display"] = False
            _pyspedas = _ps
    return _pyspedas


def data_quants() -> dict:
    return pyspedas().tplot_tools.data_quants


_output_override: Path | None = None


def _default_output_dir() -> Path:
    """./spedas_tplot_output, unless the server was started somewhere that is not a workspace:
    a plugin root (Codex starts plugin servers there), the filesystem root (some desktop
    clients), or a read-only directory. Then ~/spedas_tplot_output."""
    cwd = Path.cwd()
    in_plugin = (cwd / ".codex-plugin").exists() or (cwd / ".claude-plugin").exists()
    if in_plugin or cwd == Path(cwd.anchor) or not os.access(cwd, os.W_OK):
        return Path.home() / "spedas_tplot_output"
    return cwd / "spedas_tplot_output"


def set_output_dir(path: str) -> Path:
    global _output_override
    p = Path(path).expanduser()
    if not p.is_absolute():
        raise ValueError("output directory must be an absolute path")
    p.mkdir(parents=True, exist_ok=True)
    _output_override = p
    return p


def output_dir() -> Path:
    """Where plots, exports and the session script go (created on first use)."""
    env = os.environ.get("SPEDAS_TPLOT_OUTPUT_DIR")
    d = _output_override or (Path(env).expanduser() if env else _default_output_dir())
    d.mkdir(parents=True, exist_ok=True)
    return d


def resolve_path(path: str | None, default_name: str) -> Path:
    """Relative paths are taken relative to the output directory."""
    p = Path(path).expanduser() if path else Path(default_name)
    if not p.is_absolute():
        p = output_dir() / p
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


class Captured:
    def __init__(self):
        self.buf = io.StringIO()

    @property
    def text(self) -> str:
        s = self.buf.getvalue().strip()
        if len(s) > LOG_LIMIT:
            s = "...[earlier output trimmed]...\n" + s[-LOG_LIMIT:]
        return s


@contextlib.contextmanager
def capture():
    """Collect stdout and log records while pyspedas runs.

    stdout must never reach the real stream: on the stdio transport it carries JSON-RPC.
    """
    cap = Captured()
    handler = logging.StreamHandler(cap.buf)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    handler.setLevel(logging.INFO)
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        with contextlib.redirect_stdout(cap.buf):
            yield cap
    finally:
        root.removeHandler(handler)


def jsonable(x: Any, depth: int = 0) -> Any:
    """Convert numpy / xarray-ish values into plain JSON; NaN and inf become None."""
    if depth > 6:
        return repr(x)
    if x is None or isinstance(x, (bool, str, int)):
        return x
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, np.generic):
        return jsonable(x.item(), depth)
    if isinstance(x, np.ndarray):
        if x.dtype.kind == "M":
            return np.datetime_as_string(x, unit="ms").tolist()
        if x.dtype.kind in "fc":
            return jsonable(x.tolist(), depth)
        return x.tolist()
    if isinstance(x, dict):
        return {str(k): jsonable(v, depth + 1) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [jsonable(v, depth + 1) for v in x]
    if isinstance(x, Path):
        return str(x)
    return repr(x)


def iso(t) -> str:
    return str(np.datetime_as_string(np.datetime64(t, "ms"), unit="ms"))


def names(pattern: str | list[str] = "*") -> list[str]:
    return list(pyspedas().tnames(pattern))


def is_pseudo(name: str) -> bool:
    return bool(pyspedas().is_pseudovariable(name))


def _plot_options(da) -> dict:
    return da.attrs.get("plot_options", {}) if hasattr(da, "attrs") else {}


def _extra_coords(da) -> dict:
    out = {}
    for c in da.coords:
        if c == "time":
            continue
        out[str(c)] = list(da.coords[c].shape)
    return out


def _stats(values: np.ndarray, max_components: int = 12) -> dict | list:
    v = np.asarray(values, dtype=float)
    if v.ndim == 1:
        v = v[:, None]
    flat = v.reshape(v.shape[0], -1)
    if flat.shape[1] > max_components:
        finite = flat[np.isfinite(flat)]
        return {
            "min": jsonable(finite.min()) if finite.size else None,
            "max": jsonable(finite.max()) if finite.size else None,
            "nan_fraction": round(1 - finite.size / flat.size, 4) if flat.size else None,
        }
    out = []
    for i in range(flat.shape[1]):
        col = flat[:, i]
        good = col[np.isfinite(col)]
        out.append({
            "min": jsonable(good.min()) if good.size else None,
            "max": jsonable(good.max()) if good.size else None,
            "mean": jsonable(good.mean()) if good.size else None,
            "nan_fraction": round(1 - good.size / col.size, 4) if col.size else None,
        })
    return out


def _plot_summary(name: str, da) -> dict:
    po = _plot_options(da)
    yopt, zopt, extras = po.get("yaxis_opt", {}), po.get("zaxis_opt", {}), po.get("extras", {})
    ztitle = zopt.get("axis_label")
    if ztitle in ("Z-Axis", name):  # pyspedas placeholders, not real labels
        ztitle = None
    p = jsonable({
        "ytitle": yopt.get("axis_label"),
        "ysubtitle": yopt.get("axis_subtitle"),
        "yrange": yopt.get("y_range"),
        "ylog": yopt.get("y_axis_type") == "log" or None,
        "ztitle": ztitle,
        "zrange": zopt.get("z_range"),
        "zlog": zopt.get("z_axis_type") == "log" or None,
        "legend_names": yopt.get("legend_names"),
        "colors": extras.get("line_color"),
        "spec": extras.get("spec"),
    })
    return {k: v for k, v in p.items() if v not in (None, False, "")}


def summarize(name: str, detail: bool = False) -> dict:
    """A compact (or, with detail, full) description of one tplot variable."""
    ps = pyspedas()
    dq = data_quants()
    if name not in dq:
        raise KeyError(f"no tplot variable named {name!r}")
    da = dq[name]
    s: dict[str, Any] = {"name": name}
    if is_pseudo(name):
        s["type"] = "pseudo"
        s["components"] = list(_plot_options(da).get("overplots_mpl", []))
        if detail:
            s["plot"] = _plot_summary(name, da)
        return s
    if not hasattr(da, "coords") or "time" not in getattr(da, "coords", {}):
        s["type"] = type(da).__name__
        return s

    t = da.coords["time"].values
    po = _plot_options(da)
    extras = po.get("extras", {})
    s["type"] = "spectrogram" if extras.get("spec") else ("vector" if da.ndim == 2 and da.shape[1] in (3, 4) else "timeseries")
    s["shape"] = list(da.shape)
    s["n_times"] = int(t.size)
    if t.size:
        s["start"], s["end"] = iso(t[0]), iso(t[-1])
    with contextlib.redirect_stdout(io.StringIO()):
        units = ps.get_units(name)
        coords = ps.get_coords(name)
    if units and units != "None":
        s["units"] = units
    if coords:
        s["coord_sys"] = coords
    extra = _extra_coords(da)
    if extra:
        s["extra_coords"] = extra
    if not detail:
        return s

    if t.size > 1:
        dt = np.diff(t).astype("timedelta64[ns]").astype(float) / 1e9
        s["cadence_s"] = {"median": jsonable(np.median(dt)), "max_gap": jsonable(dt.max())}
    s["plot"] = _plot_summary(name, da)
    cdf = da.attrs.get("CDF", {}) or {}
    va = cdf.get("VATT", {}) or {}
    keep = ("CATDESC", "FIELDNAM", "UNITS", "LABLAXIS", "VAR_TYPE", "DEPEND_0", "DEPEND_1", "FILLVAL",
            "VALIDMIN", "VALIDMAX", "COORDINATE_SYSTEM", "SI_conversion")
    if va:
        s["cdf_attrs"] = jsonable({k: va[k] for k in keep if k in va})
    if cdf.get("GATT"):
        g = cdf["GATT"]
        s["source"] = jsonable({k: g[k] for k in ("Project", "Source_name", "Descriptor", "Data_type", "Logical_source", "Data_version") if k in g})
    if da.dtype.kind in "fiu":
        s["stats"] = _stats(da.values)
    for c in da.coords:
        if c != "time" and da.coords[c].ndim == 1 and da.coords[c].size <= 64:
            s.setdefault("coord_values", {})[str(c)] = jsonable(da.coords[c].values)
    return s


def values(name: str, trange: list | None, max_points: int) -> dict:
    """Decimated sample of a variable's data for reading in chat."""
    dq = data_quants()
    if name not in dq:
        raise KeyError(f"no tplot variable named {name!r}")
    if is_pseudo(name):
        raise ValueError(f"{name} is a pseudovariable; ask for one of its components")
    da = dq[name]
    if trange:
        t0, t1 = (np.datetime64(round(pyspedas().time_double(x) * 1e9), "ns") for x in trange)
        da = da.sel(time=slice(t0, t1))
    n = int(da.sizes["time"])
    stride = max(1, math.ceil(n / max(1, max_points)))
    sub = da.isel(time=slice(None, None, stride))
    out: dict[str, Any] = {"name": name, "n_total": n, "stride": stride, "n_returned": int(sub.sizes["time"])}
    per_time = int(np.prod(sub.shape[1:])) if sub.ndim > 1 else 1
    if per_time > 64:
        out["note"] = f"{per_time} values per time step: returning stats only. Export the variable to a file for the full array."
        out["stats"] = _stats(da.values)
        out["times"] = jsonable(sub.coords["time"].values)
        return out
    out["times"] = jsonable(sub.coords["time"].values)
    out["values"] = jsonable(np.round(sub.values.astype(float), 6) if sub.dtype.kind == "f" else sub.values)
    for c in sub.coords:
        if c != "time" and sub.coords[c].ndim == 1:
            out.setdefault("coords", {})[str(c)] = jsonable(sub.coords[c].values)
    return out
