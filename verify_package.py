"""Verify the distributed archive as a separate installation, using the same MCP transport."""
import asyncio
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import zipfile

from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parent

async def check(folder):
    installation = folder / "qymcad-mcp"
    params = StdioServerParameters(command=sys.executable,
        args=["-u", str(installation / "server.py"), "--workspace", str(installation / "models-check")],
        env={**os.environ, "PYTHONUTF8": "1"})
    async with Client(params, mode="legacy") as client:
        async def call(tool, **arguments):
            response = await client.call_tool("qymcad_" + tool, arguments)
            assert not response.is_error, response.content
            return response.structured_content
        await call("create_document", name="Package test")
        result = await call("create_primitive", shape={"kind": "cylinder", "radius": 4, "height": 10})
        assert math.isclose(result["document"]["bodies"][0]["volume_mm3"], math.pi * 160, rel_tol=1e-8)
        await call("save_project", file="package-test.qcad")
        await call("export", file="package-test.stl", format="stl")
        await call("export", file="package-test.step", format="step")
        return {"package_protocol_test": "passed", "tools": len((await client.list_tools()).tools)}

def main():
    (ROOT / "tests-output").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="package-check-", dir=ROOT / "tests-output") as directory:
        folder = Path(directory).resolve()
        assert folder.is_relative_to(ROOT.resolve())
        with zipfile.ZipFile(ROOT / "QymCAD-MCP-Windows.zip") as archive:
            assert archive.testzip() is None
            for info in archive.infolist():
                assert (folder / info.filename).resolve().is_relative_to(folder)
            archive.extractall(folder)
        print(json.dumps(asyncio.run(check(folder))))

if __name__ == "__main__":
    main()
