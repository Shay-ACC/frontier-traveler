# 《边境小镇：记忆旅人》MVP 设计规格

## 项目定位

一款 Agent 驱动的文字互动 RPG 原型。玩家通过自然语言与 NPC 互动，NPC 由 LLM Agent 驱动，具备角色设定、记忆系统和好感度机制。游戏系统负责任务状态、世界状态和规则约束，Agent 仅负责叙事表达和对话生成。

**核心设计原则**：Agent 负责表达（叙事、对话、语气），系统负责规则（任务、数值、状态变更）。两层分离，互不越界。

## MVP 核心玩法循环 (Core Loop)

```
玩家输入自然语言
    ↓
GameEngine 接收并解析意图
    ↓
路由到当前地点 → 判断可用 NPC / 可执行动作
    ↓
NPCAgent 构造 Prompt（角色设定 + 记忆 + 好感度 + 任务状态 + 世界上下文）
    ↓
LLMAdapter 调用 LLM（MVP 用 Mock Provider）
    ↓
GameEngine 解析 LLM 回复，提取结构化指令（任务推进 / 好感度变化 / 世界 flag 变更）
    ↓
QuestManager / RelationshipManager / WorldState 执行状态变更
    ↓
MemoryManager 记录本次交互到短期记忆
    ↓
返回 NPC 回复 + 状态变更摘要给玩家
```

**关键约束**：任务推进、好感度变化、世界状态更新由游戏系统执行，不交给 LLM 自由决定。LLM 输出中包含建议性的结构化标签（如 `[QUEST:missing_case advance]`），系统校验合法性后才执行。

## 推荐目录结构

```
frontier_traveler/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI 入口，挂载路由和生命周期
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py            # API 路由定义
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── game_engine.py       # GameEngine 主流程
│   │   └── llm_adapter.py       # LLMAdapter（含 MockProvider）
│   ├── agents/
│   │   ├── __init__.py
│   │   └── npc_agent.py         # NPCAgent Prompt 构造与回复解析
│   ├── systems/
│   │   ├── __init__.py
│   │   ├── memory.py            # MemoryManager
│   │   ├── relationship.py      # RelationshipManager
│   │   ├── quest.py             # QuestManager
│   │   └── world_state.py       # WorldState
│   ├── models/
│   │   ├── __init__.py
│   │   ├── npc.py               # NPC Pydantic 模型
│   │   ├── location.py          # Location Pydantic 模型
│   │   ├── quest.py             # Quest / QuestStage 模型
│   │   ├── memory.py            # Memory 模型
│   │   ├── relationship.py      # Relationship 模型
│   │   ├── game_state.py        # GameState 聚合模型
│   │   └── api_schemas.py       # 请求/响应 Schema
│   └── data/
│       ├── npcs.json            # NPC 初始数据
│       ├── locations.json       # 地点初始数据
│       └── quests.json          # 任务初始数据
├── db/
│   └── schema.sql               # SQLite 建表语句
├── tests/
│   ├── __init__.py
│   ├── test_game_engine.py
│   ├── test_memory.py
│   ├── test_quest.py
│   ├── test_relationship.py
│   ├── test_npc_agent.py
│   └── test_api.py
├── pyproject.toml
└── requirements.txt
```

## 核心模块职责

### 1. GameEngine (`app/engine/game_engine.py`)

**职责**：游戏主控制器，协调所有子系统。

- 接收玩家输入，维护当前游戏会话
- 调用 NPCAgent 生成 NPC 回复
- 解析 NPC 回复中的结构化指令标签
- 将合法的状态变更分发给 QuestManager / RelationshipManager / WorldState
- 调用 MemoryManager 记录交互
- 返回聚合响应给 API 层

**不负责**：直接操作数据库、直接调用 LLM。

### 2. NPCAgent (`app/agents/npc_agent.py`)

**职责**：构造 Prompt 并解析 LLM 回复。

