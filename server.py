"""Local stdio MCP server for QymCAD. No network listener or arbitrary code tool."""
import argparse
import asyncio
from pathlib import Path
from typing import Annotated, Literal, Any
from pydantic import Field
from mcp.server import MCPServer
from mcp.server.mcpserver.utilities.types import Image
from mcp_types import ToolAnnotations

from bridge import BASE, REVISION, Bridge
from live import LiveBridge
from schemas import Coordinate, Expression, Name, NodeId, Primitive, Profile, Size, Vector

HELP = """QymCAD native parametric modeling, in millimetres. Inspect the existing document first.
In headless mode create/open a document before modeling. In live mode the desktop document is
already available; create/open replaces it with an undoable action, so use those only when intended.
Each create_primitive without part_id creates a separate part. Within one part, material is joined.
Sketches support rectangle, circle and closed polygon, on XY/XZ/YZ or an offset plane.
Use extrude(mode='cut') for holes. Loft joins the first closed contour of each section in one part.
Inspect returns stable ids, dimension keys, evaluated values, recipes, volumes and bounding boxes.
Set dimensions with expressions and define named parameters. Every mutation rebuilds the actual
QymCAD/OpenCASCADE model and is committed only on success. Headless undo keeps 20 states;
live undo uses the desktop's shared history and its configured limit.
Save .qcad to keep editable history. Export STL/STEP for one body or all unconsumed bodies.
Files stay inside the configured workspace; overwrite must be explicit.
With --live, tools edit the document in the linked desktop window. Manual edits are read before
each command. Concurrent document changes reject the commit; inspect and retry. Finish active
dialogs/sketch edits first. Undo shares the desktop history. Save writes a copy; Ctrl+S saves the
window's current file. Without --live the document is private to this MCP connection.
Imported projects need cached B-reps and a compatible QymCAD format. The source revision is pinned.
In headless mode save before disconnecting; in live mode the desktop retains its document."""

READ = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)
EDIT = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False)
WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=True, open_world_hint=False)

