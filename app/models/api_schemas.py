from pydantic import BaseModel

from app.models.game_state import WorldStateModel
from app.models.location import Location
from app.models.memory import Memory
from app.models.quest import QuestState
from app.models.relationship import Relationship


class PublicNPC(BaseModel):
    id: str
    name: str
    role: str
    personality: str = ""
    dialogue_style: str = ""
    default_location: str = ""


class QuestUpdate(BaseModel):
    quest_id: str
    old_stage: str
    new_stage: str


class RelationshipChange(BaseModel):
    npc_id: str
    field: str
    delta: int


class TownEvent(BaseModel):
    event_id: str
    title: str
    narration: str
    importance: int


class NpcLocationInfo(BaseModel):
    npc_id: str
    name: str
    location: str
    visible: bool


class StateChanges(BaseModel):
    quest_updates: list[QuestUpdate] = []
    relationship_changes: list[RelationshipChange] = []
    flag_changes: dict[str, bool] = {}
    location_changed: bool = False
    new_location: str | None = None
    town_events: list[TownEvent] = []


class StartGameRequest(BaseModel):
    player_name: str = "旅行者"


class StartGameResponse(BaseModel):
    game_id: str
    opening_narrative: str
    current_location: Location
    available_npcs: list[PublicNPC]


class PlayerInputRequest(BaseModel):
    game_id: str
    message: str


class PlayerInputResponse(BaseModel):
    npc_response: str
    npc_id: str | None
    narration: str
    state_changes: StateChanges
    available_actions: list[str]


class GameStateResponse(BaseModel):
    game_id: str
    world_state: WorldStateModel
    relationships: list[Relationship]
    quest_states: list[QuestState]
    recent_memories: list[Memory]
    triggered_town_events: list[TownEvent] = []
    npc_locations: list[NpcLocationInfo] = []
