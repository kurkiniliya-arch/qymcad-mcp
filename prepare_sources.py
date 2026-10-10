"""Get the pinned upstream tree and apply the distributed desktop bridge patch."""
from pathlib import Path
import subprocess
import zipfile

from bridge import BASE, REVISION

def main():
    target = BASE.parent / "QymCAD"
    marker = target / "crates/qymcad/src/gui/live_bridge.rs"
    if marker.is_file():
        print("Desktop bridge sources are already present")
        return
    if not target.exists():
        archive = BASE / "sources/QymCAD-3ee0d138.zip"
        if archive.is_file():
            target.mkdir()
            with zipfile.ZipFile(archive) as source:
                # The archive contains repository-relative paths.
                for entry in source.infolist():
                    resolved = (target / entry.filename).resolve()
                    if not resolved.is_relative_to(target.resolve()):
                        raise RuntimeError("Unsafe upstream archive path")
                source.extractall(target)
        else:
            subprocess.run(["git", "clone", "https://github.com/QymIs-Tech/QymCAD.git", str(target)], check=True)
            subprocess.run(["git", "checkout", "--detach", REVISION], cwd=target, check=True)
    patch = BASE / "patches/live-window.patch"
    subprocess.run(["git", "apply", "--check", str(patch)], cwd=target, check=True)
    subprocess.run(["git", "apply", str(patch)], cwd=target, check=True)
    print("Pinned QymCAD sources with desktop bridge are ready")

if __name__ == "__main__":
    main()
