"""Transactional subprocess adapter to the actual QymCAD Rust crates."""
import asyncio
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from mcp.server.mcpserver.exceptions import ToolError

BASE = Path(__file__).resolve().parent
REVISION = "3ee0d1383accbf9cf34ad0bf8403215f9885dcbe"

class Bridge:
    def __init__(self, workspace: Path, backend: Path | None = None, timeout: float = 180):
        self.workspace = workspace.resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.backend = backend or BASE / "bin/qymcad-mcp-backend.exe"
        self.timeout = timeout
        self._temporary = tempfile.TemporaryDirectory(prefix=".qymcad-session-", dir=self.workspace)
        self.session = Path(self._temporary.name)
        self.current = self.session / "current.qcad"
        self.history: list[Path] = []
        self.document = None
        self.lock = asyncio.Lock()
        self.env = os.environ.copy()
        self.env["PATH"] = str(BASE / "vendor/qymcad-app") + os.pathsep + self.env.get("PATH", "")

    def close(self):
        self._temporary.cleanup()

    def path(self, value: str, suffixes: set[str], reading=False) -> Path:
        if not value or "\0" in value:
            raise ToolError("Specify a local file name inside the model workspace")
        raw = Path(value)
        if value.startswith(("//", "\\\\")) or ":" in value.replace(raw.drive, "", 1):
            raise ToolError("Network paths and alternate data streams are not supported")
        target = (raw if raw.is_absolute() else self.workspace / raw).resolve()
        try:
            relative = target.relative_to(self.workspace)
        except ValueError as exc:
            raise ToolError("File must be inside the configured model workspace") from exc
        if any(part.startswith(".") for part in relative.parts):
            raise ToolError("Internal and hidden paths cannot be accessed")
        if target.suffix.lower() not in suffixes:
            raise ToolError(f"Expected file extension: {', '.join(sorted(suffixes))}")
        if reading and not target.is_file():
            raise ToolError("The requested file does not exist")
        if reading and target.stat().st_size > 100 * 1024 * 1024:
            raise ToolError("Project files are limited to 100 MB")
        return target

    async def invoke(self, command, source=None, output=None):
        if not self.backend.is_file():
            raise ToolError("QymCAD backend is missing. Run build.ps1 first.")
        with tempfile.TemporaryDirectory(prefix="operation-", dir=self.session) as directory:
            folder = Path(directory)
            request = folder / "request.json"
            response = folder / "response.json"
            request.write_text(json.dumps({"input": str(source) if source else None,
                "output": str(output) if output else None, "command": command}, ensure_ascii=False), encoding="utf-8")
            with (folder / "kernel.log").open("wb") as log:
                try:
                    process = await asyncio.create_subprocess_exec(
                        str(self.backend), str(request), str(response), env=self.env,
                        cwd=folder, stdout=log, stderr=log,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                except OSError as exc:
                    raise ToolError(f"Cannot start QymCAD backend: {exc}") from exc
                try:
                    await asyncio.wait_for(process.wait(), self.timeout)
                except (TimeoutError, asyncio.CancelledError) as exc:
                    if process.returncode is None:
                        process.kill()
                    await process.wait()
                    if isinstance(exc, asyncio.CancelledError):
                        raise
                    raise ToolError("Geometry operation timed out; previous document preserved") from exc
            if process.returncode != 0 or not response.is_file():
                raise ToolError(f"QymCAD backend failed (exit {process.returncode}); previous document preserved. Check OCCT runtime DLLs.")
            reply = json.loads(response.read_text(encoding="utf-8"))
            if not reply["ok"]:
                raise ToolError(reply["error"])
            return reply["result"]

    def require_document(self):
        if not self.current.is_file():
            raise ToolError("Create or open a document first")

    async def synchronize(self):
        return None

    async def inspect(self):
        async with self.lock:
            self.require_document()
            return self.document

    async def change(self, command, source=None, fresh=False):
        async with self.lock:
            if not fresh:
                self.require_document()
            candidate = self.session / "candidate.qcad"
            result = await self.invoke(command, source or (None if fresh else self.current), candidate)
            if self.current.exists():
                snapshot = self.session / f"undo-{os.urandom(8).hex()}.qcad"
                shutil.copy2(self.current, snapshot)
                self.history.append(snapshot)
            os.replace(candidate, self.current)
            self.document = result["document"]
            while len(self.history) > 20:
                self.history.pop(0).unlink()
            return result

    async def undo(self):
        async with self.lock:
            if not self.history:
                raise ToolError("There is no earlier document in this session")
            snapshot = self.history[-1]
            result = await self.invoke({"op": "inspect"}, snapshot)
            os.replace(snapshot, self.current)
            self.history.pop()
            self.document = result["document"]
            return result

    @contextmanager
    def destination(self, target: Path, overwrite: bool):
        if target.exists() and not overwrite:
            raise ToolError("Destination exists; choose another name or explicitly set overwrite=true")
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix=".qymcad-output-", suffix=target.suffix,
                                         dir=target.parent, delete=False) as handle:
            staged = Path(handle.name)
        try:
            yield staged
            if overwrite:
                os.replace(staged, target)
            else:
                try:
                    os.link(staged, target)
                except FileExistsError as exc:
                    raise ToolError("Destination exists; it was not overwritten") from exc
        finally:
            staged.unlink(missing_ok=True)

    async def save(self, file: str, overwrite: bool):
        async with self.lock:
            await self.synchronize()
            self.require_document()
            target = self.path(file, {".qcad"})
            with self.destination(target, overwrite) as staged:
                shutil.copyfile(self.current, staged)
            return {"path": str(target), "bytes": target.stat().st_size}

    async def export(self, file: str, format: str, body_id, overwrite: bool):
        async with self.lock:
            await self.synchronize()
            self.require_document()
            suffixes = {".stl"} if format == "stl" else {".step", ".stp"}
            target = self.path(file, suffixes)
            with self.destination(target, overwrite) as staged:
                await self.invoke({"op": "export", "path": str(staged), "format": format,
                                   "body_id": body_id}, self.current)
                if not staged.stat().st_size:
                    raise ToolError("The CAD exporter produced an empty file")
            return {"path": str(target), "format": format, "bytes": target.stat().st_size,
                    "units": "mm", "body_id": body_id}
