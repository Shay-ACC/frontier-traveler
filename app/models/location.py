from pydantic import BaseModel


class Location(BaseModel):
    id: str
    name: str
    description: str
    connections: list[str]
    available_npcs: list[str]
