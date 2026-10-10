"""Generate absolute paths for the current installation without modifying a client."""
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parent
command = str(root / ".venv/Scripts/python.exe")
args = ["-u", str(root / "server.py"), "--workspace", str(root / "models"), "--live"]
config = {"command": command, "args": args, "env": {"PYTHONUTF8": "1"}}
(root / "mcp-config.json").write_text(json.dumps({"mcpServers": {"qymcad": config}}, ensure_ascii=False, indent=2), encoding="utf-8")
lines = ["[mcp_servers.qymcad]", "command = " + json.dumps(command, ensure_ascii=False),
         "args = " + json.dumps(args, ensure_ascii=False), "startup_timeout_sec = 20",
         "tool_timeout_sec = 240", "", "[mcp_servers.qymcad.env]", 'PYTHONUTF8 = "1"', ""]
(root / "codex-config.toml").write_text("\n".join(lines), encoding="utf-8")
print("Generated mcp-config.json and codex-config.toml")
