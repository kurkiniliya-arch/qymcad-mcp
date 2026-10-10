"""Install the pinned, unmodified runtime DLLs from the official QymCAD release."""
import hashlib
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
URL = "https://github.com/QymIs-Tech/QymCAD/releases/download/v0.1.0-dev.20261001/qymcad-0.1.0-dev.20261001-win64.zip"
SHA256 = "332521c18b7b60cdbf8215c27be5e63875ffe8010a1bad22cd46a002429b1c2d"

def main():
    archive = ROOT / "vendor" / "qymcad-windows.zip"
    archive.parent.mkdir(exist_ok=True)
    if not archive.exists():
        urllib.request.urlretrieve(URL, archive)
    with archive.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != SHA256:
        raise RuntimeError("QymCAD runtime archive checksum mismatch")
    destination = ROOT / "vendor" / "qymcad-app"
    destination.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as package:
        for info in package.infolist():
            name = Path(info.filename)
            if len(name.parts) != 1 or name.name in (".", ".."):
                raise RuntimeError("Unexpected archive path")
            package.extract(info, destination)
    print(destination)

if __name__ == "__main__":
    main()
