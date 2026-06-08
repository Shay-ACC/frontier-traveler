import pytest
import pytest_asyncio
import aiosqlite

from app.systems.memory import MemoryManager

GAME_ID = "test-game-001"
NPC_ID = "test-npc-001"


@pytest_asyncio.fixture
async def db():
    async with aiosqlite.connect(":memory:") as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "CREATE TABLE IF NOT EXISTS games ("
            "game_id TEXT PRIMARY KEY,"
            "player_name TEXT NOT NULL DEFAULT '旅行者',"
            "current_location TEXT NOT NULL DEFAULT 'tavern',"
            "time_of_day TEXT NOT NULL DEFAULT 'morning',"
            "turn_count INTEGER NOT NULL DEFAULT 0,"
            "flags TEXT NOT NULL DEFAULT '{}',"
            "created_at TEXT NOT NULL DEFAULT (datetime('now'))"
            ")"
        )
        await db.execute(
            "INSERT INTO games (game_id) VALUES (?)",
            (GAME_ID,),
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS memories ("
            "id TEXT PRIMARY KEY,"
            "game_id TEXT NOT NULL,"
            "npc_id TEXT NOT NULL,"
            "type TEXT NOT NULL CHECK(type IN ('short_term', 'long_term')),"
            "content TEXT NOT NULL,"
            "importance INTEGER NOT NULL DEFAULT 5,"
            "turn INTEGER NOT NULL,"
            "created_at TEXT NOT NULL DEFAULT (datetime('now')),"
            "accessed_count INTEGER NOT NULL DEFAULT 0,"
            "FOREIGN KEY (game_id) REFERENCES games(game_id)"
            ")"
        )
        await db.execute("CREATE INDEX IF NOT EXISTS idx_memories_game_npc ON memories(game_id, npc_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(game_id, npc_id, type)")
        await db.commit()
        yield db


@pytest.fixture
def manager():
    return MemoryManager()


@pytest.mark.asyncio
async def test_add_short_term(db, manager):
    memory = await manager.add_short_term(db, GAME_ID, NPC_ID, "测试记忆内容", importance=5, turn=1)
    assert memory.type == "short_term"
    assert memory.content == "测试记忆内容"
    assert memory.importance == 5
    assert memory.turn == 1

    cursor = await db.execute(
        "SELECT * FROM memories WHERE id = ?",
        (memory.id,),
    )
    row = await cursor.fetchone()
    assert row is not None
    assert row["content"] == "测试记忆内容"
    assert row["type"] == "short_term"


@pytest.mark.asyncio
async def test_fifo_eviction(db, manager):
    for i in range(1, 23):
        await manager.add_short_term(db, GAME_ID, NPC_ID, f"记忆_{i}", importance=3, turn=i)

    count = await manager.count_short_term(db, GAME_ID, NPC_ID)
    assert count <= MemoryManager.SHORT_TERM_LIMIT

    recent = await manager.get_recent(db, GAME_ID, NPC_ID, limit=1)
    assert recent[0].content == "记忆_22"

    cursor = await db.execute(
        "SELECT * FROM memories WHERE game_id = ? AND npc_id = ? AND content = ?",
        (GAME_ID, NPC_ID, "记忆_1"),
    )
    row = await cursor.fetchone()
    assert row is None

    cursor = await db.execute(
        "SELECT * FROM memories WHERE game_id = ? AND npc_id = ? AND content = ?",
        (GAME_ID, NPC_ID, "记忆_2"),
    )
    row = await cursor.fetchone()
    assert row is None


@pytest.mark.asyncio
async def test_promotion_on_eviction(db, manager):
    important_content = "重要记忆_不应被删除"
    await manager.add_short_term(db, GAME_ID, NPC_ID, important_content, importance=8, turn=1)

    for i in range(2, 22):
        await manager.add_short_term(db, GAME_ID, NPC_ID, f"普通记忆_{i}", importance=3, turn=i)

    cursor = await db.execute(
        "SELECT * FROM memories WHERE game_id = ? AND npc_id = ? AND content = ?",
        (GAME_ID, NPC_ID, important_content),
    )
    row = await cursor.fetchone()
    assert row is not None
    assert row["type"] == "long_term"


@pytest.mark.asyncio
async def test_recall_returns_long_and_short(db, manager):
    await manager.add_short_term(db, GAME_ID, NPC_ID, "短期记忆_1", importance=5, turn=1)
    await manager.add_short_term(db, GAME_ID, NPC_ID, "短期记忆_2", importance=5, turn=2)
    await manager.promote_to_long_term(db, (await manager.get_recent(db, GAME_ID, NPC_ID, limit=1))[0].id)
    await manager.add_short_term(db, GAME_ID, NPC_ID, "短期记忆_3", importance=5, turn=3)

    results = await manager.recall(db, GAME_ID, NPC_ID)
    types = [m.type for m in results]
    assert "long_term" in types
    assert "short_term" in types


@pytest.mark.asyncio
async def test_memories_do_not_contain_secrets_or_backstory(db, manager):
    memory = await manager.add_short_term(db, GAME_ID, NPC_ID, "旅行者问了关于失踪案的事", importance=5, turn=1)
    assert "秘密" not in memory.content
    assert "backstory" not in memory.content.lower()
    assert "矿坑失踪案与镇长" not in memory.content
    assert "亲眼目睹" not in memory.content


@pytest.mark.asyncio
async def test_recall_increments_accessed_count(db, manager):
    await manager.add_short_term(db, GAME_ID, NPC_ID, "记忆A", importance=5, turn=1)

    results = await manager.recall(db, GAME_ID, NPC_ID)
    assert results[0].accessed_count >= 1

    cursor = await db.execute(
        "SELECT accessed_count FROM memories WHERE game_id = ? AND npc_id = ?",
        (GAME_ID, NPC_ID),
    )
    row = await cursor.fetchone()
    assert row["accessed_count"] >= 1


@pytest.mark.asyncio
async def test_recall_sorting(db, manager):
    await manager.add_short_term(db, GAME_ID, NPC_ID, "低重要度", importance=3, turn=1)
    await manager.add_short_term(db, GAME_ID, NPC_ID, "高重要度", importance=9, turn=2)
    await manager.add_short_term(db, GAME_ID, NPC_ID, "中重要度", importance=6, turn=3)

    results = await manager.recall(db, GAME_ID, NPC_ID)
    importances = [m.importance for m in results]
    assert importances == sorted(importances, reverse=True)

    await manager.add_short_term(db, GAME_ID, NPC_ID, "同重要度_A", importance=5, turn=4)
    await manager.add_short_term(db, GAME_ID, NPC_ID, "同重要度_B", importance=5, turn=5)

    await db.execute(
        "UPDATE memories SET accessed_count = 10 WHERE content = '同重要度_A'",
        ()
    )
    await db.execute(
        "UPDATE memories SET accessed_count = 1 WHERE content = '同重要度_B'",
        ()
    )
    await db.commit()

    results = await manager.recall(db, GAME_ID, NPC_ID)
    same_importance = [m for m in results if m.importance == 5]
    if len(same_importance) >= 2:
        assert same_importance[0].accessed_count <= same_importance[1].accessed_count


OTHER_NPC_ID = "test-npc-002"


@pytest.mark.asyncio
async def test_recall_with_context_returns_two_lists(db, manager):
    await manager.add_short_term(db, GAME_ID, NPC_ID, "当前NPC记忆", importance=5, turn=1)
    await manager.add_short_term(db, GAME_ID, OTHER_NPC_ID, "其他NPC记忆", importance=8, turn=1)
    await manager.promote_to_long_term(db, (await manager.get_recent(db, GAME_ID, OTHER_NPC_ID, limit=1))[0].id)

    current, cross_npc = await manager.recall_with_context(db, GAME_ID, NPC_ID)
    assert isinstance(current, list)
    assert isinstance(cross_npc, list)
    assert len(current) >= 1
    assert any(m.npc_id == NPC_ID for m in current)


@pytest.mark.asyncio
async def test_recall_with_context_cross_npc_only_long_term(db, manager):
    await manager.add_short_term(db, GAME_ID, OTHER_NPC_ID, "其他NPC短期", importance=5, turn=1)
    await manager.add_short_term(db, GAME_ID, OTHER_NPC_ID, "其他NPC长期", importance=9, turn=2)
    await manager.promote_to_long_term(db, (await manager.get_recent(db, GAME_ID, OTHER_NPC_ID, limit=1))[0].id)

    _, cross_npc = await manager.recall_with_context(db, GAME_ID, NPC_ID)
    for m in cross_npc:
        assert m.type == "long_term"


@pytest.mark.asyncio
async def test_recall_with_context_cross_npc_limited_to_three(db, manager):
    for i in range(5):
        mem = await manager.add_short_term(db, GAME_ID, OTHER_NPC_ID, f"跨NPC记忆_{i}", importance=9, turn=i + 1)
        await manager.promote_to_long_term(db, mem.id)

    _, cross_npc = await manager.recall_with_context(db, GAME_ID, NPC_ID)
    assert len(cross_npc) <= 3


@pytest.mark.asyncio
async def test_recall_with_context_budget(db, manager):
    for i in range(10):
        await manager.add_short_term(db, GAME_ID, NPC_ID, f"当前记忆_{i}", importance=5, turn=i + 1)

    for i in range(5):
        mem = await manager.add_short_term(db, GAME_ID, OTHER_NPC_ID, f"跨NPC记忆_{i}", importance=9, turn=i + 1)
        await manager.promote_to_long_term(db, mem.id)

    current, cross_npc = await manager.recall_with_context(db, GAME_ID, NPC_ID)
    total = len(current) + len(cross_npc)
    assert total <= MemoryManager.RECALL_BUDGET


@pytest.mark.asyncio
async def test_get_recent_includes_long_term(db, manager):
    await manager.add_short_term(db, GAME_ID, NPC_ID, "短期记忆", importance=5, turn=1)
    mem = await manager.add_short_term(db, GAME_ID, NPC_ID, "长期记忆", importance=9, turn=2)
    await manager.promote_to_long_term(db, mem.id)

    recent = await manager.get_recent(db, GAME_ID, NPC_ID, limit=5)
    types = [m.type for m in recent]
    assert "long_term" in types
    assert "short_term" in types
