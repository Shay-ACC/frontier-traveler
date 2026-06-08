import json

import aiosqlite
import pytest
import pytest_asyncio

from app.models.quest import QuestState
from app.systems.quest import QuestManager

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS quest_states (
    game_id TEXT NOT NULL,
    quest_id TEXT NOT NULL,
    current_stage TEXT NOT NULL,
    completed INTEGER NOT NULL DEFAULT 0,
    stage_history TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (game_id, quest_id)
);
"""


@pytest_asyncio.fixture
async def db():
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.executescript(CREATE_TABLE_SQL)
    await conn.commit()
    yield conn
    await conn.close()


@pytest.fixture
def manager():
    return QuestManager()


def test_load_quests(manager):
    quests = manager.get_all_quests()
    assert len(quests) == 2
    ids = {q.id for q in quests}
    assert "missing_case" in ids
    assert "lost_ledger" in ids


def test_validate_transition_valid(manager):
    assert manager.validate_transition("missing_case", "not_started", "heard_rumor") is True
    assert manager.validate_transition("missing_case", "heard_rumor", "found_clue") is True
    assert manager.validate_transition("lost_ledger", "not_started", "accepted") is True


def test_validate_transition_invalid(manager):
    assert manager.validate_transition("missing_case", "not_started", "found_clue") is False
    assert manager.validate_transition("missing_case", "heard_rumor", "not_started") is False
    assert manager.validate_transition("missing_case", "resolved", "not_started") is False
    assert manager.validate_transition("nonexistent", "a", "b") is False


@pytest.mark.asyncio
async def test_advance_with_flag_condition(manager, db):
    await manager.init_quest_states(db, "game1")
    context = {"flags": {"heard_about_missing": True}}
    result = await manager.advance(db, "game1", "missing_case", context)
    assert result is True
    state = await manager.get_state(db, "game1", "missing_case")
    assert state.current_stage == "heard_rumor"


@pytest.mark.asyncio
async def test_advance_flag_not_met(manager, db):
    await manager.init_quest_states(db, "game1")
    context = {"flags": {"heard_about_missing": False}}
    result = await manager.advance(db, "game1", "missing_case", context)
    assert result is False
    state = await manager.get_state(db, "game1", "missing_case")
    assert state.current_stage == "not_started"


@pytest.mark.asyncio
async def test_advance_with_location_condition(manager, db):
    await manager.init_quest_states(db, "game1")
    state = await manager.get_state(db, "game1", "missing_case")
    state.current_stage = "heard_rumor"
    await db.execute(
        "UPDATE quest_states SET current_stage = ? WHERE game_id = ? AND quest_id = ?",
        (state.current_stage, "game1", "missing_case"),
    )
    await db.commit()
    context = {"location": "abandoned_mine", "turn": 3}
    result = await manager.advance(db, "game1", "missing_case", context)
    assert result is True
    state = await manager.get_state(db, "game1", "missing_case")
    assert state.current_stage == "found_clue"


@pytest.mark.asyncio
async def test_advance_with_min_trust_condition(manager, db):
    await manager.init_quest_states(db, "game1")
    context = {"npc": "innkeeper", "trust": {"innkeeper": 50}}
    result = await manager.advance(db, "game1", "lost_ledger", context)
    assert result is True
    state = await manager.get_state(db, "game1", "lost_ledger")
    assert state.current_stage == "accepted"


@pytest.mark.asyncio
async def test_quest_completion(manager, db):
    await manager.init_quest_states(db, "game1")
    stages = [
        ("not_started", {"flags": {"heard_about_missing": True}}),
        ("heard_rumor", {"location": "abandoned_mine", "turn": 3}),
        ("found_clue", {"npc": "mayor", "trust": {"mayor": 30}}),
        ("confronted_mayor", {"npc": "miner", "flags": {"found_clue": True}}),
    ]
    for stage_id, context in stages:
        state = await manager.get_state(db, "game1", "missing_case")
        assert state.current_stage == stage_id
        result = await manager.advance(db, "game1", "missing_case", context)
        assert result is True
    assert await manager.check_completion(db, "game1", "missing_case") is True
    state = await manager.get_state(db, "game1", "missing_case")
    assert state.completed is True
    assert "not_started" in state.stage_history
    assert "heard_rumor" in state.stage_history
    assert "found_clue" in state.stage_history
    assert "confronted_mayor" in state.stage_history
