"""Python extraction script sent to FreeCAD via JSON-RPC execute_python.

This script runs inside FreeCAD's interpreter with access to FreeCAD, Part,
PartDesign, Sketcher, and other FreeCAD modules. It extracts structured CAD
data and serialises it as JSON into the `result` variable.
"""

EXTRACTION_SCRIPT = r'''
import json
import FreeCAD

doc = FreeCAD.ActiveDocument
if doc is None:
    result = json.dumps({"error": "No active document"})
else:
    objects = []
    sketches = []
    materials = []
    bbox_global = None

    for obj in doc.Objects:
        entry = {
            "name": obj.Name,
            "label": obj.Label,
            "type": obj.TypeId,
        }

        # Extract shape properties if the object has a Shape
        if hasattr(obj, "Shape") and obj.Shape is not None:
            shape = obj.Shape
            entry["shape_type"] = shape.ShapeType
            entry["volume_mm3"] = round(shape.Volume, 4) if shape.Volume else None
            entry["surface_area_mm2"] = round(shape.Area, 4) if shape.Area else None

            # Bounding box
            bb = shape.BoundBox
            entry["bounding_box"] = {
                "x_min": round(bb.XMin, 4), "x_max": round(bb.XMax, 4),
                "y_min": round(bb.YMin, 4), "y_max": round(bb.YMax, 4),
                "z_min": round(bb.ZMin, 4), "z_max": round(bb.ZMax, 4),
            }

            # Compute overall bounding box
            if bbox_global is None:
                bbox_global = {
                    "x_min": bb.XMin, "x_max": bb.XMax,
                    "y_min": bb.YMin, "y_max": bb.YMax,
                    "z_min": bb.ZMin, "z_max": bb.ZMax,
                }
            else:
                bbox_global["x_min"] = min(bbox_global["x_min"], bb.XMin)
                bbox_global["x_max"] = max(bbox_global["x_max"], bb.XMax)
                bbox_global["y_min"] = min(bbox_global["y_min"], bb.YMin)
                bbox_global["y_max"] = max(bbox_global["y_max"], bb.YMax)
                bbox_global["z_min"] = min(bbox_global["z_min"], bb.ZMin)
                bbox_global["z_max"] = max(bbox_global["z_max"], bb.ZMax)

            # PartDesign feature-specific dimensions
            dimensions = {}
            for prop in ["Length", "Width", "Height", "Depth", "Radius", "Diameter", "Angle"]:
                if hasattr(obj, prop):
                    val = getattr(obj, prop)
                    # FreeCAD quantities have a Value attribute
                    if hasattr(val, "Value"):
                        val = val.Value
                    if isinstance(val, (int, float)):
                        dimensions[prop.lower()] = round(val, 4)
            if dimensions:
                entry["dimensions"] = dimensions

        # Determine parent body
        for parent in doc.Objects:
            if hasattr(parent, "Group") and obj in parent.Group:
                entry["parent"] = parent.Label
                break

        # Sketch extraction
        if obj.TypeId == "Sketcher::SketchObject":
            sketch_entry = {
                "name": obj.Name,
                "label": obj.Label,
                "constraint_count": obj.ConstraintCount,
                "constraints": [],
                "geometry": [],
            }

            for i in range(obj.ConstraintCount):
                c = obj.Constraints[i]
                constraint = {"type": c.Type}
                if hasattr(c, "Value") and c.Value != 0:
                    constraint["value"] = round(c.Value, 4)
                if hasattr(c, "First") and c.First >= 0:
                    constraint["first"] = c.First
                if hasattr(c, "Second") and c.Second >= 0:
                    constraint["second"] = c.Second
                sketch_entry["constraints"].append(constraint)

            for i in range(obj.GeometryCount):
                geo = obj.Geometry[i]
                geo_entry = {"type": type(geo).__name__}
                if hasattr(geo, "Radius"):
                    geo_entry["radius"] = round(geo.Radius, 4)
                if hasattr(geo, "Center"):
                    c = geo.Center
                    geo_entry["center"] = [round(c.x, 4), round(c.y, 4)]
                if hasattr(geo, "StartPoint") and hasattr(geo, "EndPoint"):
                    sp = geo.StartPoint
                    ep = geo.EndPoint
                    geo_entry["start"] = [round(sp.x, 4), round(sp.y, 4)]
                    geo_entry["end"] = [round(ep.x, 4), round(ep.y, 4)]
                sketch_entry["geometry"].append(geo_entry)

            sketches.append(sketch_entry)
        else:
            objects.append(entry)

        # Material extraction
        if hasattr(obj, "Material") and obj.Material:
            mat = obj.Material
            mat_name = mat.get("Name", "Unknown") if isinstance(mat, dict) else str(mat)
            materials.append({"body": obj.Label, "material": mat_name})

    # Round global bbox
    if bbox_global:
        bbox_global = {k: round(v, 4) for k, v in bbox_global.items()}

    output = {
        "document_name": doc.Name,
        "objects": objects,
        "sketches": sketches,
        "materials": materials,
        "bounding_box": bbox_global,
    }
    result = json.dumps(output)
'''
