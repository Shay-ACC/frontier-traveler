from pydantic import BaseModel


class WorldStateModel(BaseModel):
    game_id: str
    current_location: str = "tavern"
    time_of_day: str = "morning"
    turn_count: int = 0
    flags: dict[str, bool] = {}
    quest_states: dict[str, str] = {}
