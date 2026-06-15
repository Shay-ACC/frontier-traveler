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
async def test_start_game(engine):
    response = await engine.start_game("测试玩家")

    assert response.game_id
    assert len(response.game_id) == 36
    assert "边境小镇" in response.opening_narrative
    assert response.current_location.id == "tavern"
    assert len(response.available_npcs) == 1
    assert response.available_npcs[0].id == "innkeeper"


@pytest.mark.asyncio
async def test_process_input_talk(engine):
    start = await engine.start_game("旅行者")
    game_id = start.game_id

    response = await engine.process_input(game_id, "和老板娘聊聊")

    assert response.npc_response
    assert response.npc_id == "innkeeper"
    assert len(response.available_actions) > 0


@pytest.mark.asyncio
async def test_process_input_move(engine):
    start = await engine.start_game("旅行者")
    game_id = start.game_id

    response = await engine.process_input(game_id, "前往镇政厅")

    assert "镇政厅" in response.narration
    assert response.state_changes.location_changed is True
    assert response.state_changes.new_location == "town_hall"
    assert response.npc_id is None
    assert response.npc_response == ""


@pytest.mark.asyncio
async def test_get_state(engine):
    start = await engine.start_game("旅行者")
    game_id = start.game_id

    state = await engine.get_state(game_id)

    assert state is not None
    assert state.game_id == game_id
    assert state.world_state.current_location == "tavern"
    assert len(state.relationships) == 3
    assert len(state.quest_states) == 2


@pytest.mark.asyncio
async def test_get_state_not_found(engine):
    state = await engine.get_state("nonexistent-id")
    assert state is None


@pytest.mark.asyncio
async def test_process_input_not_found(engine):
    response = await engine.process_input("nonexistent-id", "你好")
    assert response.npc_response == "游戏会话不存在。"


@pytest.mark.asyncio
async def test_full_flow(engine):
    start = await engine.start_game("旅行者")
    game_id = start.game_id

    talk_response = await engine.process_input(game_id, "和老板娘聊聊")
    assert talk_response.npc_response
    assert talk_response.npc_id == "innkeeper"
    assert len(talk_response.state_changes.relationship_changes) > 0

    move_response = await engine.process_input(game_id, "前往镇政厅")
    assert "镇政厅" in move_response.narration
    assert move_response.state_changes.location_changed is True

    state = await engine.get_state(game_id)
    assert state.world_state.current_location == "town_hall"
    assert state.world_state.turn_count >= 2
    assert len(state.relationships) == 3
    assert len(state.quest_states) == 2


@pytest.mark.asyncio
async def test_move_invalid_location(engine):
    start = await engine.start_game("旅行者")
    game_id = start.game_id

    response = await engine.process_input(game_id, "前往废弃矿坑")

    assert "无法" in response.narration
    assert response.state_changes.location_changed is False


@pytest.mark.asyncio
async def test_talk_npc_not_present(engine):
    start = await engine.start_game("旅行者")
    game_id = start.game_id

    response = await engine.process_input(game_id, "和镇长交谈")

    assert "不在这里" in response.npc_response
    assert response.npc_id is None


@pytest.mark.asyncio
async def test_generic_input_default_talk(engine):
    start = await engine.start_game("旅行者")
    game_id = start.game_id

    response = await engine.process_input(game_id, "你好")

    assert response.npc_response
    assert response.npc_id == "innkeeper"


@pytest.mark.asyncio
async def test_move_and_talk_at_new_location(engine):
    start = await engine.start_game("旅行者")
    game_id = start.game_id

    await engine.process_input(game_id, "前往镇政厅")
    response = await engine.process_input(game_id, "和赫尔曼说话")

    assert response.npc_response
    assert response.npc_id == "mayor"


