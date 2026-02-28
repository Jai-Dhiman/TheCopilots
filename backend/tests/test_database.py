import pytest
import aiosqlite
from brain.database import Database


@pytest.fixture
async def test_db(tmp_path):
    """Create a test database with schema."""
    db_path = tmp_path / "test_brain.db"
    async with aiosqlite.connect(str(db_path)) as conn:
        await conn.execute("""
            CREATE TABLE geometric_characteristics (
                symbol TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                datum_required INTEGER NOT NULL,
                rules TEXT,
                when_to_use TEXT,
                common_mistakes TEXT
            )
        """)
        await conn.execute(
            "INSERT INTO geometric_characteristics VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("\u22a5", "perpendicularity", "orientation", 1, '["7.2"]', "axis control", '["forgetting datum"]'),
        )
        await conn.execute(
            "INSERT INTO geometric_characteristics VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("\u25b1", "flatness", "form", 0, '["5.4"]', "flat surfaces", '["adding datums"]'),
        )
        await conn.commit()
    db = await Database.connect(str(db_path))
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_connect_missing_db():
    with pytest.raises(FileNotFoundError):
        await Database.connect("/nonexistent/path/brain.db")


@pytest.mark.asyncio
async def test_fetchone(test_db):
    row = await test_db.fetchone(
        "SELECT * FROM geometric_characteristics WHERE symbol = ?", ("\u22a5",)
    )
    assert row is not None
    assert row["name"] == "perpendicularity"
    assert row["datum_required"] == 1


@pytest.mark.asyncio
async def test_fetchone_missing(test_db):
    row = await test_db.fetchone(
        "SELECT * FROM geometric_characteristics WHERE symbol = ?", ("FAKE",)
    )
    assert row is None


@pytest.mark.asyncio
async def test_fetchall(test_db):
    rows = await test_db.fetchall("SELECT * FROM geometric_characteristics")
    assert len(rows) == 2
    names = [r["name"] for r in rows]
    assert "perpendicularity" in names
    assert "flatness" in names
