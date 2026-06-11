# v0.5.0 TownTickSystem 设计 Spec

## 1. 当前 turn_count 和 WorldState.flags 使用方式分析

### 1.1 turn_count

`turn_count` 在 `WorldStateModel` 中定义（[game_state.py](file:///Users/chenhui/PycharmProjects/frontier_traveler/app/models/game_state.py)），初始值 0。

**递增时机**（均在写阶段）：
- `_handle_move()` — 玩家移动到新地点时 `ws.turn_count += 1`（[game_engine.py:175](file:///Users/chenhui/PycharmProjects/frontier_traveler/app/engine/game_engine.py#L175)）
- `_execute_talk_flow()` generic 空场景 — 无人可聊时递增（[game_engine.py:206](file:///Users/chenhui/PycharmProjects/frontier_traveler/app/engine/game_engine.py#L206)）
- `_apply_talk_result()` — 对话成功后递增（[game_engine.py:301](file:///Users/chenhui/PycharmProjects/frontier_traveler/app/engine/game_engine.py#L301)）

**使用方式**：
- QuestManager `_check_conditions()` 中检查 `"min_turn"` 条件（[quest.py:124-125](file:///Users/chenhui/PycharmProjects/frontier_traveler/app/systems/quest.py#L124-L125)）
- `_apply_talk_result()` 中写入记忆的 turn 字段
- `get_state()` 通过 `GameStateResponse.world_state.turn_count` 返回给前端
- Web UI 在 `turnCountEl` 展示当前轮次

**结论**：turn_count 是单调递增计数器，每次有效玩家操作 +1，是天然的时间轴度量。

### 1.2 WorldState.flags

`flags: dict[str, bool]` 存储在 games 表的 flags TEXT 字段（JSON 序列化），初始为 `{}`。

**写入来源**：
1. NPC LLM 指令 — `_dispatch_instructions()` 处理 `FLAG:name:value` 指令（[game_engine.py:366-370](file:///Users/chenhui/PycharmProjects/frontier_traveler/app/engine/game_engine.py#L366-L370)）
2. 任务推进 — `_try_advance_quests()` 在任务阶段变更时写入 `quest_{quest_id}_{stage}` 格式的 flag（[game_engine.py:413-416](file:///Users/chenhui/PycharmProjects/frontier_traveler/app/engine/game_engine.py#L413-L416)）

**使用方式**：
- QuestManager `_check_conditions()` 中检查 `"flag"` + `"value"` 条件（[quest.py:116-119](file:///Users/chenhui/PycharmProjects/frontier_traveler/app/systems/quest.py#L116-L119)）
- `get_state()` 返回完整 flags 字典
- Web UI 在 flags 面板展示

**结论**：flags 是轻量级布尔状态机，可复用为 town event 的去重标记和前置条件检查器。

## 2. TownTickSystem 职责边界

### 它做什么

1. **加载 town_events.json 配置**：在 `__init__` 时读取事件定义
2. **检查触发条件**：根据当前 turn_count、flags 判断是否有事件应该触发
3. **返回待触发事件列表**：提供 `tick(db, ws, state_changes)` 方法，返回本轮新触发的事件
4. **设置事件 flag**：触发后通过 `ws.flags` 设置 `town_event_{event_id}` 标记，防止重复触发
5. **返回结构化数据**：每个事件包含 narration（叙述文本）和 set_flags（需要设置的 flag），供 GameEngine 写入

### 它不做什么

1. **不直接操作数据库**：不自行 commit/rollback，由 GameEngine 统一管理事务
2. **不修改 turn_count**：turn_count 由 GameEngine 在 move/talk 中管理
3. **不调用 LLM**：事件内容来自 JSON 配置，无需动态生成
4. **不移动 NPC**：NPC 位置由 locations.json 静态定义，v0.5 不引入动态 NPC 位置
5. **不修改 QuestManager / RelationshipManager / MemoryManager**：与现有系统完全解耦
6. **不修改 GameEngine 核心流程**：只在已有写阶段插入一个 `tick()` 调用
7. **不生成 LLM 指令**：town event 不产出 TRUST/QUEST/FLAG 指令
8. **不控制游戏节奏**：不引入时间系统、日夜循环

## 3. 推荐数据源

### 3.1 使用 app/data/town_events.json

在 `app/data/` 目录下新增 `town_events.json`，与 `quests.json`、`npcs.json`、`locations.json` 并列。遵循现有数据文件惯例。

### 3.2 town event 字段设计

```json
[
  {
    "id": "traveler_arrival",
    "title": "神秘旅人",
    "narration": "一个裹着斗篷的陌生人走进了镇子，他似乎在寻找什么人。他在酒馆门口站了一会儿，又朝矿坑的方向去了。",
    "trigger_turn": 5,
    "required_flags": {},
    "forbidden_flags": ["town_event_traveler_arrival"],
    "set_flags": ["town_event_traveler_arrival", "stranger_seen"],
    "importance": 6
  },
  {
    "id": "market_closed",
    "title": "集市关闭",
    "narration": "镇上的商贩们开始收拾摊位。据说是镇长下令暂时关闭集市，理由是'近期治安不稳定'。",
    "trigger_turn": 8,
    "required_flags": {"heard_about_missing": true},
    "forbidden_flags": ["town_event_market_closed"],
    "set_flags": ["town_event_market_closed"],
    "importance": 4
  },
  {
    "id": "night_whispers",
    "title": "深夜低语",
    "narration": "夜深了，你隐约听到矿坑方向传来奇怪的声响。像是有人在呼救，又像是风穿过废弃矿道的回声。",
    "trigger_turn": 10,
    "required_flags": {"quest_missing_case_heard_rumor": true},
    "forbidden_flags": ["town_event_night_whispers"],
    "set_flags": ["town_event_night_whispers", "heard_cries_at_night"],
    "importance": 7
  },
  {
    "id": "mayor_announcement",
    "title": "镇长公告",
    "narration": "镇长在镇政厅前贴出告示：'近日有外来者散布不实谣言，扰乱治安。如有发现可疑人员，请立即上报。'告示上有镇长的签名，字迹看起来有些潦草。",
    "trigger_turn": 12,
    "required_flags": {},
    "forbidden_flags": ["town_event_mayor_announcement"],
    "set_flags": ["town_event_mayor_announcement", "mayor_wary"],
    "importance": 5
  },
  {
    "id": "miner_disappearance",
    "title": "托马斯失踪",
    "narration": "你再次来到矿坑入口，但托马斯不见了。地上散落着他的矿灯和一张纸条，上面潦草地写着：'他们知道了，我必须离开。'",
    "trigger_turn": 15,
    "required_flags": {"quest_missing_case_found_clue": true},
    "forbidden_flags": ["town_event_miner_disappearance"],
    "set_flags": ["town_event_miner_disappearance", "miner_gone"],
    "importance": 9
  }
]
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 唯一标识，用于去重 flag 名 |
| title | string | 事件标题，Web UI 展示用 |
| narration | string | 叙述文本，直接展示给玩家 |
| trigger_turn | int | 触发轮次（>= 时检查） |
| required_flags | dict | 必须满足的 flag 条件（key=flag名, value=布尔值） |
| forbidden_flags | list[str] | 任一存在则不触发（用于去重） |
| set_flags | list[str] | 触发后设置的 flag 列表 |
| importance | int | 事件重要度（1-10），决定展示样式和是否写入记忆 |

## 4. 事件触发规则

### 4.1 trigger_turn

- `ws.turn_count >= event.trigger_turn` 时才有资格触发
- 不是精确匹配，是"达到或超过"。理由：如果玩家在 turn=5 时没有满足 required_flags，到 turn=7 满足后仍然可以触发

### 4.2 required_flags

- 所有 required_flags 中的条件必须全部满足
- 复用 QuestManager 的 flag 检查模式：`ws.flags.get(flag_name) == expected_value`

### 4.3 forbidden_flags

- 只要 forbidden_flags 中任意一个存在于 `ws.flags` 中，事件不触发
- 主要用途：防止已触发的事件重复触发（`town_event_{id}` flag）
- 也可以用于互斥事件（事件 A 触发后阻止事件 B）

### 4.4 set_flags

- 事件触发后，将 set_flags 中的所有 flag 设置为 True
- 由 GameEngine 统一写入 `ws.flags`，TownTickSystem 不直接修改

### 4.5 move_npcs — 不进入 v0.5

**理由**：
- 当前 NPC 位置由 locations.json 静态定义，NPC 不移动
- 移动 NPC 需要：(a) 动态位置系统；(b) NPC 在场检查逻辑更新；(c) 影响所有依赖 `get_available_npcs()` 的代码
- 违反"如无必要勿增实体"
- 建议留到 v0.6 或更晚

## 5. 如何避免事件重复触发

### 5.1 方案：flag 去重

每个 town event 的 `forbidden_flags` 必须包含自身的去重标记 `"town_event_{event_id}"`。触发后 `set_flags` 中也包含该标记。

```json
{
  "id": "traveler_arrival",
  "forbidden_flags": ["town_event_traveler_arrival"],
  "set_flags": ["town_event_traveler_arrival", "stranger_seen"]
}
```

**流程**：
1. `tick()` 检查 `ws.flags.get("town_event_traveler_arrival")` — False → 继续
2. 条件满足 → 触发事件
3. GameEngine 将 `"town_event_traveler_arrival": True` 写入 ws.flags
4. 下次 `tick()` 检查 `ws.flags.get("town_event_traveler_arrival")` — True → 跳过

**优势**：
- 零额外存储，复用 WorldState.flags
- 无需新表、无需新字段
- 与现有 quest flag 机制完全一致

### 5.2 不使用独立触发记录表

**理由**：
- flags 已足够表达"是否触发过"
- 新增表违反"如无必要勿增实体"
- 当前事件量预计 < 10 个，flags 足够

## 6. GameEngine 调用时机

### 6.1 推荐：turn_count +1 之后、任务推进之后

**调用位置**：在 `_apply_talk_result()` 和 `_handle_move()` 中，`turn_count += 1` 且 `_try_advance_quests()` 执行完毕之后。

```python
# _apply_talk_flow 中（简化）：
ws.turn_count += 1
await WorldState.save(db, ws, auto_commit=False)
await self._dispatch_instructions(...)
await self._try_advance_quests(db, ws, state_changes, npc_id=npc_id)
# ↓ 新增：在此处调用
town_events = await self.town_tick_system.tick(db, ws, state_changes)
# ... 继续写记忆等
```

**理由**：
- turn_count 已递增 → 事件可以基于当前轮次判断
- quest 可能刚推进 → 事件 required_flags 可能依赖任务 flag（如 `quest_missing_case_found_clue`）
- 仍在同一事务中 → town event 的 flag 变更随主事务一起 commit/rollback
- 不影响 LLM 调用（LLM 在读阶段已执行完毕）

### 6.2 _handle_move 中也调用

移动操作同样递增 turn_count，也需要检查 town event。调用位置同理：turn_count +1 之后、quest 推进之后。

### 6.3 时序图

```
玩家输入
  → _parse_intent()
  → [读阶段] LLM 调用（talk 流程）
  → [写阶段]
      → turn_count += 1
      → _dispatch_instructions() → flags 可能变更
      → _try_advance_quests() → flags 可能变更
      → town_tick_system.tick() ← 在此处
      → 写记忆
      → db.commit()
```

## 7. /game/input response 是否需要扩展

### 7.1 建议：扩展 StateChanges.town_events

在 `StateChanges` 模型中新增：

```python
class TownEvent(BaseModel):
    event_id: str
    title: str
    narration: str
    importance: int

class StateChanges(BaseModel):
    quest_updates: list[QuestUpdate] = []
    relationship_changes: list[RelationshipChange] = []
    flag_changes: dict[str, bool] = {}
    location_changed: bool = False
    new_location: str | None = None
    town_events: list[TownEvent] = []  # 新增
```

**理由**：
- 保持向后兼容：`town_events` 默认空列表，旧客户端不受影响
- 复用现有 `state_changes` 通道，不需要新增顶层字段
- 前端已有监听 `state_changes` 的逻辑，新增字段天然集成

### 7.2 /game/input 返回值变化

```json
{
  "npc_response": "...",
  "state_changes": {
    "quest_updates": [],
    "relationship_changes": [],
    "flag_changes": {"stranger_seen": true},
    "town_events": [
      {
        "event_id": "traveler_arrival",
        "title": "神秘旅人",
        "narration": "一个裹着斗篷的陌生人走进了镇子...",
        "importance": 6
      }
    ]
  }
}
```

## 8. /game/state 是否需要展示已触发事件

### 8.1 建议：展示，通过 WorldStateModel 扩展

在 `GameStateResponse` 中新增 `triggered_town_events` 字段：

```python
class GameStateResponse(BaseModel):
    game_id: str
    world_state: WorldStateModel
    relationships: list[Relationship]
    quest_states: list[QuestState]
    recent_memories: list[Memory]
    triggered_town_events: list[TownEvent] = []  # 新增
```

`GameEngine.get_state()` 中：
- 扫描 `ws.flags` 中以 `town_event_` 开头的 flag
- 用 TownTickSystem 按 id 查找对应事件的 title/narration
- 返回已触发事件列表

**向后兼容**：新字段默认空列表。

## 9. Web UI 如何展示小镇事件

### 9.1 对话面板：作为系统消息

在 `sendMessage()` 的 `.then()` 回调中，检查 `data.state_changes.town_events`：

```javascript
if (data.state_changes && data.state_changes.town_events &&
    data.state_changes.town_events.length > 0) {
    data.state_changes.town_events.forEach(function(evt) {
        addDialogBubble("system", "🌆 " + escapeHtml(evt.title) + "：" + escapeHtml(evt.narration));
    });
}
```

**时机**：在 NPC 对话气泡之后、`refreshState()` 之前展示。理由：事件是环境变化，应在角色对话之后呈现。

### 9.2 状态面板：新增事件区域

在 index.html 中新增一个 `town-events` 区域（与 memories/flags 并列）。在 `refreshState()` 中渲染已触发事件列表：

```javascript
// refreshState() 中新增
if (data.triggered_town_events && data.triggered_town_events.length > 0) {
    townEventsEl.innerHTML = "";
    data.triggered_town_events.forEach(function(evt) {
        var item = document.createElement("div");
        item.className = "town-event-item" + (evt.importance >= 7 ? " town-event-important" : "");
        item.textContent = "[" + escapeHtml(evt.title) + "] " +
            (evt.narration.length > 60 ? evt.narration.substring(0, 60) + "..." : evt.narration);
        townEventsEl.appendChild(item);
    });
}
```

### 9.3 高重要性事件写入记忆

importance >= 7 的 town event 额外写入一条系统记忆（type=short_term, npc_id="system"），让 NPC 可以通过 recall 感知到重大世界事件。此功能为可选增强，可在实现阶段决定是否纳入。

## 10. 测试计划

### 10.1 TownTickSystem 单元测试（新增 test_town_tick.py）

| 测试 | 验证点 |
|------|--------|
| test_tick_no_events_when_turn_too_low | turn_count < trigger_turn 时不触发 |
| test_tick_triggers_on_exact_turn | turn_count == trigger_turn 时触发 |
| test_tick_triggers_after_turn | turn_count > trigger_turn 时仍可触发 |
| test_tick_requires_flags | required_flags 不满足时不触发 |
| test_tick_respects_forbidden_flags | forbidden_flags 已存在时不触发 |
| test_tick_no_repeat_after_trigger | 已触发事件不重复触发 |
| test_tick_sets_flags | 触发后正确设置 set_flags |
| test_tick_multiple_events | 多个事件可同时触发 |
| test_tick_returns_narration | 返回值包含正确的 narration 和 title |

### 10.2 GameEngine 集成测试（test_game_engine.py 新增）

| 测试 | 验证点 |
|------|--------|
| test_talk_flow_triggers_town_event | 对话流程中 town event 出现在 state_changes |
| test_move_flow_triggers_town_event | 移动流程中 town event 出现在 state_changes |
| test_town_event_after_turn_increment | 确认在 turn_count 递增后检查 |
| test_town_event_after_quest_advance | 确认在 quest 推进后检查 |

### 10.3 Web UI 测试（test_web_ui.py 新增）

| 测试 | 验证点 |
|------|--------|
| test_js_handles_town_events | app.js 包含 town_events 渲染逻辑 |
| test_api_response_contains_town_events_schema | PlayerInputResponse 包含 town_events 字段 |

### 10.4 API 向后兼容测试

| 测试 | 验证点 |
|------|--------|
| test_state_changes_default_empty_town_events | 无事件时 town_events 为空列表 |
| test_get_state_default_empty_triggered_events | 无触发事件时 triggered_town_events 为空列表 |
| 现有 107 个测试全部通过 | 无回归 |

## 11. 不进入 v0.5 的功能

| 功能 | 原因 |
|------|------|
| NPC 自主对话 | 需要多 Agent 循环调度，架构改动过大 |
| 多 Agent 计划 | 需要计划引擎和 Agent 间通信 |
| 复杂日程（日夜循环） | 需要 turn→时间映射、NPC 行为模式，复杂度高 |
| 战斗/背包 | 完整玩法系统，超出范围 |
| 新数据库表 | flags 足够表达当前需求 |
| NPC 动态位置 | 影响 get_available_npcs 和所有依赖代码 |
| 事件条件脚本（min_trust 等复杂条件） | 当前只需要 flag + turn，够用 |
| 事件优先级排序 | 同轮次多事件时按 JSON 顺序即可 |
| 事件链（event A 触发 event B） | 可通过 required_flags 自然实现，无需额外机制 |

## 12. 风险评估

### P0（实现前必须注意）

| # | 风险 | 缓解措施 |
|---|------|----------|
| P0-1 | town event flag 写入与 quest flag 写入在同一事务中，如果 town_tick 在 quest 推进之后执行，town event 的 set_flags 可能被下次 quest 检查误读 | town event 的 set_flags 使用 `town_event_` 前缀命名空间，与 `quest_` 前缀不冲突 |
| P0-2 | 多个事件同时触发时 narration 顺序影响体验 | 按 JSON 定义顺序触发，narration 按顺序追加到 state_changes.town_events |
| P0-3 | StateChanges 新增 town_events 字段可能影响现有 API consumer | 默认空列表，向后兼容；已有测试全部通过确认 |

### P1（影响体验但不阻塞）

| # | 风险 | 缓解措施 |
|---|------|----------|
| P1-1 | 事件 narration 是静态文本，无论玩家之前做了什么，内容完全相同 | v0.5 接受此限制；未来可引入条件分支 narration |
| P1-2 | 高 importance town event 写入 NPC 记忆可能增加知识泄露风险 | 系统记忆 npc_id="system" 标记清晰，NPC prompt 中可通过来源区分 |
| P1-3 | 已触发的 town event 在 get_state 中全部返回，长游戏后列表可能很长 | 可限制只返回最近 5 条，但 v0.5 先全量返回观察 |

### P2（后续优化）

| # | 建议 |
|---|------|
| P2-1 | 未来可引入 `trigger_turn_max` 字段，超过一定轮次后事件过期 |
| P2-2 | 未来可引入事件条件中的 min_trust / location 检查 |
| P2-3 | 未来可实现 NPC 对 town event 的反应（基于事件的记忆自动生成对话提示） |
| P2-4 | 未来可实现事件链（event A 完成后解锁 event B 的 required_flags） |

## 13. 实现文件范围

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/data/town_events.json` | 新增 | 5 个初始事件定义 |
| `app/systems/town_tick.py` | 新增 | TownTickSystem 类 |
| `app/models/api_schemas.py` | 修改 | 新增 TownEvent 模型，StateChanges 新增 town_events 字段 |
| `app/engine/game_engine.py` | 修改 | __init__ 新增 town_tick_system，_apply_talk_result 和 _handle_move 中调用 tick()，get_state 返回 triggered_town_events |
| `app/static/app.js` | 修改 | sendMessage 中渲染 town_events，refreshState 中渲染已触发事件 |
| `app/templates/index.html` | 修改 | 新增 town-events 区域 |
| `app/static/style.css` | 修改 | 新增 .town-event-item 样式 |
| `tests/test_town_tick.py` | 新增 | TownTickSystem 单元测试 |
| `tests/test_game_engine.py` | 修改 | 新增 town event 集成测试 |
| `tests/test_web_ui.py` | 修改 | 新增 town_events 相关测试 |

**不修改的文件**：
- `app/systems/memory.py` — 无改动
- `app/systems/quest.py` — 无改动
- `app/systems/relationship.py` — 无改动
- `app/agents/npc_agent.py` — 无改动
- `app/database.py` — 无改动
- 数据库 schema — 无改动

## 14. 结论

**建议进入实现阶段。** 理由：

1. **改动范围最小**：新增 1 个 System + 1 个 JSON 数据文件 + 1 个测试文件；修改 4 个现有文件。不触碰 Memory/Quest/Relationship/NPCAgent 核心逻辑
2. **零 DB 变更**：完全复用 WorldState.flags 实现去重和前置条件
3. **向后兼容**：StateChanges 新增字段默认空列表，现有 API consumer 不受影响
4. **测试可覆盖**：预计新增约 15 个测试，全部可通过 MockProvider 和断言验证
5. **风险可控**：3 个 P0 风险都有明确缓解措施，不影响核心三阶段架构
6. **体验提升明显**：玩家会感受到小镇在"活着"，而不是完全被动的对话背景
