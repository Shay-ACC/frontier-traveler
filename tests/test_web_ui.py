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
async def test_js_reads_npc_response_field(client):
    response = await client.get("/static/app.js")
    assert response.status_code == 200
    js = response.text
    assert "data.npc_response" in js
    assert "data.response" not in js


@pytest.mark.asyncio
async def test_js_reads_world_state_fields(client):
    response = await client.get("/static/app.js")
    assert response.status_code == 200
    js = response.text
    assert "ws.current_location" in js
    assert "ws.turn_count" in js
    assert "data.location" not in js
    assert "data.turn_count" not in js


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


@pytest.mark.asyncio
async def test_js_memory_display_format(client):
    response = await client.get("/static/app.js")
    assert response.status_code == 200
    js = response.text
    assert "memory-type-long" in js
    assert "memory-type-short" in js
    assert "memory-important" in js


@pytest.mark.asyncio
async def test_css_memory_styles(client):
    response = await client.get("/static/style.css")
    assert response.status_code == 200
    css = response.text
    assert ".memory-type-long" in css
    assert ".memory-type-short" in css
    assert ".memory-important" in css


@pytest.mark.asyncio
async def test_js_contains_strip_memory_tags(client):
    response = await client.get("/static/app.js")
    assert response.status_code == 200
    js = response.text
    assert "stripMemoryTags" in js
    assert "replace" in js
    assert "\\[" in js or "[^" in js


@pytest.mark.asyncio
async def test_js_handles_town_events(client):
    response = await client.get("/static/app.js")
    assert response.status_code == 200
    js = response.text
    assert "town_events" in js
    assert "town-event-item" in js


@pytest.mark.asyncio
async def test_index_contains_town_events_section(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert "town-events" in response.text


@pytest.mark.asyncio
async def test_js_handles_npc_locations(client):
    response = await client.get("/static/app.js")
    assert response.status_code == 200
    js = response.text
    assert "npc_locations" in js
    assert "npc-location-item" in js
    assert "LOC_NAME_MAP" in js


@pytest.mark.asyncio
async def test_index_contains_npc_locations_section(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert "npc-locations" in response.text
