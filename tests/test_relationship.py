from unittest.mock import patch

import pytest
import pytest_asyncio
import aiosqlite

from app.systems.relationship import RelationshipManager

MOCK_NPCS = [
    {"id": "innkeeper"},
    {"id": "mayor"},
    {"id": "miner"},
]


@pytest.fixture
def manager():
    return RelationshipManager()


@pytest_asyncio.fixture
async def db():
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS relationships ("
            "game_id TEXT NOT NULL,"
            "npc_id TEXT NOT NULL,"
            "trust INTEGER NOT NULL DEFAULT 30,"
            "affection INTEGER NOT NULL DEFAULT 30,"
            "status TEXT NOT NULL DEFAULT 'neutral',"
            "PRIMARY KEY (game_id, npc_id))"
        )
        await conn.commit()
        yield conn


def test_compute_status_hostile():
    assert RelationshipManager.compute_status(10) == "hostile"


def test_compute_status_neutral():
    assert RelationshipManager.compute_status(30) == "neutral"


def test_compute_status_friendly():
    assert RelationshipManager.compute_status(55) == "friendly"


def test_compute_status_trusted():
    assert RelationshipManager.compute_status(80) == "trusted"


def test_clamp_value_in_range():
    assert RelationshipManager.clamp_value(50) == 50


def test_clamp_value_over_100():
    assert RelationshipManager.clamp_value(150) == 100


def test_clamp_value_under_0():
    assert RelationshipManager.clamp_value(-10) == 0


def test_clamp_delta_normal():
    assert RelationshipManager.clamp_delta(5) == 5


def test_clamp_delta_over_10():
    assert RelationshipManager.clamp_delta(20) == 10


def test_clamp_delta_under_minus_10():
    assert RelationshipManager.clamp_delta(-20) == -10


@pytest.mark.asyncio
@patch("app.systems.relationship.load_json_data", return_value=MOCK_NPCS)
async def test_init_relationships(mock_load, manager, db):
    await manager.init_relationships(db, "game1")
    rels = await manager.get_all(db, "game1")
    assert len(rels) == 3
    npc_ids = {r.npc_id for r in rels}
    assert npc_ids == {"innkeeper", "mayor", "miner"}
    for r in rels:
        assert r.trust == 30
        assert r.affection == 30
        assert r.status == "neutral"


@pytest.mark.asyncio
@patch("app.systems.relationship.load_json_data", return_value=MOCK_NPCS)
async def test_modify_trust_increase(mock_load, manager, db):
    await manager.init_relationships(db, "game1")
    rel = await manager.modify(db, "game1", "innkeeper", "trust", 8)
    assert rel.trust == 38


@pytest.mark.asyncio
@patch("app.systems.relationship.load_json_data", return_value=MOCK_NPCS)
async def test_modify_trust_decrease(mock_load, manager, db):
    await manager.init_relationships(db, "game1")
    rel = await manager.modify(db, "game1", "innkeeper", "trust", -5)
    assert rel.trust == 25


@pytest.mark.asyncio
@patch("app.systems.relationship.load_json_data", return_value=MOCK_NPCS)
async def test_modify_over_limit(mock_load, manager, db):
    await manager.init_relationships(db, "game1")
    rel = await manager.modify(db, "game1", "innkeeper", "trust", 80)
    assert rel.trust == 40
    rel = await manager.modify(db, "game1", "innkeeper", "trust", -80)
    assert rel.trust == 30


@pytest.mark.asyncio
@patch("app.systems.relationship.load_json_data", return_value=MOCK_NPCS)
async def test_modify_updates_status(mock_load, manager, db):
    await manager.init_relationships(db, "game1")
    for _ in range(4):
        rel = await manager.modify(db, "game1", "innkeeper", "trust", 10)
    assert rel.trust == 70
    assert rel.status == "trusted"
    for _ in range(6):
        rel = await manager.modify(db, "game1", "innkeeper", "trust", -10)
    assert rel.trust == 10
    assert rel.status == "hostile"
