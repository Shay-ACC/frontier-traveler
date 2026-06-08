import uuid
from datetime import datetime, timezone

from app.models.memory import Memory


class MemoryManager:
    SHORT_TERM_LIMIT = 20
    PROMOTION_THRESHOLD = 7
    RECALL_RECENT_COUNT = 5
    RECALL_BUDGET = 12

    @staticmethod
    def _row_to_memory(row) -> Memory:
        return Memory(
            id=row["id"],
            game_id=row["game_id"],
            npc_id=row["npc_id"],
            type=row["type"],
            content=row["content"],
            importance=row["importance"],
            turn=row["turn"],
            created_at=datetime.fromisoformat(row["created_at"]),
            accessed_count=row["accessed_count"],
        )

    async def add_short_term(self, db, game_id: str, npc_id: str, content: str, importance: int, turn: int, auto_commit: bool = True):
        memory = Memory(
            id=str(uuid.uuid4()),
            game_id=game_id,
            npc_id=npc_id,
            type="short_term",
            content=content,
            importance=importance,
            turn=turn,
            created_at=datetime.now(timezone.utc),
            accessed_count=0,
        )
        await db.execute(
            "INSERT INTO memories (id, game_id, npc_id, type, content, importance, turn, created_at, accessed_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (memory.id, memory.game_id, memory.npc_id, memory.type, memory.content, memory.importance, memory.turn, memory.created_at.isoformat(), memory.accessed_count),
        )
        if auto_commit:
            await db.commit()
        await self.cleanup_expired(db, game_id, npc_id, auto_commit=auto_commit)
        return memory

    async def promote_to_long_term(self, db, memory_id: str, auto_commit: bool = True):
        await db.execute(
            "UPDATE memories SET type = 'long_term' WHERE id = ?",
            (memory_id,),
        )
        if auto_commit:
            await db.commit()

    async def recall(self, db, game_id: str, npc_id: str, auto_commit: bool = True) -> list[Memory]:
        long_term_rows = await db.execute_fetchall(
            "SELECT * FROM memories WHERE game_id = ? AND npc_id = ? AND type = 'long_term'",
            (game_id, npc_id),
        )
        short_term_rows = await db.execute_fetchall(
            "SELECT * FROM memories WHERE game_id = ? AND npc_id = ? AND type = 'short_term' ORDER BY turn DESC LIMIT ?",
            (game_id, npc_id, self.RECALL_RECENT_COUNT),
        )
        all_rows = list(long_term_rows) + list(short_term_rows)
        memories = [self._row_to_memory(row) for row in all_rows]

        for mem in memories:
            await db.execute(
                "UPDATE memories SET accessed_count = accessed_count + 1 WHERE id = ?",
                (mem.id,),
            )
            mem.accessed_count += 1
        if auto_commit:
            await db.commit()

        memories.sort(key=lambda m: (-m.importance, m.accessed_count))
        return memories

    async def recall_with_context(self, db, game_id: str, npc_id: str, auto_commit: bool = True) -> tuple[list[Memory], list[Memory]]:
        current = await self.recall(db, game_id, npc_id, auto_commit=False)
        current = current[:8]

        cursor = await db.execute(
            "SELECT * FROM memories WHERE game_id = ? AND npc_id != ? AND type = 'long_term' ORDER BY importance DESC, accessed_count ASC LIMIT 10",
            (game_id, npc_id),
        )
        cross_rows = await cursor.fetchall()
        cross_npc = [self._row_to_memory(row) for row in cross_rows]
        cross_npc.sort(key=lambda m: (-m.importance, m.accessed_count))
        cross_npc = cross_npc[:3]

        all_ids = [m.id for m in current + cross_npc]
        for mid in all_ids:
            await db.execute(
                "UPDATE memories SET accessed_count = accessed_count + 1 WHERE id = ?",
                (mid,),
            )
        if auto_commit:
            await db.commit()

        return current, cross_npc

    async def get_recent(self, db, game_id: str, npc_id: str, limit: int = 5) -> list[Memory]:
        cursor = await db.execute(
            "SELECT * FROM memories WHERE game_id = ? AND npc_id = ? ORDER BY type = 'long_term' DESC, importance DESC, turn DESC LIMIT ?",
            (game_id, npc_id, limit),
        )
        rows = await cursor.fetchall()
        return [self._row_to_memory(row) for row in rows]

    async def get_all_long_term(self, db, game_id: str, npc_id: str) -> list[Memory]:
        cursor = await db.execute(
            "SELECT * FROM memories WHERE game_id = ? AND npc_id = ? AND type = 'long_term'",
            (game_id, npc_id),
        )
        rows = await cursor.fetchall()
        return [self._row_to_memory(row) for row in rows]

    async def count_short_term(self, db, game_id: str, npc_id: str) -> int:
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM memories WHERE game_id = ? AND npc_id = ? AND type = 'short_term'",
            (game_id, npc_id),
        )
        row = await cursor.fetchone()
        return row["cnt"]

    async def cleanup_expired(self, db, game_id: str, npc_id: str, auto_commit: bool = True):
        while await self.count_short_term(db, game_id, npc_id) > self.SHORT_TERM_LIMIT:
            cursor = await db.execute(
                "SELECT * FROM memories WHERE game_id = ? AND npc_id = ? AND type = 'short_term' ORDER BY turn ASC LIMIT 1",
                (game_id, npc_id),
            )
            row = await cursor.fetchone()
            if row is None:
                break
            if row["importance"] >= self.PROMOTION_THRESHOLD:
                await self.promote_to_long_term(db, row["id"], auto_commit=False)
            else:
                await db.execute("DELETE FROM memories WHERE id = ?", (row["id"],))
        if auto_commit:
            await db.commit()
