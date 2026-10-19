"""spedas-tplot MCP server: PySPEDAS tplot as tools, state kept in one long-lived process."""

from __future__ import annotations

import ast
import functools
import importlib.metadata
import inspect
import json
import os
import re
from datetime import datetime
from typing import Any

import numpy as np
from mcp.server.fastmcp import FastMCP, Image
from mcp.server.fastmcp.exceptions import ToolError

from . import catalog, events, panels, runtime
from .runtime import capture, jsonable, pyspedas, summarize
from .script import call_src, script

INSTRUCTIONS = """\
PySPEDAS tplot in a persistent session. tplot variables loaded or computed by one call stay in
memory for the next. Typical loop: list_loaders -> describe_function (read the loader's options)
-> load_data -> list_variables / describe_variable -> call_function (tinterpol, cotrans, join_vec,
avg_data, ...) -> set_options -> plot. Plots, exports and a replayable session script are written
to the output directory reported by status. Times are 'YYYY-MM-DD/hh:mm:ss' strings or Unix
seconds. Keep loads to the interval you need. status also gives the URL of a web workbench on the
same session: the user can watch your work there, zoom the data and plot it themselves.
"""

mcp = FastMCP("spedas-tplot", instructions=INSTRUCTIONS)

EXEC_ENABLED = os.environ.get("SPEDAS_TPLOT_ALLOW_EXEC", "").lower() in ("1", "true", "yes")
RESULT_LIMIT = 20000


def _attach_log(result: Any, log: str) -> Any:
    if not log:
        return result
    if isinstance(result, dict):
        result["log"] = log
    elif isinstance(result, list) and result and isinstance(result[0], dict):
        result[0]["log"] = log
    return result


# The undecorated tool functions, for the web workbench to call through invoke().
TOOLS: dict[str, Any] = {}


def _event_summary(name: str, result: Any) -> tuple[str, dict]:
    """A one-line description and the bits of a tool result the web feed uses."""
    head = result[0] if isinstance(result, list) and result and isinstance(result[0], dict) else result
    if not isinstance(head, dict):
        return "", {}
    keep = {k: head[k] for k in ("path", "panels", "created", "replaced", "deleted", "names", "output_dir") if k in head}
    if name == "load_data":
        keep["names"] = head.get("names", [])
        return f"{head.get('loaded', 0)} variables", keep
    if name == "plot":
        return ", ".join(head.get("panels", [])), keep
    changed = head.get("created", []) + head.get("replaced", [])
    return (", ".join(changed[:6]) + (" ..." if len(changed) > 6 else "")) if changed else "", keep


def invoke(name: str, kwargs: dict[str, Any], source: str) -> tuple[Any, str]:
    """Run one tool under the session lock with pyspedas output captured; log it as an event.

    Returns (result, captured output). Errors are raised as ToolError carrying that output."""
    fn = TOOLS[name]
    with runtime.LOCK, capture() as cap:
        try:
            result = fn(**kwargs)
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
            if cap.text:
                msg += f"\n--- pyspedas output ---\n{cap.text}"
            events.record(source, name, kwargs, False, f"{type(e).__name__}: {e}")
            raise ToolError(msg) from e
    summary, keep = _event_summary(name, result)
    if not (source == "web" and name in events.READ_ONLY_TOOLS):  # the page's own lookups are noise
        events.record(source, name, kwargs, True, summary, keep)
    return result, cap.text


def tool(fn):
    """Register fn as an MCP tool (and in TOOLS for the web workbench)."""
    TOOLS[fn.__name__] = fn

    @functools.wraps(fn)
    def wrapper(**kwargs):
        result, log = invoke(fn.__name__, kwargs, "agent")
        result = _attach_log(result, log)
        if isinstance(result, list):
            return [json.dumps(r, indent=1) if isinstance(r, dict) else r for r in result]
        return result

    return mcp.tool()(wrapper)


def _as_list(v: str | list[str]) -> list[str]:
    """Names as a list. Accepts a list, a space-separated string, or a JSON-encoded string/list
    (agents sometimes send '"name"' or '["a", "b"]')."""
    if isinstance(v, str):
        s = v.strip()
        if s[:1] in ('"', "["):
            try:
                v = json.loads(s)
            except ValueError:
                v = s.strip('"')
        if isinstance(v, str):
            return v.split()
    return list(v)


def _snapshot() -> dict[str, int]:
    return {k: id(v) for k, v in runtime.data_quants().items()}


