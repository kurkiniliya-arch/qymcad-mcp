Experimental Windows x64 integration for QymCAD and MCP clients.

- Two-way access to the document in an actual desktop window, including unsaved manual edits.
- Native modeling with 21 tools, model inspection, STL/STEP export and editable QCAD files.
- Revision-checked transactions, shared undo history, screenshots and view fitting.
- The desktop remains open when the MCP client disconnects.
- Includes the matching desktop executable, OCCT runtime, backend, original pinned source,
  desktop patch and installation/build instructions. Python 3.12+ is required.

Extract the ZIP and run `setup.ps1`, then `open_gui.ps1`. Use `install_codex.ps1` for Codex,
or the generated `mcp-config.json` in another MCP client.

The MCP tests and live-window integration scenario passed. The complete QymCAD suite has
remaining failures in this environment, and Clippy reports warnings in existing CAD code.
See `VALIDATION.md` for the exact scope. This is a prerelease, not a fully validated CAD distribution.

AGPL-3.0-or-later. Independent integration based on QymCAD revision
`3ee0d1383accbf9cf34ad0bf8403215f9885dcbe`; not an official QymCAD release.