- 根据目标 NPC 加载角色设定
- 从 MemoryManager 获取该 NPC 相关记忆
- 从 RelationshipManager 获取当前好感度
- 从 QuestManager 获取相关任务状态
- 组装完整 Prompt（系统提示 + 上下文 + 约束 + 输出格式）
- 调用 LLMAdapter 获取回复
- 解析回复中的结构化标签，返回 `(对话文本, 指令列表)`

**不负责**：执行任何状态变更、直接访问数据库。

### 3. MemoryManager (`app/systems/memory.py`)

**职责**：管理 NPC 的短期和长期记忆。

- 短期记忆：存储最近 N 轮交互（N 可配置，默认 20），按 NPC 分组
- 长期记忆：重要性 >= 阈值的事件从短期记忆晋升，永久存储
- 查询：按 NPC ID + 关键词检索记忆
- 记忆格式：`{轮次, NPC_ID, 内容, 重要性, 时间戳}`
- MVP 使用 SQLite 存储，不做向量检索

### 4. RelationshipManager (`app/systems/relationship.py`)

**职责**：管理玩家与 NPC 的关系数值。

- 每个关系包含：`trust`（信任度 0-100）、`affection`（好感度 0-100）
- 提供 `modify(npc_id, field, delta)` 方法，内部做范围钳制 [0, 100]
- 系统校验：每次变更幅度不超过 ±10（防止单次交互剧变）
- 提供查询方法 `get(npc_id) -> Relationship`

### 5. QuestManager (`app/systems/quest.py`)

**职责**：管理任务状态机。

- 从 `quests.json` 加载任务定义和阶段
- 提供 `advance(quest_id, next_stage)` 方法，校验状态转换合法性
- 提供 `get_state(quest_id) -> QuestState`
- 提供 `check_completion(quest_id) -> bool`
- 任务状态持久化到 SQLite

### 6. WorldState (`app/systems/world_state.py`)

**职责**：管理全局世界状态。

- 维护 `current_location`、`time_of_day`、`turn_count`
- 维护 `flags: dict[str, bool]` 用于标记世界事件
- 提供 `set_flag(key, value)` / `get_flag(key)` 方法
- 提供 `move_to(location_id)` 方法，校验地点连通性
- 持久化到 SQLite

### 7. LLMAdapter (`app/engine/llm_adapter.py`)

**职责**：封装 LLM 调用。

- 定义 `BaseLLMProvider` 抽象基类，接口：`async def generate(prompt: str, system: str) -> str`
- 实现 `MockProvider`：根据 Prompt 中的 NPC ID 和上下文，返回预设模板回复
- 预留 `OpenAIProvider` 接口（MVP 不实现）
- Mock 回复需包含结构化标签，模拟真实 LLM 行为

## 数据结构设计

### NPC (`app/models/npc.py`)

```python
class NPC(BaseModel):
    id: str                          # "innkeeper" | "mayor" | "miner"
    name: str                        # 显示名
    role: str                        # 角色身份描述
    personality: str                 # 性格特征
    backstory: str                   # 背景故事（Prompt 用）
    default_location: str            # 默认所在地点 ID
    dialogue_style: str              # 对话风格描述
    secrets: list[str]               # 角色秘密（影响特定条件下对话）
```

初始数据：
| id | name | role | personality | default_location |
|---|---|---|---|---|
| innkeeper | 艾琳娜 | 酒馆老板娘 | 精明、谨慎、善于察言观色 | tavern |
| mayor | 赫尔曼 | 镇长 | 表面和善、内心深沉、善于回避话题 | town_hall |
| miner | 托马斯 | 矿工 | 神经质、恐惧、说话断断续续 | abandoned_mine |

### Location (`app/models/location.py`)

```python
class Location(BaseModel):
    id: str                          # "tavern" | "town_hall" | "abandoned_mine"
    name: str                        # 显示名
    description: str                 # 环境描述
    connections: list[str]           # 可达地点 ID 列表
    available_npcs: list[str]        # 常驻 NPC ID 列表
```

