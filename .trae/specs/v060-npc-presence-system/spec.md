# v0.6.0 NpcPresenceSystem 设计 Spec

## 1. 当前 NPC 可见性和地点逻辑分析

### 1.1 核心数据流

NPC 位置信息分散在三个数据源中：

| 数据源 | 字段 | 作用 |
|--------|------|------|
| `locations.json` → `Location.available_npcs` | `["innkeeper"]` | 每个地点有哪些 NPC |
| `npcs.json` → `NPC.default_location` | `"tavern"` | NPC 的默认地点（仅用于角色定义） |
| `WorldState.get_available_npcs()` | 读取 `Location.available_npcs` | 返回当前地点的 NPC 列表 |

### 1.2 调用链分析

**`/game/start`** → `start_game()`
```
location = self.world_state.get_location(ws.current_location)  # tavern
npc_ids = self.world_state.get_available_npcs(ws.current_location)  # ["innkeeper"]
→ 返回 available_npcs: [PublicNPC(innkeeper)]
```

**`/game/state`** → `get_state()`
- 不直接返回 available_npcs，但返回 `ws.current_location`
- 前端通过 `data.world_state.current_location` 显示位置名称

**`/game/input` (talk)** → `_build_talk_context()`
```
npc_ids = self.world_state.get_available_npcs(ws.current_location)  # 读取 Location.available_npcs
if npc_id not in available_npcs:
    → 返回 "{npc_name}不在这里。"
```

**`/game/input` (move)** → `_handle_move()`
```
→ 无 NPC 检查，只更新 current_location
→ narration 中展示新地点描述
```

**`_get_available_actions()`**
```
npcs = self.world_state.get_available_npcs(ws.current_location)
→ 生成 "和{npc.name}交谈" 动作建议
```

### 1.3 关键发现

1. **NPC 位置完全静态**：`Location.available_npcs` 是 `locations.json` 中的硬编码列表，运行时永不改变
2. **NPC.default_location 未被使用**：`npcs.json` 中每个 NPC 都有 `default_location` 字段，但 GameEngine/WorldState 从未读取它——位置完全由 `locations.json` 的 `available_npcs` 决定
3. **无动态 NPC 移动机制**：没有代码在任何时刻修改 `available_npcs`
4. **town_events.json 的 `miner_gone` flag 已设置但无效果**：v0.5.0 的 "托马斯失踪" 事件设置了 `miner_gone` flag，但没有任何代码检查该 flag 来移除矿工

### 1.4 当前方法签名

```python
# WorldState (静态)
def get_available_npcs(self, location_id: str) -> list[str]

# Location model
class Location(BaseModel):
    available_npcs: list[str]  # 硬编码
```

## 2. NpcPresenceSystem 职责边界

### 它做什么

1. **加载 NPC 位置规则**：从 `npcs.json` 扩展字段或新增 `npc_presence_rules.json` 读取规则
2. **解析 NPC 当前位置**：提供 `get_npcs_at_location(ws, location_id) -> list[str]` 方法，根据规则 + flags + turn_count 返回当前可见 NPC
3. **解析 NPC 可见性**：某些 NPC 可能在某地点但不可见（隐藏、伪装）
4. **返回所有 NPC 位置映射**：提供 `get_all_npc_locations(ws) -> dict[str, str]` 供 get_state 使用
5. **纯函数式**：不修改 ws、不调用 DB、不写 flags

### 它不做什么

1. **不修改 WorldState.flags**：只读取 flags
2. **不修改 locations.json 的 available_npcs**：不改变静态数据
3. **不移动 NPC**：不产生"NPC 从 A 移到 B"的事件
4. **不调用 LLM**：位置判断完全基于规则
5. **不产生 narration**：NPC 不在场的叙述由 GameEngine 处理
6. **不直接修改 WorldState.get_available_npcs()**：提供一个新方法，GameEngine 选择何时使用
7. **不处理 NPC 自主行为**：NPC 不会主动选择去哪里

## 3. 推荐数据源

### 方案对比

