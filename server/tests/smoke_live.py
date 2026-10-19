"""Live smoke: drive the server through an in-memory MCP client session (needs network)."""
import asyncio, json, os, sys, tempfile
os.environ.setdefault("SPEDAS_TPLOT_OUTPUT_DIR", tempfile.mkdtemp(prefix="tplot_smoke_"))
os.environ.setdefault("SPEDAS_TPLOT_ALLOW_EXEC", "1")
from mcp.shared.memory import create_connected_server_and_client_session
from spedas_tplot_mcp.server import mcp

async def main():
    async with create_connected_server_and_client_session(mcp._mcp_server) as c:
        tools = await c.list_tools()
        print("tools:", [t.name for t in tools.tools])
        async def call(_tool, **args):
            r = await c.call_tool(_tool, args)
            for item in r.content:
                if item.type == "text":
                    txt = item.text
                    print(f"--- {_tool} {'ERROR ' if r.isError else ''}{txt[:1500]}")
                else:
                    print(f"--- {_tool} [{item.type} {item.mimeType} {len(item.data)} b64 chars]")
            return r
        await call("status")
        await call("list_loaders", mission="omni")
        await call("describe_function", name="omni.data", max_doc=400)
        await call("load_data", mission="omni", instrument="data", trange=["2015-10-16", "2015-10-17"], options={"datatype": "1min"})
        await call("list_variables", pattern="B*GSM")
        await call("describe_variable", name="BZ_GSM")
        await call("get_values", name="BZ_GSM", max_points=5)
        await call("call_function", function="join_vec", args=[["BX_GSE", "BY_GSM", "BZ_GSM"]], kwargs={"newname": "b_gsm"})
        await call("call_function", function="avg_data", args=["b_gsm"], kwargs={"res": 600})
        await call("set_options", variables="b_gsm", options={"ytitle": "B GSM", "legend_names": ["Bx", "By", "Bz"]})
        await call("plot", variables=["b_gsm", "b_gsm-avg", "flow_speed", "SYM_H"], title="OMNI 2015-10-16")
        await call("export_variables", variables="b_gsm", path="exports/b.csv")
        await call("export_variables", variables=["b_gsm", "SYM_H"], path="exports/b.nc")
        await call("export_variables", variables=["b_gsm"], path="exports/b.pytplot")
        await call("run_python", code="d = pyspedas.get_data('SYM_H'); print(len(d.times)); float(np.nanmin(d.y))")
        await call("call_function", function="nonexistent")
        await call("get_values", name="nope")
        await call("get_script")
asyncio.run(main())
