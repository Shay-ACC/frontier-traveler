from datetime import datetime
from unittest.mock import patch

import pytest

from app.agents.npc_agent import NPCAgent
from app.engine.llm_adapter import MockProvider
from app.models.memory import Memory
from app.models.quest import QuestState
from app.models.relationship import Relationship

MOCK_NPCS = [
    {
        "id": "innkeeper",
        "name": "艾琳娜",
        "role": "酒馆老板娘",
        "personality": "精明、谨慎、善于察言观色。对陌生人保持距离，但一旦信任就会非常热心。",
        "backstory": "艾琳娜在边境小镇经营破晓酒馆已有十年。",
        "default_location": "tavern",
        "dialogue_style": "说话简洁有力，偶尔带点讽刺。",
        "secrets": ["她知道矿坑失踪案与镇长有关"],
    },
    {
        "id": "mayor",
        "name": "赫尔曼",
        "role": "镇长",
        "personality": "表面和善、内心深沉、善于回避话题。",
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


@pytest.fixture
def mock_provider():
    return MockProvider()


@pytest.fixture
def agent(mock_provider):
    with patch("app.agents.npc_agent.load_json_data", return_value=MOCK_NPCS):
        return NPCAgent(mock_provider)


def test_build_prompt_contains_character_setting(agent):
    relationship = Relationship(game_id="g1", npc_id="innkeeper", trust=30)
    system_prompt, _ = agent.build_prompt(
        npc_id="innkeeper",
        player_message="你好",
        location_name="破晓酒馆",
        location_description="一个温暖的酒馆",
        time_of_day="evening",
        relationship=relationship,
        memories=[],
        quest_states=[],
    )
    assert "艾琳娜" in system_prompt
    assert "酒馆老板娘" in system_prompt
    assert "精明" in system_prompt


def test_build_prompt_contains_trust_level(agent):
    relationship = Relationship(game_id="g1", npc_id="innkeeper", trust=45)
    system_prompt, _ = agent.build_prompt(
        npc_id="innkeeper",
        player_message="你好",
        location_name="破晓酒馆",
        location_description="一个温暖的酒馆",
        time_of_day="evening",
        relationship=relationship,
        memories=[],
        quest_states=[],
    )
    assert "45" in system_prompt
    assert "信任度" in system_prompt


def test_build_prompt_contains_memories(agent):
    relationship = Relationship(game_id="g1", npc_id="innkeeper", trust=30)
    memories = [
        Memory(
            id="m1",
            game_id="g1",
            npc_id="innkeeper",
            type="short_term",
            content="旅行者问了关于失踪案的事",
            importance=5,
            turn=1,
            created_at=datetime(2025, 1, 1, 12, 0, 0),
        ),
    ]
    system_prompt, _ = agent.build_prompt(
        npc_id="innkeeper",
        player_message="你好",
        location_name="破晓酒馆",
        location_description="一个温暖的酒馆",
        time_of_day="evening",
        relationship=relationship,
        memories=memories,
        quest_states=[],
    )
    assert "旅行者问了关于失踪案的事" in system_prompt
    assert "第1轮" in system_prompt


def test_parse_response_with_instructions(agent):
    raw = (
        "（艾琳娜擦着杯子）\n"
        "欢迎来到破晓酒馆。\n\n"
        "[INSTRUCTIONS]\n"
        "TRUST:innkeeper:1\n"
        "FLAG:heard_about_missing:true\n"
    )
    response = agent.parse_response(raw)
    assert "艾琳娜" in response.dialogue
    assert "INSTRUCTIONS" not in response.dialogue
    trust_instr = [i for i in response.instructions if i.type == "TRUST"]
    assert len(trust_instr) == 1
    assert trust_instr[0].npc_id == "innkeeper"
    assert trust_instr[0].delta == 1
    flag_instr = [i for i in response.instructions if i.type == "FLAG"]
    assert len(flag_instr) == 1
    assert flag_instr[0].flag_name == "heard_about_missing"
    assert flag_instr[0].flag_value == "true"


def test_parse_response_quest_instruction(agent):
    raw = (
        "对话内容\n\n"
        "[INSTRUCTIONS]\n"
        "QUEST:missing_case:start:开始调查\n"
    )
    response = agent.parse_response(raw)
    quest_instr = [i for i in response.instructions if i.type == "QUEST"]
    assert len(quest_instr) == 1
    assert quest_instr[0].quest_id == "missing_case"
    assert quest_instr[0].action == "start"
    assert quest_instr[0].detail == "开始调查"


def test_parse_response_no_instructions(agent):
    raw = "（艾琳娜微笑着）欢迎。"
    response = agent.parse_response(raw)
    assert response.dialogue == raw
    assert response.instructions == []


def test_parse_response_invalid_instructions_ignored(agent):
    raw = (
        "对话内容\n\n"
        "[INSTRUCTIONS]\n"
        "TRUST:innkeeper:abc\n"
        "INVALID_LINE\n"
        "QUEST:only_one_part\n"
    )
    response = agent.parse_response(raw)
    assert response.dialogue == "对话内容"
    assert len(response.instructions) == 0


@pytest.mark.asyncio
async def test_get_npc_response_integration(agent):
    relationship = Relationship(game_id="g1", npc_id="innkeeper", trust=30)
    quest_states = [
        QuestState(
            quest_id="missing_case",
            current_stage="not_started",
            completed=False,
            stage_history=[],
        ),
    ]
    response = await agent.get_npc_response(
        npc_id="innkeeper",
        player_message="你好",
        location_name="破晓酒馆",
        location_description="一个温暖的酒馆",
        time_of_day="evening",
        relationship=relationship,
        memories=[],
        quest_states=quest_states,
    )
    assert response.dialogue != ""
    assert len(response.instructions) > 0


def test_build_prompt_memory_importance_labels(agent):
    relationship = Relationship(game_id="g1", npc_id="innkeeper", trust=30)
    memories = [
        Memory(
            id="m1",
            game_id="g1",
            npc_id="innkeeper",
            type="long_term",
            content="重要记忆",
            importance=8,
            turn=1,
            created_at=datetime(2025, 1, 1, 12, 0, 0),
        ),
        Memory(
            id="m2",
            game_id="g1",
            npc_id="innkeeper",
            type="short_term",
            content="普通记忆",
            importance=3,
            turn=2,
            created_at=datetime(2025, 1, 1, 12, 0, 0),
        ),
    ]
    system_prompt, _ = agent.build_prompt(
        npc_id="innkeeper",
        player_message="你好",
        location_name="破晓酒馆",
        location_description="一个温暖的酒馆",
        time_of_day="evening",
        relationship=relationship,
        memories=memories,
        quest_states=[],
    )
    assert "[重要]" in system_prompt
    assert "[普通]" in system_prompt


def test_build_prompt_cross_npc_memories(agent):
    relationship = Relationship(game_id="g1", npc_id="innkeeper", trust=30)
    cross_memories = [
        Memory(
            id="m1",
            game_id="g1",
            npc_id="mayor",
            type="long_term",
            content="镇长提到了矿坑",
            importance=8,
            turn=3,
            created_at=datetime(2025, 1, 1, 12, 0, 0),
        ),
    ]
    system_prompt, _ = agent.build_prompt(
        npc_id="innkeeper",
        player_message="你好",
        location_name="破晓酒馆",
        location_description="一个温暖的酒馆",
        time_of_day="evening",
        relationship=relationship,
        memories=[],
        quest_states=[],
        cross_npc_memories=cross_memories,
    )
    assert "玩家上下文" in system_prompt
    assert "不代表" in system_prompt
    assert "不得" in system_prompt
    assert "赫尔曼" in system_prompt or "mayor" in system_prompt
    assert "镇长提到了矿坑" in system_prompt


def test_build_prompt_cross_npc_knowledge_constraint(agent):
    relationship = Relationship(game_id="g1", npc_id="innkeeper", trust=30)
    cross_memories = [
        Memory(
            id="m1",
            game_id="g1",
            npc_id="mayor",
            type="long_term",
            content="test",
            importance=8,
            turn=1,
            created_at=datetime(2025, 1, 1, 12, 0, 0),
        ),
    ]
    system_prompt, _ = agent.build_prompt(
        npc_id="innkeeper",
        player_message="你好",
        location_name="破晓酒馆",
        location_description="一个温暖的酒馆",
        time_of_day="evening",
        relationship=relationship,
        memories=[],
        quest_states=[],
        cross_npc_memories=cross_memories,
    )
    assert "自己知道" in system_prompt
    assert "引用其他 NPC 的原话" in system_prompt or "引用其他NPC的原话" in system_prompt
    assert "艾琳娜" in system_prompt


def test_build_prompt_no_cross_section_when_empty(agent):
    relationship = Relationship(game_id="g1", npc_id="innkeeper", trust=30)
    system_prompt, _ = agent.build_prompt(
        npc_id="innkeeper",
        player_message="你好",
        location_name="破晓酒馆",
        location_description="一个温暖的酒馆",
        time_of_day="evening",
        relationship=relationship,
        memories=[],
        quest_states=[],
        cross_npc_memories=[],
    )
    assert "玩家上下文" not in system_prompt


def test_sanitize_cross_memory_content_strips_tags(agent):
    raw = "[talk|trust+3|quest:missing_case] 第3轮@破晓酒馆：玩家说「你好」，艾琳娜回应「最近有人失踪了」"
    result = NPCAgent._sanitize_cross_memory_content(raw)
    assert "[" not in result
    assert "talk" not in result
    assert "trust+3" not in result
    assert "quest:missing_case" not in result
    assert "第3轮@破晓酒馆" in result
    assert "旅行者提到" in result


def test_sanitize_cross_memory_content_strips_npc_response(agent):
    raw = "第3轮@破晓酒馆：玩家说「你好」，艾琳娜回应「最近有人失踪了」"
    result = NPCAgent._sanitize_cross_memory_content(raw)
    assert "回应" not in result
    assert "最近有人失踪了" not in result
    assert "旅行者提到" in result


def test_cross_npc_memories_no_npc_response_in_prompt(agent):
    relationship = Relationship(game_id="g1", npc_id="innkeeper", trust=30)
    cross_memories = [
        Memory(
            id="m1",
            game_id="g1",
            npc_id="mayor",
            type="long_term",
            content="[talk|trust+3] 第5轮@市政厅：玩家说「矿坑的事」，赫尔曼回应「我什么都不知道」",
            importance=8,
            turn=5,
            created_at=datetime(2025, 1, 1, 12, 0, 0),
        ),
    ]
    system_prompt, _ = agent.build_prompt(
        npc_id="innkeeper",
        player_message="你好",
        location_name="破晓酒馆",
        location_description="一个温暖的酒馆",
        time_of_day="evening",
        relationship=relationship,
        memories=[],
        quest_states=[],
        cross_npc_memories=cross_memories,
    )
    assert "我什么都不知道" not in system_prompt
    assert "trust+3" not in system_prompt
    assert "[talk" not in system_prompt
    assert "旅行者提到" in system_prompt


def test_own_memories_keep_full_content(agent):
    relationship = Relationship(game_id="g1", npc_id="innkeeper", trust=30)
    own_memories = [
        Memory(
            id="m1",
            game_id="g1",
            npc_id="innkeeper",
            type="short_term",
            content="[talk|trust+3] 第3轮@破晓酒馆：玩家说「你好」，艾琳娜回应「欢迎」",
            importance=5,
            turn=3,
            created_at=datetime(2025, 1, 1, 12, 0, 0),
        ),
    ]
    system_prompt, _ = agent.build_prompt(
        npc_id="innkeeper",
        player_message="你好",
        location_name="破晓酒馆",
        location_description="一个温暖的酒馆",
        time_of_day="evening",
        relationship=relationship,
        memories=own_memories,
        quest_states=[],
    )
    assert "[talk|trust+3]" in system_prompt
    assert "艾琳娜回应" in system_prompt
