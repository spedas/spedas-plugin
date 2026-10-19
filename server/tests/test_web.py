"""The web workbench: same session as the tools, events from both sides, panels for the browser."""

import json
import os
import urllib.error
import urllib.request

import numpy as np
import pytest

os.environ["SPEDAS_TPLOT_ALLOW_EXEC"] = "1"

from spedas_tplot_mcp import events, runtime, web  # noqa: E402
from spedas_tplot_mcp.server import invoke  # noqa: E402

T0 = 1444953600.0


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    os.environ["SPEDAS_TPLOT_OUTPUT_DIR"] = str(tmp_path_factory.mktemp("web"))
    os.environ["SPEDAS_TPLOT_WEB"] = "1"
    url = web.start(port=18765)
    assert url
    return url.rstrip("/")


def req(base, path, body=None, headers=None):
    h = {"Content-Type": "application/json", **(headers or {})}
    r = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(), headers=h)
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, json.loads(resp.read()) if "json" in resp.headers["Content-Type"] else resp.read()
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_shared_session(base):
    t = (T0 + np.arange(5000) * 0.5).tolist()
    b = np.column_stack([np.sin(np.arange(5000) / 80), np.cos(np.arange(5000) / 80), np.ones(5000)])
    b[2500, 0] = 40.0  # a spike that decimation must keep
    invoke("create_variable", {"name": "wb_b", "times": t, "values": b.tolist(), "units": "nT"}, "agent")
    invoke("create_variable", {"name": "wb_spec", "times": t[:300], "values": np.random.rand(300, 16).tolist(),
                               "v": np.logspace(1, 4, 16).tolist()}, "agent")
    invoke("set_options", {"variables": "wb_spec", "options": {"spec": True, "zlog": True, "ylog": True}}, "agent")
    invoke("call_function", {"function": "store_data", "args": ["wb_combo"],
                             "kwargs": {"data": ["wb_b", "wb_b"]}}, "agent")

    status, page = req(base, "/")
    assert status == 200 and b"tplot workbench" in page
    status, st = req(base, "/api/state")
    names = {v["name"] for v in st["variables"]}
    assert {"wb_b", "wb_spec", "wb_combo"} <= names and "run_python" not in st["tools"]

    status, p = req(base, "/api/panels?names=wb_b,wb_spec,wb_combo&max_points=400")
    line, spec, combo = p["panels"]
    assert line["kind"] == "line" and len(line["traces"]) == 3
    assert len(line["traces"][0]["x"]) <= 400 and max(v for v in line["traces"][0]["y"] if v is not None) == 40.0
    assert spec["kind"] == "spec" and len(spec["y"]) == 16 and len(spec["z"]) == 16 and spec["options"]["ylog"]
    assert combo["kind"] == "line" and len(combo["traces"]) == 6
    assert p["full_range"][0].startswith("2015-10-16T00:00:00")

    status, p = req(base, "/api/panels?names=wb_b&t0=2015-10-16/00:10&t1=2015-10-16/00:11")
    assert len(p["panels"][0]["traces"][0]["x"]) == 121  # full detail inside the zoom window

    status, r = req(base, "/api/tool/call_function", {"function": "avg_data", "args": ["wb_b"], "kwargs": {"res": 60}})
    assert status == 200 and r["result"]["created"] == ["wb_b-avg"]
    status, r = req(base, "/api/tool/plot", {"variables": ["wb_b", "wb_spec"], "return_image": False})
    assert status == 200 and r["result"]["url"].startswith("/files/plots/")
    status, png = req(base, r["result"]["url"])
    assert status == 200 and png[:4] == b"\x89PNG"

    evs, _, _ = events.since(0)
    sources = {(e["source"], e["tool"]) for e in evs}
    assert ("agent", "create_variable") in sources and ("web", "call_function") in sources and ("web", "plot") in sources
    plot_ev = [e for e in evs if e["tool"] == "plot"][-1]
    assert plot_ev["result"]["panels"] == ["wb_b", "wb_spec"]


def test_refusals(base):
    assert req(base, "/api/tool/run_python", {"code": "1"})[0] == 404
    assert req(base, "/api/tool/get_values", {"name": "nope"})[0] == 400
    assert req(base, "/api/tool/status", {}, {"Origin": "http://evil.example"})[0] == 403
    assert req(base, "/api/state", None, {"Host": "evil.example"})[0] == 403
    assert req(base, "/files/../../etc/passwd")[0] == 404
