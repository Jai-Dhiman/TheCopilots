import json
from .database import Database


class ManufacturingLookup:
    def __init__(self, db: Database):
        self.db = db

    async def get_tolerance_range(
        self, process: str, material: str, feature_type: str
    ) -> dict | None:
        """Lookup typical achievable tolerance for a process/material/feature combo."""
        return await self.db.fetchone(
            """SELECT * FROM tolerance_tables
               WHERE process = ? AND material = ? AND feature_type = ?""",
            (process, material, feature_type),
        )

    async def get_process_capability(self, process: str) -> list[dict]:
        """Full process capability profile across all materials."""
        return await self.db.fetchall(
            "SELECT * FROM tolerance_tables WHERE process = ?",
            (process,),
        )

    async def get_material_properties(self, material: str) -> dict | None:
        """Material properties relevant to tolerancing."""
        row = await self.db.fetchone(
            "SELECT * FROM material_properties WHERE material_id = ? OR name LIKE ?",
            (material, f"%{material}%"),
        )
        if row and row.get("common_processes") and isinstance(row["common_processes"], str):
            try:
                row["common_processes"] = json.loads(row["common_processes"])
            except json.JSONDecodeError:
                pass
        return row
