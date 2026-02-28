import pytest
import aiosqlite
from brain.database import Database
from brain.lookup import BrainLookup


@pytest.fixture
async def brain(tmp_path):
    db_path = tmp_path / "test_brain.db"
    async with aiosqlite.connect(str(db_path)) as conn:
        await conn.execute("""
            CREATE TABLE geometric_characteristics (
                symbol TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                datum_required INTEGER NOT NULL,
                applicable_modifiers TEXT,
                applicable_features TEXT,
                rules TEXT,
                when_to_use TEXT,
                when_not_to_use TEXT,
                common_mistakes TEXT
            )
        """)
        await conn.execute(
            "INSERT INTO geometric_characteristics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "\u22a5", "perpendicularity", "orientation", 1,
                '["MMC", "LMC"]', '["boss", "hole"]',
                '["7.2"]', "axis perpendicular to datum",
                "not for form control", '["forgetting datum"]',
            ),
        )
        await conn.execute("""
            CREATE TABLE datum_patterns (
                pattern_name TEXT PRIMARY KEY,
                description TEXT,
                primary_type TEXT,
                secondary_type TEXT,
                tertiary_type TEXT,
                example_parts TEXT,
                common_mistakes TEXT
            )
        """)
        await conn.execute(
            "INSERT INTO datum_patterns VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "boss_on_plate", "Boss perpendicular to flat plate",
                "planar", "cylindrical", None,
                '["bracket", "housing"]', '["wrong datum order"]',
            ),
        )
        await conn.commit()
    db = await Database.connect(str(db_path))
    yield BrainLookup(db)
    await db.close()


@pytest.mark.asyncio
async def test_lookup_standard_by_symbol(brain):
    result = await brain.lookup_standard("\u22a5")
    assert result is not None
    assert result["name"] == "perpendicularity"


@pytest.mark.asyncio
async def test_lookup_standard_by_name(brain):
    result = await brain.lookup_standard("perpendicularity")
    assert result is not None
    assert result["symbol"] == "\u22a5"


@pytest.mark.asyncio
async def test_lookup_standard_missing(brain):
    result = await brain.lookup_standard("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_get_geometric_characteristic_parses_json_fields(brain):
    result = await brain.get_geometric_characteristic("\u22a5")
    assert result is not None
    assert result["applicable_modifiers"] == ["MMC", "LMC"]
    assert result["applicable_features"] == ["boss", "hole"]
    assert result["rules"] == ["7.2"]


@pytest.mark.asyncio
async def test_lookup_datum_pattern(brain):
    result = await brain.lookup_datum_pattern("boss")
    assert result is not None
    assert result["pattern_name"] == "boss_on_plate"
    assert result["example_parts"] == ["bracket", "housing"]


@pytest.mark.asyncio
async def test_search_standards(brain):
    results = await brain.search_standards("perpendicular")
    assert len(results) >= 1
    assert results[0]["name"] == "perpendicularity"
