import pytest
import aiosqlite
from brain.database import Database
from brain.manufacturing import ManufacturingLookup


@pytest.fixture
async def mfg(tmp_path):
    db_path = tmp_path / "test_brain.db"
    async with aiosqlite.connect(str(db_path)) as conn:
        await conn.execute("""
            CREATE TABLE tolerance_tables (
                id INTEGER PRIMARY KEY,
                process TEXT NOT NULL,
                material TEXT NOT NULL,
                feature_type TEXT NOT NULL,
                min_mm REAL,
                max_mm REAL,
                achievable_best_mm REAL,
                notes TEXT
            )
        """)
        await conn.execute(
            "INSERT INTO tolerance_tables VALUES (1, 'cnc_milling', 'AL6061-T6', 'position', 0.02, 0.1, 0.01, 'tight with fixturing')"
        )
        await conn.execute(
            "INSERT INTO tolerance_tables VALUES (2, 'cnc_milling', 'steel_4140', 'position', 0.03, 0.15, 0.02, 'harder material')"
        )
        await conn.execute("""
            CREATE TABLE material_properties (
                material_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                common_processes TEXT,
                machinability TEXT,
                thermal_expansion_ppm_c REAL
            )
        """)
        await conn.execute(
            """INSERT INTO material_properties VALUES (
                'AL6061-T6', 'Aluminum 6061-T6', 'aluminum',
                '["cnc_milling", "turning", "sheet_metal"]', 'excellent', 23.6
            )"""
        )
        await conn.commit()
    db = await Database.connect(str(db_path))
    yield ManufacturingLookup(db)
    await db.close()


@pytest.mark.asyncio
async def test_get_tolerance_range(mfg):
    result = await mfg.get_tolerance_range("cnc_milling", "AL6061-T6", "position")
    assert result is not None
    assert result["min_mm"] == 0.02
    assert result["max_mm"] == 0.1


@pytest.mark.asyncio
async def test_get_tolerance_range_missing(mfg):
    result = await mfg.get_tolerance_range("casting", "bronze", "position")
    assert result is None


@pytest.mark.asyncio
async def test_get_process_capability(mfg):
    results = await mfg.get_process_capability("cnc_milling")
    assert len(results) == 2


@pytest.mark.asyncio
async def test_get_material_properties(mfg):
    result = await mfg.get_material_properties("AL6061-T6")
    assert result is not None
    assert result["name"] == "Aluminum 6061-T6"
    assert result["common_processes"] == ["cnc_milling", "turning", "sheet_metal"]


@pytest.mark.asyncio
async def test_get_material_properties_by_partial_name(mfg):
    result = await mfg.get_material_properties("Aluminum")
    assert result is not None
    assert result["material_id"] == "AL6061-T6"
