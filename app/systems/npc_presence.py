from app.database import load_json_data
from app.models.api_schemas import NpcLocationInfo
from app.models.game_state import WorldStateModel


class NpcPresenceSystem:
    def __init__(self):
        self._rules: list[dict] = load_json_data("npc_presence_rules.json")
        npc_data: list[dict] = load_json_data("npcs.json")
        self._defaults: dict[str, dict] = {npc["id"]: npc for npc in npc_data}

    def _resolve(self, npc_id: str, ws: WorldStateModel) -> tuple[str, bool, str | None]:
        default = self._defaults.get(npc_id, {})
        default_loc = default.get("default_location", "")
        for entry in self._rules:
            if entry["npc_id"] != npc_id:
                continue
            for rule in entry.get("rules", []):
                when = rule.get("when_flags", {})
                if not all(ws.flags.get(k) == v for k, v in when.items()):
                    continue
                unless = rule.get("unless_flags", {})
                if any(ws.flags.get(k) == v for k, v in unless.items()):
                    continue
                return rule["location"], rule.get("visible", True), rule.get("reason")
        return default_loc, True, None

    def get_npcs_at_location(self, ws: WorldStateModel, location_id: str) -> list[str]:
        result = []
        for npc_id in self._defaults:
            loc, visible, _ = self._resolve(npc_id, ws)
            if loc == location_id and visible:
                result.append(npc_id)
        return result

    def get_all_npc_locations(self, ws: WorldStateModel) -> list[NpcLocationInfo]:
        result = []
        for npc_id, data in self._defaults.items():
            loc, visible, _ = self._resolve(npc_id, ws)
            result.append(NpcLocationInfo(
                npc_id=npc_id,
                name=data.get("name", npc_id),
                location=loc,
                visible=visible,
            ))
        return result

    def get_absence_reason(self, ws: WorldStateModel, npc_id: str, location_id: str) -> str | None:
        loc, visible, reason = self._resolve(npc_id, ws)
        if loc != location_id:
            return reason
        if not visible:
            return reason
        return None