| 维度 | 扩展 npcs.json | 新增 npc_presence_rules.json |
|------|----------------|------------------------------|
| 改动量 | 在每个 NPC 对象中新增 presence_rules 字段 | 新增独立文件 |
| 职责清晰度 | NPC 定义和位置规则混合 | 关注点分离 |
| 加载方式 | 修改 NPC 模型 + NPCAgent 加载逻辑 | 独立 System 加载 |
| 向后兼容 | 需修改 NPC model 加 presence_rules 可选字段 | 零影响 |
| 遵循惯例 | quests.json、town_events.json 都是独立文件 | ✅ |

### 推荐：新增 `app/data/npc_presence_rules.json`

**理由**：
1. 遵循现有惯例：`quests.json`、`town_events.json` 都是独立的规则文件
2. 不修改 NPC model 和 NPCAgent：符合"如无必要勿增实体"
3. 关注点分离：NPC 定义（角色信息）vs NPC 位置（世界规则）
4. 零风险：不影响任何现有代码的加载逻辑

## 4. 规则字段设计

### 4.1 字段定义

```json
[
  {
    "npc_id": "miner",
    "rules": [
      {
        "location": "abandoned_mine",
        "visible": false,
        "when_flags": {"miner_gone": true},
        "unless_flags": {},
        "reason": "托马斯已经离开了矿坑"
      },
      {
        "location": "tavern",
        "visible": true,
        "when_flags": {"miner_gone": true, "stranger_seen": true},
        "unless_flags": {},
        "reason": "托马斯逃到酒馆寻求庇护"
      }
    ]
  }
]
```

### 4.2 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| npc_id | string | 是 | 关联到 npcs.json 中的 NPC |
| rules | array | 是 | 位置规则列表，按顺序检查 |
| rules[].location | string | 是 | 规则匹配时 NPC 所在地点 |
| rules[].visible | bool | 是 | NPC 是否可见（false = 隐藏/离开） |
| rules[].when_flags | dict | 是 | 触发此规则的 flag 条件（全满足才匹配） |
| rules[].unless_flags | dict | 否 | 阻止匹配的 flag 条件 |
| rules[].reason | string | 否 | 位置变化的原因，供 narration 使用 |

### 4.3 关于 min_turn / max_turn

**不纳入 v0.6**。

理由：
- turn_count 已通过 `town_events.json` 间接影响 flags（town event 触发后设置 flag → presence rule 匹配 flag）
- 如果需要 turn 条件，应通过 town event 中转，而非在 presence rule 中直接检查 turn
- 保持规则简单：只读 flags

### 4.4 关于 reason

**纳入 v0.6**。

理由：
- 当 NPC 不在场时，GameEngine 可以用 reason 生成更友好的提示（如"托马斯已经离开了矿坑"而非"这里没有人"）
- 零成本：只读字符串，不影响逻辑
- 可选字段：没有 reason 时回退到通用提示

## 5. 规则优先级

### 5.1 匹配算法

```
对于每个 NPC：
  1. 遍历 rules 列表（按 JSON 数组顺序）
  2. 找到第一条 when_flags 全满足且 unless_flags 全不满足的规则
  3. 如果找到 → 使用该规则的 location 和 visible
  4. 如果没找到 → 使用 npcs.json 中的 default_location，visible=true
```

### 5.2 后者覆盖前者？

不是。按数组顺序，**第一条匹配**即生效（类似 switch-case 的 first-match 语义）。

理由：
- first-match 更直觉：把最常见的规则放前面
- 避免"最后一条赢"的混淆（需要理解所有规则才能判断最终结果）

### 5.3 不需要 priority 字段

理由：
- JSON 数组顺序就是优先级
- 每个NPC预计只有 2-3 条规则，不需要额外排序机制
- 与 town_events.json 保持一致（无 priority 字段）

## 6. 与 TownTickSystem 的关系

### 6.1 两者完全解耦

```
TownTickSystem:
  → 写 flags（town_event_xxx, miner_gone, stranger_seen 等）
  → 不关心 NPC 在哪里

NpcPresenceSystem:
  → 读 flags
  → 不关心 flags 是谁设置的
```

### 6.2 数据流

