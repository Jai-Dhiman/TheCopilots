"""Seed SQLite database from JSON standards files.

Reads data/standards/*.json and creates data/brain.db with:
- geometric_characteristics (14 rows + FTS5 index)
- tolerance_tables (flattened: one row per process/material/characteristic)
- material_properties (12 rows)
- datum_patterns (7 rows)

Idempotent: drops and recreates all tables on each run.
"""

import json
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STANDARDS_DIR = BASE_DIR / "data" / "standards"
DB_PATH = BASE_DIR / "data" / "brain.db"

REQUIRED_FILES = [
    "asme_y14_5.json",
    "tolerance_tables.json",
    "material_properties.json",
    "datum_patterns.json",
]

# Tolerance table keys that are NOT geometric characteristics
TOLERANCE_META_KEYS = {"surface_finish_ra_um", "notes"}


def load_json(filename: str) -> dict:
    path = STANDARDS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        DROP TABLE IF EXISTS characteristics_fts;
        DROP TABLE IF EXISTS geometric_characteristics;
        DROP TABLE IF EXISTS tolerance_tables;
        DROP TABLE IF EXISTS material_properties;
        DROP TABLE IF EXISTS datum_patterns;

        CREATE TABLE geometric_characteristics (
            id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            asme_section TEXT,
            datum_required BOOLEAN NOT NULL,
            datum_optional BOOLEAN DEFAULT FALSE,
            applicable_modifiers TEXT,
            applicable_features TEXT,
            tolerance_zone TEXT,
            rules TEXT,
            when_to_use TEXT,
            when_not_to_use TEXT,
            common_mistakes TEXT,
            example_callout TEXT,
            prefer_instead TEXT,
            deprecation_note TEXT
        );

        CREATE TABLE tolerance_tables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            process TEXT NOT NULL,
            material TEXT NOT NULL,
            characteristic TEXT NOT NULL,
            min_mm REAL NOT NULL,
            max_mm REAL NOT NULL,
            notes TEXT,
            UNIQUE(process, material, characteristic)
        );

        CREATE TABLE material_properties (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            common_processes TEXT,
            machinability TEXT,
            thermal_expansion_ppm_c REAL,
            density_g_cm3 REAL,
            yield_strength_mpa REAL,
            hardness TEXT,
            cost_tier TEXT,
            notes TEXT
        );

        CREATE TABLE datum_patterns (
            id TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            primary_type TEXT NOT NULL,
            primary_reasoning TEXT NOT NULL,
            secondary_type TEXT,
            secondary_reasoning TEXT,
            tertiary_type TEXT,
            tertiary_reasoning TEXT,
            applicable_features TEXT,
            typical_callouts TEXT,
            example_parts TEXT,
            common_mistakes TEXT
        );

        CREATE VIRTUAL TABLE characteristics_fts USING fts5(
            id, name, rules, when_to_use, when_not_to_use, common_mistakes,
            content='geometric_characteristics',
            content_rowid='rowid'
        );
    """)


def seed_characteristics(conn: sqlite3.Connection, data: dict) -> int:
    rows = []
    for char in data["characteristics"]:
        rows.append((
            char["id"],
            char["symbol"],
            char["name"],
            char["category"],
            char.get("asme_section"),
            char["datum_required"],
            char.get("datum_optional", False),
            json.dumps(char.get("applicable_modifiers", [])),
            json.dumps(char.get("applicable_features", [])),
            char.get("tolerance_zone"),
            json.dumps(char.get("rules", [])),
            char.get("when_to_use"),
            char.get("when_NOT_to_use"),
            json.dumps(char.get("common_mistakes", [])),
            char.get("example_callout"),
            char.get("prefer_instead"),
            char.get("deprecation_note"),
        ))

    conn.executemany(
        """INSERT INTO geometric_characteristics
           (id, symbol, name, category, asme_section, datum_required, datum_optional,
            applicable_modifiers, applicable_features, tolerance_zone, rules,
            when_to_use, when_not_to_use, common_mistakes, example_callout,
            prefer_instead, deprecation_note)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )

    # Populate FTS5 index
    conn.executemany(
        """INSERT INTO characteristics_fts
           (rowid, id, name, rules, when_to_use, when_not_to_use, common_mistakes)
           SELECT rowid, id, name, rules, when_to_use, when_not_to_use, common_mistakes
           FROM geometric_characteristics WHERE id = ?""",
        [(r[0],) for r in rows],
    )

    return len(rows)


