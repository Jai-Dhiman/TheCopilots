"""TechDraw annotation script generator.

Generates FreeCAD Python scripts that create TechDraw pages with
GD&T callout annotations. Scripts are deterministic string templates
-- no model-generated code.
"""


def generate_techdraw_script(
    document_name: str,
    callouts: list[dict],
    datum_scheme: dict,
    features: dict,
) -> str:
    """Generate a FreeCAD Python script that creates a TechDraw page with GD&T annotations.

    The returned script, when executed inside FreeCAD's interpreter, will:
    1. Create a TechDraw::DrawPage with an A4 landscape template
    2. Add a TechDraw::DrawViewPart (front view of the active Body)
    3. Add TechDraw::DrawRichAnno for each GD&T callout
    4. Add datum triangle annotations for each datum in the scheme
    5. Recompute and return metadata

    Args:
        document_name: FreeCAD document name (e.g. "Unnamed").
        callouts: List of GDT callout dicts, each with at least
            "feature", "feature_control_frame", and "symbol_name".
        datum_scheme: Dict with "primary", "secondary", "tertiary" keys,
            each None or a dict with "datum" and "surface".
        features: Dict with feature info (used for positioning hints).

    Returns:
        A Python script string ready for FreecadClient.execute_python().
    """
    lines = [
        "import FreeCAD",
        "import TechDraw",
        "",
        f"doc = FreeCAD.getDocument({document_name!r})",
        "if doc is None:",
        f"    raise RuntimeError(\"Document '{{}}' not found\".format({document_name!r}))",
        "",
        "# --- Helper functions ---",
        "",
        "def _add_annotation(doc, page, fcf_text, feature_name, x, y):",
        '    anno_name = "GDT_" + feature_name.replace(" ", "_")',
        '    anno = doc.addObject("TechDraw::DrawRichAnno", anno_name)',
        "    anno.AnnoParent = page",
        "    anno.AnnoText = fcf_text",
        "    anno.X = x",
        "    anno.Y = y",
        "    return anno",
        "",
        "def _add_datum(doc, page, letter, surface, x, y):",
        '    datum_name = "Datum_" + letter',
        '    anno = doc.addObject("TechDraw::DrawRichAnno", datum_name)',
        "    anno.AnnoParent = page",
        '    anno.AnnoText = "[" + letter + "]"',
        "    anno.X = x",
        "    anno.Y = y",
        "    return anno",
        "",
        "# --- Create drawing page ---",
        "",
        'page = doc.addObject("TechDraw::DrawPage", "GDT_Drawing")',
        'template = doc.addObject("TechDraw::DrawSVGTemplate", "GDT_Template")',
        'template.Template = FreeCAD.getResourceDir() + "Mod/TechDraw/Templates/A4_LandscapeTD.svg"',
        "page.Template = template",
        "",
        "# --- Add part view ---",
        "",
        "body = None",
        "for obj in doc.Objects:",
        '    if obj.TypeId == "PartDesign::Body":',
        "        body = obj",
        "        break",
        "",
        'view = doc.addObject("TechDraw::DrawViewPart", "GDT_View")',
        "page.addView(view)",
        "if body is not None:",
        "    view.Source = [body]",
        "view.Direction = FreeCAD.Vector(0, 0, 1)",
        "view.Scale = 0.5",
        "view.X = 150.0",
        "view.Y = 150.0",
        "",
        "# --- Add GD&T callout annotations ---",
        "",
    ]

    # Add callout annotations
    for i, callout in enumerate(callouts):
        fcf = callout.get("feature_control_frame", "")
        feature_name = callout.get("feature", f"Feature_{i}")
        x_pos = 120.0
        y_pos = 60.0 + i * 30.0
        lines.append(
            f"_add_annotation(doc, page, {fcf!r}, {feature_name!r}, {x_pos}, {y_pos})"
        )

    lines.extend([
        "",
        "# --- Add datum annotations ---",
        "",
    ])

    # Add datum annotations
    datum_y = 200.0
    for level in ("primary", "secondary", "tertiary"):
        entry = datum_scheme.get(level)
        if entry is None:
            continue
        datum_letter = entry.get("datum", level[0].upper())
        surface = entry.get("surface", "")
        lines.append(
            f"_add_datum(doc, page, {datum_letter!r}, {surface!r}, 50.0, {datum_y})"
        )
        datum_y += 25.0

    lines.extend([
        "",
        "# --- Finalize ---",
        "",
        "doc.recompute()",
        'annotation_count = len([o for o in doc.Objects if o.TypeId == "TechDraw::DrawRichAnno"])',
        'result = {"page_name": "GDT_Drawing", "annotation_count": annotation_count}',
    ])

    return "\n".join(lines) + "\n"
