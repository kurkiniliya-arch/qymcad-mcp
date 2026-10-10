"""Two-way transactions with one explicitly launched QymCAD desktop window."""
import asyncio
import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid

from mcp.server.mcpserver.exceptions import ToolError
from bridge import BASE, Bridge


def process_alive(pid: int) -> bool:
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(kernel.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code))) and code.value == 259
        finally:
            kernel.CloseHandle(ctypes.c_void_p(handle))
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


class LiveBridge(Bridge):
    def __init__(self, workspace: Path, backend: Path | None = None, timeout: float = 180,
                 endpoint: Path | None = None):
        super().__init__(workspace, backend, timeout)
        self.endpoint = endpoint
        self.registry = BASE / ".live/window.json"
        self.gui = BASE / "bin/qymcad.exe"

    async def _request(self, operation: str, *, revision=None, candidate=None, document=None,
                       timeout=15):
        deadline = time.monotonic() + timeout
        while True:
            try:
                return await self._exchange(operation, revision=revision, candidate=candidate,
                                            document=document, timeout=max(0.3, deadline-time.monotonic()))
            except ToolError as error:
                if not str(error).startswith("Window is busy:") or time.monotonic() + 0.3 >= deadline:
                    raise
                # A just-committed model may still be finishing its desktop rebuild.
                await asyncio.sleep(0.15)

    async def _exchange(self, operation: str, *, revision=None, candidate=None, document=None,
                        timeout=15):
        if self.endpoint is None:
            raise ToolError("No desktop connection")
        folder = self.endpoint / uuid.uuid4().hex
        folder.mkdir(parents=True)
        if candidate is not None:
            shutil.copyfile(candidate, folder / "candidate.qcad")
        payload = {"op": operation, "deadline_ms": int((time.time() + timeout - 0.2) * 1000),
                   "revision": revision, "document": document}
        pending = folder / "request.tmp"
        pending.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        pending.replace(folder / "request.json")
        deadline = time.monotonic() + timeout
        try:
            while time.monotonic() < deadline:
                response = folder / "response.json"
                if response.is_file():
                    result = json.loads(response.read_text(encoding="utf-8"))
                    if not result["ok"]:
                        raise ToolError(result["error"])
                    if operation == "snapshot":
                        shutil.copyfile(folder / "snapshot.qcad", self.current)
                    if operation == "screenshot":
                        result["png"] = (folder / "window.png").read_bytes()
                    return result
                await asyncio.sleep(0.05)
            # Cancellation cannot retract a commit already accepted by the GUI.
            raise ToolError("Desktop did not acknowledge the request. Its outcome is unknown; inspect the window before retrying.")
        finally:
            # Rename prevents an unclaimed request from running after cancellation.
            request = folder / "request.json"
            try:
                request.rename(folder / "cancelled.json")
            except FileNotFoundError:
                pass
            if (folder / "response.json").exists() or (folder / "cancelled.json").exists():
                shutil.rmtree(folder)

    async def connect(self):
        if self.endpoint is not None:
            return await self._request("status")
        self.registry.parent.mkdir(parents=True, exist_ok=True)
        launch_lock = self.registry.with_suffix(".lock")
        start = time.monotonic()
        while True:
            try:
                lock = launch_lock.open("x")
                break
            except FileExistsError:
                if time.monotonic() - start > 30:
                    raise ToolError("Another desktop launcher is active. Check .live/window.lock if its process stopped.")
                await asyncio.sleep(0.1)
        try:
            if self.registry.is_file():
                record = json.loads(self.registry.read_text(encoding="utf-8"))
                if process_alive(record["pid"]):
                    self.endpoint = Path(record["endpoint"])
                    return await self._request("status")
            if not self.gui.is_file():
                raise ToolError("Desktop with live support is missing. Run build_gui.ps1 first.")
            root = self.registry.parent / uuid.uuid4().hex
            root.mkdir()
            env = self.env.copy()
            env["QYMCAD_LIVE_DIR"] = str(root)
            with (root / "desktop.log").open("wb") as log:
                process = subprocess.Popen([str(self.gui)], env=env, cwd=BASE, stdin=subprocess.DEVNULL,
                                           stdout=log, stderr=log)
            self.registry.write_text(json.dumps({"pid": process.pid, "endpoint": str(root)}), encoding="utf-8")
            self.endpoint = root
            return await self._request("status", timeout=45)
        finally:
            lock.close()
            launch_lock.unlink(missing_ok=True)

    async def synchronize(self):
        await self.connect()
        return await self._request("snapshot")

    async def inspect(self):
        async with self.lock:
            snapshot = await self.synchronize()
            result = await self.invoke({"op": "inspect"}, self.current)
            self.document = result["document"]
            return {**self.document, "gui": snapshot}

    async def change(self, command, source=None, fresh=False):
        async with self.lock:
            before = await self.synchronize()
            candidate = self.session / "candidate.qcad"
            result = await self.invoke(command, source or (None if fresh else self.current), candidate)
            document = str(source) if fresh and source else "" if fresh else None
            applied = await self._request("apply", revision=before["revision"], candidate=candidate,
                                          document=document)
            os.replace(candidate, self.current)
            self.document = result["document"]
            return {**result, "gui": applied}

    async def undo(self):
        async with self.lock:
            before = await self.synchronize()
            await self._request("undo", revision=before["revision"])
            after = await self.synchronize()
            result = await self.invoke({"op": "inspect"}, self.current)
            self.document = result["document"]
            return {**result, "gui": after}

    async def status(self):
        async with self.lock:
            return await self.connect()

    async def fit(self):
        async with self.lock:
            await self.connect()
            return await self._request("fit")

    async def screenshot(self):
        async with self.lock:
            await self.connect()
            return (await self._request("screenshot"))["png"]
