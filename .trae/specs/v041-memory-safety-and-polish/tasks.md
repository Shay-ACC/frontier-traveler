# Tasks

- [x] Task 1: cross-NPC memory content 安全转换（npc_agent.py）
  - [x] 1.1: 在 npc_agent.py 中新增 `_sanitize_cross_memory_content(content)` 静态方法
    - 输入：`"[talk|trust+3|quest:missing_case] 第3轮@破晓酒馆：玩家说「...」，艾琳娜回应「...」"`
    - 输出：`"第3轮@破晓酒馆：旅行者提到「...」"`
    - 逻辑：(a) 用正则去掉 `[...]` 开头的标签块；(b) 用正则去掉 `，{NPC名}回应「...」` 部分；(c) 将 `玩家说` 替换为 `旅行者提到`
  - [x] 1.2: 在 `build_prompt()` 的 cross_npc_memories 循环中调用 `_sanitize_cross_memory_content()` 处理 content
  - [x] 1.3: 确保 `build_prompt()` 中当前 NPC 自己的 memories 仍使用完整 content

- [x] Task 2: Web UI memory content 展示清理（app.js）
  - [x] 2.1: 在 app.js 中新增 `stripMemoryTags(content)` 函数
    - 用正则去掉 `[...]` 开头的标签块（匹配 `^\[[^\]]*\]\s*`）
  - [x] 2.2: 在 `refreshState()` memories 渲染中，对 `m.content` 调用 `stripMemoryTags()` 后再展示
  - [x] 2.3: 确保 `stripMemoryTags()` 对不含标签的旧格式 content 也能正常工作（向后兼容）

- [x] Task 3: 新增/更新测试
  - [x] 3.1: test_npc_agent.py — 验证 cross_npc_memories 注入 Prompt 时不包含其他 NPC 回应原文
  - [x] 3.2: test_npc_agent.py — 验证 cross_npc_memories 注入 Prompt 时不包含 trust+/quest: 等内部标签
  - [x] 3.3: test_npc_agent.py — 验证当前 NPC 自己的 memories 保留完整 content（含标签和 NPC 回应）
  - [x] 3.4: test_npc_agent.py — 验证 `_sanitize_cross_memory_content()` 的输入输出
  - [x] 3.5: test_web_ui.py — 验证 app.js 包含标签清理逻辑（stripMemoryTags）
  - [x] 3.6: test_memory.py — 新增显式测试：memories 表中的记忆 content 不包含 NPC secrets/backstory

- [x] Task 4: 全量 pytest 验证
  - [x] 4.1: 运行全部测试（107 passed），确保全部通过

# Task Dependencies
- Task 1 和 Task 2 可并行
- Task 3 依赖 Task 1 和 Task 2
- Task 4 依赖全部完成
