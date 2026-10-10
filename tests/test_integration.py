"""End-to-end tests call the real server over stdio and use the real OCCT kernel."""
import asyncio
import math
import os
from pathlib import Path
import struct
import sys
import tempfile
import zipfile

from mcp import Client
from mcp.client.stdio import StdioServerParameters

BASE = Path(__file__).resolve().parents[1]

async def scenario(workspace: Path):
    params = StdioServerParameters(command=sys.executable,
        args=[str(BASE / "server.py"), "--workspace", str(workspace)],
        env={**os.environ, "PYTHONUTF8": "1"})
    async with Client(params, read_timeout_seconds=240) as client:
        tools = await client.list_tools()
        assert len(tools.tools) == 19
        async def call(tool, **arguments):
            result = await client.call_tool("qymcad_" + tool, arguments)
            assert not result.is_error, result.content
            return result.structured_content
        async def fails(tool, **arguments):
            result = await client.call_tool("qymcad_" + tool, arguments)
            assert result.is_error, result
            return result
        status = await call("status")
        assert status["backend_available"] and not status["gui_live_sync"]
        await fails("inspect")
        await call("create_document", name="Проверка MCP")
        box = await call("create_primitive", name="Основание", shape={
            "kind": "box", "size": {"x": 40, "y": 30, "z": 8}})
        box_id = box["outcome"]["body_id"]
        part_id = box["outcome"]["part_id"]
        assert math.isclose(box["document"]["bodies"][0]["volume_mm3"], 9600)
        await call("set_parameters", values={"width": "50", "height": "width/5"})
        await call("set_dimension", feature_id=box_id, key="dx", expression="width")
        await call("set_dimension", feature_id=box_id, key="dz", expression="height")
        changed = await call("inspect")
        assert math.isclose(changed["bodies"][0]["volume_mm3"], 15000)
        assert len(changed["bodies"][0]["edge_ids"]) == 12
        await fails("set_dimension", feature_id=box_id, key="missing", expression="10")
        await fails("set_dimension", feature_id=box_id, key="dx", expression="unknown_variable")
        assert (await call("inspect")) == changed
        await call("undo")
        assert math.isclose((await call("inspect"))["bodies"][0]["volume_mm3"], 12000)
        hole = await call("create_sketch", name="Отверстие", part_id=part_id, profile={
            "kind": "circle", "center": {"x": 10, "y": 10}, "radius": 3})
        cut = await call("extrude", sketch_id=hole["outcome"]["sketch_id"], height=20, mode="cut")
        cut_body = next(b for b in cut["document"]["bodies"] if not b["consumed"])
        assert math.isclose(cut_body["volume_mm3"], 12000 - math.pi * 9 * 8, rel_tol=1e-7)
        await call("rename", node_id=cut["outcome"]["body_id"], name="Основание с отверстием")
        await call("save_project", file="деталь.qcad")
        await call("export", file="деталь.stl", format="stl")
        await call("export", file="деталь.step", format="step")
        assert zipfile.is_zipfile(workspace / "деталь.qcad")
        stl = (workspace / "деталь.stl").read_bytes()
        triangles = struct.unpack_from("<I", stl, 80)[0]
        assert len(stl) == 84 + 50 * triangles and triangles > 20
        assert b"ISO-10303-21" in (workspace / "деталь.step").read_bytes()[:100]
        original = (workspace / "деталь.qcad").read_bytes()
        await fails("save_project", file="деталь.qcad")
        assert (workspace / "деталь.qcad").read_bytes() == original
        await fails("save_project", file="../outside.qcad")
        await fails("export", file="../outside.stl", format="stl")
        await fails("save_project", file="test.qcad:stream")
        await fails("save_project", file=".hidden/test.qcad")
        await call("create_document", name="Second")
        reopened = await call("open_project", file="деталь.qcad")
        live = next(b for b in reopened["document"]["bodies"] if not b["consumed"])
        assert math.isclose(live["volume_mm3"], cut_body["volume_mm3"], rel_tol=1e-8)
        await call("set_parameters", values={"width": "60"})
        live = next(b for b in (await call("inspect"))["bodies"] if not b["consumed"])
        assert math.isclose(live["volume_mm3"], 14400 - math.pi * 9 * 8, rel_tol=1e-7)
        await call("save_project", file="деталь.qcad", overwrite=True)
        await fails("create_primitive", shape={"kind": "sphere", "radius": -1})
        await fails("create_primitive", shape={"kind": "sphere", "radius": 1, "unexpected": 5})
        return {"tools": len(tools.tools), "triangles": triangles}

def test_stdio_native_cad_round_trip():
    with tempfile.TemporaryDirectory(prefix="integration-", dir=BASE / "models") as folder:
        result = asyncio.run(scenario(Path(folder)))
        print(result)
