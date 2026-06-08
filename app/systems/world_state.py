import json

from app.database import load_json_data
from app.models.game_state import WorldStateModel
from app.models.location import Location


class WorldState:
    def __init__(self):
        self._locations: dict[str, Location] = {}
        self._load_locations()

    def _load_locations(self):
        data = load_json_data("locations.json")
        for item in data:
            location = Location(**item)
            self._locations[location.id] = location

    def get_location(self, location_id: str) -> Location | None:
        return self._locations.get(location_id)

    def can_move_to(self, from_location: str, to_location: str) -> bool:
        source = self._locations.get(from_location)
        if source is None:
            return False
        return to_location in source.connections

    def get_connections(self, location_id: str) -> list[str]:
        location = self._locations.get(location_id)
        if location is None:
            return []
        return list(location.connections)

    def get_available_npcs(self, location_id: str) -> list[str]:
        location = self._locations.get(location_id)
        if location is None:
            return []
        return list(location.available_npcs)

    @staticmethod
    async def load(db, game_id: str) -> WorldStateModel | None:
        cursor = await db.execute(
            "SELECT game_id, current_location, time_of_day, turn_count, flags FROM games WHERE game_id = ?",
            (game_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        flags = json.loads(row["flags"]) if row["flags"] else {}
        return WorldStateModel(
            game_id=row["game_id"],
            current_location=row["current_location"],
            time_of_day=row["time_of_day"],
            turn_count=row["turn_count"],
            flags=flags,
        )

    @staticmethod
    async def save(db, state: WorldStateModel, auto_commit: bool = True):
        await db.execute(
            "INSERT OR REPLACE INTO games (game_id, current_location, time_of_day, turn_count, flags) VALUES (?, ?, ?, ?, ?)",
            (
                state.game_id,
                state.current_location,
                state.time_of_day,
                state.turn_count,
                json.dumps(state.flags),
            ),
        )
        if auto_commit:
            await db.commit()

    @staticmethod
    async def create(db, game_id: str) -> WorldStateModel:
        state = WorldStateModel(game_id=game_id)
        await WorldState.save(db, state)
        return state