| id | name | connections | available_npcs |
|---|---|---|---|
| tavern | 破晓酒馆 | ["town_hall"] | ["innkeeper"] |
| town_hall | 镇政厅 | ["tavern", "abandoned_mine"] | ["mayor"] |
| abandoned_mine | 废弃矿坑 | ["town_hall"] | ["miner"] |

### Quest (`app/models/quest.py`)

```python
class QuestStage(BaseModel):
    id: str                          # 阶段 ID
    description: str                 # 阶段描述
    completion_conditions: dict      # 完成条件（flag / 事件）
    next_stage: str | None           # 下一阶段 ID，None 表示完结

class Quest(BaseModel):
    id: str                          # "missing_case" | "lost_ledger"
    title: str
    description: str
    type: Literal["main", "side"]
    stages: list[QuestStage]
    initial_stage: str

class QuestState(BaseModel):
    quest_id: str
    current_stage: str
    completed: bool
    stage_history: list[str]
```

### Memory (`app/models/memory.py`)

```python
class Memory(BaseModel):
    id: str                          # UUID
    game_id: str                     # 游戏会话 ID
    npc_id: str                      # 关联 NPC
    type: Literal["short_term", "long_term"]
    content: str                     # 记忆内容摘要
    importance: int                  # 1-10，>=7 晋升长期记忆
    turn: int                        # 发生轮次
    created_at: datetime
    accessed_count: int              # 被召回次数
```

### Relationship (`app/models/relationship.py`)

```python
class Relationship(BaseModel):
    game_id: str
    npc_id: str
    trust: int = Field(default=30, ge=0, le=100)    # 初始 30（陌生人）
    affection: int = Field(default=30, ge=0, le=100) # 初始 30
    status: str = "neutral"                          # neutral / friendly / suspicious / trusted
```

状态阈值：
- trust < 20: hostile（敌对）
- trust 20-40: neutral（中立）
- trust 40-70: friendly（友好）
- trust > 70: trusted（信赖）

### WorldState (`app/models/game_state.py`)

```python
class WorldStateModel(BaseModel):
    game_id: str
    current_location: str = "tavern"
    time_of_day: str = "morning"     # morning / afternoon / evening / night
    turn_count: int = 0
    flags: dict[str, bool] = {}
    quest_states: dict[str, str] = {} # quest_id -> current_stage
```

### API Schemas (`app/models/api_schemas.py`)

```python
class StartGameRequest(BaseModel):
    player_name: str = "旅行者"

class StartGameResponse(BaseModel):
    game_id: str
    opening_narrative: str
    current_location: Location
    available_npcs: list[NPC]

class PlayerInputRequest(BaseModel):
    game_id: str
    message: str

class PlayerInputResponse(BaseModel):
    npc_response: str
    npc_id: str | None
    narration: str                   # 环境叙事 / 旁白
    state_changes: StateChanges
    available_actions: list[str]

class StateChanges(BaseModel):
    quest_updates: list[QuestUpdate]
    relationship_changes: list[RelationshipChange]
    flag_changes: dict[str, bool]
    location_changed: bool
    new_location: str | None

class GameStateResponse(BaseModel):
    game_id: str
    world_state: WorldStateModel
    relationships: list[Relationship]
    quest_states: list[QuestState]
    recent_memories: list[Memory]
```

## FastAPI 接口设计

### POST /game/start

**功能**：创建新游戏会话。

**请求**：
```json
{ "player_name": "旅行者" }
```

**响应**：
```json
{
  "game_id": "uuid",
  "opening_narrative": "你推开了破晓酒馆的大门...",
  "current_location": { "id": "tavern", "name": "破晓酒馆", "description": "..." },
  "available_npcs": [{ "id": "innkeeper", "name": "艾琳娜", "role": "酒馆老板娘" }]
}
```

**处理逻辑**：
1. 生成 `game_id`，初始化 WorldState（起始地点 tavern）
2. 初始化所有 NPC 的 Relationship（默认值）
3. 初始化所有 Quest 为初始阶段
4. 生成开场叙事（固定文本，不走 LLM）
5. 返回聚合响应

### POST /game/input

