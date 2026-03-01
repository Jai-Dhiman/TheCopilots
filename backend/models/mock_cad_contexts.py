"""Mock CAD context data for demo mode.

When the FreeCAD RPC server is unavailable, these functions provide
realistic structured data matching what the extraction script would
return for known demo models. Invisible to the audience -- looks
like live CAD extraction.
"""

import math


def get_desk_mock() -> dict:
    """Return mock extraction data for the table model.

    Model: rectangular tabletop (700x350x50mm) with 4 holes at corners
    for press-fit legs. Each leg is 100mm diameter x 700mm tall, with a
    cylindrical boss (60mm diameter x 50mm tall) at the top that press-fits
    into the tabletop holes.
    Document "Table_Model", Assembly_1.
    """
    # Tabletop dimensions
    top_length = 700.0
    top_width = 350.0
    top_height = 50.0

    # Leg dimensions
    leg_diameter = 100.0
    leg_radius = leg_diameter / 2
    leg_height = 700.0
    leg_volume = math.pi * leg_radius**2 * leg_height
    leg_lateral_area = 2 * math.pi * leg_radius * leg_height
    leg_end_area = math.pi * leg_radius**2
    leg_surface_area = leg_lateral_area + 2 * leg_end_area

    # Press-fit boss dimensions (top of each leg)
    boss_diameter = 60.0
    boss_radius = boss_diameter / 2
    boss_height = 50.0
    boss_volume = math.pi * boss_radius**2 * boss_height
    boss_lateral_area = 2 * math.pi * boss_radius * boss_height
    boss_end_area = math.pi * boss_radius**2
    boss_surface_area = boss_lateral_area + 2 * boss_end_area

    # Hole dimensions in tabletop (matches boss for press fit)
    hole_diameter = 60.0
    hole_radius = hole_diameter / 2
    hole_volume = math.pi * hole_radius**2 * top_height

    # Corner positions: inset by leg radius from edges
    corner_inset_x = leg_radius
    corner_inset_y = leg_radius
    leg_positions = {
        "Leg_FL": {"x": corner_inset_x, "y": corner_inset_y},
        "Leg_FR": {"x": top_length - corner_inset_x, "y": corner_inset_y},
        "Leg_BL": {"x": corner_inset_x, "y": top_width - corner_inset_y},
        "Leg_BR": {"x": top_length - corner_inset_x, "y": top_width - corner_inset_y},
    }

    # Tabletop volume accounts for 4 holes
    tabletop_solid_volume = top_length * top_width * top_height - 4 * hole_volume

    objects = [
        {
            "name": "Tabletop",
            "label": "Tabletop",
            "type": "PartDesign::Pad",
            "shape_type": "Solid",
            "volume_mm3": round(tabletop_solid_volume, 1),
            "surface_area_mm2": round(
                2 * (top_length * top_width + top_length * top_height + top_width * top_height),
                1,
            ),
            "bounding_box": {
                "x_min": 0.0, "x_max": top_length,
                "y_min": 0.0, "y_max": top_width,
                "z_min": leg_height, "z_max": leg_height + top_height,
            },
            "dimensions": {
                "length": top_length,
                "width": top_width,
                "height": top_height,
            },
            "parent": "Body",
        },
    ]

    # Add holes in tabletop
    for name, pos in leg_positions.items():
        hole_name = f"Hole_{name.split('_')[1]}"
        objects.append({
            "name": hole_name,
            "label": hole_name,
            "type": "PartDesign::Pocket",
            "shape_type": "Hole",
            "volume_mm3": round(hole_volume, 1),
            "surface_area_mm2": round(
                2 * math.pi * hole_radius * top_height + 2 * math.pi * hole_radius**2,
                1,
            ),
            "bounding_box": {
                "x_min": pos["x"] - hole_radius,
                "x_max": pos["x"] + hole_radius,
                "y_min": pos["y"] - hole_radius,
                "y_max": pos["y"] + hole_radius,
                "z_min": leg_height,
                "z_max": leg_height + top_height,
            },
            "dimensions": {
                "diameter": hole_diameter,
                "depth": top_height,
            },
            "parent": "Tabletop",
        })

    # Add legs
    for name, pos in leg_positions.items():
        objects.append({
            "name": name,
            "label": name,
            "type": "PartDesign::Pad",
            "shape_type": "Solid",
            "volume_mm3": round(leg_volume, 1),
            "surface_area_mm2": round(leg_surface_area, 1),
            "bounding_box": {
                "x_min": pos["x"] - leg_radius,
                "x_max": pos["x"] + leg_radius,
                "y_min": pos["y"] - leg_radius,
                "y_max": pos["y"] + leg_radius,
                "z_min": 0.0,
                "z_max": leg_height,
            },
            "dimensions": {
                "diameter": leg_diameter,
                "height": leg_height,
            },
            "parent": "Body",
        })

    # Add press-fit bosses on top of each leg
    for name, pos in leg_positions.items():
        boss_name = f"Boss_{name.split('_')[1]}"
        objects.append({
            "name": boss_name,
            "label": boss_name,
            "type": "PartDesign::Pad",
            "shape_type": "Solid",
            "volume_mm3": round(boss_volume, 1),
            "surface_area_mm2": round(boss_surface_area, 1),
            "bounding_box": {
                "x_min": pos["x"] - boss_radius,
                "x_max": pos["x"] + boss_radius,
                "y_min": pos["y"] - boss_radius,
                "y_max": pos["y"] + boss_radius,
                "z_min": leg_height,
                "z_max": leg_height + boss_height,
            },
            "dimensions": {
                "diameter": boss_diameter,
                "height": boss_height,
            },
            "parent": name,
        })

    sketches = [
        {
            "name": "Sketch_Tabletop",
            "label": "Sketch_Tabletop",
            "constraint_count": 4,
            "constraints": [
                {"type": "Distance", "value": top_length, "first": 0},
                {"type": "Distance", "value": top_width, "first": 1},
                {"type": "Coincident", "first": 0, "second": 1},
                {"type": "Coincident", "first": 2, "second": 3},
            ],
            "geometry": [
                {"type": "Line", "start": [0, 0], "end": [top_length, 0]},
                {"type": "Line", "start": [top_length, 0], "end": [top_length, top_width]},
                {"type": "Line", "start": [top_length, top_width], "end": [0, top_width]},
                {"type": "Line", "start": [0, top_width], "end": [0, 0]},
            ],
        },
        {
            "name": "Sketch_Hole",
            "label": "Sketch_Hole",
            "constraint_count": 1,
            "constraints": [
                {"type": "Radius", "value": hole_radius, "first": 0},
            ],
            "geometry": [
                {"type": "Circle", "radius": hole_radius, "center": [corner_inset_x, corner_inset_y]},
            ],
        },
        {
            "name": "Sketch_Leg",
            "label": "Sketch_Leg",
            "constraint_count": 1,
            "constraints": [
                {"type": "Radius", "value": leg_radius, "first": 0},
            ],
            "geometry": [
                {"type": "Circle", "radius": leg_radius, "center": [corner_inset_x, corner_inset_y]},
            ],
        },
        {
            "name": "Sketch_Boss",
            "label": "Sketch_Boss",
            "constraint_count": 1,
            "constraints": [
                {"type": "Radius", "value": boss_radius, "first": 0},
            ],
            "geometry": [
                {"type": "Circle", "radius": boss_radius, "center": [corner_inset_x, corner_inset_y]},
            ],
        },
    ]

    return {
        "document_name": "Table_Model",
        "objects": objects,
        "sketches": sketches,
        "materials": [{"body": "Body", "material": "Birch Plywood"}],
        "bounding_box": {
            "x_min": 0.0, "x_max": top_length,
            "y_min": 0.0, "y_max": top_width,
            "z_min": 0.0, "z_max": leg_height + top_height,
        },
    }
