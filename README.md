# 边境小镇：记忆旅人

> Border Town: Memory Traveler — 文字 RPG MVP (v0.1)

一个基于 Python / FastAPI / SQLite 的文字冒险游戏引擎。玩家扮演路过边境小镇的旅行者，通过与 NPC 对话、探索地点来揭开失踪案的真相。

当前版本使用 **MockProvider** 生成 NPC 回复，尚未接入真实 LLM。

## 核心玩法循环

```
玩家输入 → 意图识别(移动/对话/探索) → NPC 回复 + 状态变更 → 任务推进检查 → 返回结果
```

- **探索**：在 3 个地点之间移动（破晓酒馆、镇政厅、废弃矿坑）
- **对话**：与 3 位 NPC 交谈（老板娘艾琳娜、镇长赫尔曼、矿工托马斯）
- **任务**：2 条任务线——主线「边境小镇失踪案」、支线「遗失的账本」
- **关系**：NPC 信任/好感系统，影响对话内容和任务解锁

## 技术栈

| 层 | 技术 |
|---|---|
| Web 框架 | FastAPI |
| 异步数据库 | aiosqlite (SQLite) |
| 数据模型 | Pydantic v2 |
| 测试 | pytest + pytest-asyncio |
| Python | ≥ 3.11 |

## 架构原则

> **Agent 负责表达，系统负责状态。**

- `NPCAgent` — 构建提示词、解析 NPC 回复，不直接读写数据库
- `GameEngine` — 协调流程、调度系统管理器
- `WorldState` / `QuestManager` / `RelationshipManager` / `MemoryManager` — 各自管理一块领域状态
- `LLMAdapter` — 抽象 LLM 调用，当前仅实现 MockProvider

所有状态写入在 `process_input` 中统一 commit/rollback，保证一次玩家输入内的状态一致性。

## 目录结构

```
frontier_traveler/
├── app/
│   ├── agents/
│   │   └── npc_agent.py          # NPC 提示词构建 + 回复解析
│   ├── api/
│   │   └── routes.py             # FastAPI 路由 (3 个端点)
│   ├── data/
│   │   ├── locations.json        # 3 个地点定义
│   │   ├── npcs.json             # 3 位 NPC 定义
│   │   └── quests.json           # 2 条任务线定义
│   ├── engine/
│   │   ├── game_engine.py        # 游戏主循环协调器
│   │   └── llm_adapter.py        # LLM 抽象层 + MockProvider
│   ├── models/
│   │   ├── api_schemas.py        # API 请求/响应模型
│   │   ├── game_state.py         # WorldState 数据模型
│   │   ├── location.py           # 地点模型
│   │   ├── memory.py             # 记忆模型
│   │   ├── npc.py                # NPC 模型
│   │   ├── quest.py              # 任务状态模型
│   │   └── relationship.py       # 关系模型
│   ├── systems/
│   │   ├── memory.py             # 短期(FIFO) + 长期记忆管理
│   │   ├── quest.py              # 任务状态机 + 条件检查
│   │   ├── relationship.py       # 信任/好感 + 安全边界
│   │   └── world_state.py        # 世界状态持久化
│   ├── cli.py                    # 命令行交互界面
│   ├── database.py               # 数据库连接 + 初始化
│   └── main.py                   # FastAPI 应用入口
├── db/
│   └── schema.sql                # SQLite 表结构
├── tests/
│   ├── test_e2e.py               # 端到端流程测试
│   ├── test_game_engine.py       # GameEngine 单元测试
│   ├── test_memory.py            # 记忆系统测试
│   ├── test_npc_agent.py         # NPC Agent 测试
│   ├── test_quest.py             # 任务系统测试
│   └── test_relationship.py      # 关系系统测试
└── pyproject.toml
```

## 安装依赖

```bash
# 克隆项目后，在项目根目录执行
pip install -e ".[dev]"
```

## 启动 API 服务

```bash
uvicorn app.main:app --reload
```

服务默认监听 `http://127.0.0.1:8000`，启动时自动初始化 SQLite 数据库。

API 文档：`http://127.0.0.1:8000/docs`

## 使用 CLI

```bash
python -m app.cli
```

CLI 命令：

| 命令 | 说明 |
|------|------|
| `/start` | 开始新游戏 |
| `/state` | 查看当前位置、关系、任务 |
| `/help` | 显示帮助 |
| `/quit` | 退出游戏 |

自然语言输入示例：
- `和老板娘聊聊` — 与当前地点的 NPC 对话
- `前往镇政厅` — 移动到其他地点
- `打听失踪案` — 触发默认对话

## API 示例

### POST /game/start

开始新游戏。

```bash
curl -X POST http://127.0.0.1:8000/game/start \
  -H "Content-Type: application/json" \
  -d '{"player_name": "旅行者"}'
```

响应：

```json
{
  "game_id": "abc123...",
  "opening_narrative": "你推开了破晓酒馆沉重的大门...",
  "current_location": {
    "id": "tavern",
    "name": "破晓酒馆",
    "description": "一间昏暗但温馨的小酒馆...",
    "connections": ["town_hall"],
    "available_npcs": ["innkeeper"]
  },
  "available_npcs": [
    {
      "id": "innkeeper",
      "name": "艾琳娜",
      "role": "酒馆老板娘",
      "personality": "精明、谨慎、善于察言观色...",
      "dialogue_style": "说话简洁有力，偶尔带点讽刺...",
      "default_location": "tavern"
    }
  ]
}
```

### POST /game/input

发送玩家输入。

```bash
curl -X POST http://127.0.0.1:8000/game/input \
  -H "Content-Type: application/json" \
  -d '{"game_id": "abc123...", "message": "和老板娘聊聊"}'
```

