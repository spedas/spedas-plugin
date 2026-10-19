"""Offline tests: every tool through an in-memory MCP client, on synthetic tplot variables."""

import asyncio
import json
import os

import numpy as np
import pytest

os.environ["SPEDAS_TPLOT_ALLOW_EXEC"] = "1"

from mcp.shared.memory import create_connected_server_and_client_session  # noqa: E402

from spedas_tplot_mcp import runtime  # noqa: E402
from spedas_tplot_mcp.server import mcp  # noqa: E402

T0 = 1444953600.0  # 2015-10-16/00:00


@pytest.fixture(autouse=True)
def _outdir(tmp_path, monkeypatch):
    monkeypatch.setenv("SPEDAS_TPLOT_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(runtime, "_output_override", None)


def run(steps):
    """Run (tool, args) steps in one session; return [(is_error, text_or_dict, n_images)]."""

    async def go():
        out = []
        async with create_connected_server_and_client_session(mcp._mcp_server) as c:
            for name, args in steps:
                r = await c.call_tool(name, args)
                texts = [i.text for i in r.content if i.type == "text"]
                images = [i for i in r.content if i.type == "image"]
                body = texts[0] if texts else None
                if not r.isError and body and body.startswith("{"):
                    body = json.loads(body)
                out.append((r.isError, body, len(images)))
        return out

    return asyncio.run(go())


def test_tool_list():
    async def go():
        async with create_connected_server_and_client_session(mcp._mcp_server) as c:
            return {t.name for t in (await c.list_tools()).tools}

    names = asyncio.run(go())
    assert {"status", "load_data", "list_variables", "describe_variable", "get_values", "call_function",
            "set_options", "plot", "export_variables", "restore_file", "get_script", "run_python"} <= names


def test_create_transform_plot_export(tmp_path):
    t = (T0 + np.arange(600) * 1.0).tolist()
    b = np.column_stack([np.sin(np.arange(600) / 50), np.cos(np.arange(600) / 50), np.ones(600)]).tolist()
    res = run([
        ("create_variable", {"name": "b", "times": t, "values": b, "units": "nT", "coord_sys": "gse"}),
        ("describe_variable", {"name": "b"}),
        ("get_values", {"name": "b", "max_points": 10}),
        ("call_function", {"function": "tvectot", "args": ["b"], "kwargs": {"newname": "bmag"}}),
        ("call_function", {"function": "avg_data", "args": ["b"], "kwargs": {"res": 60}}),
        ("set_options", {"variables": "b", "options": {"ytitle": "B", "legend_names": ["x", "y", "z"]}}),
        ("plot", {"variables": ["b", "bmag", "b-avg"], "title": "test"}),
        ("plot", {"variables": "b", "path": "figs/b.pdf"}),
        ("export_variables", {"variables": ["b", "bmag"], "path": "out/b.pytplot"}),
        ("export_variables", {"variables": "b", "path": "out/b.csv"}),
        ("export_variables", {"variables": ["b", "bmag"], "path": "out/b.nc"}),
        ("call_function", {"function": "del_data", "args": ["b*"]}),
        ("restore_file", {"path": "out/b.pytplot"}),
        ("get_script", {}),
    ])
    errors = [(i, r[1]) for i, r in enumerate(res) if r[0]]
    assert not errors, errors
    desc = res[1][1]
    assert desc["shape"] == [600, 3] and desc["units"] == "nT" and desc["coord_sys"] == "gse"
    assert desc["cadence_s"]["median"] == 1.0
    assert res[2][1]["n_returned"] == 10 and len(res[2][1]["values"][0]) == 3
    assert res[3][1]["created"] == ["bmag"]
    assert res[4][1]["created"] == ["b-avg"] and res[4][1]["variables"][0]["n_times"] == 10
    assert res[6][2] == 1  # PNG returned as an image
    assert (tmp_path / "figs/b.pdf").exists() and res[7][2] == 0
    assert set(res[12][1]["created"]) == {"b", "bmag"}
    script = res[13][1]["script"]
    assert "pyspedas.tvectot(['b'], newname='bmag')" in script or "pyspedas.tvectot('b', newname='bmag')" in script
    assert "pyspedas.tplot(" in script


def test_spectrogram_and_pseudo():
    t = (T0 + np.arange(100) * 4.0).tolist()
    res = run([
        ("create_variable", {"name": "spec", "times": t, "values": np.random.rand(100, 8).tolist(),
                             "v": np.logspace(1, 4, 8).tolist()}),
        ("set_options", {"variables": "spec", "options": {"spec": True, "zlog": True, "ylog": True}}),
        ("describe_variable", {"name": "spec"}),
        ("call_function", {"function": "store_data", "args": ["combo"], "kwargs": {"data": ["spec", "spec"]}}),
        ("list_variables", {"pattern": "*"}),
        ("plot", {"variables": ["spec", "combo"], "return_image": False}),
    ])
    assert not any(r[0] for r in res), [r for r in res if r[0]]
    assert res[2][1]["type"] == "spectrogram" and res[2][1]["plot"]["zlog"] is True
    kinds = {v["name"]: v["type"] for v in res[4][1]["variables"]}
    assert kinds["combo"] == "pseudo"


def test_errors_are_reported():
    res = run([
        ("get_values", {"name": "missing"}),
        ("call_function", {"function": "download"}),
        ("load_data", {"mission": "nosuch", "instrument": "x", "trange": ["2020-01-01", "2020-01-02"]}),
        ("load_data", {"mission": "omni", "instrument": "data", "trange": ["2020-01-01", "2020-01-02"],
                       "options": {"downloadonly": True}}),
        ("plot", {"variables": "missing*"}),
    ])
    assert all(r[0] for r in res)
    assert "not in the operation catalog" in res[1][1]
    assert "unknown mission" in res[2][1]


def test_discovery():
    res = run([
        ("list_loaders", {}),
        ("list_loaders", {"mission": "themis"}),
        ("describe_function", {"name": "mms.fgm", "max_doc": 200}),
        ("describe_function", {"name": "tinterpol"}),
        ("list_operations", {}),
        ("run_python", {"code": "x = 2\nx * 21"}),
        ("run_python", {"code": "x + 1"}),
    ])
    assert not any(r[0] for r in res), [r for r in res if r[0]]
    assert {"themis", "mms", "psp", "omni", "wind"} <= set(res[0][1]["missions"])
    assert "fgm" in res[1][1]["loaders"]
    assert "trange" in res[2][1]["signature"]
    assert "cotrans" in res[4][1]["coordinates"]
    assert res[5][1]["value"] == 42 and res[6][1]["value"] == 3


def test_output_dir(tmp_path, monkeypatch):
    target = tmp_path / "elsewhere"
    res = run([
        ("set_output_dir", {"path": "relative/not/allowed"}),
        ("set_output_dir", {"path": str(target)}),
        ("create_variable", {"name": "o", "times": [T0, T0 + 1], "values": [1.0, 2.0]}),
        ("plot", {"variables": "o", "return_image": False}),
        ("status", {}),
    ])
    assert res[0][0] and not any(r[0] for r in res[1:])
    assert res[3][1]["path"].startswith(str(target)) and res[4][1]["output_dir"] == str(target)
    monkeypatch.setattr(runtime, "_output_override", None)
    monkeypatch.delenv("SPEDAS_TPLOT_OUTPUT_DIR")
    plugin = tmp_path / "plugin"
    (plugin / ".codex-plugin").mkdir(parents=True)
    monkeypatch.chdir(plugin)
    assert runtime._default_output_dir() == runtime.Path.home() / "spedas_tplot_output"
    monkeypatch.chdir(tmp_path)
    assert runtime._default_output_dir() == tmp_path / "spedas_tplot_output"
