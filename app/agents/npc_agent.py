import re
from dataclasses import dataclass

from app.database import load_json_data
from app.engine.llm_adapter import BaseLLMProvider
from app.models.npc import NPC
from app.models.memory import Memory
from app.models.relationship import Relationship
from app.models.quest import QuestState


@dataclass
class ParsedInstruction:
    type: str
    quest_id: str = ""
    action: str = ""
    detail: str = ""
    npc_id: str = ""
    delta: int = 0
    flag_name: str = ""
    flag_value: str = ""


@dataclass
class NPCResponse:
    dialogue: str
    instructions: list[ParsedInstruction]


class NPCAgent:
    def __init__(self, llm_provider: BaseLLMProvider):
        self._llm = llm_provider
        self._npcs: dict[str, NPC] = {}
        self._load_npcs()

    def _load_npcs(self):
        data = load_json_data("npcs.json")
        for item in data:
            npc = NPC(**item)
            self._npcs[npc.id] = npc

    def get_npc(self, npc_id: str) -> NPC | None:
        return self._npcs.get(npc_id)

    def build_prompt(
        self,
        npc_id: str,
        player_message: str,
        location_name: str,
        location_description: str,
        time_of_day: str,
        relationship: Relationship,
        memories: list[Memory],
        quest_states: list[QuestState],
    ) -> tuple[str, str]:
        npc = self._npcs.get(npc_id)
        if npc is None:
            return "", player_message

        quest_knowledge = ""
        for qs in quest_states:
            quest_knowledge += f"- {qs.quest_id}: 当前阶段 {qs.current_stage}\n"

        memory_text = ""
        for mem in memories:
            memory_text += f"- (第{mem.turn}轮) {mem.content}\n"

        secrets_text = ""
        for i, secret in enumerate(npc.secrets, 1):
            secrets_text += f"{i}. {secret}\n"

        system_prompt = (
            f"你是《边境小镇：记忆旅人》中的 NPC：{npc.name}。\n"
            f"{npc.role}，{npc.personality}。\n"
            f"{npc.backstory}\n"
            f"你的对话风格：{npc.dialogue_style}\n\n"
            f"当前状态：\n"
            f"- 地点：{location_name} - {location_description}\n"
            f"- 时间：{time_of_day}\n"
            f"- 你对旅行者的信任度：{relationship.trust}/100\n"
            f"- 你对旅行者的好感度：{relationship.affection}/100\n"
            f"- 关系状态：{relationship.status}\n\n"
            f"关于以下任务的知识：\n{quest_knowledge}\n"
            f"你记得的事情：\n{memory_text}\n"
            f"你的秘密（只在特定条件下透露）：\n{secrets_text}\n\n"
            f"严格规则：\n"
            f"1. 始终保持角色，不要跳出角色\n"
            f"2. 根据信任度调整透露信息的多少：\n"
            f"   - trust < 20：拒绝交谈或撒谎\n"
            f"   - trust 20-40：只说表面信息\n"
            f"   - trust 40-70：愿意分享一些内情\n"
            f"   - trust > 70：可以透露秘密\n"
            f"3. 不要一次透露所有信息，保持悬念\n"
            f"4. 回复结尾不要使用问号引导玩家\n\n"
            f"输出格式（严格遵守）：\n"
            f"[对话内容]\n"
            f"（你的角色扮演回复，可以包含动作描写用括号包裹）\n\n"
            f"[INSTRUCTIONS]\n"
            f"（如有状态变更建议，每行一条，可选）\n"
            f"QUEST:{{quest_id}}:{{action}}:{{detail}}\n"
            f"TRUST:{{npc_id}}:{{delta}}\n"
            f"FLAG:{{flag_name}}:{{value}}\n"
        )

        user_msg = f"玩家说：{player_message}"

        return system_prompt, user_msg

    def parse_response(self, raw_response: str) -> NPCResponse:
        dialogue = raw_response
        instructions = []

        if "[INSTRUCTIONS]" in raw_response:
            parts = raw_response.split("[INSTRUCTIONS]", 1)
            dialogue = parts[0].strip()
            instruction_block = parts[1].strip()

            for line in instruction_block.split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    if line.startswith("QUEST:"):
                        parts = line[6:].split(":", 2)
                        if len(parts) >= 2:
                            instructions.append(ParsedInstruction(
                                type="QUEST",
                                quest_id=parts[0],
                                action=parts[1],
                                detail=parts[2] if len(parts) > 2 else "",
                            ))
                    elif line.startswith("TRUST:"):
                        parts = line[6:].split(":", 1)
                        if len(parts) == 2:
                            instructions.append(ParsedInstruction(
                                type="TRUST",
                                npc_id=parts[0],
                                delta=int(parts[1]),
                            ))
                    elif line.startswith("FLAG:"):
                        parts = line[5:].split(":", 1)
                        if len(parts) == 2:
                            instructions.append(ParsedInstruction(
                                type="FLAG",
                                flag_name=parts[0],
                                flag_value=parts[1],
                            ))
                except (ValueError, IndexError):
                    continue

        return NPCResponse(dialogue=dialogue, instructions=instructions)

    async def get_npc_response(
        self,
        npc_id: str,
        player_message: str,
        location_name: str,
        location_description: str,
        time_of_day: str,
        relationship: Relationship,
        memories: list[Memory],
        quest_states: list[QuestState],
    ) -> NPCResponse:
        system_prompt, user_msg = self.build_prompt(
            npc_id, player_message, location_name, location_description,
            time_of_day, relationship, memories, quest_states,
        )
        raw = await self._llm.generate(system_prompt, user_msg)
        return self.parse_response(raw)
