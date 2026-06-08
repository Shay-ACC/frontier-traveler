from app.database import load_json_data
from app.models.relationship import Relationship


class RelationshipManager:
    MAX_CHANGE_PER_INTERACTION = 10
    STATUS_THRESHOLDS = {
        "hostile": (0, 20),
        "neutral": (20, 40),
        "friendly": (40, 70),
        "trusted": (70, 101),
    }

    @staticmethod
    def compute_status(trust: int) -> str:
        for status, (low, high) in RelationshipManager.STATUS_THRESHOLDS.items():
            if low <= trust < high:
                return status
        return "trusted"

    @staticmethod
    def clamp_value(value: int) -> int:
        return max(0, min(100, value))

    @staticmethod
    def clamp_delta(delta: int) -> int:
        return max(-10, min(10, delta))

    async def init_relationships(self, db, game_id: str):
        npcs = load_json_data("npcs.json")
        for npc in npcs:
            npc_id = npc["id"]
            await db.execute(
                "INSERT OR IGNORE INTO relationships (game_id, npc_id, trust, affection, status) VALUES (?, ?, 30, 30, 'neutral')",
                (game_id, npc_id),
            )
        await db.commit()

    async def get(self, db, game_id: str, npc_id: str) -> Relationship | None:
        cursor = await db.execute(
            "SELECT game_id, npc_id, trust, affection, status FROM relationships WHERE game_id = ? AND npc_id = ?",
            (game_id, npc_id),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return Relationship(
            game_id=row["game_id"],
            npc_id=row["npc_id"],
            trust=row["trust"],
            affection=row["affection"],
            status=row["status"],
        )

    async def get_all(self, db, game_id: str) -> list[Relationship]:
        cursor = await db.execute(
            "SELECT game_id, npc_id, trust, affection, status FROM relationships WHERE game_id = ?",
            (game_id,),
        )
        rows = await cursor.fetchall()
        return [
            Relationship(
                game_id=row["game_id"],
                npc_id=row["npc_id"],
                trust=row["trust"],
                affection=row["affection"],
                status=row["status"],
            )
            for row in rows
        ]

    async def modify(self, db, game_id: str, npc_id: str, field: str, delta: int) -> Relationship | None:
        rel = await self.get(db, game_id, npc_id)
        if rel is None:
            return None
        clamped_delta = self.clamp_delta(delta)
        current = getattr(rel, field)
        new_value = self.clamp_value(current + clamped_delta)
        setattr(rel, field, new_value)
        rel.status = self.compute_status(rel.trust)
        await db.execute(
            "UPDATE relationships SET trust = ?, affection = ?, status = ? WHERE game_id = ? AND npc_id = ?",
            (rel.trust, rel.affection, rel.status, game_id, npc_id),
        )
        await db.commit()
        return rel