def seed_tolerances(conn: sqlite3.Connection, data: dict) -> int:
    rows = []
    for process_id, process_data in data["processes"].items():
        materials = process_data.get("materials", {})
        for material_id, material_data in materials.items():
            notes = material_data.get("notes")
            for key, value in material_data.items():
                if key in TOLERANCE_META_KEYS:
                    continue
                if not isinstance(value, dict) or "min_mm" not in value:
                    continue
                rows.append((
                    process_id,
                    material_id,
                    key,
                    value["min_mm"],
                    value["max_mm"],
                    notes,
                ))

    conn.executemany(
        """INSERT INTO tolerance_tables
           (process, material, characteristic, min_mm, max_mm, notes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        rows,
    )
    return len(rows)


def seed_materials(conn: sqlite3.Connection, data: dict) -> int:
    rows = []
    for mat_id, mat in data["materials"].items():
        rows.append((
            mat_id,
            mat["name"],
            mat["category"],
            json.dumps(mat.get("common_processes", [])),
            mat.get("machinability"),
            mat.get("thermal_expansion_ppm_c"),
            mat.get("density_g_cm3"),
            mat.get("yield_strength_mpa"),
            mat.get("hardness"),
            mat.get("cost_tier"),
            mat.get("notes"),
        ))

    conn.executemany(
        """INSERT INTO material_properties
           (id, name, category, common_processes, machinability,
            thermal_expansion_ppm_c, density_g_cm3, yield_strength_mpa,
            hardness, cost_tier, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    return len(rows)


def seed_datum_patterns(conn: sqlite3.Connection, data: dict) -> int:
    rows = []
    for pat_id, pat in data["patterns"].items():
        rows.append((
            pat_id,
            pat["description"],
            pat["primary"]["type"],
            pat["primary"]["reasoning"],
            pat.get("secondary", {}).get("type"),
            pat.get("secondary", {}).get("reasoning"),
            pat.get("tertiary", {}).get("type"),
            pat.get("tertiary", {}).get("reasoning"),
            json.dumps(pat.get("applicable_features", [])),
            json.dumps(pat.get("typical_callouts", [])),
            json.dumps(pat.get("example_parts", [])),
            json.dumps(pat.get("common_mistakes", [])),
        ))

    conn.executemany(
        """INSERT INTO datum_patterns
           (id, description, primary_type, primary_reasoning,
            secondary_type, secondary_reasoning, tertiary_type, tertiary_reasoning,
            applicable_features, typical_callouts, example_parts, common_mistakes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    return len(rows)


def verify(conn: sqlite3.Connection) -> None:
    tables = [
        "geometric_characteristics",
        "tolerance_tables",
        "material_properties",
        "datum_patterns",
    ]
    for table in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count} rows")

    # FTS5 search test
    fts_results = conn.execute(
        "SELECT id FROM characteristics_fts WHERE characteristics_fts MATCH 'perpendicular'"
    ).fetchall()
    fts_ids = [r[0] for r in fts_results]
    print(f"  FTS 'perpendicular': {fts_ids}")
    if "perpendicularity" not in fts_ids:
        raise RuntimeError("FTS5 verification failed: 'perpendicularity' not found")

    # Tribal knowledge test
    prefer = conn.execute(
        "SELECT prefer_instead FROM geometric_characteristics WHERE id='concentricity'"
    ).fetchone()
    if prefer is None or prefer[0] != "circular_runout":
        raise RuntimeError(
            f"Tribal knowledge check failed: concentricity.prefer_instead = {prefer}"
        )
    print(f"  concentricity.prefer_instead: {prefer[0]}")

    # Tolerance lookup test
    tol = conn.execute(
        "SELECT min_mm, max_mm FROM tolerance_tables "
        "WHERE process='cnc_milling' AND material='aluminum' AND characteristic='position'"
    ).fetchone()
    if tol is None:
        raise RuntimeError("Tolerance lookup failed: cnc_milling/aluminum/position not found")
    print(f"  cnc_milling.aluminum.position: {tol[0]}-{tol[1]} mm")


def main() -> None:
    # Verify all source files exist
    for filename in REQUIRED_FILES:
        path = STANDARDS_DIR / filename
        if not path.exists():
            raise FileNotFoundError(f"Required file not found: {path}")

    print(f"Seeding database: {DB_PATH}")

    conn = sqlite3.connect(str(DB_PATH))
    try:
        create_tables(conn)

        asme_data = load_json("asme_y14_5.json")
        tol_data = load_json("tolerance_tables.json")
        mat_data = load_json("material_properties.json")
        datum_data = load_json("datum_patterns.json")

        n_chars = seed_characteristics(conn, asme_data)
        n_tols = seed_tolerances(conn, tol_data)
        n_mats = seed_materials(conn, mat_data)
        n_pats = seed_datum_patterns(conn, datum_data)

        conn.commit()

        print(f"Seeded: {n_chars} characteristics, {n_tols} tolerances, "
              f"{n_mats} materials, {n_pats} datum patterns")

        print("Verification:")
        verify(conn)
        print("Database seeded successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
