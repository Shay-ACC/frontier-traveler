import json
from pathlib import Path

from app.models.quest import Quest, QuestStage, QuestState

_QUESTS_PATH = Path(__file__).resolve().parent.parent / "data" / "quests.json"


class QuestManager:
    def __init__(self):
        self._quests: dict[str, Quest] = {}
        self._load_quests()

    def _load_quests(self):
        data = json.loads(_QUESTS_PATH.read_text(encoding="utf-8"))
        for item in data:
            quest = Quest(**item)
            self._quests[quest.id] = quest

    def get_quest(self, quest_id: str) -> Quest | None:
        return self._quests.get(quest_id)

    def get_all_quests(self) -> list[Quest]:
        return list(self._quests.values())

    def get_stage(self, quest_id: str, stage_id: str) -> QuestStage | None:
        quest = self.get_quest(quest_id)
        if quest is None:
            return None
        for stage in quest.stages:
            if stage.id == stage_id:
                return stage
        return None

    async def get_state(self, db, game_id: str, quest_id: str) -> QuestState | None:
        cursor = await db.execute(
            "SELECT * FROM quest_states WHERE game_id = ? AND quest_id = ?",
            (game_id, quest_id),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return QuestState(
            quest_id=row["quest_id"],
            current_stage=row["current_stage"],
            completed=bool(row["completed"]),
            stage_history=json.loads(row["stage_history"]),
        )

    async def get_all_states(self, db, game_id: str) -> list[QuestState]:
        cursor = await db.execute(
            "SELECT * FROM quest_states WHERE game_id = ?",
            (game_id,),
        )
        rows = await cursor.fetchall()
        states = []
        for row in rows:
            states.append(
                QuestState(
                    quest_id=row["quest_id"],
                    current_stage=row["current_stage"],
                    completed=bool(row["completed"]),
                    stage_history=json.loads(row["stage_history"]),
                )
            )
        return states

    async def init_quest_states(self, db, game_id: str):
        for quest in self._quests.values():
            await db.execute(
                "INSERT OR IGNORE INTO quest_states (game_id, quest_id, current_stage, completed, stage_history) VALUES (?, ?, ?, 0, '[]')",
                (game_id, quest.id, quest.initial_stage),
            )
        await db.commit()

    def validate_transition(self, quest_id: str, current_stage: str, target_stage: str) -> bool:
        stage = self.get_stage(quest_id, current_stage)
        if stage is None:
            return False
        return stage.next_stage == target_stage

    async def advance(self, db, game_id: str, quest_id: str, context: dict) -> bool:
        state = await self.get_state(db, game_id, quest_id)
        if state is None or state.completed:
            return False
        stage = self.get_stage(quest_id, state.current_stage)
        if stage is None:
            return False
        conditions = stage.completion_conditions
        if not self._check_conditions(conditions, context):
            return False
        if stage.next_stage is None:
            state.stage_history.append(state.current_stage)
            await db.execute(
                "UPDATE quest_states SET completed = 1, current_stage = ?, stage_history = ? WHERE game_id = ? AND quest_id = ?",
                (state.current_stage, json.dumps(state.stage_history), game_id, quest_id),
            )
            await db.commit()
            return True
        state.stage_history.append(state.current_stage)
        state.current_stage = stage.next_stage
        next_stage_obj = self.get_stage(quest_id, stage.next_stage)
        completed = next_stage_obj is not None and next_stage_obj.next_stage is None
        await db.execute(
            "UPDATE quest_states SET current_stage = ?, completed = ?, stage_history = ? WHERE game_id = ? AND quest_id = ?",
            (state.current_stage, int(completed), json.dumps(state.stage_history), game_id, quest_id),
        )
        await db.commit()
        return True

    def _check_conditions(self, conditions: dict, context: dict) -> bool:
        if not conditions:
            return True
        if "flag" in conditions:
            flag_name = conditions["flag"]
            expected = conditions.get("value", True)
            if context.get("flags", {}).get(flag_name) != expected:
                return False
        if "location" in conditions:
            if context.get("location") != conditions["location"]:
                return False
        if "min_turn" in conditions:
            if context.get("turn", 0) < conditions["min_turn"]:
                return False
        if "npc" in conditions:
            if context.get("npc") != conditions["npc"]:
                return False
        if "min_trust" in conditions:
            npc_name = context.get("npc", "")
            trust = context.get("trust", {}).get(npc_name, 0)
            if trust < conditions["min_trust"]:
                return False
        if "max_trust" in conditions:
            npc_name = context.get("npc", "")
            trust = context.get("trust", {}).get(npc_name, 101)
            if trust > conditions["max_trust"]:
                return False
        return True

    async def check_completion(self, db, game_id: str, quest_id: str) -> bool:
        state = await self.get_state(db, game_id, quest_id)
        if state is None:
            return False
        return state.completed
