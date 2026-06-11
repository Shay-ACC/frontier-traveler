import pytest
from unittest.mock import patch

from app.models.api_schemas import StateChanges, TownEvent
from app.models.game_state import WorldStateModel
from app.systems.town_tick import TownTickSystem


MOCK_EVENTS = [
    {
        "id": "test_event_1",
        "title": "测试事件1",
        "narration": "测试叙述1",
        "trigger_turn": 3,
        "required_flags": {},
        "forbidden_flags": ["town_event_test_event_1"],
        "set_flags": ["town_event_test_event_1", "flag_a"],
        "importance": 5,
    },
    {
        "id": "test_event_2",
        "title": "测试事件2",
        "narration": "测试叙述2",
        "trigger_turn": 5,
        "required_flags": {"flag_a": True},
        "forbidden_flags": ["town_event_test_event_2"],
        "set_flags": ["town_event_test_event_2"],
        "importance": 7,
    },
    {
        "id": "test_event_3",
        "title": "测试事件3",
        "narration": "需要前置flag",
        "trigger_turn": 2,
        "required_flags": {"never_set_flag": True},
        "forbidden_flags": ["town_event_test_event_3"],
        "set_flags": ["town_event_test_event_3"],
        "importance": 3,
    },
]


@pytest.fixture
def system():
    with patch("app.systems.town_tick.load_json_data", return_value=MOCK_EVENTS):
        yield TownTickSystem()


def test_tick_no_events_when_turn_too_low(system):
    ws = WorldStateModel(game_id="test", turn_count=0)
    sc = StateChanges()
    result = system.tick(ws, sc)
    assert result == []


def test_tick_triggers_on_exact_turn(system):
    ws = WorldStateModel(game_id="test", turn_count=3)
    sc = StateChanges()
    result = system.tick(ws, sc)
    assert len(result) == 1
    assert result[0].event_id == "test_event_1"


def test_tick_triggers_after_turn(system):
    ws = WorldStateModel(game_id="test", turn_count=10)
    sc = StateChanges()
    result = system.tick(ws, sc)
    ids = [r.event_id for r in result]
    assert "test_event_1" in ids
    assert "test_event_2" in ids


def test_tick_requires_flags(system):
    ws = WorldStateModel(game_id="test", turn_count=10)
    sc = StateChanges()
    result = system.tick(ws, sc)
    assert all(r.event_id != "test_event_3" for r in result)


def test_tick_respects_forbidden_flags(system):
    ws = WorldStateModel(
        game_id="test",
        turn_count=3,
        flags={"town_event_test_event_1": True},
    )
    sc = StateChanges()
    result = system.tick(ws, sc)
    assert all(r.event_id != "test_event_1" for r in result)


def test_tick_no_repeat_after_trigger(system):
    ws = WorldStateModel(game_id="test", turn_count=3)
    sc = StateChanges()
    result1 = system.tick(ws, sc)
    assert len(result1) == 1
    result2 = system.tick(ws, sc)
    assert len(result2) == 0


def test_tick_sets_flags(system):
    ws = WorldStateModel(game_id="test", turn_count=3)
    sc = StateChanges()
    system.tick(ws, sc)
    assert ws.flags.get("town_event_test_event_1") is True
    assert ws.flags.get("flag_a") is True
    assert sc.flag_changes.get("flag_a") is True


def test_tick_multiple_events(system):
    ws = WorldStateModel(game_id="test", turn_count=5, flags={"flag_a": True})
    sc = StateChanges()
    result = system.tick(ws, sc)
    ids = [r.event_id for r in result]
    assert "test_event_1" in ids
    assert "test_event_2" in ids


def test_tick_returns_narration(system):
    ws = WorldStateModel(game_id="test", turn_count=3)
    sc = StateChanges()
    result = system.tick(ws, sc)
    assert result[0].title == "测试事件1"
    assert result[0].narration == "测试叙述1"
    assert result[0].importance == 5


def test_get_triggered_events(system):
    ws = WorldStateModel(
        game_id="test",
        turn_count=3,
        flags={"town_event_test_event_1": True},
    )
    result = system.get_triggered_events(ws)
    assert len(result) == 1
    assert result[0].event_id == "test_event_1"
    assert result[0].title == "测试事件1"


def test_get_triggered_events_empty(system):
    ws = WorldStateModel(game_id="test", turn_count=0)
    result = system.get_triggered_events(ws)
    assert result == []