响应：

```json
{
  "npc_response": "嗯？你是新来的吧。我这里可不是问路的地方。",
  "npc_id": "innkeeper",
  "narration": "",
  "state_changes": {
    "quest_updates": [],
    "relationship_changes": [
      {"npc_id": "innkeeper", "field": "trust", "delta": 5}
    ],
    "flag_changes": {"heard_about_missing": true},
    "location_changed": false,
    "new_location": null
  },
  "available_actions": ["和艾琳娜交谈", "前往镇政厅"]
}
```

### GET /game/state/{game_id}

查询完整游戏状态。

```bash
curl http://127.0.0.1:8000/game/state/abc123...
```

响应：

```json
{
  "game_id": "abc123...",
  "world_state": {
    "game_id": "abc123...",
    "current_location": "tavern",
    "turn_count": 3,
    "time_of_day": "白天",
    "flags": {"heard_about_missing": true}
  },
  "relationships": [
    {"game_id": "abc123...", "npc_id": "innkeeper", "trust": 35, "affection": 30, "status": "neutral"},
    {"game_id": "abc123...", "npc_id": "mayor", "trust": 30, "affection": 30, "status": "neutral"},
    {"game_id": "abc123...", "npc_id": "miner", "trust": 20, "affection": 20, "status": "hostile"}
  ],
  "quest_states": [
    {"quest_id": "missing_case", "current_stage": "heard_rumor", "completed": false, "stage_history": ["not_started"]},
    {"quest_id": "lost_ledger", "current_stage": "not_started", "completed": false, "stage_history": []}
  ],
  "recent_memories": [
    {"id": "...", "game_id": "abc123...", "npc_id": "innkeeper", "content": "旅行者询问了失踪案", "type": "short_term", "importance": 8, "turn": 2, "accessed_count": 1}
  ]
}
```

## Walkthrough：主线完整流程

以下是主线「边境小镇失踪案」的一条通关路径：

```
> /start
  → 开局，你出现在破晓酒馆，老板娘艾琳娜在吧台后面

> 和老板娘聊聊
  → 艾琳娜提到最近有人失踪，flag「heard_about_missing」触发
  → [任务更新] 边境小镇失踪案: not_started → heard_rumor

> 和老板娘聊聊
  → 继续对话，提升信任

> 前往镇政厅
  → 移动到镇政厅，镇长赫尔曼在办公室

> 和镇长聊聊
  → 镇长回避话题，可能触发信任变化

> 前往废弃矿坑
  → 来到矿坑，满足「heard_rumor → found_clue」条件（地点=矿坑，回合≥3）
  → [任务更新] 边境小镇失踪案: heard_rumor → found_clue

> 和矿工聊聊
  → 托马斯紧张地与你交谈

> 前往镇政厅
> 和镇长聊聊
  → 质问镇长，信任值≤60 满足「found_clue → confronted_mayor」条件
  → [任务更新] 边境小镇失踪案: found_clue → confronted_mayor

> 前往废弃矿坑
> 和矿工聊聊
  → 矿工证实一切，满足「confronted_mayor → resolved」条件
  → [任务更新] 边境小镇失踪案: confronted_mayor → resolved
  → 案件告破！

> /state
  → 查看最终状态：任务已完成，关系值已变化
```

## 测试命令

```bash
# 运行全部测试
python -m pytest tests/ -v

# 运行单个测试文件
python -m pytest tests/test_e2e.py -v

# 运行单个测试
python -m pytest tests/test_game_engine.py::test_process_input_rollback_on_failure -v
```

当前共 56 个测试，覆盖：

| 测试文件 | 覆盖范围 |
|----------|----------|
| `test_e2e.py` | 主线/支线完整流程、flag 命名空间隔离、裸 flag 防污染 |
| `test_game_engine.py` | 开始/移动/对话/状态查询、NPC 信息不泄露、全状态持久化、异常 rollback |
| `test_memory.py` | 短期记忆 FIFO、长期晋升、记忆召回排序 |
| `test_npc_agent.py` | 提示词构建、回复解析、指令提取 |
| `test_quest.py` | 任务加载、阶段转换、条件检查（flag/地点/信任/NPC） |
| `test_relationship.py` | 状态计算、安全边界 clamp、信任增减 |

## 当前限制

- **NPC 回复由 MockProvider 生成**：基于 NPC 角色模板的预设回复，不是真正的 AI 生成
- **意图识别基于关键词**：通过正则匹配判断移动/对话/探索，不支持复杂自然语言理解
- **无 Web UI**：仅提供 REST API 和命令行两种交互方式
- **无多存档**：同一进程可创建多个 game，但无存档导入/导出
- **无战斗系统**：纯对话 + 探索驱动的任务推进
- **地点连通性简单**：线性三地点（酒馆 ↔ 镇政厅 ↔ 矿坑）
- **记忆系统仅后端**：记忆影响 NPC 提示词构建，但不影响 MockProvider 的回复内容

## v0.2 Roadmap

- [ ] **OpenAI-compatible LLMAdapter** — 接入真实 LLM（OpenAI / 兼容 API），替换 MockProvider
- [ ] **更稳健的 Prompt 输出解析** — 增强对 LLM 输出格式不一致的容错能力
- [ ] **LLM fallback 到 MockProvider** — 当 LLM 调用失败时自动降级到 MockProvider
- [ ] **简单 Web UI** — 浏览器端的对话式交互界面
- [ ] **长期记忆检索增强** — 基于 embedding 的语义检索，让 NPC 能引用更久远的对话内容
