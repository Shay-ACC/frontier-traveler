from pydantic import BaseModel, Field


class Relationship(BaseModel):
    game_id: str
    npc_id: str
    trust: int = Field(default=30, ge=0, le=100)
    affection: int = Field(default=30, ge=0, le=100)
    status: str = "neutral"
