import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_index_page(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert "边境小镇" in response.text
    assert "text/html" in response.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_static_css(client):
    response = await client.get("/static/style.css")
    assert response.status_code == 200
    assert "text/css" in response.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_static_js(client):
    response = await client.get("/static/app.js")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_game_start_still_works(client):
    response = await client.post("/game/start", json={"player_name": "旅行者"})
    assert response.status_code == 200
    data = response.json()
    assert "game_id" in data
    assert "opening_narrative" in data


@pytest.mark.asyncio
async def test_game_input_still_works(client):
    start = await client.post("/game/start", json={"player_name": "旅行者"})
    game_id = start.json()["game_id"]
    response = await client.post("/game/input", json={"game_id": game_id, "message": "和老板娘聊聊"})
    assert response.status_code == 200
    data = response.json()
    assert "npc_response" in data


@pytest.mark.asyncio
async def test_game_state_still_works(client):
    start = await client.post("/game/start", json={"player_name": "旅行者"})
    game_id = start.json()["game_id"]
    response = await client.get(f"/game/state/{game_id}")
    assert response.status_code == 200
    data = response.json()
    assert "world_state" in data
