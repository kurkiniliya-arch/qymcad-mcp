"""Create a redistributable Windows bundle with the matching upstream source archive."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "QymCAD-MCP-Windows.zip"

def main():
    files = []
    for pattern in ("*.py", "*.ps1", "requirements*.txt", "*.md", "*.toml", "*.json", "LICENSE", ".gitignore", ".gitattributes"):
        files.extend(ROOT.glob(pattern))
    files = [p for p in files if p.name not in {"mcp-config.json", "codex-config.toml"} and not p.name.startswith("publish-")]
    for folder in ("bin", "backend/src", "sources", "patches", "tests", "vendor/qymcad-app", "models/demo"):
        files.extend(p for p in (ROOT / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    files.extend([ROOT / "backend/Cargo.toml", ROOT / "backend/Cargo.lock"])
    # Only the matching patched desktop is distributed; this folder supplies runtime DLLs.
    files = [path for path in files if path != ROOT / "vendor/qymcad-app/qymcad.exe"]
    with zipfile.ZipFile(TARGET, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(set(files)):
            archive.write(path, "qymcad-mcp/" + path.relative_to(ROOT).as_posix())
    with TARGET.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    TARGET.with_suffix(".zip.sha256").write_text(digest + "  " + TARGET.name + "\n", encoding="ascii")
    print(json.dumps({"file": str(TARGET), "bytes": TARGET.stat().st_size, "sha256": digest}))

if __name__ == "__main__":
    main()
