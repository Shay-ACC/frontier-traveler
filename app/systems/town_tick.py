from app.database import load_json_data
from app.models.api_schemas import TownEvent
from app.models.game_state import WorldStateModel
from app.models.api_schemas import StateChanges


class TownTickSystem:
    def __init__(self):
        self._events: list[dict] = load_json_data("town_events.json")

    def _find_event(self, event_id: str) -> dict | None:
        for event in self._events:
            if event["id"] == event_id:
                return event
        return None

    def tick(self, ws: WorldStateModel, state_changes: StateChanges) -> list[TownEvent]:
        triggered = []
        for event in self._events:
            if ws.turn_count < event["trigger_turn"]:
                continue
            required = event.get("required_flags", {})
            if not all(ws.flags.get(k) == v for k, v in required.items()):
                continue
            forbidden = event.get("forbidden_flags", [])
            if any(ws.flags.get(f) for f in forbidden):
                continue
            ws.flags[f"town_event_{event['id']}"] = True
            for flag_name in event.get("set_flags", []):
                ws.flags[flag_name] = True
                state_changes.flag_changes[flag_name] = True
            triggered.append(TownEvent(
                event_id=event["id"],
                title=event["title"],
                narration=event["narration"],
                importance=event["importance"],
            ))
        return triggered

    def get_triggered_events(self, ws: WorldStateModel) -> list[TownEvent]:
        triggered = []
        for key, value in ws.flags.items():
            if key.startswith("town_event_") and value:
                event_id = key[len("town_event_"):]
                event = self._find_event(event_id)
                if event:
                    triggered.append(TownEvent(
                        event_id=event["id"],
                        title=event["title"],
                        narration=event["narration"],
                        importance=event["importance"],
                    ))
        return triggered