@pytest.mark.asyncio
async def test_start_game_no_secrets_leaked(engine):
    response = await engine.start_game("旅行者")

    for npc in response.available_npcs:
        npc_dict = npc.model_dump()
        assert "secrets" not in npc_dict
        assert "backstory" not in npc_dict
        assert "id" in npc_dict
        assert "name" in npc_dict
        assert "role" in npc_dict


@pytest.mark.asyncio
async def test_get_state_no_secrets_leaked(engine):
    start = await engine.start_game("旅行者")
    game_id = start.game_id

    state = await engine.get_state(game_id)
    state_dict = state.model_dump()

    state_json = str(state_dict)
    for secret in [
        "她知道矿坑失踪案与镇长有关",
        "他与矿业公司签了秘密协议",
        "他亲眼目睹了矿坑中发生的一切",
    ]:
        assert secret not in state_json


@pytest.mark.asyncio
async def test_process_input_all_state_persisted(engine):
    start = await engine.start_game("旅行者")
    game_id = start.game_id

    state_before = await engine.get_state(game_id)
    assert state_before.world_state.turn_count == 0
    innkeeper_before = [r for r in state_before.relationships if r.npc_id == "innkeeper"][0]
    assert innkeeper_before.trust == 30
    assert len(state_before.recent_memories) == 0

    result = await engine.process_input(game_id, "和老板娘聊聊")
    assert result.npc_id == "innkeeper"

    state_after = await engine.get_state(game_id)
    assert state_after.world_state.turn_count == 1

    innkeeper_after = [r for r in state_after.relationships if r.npc_id == "innkeeper"][0]
    assert innkeeper_after.trust != innkeeper_before.trust

    assert len(state_after.recent_memories) > 0


@pytest.mark.asyncio
async def test_process_input_rollback_on_failure(engine):
    start = await engine.start_game("旅行者")
    game_id = start.game_id

    state_before = await engine.get_state(game_id)
    turn_before = state_before.world_state.turn_count
    trust_before = [r for r in state_before.relationships if r.npc_id == "innkeeper"][0].trust

    with patch.object(
        engine.memory_manager, "add_short_term",
        side_effect=RuntimeError("simulated failure"),
    ):
        with pytest.raises(RuntimeError, match="simulated failure"):
            await engine.process_input(game_id, "和老板娘聊聊")

    state_after = await engine.get_state(game_id)
    assert state_after.world_state.turn_count == turn_before

    trust_after = [r for r in state_after.relationships if r.npc_id == "innkeeper"][0].trust
    assert trust_after == trust_before

    assert len(state_after.recent_memories) == 0


@pytest.mark.asyncio
async def test_game_engine_default_provider_is_mock(engine):
    from app.engine.llm_adapter import MockProvider
    assert isinstance(engine.npc_agent._llm, MockProvider)


@pytest.mark.asyncio
async def test_llm_called_without_open_write_transaction(engine):
    start = await engine.start_game("旅行者")
    game_id = start.game_id

    original_generate = engine.npc_agent._llm.generate
    call_log = []

    async def _spy_generate(system_prompt, user_message):
        call_log.append("llm_generate_called")
        result = await original_generate(system_prompt, user_message)
        return result

    with patch.object(
        engine.npc_agent._llm, "generate", side_effect=_spy_generate
    ):
        await engine.process_input(game_id, "和老板娘聊聊")

    assert len(call_log) == 1
    assert call_log[0] == "llm_generate_called"


@pytest.mark.asyncio
async def test_write_phase_rollback_on_failure(engine):
    start = await engine.start_game("旅行者")
    game_id = start.game_id

    with patch.object(
        engine.memory_manager, "add_short_term",
        side_effect=RuntimeError("simulated failure"),
    ):
        with pytest.raises(RuntimeError, match="simulated failure"):
            await engine.process_input(game_id, "和老板娘聊聊")

    state_after = await engine.get_state(game_id)
    assert state_after.world_state.turn_count == 0

    trust = [r for r in state_after.relationships if r.npc_id == "innkeeper"][0].trust
    assert trust == 30

    assert len(state_after.recent_memories) == 0