```
town_events.json → TownTickSystem.tick() → ws.flags
                                                  ↓
npcs.json (default) ────────────────────→ NpcPresenceSystem.get_npcs_at_location()
npc_presence_rules.json ────────────────→        ↑
                                             读 ws.flags
```

### 6.3 不直接交互

两个 System 互不引用、互不调用。通过 `ws.flags` 间接通信。

## 7. GameEngine 集成点

### 7.1 核心改动：替换 WorldState.get_available_npcs()

当前所有调用 `self.world_state.get_available_npcs(location_id)` 的地方，改为调用 `self.npc_presence_system.get_npcs_at_location(ws, location_id)`。

涉及方法：
- `start_game()` — [game_engine.py:54](file:///Users/chenhui/PycharmProjects/frontier_traveler/app/engine/game_engine.py#L54)
- `_build_talk_context()` — [game_engine.py:270](file:///Users/chenhui/PycharmProjects/frontier_traveler/app/engine/game_engine.py#L270) 和 [game_engine.py:277](file:///Users/chenhui/PycharmProjects/frontier_traveler/app/engine/game_engine.py#L277)
- `_get_available_actions()` — [game_engine.py:447](file:///Users/chenhui/PycharmProjects/frontier_traveler/app/engine/game_engine.py#L447)

### 7.2 start_game()

```python
# 旧
npc_ids = self.world_state.get_available_npcs(ws.current_location)
# 新
npc_ids = self.npc_presence_system.get_npcs_at_location(ws, ws.current_location)
```

游戏开始时 ws.flags = {}，所有 when_flags 不满足，presence rule 不生效 → 回退到 npcs.json 的 default_location → 行为与当前完全一致。

### 7.3 get_state()

新增返回 `npc_locations: dict[str, str]`，显示所有 NPC 当前所在地点。

### 7.4 process_input (talk)

`_build_talk_context()` 中已经检查 NPC 是否在当前地点。改用 `npc_presence_system` 后，NPC 不在场时：

```python
if npc_id not in available_npcs:
    npc = self.npc_agent.get_npc(npc_id)
    npc_name = npc.name if npc else npc_id
    reason = self.npc_presence_system.get_absence_reason(ws, npc_id, ws.current_location)
    return {"error": reason or f"{npc_name}不在这里。"}
```

### 7.5 process_input (move)

`_handle_move()` 移动后 narration 展示新地点描述，不需要直接展示 NPC。但 `_get_available_actions()` 会更新可用动作列表。

## 8. API 扩展

### 8.1 available_npcs 保持 PublicNPC list

`StartGameResponse.available_npcs` 和 `PlayerInputResponse.available_actions` 保持不变。NPC 列表已通过这些字段返回。

### 8.2 新增 npc_locations 到 GameStateResponse

```python
class NpcLocationInfo(BaseModel):
    npc_id: str
    name: str
    location: str
    visible: bool

class GameStateResponse(BaseModel):
    ...
    npc_locations: list[NpcLocationInfo] = []  # 新增
```

**向后兼容**：默认空列表。

### 8.3 API 变化总结

| 端点 | 变化 |
|------|------|
| POST /game/start | `available_npcs` 内容可能随 flags 变化（但开始时 flags 为空，行为不变） |
| POST /game/input | `available_actions` 和 NPC 可达性可能变化；NPC 不在场时 error message 更友好 |
| GET /game/state | 新增 `npc_locations` 字段 |

## 9. Web UI 展示

### 9.1 右侧状态面板：新增 NPC 位置区域

在 relationships 和 quest_states 之间，新增一个"NPC 位置"区域：

```javascript
// refreshState() 中
if (data.npc_locations && data.npc_locations.length > 0) {
    npcLocationsEl.innerHTML = "";
    data.npc_locations.forEach(function(npc) {
        var item = document.createElement("div");
        item.className = "npc-location-item";
        var locName = LOC_NAME_MAP[npc.location] || npc.location;
        if (npc.visible) {
            item.textContent = npc.name + " - " + locName;
        } else {
            item.className += " npc-location-hidden";
            item.textContent = npc.name + " - 行踪不明";
        }
        npcLocationsEl.appendChild(item);
    });
}
```

### 9.2 不可见 NPC

显示为"行踪不明"而非完全隐藏。

理由：
- 玩家已知 3 个 NPC 的存在（在 start_game 时已介绍）
- 完全隐藏会让玩家困惑
- "行踪不明"暗示 NPC 存在但不知去向，更符合叙事

### 9.3 位置名称映射

新增 `LOC_NAME_MAP`：

```javascript
const LOC_NAME_MAP = {
    tavern: "破晓酒馆",
    town_hall: "镇政厅",
    abandoned_mine: "废弃矿坑"
};
```

## 10. 测试计划

### 10.1 NpcPresenceSystem 单元测试（新增 test_npc_presence.py）

| 测试 | 验证点 |
|------|--------|
| test_default_location_when_no_rules | 无规则时回退到 npcs.json default_location |
| test_default_location_when_no_flags | 有规则但 flags 为空时回退到 default |
| test_rule_matches_when_flags_satisfied | when_flags 全满足时规则生效 |
| test_rule_not_match_when_flags_missing | when_flags 部分满足时规则不生效 |
| test_unless_flags_block_rule | unless_flags 阻止规则匹配 |
| test_first_match_wins | 多条规则时第一条匹配的生效 |
| test_visible_false | visible=false 时 NPC 在地点但不可见 |
| test_get_all_npc_locations | 返回所有 NPC 的位置映射 |
| test_get_absence_reason | 返回 NPC 不在场的原因文本 |
| test_miner_gone_flag_removes_miner | miner_gone=true 时矿工从矿坑消失 |

### 10.2 GameEngine 集成测试（test_game_engine.py 新增）

| 测试 | 验证点 |
|------|--------|
| test_talk_to_npc_not_present | NPC 不在场时返回友好提示 |
| test_talk_to_npc_after_flag_change | flag 设置后 NPC 变为不可达 |
| test_available_actions_changes_with_flags | flag 改变后 available_actions 更新 |
| test_start_game_default_npc_list | 游戏开始时 NPC 列表与当前行为一致 |

### 10.3 API 兼容性测试（test_game_engine.py 新增）

| 测试 | 验证点 |
|------|--------|
| test_get_state_returns_npc_locations | get_state 返回 npc_locations |
| test_npc_locations_default_empty | 无规则时 npc_locations 仍正确返回 |

### 10.4 Web UI 测试（test_web_ui.py 新增）

| 测试 | 验证点 |
|------|--------|
| test_js_handles_npc_locations | app.js 包含 npc_locations 渲染逻辑 |
| test_index_contains_npc_locations_section | index.html 包含 NPC 位置区域 |

### 10.5 现有测试兼容

- 124 个现有测试全部通过
- MockProvider 场景下 flags 始终为空 → 所有规则不匹配 → 回退到 default_location → 行为完全不变

## 11. 不进入 v0.6 的功能

| 功能 | 原因 |
|------|------|
| NPC 自主移动 | 需要 NPC 决策逻辑，v0.6 只做规则驱动 |
| NPC 日程（基于 turn 的时间表） | 可通过 town event + flag 间接实现 |
| NPC 自主对话 | 需要多 Agent 调度 |
| 战斗/背包 | 完整玩法系统 |
| 新数据库表 | flags 足够 |
| NPC 情绪影响位置 | 复杂度过高 |
| 动态生成 presence rule | 需 LLM 参与 |
| NPC 追踪玩家 | 需要主动行为系统 |

## 12. 风险评估

### P0（实现前必须注意）

| # | 风险 | 缓解措施 |
|---|------|----------|
| P0-1 | NPC 从某地点消失后，依赖该 NPC 的任务无法继续 | presence rule 不影响 quest 逻辑；quest 条件基于 flags 而非 NPC 在场；同时确保矿工消失后仍在其他地点可达 |
| P0-2 | 替换 `get_available_npcs()` 后，所有现有测试失败 | 新方法在 flags={} 时行为与旧方法完全一致；现有测试 flags 始终为空 |
| P0-3 | start_game() 中 ws.flags 为空，但 npc_presence_system 需要 ws 参数 | 空时回退到 default_location，行为不变 |

### P1（影响体验但不阻塞）

| # | 风险 | 缓解措施 |
|---|------|----------|
| P1-1 | NPC 在两个地点间来回"瞬移"（rule A 匹配时在酒馆，rule B 匹配时在矿坑） | 确保规则设计逻辑自洽；test_first_match_wins 验证 |
| P1-2 | 不可见 NPC 的"行踪不明"提示可能不够自然 | v0.6 接受；未来可让 LLM 生成更自然的描述 |
| P1-3 | reason 字段未被充分利用（只在 error message 中使用） | v0.6 最小使用；未来可用于 narration 增强 |

### P2（后续优化）

| # | 建议 |
|---|------|
| P2-1 | 未来可支持 location 为 null（NPC 完全离开小镇） |
| P2-2 | 未来可支持 NPC 在多个地点可见（巡逻模式） |
| P2-3 | 未来可让 importance >= 7 的 NPC 位置变化写入系统记忆 |
| P2-4 | 未来可将 LOC_NAME_MAP 与 locations.json 共享，避免前端硬编码 |

## 13. 初始规则数据

与 v0.5.0 的 town_events.json 对齐，v0.6.0 仅定义 1 组规则（矿工托马斯）：

```json
[
  {
    "npc_id": "miner",
    "rules": [
      {
        "location": "tavern",
        "visible": true,
        "when_flags": {"miner_gone": true},
        "unless_flags": {},
        "reason": "托马斯逃到酒馆寻求庇护"
      },
      {
        "location": "abandoned_mine",
        "visible": false,
        "when_flags": {"miner_gone": true},
        "unless_flags": {},
        "reason": "托马斯已经不在矿坑了，地上散落着他的矿灯"
      }
    ]
  }
]
```

**innkeeper 和 mayor 不需要规则**：他们始终在各自地点，flags={} 时回退到 default_location 即可。

## 14. 实现文件范围

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/data/npc_presence_rules.json` | 新增 | 矿工位置规则 |
| `app/systems/npc_presence.py` | 新增 | NpcPresenceSystem 类 |
| `app/models/api_schemas.py` | 修改 | 新增 NpcLocationInfo，GameStateResponse 新增 npc_locations |
| `app/engine/game_engine.py` | 修改 | 初始化 NpcPresenceSystem，替换 4 处 get_available_npcs 调用 |
| `app/static/app.js` | 修改 | 新增 LOC_NAME_MAP，refreshState 渲染 npc_locations |
| `app/templates/index.html` | 修改 | 新增 npc-locations 区域 |
| `app/static/style.css` | 修改 | 新增 .npc-location-item / .npc-location-hidden 样式 |
| `tests/test_npc_presence.py` | 新增 | NpcPresenceSystem 单元测试 |
| `tests/test_game_engine.py` | 修改 | 新增 presence 集成测试 |
| `tests/test_web_ui.py` | 修改 | 新增 UI 测试 |

**不修改的文件**：
- `app/systems/memory.py` — 无改动
- `app/systems/quest.py` — 无改动
- `app/systems/relationship.py` — 无改动
- `app/systems/town_tick.py` — 无改动
- `app/agents/npc_agent.py` — 无改动
- `app/database.py` — 无改动
- `app/data/npcs.json` — 无改动
- `app/data/locations.json` — 无改动
- 数据库 schema — 无改动

## 15. 结论

**建议进入实现阶段。** 理由：

1. **改动范围最小**：新增 1 个 System + 1 个 JSON + 1 个测试文件；修改 4 个现有文件。不触碰 Memory/Quest/Relationship/NPCAgent/TownTick
2. **零 DB 变更**：完全复用 WorldState.flags
3. **零数据变更**：不修改 locations.json 和 npcs.json
4. **向后兼容**：flags={} 时行为与 v0.5 完全一致，所有现有测试无需修改
5. **与 v0.5 天然衔接**：town_events.json 设置的 `miner_gone` flag 直接驱动矿工位置变化
6. **测试可覆盖**：预计新增约 16 个测试
7. **体验提升**：玩家会感受到 NPC 位置随剧情变化，小镇更加"活着"
