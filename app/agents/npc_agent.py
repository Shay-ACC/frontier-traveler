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
    _TAG_PATTERN = re.compile(r"^\[[^\]]*\]\s*")
    _NPC_RESPONSE_PATTERN = re.compile(r"，[^，]+回应「[^」]*」")

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

    @staticmethod
    def _sanitize_cross_memory_content(content: str) -> str:
        result = NPCAgent._TAG_PATTERN.sub("", content)
        result = NPCAgent._NPC_RESPONSE_PATTERN.sub("", result)
        result = result.replace("玩家说", "旅行者提到")
        return result.strip()

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
        cross_npc_memories: list[Memory] | None = None,
    ) -> tuple[str, str]:
        npc = self._npcs.get(npc_id)
        if npc is None:
            return "", player_message

        quest_knowledge = ""
        for qs in quest_states:
            quest_knowledge += f"- {qs.quest_id}: 当前阶段 {qs.current_stage}\n"

        memory_text = ""
        for mem in memories:
            label = "重要" if mem.importance >= 7 else "普通"
            memory_text += f"- [{label}] (第{mem.turn}轮) {mem.content}\n"

        cross_text = ""
        if cross_npc_memories:
            for mem in cross_npc_memories:
                cross_name = self._npcs.get(mem.npc_id)
                name = cross_name.name if cross_name else mem.npc_id
                label = "重要" if mem.importance >= 7 else "普通"
                safe_content = self._sanitize_cross_memory_content(mem.content)
                cross_text += f"- [{label}] (第{mem.turn}轮，来自与{name}的对话) {safe_content}\n"

        secrets_text = ""
        for i, secret in enumerate(npc.secrets, 1):
            secrets_text += f"{i}. {secret}\n"

        cross_section = ""
        if cross_text:
            cross_section = (
                "\n来自其他对话的玩家上下文：\n"
                "以下信息来自旅行者在其他场景或其他 NPC 对话中的经历，"
                "只用于帮助理解玩家当前输入。"
                "这些不代表你（{npc_name}）自己知道的事实。"
                "除非玩家在当前对话中主动提及，"
                "否则你不得表现为已经知道这些内容，"
                "也不得直接引用其他 NPC 的原话。\n"
                f"{cross_text}"
            ).format(npc_name=npc.name)

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
            f"你记得的事情（按重要程度排列）：\n{memory_text}"
            f"{cross_section}\n"
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
            f"第一部分是你的角色扮演回复（对话内容），可以包含动作描写用括号包裹。\n"
            f"第二部分是 [INSTRUCTIONS] 标记后的状态变更建议。\n"
            f"两部分之间用 [INSTRUCTIONS] 分隔，对话内容中不要出现 [INSTRUCTIONS] 标记。\n\n"
            f"指令格式（每行一条，可选，不要包含多余文字）：\n"
            f"QUEST:{{quest_id}}:{{action}}:{{detail}}\n"
            f"TRUST:{{npc_id}}:{{delta}}  （delta 范围 -5 到 +5）\n"
            f"FLAG:{{flag_name}}:{{value}}\n\n"
            f"输出示例：\n"
            f"（艾琳娜放下手中的杯子，叹了口气）\n"
            f"你看起来不像坏人...我可以告诉你，这镇子有些不对劲。\n"
            f"最近几个月，已经有三个人失踪了。都是矿工。\n\n"
            f"[INSTRUCTIONS]\n"
            f"TRUST:innkeeper:3\n"
            f"FLAG:heard_about_missing:true\n"
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
        cross_npc_memories: list[Memory] | None = None,
    ) -> NPCResponse:
        system_prompt, user_msg = self.build_prompt(
            npc_id, player_message, location_name, location_description,
            time_of_day, relationship, memories, quest_states,
            cross_npc_memories=cross_npc_memories,
        )
        raw = await self._llm.generate(system_prompt, user_msg)
        return self.parse_response(raw)