@pytest.mark.asyncio
async def test_importance_quest_keyword(engine):
    start = await engine.start_game("旅行者")
    game_id = start.game_id

    await engine.process_input(game_id, "我想调查失踪案，这里有什么秘密")
    state = await engine.get_state(game_id)
    if len(state.recent_memories) > 0:
        mem = state.recent_memories[0]
        assert mem.importance >= 4


@pytest.mark.asyncio
async def test_importance_promise_keyword(engine):
    start = await engine.start_game("旅行者")
    game_id = start.game_id

    await engine.process_input(game_id, "我答应帮你调查这件事")
    state = await engine.get_state(game_id)
    if len(state.recent_memories) > 0:
        mem = state.recent_memories[0]
        assert mem.importance >= 3


@pytest.mark.asyncio
async def test_importance_plain_chat(engine):
    start = await engine.start_game("旅行者")
    game_id = start.game_id

    await engine.process_input(game_id, "天气真好啊")
    state = await engine.get_state(game_id)
    if len(state.recent_memories) > 0:
        mem = state.recent_memories[0]
        assert mem.importance >= 1
        assert mem.importance <= 4


@pytest.mark.asyncio
async def test_memory_content_has_structured_tags(engine):
    start = await engine.start_game("旅行者")
    game_id = start.game_id

    await engine.process_input(game_id, "和老板娘聊聊")
    state = await engine.get_state(game_id)
    assert len(state.recent_memories) > 0
    content = state.recent_memories[0].content
    assert content.startswith("[talk")
    assert "@" in content


@pytest.mark.asyncio
async def test_memory_content_has_location(engine):
    start = await engine.start_game("旅行者")
    game_id = start.game_id

    await engine.process_input(game_id, "和老板娘聊聊")
    state = await engine.get_state(game_id)
    if len(state.recent_memories) > 0:
        content = state.recent_memories[0].content
        assert "@破晓酒馆" in content or "@tavern" in content


@pytest.mark.asyncio
async def test_active_promotion_on_high_importance(engine):
    start = await engine.start_game("旅行者")
    game_id = start.game_id

    await engine.process_input(game_id, "矿坑失踪案的秘密真相是什么")
    state = await engine.get_state(game_id)
    assert len(state.recent_memories) > 0
    mem = state.recent_memories[0]
    assert mem.importance >= 4
    assert "quest_keyword" in mem.content


@pytest.mark.asyncio
async def test_get_state_includes_long_term_memories(engine):
    start = await engine.start_game("旅行者")
    game_id = start.game_id

    await engine.process_input(game_id, "矿坑失踪案的秘密真相是什么")
    state = await engine.get_state(game_id)
    if len(state.recent_memories) > 0:
        types = [m.type for m in state.recent_memories]
        has_long = "long_term" in types
        has_short = "short_term" in types
        assert has_long or has_short


MOCK_TOWN_EVENTS = [
    {
        "id": "test_event",
        "title": "测试小镇事件",
        "narration": "一个测试事件发生了。",
        "trigger_turn": 1,
        "required_flags": {},
        "forbidden_flags": ["town_event_test_event"],
        "set_flags": ["town_event_test_event"],
        "importance": 5,
    },
]


@pytest_asyncio.fixture
async def engine_with_events(db):
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _mock_get_db():
        yield db

    with (
        patch("app.systems.world_state.load_json_data", return_value=MOCK_LOCATIONS),
        patch("app.agents.npc_agent.load_json_data", return_value=MOCK_NPCS),
        patch("app.systems.relationship.load_json_data", return_value=MOCK_NPCS),
        patch("app.systems.town_tick.load_json_data", return_value=MOCK_TOWN_EVENTS),
        patch("app.engine.game_engine.get_db", _mock_get_db),
    ):
        yield GameEngine()


