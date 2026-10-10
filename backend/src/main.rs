//! One isolated CAD transaction. Response files keep kernel logs out of MCP stdout.
mod operations;
use qymcad_core::feature::FeatureKind;
use qymcad_core::model::Project;
use qymcad_kernel::{kernel_gate, OcctKernel, Shape};
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::HashMap;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    input: Option<String>,
    output: Option<String>,
    command: operations::Command,
}

fn regenerate(project: &mut Project, kernel: &OcctKernel) -> Result<(), String> {
    let errors = project.eval_parameters();
    if !errors.is_empty() {
        return Err(format!("Invalid parameter expressions: {errors:?}"));
    }
    project.mark_all_dirty();
    let report = project.regenerate(kernel);
    if report.cancelled || !report.errors.is_empty() {
        return Err(format!("Geometry rebuild failed: {:?}", report.errors));
    }
    for (body, faces) in report.built {
        project.set_body_faces(body, faces);
    }
    for (id, shape) in kernel.shapes.borrow().iter() {
        if !shape.is_valid() {
            return Err(format!("Invalid B-rep for body {id}"));
        }
    }
    Ok(())
}

fn inspect(project: &Project, kernel: &OcctKernel) -> Value {
    let consumed = project.consumed_bodies();
    let vars = project.param_map();
    let shapes = kernel.shapes.borrow();
    let bodies: Vec<Value> = project
        .bodies
        .iter()
        .map(|body| {
            let shape = shapes.get(&body.id);
            json!({"id": body.id, "part_id": project.body_owner(body.id),
            "consumed": consumed.contains(&body.id), "triangles": body.mesh.tris.len(),
            "volume_mm3": shape.map(Shape::volume), "bbox_mm": shape.and_then(Shape::bbox),
            "valid_brep": shape.map(Shape::is_valid),
            "edge_ids": shape.map(|s| s.edges_with_ids().1),
            "faces": body.faces.iter().map(|f| json!({"id": f.id, "area_mm2": f.area,
                "center": f.centroid, "normal": f.normal})).collect::<Vec<_>>()})
        })
        .collect();
    let features: Vec<Value> = project
        .timeline
        .iter()
        .map(|node| {
            let dimensions: Vec<Value> = node
                .kind
                .dims()
                .into_iter()
                .map(|(key, stored)| {
                    json!({
            "key": key, "expression": project.feat_dim(node.id, key),
            "value": project.feat_dim_value(node.id, key, stored, &vars)})
                })
                .collect();
            json!({"id": node.id, "name": node.name, "part_id": node.parent,
            "recipe": node.kind, "dimensions": dimensions, "suppressed": node.suppressed})
        })
        .collect();
    json!({"units": "mm", "active_part_id": project.active_component,
        "components": project.components, "parameters": project.parameters,
        "features": features, "bodies": bodies,
        "sketches": project.sketches.iter().map(|s| json!({"id": s.id, "name": s.name,
            "part_id": project.sketch_owner(s.id), "contour_ids": s.contour_ids,
            "plane": s.plane, "entity_count": s.entities.len()})).collect::<Vec<_>>()})
}

fn run(request: Request) -> Result<Value, String> {
    let _gate = kernel_gate();
    let mut shapes = HashMap::new();
    let mut project = if let Some(path) = &request.input {
        let loaded = qymcad_io::load_project_with_brep(path)?;
        for (id, bytes) in loaded.breps {
            if let Some(shape) = Shape::from_brep_bytes(&bytes) {
                shapes.insert(id, shape);
            }
        }
        for node in &loaded.project.timeline {
            if let FeatureKind::Import { body, .. } = node.kind {
                if !shapes.contains_key(&body) {
                    return Err(format!("Imported body {body} has no cached B-rep. Open and save it in the matching QymCAD version first."));
                }
            }
        }
        loaded.project
    } else {
        Project::default()
    };
    let kernel = OcctKernel {
        shapes: std::cell::RefCell::new(shapes),
        quality_k: project.geom_quality.deflection_k(),
        ..Default::default()
    };
    if request.input.is_some() {
        regenerate(&mut project, &kernel)?;
    }
    let outcome = operations::apply(&mut project, &request.command)?;
    regenerate(&mut project, &kernel)?;
    if let operations::Command::Export {
        path,
        format,
        body_id,
    } = &request.command
    {
        let consumed = project.consumed_bodies();
        let selected: Vec<_> = project
            .bodies
            .iter()
            .filter(|b| match body_id {
                Some(id) => b.id == *id,
                None => !consumed.contains(&b.id),
            })
            .collect();
        if selected.is_empty() {
            return Err("No bodies selected for export".into());
        }
        match format.as_str() {
            "stl" => {
                let meshes: Vec<_> = selected.iter().map(|b| b.mesh.clone()).collect();
                qymcad_io::export_stl(&meshes, path)?;
            }
            "step" => {
                let cache = kernel.shapes.borrow();
                let mut exact = Vec::new();
                for body in &selected {
                    let shape = cache
                        .get(&body.id)
                        .ok_or("Selected body has no exact B-rep")?;
                    exact.push((shape, qymcad_core::feature::PLACE_IDENTITY));
                }
                qymcad_kernel::write_step(&exact, path)?;
            }
            _ => return Err("Supported export formats: stl, step".into()),
        }
    }
    if let Some(path) = request.output {
        let cache = kernel.shapes.borrow();
        let mut breps = Vec::new();
        for body in &project.bodies {
            if let Some(shape) = cache.get(&body.id) {
                let bytes = shape.to_brep_bytes().ok_or("Could not serialize B-rep")?;
                breps.push((body.id, bytes));
            }
        }
        qymcad_io::save_project_with_brep(&project, &path, &breps)?;
    }
    Ok(json!({"outcome": outcome, "document": inspect(&project, &kernel)}))
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 3 {
        eprintln!("Usage: qymcad-mcp-backend REQUEST.json RESPONSE.json");
        std::process::exit(2);
    }
    let result = std::fs::read(&args[1])
        .map_err(|e| e.to_string())
        .and_then(|bytes| serde_json::from_slice::<Request>(&bytes).map_err(|e| e.to_string()))
        .and_then(run);
    let response = match result {
        Ok(value) => json!({"ok": true, "result": value}),
        Err(error) => json!({"ok": false, "error": error}),
    };
    if let Err(error) = std::fs::write(
        &args[2],
        serde_json::to_vec(&response).expect("JSON response"),
    ) {
        eprintln!("Cannot write response: {error}");
        std::process::exit(1);
    }
}
