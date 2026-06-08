# Tasks

## Phase 1：数据模型与基础设施

- [x] Task 1：项目骨架搭建
  - [x] 1.1：创建 pyproject.toml，配置依赖（fastapi, uvicorn, pydantic, aiosqlite）
  - [x] 1.2：创建目录结构（app/, app/api/, app/engine/, app/agents/, app/systems/, app/models/, app/data/, db/, tests/）
  - [x] 1.3：创建所有 __init__.py 文件
  - [x] 1.4：创建 app/main.py，FastAPI 应用入口，配置 CORS 和生命周期

- [x] Task 2：Pydantic 数据模型
  - [x] 2.1：app/models/npc.py — NPC 模型
  - [x] 2.2：app/models/location.py — Location 模型
  - [x] 2.3：app/models/quest.py — Quest / QuestStage / QuestState 模型
  - [x] 2.4：app/models/memory.py — Memory 模型
  - [x] 2.5：app/models/relationship.py — Relationship 模型
  - [x] 2.6：app/models/game_state.py — WorldStateModel 模型
  - [x] 2.7：app/models/api_schemas.py — 请求/响应 Schema（StartGameRequest/Response, PlayerInputRequest/Response, GameStateResponse, StateChanges）

- [x] Task 3：初始数据文件
  - [x] 3.1：app/data/npcs.json — 3 个 NPC 数据（innkeeper, mayor, miner）
  - [x] 3.2：app/data/locations.json — 3 个地点数据（tavern, town_hall, abandoned_mine）
  - [x] 3.3：app/data/quests.json — 2 条任务数据（missing_case, lost_ledger），含完整阶段定义和转换条件

- [x] Task 4：SQLite 数据库层
  - [x] 4.1：db/schema.sql — 建表语句（games, memories, relationships, quest_states, world_states）
  - [x] 4.2：app/db.py 或 app/database.py — 数据库连接管理、初始化、CRUD 基础方法

## Phase 2：核心游戏系统

- [x] Task 5：WorldState 系统实现
  - [x] 5.1：app/systems/world_state.py — WorldState 类，实现 move_to / set_flag / get_flag / advance_time / save / load

- [x] Task 6：QuestManager 系统实现
  - [x] 6.1：app/systems/quest.py — QuestManager 类，实现 load_quests / advance / get_state / check_completion / validate_transition
  - [x] 6.2：单元测试 tests/test_quest.py — 状态机转换正确性、非法转换拒绝、完成检测

- [x] Task 7：RelationshipManager 系统实现
  - [x] 7.1：app/systems/relationship.py — RelationshipManager 类，实现 modify / get / compute_status / save / load
  - [x] 7.2：单元测试 tests/test_relationship.py — 范围钳制、单次变更幅度限制、状态计算

- [x] Task 8：MemoryManager 系统实现
  - [x] 8.1：app/systems/memory.py — MemoryManager 类，实现 add_short_term / promote_to_long_term / recall / get_recent / cleanup_expired
  - [x] 8.2：单元测试 tests/test_memory.py — FIFO 淘汰、晋升规则、召回排序

## Phase 3：NPCAgent 与 LLMAdapter

- [x] Task 9：LLMAdapter 实现
  - [x] 9.1：app/engine/llm_adapter.py — BaseLLMProvider 抽象基类 + MockProvider
  - [x] 9.2：MockProvider 预设回复模板（每个 NPC × 5 个场景 = 15 个模板）

- [x] Task 10：NPCAgent 实现
  - [x] 10.1：app/agents/npc_agent.py — NPCAgent 类，实现 build_prompt / parse_response / get_npc_response
  - [x] 10.2：单元测试 tests/test_npc_agent.py — Prompt 构造完整性、回复解析正确性、无效指令过滤

## Phase 4：GameEngine 与 API

- [x] Task 11：GameEngine 实现
  - [x] 11.1：app/engine/game_engine.py — GameEngine 类，实现 process_input / start_game / get_state / parse_intent / dispatch_instructions
  - [x] 11.2：单元测试 tests/test_game_engine.py — 对话流程、移动流程、指令分发

- [x] Task 12：API 路由实现
  - [x] 12.1：app/api/routes.py — POST /game/start、POST /game/input、GET /game/state、GET /game/locations、GET /game/quests
  - [x] 12.2：集成测试 tests/test_api.py — 完整 HTTP 请求响应测试

## Phase 5：集成测试与 CLI

- [x] Task 13：端到端集成测试
  - [x] 13.1：tests/test_e2e.py — 主线任务完整流程测试（start → 听闻传闻 → 矿坑发现线索 → 质问镇长 → 矿工作证 → 结案）
  - [x] 13.2：tests/test_e2e.py — 支线任务完整流程测试（与老板娘建立信任 → 接受任务 → 镇政厅搜查 → 归还账本）

- [x] Task 14：CLI 交互界面
  - [x] 14.1：app/cli.py — 简易命令行交互循环，支持输入/输出/状态查看
  - [x] 14.2：启动入口配置（pyproject.toml scripts 或 if __name__）

# Task Dependencies

- Task 2 依赖 Task 1（目录结构先就位）
- Task 3 依赖 Task 2（JSON 数据需匹配模型定义）
- Task 4 依赖 Task 2（表结构需匹配模型定义）
- Task 5, 6, 7, 8 依赖 Task 4（系统层需数据库）
- Task 5, 6, 7, 8 之间无依赖，可并行
- Task 9 依赖 Task 2（需要模型定义）
- Task 10 依赖 Task 8, Task 7, Task 6（需要记忆、关系、任务数据）
- Task 11 依赖 Task 5, 6, 7, 8, 9, 10（需要所有子系统就绪）
- Task 12 依赖 Task 11（路由层依赖引擎层）
- Task 13 依赖 Task 12（端到端测试需 API 就绪）
- Task 14 依赖 Task 11（CLI 需引擎就绪，与 Task 12 并行）
