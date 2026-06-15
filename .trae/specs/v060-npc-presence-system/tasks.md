# Tasks

- [x] Task 1: 新增数据文件 npc_presence_rules.json
  - [x] 1.1: 在 app/data/ 下创建 npc_presence_rules.json，包含矿工托马斯的 2 条位置规则
  - [x] 1.2: 验证 JSON 格式正确，字段完整

- [x] Task 2: 新增 NpcPresenceSystem（app/systems/npc_presence.py）
  - [x] 2.1: 创建 NpcPresenceSystem 类，__init__ 加载 npc_presence_rules.json 和 npcs.json
  - [x] 2.2: 实现 `get_npcs_at_location(ws, location_id) -> list[str]` 方法
    - 遍历所有 NPC，对每个 NPC 检查 presence rules
    - 第一条匹配的规则决定位置和可见性
    - 无匹配规则时回退到 npcs.json 的 default_location，visible=True
    - 返回当前在指定地点且可见的 NPC id 列表
  - [x] 2.3: 实现 `get_all_npc_locations(ws) -> list[NpcLocationInfo]` 方法
    - 返回所有 NPC 的当前位置和可见性
  - [x] 2.4: 实现 `get_absence_reason(ws, npc_id, location_id) -> str | None` 方法
    - 返回 NPC 不在指定地点的原因文本（来自 rule.reason）

- [x] Task 3: 扩展 API 模型（app/models/api_schemas.py）
  - [x] 3.1: 新增 `NpcLocationInfo` 模型（npc_id, name, location, visible）
  - [x] 3.2: `GameStateResponse` 新增 `npc_locations: list[NpcLocationInfo] = []` 字段

- [x] Task 4: 集成到 GameEngine（app/engine/game_engine.py）
  - [x] 4.1: `__init__` 中初始化 `self.npc_presence_system = NpcPresenceSystem()`
  - [x] 4.2: `start_game()` 中替换 `get_available_npcs()` 为 `get_npcs_at_location()`
  - [x] 4.3: `_build_talk_context()` 中替换 2 处 `get_available_npcs()` 调用
  - [x] 4.4: `_build_talk_context()` 中 NPC 不在场时使用 `get_absence_reason()` 生成提示
  - [x] 4.5: `_get_available_actions()` 中替换 `get_available_npcs()` 调用
  - [x] 4.6: `get_state()` 中调用 `get_all_npc_locations()` 返回 npc_locations

- [x] Task 5: Web UI 展示（app/static/app.js + app/templates/index.html + app/static/style.css）
  - [x] 5.1: app.js 新增 `LOC_NAME_MAP` 映射
  - [x] 5.2: index.html 新增 `npc-locations` 区域
  - [x] 5.3: refreshState() 中渲染 `npc_locations` 列表
  - [x] 5.4: style.css 新增 `.npc-location-item` / `.npc-location-hidden` 样式

- [x] Task 6: 新增测试
  - [x] 6.1: 新建 `tests/test_npc_presence.py`：NpcPresenceSystem 单元测试（12 个测试）
  - [x] 6.2: `tests/test_game_engine.py` 新增 presence 集成测试（3 个测试）
  - [x] 6.3: `tests/test_web_ui.py` 新增 UI 测试（2 个测试）

- [x] Task 7: 全量 pytest 验证
  - [x] 7.1: 运行全部测试（124 原有 + 17 新增 = 141），全部通过

# Task Dependencies
- Task 1 和 Task 3 无依赖，可最先开始
- Task 2 依赖 Task 1（加载 npc_presence_rules.json）和 npcs.json（读取 default_location）
- Task 4 依赖 Task 2 和 Task 3
- Task 5 依赖 Task 3（API 模型定义）
- Task 6 依赖 Task 2、Task 3、Task 4
- Task 7 依赖全部完成