def _diff(before: dict[str, int]) -> dict[str, list[str]]:
    after = _snapshot()
    out = {
        "created": [k for k in after if k not in before],
        "replaced": [k for k in after if k in before and after[k] != before[k]],
        "deleted": [k for k in before if k not in after],
    }
    return {k: v for k, v in out.items() if v}


def _short(names_: list[str], limit: int = 40) -> list[dict]:
    return [summarize(n) for n in names_[:limit]]


def _describe_return(r: Any) -> Any:
    if r is None or isinstance(r, (bool, int, float, str)):
        return jsonable(r)
    if isinstance(r, np.ndarray) and r.size > 200:
        return {"type": "ndarray", "shape": list(r.shape), "dtype": str(r.dtype),
                "note": "large array not shown; store it as a tplot variable or use run_python"}
    if hasattr(r, "_fields"):  # namedtuple, e.g. get_data
        return {f: _describe_return(getattr(r, f)) for f in r._fields}
    out = jsonable(r)
    if len(json.dumps(out)) > RESULT_LIMIT:
        return {"type": type(r).__name__, "note": "return value too large to show", "repr": repr(r)[:500]}
    return out


@tool
def status() -> dict:
    """Session status: pyspedas and server versions, data and output directories, how many tplot
    variables are in memory, and whether run_python is enabled."""
    ps = pyspedas()
    return {
        "pyspedas": importlib.metadata.version("pyspedas"),
        "server": importlib.metadata.version("spedas-tplot-mcp"),
        "data_dir": os.environ.get("SPEDAS_DATA_DIR") or "(set by your pyspedas preferences file)",
        "output_dir": str(runtime.output_dir()),
        "session_script": str(script.path),
        "n_variables": len(ps.tnames()),
        "run_python_enabled": EXEC_ENABLED,
        "workbench_url": runtime.WEB_URL or "(off; set SPEDAS_TPLOT_WEB=1)",
    }


@tool
def set_output_dir(path: str) -> dict:
    """Send plots, exports and the session script to this absolute directory from now on.
    Call it first when status shows an output_dir outside the user's workspace (for example
    ~/spedas_tplot_output) and the user wants files in their project."""
    d = runtime.set_output_dir(path)
    if script.lines:
        script.path.write_text(script.text())
    return {"output_dir": str(d), "session_script": str(script.path)}


@tool
def list_loaders(mission: str | None = None) -> dict:
    """List PySPEDAS mission loaders. Without a mission: every mission and its loader names.
    With a mission (e.g. 'themis', 'mms', 'psp', 'wind', 'omni'): its loaders with one-line
    descriptions. Next step: describe_function('<mission>.<loader>') for the options."""
    m = catalog.missions()
    if mission is None:
        return {"missions": m}
    mod_loaders = {n: catalog.first_line(catalog.loader(mission, n).__doc__) for n in m.get(mission, [])}
    if not mod_loaders:
        raise ValueError(f"unknown mission {mission!r}; known: {', '.join(m)}")
    return {"mission": mission, "loaders": mod_loaders}


@tool
def describe_function(name: str, max_doc: int = 6000) -> dict:
    """Signature and docstring of a PySPEDAS function. Use '<mission>.<loader>' for loaders
    (e.g. 'mms.fgm', 'psp.fields') or a bare name for tplot functions (e.g. 'tinterpol', 'cotrans',
    'options'). Read this before passing keyword arguments you are unsure about."""
    full, f = catalog.resolve(name)
    return {"name": full, **catalog.describe(f, max_doc)}


