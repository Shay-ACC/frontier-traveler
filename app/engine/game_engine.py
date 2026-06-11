import uuid

from app.agents.npc_agent import NPCAgent, ParsedInstruction
from app.database import get_db
from app.engine.llm_adapter import create_provider
from app.models.api_schemas import (
    GameStateResponse,
    PlayerInputResponse,
    PublicNPC,
    QuestUpdate,
    RelationshipChange,
    StartGameResponse,
    StateChanges,
)
from app.models.game_state import WorldStateModel
from app.models.location import Location
from app.models.memory import Memory
from app.models.npc import NPC
from app.models.quest import QuestState
from app.models.relationship import Relationship
from app.systems.memory import MemoryManager
from app.systems.quest import QuestManager
from app.systems.relationship import RelationshipManager
from app.systems.town_tick import TownTickSystem
from app.systems.world_state import WorldState


class GameEngine:
    QUEST_KEYWORDS = {"失踪", "账本", "矿坑", "秘密", "协议", "毒气", "灭口", "真相", "线索", "调查"}
    PROMISE_KEYWORDS = {"答应", "保证", "承诺", "发誓", "威胁", "报警", "举报", "帮忙", "帮助"}

    def __init__(self):
        self.world_state = WorldState()
        self.quest_manager = QuestManager()
        self.relationship_manager = RelationshipManager()
        self.memory_manager = MemoryManager()
        self.npc_agent = NPCAgent(create_provider())
        self.town_tick_system = TownTickSystem()
        self._sessions: dict[str, dict] = {}

    async def start_game(self, player_name: str = "旅行者") -> StartGameResponse:
        game_id = str(uuid.uuid4())
        async with get_db() as db:
            ws = await WorldState.create(db, game_id)
            await db.execute(
                "UPDATE games SET player_name = ? WHERE game_id = ?",
                (player_name, game_id),
            )
            await db.commit()
            await self.relationship_manager.init_relationships(db, game_id)
            await self.quest_manager.init_quest_states(db, game_id)

            location = self.world_state.get_location(ws.current_location)
            npc_ids = self.world_state.get_available_npcs(ws.current_location)
            npcs = []
            for npc_id in npc_ids:
                npc = self.npc_agent.get_npc(npc_id)
                if npc:
                    npcs.append(PublicNPC(
                        id=npc.id,
                        name=npc.name,
                        role=npc.role,
                        personality=npc.personality,
                        dialogue_style=npc.dialogue_style,
                        default_location=npc.default_location,
                    ))

            opening = (
                "你是一名旅行者，在漫长的旅途中来到了一个偏远的边境小镇。\n"
                "空气中弥漫着不安的气息，镇上的人们似乎都在隐藏着什么。\n"
                "你推开了破晓酒馆的大门，决定在这里歇歇脚，顺便了解一下情况..."
            )

            return StartGameResponse(
                game_id=game_id,
                opening_narrative=opening,
                current_location=location,
                available_npcs=npcs,
            )

    async def process_input(self, game_id: str, message: str) -> PlayerInputResponse:
        intent = self._parse_intent(message)

        if intent["type"] == "move":
            async with get_db() as db:
                ws = await WorldState.load(db, game_id)
                if ws is None:
                    return self._not_found_response()
                try:
                    result = await self._handle_move(db, ws, intent, message)
                except Exception:
                    await db.rollback()
                    raise
                await db.commit()
                return result

        return await self._execute_talk_flow(game_id, intent, message)

    def _not_found_response(self) -> PlayerInputResponse:
        return PlayerInputResponse(
            npc_response="游戏会话不存在。",
            npc_id=None,
            narration="",
            state_changes=StateChanges(),
            available_actions=[],
        )

    def _parse_intent(self, message: str) -> dict:
        location_keywords = {
            "tavern": ["酒馆", "破晓酒馆", "tavern"],
            "town_hall": ["镇政厅", "市政厅", "town_hall"],
            "abandoned_mine": ["矿坑", "废弃矿坑", "mine"],
        }

        npc_keywords = {
            "innkeeper": ["老板娘", "艾琳娜", "innkeeper"],
            "mayor": ["镇长", "赫尔曼", "mayor"],
            "miner": ["矿工", "托马斯", "miner"],
        }

        move_words = ["前往", "去", "到", "移动", "走", "进入", "去到"]
        talk_words = ["聊", "说话", "交谈", "问", "打听", "谈谈", "对话", "说话"]

        target_npc = None
        for npc_id, keywords in npc_keywords.items():
            for kw in keywords:
                if kw in message:
                    target_npc = npc_id
                    break
            if target_npc:
                break

        has_talk_intent = any(w in message for w in talk_words) or target_npc is not None

        target_location = None
        for loc_id, keywords in location_keywords.items():
            for kw in keywords:
                if kw in message:
                    target_location = loc_id
                    break
            if target_location:
                break

        has_move_intent = any(w in message for w in move_words) and target_location is not None

        if has_talk_intent and target_npc:
            return {"type": "talk", "npc_id": target_npc}

        if has_move_intent:
            return {"type": "move", "target_location": target_location}

        return {"type": "generic"}

    async def _handle_move(
        self, db, ws: WorldStateModel, intent: dict, message: str
    ) -> PlayerInputResponse:
        target = intent.get("target_location")
        if not target:
            return PlayerInputResponse(
                npc_response="",
                npc_id=None,
                narration="你想去哪里？",
                state_changes=StateChanges(),
                available_actions=self._get_available_actions(ws),
            )

        if not self.world_state.can_move_to(ws.current_location, target):
            return PlayerInputResponse(
                npc_response="",
                npc_id=None,
                narration="你无法从当前位置直接前往那里。",
                state_changes=StateChanges(),
                available_actions=self._get_available_actions(ws),
            )

        ws.current_location = target
        ws.turn_count += 1
        await WorldState.save(db, ws, auto_commit=False)

        location = self.world_state.get_location(target)
        narration = f"你来到了{location.name}。\n{location.description}"

        state_changes = StateChanges(location_changed=True, new_location=target)
        await self._try_advance_quests(db, ws, state_changes, npc_id=None)
        town_events = self.town_tick_system.tick(ws, state_changes)
        state_changes.town_events = town_events
        if town_events:
            await WorldState.save(db, ws, auto_commit=False)

        return PlayerInputResponse(
            npc_response="",
            npc_id=None,
            narration=narration,
            state_changes=state_changes,
            available_actions=self._get_available_actions(ws),
        )

    async def _execute_talk_flow(
        self, game_id: str, intent: dict, message: str
    ) -> PlayerInputResponse:
        is_generic = intent.get("type") == "generic"

        async with get_db() as db:
            ws = await WorldState.load(db, game_id)
            if ws is None:
                return self._not_found_response()

            talk_ctx = await self._build_talk_context(db, ws, intent)

            if talk_ctx is None:
                if is_generic:
                    ws.turn_count += 1
                    await WorldState.save(db, ws, auto_commit=False)
                    await db.commit()
                    return PlayerInputResponse(
                        npc_response="",
                        npc_id=None,
                        narration="你环顾四周，这里空无一人。",
                        state_changes=StateChanges(),
                        available_actions=self._get_available_actions(ws),
                    )
                return PlayerInputResponse(
                    npc_response="这里没有人可以交谈。",
                    npc_id=None,
                    narration="",
                    state_changes=StateChanges(),
                    available_actions=self._get_available_actions(ws),
                )

            if "error" in talk_ctx:
                return PlayerInputResponse(
                    npc_response=talk_ctx["error"],
                    npc_id=None,
                    narration="",
                    state_changes=StateChanges(),
                    available_actions=self._get_available_actions(ws),
                )

        npc_response = await self.npc_agent.get_npc_response(
            npc_id=talk_ctx["npc_id"],
            player_message=message,
            location_name=talk_ctx["location"].name,
            location_description=talk_ctx["location"].description,
            time_of_day=talk_ctx["time_of_day"],
            relationship=talk_ctx["relationship"],
            memories=talk_ctx["memories"],
            cross_npc_memories=talk_ctx.get("cross_npc_memories", []),
            quest_states=talk_ctx["quest_states"],
        )

        async with get_db() as db:
            ws = await WorldState.load(db, game_id)
            if ws is None:
                return self._not_found_response()
            try:
                result = await self._apply_talk_result(
                    db, ws, talk_ctx["npc_id"], npc_response, message
                )
            except Exception:
                await db.rollback()
                raise
            await db.commit()
            return result

    async def _build_talk_context(
        self, db, ws: WorldStateModel, intent: dict
    ) -> dict | None:
        npc_id = intent.get("npc_id")
        if not npc_id:
            npcs = self.world_state.get_available_npcs(ws.current_location)
            if npcs:
                npc_id = npcs[0]

        if not npc_id:
            return None

        available_npcs = self.world_state.get_available_npcs(ws.current_location)
        if npc_id not in available_npcs:
            npc = self.npc_agent.get_npc(npc_id)
            npc_name = npc.name if npc else npc_id
            return {"error": f"{npc_name}不在这里。"}

        location = self.world_state.get_location(ws.current_location)
        relationship = await self.relationship_manager.get(db, ws.game_id, npc_id)
        if relationship is None:
            relationship = Relationship(game_id=ws.game_id, npc_id=npc_id)

        memories, cross_npc_memories = await self.memory_manager.recall_with_context(db, ws.game_id, npc_id, auto_commit=True)
        quest_states = await self.quest_manager.get_all_states(db, ws.game_id)

        return {
            "npc_id": npc_id,
            "location": location,
            "time_of_day": ws.time_of_day,
            "relationship": relationship,
            "memories": memories,
            "cross_npc_memories": cross_npc_memories,
            "quest_states": quest_states,
        }

    async def _apply_talk_result(
        self, db, ws: WorldStateModel, npc_id: str,
        npc_response, message: str
    ) -> PlayerInputResponse:
        npc = self.npc_agent.get_npc(npc_id)

        ws.turn_count += 1
        await WorldState.save(db, ws, auto_commit=False)

        state_changes = StateChanges()
        await self._dispatch_instructions(
            db, ws, npc_id, npc_response.instructions, state_changes
        )
        await self._try_advance_quests(db, ws, state_changes, npc_id=npc_id)
        town_events = self.town_tick_system.tick(ws, state_changes)
        state_changes.town_events = town_events
        if town_events:
            await WorldState.save(db, ws, auto_commit=False)

        importance = self._calculate_importance(message, npc_response.instructions, state_changes)

        location = self.world_state.get_location(ws.current_location)
        loc_name = location.name if location else ws.current_location

        tags = ["talk"]
        for rc in state_changes.relationship_changes:
            sign = "+" if rc.delta > 0 else ""
            tags.append(f"trust{sign}{rc.delta}")
        for qu in state_changes.quest_updates:
            tags.append(f"quest:{qu.quest_id}")
        if any(kw in message for kw in self.PROMISE_KEYWORDS):
            tags.append("promise")
        if any(kw in message for kw in self.QUEST_KEYWORDS):
            tags.append("quest_keyword")
        tag_str = "|".join(tags)

        memory_content = (
            f"[{tag_str}] 第{ws.turn_count}轮@{loc_name}："
            f"玩家说「{message[:50]}」，{npc.name}回应「{npc_response.dialogue[:50]}」"
        )
        memory = await self.memory_manager.add_short_term(
            db, ws.game_id, npc_id, memory_content, importance, ws.turn_count,
            auto_commit=False
        )
        if importance >= MemoryManager.PROMOTION_THRESHOLD:
            await self.memory_manager.promote_to_long_term(db, memory.id, auto_commit=False)

        return PlayerInputResponse(
            npc_response=npc_response.dialogue,
            npc_id=npc_id,
            narration="",
            state_changes=state_changes,
            available_actions=self._get_available_actions(ws),
        )

    async def _dispatch_instructions(
        self,
        db,
        ws: WorldStateModel,
        npc_id: str,
        instructions: list[ParsedInstruction],
        state_changes: StateChanges,
    ):
        for inst in instructions:
            if inst.type == "TRUST":
                rel = await self.relationship_manager.modify(
                    db, ws.game_id, inst.npc_id, "trust", inst.delta,
                    auto_commit=False
                )
                if rel:
                    state_changes.relationship_changes.append(
                        RelationshipChange(
                            npc_id=inst.npc_id, field="trust", delta=inst.delta
                        )
                    )
            elif inst.type == "FLAG":
                flag_value = inst.flag_value.lower() == "true"
                ws.flags[inst.flag_name] = flag_value
                await WorldState.save(db, ws, auto_commit=False)
                state_changes.flag_changes[inst.flag_name] = flag_value
            elif inst.type == "QUEST":
                pass

    async def _try_advance_quests(
        self,
        db,
        ws: WorldStateModel,
        state_changes: StateChanges,
        npc_id: str | None = None,
    ):
        for quest in self.quest_manager.get_all_quests():
            state = await self.quest_manager.get_state(db, ws.game_id, quest.id)
            if state is None or state.completed:
                continue

            all_rels = await self.relationship_manager.get_all(db, ws.game_id)
            trust_map = {r.npc_id: r.trust for r in all_rels}

            context = {
                "flags": ws.flags,
                "location": ws.current_location,
                "turn": ws.turn_count,
                "npc": npc_id,
                "trust": trust_map,
            }

            old_stage = state.current_stage
            success = await self.quest_manager.advance(
                db, ws.game_id, quest.id, context, auto_commit=False
            )
            if success:
                new_state = await self.quest_manager.get_state(
                    db, ws.game_id, quest.id
                )
                new_stage = new_state.current_stage if new_state else old_stage
                state_changes.quest_updates.append(
                    QuestUpdate(
                        quest_id=quest.id,
                        old_stage=old_stage,
                        new_stage=new_stage,
                    )
                )
                namespaced_flag = f"quest_{quest.id}_{new_stage}"
                ws.flags[namespaced_flag] = True
                await WorldState.save(db, ws, auto_commit=False)
                state_changes.flag_changes[namespaced_flag] = True

    def _calculate_importance(self, message: str, instructions: list[ParsedInstruction], state_changes: StateChanges) -> int:
        score = 1
        if any(kw in message for kw in self.QUEST_KEYWORDS):
            score += 3
        if state_changes.quest_updates:
            score += 3
        if state_changes.relationship_changes:
            score += 1
            for rc in state_changes.relationship_changes:
                if abs(rc.delta) >= 4:
                    score += 2
                    break
        if any(kw in message for kw in self.PROMISE_KEYWORDS):
            score += 2
        return min(score, 10)

    def _get_available_actions(self, ws: WorldStateModel) -> list[str]:
        actions = []

        npcs = self.world_state.get_available_npcs(ws.current_location)
        for npc_id in npcs:
            npc = self.npc_agent.get_npc(npc_id)
            if npc:
                actions.append(f"和{npc.name}交谈")

        connections = self.world_state.get_connections(ws.current_location)
        for loc_id in connections:
            loc = self.world_state.get_location(loc_id)
            if loc:
                actions.append(f"前往{loc.name}")

        actions.append("查看任务日志")
        return actions

    async def get_state(self, game_id: str) -> GameStateResponse | None:
        async with get_db() as db:
            ws = await WorldState.load(db, game_id)
            if ws is None:
                return None

            relationships = await self.relationship_manager.get_all(db, game_id)
            quest_states = await self.quest_manager.get_all_states(db, game_id)

            recent_memories = []
            for npc_id in ["innkeeper", "mayor", "miner"]:
                mems = await self.memory_manager.get_recent(db, game_id, npc_id, limit=3)
                recent_memories.extend(mems)

            triggered_town_events = self.town_tick_system.get_triggered_events(ws)

            return GameStateResponse(
                game_id=game_id,
                world_state=ws,
                relationships=relationships,
                quest_states=quest_states,
                recent_memories=recent_memories,
                triggered_town_events=triggered_town_events,
            )
