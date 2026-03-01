"""Mock CAD context data for demo mode.

When the FreeCAD RPC server is unavailable, these functions provide
realistic structured data matching what the extraction script would
return for known demo models. Invisible to the audience -- looks
like live CAD extraction.
"""

import math


def get_desk_mock() -> dict:
    """Return mock extraction data for the desk model.

    Model: rectangular tabletop (600x400x12mm) + 4 cylindrical legs
    (30mm diameter x 388mm height), positioned at corners inset ~40mm.
    Document "Unnamed", Assembly_1.
    """
    leg_radius = 15.0
    leg_height = 388.0
    leg_volume = math.pi * leg_radius**2 * leg_height
    leg_lateral_area = 2 * math.pi * leg_radius * leg_height
    leg_end_area = math.pi * leg_radius**2
    leg_surface_area = leg_lateral_area + 2 * leg_end_area

    # Corner positions: inset 40mm from edges
    leg_positions = {
        "Leg_FL": {"x": 40.0, "y": 40.0},
        "Leg_FR": {"x": 560.0, "y": 40.0},
        "Leg_BL": {"x": 40.0, "y": 360.0},
        "Leg_BR": {"x": 560.0, "y": 360.0},
    }

    objects = [
        {
            "name": "Tabletop",
            "label": "Tabletop",
            "type": "PartDesign::Pad",
            "shape_type": "Solid",
            "volume_mm3": 600.0 * 400.0 * 12.0,
            "surface_area_mm2": 2 * (600.0 * 400.0 + 600.0 * 12.0 + 400.0 * 12.0),
            "bounding_box": {
                "x_min": 0.0, "x_max": 600.0,
                "y_min": 0.0, "y_max": 400.0,
                "z_min": 388.0, "z_max": 400.0,
            },
            "dimensions": {"length": 600.0, "width": 400.0, "height": 12.0},
            "parent": "Body",
        },
    ]

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
                "diameter": leg_radius * 2,
                "height": leg_height,
            },
            "parent": "Body",
        })

    sketches = [
        {
            "name": "Sketch_Tabletop",
            "label": "Sketch_Tabletop",
            "constraint_count": 4,
            "constraints": [
                {"type": "Distance", "value": 600.0, "first": 0},
                {"type": "Distance", "value": 400.0, "first": 1},
                {"type": "Coincident", "first": 0, "second": 1},
                {"type": "Coincident", "first": 2, "second": 3},
            ],
            "geometry": [
                {"type": "Line", "start": [0, 0], "end": [600, 0]},
                {"type": "Line", "start": [600, 0], "end": [600, 400]},
                {"type": "Line", "start": [600, 400], "end": [0, 400]},
                {"type": "Line", "start": [0, 400], "end": [0, 0]},
            ],
        },
        {
            "name": "Sketch_Leg",
            "label": "Sketch_Leg",
            "constraint_count": 1,
            "constraints": [
                {"type": "Radius", "value": 15.0, "first": 0},
            ],
            "geometry": [
                {"type": "Circle", "radius": 15.0, "center": [40, 40]},
            ],
        },
    ]

    return {
        "document_name": "Unnamed",
        "objects": objects,
        "sketches": sketches,
        "materials": [{"body": "Body", "material": "Birch Plywood"}],
        "bounding_box": {
            "x_min": 0.0, "x_max": 600.0,
            "y_min": 0.0, "y_max": 400.0,
            "z_min": 0.0, "z_max": 400.0,
        },
    }
