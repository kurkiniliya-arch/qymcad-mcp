# Validation of 0.2.0

Tested on Windows x64 with Rust 1.95, Python 3.12 and Open CASCADE 7.8.1.

Passing checks:

- 12 Python tests: native geometry, parameter changes, rollback, export, file boundaries,
  serialization, protocol compatibility, cancellation and stale desktop transactions.
- The desktop integration test through QymCAD `Session`: applying a real B-rep model,
  native undo/redo, rejection of stale and expired writes, shared keyboard history,
  and a rendered preview.
- A real visible desktop driven through MCP: opening a mounting plate, changing width
  from 50 to 60 mm, reading a screenshot through MCP, manually undoing in the CAD menu,
  and reading the restored 50 mm value from MCP. Saving, restarting the patched desktop,
  and reconnecting retained the model.
- `cargo check --workspace --all-targets`.
- Formatting of every workspace package, dependency-version consistency and the App-size guards.
- Applying the distributed patch to a fresh copy of the pinned source reproduces the modified files.

The complete upstream test/lint suite is **not green** in this environment. The broad
QymCAD test run completed with 1265 passing, 16 failing and 34 ignored tests; a dependency
declaration failure introduced by the adapter was corrected and its check passed separately.
Remaining reported failures include STEP/IGES assembly-tree expectations, sketch double-click,
tree dragging and source-scanning guards for help/keyboard/panels. The new transaction module
is explicitly classified as a non-panel because it draws no widgets. The full suite was not
rerun after those targeted corrections; do not interpret this package as a fully validated CAD release.

Clippy reports warnings in existing `qymcad-core` code, `gui/import_scale.rs` and existing
GUI tests with Rust 1.95. No warning in the added bridge modules was reported. Those unrelated
implementations were left unchanged. Native menu Undo and Session keyboard Undo were verified;
an injected Windows Ctrl+Z gesture did not trigger Undo in the test desktop's input environment.

This is an experimental integration. Linux/macOS, arbitrary external project versions,
all QymCAD tools and physical 3D printing are outside the verified scope.
