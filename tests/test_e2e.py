from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch

import aiosqlite
import pytest
import pytest_asyncio

from app.engine.game_engine import GameEngine

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "db" / "schema.sql"

MOCK_LOCATIONS = [
    {
        "id": "tavern",
        "name": "破晓酒馆",
        "description": "一间昏暗但温馨的小酒馆",
        "connections": ["town_hall"],
        "available_npcs": ["innkeeper"],
    },
    {
        "id": "town_hall",
        "name": "镇政厅",
        "description": "一座两层的石砌建筑",
        "connections": ["tavern", "abandoned_mine"],
        "available_npcs": ["mayor"],
    },
    {
        "id": "abandoned_mine",
        "name": "废弃矿坑",
        "description": "矿坑入口被锈迹斑斑的铁栅栏半遮着",
        "connections": ["town_hall"],
        "available_npcs": ["miner"],
    },
]

MOCK_NPCS = [
    {
        "id": "innkeeper",
        "name": "艾琳娜",
        "role": "酒馆老板娘",
        "personality": "精明、谨慎、善于察言观色。",
        "backstory": "艾琳娜在边境小镇经营破晓酒馆已有十年。",
        "default_location": "tavern",
        "dialogue_style": "说话简洁有力，偶尔带点讽刺。",
        "secrets": ["她知道矿坑失踪案与镇长有关"],
    },
    {
        "id": "mayor",
        "name": "赫尔曼",
        "role": "镇长",
        "personality": "表面和善、内心深沉。",
        "backstory": "赫尔曼担任边境小镇镇长已有十五年。",
        "default_location": "town_hall",
        "dialogue_style": "说话冠冕堂皇。",
        "secrets": ["他与矿业公司签了秘密协议"],
    },
    {
        "id": "miner",
        "name": "托马斯",
        "role": "矿工",
        "personality": "神经质、恐惧。",
        "backstory": "托马斯是矿坑失踪案的唯一幸存者。",
        "default_location": "abandoned_mine",
        "dialogue_style": "说话断断续续。",
        "secrets": ["他亲眼目睹了矿坑中发生的一切"],
    },
]


async def _get_quest_state(engine, game_id, quest_id):
    state = await engine.get_state(game_id)
    for qs in state.quest_states:
        if qs.quest_id == quest_id:
            return qs
    return None


async def _get_trust(engine, game_id, npc_id):
    state = await engine.get_state(game_id)
    for rel in state.relationships:
        if rel.npc_id == npc_id:
            return rel.trust
    return None


@pytest_asyncio.fixture
async def db():
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    await conn.commit()
    yield conn
    await conn.close()


@pytest_asyncio.fixture
async def engine(db):
    @asynccontextmanager
    async def _mock_get_db():
        yield db

    with (
        patch("app.systems.world_state.load_json_data", return_value=MOCK_LOCATIONS),
        patch("app.agents.npc_agent.load_json_data", return_value=MOCK_NPCS),
        patch("app.systems.relationship.load_json_data", return_value=MOCK_NPCS),
        patch("app.engine.game_engine.get_db", _mock_get_db),
    ):
        yield GameEngine()


