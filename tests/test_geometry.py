import asyncio
import math
from pathlib import Path
import tempfile

import pytest
from mcp import Client
from mcp.server.mcpserver.exceptions import ToolError
from mcp.client.stdio import StdioServerParameters
import sys

from bridge import BASE, Bridge

def live(document):
    return [b for b in document["bodies"] if not b["consumed"]]

async def with_bridge(action):
    with tempfile.TemporaryDirectory(prefix="geometry-", dir=BASE / "models") as folder:
        bridge = Bridge(Path(folder))
        try:
            await bridge.change({"op": "new", "name": "Test"}, fresh=True)
            await action(bridge)
        finally:
            bridge.close()

@pytest.mark.parametrize("shape,volume", [
    ({"kind": "cylinder", "radius": 5, "height": 10}, math.pi * 250),
    ({"kind": "sphere", "radius": 5}, math.pi * 500 / 3),
    ({"kind": "cone", "bottom_radius": 5, "top_radius": 2, "height": 10}, math.pi * 130),
    ({"kind": "torus", "major_radius": 10, "minor_radius": 2}, 80 * math.pi**2),
])
def test_primitive_exact_volumes(shape, volume):
    async def action(b):
        result = await b.change({"op": "primitive", "shape": shape, "name": "Solid", "part_id": None})
        body = live(result["document"])[0]
        assert body["valid_brep"]
        assert math.isclose(body["volume_mm3"], volume, rel_tol=1e-7)
    asyncio.run(with_bridge(action))

def test_sketch_extrusion_revolution_and_loft():
    async def action(b):
        rectangle = await b.change({"op": "sketch", "name": "Rectangle", "part_id": None,
            "plane": "XY", "offset": 0, "profile": {"kind": "rectangle",
            "origin": {"x": 5, "y": 0}, "size": {"x": 5, "y": 10}}})
        sid = rectangle["outcome"]["sketch_id"]
        result = await b.change({"op": "revolve", "sketch_id": sid, "angle": 360, "axis": 1})
        assert math.isclose(live(result["document"])[0]["volume_mm3"], 750 * math.pi, rel_tol=1e-7)
        await b.change({"op": "new", "name": "Loft"}, fresh=True)
        first = await b.change({"op": "sketch", "name": "Base", "part_id": None,
            "plane": "XY", "offset": 0, "profile": {"kind": "circle",
            "center": {"x": 0, "y": 0}, "radius": 10}})
        second = await b.change({"op": "sketch", "name": "Top", "part_id": first["outcome"]["part_id"],
            "plane": "XY", "offset": 20, "profile": {"kind": "circle",
            "center": {"x": 0, "y": 0}, "radius": 5}})
        result = await b.change({"op": "loft", "sketch_ids":
            [first["outcome"]["sketch_id"], second["outcome"]["sketch_id"]], "ruled": False})
        assert math.isclose(live(result["document"])[0]["volume_mm3"], math.pi * 20 * 175 / 3, rel_tol=1e-6)
        await b.change({"op": "new", "name": "Polygon"}, fresh=True)
        polygon = await b.change({"op": "sketch", "name": "Triangle", "part_id": None,
            "plane": "XZ", "offset": 3, "profile": {"kind": "polygon",
            "points": [{"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 0, "y": 10}]}})
        result = await b.change({"op": "extrude", "sketch_id": polygon["outcome"]["sketch_id"],
                                 "height": 5, "mode": "add"})
        assert math.isclose(live(result["document"])[0]["volume_mm3"], 250, rel_tol=1e-7)
    asyncio.run(with_bridge(action))

def test_edge_operations_translation_and_failure_rollback():
    async def action(b):
        box = await b.change({"op": "primitive", "shape": {"kind": "box",
            "size": {"x": 40, "y": 30, "z": 10}}, "name": "Base", "part_id": None})
        bid = box["outcome"]["body_id"]
        rounded = await b.change({"op": "fillet", "body_id": bid, "radius": 2, "edge_ids": []})
        rounded_body = live(rounded["document"])[0]
        assert 11000 < rounded_body["volume_mm3"] < 12000
        moved = await b.change({"op": "translate", "body_id": rounded_body["id"],
                               "offset": {"x": 20, "y": -5, "z": 3}})
        moved_body = live(moved["document"])[0]
        assert math.isclose(moved_body["volume_mm3"], rounded_body["volume_mm3"], rel_tol=1e-8)
        for index, delta in enumerate([20, -5, 3, 20, -5, 3]):
            assert math.isclose(moved_body["bbox_mm"][index] - rounded_body["bbox_mm"][index], delta, abs_tol=1e-5)
        before = b.current.read_bytes()
        with pytest.raises(ToolError):
            await b.change({"op": "fillet", "body_id": moved_body["id"], "radius": 1000, "edge_ids": []})
        assert b.current.read_bytes() == before
        await b.undo()
        await b.undo()
        chamfer = await b.change({"op": "chamfer", "body_id": bid, "distance": 1, "edge_ids": []})
        assert 11000 < live(chamfer["document"])[0]["volume_mm3"] < 12000
        before = b.current.read_bytes()
        b.timeout = 0.00001
        with pytest.raises(ToolError, match="timed out"):
            await b.change({"op": "part", "name": "Must not commit"})
        assert b.current.read_bytes() == before
    asyncio.run(with_bridge(action))

def test_concurrent_changes_are_serialized():
    async def action(b):
        await asyncio.gather(*[b.change({"op": "primitive", "shape": {"kind": "sphere",
            "radius": r}, "name": f"Sphere {r}", "part_id": None}) for r in [2, 3]])
        assert len(live(b.document)) == 2
        assert len({body["id"] for body in live(b.document)}) == 2
    asyncio.run(with_bridge(action))

def test_legacy_protocol():
    async def action(b):
        params = StdioServerParameters(command=sys.executable,
            args=[str(BASE / "server.py"), "--workspace", str(b.workspace)])
        async with Client(params, mode="legacy") as client:
            tools = await client.list_tools()
            assert len(tools.tools) == 19
            result = await client.call_tool("qymcad_create_document", {"name": "Legacy"})
            assert not result.is_error
            assert result.structured_content["document"]["units"] == "mm"
    asyncio.run(with_bridge(action))

