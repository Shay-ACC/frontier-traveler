from pydantic import BaseModel


class QuestStage(BaseModel):
    id: str
    description: str
    completion_conditions: dict
    next_stage: str | None


class Quest(BaseModel):
    id: str
    title: str
    description: str
    type: str
    stages: list[QuestStage]
    initial_stage: str


class QuestState(BaseModel):
    quest_id: str
    current_stage: str
    completed: bool
    stage_history: list[str]