**功能**：处理玩家输入，返回 NPC 回复和状态变更。

**请求**：
```json
{ "game_id": "uuid", "message": "我想和老板娘聊聊最近镇上发生了什么" }
```

**响应**：
```json
{
  "npc_response": "（艾琳娜擦着杯子，眼神警惕地打量着你）...你想知道什么？这里没什么特别的。",
  "npc_id": "innkeeper",
  "narration": "酒馆里弥漫着淡淡的烟草味，角落里几个老矿工低声交谈着什么。",
  "state_changes": {
    "quest_updates": [],
    "relationship_changes": [{ "npc_id": "innkeeper", "field": "trust", "delta": 1 }],
    "flag_changes": {},
    "location_changed": false,
    "new_location": null
  },
  "available_actions": ["继续和艾琳娜交谈", "前往镇政厅", "查看任务日志"]
}
```

**处理逻辑**：
1. 加载 WorldState，确定当前地点
2. 解析玩家意图：对话 / 移动 / 查看信息 / 通用
3. 对话意图 → 确定 NPC → NPCAgent 生成回复 → 解析指令 → 执行状态变更 → 记录记忆
4. 移动意图 → WorldState.move_to → 更新地点 → 返回新地点描述
5. 记录本次交互到 MemoryManager

### GET /game/state

**功能**：查询当前游戏完整状态。

**响应**：
```json
{
  "game_id": "uuid",
  "world_state": { ... },
  "relationships": [ ... ],
  "quest_states": [ ... ],
  "recent_memories": [ ... ]
}
```

### GET /game/locations

**功能**：获取当前地点信息和可达地点列表。

### GET /game/quests

**功能**：获取所有任务及其当前状态。

## 任务状态机设计

### 主线任务：missing_case（调查边境小镇失踪案）

```
[not_started] → 玩家从 NPC 处听闻失踪传闻
      ↓
[heard_rumor] → 玩家前往废弃矿坑并发现线索
      ↓
[found_clue] → 玩家拿着线索质问镇长
      ↓
[confronted_mayor] → 揭露真相 / 矿工证实
      ↓
[resolved] ✓
```

**阶段转换条件**（由系统校验）：
| 当前阶段 | 触发条件 | 下一阶段 |
|---|---|---|
| not_started | flag `heard_about_missing` = true | heard_rumor |
| heard_rumor | location = abandoned_mine AND turn >= 3 | found_clue |
| found_clue | 与 mayor 对话 AND trust(mayor) < 60 | confronted_mayor |
| confronted_mayor | 与 miner 对话 AND 有矿坑线索 | resolved |

### 支线任务：lost_ledger（帮助老板娘找回账本）

```
[not_started] → 老板娘主动提到账本丢失（trust >= 40 时触发）
      ↓
[accepted] → 玩家答应帮忙
      ↓
[searching] → 玩家在镇政厅发现账本线索
      ↓
[found_ledger] → 将账本归还老板娘
      ↓
[resolved] ✓
```

**阶段转换条件**：
| 当前阶段 | 触发条件 | 下一阶段 |
|---|---|---|
| not_started | 与 innkeeper 对话 AND trust(innkeeper) >= 40 | accepted（需玩家同意） |
| accepted | location = town_hall AND 与 mayor 对话 | searching |
| searching | flag `found_ledger_location` = true | found_ledger |
| found_ledger | 与 innkeeper 对话 | resolved |

## 记忆系统最小设计

### 存储层

SQLite 表 `memories`：

```sql
CREATE TABLE memories (
    id TEXT PRIMARY KEY,
    game_id TEXT NOT NULL,
    npc_id TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('short_term', 'long_term')),
    content TEXT NOT NULL,
    importance INTEGER NOT NULL DEFAULT 5,
    turn INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    accessed_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (game_id) REFERENCES games(game_id)
);
CREATE INDEX idx_memories_game_npc ON memories(game_id, npc_id);
CREATE INDEX idx_memories_type ON memories(game_id, npc_id, type);
```

### 短期记忆

