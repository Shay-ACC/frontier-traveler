from pydantic import BaseModel


class NPC(BaseModel):
    id: str
    name: str
    role: str
    personality: str
    backstory: str
    default_location: str
    dialogue_style: str
    secrets: list[str]
