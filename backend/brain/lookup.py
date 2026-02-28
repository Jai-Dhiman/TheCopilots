import json
from .database import Database


JSON_FIELDS = [
    "applicable_modifiers",
    "applicable_features",
    "rules",
    "common_mistakes",
    "example_parts",
]


def _parse_json_fields(row: dict | None) -> dict | None:
    """Parse JSON string fields in a database row."""
    if row is None:
        return None
    for field in JSON_FIELDS:
        if field in row and row[field] and isinstance(row[field], str):
            try:
                row[field] = json.loads(row[field])
            except json.JSONDecodeError:
                pass
    return row


class BrainLookup:
    def __init__(self, db: Database):
        self.db = db

    async def lookup_standard(self, code: str) -> dict | None:
        """Fetch ASME Y14.5 section by symbol or name (case-insensitive)."""
        return await self.db.fetchone(
            "SELECT * FROM geometric_characteristics "
            "WHERE symbol = ? OR name = ? COLLATE NOCASE",
            (code, code),
        )

    async def get_geometric_characteristic(self, symbol: str) -> dict | None:
        """Full rule set for a given GD&T symbol with parsed JSON fields."""
        row = await self.db.fetchone(
            "SELECT * FROM geometric_characteristics WHERE symbol = ?",
            (symbol,),
        )
        return _parse_json_fields(row)

    async def lookup_datum_pattern(self, feature_type: str) -> dict | None:
        """Match features to common datum scheme patterns."""
        row = await self.db.fetchone(
            "SELECT * FROM datum_patterns WHERE pattern_name LIKE ?",
            (f"%{feature_type}%",),
        )
        return _parse_json_fields(row)

    async def search_standards(self, query: str) -> list[dict]:
        """Search across standards by name or usage text."""
        return await self.db.fetchall(
            "SELECT * FROM geometric_characteristics WHERE name LIKE ? OR when_to_use LIKE ?",
            (f"%{query}%", f"%{query}%"),
        )
