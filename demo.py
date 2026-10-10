"""Build a saved demonstration part through the MCP protocol, not internal calls."""
import asyncio
import json
import os
import sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parent

async def main():
    params = StdioServerParameters(command=sys.executable,
        args=[str(ROOT / "server.py"), "--workspace", str(ROOT / "models")],
        env={**os.environ, "PYTHONUTF8": "1"})
    async with Client(params) as client:
        async def call(tool, **arguments):
            result = await client.call_tool("qymcad_" + tool, arguments)
            if result.is_error:
                raise RuntimeError(str(result.content))
            return result.structured_content
        await call("create_document", name="MCP demonstration")
        base = await call("create_primitive", name="Mounting plate", shape={
            "kind": "box", "size": {"x": 50, "y": 30, "z": 8}})
        await call("set_parameters", values={"width": "50", "depth": "30", "thickness": "8"})
        for key, expression in {"dx": "width", "dy": "depth", "dz": "thickness"}.items():
            await call("set_dimension", feature_id=base["outcome"]["feature_id"], key=key, expression=expression)
        await call("fillet", body_id=base["outcome"]["body_id"], radius=2)
        for x in (-15, 15):
            sketch = await call("create_sketch", name=f"Hole at {x}", part_id=base["outcome"]["part_id"],
                profile={"kind": "circle", "center": {"x": x, "y": 0}, "radius": 3})
            await call("extrude", sketch_id=sketch["outcome"]["sketch_id"], height=8, mode="cut")
        await call("save_project", file="demo/Крепление.qcad", overwrite=True)
        await call("export", file="demo/Крепление.stl", format="stl", overwrite=True)
        await call("export", file="demo/Крепление.step", format="step", overwrite=True)
        report = await call("inspect")
        (ROOT / "models/demo/inspection.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"saved": "models/demo", "bodies": len([b for b in report["bodies"] if not b["consumed"]])}))

if __name__ == "__main__":
    asyncio.run(main())
