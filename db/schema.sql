CREATE TABLE IF NOT EXISTS games (
    game_id TEXT PRIMARY KEY,
    player_name TEXT NOT NULL DEFAULT '旅行者',
    current_location TEXT NOT NULL DEFAULT 'tavern',
    time_of_day TEXT NOT NULL DEFAULT 'morning',
    turn_count INTEGER NOT NULL DEFAULT 0,
    flags TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    game_id TEXT NOT NULL,
    npc_id TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('short_term', 'long_term')),
    content TEXT NOT NULL,
    importance INTEGER NOT NULL DEFAULT 5,
    turn INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    accessed_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (game_id) REFERENCES games(game_id)
);

CREATE TABLE IF NOT EXISTS relationships (
    game_id TEXT NOT NULL,
    npc_id TEXT NOT NULL,
    trust INTEGER NOT NULL DEFAULT 30,
    affection INTEGER NOT NULL DEFAULT 30,
    status TEXT NOT NULL DEFAULT 'neutral',
    PRIMARY KEY (game_id, npc_id),
    FOREIGN KEY (game_id) REFERENCES games(game_id)
);

CREATE TABLE IF NOT EXISTS quest_states (
    game_id TEXT NOT NULL,
    quest_id TEXT NOT NULL,
    current_stage TEXT NOT NULL,
    completed INTEGER NOT NULL DEFAULT 0,
    stage_history TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (game_id, quest_id),
    FOREIGN KEY (game_id) REFERENCES games(game_id)
);

CREATE INDEX IF NOT EXISTS idx_memories_game_npc ON memories(game_id, npc_id);
CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(game_id, npc_id, type);
