import pytest
from unittest.mock import patch

from app.models.game_state import WorldStateModel
from app.systems.npc_presence import NpcPresenceSystem


MOCK_NPCS = [
    {
        "id": "innkeeper",
        "name": "艾琳娜",
        "role": "酒馆老板娘",
        "default_location": "tavern",
    },
    {
        "id": "mayor",
        "name": "赫尔曼",
        "role": "镇长",
        "default_location": "town_hall",
    },
    {
        "id": "miner",
        "name": "托马斯",
        "role": "矿工",
        "default_location": "abandoned_mine",
    },
]

MOCK_RULES = [
    {
        "npc_id": "miner",
        "rules": [
            {
                "location": "tavern",
                "visible": True,
                "when_flags": {"miner_gone": True},
                "unless_flags": {},
                "reason": "托马斯逃到酒馆寻求庇护",
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
    {
        "npc_id": "innkeeper",
        "rules": [
            {
                "location": "tavern",
                "visible": False,
                "when_flags": {"innkeeper_busy": True},
                "unless_flags": {},
                "reason": "艾琳娜正在忙",
            },
        ],
    },
    {
        "npc_id": "mayor",
        "rules": [
            {
                "location": "tavern",
                "visible": True,
                "when_flags": {"mayor_visible": True},
                "unless_flags": {"mayor_away": True},
                "reason": "赫尔曼来到了酒馆",
            },
        ],
    },
]


@pytest.fixture
def system():
    def mock_load(name):
        if name == "npcs.json":
            return MOCK_NPCS
        if name == "npc_presence_rules.json":
            return MOCK_RULES
        return []

    with patch("app.systems.npc_presence.load_json_data", side_effect=mock_load):
        yield NpcPresenceSystem()


def test_default_location_when_no_flags(system):
    ws = WorldStateModel(game_id="test")
    npcs = system.get_npcs_at_location(ws, "tavern")
    assert "innkeeper" in npcs
    assert "mayor" not in npcs
    assert "miner" not in npcs


def test_miner_default_at_mine(system):
    ws = WorldStateModel(game_id="test")
    npcs = system.get_npcs_at_location(ws, "abandoned_mine")
    assert "miner" in npcs


def test_miner_moves_to_tavern_when_gone(system):
    ws = WorldStateModel(game_id="test", flags={"miner_gone": True})
    mine_npcs = system.get_npcs_at_location(ws, "abandoned_mine")
    assert "miner" not in mine_npcs

    tavern_npcs = system.get_npcs_at_location(ws, "tavern")
    assert "miner" in tavern_npcs


def test_visible_false_hides_npc(system):
    ws = WorldStateModel(game_id="test", flags={"innkeeper_busy": True})
    tavern_npcs = system.get_npcs_at_location(ws, "tavern")
    assert "innkeeper" not in tavern_npcs


def test_unless_flags_block_rule(system):
    ws = WorldStateModel(game_id="test", flags={"mayor_visible": True})
    npcs = system.get_npcs_at_location(ws, "town_hall")
    assert "mayor" not in npcs

    ws2 = WorldStateModel(game_id="test", flags={"mayor_visible": True, "mayor_away": True})
    npcs2 = system.get_npcs_at_location(ws2, "town_hall")
    assert "mayor" in npcs2


def test_first_match_wins(system):
    ws = WorldStateModel(game_id="test", flags={"miner_gone": True})
    mine_npcs = system.get_npcs_at_location(ws, "abandoned_mine")
    assert "miner" not in mine_npcs

    tavern_npcs = system.get_npcs_at_location(ws, "tavern")
    assert "miner" in tavern_npcs


def test_get_all_npc_locations(system):
    ws = WorldStateModel(game_id="test")
    locations = system.get_all_npc_locations(ws)
    assert len(locations) == 3

    by_id = {loc.npc_id: loc for loc in locations}
    assert by_id["innkeeper"].location == "tavern"
    assert by_id["mayor"].location == "town_hall"
    assert by_id["miner"].location == "abandoned_mine"
    assert all(loc.visible for loc in locations)


def test_get_all_npc_locations_with_flags(system):
    ws = WorldStateModel(game_id="test", flags={"miner_gone": True})
    locations = system.get_all_npc_locations(ws)
    by_id = {loc.npc_id: loc for loc in locations}
    assert by_id["miner"].location == "tavern"
    assert by_id["miner"].visible is True


def test_get_absence_reason_npc_not_at_location(system):
    ws = WorldStateModel(game_id="test")
    reason = system.get_absence_reason(ws, "miner", "tavern")
    assert reason is None

    ws2 = WorldStateModel(game_id="test", flags={"miner_gone": True})
    reason2 = system.get_absence_reason(ws2, "miner", "abandoned_mine")
    assert reason2 is not None
    assert "酒馆" in reason2


def test_get_absence_reason_npc_visible_at_location(system):
    ws = WorldStateModel(game_id="test")
    reason = system.get_absence_reason(ws, "innkeeper", "tavern")
    assert reason is None


def test_get_absence_reason_invisible_at_location(system):
    ws = WorldStateModel(game_id="test", flags={"innkeeper_busy": True})
    reason = system.get_absence_reason(ws, "innkeeper", "tavern")
    assert reason is not None


def test_miner_gone_flag_changes_location(system):
    ws_before = WorldStateModel(game_id="test")
    locs_before = {loc.npc_id: loc for loc in system.get_all_npc_locations(ws_before)}
    assert locs_before["miner"].location == "abandoned_mine"

    ws_after = WorldStateModel(game_id="test", flags={"miner_gone": True})
    locs_after = {loc.npc_id: loc for loc in system.get_all_npc_locations(ws_after)}
    assert locs_after["miner"].location == "tavern"