@tool
def load_data(mission: str, instrument: str, trange: list[str], options: dict[str, Any] | None = None) -> dict:
    """Load mission data into tplot variables by calling pyspedas.projects.<mission>.<instrument>.

    trange: ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss'].
    options: the loader's keyword arguments, e.g. {"probe": "a", "level": "l2", "datatype": "fgs"}
    for themis.fgm, or {"probe": "1", "data_rate": "srvy"} for mms.fgm. time_clip defaults to True
    when the loader supports it. Returns the variables created, with shape, time span and units."""
    f = catalog.loader(mission, instrument)
    kw = dict(options or {})
    params = inspect.signature(f).parameters
    if "time_clip" in params and "time_clip" not in kw:
        kw["time_clip"] = True
    for bad in ("notplot", "downloadonly"):
        if kw.get(bad):
            raise ValueError(f"{bad}=True does not create tplot variables; this tool is for loading into tplot")
    before = _snapshot()
    ret = f(trange=list(trange), **kw)
    diff = _diff(before)
    loaded = diff.get("created", []) + diff.get("replaced", [])
    if not loaded and isinstance(ret, (list, tuple)):
        loaded = [n for n in ret if isinstance(n, str) and n in runtime.data_quants()]
    script.add(call_src(f"pyspedas.projects.{mission}.{instrument}", kwargs={"trange": list(trange), **kw}))
    result: dict[str, Any] = {"loaded": len(loaded), "names": loaded}
    if len(loaded) <= 12:
        result["variables"] = _short(loaded)
    else:
        result["note"] = "describe_variable or list_variables('<pattern>') for shapes, spans and units"
    if not loaded:
        result["note"] = "no variables were created; check the log, the time range and the loader options"
    return result


@tool
def list_variables(pattern: str = "*") -> dict:
    """List tplot variables in memory (wildcards allowed, e.g. 'tha_*', 'mms1_fgm_b_gse*'), each
    with type, shape, time span, units and coordinate system."""
    ns = runtime.names(pattern)
    return {"count": len(ns), "variables": _short(ns, 200)}


@tool
def describe_variable(name: str) -> dict:
    """Everything about one tplot variable: shape, time span, cadence and largest gap, units,
    coordinate system, plot settings, CDF attributes (CATDESC, FILLVAL, ...) and per-component
    min/max/mean/NaN fraction."""
    return summarize(name, detail=True)


@tool
def get_values(name: str, trange: list[str] | None = None, max_points: int = 100) -> dict:
    """Read a variable's values, decimated to at most max_points times (stride sampling), with
    ISO times. Restrict with trange to look closely at an event. For full-resolution arrays use
    export_variables and read the file."""
    return runtime.values(name, trange, max_points)


@tool
def create_variable(name: str, times: list[Any], values: list[Any], v: list[Any] | None = None,
                    units: str | None = None, coord_sys: str | None = None) -> dict:
    """Create a tplot variable from small JSON arrays (store_data). times: ISO strings or Unix
    seconds; values: list (scalar series) or list of lists (one row per time); v: optional
    y-bins for a spectrogram."""
    ps = pyspedas()
    t = [ps.time_double(x) if isinstance(x, str) else float(x) for x in times]
    data: dict[str, Any] = {"x": t, "y": np.asarray(values, dtype=float)}
    if v is not None:
        data["v"] = np.asarray(v, dtype=float)
    ps.store_data(name, data=data)
    if units:
        ps.set_units(name, units)
    if coord_sys:
        ps.set_coords(name, coord_sys)
    script.add(f"# create_variable({name!r}): {len(t)} points supplied inline; not replayed")
    return summarize(name, detail=True)


@tool
def list_operations(category: str | None = None) -> dict:
    """The tplot functions call_function can run, by category (variables, time, arithmetic,
    cleaning, derivatives, spectral, coordinates, field_models, plot_settings), each with a
    one-line description. Use describe_function for the full signature."""
    ops = catalog.operations()
    if category:
        if category not in ops:
            raise ValueError(f"unknown category {category!r}; categories: {', '.join(ops)}")
        ops = {category: ops[category]}
    ps = pyspedas()
    return {cat: {n: catalog.first_line(getattr(ps, n).__doc__) for n in fns} for cat, fns in ops.items()}


@tool
def call_function(function: str, args: list[Any] | None = None, kwargs: dict[str, Any] | None = None) -> dict:
    """Run a catalogued tplot function (see list_operations) on variables in memory, e.g.
    function='tinterpol', args=['mms1_fgm_b_gse_srvy_l2', 'mms1_dis_bulkv_gse_fast'];
    function='cotrans', kwargs={'name_in': 'tha_fgs_gse', 'name_out': 'tha_fgs_gsm',
    'coord_in': 'gse', 'coord_out': 'gsm'}; function='avg_data', args=['wi_b'], kwargs={'res': 60}.
    Returns the function's return value and which variables were created, replaced or deleted."""
    f = catalog.operation(function)
    args, kwargs = list(args or []), dict(kwargs or {})
    before = _snapshot()
    ret = f(*args, **kwargs)
    diff = _diff(before)
    if function not in catalog.READ_ONLY:
        script.add(call_src(f"pyspedas.{function}", args, kwargs))
    out: dict[str, Any] = {"function": function, "returned": _describe_return(ret), **diff}
    if diff.get("created") or diff.get("replaced"):
        out["variables"] = _short(diff.get("created", []) + diff.get("replaced", []))
    return out