- 每次交互后写入一条短期记忆
- 保留最近 20 条（按 NPC 分组）
- 超出部分按 FIFO 淘汰，但先检查是否需要晋升

### 长期记忆晋升规则

- importance >= 7 的短期记忆自动晋升为长期记忆
- 晋升后从短期记忆池移除，写入长期记忆
- 长期记忆不淘汰

### 记忆召回策略（MVP）

1. 始终召回该 NPC 的所有长期记忆（MVP 数据量小）
2. 召回该 NPC 最近 5 条短期记忆
3. 按 `accessed_count` 升序 + `importance` 降序排列
4. 召回后 `accessed_count += 1`

### 记忆生成

- 由 GameEngine 在每次交互后生成摘要
- 摘要格式：`"第{turn}轮：玩家{动作摘要}，NPC{回应摘要}"`
- importance 由系统根据交互内容规则判定：
  - 涉及任务推进：importance = 8
  - 涉及好感度变化：importance = 6
  - 普通闲聊：importance = 3
  - 揭示秘密/关键信息：importance = 9

## LLM Prompt 构造策略

### Prompt 模板结构

```
[SYSTEM]
你是《边境小镇：记忆旅人》中的 NPC：{npc.name}。
{npc.role}，{npc.personality}。
{npc.backstory}
你的对话风格：{npc.dialogue_style}

当前状态：
- 地点：{location.name} - {location.description}
- 时间：{time_of_day}
- 你对旅行者的信任度：{trust}/100
- 你对旅行者的好感度：{affection}/100
- 关系状态：{status}

关于以下任务的知识：
{quest_knowledge}

你记得的事情：
{recalled_memories}

你的秘密（只在特定条件下透露）：
{npc.secrets}

严格规则：
1. 始终保持角色，不要跳出角色
2. 根据信任度调整透露信息的多少：
   - trust < 20：拒绝交谈或撒谎
   - trust 20-40：只说表面信息
   - trust 40-70：愿意分享一些内情
   - trust > 70：可以透露秘密
3. 不要一次透露所有信息，保持悬念
4. 回复结尾不要使用问号引导玩家

输出格式（严格遵守）：
[对话内容]
（你的角色扮演回复，可以包含动作描写用括号包裹）

[INSTRUCTIONS]
（如有状态变更建议，每行一条，可选）
QUEST:{quest_id}:{action}:{detail}
TRUST:{npc_id}:{delta}
FLAG:{flag_name}:{value}

[USER]
玩家说：{player_message}
```

### MockProvider 行为

MockProvider 不调用真实 LLM，而是根据以下规则生成回复：

1. 根据 NPC ID 选择预设对话模板
2. 根据 trust 值选择信息开放程度
3. 根据当前 quest 阶段决定 NPC 知道什么
4. 返回的回复中包含 `[INSTRUCTIONS]` 块，模拟 LLM 输出的结构化标签

示例 Mock 回复（innkeeper，trust=30，heard_rumor 阶段）：
```
（艾琳娜停下手里的活，压低声音）
镇上最近确实有些人不见了...但我劝你少管闲事。
这里不太平，陌生人。

[INSTRUCTIONS]
TRUST:innkeeper:2
FLAG:heard_about_missing:true
```

### 指令解析规则

GameEngine 从 NPC 回复中提取 `[INSTRUCTIONS]` 块：
- `QUEST:{quest_id}:{action}:{detail}` → 交给 QuestManager 校验并执行
- `TRUST:{npc_id}:{delta}` → 交给 RelationshipManager 校验（幅度限制 ±10）并执行
- `FLAG:{flag_name}:{value}` → 交给 WorldState.set_flag 校验后执行

所有指令都必须通过系统校验才能执行，非法指令静默忽略。

## 开发阶段拆分

### Phase 1：数据模型与基础设施

**内容**：
- Pydantic 模型定义（NPC, Location, Quest, Memory, Relationship, WorldState）
- SQLite schema 建表
- 初始数据 JSON 文件（npcs.json, locations.json, quests.json）
- FastAPI 项目骨架 + 数据库初始化

