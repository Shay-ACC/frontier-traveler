import json
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = _ROOT / "game.db"
SCHEMA_PATH = _ROOT / "db" / "schema.sql"
DATA_DIR = _ROOT / "app" / "data"


@asynccontextmanager
async def get_db():
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


async def init_db():
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    async with get_db() as db:
        await db.executescript(schema_sql)
        await db.commit()


def load_json_data(filename: str):
    filepath = DATA_DIR / filename
    return json.loads(filepath.read_text(encoding="utf-8"))
