import asyncio
import json
from pathlib import Path
import time

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from live import LiveBridge


def test_unclaimed_timeout_cannot_execute_later(tmp_path):
    async def run():
        endpoint = tmp_path / "endpoint"
        bridge = LiveBridge(tmp_path / "models", endpoint=endpoint)
        try:
            with pytest.raises(ToolError, match="outcome is unknown"):
                await bridge._request("undo", revision="old", timeout=0.3)
            assert list(endpoint.iterdir()) == []
        finally:
            bridge.close()
    asyncio.run(run())


def test_desktop_rejection_is_preserved_and_request_is_cleaned(tmp_path):
    async def run():
        endpoint = tmp_path / "endpoint"
        endpoint.mkdir()
        bridge = LiveBridge(tmp_path / "models", endpoint=endpoint)

        async def window():
            while True:
                requests = list(endpoint.glob("*/request.json"))
                if requests:
                    request = requests[0]
                    payload = json.loads(request.read_text(encoding="utf-8"))
                    assert payload["revision"] == "stale"
                    assert payload["deadline_ms"] > time.time() * 1000
                    request.rename(request.with_name("processing.json"))
                    request.with_name("response.json").write_text(json.dumps({"ok": False,
                        "error": "Document changed in the window; inspect it and retry the operation"}), encoding="utf-8")
                    return
                await asyncio.sleep(0.01)

        task = asyncio.create_task(window())
        try:
            with pytest.raises(ToolError, match="Document changed in the window"):
                await bridge._request("apply", revision="stale")
            await task
            assert list(endpoint.iterdir()) == []
        finally:
            task.cancel()
            bridge.close()
    asyncio.run(run())


def test_cancelling_unclaimed_request_removes_it(tmp_path):
    async def run():
        endpoint = tmp_path / "endpoint"
        bridge = LiveBridge(tmp_path / "models", endpoint=endpoint)
        try:
            task = asyncio.create_task(bridge._request("undo", revision="old"))
            await asyncio.sleep(0.05)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert list(endpoint.iterdir()) == []
        finally:
            bridge.close()
    asyncio.run(run())