**验收标准**：
- [ ] 所有 Pydantic 模型无校验错误
- [ ] SQLite 表创建成功，可 CRUD
- [ ] 初始数据加载正常
- [ ] `uvicorn app.main:app` 启动无报错

### Phase 2：核心游戏系统

**内容**：
- WorldState：地点切换、flag 管理、时间推进
- QuestManager：状态机加载、阶段推进、完成检测
- RelationshipManager：好感度/信任度修改、状态计算
- MemoryManager：短期记忆存储、长期记忆晋升、记忆召回
- 每个系统独立的单元测试

**验收标准**：
- [ ] WorldState 可切换地点，校验连通性
- [ ] QuestManager 状态转换合法时推进，非法时拒绝
- [ ] RelationshipManager 修改值在 [0, 100] 范围内，单次变更不超过 ±10
- [ ] MemoryManager 短期记忆 FIFO 正常，importance >= 7 晋升长期记忆
- [ ] 所有单元测试通过

### Phase 3：NPCAgent 与 LLMAdapter

**内容**：
- LLMAdapter 抽象基类 + MockProvider
- MockProvider 预设回复模板（每个 NPC 至少 5 个场景模板）
- NPCAgent Prompt 构造逻辑
- NPCAgent 回复解析（提取对话文本 + 指令列表）

**验收标准**：
- [ ] MockProvider 根据不同 NPC + trust + quest 阶段返回合理回复
- [ ] Prompt 构造包含所有必要上下文
- [ ] 回复解析正确提取对话文本和指令标签
- [ ] 无效指令标签被静默忽略

### Phase 4：GameEngine 与 API

**内容**：
- GameEngine 主流程实现
- FastAPI 路由实现（POST /game/start, POST /game/input, GET /game/state）
- 玩家意图解析（简单关键词匹配：对话/移动/查看）
- 会话管理（内存 dict，game_id 为 key）

**验收标准**：
- [ ] POST /game/start 返回有效 game_id 和开场叙事
- [ ] POST /game/input 处理对话意图，返回 NPC 回复 + 状态变更
- [ ] POST /game/input 处理移动意图，切换地点
- [ ] GET /game/state 返回完整游戏状态
- [ ] 完整对话流程可跑通（start → 多轮 input → state 查询）

### Phase 5：集成测试与 CLI

**内容**：
- 端到端集成测试
- 简易 CLI 交互界面（或极简 HTML 页面）
- 错误处理和边界情况

**验收标准**：
- [ ] 端到端测试覆盖主线任务完整流程
- [ ] 端到端测试覆盖支线任务完整流程
- [ ] CLI 可正常交互，输入/输出格式清晰
- [ ] 非法输入不会导致崩溃

## 明确不进入 MVP 的功能

| 功能 | 原因 | 计划版本 |
|---|---|---|
| 真实 LLM API 调用（OpenAI） | Mock 足够验证架构 | v0.2 |
| 向量数据库（Qdrant / Chroma） | 数据量小，SQLite 够用 | v0.3 |
| LangChain / LangGraph 集成 | 过度复杂，MVP 不需要 | v0.3+ |
| 战斗系统 | 核心循环不含战斗 | v0.4 |
| 物品/背包系统 | 不影响核心玩法验证 | v0.3 |
| 角色创建 | MVP 固定角色 | v0.2 |
| 存档/读档 | 内存会话足够 MVP | v0.2 |
| 多结局系统 | 先做线性叙事 | v0.4+ |
| 程序化内容生成 | 过度复杂 | v0.5+ |
| 用户认证 | 单用户原型不需要 | v0.3 |
| 多人游戏 | 架构不支持 | 无计划 |
| 前端 UI | CLI 足够验证 | v0.2 |
| 更多地点/NPC | 先验证核心循环 | v0.2+ |
| 时间系统（昼夜影响） | 简化为固定值 | v0.3 |
| NPC 移动（NPC 离开默认地点） | 增加复杂度 | v0.3+ |
