# Tasks

- [x] Task 1: 新增数据文件 town_events.json
  - [x] 1.1: 在 app/data/ 下创建 town_events.json，包含 5 个初始事件
  - [x] 1.2: 验证 JSON 格式正确，字段完整

- [x] Task 2: 新增 TownTickSystem（app/systems/town_tick.py）
  - [x] 2.1: 创建 TownTickSystem 类，__init__ 加载 town_events.json
  - [x] 2.2: 实现 `tick(ws: WorldStateModel, state_changes: StateChanges) -> list[TownEvent]` 方法
  - [x] 2.3: 实现 `get_triggered_events(ws: WorldStateModel) -> list[TownEvent]` 方法

- [x] Task 3: 扩展 API 模型（app/models/api_schemas.py）
  - [x] 3.1: 新增 `TownEvent` 模型（event_id, title, narration, importance）
  - [x] 3.2: `StateChanges` 新增 `town_events: list[TownEvent] = []` 字段
  - [x] 3.3: `GameStateResponse` 新增 `triggered_town_events: list[TownEvent] = []` 字段

- [x] Task 4: 集成到 GameEngine（app/engine/game_engine.py）
  - [x] 4.1: `__init__` 中初始化 `self.town_tick_system = TownTickSystem()`
  - [x] 4.2: `_apply_talk_result()` 中在 `_try_advance_quests()` 之后调用 `tick()`，结果加入 state_changes
  - [x] 4.3: `_handle_move()` 中在 `_try_advance_quests()` 之后调用 `tick()`，结果加入 state_changes
  - [x] 4.4: `get_state()` 中调用 `get_triggered_events()` 返回已触发事件

- [x] Task 5: Web UI 展示（app/static/app.js + app/templates/index.html + app/static/style.css）
  - [x] 5.1: sendMessage() 中检查并渲染 `state_changes.town_events` 为系统消息气泡
  - [x] 5.2: index.html 新增 `town-events` 区域
  - [x] 5.3: refreshState() 中渲染 `triggered_town_events` 列表
  - [x] 5.4: style.css 新增 `.town-event-item` / `.town-event-important` 样式

- [x] Task 6: 新增测试
  - [x] 6.1: 新建 `tests/test_town_tick.py`：TownTickSystem 单元测试（11 个测试）
  - [x] 6.2: `tests/test_game_engine.py` 新增 town event 集成测试（4 个测试）
  - [x] 6.3: `tests/test_web_ui.py` 新增 town_events 相关测试（2 个测试）

- [x] Task 7: 全量 pytest 验证
  - [x] 7.1: 运行全部测试（107 原有 + 17 新增 = 124），确保全部通过

# Task Dependencies
- Task 1 和 Task 3 无依赖，可最先开始
- Task 2 依赖 Task 1（加载 town_events.json）
- Task 4 依赖 Task 2 和 Task 3
- Task 5 依赖 Task 3（API 模型定义）
- Task 6 依赖 Task 2、Task 3、Task 4
- Task 7 依赖全部完成
