# 验收清单

## Phase 1：数据模型与基础设施

- [x] 所有 Pydantic 模型可通过基本校验（字段类型、默认值、范围约束）
- [x] SQLite 数据库可正常创建，所有表存在且 schema 正确
- [x] 初始数据 JSON 文件可被正确加载并解析为 Pydantic 模型实例
- [x] FastAPI 应用 `uvicorn app.main:app` 启动无报错

## Phase 2：核心游戏系统

- [x] WorldState：可切换地点，非法地点切换被拒绝，连通性校验正确
- [x] WorldState：flag 可设置和读取，持久化到 SQLite 后可恢复
- [x] QuestManager：状态机转换在条件满足时推进，条件不满足时拒绝
- [x] QuestManager：missing_case 的 5 个阶段和 lost_ledger 的 5 个阶段转换均正确
- [x] RelationshipManager：trust/affection 修改后在 [0, 100] 范围内
- [x] RelationshipManager：单次变更不超过 ±10，超出部分被截断
- [x] RelationshipManager：status 根据 trust 值正确计算（hostile/neutral/friendly/trusted）
- [x] MemoryManager：短期记忆按 NPC 分组存储，超过 20 条时 FIFO 淘汰
- [x] MemoryManager：importance >= 7 的记忆晋升为长期记忆
- [x] MemoryManager：召回返回长期记忆 + 最近 5 条短期记忆，排序正确

## Phase 3：NPCAgent 与 LLMAdapter

- [x] MockProvider 根据 NPC ID + trust 等级 + quest 阶段返回对应模板回复
- [x] Prompt 构造输出包含：角色设定、当前状态、记忆、任务知识、行为约束、输出格式要求
- [x] 回复解析正确分离对话文本和 [INSTRUCTIONS] 块
- [x] 回复解析正确提取 QUEST / TRUST / FLAG 指令
- [x] 格式错误的指令标签被静默忽略，不抛异常

## Phase 4：GameEngine 与 API

- [x] POST /game/start 返回有效 game_id、开场叙事、当前地点、可用 NPC
- [x] POST /game/input 处理对话意图：返回 NPC 回复 + 状态变更摘要
- [x] POST /game/input 处理移动意图：切换地点，返回新地点描述
- [x] POST /game/input 处理非法输入：返回提示信息，不崩溃
- [x] GET /game/state 返回完整游戏状态（world_state + relationships + quest_states + recent_memories）
- [x] 指令分发：TRUST 指令经校验后执行，超限指令被截断
- [x] 指令分发：QUEST 指令经状态机校验后执行，非法转换被忽略
- [x] 指令分发：FLAG 指令直接设置，无特殊校验

## Phase 5：集成测试与 CLI

- [x] 端到端测试：主线任务 missing_case 从 not_started 到 resolved 完整走通
- [x] 端到端测试：支线任务 lost_ledger 从 not_started 到 resolved 完整走通
- [x] CLI 可正常启动，支持多轮交互
- [x] CLI 输出格式清晰（区分旁白、NPC 对话、系统提示）
- [x] 输入未知命令或空输入不会导致崩溃
- [x] 完整游戏流程（start → 至少 10 轮交互 → 查看状态）无报错