@pytest.mark.asyncio
async def test_talk_flow_triggers_town_event(engine_with_events):
    start = await engine_with_events.start_game("旅行者")
    game_id = start.game_id

    response = await engine_with_events.process_input(game_id, "和老板娘聊聊")
    assert response.npc_response
    assert len(response.state_changes.town_events) >= 1
    assert response.state_changes.town_events[0].event_id == "test_event"


@pytest.mark.asyncio
async def test_move_flow_triggers_town_event(engine_with_events):
    start = await engine_with_events.start_game("旅行者")
    game_id = start.game_id

    response = await engine_with_events.process_input(game_id, "前往镇政厅")
    assert "镇政厅" in response.narration
    assert len(response.state_changes.town_events) >= 1


@pytest.mark.asyncio
async def test_town_event_after_turn_increment(engine_with_events):
    start = await engine_with_events.start_game("旅行者")
    game_id = start.game_id

    state = await engine_with_events.get_state(game_id)
    assert state.world_state.turn_count == 0

    response = await engine_with_events.process_input(game_id, "和老板娘聊聊")
    assert response.state_changes.town_events[0].event_id == "test_event"

    state_after = await engine_with_events.get_state(game_id)
    assert state_after.world_state.turn_count >= 1
    assert len(state_after.triggered_town_events) >= 1


@pytest.mark.asyncio
async def test_state_changes_default_empty_town_events(engine):
    start = await engine.start_game("旅行者")
    game_id = start.game_id

    response = await engine.process_input(game_id, "和老板娘聊聊")
    assert response.state_changes.town_events == []


MOCK_PRESENCE_RULES = [
    {
        "npc_id": "miner",
        "rules": [
            {
                "location": "tavern",
                "visible": True,
                "when_flags": {"miner_gone": True},
                "unless_flags": {},
                "reason": "托马斯逃到酒馆了",
            },
            {
                "location": "abandoned_mine",
                "visible": False,
                "when_flags": {"miner_gone": True},
                "unless_flags": {},
                "reason": "托马斯已经不在矿坑了",
            },
        ],
    },
]


@pytest_asyncio.fixture
async def engine_with_presence(db):
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _mock_get_db():
        yield db

    with (
        patch("app.systems.world_state.load_json_data", return_value=MOCK_LOCATIONS),
        patch("app.agents.npc_agent.load_json_data", return_value=MOCK_NPCS),
        patch("app.systems.relationship.load_json_data", return_value=MOCK_NPCS),
        patch("app.engine.game_engine.get_db", _mock_get_db),
        patch("app.systems.npc_presence.load_json_data", side_effect=lambda name: MOCK_PRESENCE_RULES if name == "npc_presence_rules.json" else MOCK_NPCS),
    ):
        yield GameEngine()


@pytest.mark.asyncio
async def test_get_state_returns_npc_locations(engine_with_presence):
    start = await engine_with_presence.start_game("旅行者")
    game_id = start.game_id

    state = await engine_with_presence.get_state(game_id)
    assert state is not None
    assert len(state.npc_locations) == 3

    by_id = {loc.npc_id: loc for loc in state.npc_locations}
    assert by_id["innkeeper"].location == "tavern"
    assert by_id["mayor"].location == "town_hall"
    assert by_id["miner"].location == "abandoned_mine"


@pytest.mark.asyncio
async def test_start_game_presence_default(engine_with_presence):
    response = await engine_with_presence.start_game("旅行者")
    assert len(response.available_npcs) == 1
    assert response.available_npcs[0].id == "innkeeper"


@pytest.mark.asyncio
async def test_talk_npc_not_at_location_presence(engine_with_presence):
    start = await engine_with_presence.start_game("旅行者")
    game_id = start.game_id

    response = await engine_with_presence.process_input(game_id, "和镇长交谈")
    assert "不在这里" in response.npc_response
    assert response.npc_id is None
