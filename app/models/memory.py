from datetime import datetime

from pydantic import BaseModel


class Memory(BaseModel):
    id: str
    game_id: str
    npc_id: str
    type: str
    content: str
    importance: int
    turn: int
    created_at: datetime
    accessed_count: int = 0