def create_server(bridge: Bridge):
    server = MCPServer("qymcad", version="0.2.0", instructions=HELP, log_level="WARNING")

    @server.resource("qymcad://help")
    def help_resource() -> str:
        return HELP

    @server.tool(annotations=READ)
    async def qymcad_status() -> dict[str, Any]:
        """Return capabilities, workspace, backend availability and pinned source revision."""
        return {"backend_available": bridge.backend.is_file(), "workspace": str(bridge.workspace),
                "qymcad_revision": REVISION, "units": "mm", "transport": "stdio",
                "gui_live_sync": isinstance(bridge, LiveBridge),
                "gui": await bridge.status() if isinstance(bridge, LiveBridge) else None,
                "has_document": bridge.current.is_file(), "help": HELP}

    @server.tool(annotations=EDIT)
    async def qymcad_create_document(name: Name = "New project") -> dict[str, Any]:
        """Start a new native project. Previous state remains available through undo."""
        return await bridge.change({"op": "new", "name": name}, fresh=True)

    @server.tool(annotations=EDIT)
    async def qymcad_open_project(file: str) -> dict[str, Any]:
        """Open a workspace .qcad; in live mode it becomes the current document of the window."""
        source = bridge.path(file, {".qcad"}, reading=True)
        return await bridge.change({"op": "inspect"}, source=source, fresh=True)

    @server.tool(annotations=READ)
    async def qymcad_inspect() -> dict[str, Any]:
        """Read model tree, sketch ids, body ids, dimensions, volume and bounding boxes."""
        return await bridge.inspect()

    @server.tool(annotations=EDIT)
    async def qymcad_create_part(name: Name) -> dict[str, Any]:
        """Create an empty part under the root assembly."""
        return await bridge.change({"op": "part", "name": name})

    @server.tool(annotations=EDIT)
    async def qymcad_create_primitive(shape: Primitive, name: Name = "Primitive",
                                      part_id: NodeId | None = None) -> dict[str, Any]:
        """Create box, cylinder, sphere, cone or torus. Supply part_id to join an existing part."""
        return await bridge.change({"op": "primitive", "shape": shape.model_dump(),
                                    "name": name, "part_id": part_id})

    @server.tool(annotations=EDIT)
    async def qymcad_create_sketch(profile: Profile, name: Name = "Sketch",
                                   part_id: NodeId | None = None,
                                   plane: Literal["XY", "XZ", "YZ"] = "XY",
                                   offset: Coordinate = 0) -> dict[str, Any]:
        """Create an editable rectangle, circle or closed polygon on a base/offset plane."""
        return await bridge.change({"op": "sketch", "profile": profile.model_dump(), "name": name,
                                    "part_id": part_id, "plane": plane, "offset": offset})

    @server.tool(annotations=EDIT)
    async def qymcad_extrude(sketch_id: NodeId, height: Size,
                            mode: Literal["add", "cut", "intersect"] = "add") -> dict[str, Any]:
        """Extrude along the sketch normal. Cut/intersect acts on the current body of that part."""
        return await bridge.change({"op": "extrude", "sketch_id": sketch_id, "height": height, "mode": mode})

    @server.tool(annotations=EDIT)
    async def qymcad_revolve(sketch_id: NodeId,
                             angle: Annotated[float, Field(gt=0, le=360, allow_inf_nan=False)] = 360,
                             axis: Literal[0, 1] = 1) -> dict[str, Any]:
        """Revolve a closed sketch about its local X (0) or Y (1) axis, in degrees."""
        return await bridge.change({"op": "revolve", "sketch_id": sketch_id, "angle": angle, "axis": axis})

    @server.tool(annotations=EDIT)
    async def qymcad_loft(sketch_ids: Annotated[list[NodeId], Field(min_length=2, max_length=16)],
                         ruled: bool = False) -> dict[str, Any]:
        """Build a solid through ordered sketch sections belonging to the same part."""
        return await bridge.change({"op": "loft", "sketch_ids": sketch_ids, "ruled": ruled})

    @server.tool(annotations=EDIT)
    async def qymcad_fillet(body_id: NodeId, radius: Size,
                            edge_ids: list[int] | None = None) -> dict[str, Any]:
        """Round edges of a current body. Omit edge_ids to round all edges."""
        return await bridge.change({"op": "fillet", "body_id": body_id, "radius": radius,
                                    "edge_ids": edge_ids or []})

    @server.tool(annotations=EDIT)
    async def qymcad_chamfer(body_id: NodeId, distance: Size,
                             edge_ids: list[int] | None = None) -> dict[str, Any]:
        """Chamfer edges of a current body. Omit edge_ids for all edges."""
        return await bridge.change({"op": "chamfer", "body_id": body_id, "distance": distance,
                                    "edge_ids": edge_ids or []})

    @server.tool(annotations=EDIT)
    async def qymcad_translate(body_id: NodeId, offset: Vector) -> dict[str, Any]:
        """Move a current body by an XYZ offset, preserving the operation in its history."""
        return await bridge.change({"op": "translate", "body_id": body_id, "offset": offset.model_dump()})

    @server.tool(annotations=EDIT)
    async def qymcad_set_parameters(values: dict[Name, Expression]) -> dict[str, Any]:
        """Set named expressions such as width=40, height=width/2; rebuild dependent features."""
        return await bridge.change({"op": "parameters", "values": values})

    @server.tool(annotations=EDIT)
    async def qymcad_set_dimension(feature_id: NodeId, key: Name, expression: Expression) -> dict[str, Any]:
        """Edit a feature dimension using a number or expression. Inspect first for allowed keys."""
        return await bridge.change({"op": "dimension", "feature_id": feature_id,
                                    "key": key, "expression": expression})

    @server.tool(annotations=EDIT)
    async def qymcad_rename(node_id: NodeId, name: Name) -> dict[str, Any]:
        """Rename a node in the native project tree."""
        return await bridge.change({"op": "rename", "node_id": node_id, "name": name})

    @server.tool(annotations=EDIT)
    async def qymcad_undo() -> dict[str, Any]:
        """Undo the last action: shared desktop history in live mode, 20 session states in headless mode."""
        return await bridge.undo()

    @server.tool(annotations=WRITE)
    async def qymcad_save_project(file: str, overwrite: bool = False) -> dict[str, Any]:
        """Save an editable .qcad copy with B-reps. This does not mark the desktop document as saved."""
        return await bridge.save(file, overwrite)

    @server.tool(annotations=WRITE)
    async def qymcad_export(file: str, format: Literal["stl", "step"],
                            body_id: NodeId | None = None, overwrite: bool = False) -> dict[str, Any]:
        """Export a body, or all unconsumed bodies, in mm. Existing files require overwrite=true."""
        return await bridge.export(file, format, body_id, overwrite)

    if isinstance(bridge, LiveBridge):
        @server.tool(annotations=READ)
        async def qymcad_screenshot() -> Image:
            """Return an actual image of the linked CAD window, including its model and panels."""
            return Image(data=await bridge.screenshot(), format="png")

        @server.tool(annotations=EDIT)
        async def qymcad_fit_view() -> dict[str, Any]:
            """Frame the current model in the linked desktop viewport."""
            return await bridge.fit()

    return server

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=BASE / "models")
    parser.add_argument("--backend", type=Path)
    parser.add_argument("--live", action="store_true", help="Synchronize with the linked desktop window")
    parser.add_argument("--endpoint", type=Path, help="Attach to an existing private live directory")
    args = parser.parse_args()
    bridge = LiveBridge(args.workspace, args.backend, endpoint=args.endpoint) if args.live else Bridge(args.workspace, args.backend)
    try:
        create_server(bridge).run(transport="stdio")
    finally:
        bridge.close()

if __name__ == "__main__":
    main()