@tool
def set_options(variables: str | list[str], options: dict[str, Any]) -> dict:
    """Set tplot plot options on one or more variables (pyspedas.options with opt_dict).
    Common keys: ytitle, ysubtitle, ztitle, yrange [lo, hi], zrange, ylog (bool), zlog, spec
    (bool), legend_names [..], color / colors, linestyle, thick, panel_size, Colormap,
    char_size, ytitle_color, y_major_ticks. Global options (title, axis_font_size, ...) go through
    call_function('tplot_options', [option, value])."""
    names_ = _as_list(variables)
    ps = pyspedas()
    for n in names_:
        if not ps.tnames(n):
            raise KeyError(f"no tplot variable matches {n!r}")
    ps.options(names_, opt_dict=options)
    panels.note_explicit(ps.tnames(names_), options)
    script.add(call_src("pyspedas.options", [names_], {"opt_dict": options}))
    return {"updated": ps.tnames(names_), "plot": {n: summarize(n, detail=True).get("plot", {}) for n in ps.tnames(names_)[:20]}}


_FORMATS = {".png": "png", ".pdf": "pdf", ".svg": "svg", ".jpeg": "jpeg", ".jpg": "jpeg", ".eps": "eps"}


def _slug(names_: list[str]) -> str:
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", "_".join(names_))[:60]
    return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{s}"


@tool
def plot(variables: str | list[str], trange: list[str] | None = None, path: str | None = None,
         title: str | None = None, var_label: str | list[str] | None = None,
         xsize: float | None = None, ysize: float | None = None, dpi: int = 100,
         return_image: bool = True) -> list:
    """Plot tplot variables as stacked panels (pyspedas.tplot) and save the figure.

    variables: names or wildcards, one panel each (a pseudovariable overplots its components).
    trange: optional zoom. path: output file (.png default; .pdf/.svg/.jpeg/.eps also work);
    relative paths go under the output directory. var_label: variables shown as extra x-axis tick
    labels (e.g. position). With return_image the PNG is returned so you can look at it: check
    every panel has data, sensible ranges and readable labels before showing the user."""
    ps = pyspedas()
    names_ = ps.tnames(_as_list(variables))
    if not names_:
        raise KeyError(f"no tplot variables match {variables!r}")
    out = runtime.resolve_path(path, f"plots/{_slug(names_)}.png")
    fmt = _FORMATS.get(out.suffix.lower())
    if fmt is None:
        raise ValueError(f"unsupported plot format {out.suffix!r}; use one of {', '.join(_FORMATS)}")
    kw: dict[str, Any] = {"display": False, f"save_{fmt}": str(out), "dpi": dpi}
    if trange:
        kw["trange"] = list(trange)
    if var_label:
        kw["var_label"] = _as_list(var_label)
    if xsize:
        kw["xsize"] = xsize
    if ysize:
        kw["ysize"] = ysize

    import matplotlib.pyplot as plt

    old_title = ps.tplot_tools.tplot_opt_glob.get("title_text", "")
    if title is not None:
        ps.tplot_options("title", title)
    try:
        ps.tplot(names_, **kw)
    finally:
        if title is not None:
            ps.tplot_options("title", old_title)
        plt.close("all")
    replay = {k: v for k, v in kw.items() if k != "dpi" or v != 100}
    if title is not None:
        script.add(call_src("pyspedas.tplot_options", ["title", title]))
    script.add(call_src("pyspedas.tplot", [names_], replay))
    meta = {"path": str(out), "panels": names_}
    if return_image and fmt in ("png", "jpeg"):
        return [meta, Image(path=str(out))]
    return [meta]


SAVE_EXTS = (".pytplot", ".pyspedas", ".tplot")


