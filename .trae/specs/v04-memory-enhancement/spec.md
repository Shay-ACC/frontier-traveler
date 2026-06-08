# v0.4.0 记忆系统增强 Spec

## 1. 当前 MemoryManager 实现分析

### 1.1 short_term 写入

`MemoryManager.add_short_term()` ([memory.py:12-31](file:///Users/chenhui/PycharmProjects/frontier_traveler/app/systems/memory.py#L12-L31))：
- 创建 `Memory(type="short_term")`，INSERT 到 memories 表
- 调用 `cleanup_expired()` 触发 FIFO 淘汰
- 由 `GameEngine._apply_talk_result()` 在写阶段调用（[game_engine.py:310-313](file:///Users/chenhui/PycharmProjects/frontier_traveler/app/engine/game_engine.py#L310-L313)）
- memory_content 格式：`"第{turn}轮：玩家说「{msg[:50]}」，{npc_name}回应「{dialogue[:50]}」"`

### 1.2 long_term 晋升

`MemoryManager.cleanup_expired()` → `promote_to_long_term()` ([memory.py:130-143](file:///Users/chenhui/PycharmProjects/frontier_traveler/app/systems/memory.py#L130-L143))：
- 仅在 FIFO 淘汰时触发：短期记忆超过 `SHORT_TERM_LIMIT=20` 时，最旧的被评估
- `importance >= PROMOTION_THRESHOLD(7)` → 晋升为 long_term
- `importance < 7` → 永久删除
- **问题**：重要记忆必须等到缓冲区满才被评估。如果游戏在 20 轮内结束，所有短期记忆都不会被评估晋升

### 1.3 recall 工作方式

`MemoryManager.recall()` ([memory.py:41-76](file:///Users/chenhui/PycharmProjects/frontier_traveler/app/systems/memory.py#L41-L76))：
- 查询所有 long_term + 最近 5 条 short_term（`RECALL_RECENT_COUNT=5`）
- **仅限当前 npc_id**：WHERE npc_id = ?
- 副作用：所有被 recall 的记忆 accessed_count += 1，并立即 commit
- 排序：`(-importance, accessed_count)` → 高重要度优先，同重要度下低访问量优先
- **无总量上限**：如果有 50 条 long_term，全部返回

### 1.4 importance 计算

`GameEngine._calculate_importance()` ([game_engine.py:395-403](file:///Users/chenhui/PycharmProjects/frontier_traveler/app/engine/game_engine.py#L395-L403))：
- 仅基于 LLM 返回的 instruction 类型：
  - 有 QUEST 指令 → 8
  - 有 TRUST 指令 → 6
  - 其他 → 3
- **不分析**：玩家消息内容、信任变化幅度、任务状态转换、地点重要性

### 1.5 /game/state 展示 recent_memories

`GameEngine.get_state()` ([game_engine.py:423-443](file:///Users/chenhui/PycharmProjects/frontier_traveler/app/engine/game_engine.py#L423-L443))：
- 对 3 个 NPC 各调 `get_recent(limit=3)`
- `get_recent()` **只返回 short_term**，不包含 long_term
- Web UI 调试面板通过 `data.recent_memories` 展示，`JSON.stringify(m)` 输出全部字段

## 2. 当前记忆系统的主要问题

| # | 问题 | 影响 |
|---|------|------|
| M1 | **recall 仅限当前 NPC**：与老板娘对话时看不到与其他 NPC 的交互记忆 | NPC 行为不连贯，玩家对镇长说的话老板娘完全不知道 |
| M2 | **recall 无总量上限**：长期记忆无限累积，prompt 可能膨胀到数千 token | LLM 上下文溢出、响应变慢、成本增加 |
| M3 | **importance 粒度过粗**：只有 3/6/8 三档，仅看 instruction 类型 | 普通闲聊和关键剧情线索区分不够，晋升/淘汰决策粗糙 |
| M4 | **memory_content 格式扁平**：仅存对话摘要字符串，无结构化标签 | 无法按任务/主题/关键词过滤记忆 |
| M5 | **get_state 不展示 long_term**：Web UI 只能看到短期记忆 | 调试面板看不到哪些记忆被永久保留 |
| M6 | **晋升时机被动**：只在 FIFO 淘汰时评估，20 轮内无晋升 | 短游戏流程中，重要记忆永远不会晋升 |
| M7 | **recall 副作用**：每次 recall 都 commit accessed_count | 在三阶段读阶段产生写操作，增加 DB 负担 |
| M8 | **Prompt 记忆格式简陋**：flat list 无结构，无优先级标注 | LLM 难以区分重要和次要记忆 |

## 3. v0.4 最小增强范围

### 进入 v0.4 的功能

| 功能 | 解决问题 | 复杂度 |
|------|----------|--------|
| F1: 增强 importance scoring | M3 | 低 |
| F2: 结构化 memory content（内嵌标签） | M4 | 低 |
| F3: recall 总量上限 + 优先级策略 | M2, M8 | 低 |
| F4: 跨 NPC 关键记忆注入 | M1 | 中 |
| F5: /game/state 展示 long_term + 类型/importance | M5 | 低 |
| F6: Web UI 记忆面板增强 | M5 | 低 |
| F7: 主动晋升（每轮对话后评估） | M6 | 低 |

### 不进入 v0.4 的功能

- 向量检索 / embedding / 语义搜索
- 多 Agent 自主行动
- NPC 日程系统
- 战斗 / 背包系统
- 复杂存档系统
- memory summary（见第 6 节分析）
- 记忆遗忘机制（长期记忆衰减）

## 4. 推荐数据结构改动

### 方案：不修改 schema

**理由**：
- 现有 `content` 字段是 TEXT，足够存储结构化信息
- 现有 `importance` 字段是 INTEGER，扩展范围即可
- 不需要新增列，不需要迁移
- "如无必要勿增实体"

**具体做法**：

```
# 当前格式
"第3轮：玩家说「和老板娘聊聊」，艾琳娜回应「你看起来不像坏人...」"

# v0.4 格式（结构化标签内嵌在 content 中）
"[talk|trust+3|quest:missing_case] 第3轮@酒馆：玩家询问失踪案，艾琳娜提到最近有人失踪"
```

标签约定：
- 第一个 `[...]` 块为元数据标签，`|` 分隔
- 标签格式：`类别:值`，类别包括 `talk`/`move`/`quest:{id}`/`trust{+/-}N`/`promise`/`secret`
- `@地点` 标注发生地点
- 后面为自然语言描述

**优势**：
- 零迁移成本
- 前端 `JSON.stringify` 仍可正常展示
- recall 时可通过字符串匹配过滤（`"[quest:" in content`）
- 未来如果需要 schema 改动，可从 content 中解析

## 5. importance scoring 规则设计

### 当前规则（3 档）

```
QUEST 指令 → 8
TRUST 指令 → 6
其他 → 3
```

### v0.4 规则（1-10 档）

在 `_calculate_importance()` 中综合评估，**不依赖 LLM instruction**（因为 MockProvider 不生成复杂指令）：

| 信号 | importance 贡献 | 说明 |
|------|-----------------|------|
| 任务线索关键词（失踪/账本/矿坑/秘密/协议/毒气） | +3 | 玩家消息中匹配 quests.json 中的关键词 |
| 任务状态转换（quest_updates 非空） | +3 | 系统检测到任务推进 |
| TRUST 变化（relationship_changes 非空） | +1 | 信任度有变化 |
| TRUST 大幅变化（\|delta\| >= 4） | +2 | 显著的信任变化 |
| 玩家承诺/威胁关键词（答应/保证/威胁/报警） | +2 | 对未来行为有约束力 |
| NPC secret 相关（flag 变化涉及 secret 解锁） | +2 | 关键剧情节点 |
| 普通对话（无以上信号） | 1 | 基础值 |

**计算逻辑**：`base=1`，累加匹配的信号贡献，clamp 到 `[1, 10]`。

**PROMOTION_THRESHOLD 保持 7 不变**。只有真正重要的记忆（任务线索+任务推进、或多个信号叠加）才能晋升。

### 关键词匹配实现

从 quests.json 和 npcs.json 中提取关键词集合，硬编码为常量：

```python
QUEST_KEYWORDS = {"失踪", "账本", "矿坑", "秘密", "协议", "毒气", "灭口", "真相"}
PROMISE_KEYWORDS = {"答应", "保证", "承诺", "发誓", "威胁", "报警", "举报"}
```

不使用 LLM 分析，纯关键词匹配。简单可靠，适合 MVP。

## 6. memory summary 设计

### 建议：本轮不实现

**理由**：
- Summary 需要额外的 LLM 调用或复杂的规则引擎
- 当前记忆量（20 条短期/每个 NPC）不大，不需要压缩
- "如无必要勿增实体"
- 引入 summary 会带来一致性问题（summary 与原始记忆不同步）

### 如果未来需要

**推荐方案**：运行时生成，不存储
- 在 recall 时，如果记忆超过上限，对低 importance 记忆做简单合并
- 合并规则：同一 NPC、连续 turn、低 importance（≤3）的记忆合并为一条
- 不引入 LLM，用模板拼接：`"第{t1}-{t2}轮：与{npc}进行了{count}次普通对话"`

## 7. recall 策略设计

### 当前策略

```
全部 long_term(npc_id) + 5 条 short_term(npc_id)
→ 按 (-importance, accessed_count) 排序
```

### v0.4 策略

**总量上限**：`RECALL_BUDGET = 12`

**分配策略**：
1. 当前 NPC 记忆（最多 8 条）
   - 所有 long_term(npc_id)，按 importance 降序取 top
   - 补充 recent short_term(npc_id) 至 8 条
2. 跨 NPC 关键记忆（最多 3 条）
   - 从其他 NPC 的 long_term 中取 importance 最高的
   - 在 prompt 中标注 `[来自其他对话]`
3. 任务相关记忆（最多 1 条）
   - 如果当前有活跃任务，取 importance 最高的任务相关记忆
   - 通过 content 中的 `[quest:{id}]` 标签匹配

**排序**：保持 `(-importance, accessed_count)` 不变。

### recall 副作用处理

将 accessed_count 更新改为非自动 commit：
- 在 `_build_talk_context()` 阶段调用 recall 时，`auto_commit=False`
- accessed_count 更新随主事务一起 commit
- 这消除读阶段的独立写操作

## 8. NPCAgent Prompt 如何加入记忆上下文

### 当前 prompt 格式

```
你记得的事情：
- (第3轮) 第3轮：玩家说「和老板娘聊聊」，艾琳娜回应「你看起来不像坏人...」
- (第1轮) ...
```

### v0.4 prompt 格式

```
你记得的事情（按重要程度排列）：
[重要] (第3轮@酒馆) [quest:missing_case] 玩家询问失踪案，你提到最近有人失踪
[重要] (第5轮@镇政厅) [trust+3] 镇长对失踪话题表现紧张
[普通] (第4轮@酒馆) [talk] 玩家和老板娘闲聊天气
---
来自其他对话的记忆：
[重要] (第6轮@矿坑) [quest:missing_case] 矿工托马斯提到矿坑里有危险物质
```

**变更点**：
- 每条记忆前加 `[重要]` / `[普通]` 标注（importance >= 7 为重要）
- 保留 `@地点` 和分类标签
- 新增"来自其他对话的记忆"段落
- 控制总条目数 ≤ 12

## 9. /game/state 是否需要扩展 memory_debug 字段

### 建议：不新增字段，增强现有 recent_memories

**理由**：
- `GameStateResponse.recent_memories` 已包含 `Memory` 模型的全部字段（id/type/content/importance/turn/accessed_count）
- 问题在于 `get_state()` 只调 `get_recent()`（仅 short_term，limit=3/NPC）

### 改动方案

修改 `GameEngine.get_state()` 中的记忆获取逻辑：
1. 每个 NPC 取 `limit=3` 条 short_term + `limit=2` 条 long_term
2. 按重要性排序后返回
3. Memory 模型中 `type` 字段已存在，前端可区分

不需要新增 `memory_debug` 字段。Memory 模型的 `type` 和 `importance` 字段已经提供了调试所需信息。

## 10. Web UI 如何展示

### 当前展示

```javascript
item.textContent = typeof m === "string" ? m : JSON.stringify(m);
```

直接 JSON.stringify，信息密集且不可读。

### v0.4 展示方案

在 `refreshState()` 中解析 Memory 对象，格式化展示：

```
记忆面板：
┌─────────────────────────┐
│ [长期★8] 第3轮@酒馆      │
│ 玩家询问失踪案...         │
├─────────────────────────┤
│ [短期·3] 第7轮@酒馆       │
│ 和老板娘闲聊...           │
└─────────────────────────┘
```

**实现**：
- 记忆类型标签：`[长期]` / `[短期]`
- importance 星级：importance >= 7 显示 ★
- NPC 名称映射：使用 NPC_NAME_MAP
- 内容截断：超过 60 字符截断
- 按重要性分组：长期记忆在前，短期在后

**改动范围**：仅 `app.js` 的 `refreshState()` 中 memories 部分 + `style.css` 新增 `.memory-type-long` / `.memory-type-short` 样式。

## 11. 测试计划

### 11.1 MemoryManager 单元测试（test_memory.py 新增）

| 测试 | 验证点 |
|------|--------|
| test_recall_respects_budget | recall 返回总量不超过 RECALL_BUDGET |
| test_recall_includes_cross_npc | recall 包含其他 NPC 的高 importance 记忆 |
| test_cross_npc_limited | 跨 NPC 记忆不超过 3 条 |
| test_get_recent_includes_long_term | get_recent 返回 long_term 和 short_term |

### 11.2 GameEngine 对话后记忆写入测试（test_game_engine.py 新增）

| 测试 | 验证点 |
|------|--------|
| test_importance_quest_keyword | 玩家消息含任务关键词时 importance >= 4 |
| test_importance_promise_keyword | 玩家消息含承诺关键词时 importance >= 3 |
| test_importance_trust_change | 有 trust 变化时 importance 提升 |
| test_importance_plain_chat | 普通对话 importance 为 1 |
| test_memory_content_has_tags | memory_content 包含结构化标签 |
| test_memory_content_has_location | memory_content 包含 @地点 |
| test_active_promotion | 高 importance 记忆在对话后主动晋升 |

### 11.3 NPC Prompt 包含记忆测试（test_npc_agent.py 新增）

| 测试 | 验证点 |
|------|--------|
| test_build_prompt_memory_format | prompt 中记忆格式包含 [重要]/[普通] 标注 |
| test_build_prompt_cross_npc_memory | prompt 包含跨 NPC 记忆段落 |
| test_build_prompt_memory_budget | prompt 中记忆条目不超过上限 |

### 11.4 Web UI memory 展示测试（test_web_ui.py 新增）

| 测试 | 验证点 |
|------|--------|
| test_js_memory_display_format | app.js 包含长期/短期标签渲染逻辑 |

### 11.5 现有测试

- 全部 83 个现有测试必须继续通过
- 特别注意 test_recall_sorting、test_promotion_on_eviction、test_fifo_eviction

## 12. 不进入 v0.4 的功能

| 功能 | 原因 |
|------|------|
| 向量检索 / embedding | 引入外部依赖，违反"如无必要勿增实体" |
| 多 Agent 自主行动 | 架构改动过大，超出记忆增强范围 |
| NPC 日程系统 | 新增系统，超出记忆增强范围 |
| 战斗 / 背包 | 新增玩法系统，超出范围 |
| 复杂存档系统 | 新增基础设施，超出范围 |
| memory summary | 需要额外 LLM 调用或复杂规则，收益不明显 |
| 记忆衰减 | 增加系统复杂度，当前记忆量不需要衰减 |
| NPC 情感模型 | 超出记忆增强范围 |

## 风险评估

### P0（实现前必须注意）

| # | 风险 | 缓解措施 |
|---|------|----------|
| P0-1 | recall 策略变更可能破坏现有 test_recall_* 测试 | 先更新测试再改实现，保持排序语义不变 |
| P0-2 | 跨 NPC 记忆注入可能泄露剧情秘密（NPC A 知道 NPC B 的秘密） | 跨 NPC 记忆只注入玩家行为侧（"玩家与 XX 谈论了 YY"），不注入 NPC 的 secret/backstory |
| P0-3 | importance scoring 变更导致大量记忆意外晋升或意外淘汰 | 保持 PROMOTION_THRESHOLD=7 不变，新评分规则下同等条件不会比当前更激进 |

### P1（影响体验但不阻塞）

| # | 风险 | 缓解措施 |
|---|------|----------|
| P1-1 | 关键词匹配可能误判（"矿坑"出现在闲聊中） | importance 只是评分维度之一，单次误判不会导致严重问题 |
| P1-2 | 跨 NPC 记忆格式可能让 LLM 困惑 | 使用明确的分隔标记，在 prompt 中说明来源 |
| P1-3 | Web UI 记忆面板改动可能影响现有调试体验 | 保持 JSON 展示为 fallback，新增格式化为增强 |

### P2（后续优化）

| # | 建议 |
|---|------|
| P2-1 | 未来考虑 `category` 列替代 content 内嵌标签，提升查询效率 |
| P2-2 | 未来引入记忆衰减：长期记忆的 importance 随时间递减 |
| P2-3 | 未来考虑 embedding-based recall 替代关键词匹配 |

## 结论

**建议进入实现阶段。** 理由：

1. **改动范围可控**：不修改 DB schema，不引入外部依赖，核心改动集中在 `_calculate_importance()`、`recall()`、`_apply_talk_result()`、`build_prompt()` 和 Web UI 前端
2. **收益明确**：解决 8 个已识别问题中的 7 个（M1-M6, M8），仅 M7（recall 副作用）降级处理
3. **风险可控**：3 个 P0 风险都有明确缓解措施，不影响核心三阶段架构
4. **测试可覆盖**：预计新增约 15 个测试，全部可通过关键词匹配和结构断言验证

## What Changes

- 增强 `GameEngine._calculate_importance()`：基于消息内容关键词 + 指令类型综合评分
- 增强 `MemoryManager.recall()`：总量上限 + 跨 NPC 关键记忆注入
- 修改 `GameEngine._apply_talk_result()`：结构化 memory_content 格式
- 新增 `MemoryManager.recall_with_context()`：跨 NPC recall 策略
- 修改 `GameEngine.get_state()`：展示 long_term 记忆
- 修改 `NPCAgent.build_prompt()`：增强记忆格式 + 跨 NPC 段落
- 修改 `app.js` refreshState()：格式化记忆展示
- 修改 `style.css`：新增记忆类型样式
- 新增约 15 个测试

## Impact

- Affected code: `app/systems/memory.py`, `app/engine/game_engine.py`, `app/agents/npc_agent.py`, `app/static/app.js`, `app/static/style.css`, `tests/`
- No breaking changes to API schema
- No new database tables or columns
- No new dependencies
