use qymcad_core::feature::{BasePlane, Purpose, SketchPlane, PLACE_IDENTITY};
use qymcad_core::model::{Id, Param, Project};
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::BTreeMap;

#[derive(Deserialize)]
#[serde(tag = "op", rename_all = "snake_case", deny_unknown_fields)]
pub enum Command {
    New {
        name: String,
    },
    Inspect,
    Part {
        name: String,
    },
    Primitive {
        name: String,
        part_id: Option<Id>,
        shape: Primitive,
    },
    Sketch {
        name: String,
        part_id: Option<Id>,
        plane: Plane,
        offset: f64,
        profile: Profile,
    },
    Extrude {
        sketch_id: Id,
        height: f64,
        mode: BooleanMode,
    },
    Revolve {
        sketch_id: Id,
        angle: f64,
        axis: u8,
    },
    Loft {
        sketch_ids: Vec<Id>,
        ruled: bool,
    },
    Fillet {
        body_id: Id,
        radius: f64,
        edge_ids: Vec<u32>,
    },
    Chamfer {
        body_id: Id,
        distance: f64,
        edge_ids: Vec<u32>,
    },
    Translate {
        body_id: Id,
        offset: Vector,
    },
    Parameters {
        values: BTreeMap<String, String>,
    },
    Dimension {
        feature_id: Id,
        key: String,
        expression: String,
    },
    Rename {
        node_id: Id,
        name: String,
    },
    Export {
        path: String,
        format: String,
        body_id: Option<Id>,
    },
}
#[derive(Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum Primitive {
    Box {
        size: Vector,
    },
    Cylinder {
        radius: f64,
        height: f64,
    },
    Sphere {
        radius: f64,
    },
    Cone {
        bottom_radius: f64,
        top_radius: f64,
        height: f64,
    },
    Torus {
        major_radius: f64,
        minor_radius: f64,
    },
}
#[derive(Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum Profile {
    Rectangle { origin: Point, size: Point },
    Circle { center: Point, radius: f64 },
    Polygon { points: Vec<Point> },
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Point {
    x: f64,
    y: f64,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Vector {
    x: f64,
    y: f64,
    z: f64,
}
#[derive(Deserialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum Plane {
    Xy,
    Xz,
    Yz,
}
#[derive(Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum BooleanMode {
    Add,
    Cut,
    Intersect,
}