@tool
def export_variables(variables: str | list[str], path: str) -> dict:
    """Save variables to a file. Format by extension: .pytplot (tplot_save; restores every tplot
    detail), .csv (one file per variable via tplot_ascii, spectrogram bins in *_v.csv), .nc
    (netCDF via xarray). Relative paths go under the output directory."""
    ps = pyspedas()
    names_ = ps.tnames(_as_list(variables))
    if not names_:
        raise KeyError(f"no tplot variables match {variables!r}")
    out = runtime.resolve_path(path, path)
    ext = out.suffix.lower()
    written: list[str] = []
    if ext in SAVE_EXTS:
        ps.tplot_save(names_, filename=str(out))
        written = [str(out)]
    elif ext == ".csv":
        for n in names_:
            base = out.with_suffix("") if len(names_) == 1 else out.with_name(f"{out.stem}_{n}")
            ps.tplot_ascii(n, filename=str(base))
            written += [str(p) for p in sorted(base.parent.glob(base.name + "*.csv"))]
    elif ext == ".nc":
        import xarray as xr

        ds = xr.Dataset({n: _plain(runtime.data_quants()[n]) for n in names_ if not runtime.is_pseudo(n)})
        ds.to_netcdf(out)
        written = [str(out)]
    else:
        raise ValueError("path must end in .pytplot (or .pyspedas), .csv or .nc")
    script.add(f"# export_variables({names_!r}) -> {[str(w) for w in written]!r}")
    return {"written": written, "variables": names_}


def _plain(da):
    """A copy of a tplot DataArray with netCDF-safe attributes and unique dimension names."""
    da = da.copy()
    keep = {}
    for k, v in (da.attrs.get("CDF", {}) or {}).get("VATT", {}).items():
        if isinstance(v, (str, int, float)):
            keep[k] = v
    da.attrs = keep
    rename = {d: f"{da.name}_{d}" for d in da.dims if d != "time"}
    da = da.rename({k: v for k, v in rename.items()})
    for c in list(da.coords):
        if c not in da.dims and c != "time":
            da = da.drop_vars(c)
    return da


@tool
def restore_file(path: str, options: dict[str, Any] | None = None) -> dict:
    """Load tplot variables from a file: .pytplot (tplot_restore), .cdf (cdf_to_tplot; options
    such as {"varformat": "*b_gse*", "get_support_data": true}) or .nc (netcdf_to_tplot)."""
    ps = pyspedas()
    p = runtime.resolve_path(path, path)
    if not p.exists():
        raise FileNotFoundError(str(p))
    before = _snapshot()
    ext = p.suffix.lower()
    if ext in SAVE_EXTS:
        ps.tplot_restore(str(p))
        script.add(call_src("pyspedas.tplot_restore", [str(p)]))
    elif ext == ".cdf":
        ps.cdf_to_tplot(str(p), **(options or {}))
        script.add(call_src("pyspedas.cdf_to_tplot", [str(p)], options or {}))
    elif ext == ".nc":
        ps.netcdf_to_tplot(str(p), **(options or {}))
        script.add(call_src("pyspedas.netcdf_to_tplot", [str(p)], options or {}))
    else:
        raise ValueError("path must end in .pytplot (or .pyspedas), .cdf or .nc")
    diff = _diff(before)
    return {**diff, "variables": _short(diff.get("created", []) + diff.get("replaced", []))}


@tool
def get_script() -> dict:
    """The replayable Python script of this session so far (every load, call, option change and
    plot), and the file it is saved to. Give it to the user so the analysis can be rerun without
    the MCP server."""
    return {"path": str(script.path), "script": script.text()}


_namespace: dict[str, Any] = {}


def _exec(code: str) -> Any:
    if not _namespace:
        import matplotlib.pyplot as plt

        _namespace.update({"pyspedas": pyspedas(), "np": np, "plt": plt})
    tree = ast.parse(code)
    last = None
    if tree.body and isinstance(tree.body[-1], ast.Expr):
        last = ast.Expression(tree.body.pop().value)
    exec(compile(tree, "<run_python>", "exec"), _namespace)
    return eval(compile(last, "<run_python>", "eval"), _namespace) if last else None


if EXEC_ENABLED:

    @tool
    def run_python(code: str) -> dict:
        """Run Python in the server process, with pyspedas, np and plt imported and every tplot
        variable in memory (pyspedas.get_data / store_data). Variables you define persist between
        calls. Printed output and the value of a final expression are returned. Use it for
        analysis the catalogued tools do not cover; prefer the dedicated tools when they fit."""
        before = _snapshot()
        value = _exec(code)
        script.add("# run_python\n" + code.rstrip())
        return {"value": _describe_return(value), **_diff(before)}


def main() -> None:
    from . import web

    web.start()
    mcp.run()


if __name__ == "__main__":
    main()
