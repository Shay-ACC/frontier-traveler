# Tasks

- [x] Task 1: 增强 importance scoring
  - [x] 1.1: 在 game_engine.py 中定义 QUEST_KEYWORDS / PROMISE_KEYWORDS 常量
  - [x] 1.2: 重写 `_calculate_importance()` 为累加式评分（base=1 + 信号贡献），clamp [1,10]
  - [x] 1.3: 新增测试：验证任务关键词、承诺关键词、trust 变化、普通对话的 importance 值
  - [x] 1.4: 运行现有 83 个测试确保不回归

- [x] Task 2: 结构化 memory content 格式
  - [x] 2.1: 修改 `_apply_talk_result()` 中 memory_content 拼接逻辑，加入 `[类别|标签]` 和 `@地点`
  - [x] 2.2: 新增测试：验证 memory_content 包含标签和地点
  - [x] 2.3: 确保现有记忆读取逻辑兼容新格式（content 仍为 TEXT，向后兼容）

- [x] Task 3: recall 总量上限 + 跨 NPC 记忆注入
  - [x] 3.1: 在 memory.py 中定义 RECALL_BUDGET=12
  - [x] 3.2: 新增 `recall_with_context(game_id, npc_id, db)` 方法：当前 NPC 8 条 + 跨 NPC 3 条 + 任务相关 1 条
  - [x] 3.3: 跨 NPC 记忆只注入玩家行为侧，不注入 NPC secret/backstory
  - [x] 3.4: 修改 `_build_talk_context()` 调用 `recall_with_context()` 替代 `recall()`
  - [x] 3.5: 新增测试：验证 recall_with_context 总量上限、跨 NPC 记忆数量限制、跨 NPC 不含 secret

- [x] Task 4: NPCAgent Prompt 增强记忆格式
  - [x] 4.1: 修改 `build_prompt()` 记忆格式：加 `[重要]/[普通]` 标注、保留地点和分类标签
  - [x] 4.2: 新增"来自其他对话的记忆"段落（跨 NPC 记忆）
  - [x] 4.3: 新增测试：验证 prompt 记忆格式、跨 NPC 段落、总量上限

- [x] Task 5: 主动晋升机制
  - [x] 5.1: 在 `_apply_talk_result()` 中写入记忆后，立即检查 importance >= 7 的短期记忆并主动晋升
  - [x] 5.2: 新增测试：验证高 importance 记忆在对话后立即晋升，不依赖 FIFO 淘汰
  - [x] 5.3: 确保现有 test_promotion_on_eviction 不受影响

- [x] Task 6: /game/state 展示增强
  - [x] 6.1: 修改 `get_state()` 记忆获取：每个 NPC 取 short_term + long_term 混合（get_recent 已改为按类型/重要性排序）
  - [x] 6.2: 新增测试：验证 get_state 返回的记忆包含 long_term

- [x] Task 7: Web UI 记忆面板增强
  - [x] 7.1: 修改 app.js refreshState() 中 memories 渲染逻辑：解析 Memory 对象，显示类型/importance/内容
  - [x] 7.2: 新增 style.css 记忆类型样式（.memory-type-long / .memory-type-short / .memory-important）
  - [x] 7.3: 新增测试：验证 app.js 和 style.css 包含记忆面板增强

- [x] Task 8: 全量 pytest 验证
  - [x] 8.1: 运行全部测试（100 passed），确保全部通过

# Task Dependencies
- Task 1 和 Task 2 可并行（无依赖关系）
- Task 3 依赖 Task 1（recall 需要 importance 值做优先级排序）
- Task 4 依赖 Task 2 和 Task 3（prompt 需要新格式和跨 NPC 记忆）
- Task 5 独立（可与 Task 3/4 并行）
- Task 6 依赖 Task 5（get_state 展示需要主动晋升生效）
- Task 7 依赖 Task 6（前端需要 API 返回 long_term）
- Task 8 依赖全部完成
