from fastapi import APIRouter, HTTPException

from app.engine.game_engine import GameEngine
from app.models.api_schemas import (
    GameStateResponse,
    PlayerInputRequest,
    PlayerInputResponse,
    StartGameRequest,
    StartGameResponse,
)

router = APIRouter(prefix="/game")
_engine = GameEngine()


@router.post("/start", response_model=StartGameResponse)
async def start_game(request: StartGameRequest):
    return await _engine.start_game(request.player_name)


@router.post("/input", response_model=PlayerInputResponse)
async def player_input(request: PlayerInputRequest):
    response = await _engine.process_input(request.game_id, request.message)
    if response.npc_response == "游戏会话不存在。":
        raise HTTPException(status_code=404, detail="Game session not found")
    return response


@router.get("/state/{game_id}", response_model=GameStateResponse)
async def get_game_state(game_id: str):
    state = await _engine.get_state(game_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Game session not found")
    return state
