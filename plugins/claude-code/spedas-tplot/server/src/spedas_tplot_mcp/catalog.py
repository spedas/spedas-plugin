"""What the server exposes: mission loaders (found by introspection) and a curated set of
tplot functions that ``call_function`` may run."""

from __future__ import annotations

import functools
import importlib
import inspect
import pkgutil
from typing import Any, Callable

from .runtime import pyspedas

# Functions call_function may run, by category. Names that the installed pyspedas lacks are skipped.
# Only functions that take tplot variable names belong here; array-in/array-out helpers do not.
OPERATIONS: dict[str, list[str]] = {
    "variables": [
        "tplot_rename", "tplot_copy", "del_data", "store_data", "set_units", "set_coords",
        "get_units", "get_coords", "data_exists", "tres", "get_timespan", "link", "split_vec", "join_vec",
    ],
    "time": [
        "time_clip", "crop", "tinterpol", "tinterpol_mxn", "tinterp", "avg_data", "avg_res_data", "degap", "makegap",
        "timespan", "tlimit", "time_string", "time_double",
    ],
    "arithmetic": [
        "add", "subtract", "multiply", "divide", "add_across", "tdotp", "tcrossp", "tnormalize",
        "tvectot", "spec_mult", "tkm2re",
    ],
    "cleaning": [
        "clip", "yclip", "deflag", "tdeflag", "clean_spikes", "interp_nan", "subtract_average",
        "subtract_median", "tsmooth",
    ],
    "derivatives": ["deriv_data", "derive"],
    "spectral": ["pwr_spec", "tpwrspc", "tdpwrspc", "wavelet", "twavpol"],
    "coordinates": [
        "cotrans", "tvector_rotate", "fac_matrix_make", "minvar_matrix_make", "lmn_matrix_make",
    ],
    "field_models": ["tt89", "tt96", "tt01", "tts04", "tigrf", "calculate_lshell", "get_tsy_params"],
    "plot_settings": ["options", "tplot_options", "xlim", "ylim", "zlim", "timebar", "databar", "highlight", "annotate"],
}

# Functions that only read, so the session script does not need to replay them.
READ_ONLY = {"get_units", "get_coords", "data_exists", "tres", "get_timespan", "time_string", "time_double"}


@functools.cache
def operations() -> dict[str, list[str]]:
    ps = pyspedas()
    return {cat: [n for n in fns if callable(getattr(ps, n, None))] for cat, fns in OPERATIONS.items()}


def operation(name: str) -> Callable:
    for fns in operations().values():
        if name in fns:
            return getattr(pyspedas(), name)
    raise ValueError(
        f"{name!r} is not in the operation catalog; call list_operations to see what is available"
        " (run_python, when enabled, can reach anything else)"
    )


@functools.cache
def missions() -> dict[str, list[str]]:
    """mission -> public loader functions (callables in pyspedas.projects.<mission> taking trange)."""
    ps = pyspedas()
    out = {}
    for info in sorted(pkgutil.iter_modules(ps.projects.__path__), key=lambda m: m.name):
        try:
            mod = importlib.import_module(f"pyspedas.projects.{info.name}")
        except Exception:
            continue
        fns = []
        for n in dir(mod):
            if n.startswith("_"):
                continue
            f = getattr(mod, n)
            if not callable(f) or inspect.isclass(f):
                continue
            try:
                if "trange" in inspect.signature(f).parameters:
                    fns.append(n)
            except (TypeError, ValueError):
                continue
        if fns:
            out[info.name] = fns
    return out


def loader(mission: str, instrument: str) -> Callable:
    m = missions()
    if mission not in m:
        raise ValueError(f"unknown mission {mission!r}; known: {', '.join(m)}")
    if instrument not in m[mission]:
        raise ValueError(f"{mission} has no loader {instrument!r}; it has: {', '.join(m[mission])}")
    return getattr(importlib.import_module(f"pyspedas.projects.{mission}"), instrument)


def resolve(name: str) -> tuple[str, Callable]:
    """'themis.fgm' -> mission loader; 'tinterpol' or 'pyspedas.tinterpol' -> top-level function."""
    name = name.removeprefix("pyspedas.").removeprefix("projects.")
    if "." in name:
        mission, fn = name.split(".", 1)
        return f"pyspedas.projects.{mission}.{fn}", loader(mission, fn)
    f = getattr(pyspedas(), name, None)
    if not callable(f):
        raise ValueError(f"pyspedas has no function {name!r}")
    return f"pyspedas.{name}", f


def first_line(doc: str | None) -> str:
    for line in (doc or "").strip().splitlines():
        line = line.strip()
        if line:
            return line[:160]
    return ""


def describe(f: Callable, max_doc: int) -> dict[str, Any]:
    try:
        sig = str(inspect.signature(f))
    except (TypeError, ValueError):
        sig = "(...)"
    doc = inspect.getdoc(f) or ""
    if len(doc) > max_doc:
        doc = doc[:max_doc] + "\n...[docstring trimmed; raise max_doc to see more]"
    return {"signature": sig, "doc": doc}