fn positive(value: f64) -> Result<f64, String> {
    if value.is_finite() && (0.01..=10000.0).contains(&value) {
        Ok(value)
    } else {
        Err("A dimension must be between 0.01 and 10000 mm".into())
    }
}
fn activate_part(project: &mut Project, id: Option<Id>, name: &str) -> Result<Id, String> {
    let part = if let Some(id) = id {
        if !project.component_is_part(id) {
            return Err(format!("Part {id} not found"));
        }
        id
    } else {
        let root = project.ensure_root();
        project.set_active_component(Some(root));
        project.add_part(name)
    };
    project.set_active_component(Some(part));
    Ok(part)
}
fn activate_body(project: &mut Project, id: Id) -> Result<(), String> {
    if !project.bodies.iter().any(|b| b.id == id) {
        return Err(format!("Body {id} not found"));
    }
    if project.consumed_bodies().contains(&id) {
        return Err("Use the current, unconsumed body id".into());
    }
    let owner = project.body_owner(id).ok_or("Body has no owning part")?;
    activate_part(project, Some(owner), "")?;
    Ok(())
}
fn activate_sketch(project: &mut Project, id: Id) -> Result<Id, String> {
    let sketch = project
        .sketches
        .iter()
        .find(|s| s.id == id)
        .ok_or("Sketch not found")?;
    if sketch.contour_ids.is_empty() {
        return Err("Sketch has no closed contour".into());
    }
    let owner = project
        .sketch_owner(id)
        .ok_or("Sketch has no owning part")?;
    activate_part(project, Some(owner), "")
}
fn body_result(project: &mut Project, id: Id) -> Value {
    let body = project.finish_base_body(id, 1);
    json!({"feature_id": id, "body_id": body, "part_id": project.body_owner(body)})
}
pub fn apply(project: &mut Project, command: &Command) -> Result<Value, String> {
    match command {
        Command::New { name } => {
            *project = Project::default();
            let root = project.new_empty_document();
            if let Some(component) = project.components.iter_mut().find(|c| c.id == root) {
                component.name.clone_from(name);
            }
            Ok(json!({"root_id": root}))
        }
        Command::Inspect | Command::Export { .. } => Ok(json!({})),
        Command::Part { name } => Ok(json!({"part_id": activate_part(project, None, name)?})),
        Command::Primitive {
            name,
            part_id,
            shape,
        } => {
            activate_part(project, *part_id, name)?;
            let id = match shape {
                Primitive::Box { size } => {
                    project.add_box(positive(size.x)?, positive(size.y)?, positive(size.z)?)
                }
                Primitive::Cylinder { radius, height } => {
                    project.add_cylinder(positive(*radius)?, positive(*height)?)
                }
                Primitive::Sphere { radius } => project.add_sphere(positive(*radius)?),
                Primitive::Cone {
                    bottom_radius,
                    top_radius,
                    height,
                } => {
                    if !top_radius.is_finite() || *top_radius < 0.0 || *top_radius > 10000.0 {
                        return Err("Invalid top radius".into());
                    }
                    project.add_cone(positive(*bottom_radius)?, *top_radius, positive(*height)?)
                }
                Primitive::Torus {
                    major_radius,
                    minor_radius,
                } => {
                    if minor_radius >= major_radius {
                        return Err("Minor radius must be less than major radius".into());
                    }
                    project.add_torus(positive(*major_radius)?, positive(*minor_radius)?)
                }
            };
            project.rename_node(id, name);
            Ok(body_result(project, id))
        }
        Command::Sketch {
            name,
            part_id,
            plane,
            offset,
            profile,
        } => {
            let part = activate_part(project, *part_id, name)?;
            let si = project.new_sketch(name);
            let sid = project.sketches[si].id;
            project.add_sketch_node(sid, name);
            let base = match plane {
                Plane::Xy => BasePlane::XY,
                Plane::Xz => BasePlane::XZ,
                Plane::Yz => BasePlane::YZ,
            };
            project.sketches[si].plane = if *offset == 0.0 {
                SketchPlane::World(base)
            } else {
                SketchPlane::Datum(project.add_offset_plane(base, *offset))
            };
            match profile {
                Profile::Rectangle { origin, size } => {
                    project.add_rect_entity(
                        si,
                        origin.x,
                        origin.y,
                        origin.x + positive(size.x)?,
                        origin.y + positive(size.y)?,
                        Purpose::Real,
                    );
                }
                Profile::Circle { center, radius } => {
                    project.add_circle_entity(
                        si,
                        center.x,
                        center.y,
                        positive(*radius)?,
                        Purpose::Real,
                    );
                }
                Profile::Polygon { points } => {
                    if !(3..=256).contains(&points.len()) {
                        return Err("A polygon needs 3 to 256 vertices".into());
                    }
                    for (a, b) in points
                        .iter()
                        .zip(points.iter().cycle().skip(1))
                        .take(points.len())
                    {
                        project.add_line_entity(si, a.x, a.y, b.x, b.y, Purpose::Real);
                    }
                }
            }
            project.regen_sketch(si);
            if project.sketches[si].contour_ids.is_empty() {
                return Err("Profile did not form a closed contour".into());
            }
            Ok(json!({"sketch_id": sid, "part_id": part}))
        }
        Command::Extrude {
            sketch_id,
            height,
            mode,
        } => {
            positive(*height)?;
            let owner = activate_sketch(project, *sketch_id)?;
            let id = match mode {
                BooleanMode::Add => {
                    let id = project.add_extrude(*sketch_id, *height);
                    return Ok(body_result(project, id));
                }
                BooleanMode::Cut | BooleanMode::Intersect => {
                    let source = project
                        .active_body(owner)
                        .ok_or("No body in this part to cut or intersect")?;
                    let operation = if matches!(mode, BooleanMode::Cut) {
                        0
                    } else {
                        2
                    };
                    project.add_combine(source, *sketch_id, *height, operation)
                }
            };
            Ok(json!({"feature_id": id, "body_id": id}))
        }
        Command::Revolve {
            sketch_id,
            angle,
            axis,
        } => {
            activate_sketch(project, *sketch_id)?;
            if *axis > 1 || !angle.is_finite() || *angle <= 0.0 || *angle > 360.0 {
                return Err(
                    "Axis must be 0 (X) or 1 (Y); angle must be in (0, 360] degrees".into(),
                );
            }
            let id = project.add_revolve(*sketch_id, *axis, *angle);
            Ok(body_result(project, id))
        }
        Command::Loft { sketch_ids, ruled } => {
            if !(2..=16).contains(&sketch_ids.len()) {
                return Err("Loft needs 2 to 16 sketches".into());
            }
            let owner = activate_sketch(project, sketch_ids[0])?;
            for id in sketch_ids {
                if activate_sketch(project, *id)? != owner {
                    return Err("Loft sketches must belong to the same part".into());
                }
            }
            let contours = sketch_ids
                .iter()
                .map(|id| {
                    project
                        .sketches
                        .iter()
                        .find(|s| s.id == *id)
                        .unwrap()
                        .contour_ids[0]
                })
                .collect();
            let id = project.add_loft(sketch_ids.clone(), contours, *ruled, 0, 1, false);
            Ok(body_result(project, id))
        }
        Command::Fillet {
            body_id,
            radius,
            edge_ids,
        } => {
            activate_body(project, *body_id)?;
            let id = project.add_fillet(*body_id, positive(*radius)?, edge_ids.clone());
            Ok(json!({"feature_id": id, "body_id": id}))
        }
        Command::Chamfer {
            body_id,
            distance,
            edge_ids,
        } => {
            activate_body(project, *body_id)?;
            let id = project.add_chamfer(*body_id, positive(*distance)?, edge_ids.clone());
            Ok(json!({"feature_id": id, "body_id": id}))
        }
        Command::Translate { body_id, offset } => {
            activate_body(project, *body_id)?;
            let mut matrix = PLACE_IDENTITY;
            matrix[3] = offset.x;
            matrix[7] = offset.y;
            matrix[11] = offset.z;
            let id = project.add_move(*body_id, matrix);
            Ok(json!({"feature_id": id, "body_id": id}))
        }
        Command::Parameters { values } => {
            for (name, expression) in values {
                if name.is_empty()
                    || !name.chars().all(|c| c.is_ascii_alphanumeric() || c == '_')
                    || name.starts_with(|c: char| c.is_ascii_digit())
                {
                    return Err(
                        "Parameter names must be identifiers such as width or petal_count".into(),
                    );
                }
                if let Some(parameter) = project.parameters.iter_mut().find(|p| p.name == *name) {
                    parameter.expr.clone_from(expression);
                } else {
                    project.parameters.push(Param {
                        name: name.clone(),
                        expr: expression.clone(),
                        value: 0.0,
                    });
                }
            }
            project.mark_param_dependents_dirty();
            Ok(json!({"updated": values.keys().collect::<Vec<_>>()}))
        }
        Command::Dimension {
            feature_id,
            key,
            expression,
        } => {
            let node = project
                .timeline
                .iter()
                .find(|n| n.id == *feature_id)
                .ok_or("Feature not found")?;
            if node.kind.dim(key).is_none() {
                return Err("Unknown dimension key; inspect the feature first".into());
            }
            let value = project
                .eval_expr(expression)
                .map_err(|e| format!("Invalid dimension expression: {e:?}"))?;
            if !value.is_finite() || value.abs() > 10000.0 {
                return Err("Dimension outside supported range".into());
            }
            project.set_feat_dim(*feature_id, key, expression.clone());
            Ok(json!({"feature_id": feature_id, "key": key, "value": value}))
        }
        Command::Rename { node_id, name } => {
            if !project.rename_node(*node_id, name) {
                return Err("Node not found".into());
            }
            Ok(json!({"node_id": node_id, "name": name}))
        }
    }
}
