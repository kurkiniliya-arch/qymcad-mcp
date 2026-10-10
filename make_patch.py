"""Package the desktop changes against the pinned upstream checkout."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent

def main():
    source = ROOT.parent / "QymCAD"
    patch = subprocess.run(["git", "diff", "--binary", "HEAD"], cwd=source, check=True, capture_output=True).stdout
    for name in ("crates/qymcad/src/gui/live_bridge.rs", "crates/qymcad/src/gui/selection_sync.rs",
                 "crates/qymcad/tests/live_bridge.rs"):
        lines = (source / name).read_text(encoding="utf-8").splitlines()
        addition = f"diff --git a/{name} b/{name}\nnew file mode 100644\n--- /dev/null\n+++ b/{name}\n@@ -0,0 +1,{len(lines)} @@\n"
        addition += "".join("+" + line + "\n" for line in lines)
        patch += addition.encode("utf-8")
    target = ROOT / "patches/live-window.patch"
    target.parent.mkdir(exist_ok=True)
    target.write_bytes(patch)
    print(f"Desktop patch: {len(patch)} bytes")

if __name__ == "__main__":
    main()
