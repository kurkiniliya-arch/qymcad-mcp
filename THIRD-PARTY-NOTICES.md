# Third-party notices

The adapter and its Rust backend are distributed under AGPL-3.0-or-later; see LICENSE.

QymCAD: https://github.com/QymIs-Tech/QymCAD, AGPL-3.0-or-later.
The backend statically links the unmodified qymcad-core, qymcad-io, qymcad-kernel
and qymcad-meshfit crates at revision 3ee0d1383accbf9cf34ad0bf8403215f9885dcbe.
The complete pinned source tree is included in sources/QymCAD-3ee0d138.zip.
The desktop is built from the same revision with the changes in patches/live-window.patch.
Those changes add a local transaction bridge, shared undo and window screenshots.
The patch, complete original source archive and build instructions accompany the binary.

Open CASCADE Technology 7.8.1: LGPL-2.1 with the Open CASCADE exception,
https://github.com/Open-Cascade-SAS/OCCT/tree/V7_8_1.
Runtime libraries are dynamically linked and replaceable. They are shipped unmodified
from the official QymCAD v0.1.0-dev.20261001 Windows release.
The original notices accompany them in vendor/qymcad-app.
setup_occt.py obtains build headers/import libraries from the pinned conda-forge SDK;
setup_runtime.py obtains the matching runtime from the official QymCAD release.
The SDK is a build dependency and is not included in the distribution ZIP.

Official MCP Python SDK 2.3.0: MIT,
https://github.com/modelcontextprotocol/python-sdk.
Python dependencies and their versions are listed in requirements-lock.txt;
their license metadata is installed alongside them in .venv/Lib/site-packages.
Rust dependencies are recorded in backend/Cargo.lock and retain their upstream licenses.
Microsoft runtime DLLs remain in the original official QymCAD runtime directory.

This is an independent integration, not an official QymCAD MCP release.