@pytest.mark.asyncio
async def test_main_quest_full_flow(engine):
    start = await engine.start_game("旅行者")
    game_id = start.game_id
    assert start.current_location.id == "tavern"

    r1 = await engine.process_input(game_id, "和老板娘聊聊")
    assert r1.npc_id == "innkeeper"
    assert len(r1.state_changes.relationship_changes) == 1
    assert r1.state_changes.relationship_changes[0].delta == 1
    assert await _get_trust(engine, game_id, "innkeeper") == 31
    mc = await _get_quest_state(engine, game_id, "missing_case")
    assert mc.current_stage == "not_started"

    r2 = await engine.process_input(game_id, "和老板娘聊聊")
    assert r2.npc_id == "innkeeper"
    assert r2.state_changes.flag_changes.get("heard_about_missing") is True
    assert await _get_trust(engine, game_id, "innkeeper") == 34
    mc = await _get_quest_state(engine, game_id, "missing_case")
    assert mc.current_stage == "heard_rumor"
    assert r2.state_changes.flag_changes.get("heard_rumor") is True

    r3 = await engine.process_input(game_id, "前往镇政厅")
    assert r3.state_changes.location_changed is True
    assert r3.state_changes.new_location == "town_hall"
    mc = await _get_quest_state(engine, game_id, "missing_case")
    assert mc.current_stage == "heard_rumor"

    r4 = await engine.process_input(game_id, "前往废弃矿坑")
    assert r4.state_changes.location_changed is True
    assert r4.state_changes.new_location == "abandoned_mine"
    mc = await _get_quest_state(engine, game_id, "missing_case")
    assert mc.current_stage == "found_clue"
    assert r4.state_changes.flag_changes.get("found_clue") is True

    r5 = await engine.process_input(game_id, "和矿工说话")
    assert r5.npc_id == "miner"
    assert len(r5.state_changes.relationship_changes) == 1
    assert r5.state_changes.relationship_changes[0].delta == 1
    assert await _get_trust(engine, game_id, "miner") == 31
    mc = await _get_quest_state(engine, game_id, "missing_case")
    assert mc.current_stage == "found_clue"

    r6 = await engine.process_input(game_id, "前往镇政厅")
    assert r6.state_changes.location_changed is True
    assert r6.state_changes.new_location == "town_hall"

    r7 = await engine.process_input(game_id, "和镇长交谈")
    assert r7.npc_id == "mayor"
    trust_delta = r7.state_changes.relationship_changes[0].delta
    assert trust_delta == -5
    assert await _get_trust(engine, game_id, "mayor") == 25
    assert r7.state_changes.flag_changes.get("mayor_confessed") is True
    mc = await _get_quest_state(engine, game_id, "missing_case")
    assert mc.current_stage == "confronted_mayor"
    assert r7.state_changes.flag_changes.get("confronted_mayor") is True

    r8 = await engine.process_input(game_id, "前往废弃矿坑")
    assert r8.state_changes.location_changed is True
    assert r8.state_changes.new_location == "abandoned_mine"

    r9 = await engine.process_input(game_id, "和矿工说话")
    assert r9.npc_id == "miner"
    assert r9.state_changes.flag_changes.get("miner_testified") is True
    assert await _get_trust(engine, game_id, "miner") == 36
    mc = await _get_quest_state(engine, game_id, "missing_case")
    assert mc.current_stage == "resolved"
    assert mc.completed is True

    state = await engine.get_state(game_id)
    assert state.world_state.turn_count == 9


@pytest.mark.asyncio
async def test_side_quest_full_flow(engine):
    start = await engine.start_game("旅行者")
    game_id = start.game_id
    assert start.current_location.id == "tavern"

    await engine.process_input(game_id, "和老板娘聊聊")
    assert await _get_trust(engine, game_id, "innkeeper") == 31
    ll = await _get_quest_state(engine, game_id, "lost_ledger")
    assert ll.current_stage == "not_started"

    await engine.process_input(game_id, "和老板娘聊聊")
    assert await _get_trust(engine, game_id, "innkeeper") == 34
    mc = await _get_quest_state(engine, game_id, "missing_case")
    assert mc.current_stage == "heard_rumor"

    await engine.process_input(game_id, "和老板娘聊聊")
    assert await _get_trust(engine, game_id, "innkeeper") == 37
    ll = await _get_quest_state(engine, game_id, "lost_ledger")
    assert ll.current_stage == "not_started"

    r4 = await engine.process_input(game_id, "和老板娘聊聊")
    assert await _get_trust(engine, game_id, "innkeeper") == 40
    ll = await _get_quest_state(engine, game_id, "lost_ledger")
    assert ll.current_stage == "accepted"
    assert r4.state_changes.flag_changes.get("accepted") is True

    await engine.process_input(game_id, "前往镇政厅")
    state = await engine.get_state(game_id)
    assert state.world_state.current_location == "town_hall"

    r6 = await engine.process_input(game_id, "和镇长交谈")
    assert r6.npc_id == "mayor"
    assert await _get_trust(engine, game_id, "mayor") == 31
    ll = await _get_quest_state(engine, game_id, "lost_ledger")
    assert ll.current_stage == "searching"

    r7 = await engine.process_input(game_id, "和镇长交谈")
    assert r7.npc_id == "mayor"
    assert r7.state_changes.flag_changes.get("found_ledger_location") is True
    assert await _get_trust(engine, game_id, "mayor") == 29
    ll = await _get_quest_state(engine, game_id, "lost_ledger")
    assert ll.current_stage == "found_ledger"
    assert r7.state_changes.flag_changes.get("found_ledger") is True

    r8 = await engine.process_input(game_id, "前往破晓酒馆")
    assert r8.state_changes.location_changed is True
    assert r8.state_changes.new_location == "tavern"

    r9 = await engine.process_input(game_id, "和老板娘聊聊")
    assert r9.npc_id == "innkeeper"
    assert await _get_trust(engine, game_id, "innkeeper") == 43
    ll = await _get_quest_state(engine, game_id, "lost_ledger")
    assert ll.current_stage == "resolved"
    assert ll.completed is True

    state = await engine.get_state(game_id)
    assert state.world_state.turn_count == 9
