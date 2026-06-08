# v0.4.1 记忆安全化与展示优化 Spec

## Why

v0.4 引入的 cross_npc_memories 在注入 Prompt 时携带了其他 NPC 的回应原文和内部结构化标签，增加 NPC 知识串线风险。同时 Web UI 调试面板直接展示 `[talk|trust+3|quest:missing_case]` 等内部标签，对玩家不友好。

## What Changes

- 在 `npc_agent.py` 的 `build_prompt()` 中，对 cross_npc_memories 的 content 做安全转换，只保留玩家行为侧摘要
- 在 `app.js` 的 `refreshState()` 中，清理 memory content 的内部结构化标签，展示可读文本
- 不修改 memories 表中的原始 content，只在展示/Prompt 构造阶段做转换

## Impact

- Affected code: `app/agents/npc_agent.py`, `app/static/app.js`
- No API schema changes
- No database changes
- No dependency changes

## ADDED Requirements

### Requirement: Cross-NPC Memory Safety Transformation

When cross_npc_memories are injected into the NPC prompt, the system SHALL transform each memory's content to exclude NPC response text and internal structured tags, keeping only the player-facing summary.

#### Scenario: Cross-NPC memory in prompt
- **WHEN** cross_npc_memories contains `"[talk|trust+3|quest:missing_case] 第3轮@破晓酒馆：玩家说「我想调查失踪案」，艾琳娜回应「最近有人失踪了...」"`
- **THEN** the prompt SHALL show only `"第3轮@破晓酒馆：旅行者提到「我想调查失踪案」"`
- **AND** SHALL NOT contain `艾琳娜回应` or `trust+3` or `quest:missing_case` or `talk`

#### Scenario: Current NPC memories unchanged
- **WHEN** the current NPC's own memories contain structured tags
- **THEN** the prompt SHALL keep the full content unchanged

### Requirement: Web UI Memory Display Cleanup

The Web UI memory panel SHALL strip internal structured tags from memory content before displaying to the player.

#### Scenario: Memory with structured tags
- **WHEN** a memory has content `"[talk|trust+3|quest:missing_case] 第3轮@破晓酒馆：玩家说「...」，艾琳娜回应「...」"`
- **THEN** the display SHALL show `"第3轮@破晓酒馆：玩家说「...」，艾琳娜回应「...」"`
- **AND** SHALL NOT show `[talk|trust+3|quest:missing_case]`

## MODIFIED Requirements

### Requirement: Cross-NPC Prompt Section

The previous v0.4.0 cross-NPC prompt section title "来自其他对话的玩家上下文" and constraints remain unchanged. Only the memory content displayed within that section is now safety-transformed.

## REMOVED Requirements

None.
