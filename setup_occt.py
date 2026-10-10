"""Fetch the pinned OCCT SDK from conda-forge and verify its published hash."""
import hashlib
import json
from pathlib import Path
import tarfile
import urllib.request
import zipfile

import zstandard

ROOT = Path(__file__).resolve().parent
NAME = "occt-7.8.1-novtk_hdfbec02_103.conda"
URL = f"https://conda.anaconda.org/conda-forge/win-64/{NAME}"
SHA256 = "28e3da6feaec750f1a7b64f0aebc7a5f209d64ce3cbc49a3d1a22d2c81ff32d1"


def main():
    destination = ROOT / "vendor" / "occt"
    archive = ROOT / "vendor" / NAME
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        urllib.request.urlretrieve(URL, archive)
    with archive.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != SHA256:
        raise RuntimeError("OCCT archive checksum mismatch")
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as package:
        for item in package.namelist():
            if item.endswith(".tar.zst"):
                with package.open(item) as compressed:
                    with zstandard.ZstdDecompressor().stream_reader(compressed) as stream:
                        with tarfile.open(fileobj=stream, mode="r|") as files:
                            files.extractall(destination, filter="data")
    (ROOT / "vendor" / "occt-source.json").write_text(json.dumps({
        "url": URL, "sha256": actual,
        "upstream": "https://github.com/Open-Cascade-SAS/OCCT/tree/V7_8_1",
        "package": NAME,
    }, indent=2), encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
