import aiosqlite
from pathlib import Path


class Database:
    def __init__(self):
        self.conn: aiosqlite.Connection | None = None

    @classmethod
    async def connect(cls, path: str) -> "Database":
        db_path = Path(path)
        if not db_path.exists():
            raise FileNotFoundError(
                f"Brain database not found at {path}. "
                f"Run 'python scripts/seed_database.py' first."
            )
        db = cls()
        db.conn = await aiosqlite.connect(str(db_path))
        db.conn.row_factory = aiosqlite.Row
        await db.conn.execute("PRAGMA journal_mode=WAL")
        return db

    async def fetchone(self, query: str, params: tuple = ()) -> dict | None:
        async with self.conn.execute(query, params) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return dict(row)

    async def fetchall(self, query: str, params: tuple = ()) -> list[dict]:
        async with self.conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def close(self):
        if self.conn:
            await self.conn.close()
