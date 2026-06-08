# v0.3 极简 Web UI Spec

## Why

当前游戏仅提供 REST API 和 CLI 两种交互方式，无法在浏览器中直观体验。需要一个最小可演示的网页界面，让用户通过浏览器游玩当前文字 RPG，同时不引入任何前端工程化工具链。

## What Changes

- 新增 `app/static/style.css` — 页面样式
- 新增 `app/static/app.js` — 前端逻辑，调用现有 API
- 新增 `app/templates/index.html` — 页面结构
- 修改 `app/main.py` — 挂载静态文件、模板引擎、`GET /` 路由
- 新增 `tests/test_web_ui.py` — Web UI 相关测试
- 更新 `README.md` — Web UI 启动说明

## Impact

- Affected specs: main.py（新增路由和中间件挂载）
- Affected code: `app/main.py`（仅新增挂载代码，不修改现有逻辑）
- 不影响任何 GameEngine、QuestManager、MemoryManager、RelationshipManager、LLMAdapter 代码

---

## ADDED Requirements

### Requirement: 页面路由

系统 SHALL 在 `GET /` 返回 `index.html` 页面。

- 使用 FastAPI 内置的 `Jinja2Templates` 渲染模板
- 不需要任何模板变量，直接渲染静态页面

### Requirement: 静态文件挂载

系统 SHALL 挂载 `app/static/` 目录为 `/static/` 路径。

- CSS 文件通过 `/static/style.css` 访问
- JS 文件通过 `/static/app.js` 访问
- 使用 `StaticFiles` 中间件

### Requirement: 页面布局

`index.html` SHALL 包含以下区域：

1. **顶部标题栏**：显示「边境小镇：记忆旅人」
2. **左侧状态面板**：
   - game_id
   - 当前地点
   - 当前回合
   - 可用 NPC 列表
   - 各 NPC 关系/信任值
   - 任务状态列表
3. **中间对话面板**：
   - 开局叙述文本
   - 玩家输入和 NPC 回复的对话记录（滚动显示）
   - 状态变更提示（quest_updates、relationship_changes、flag_changes）
4. **底部输入区域**：
   - 文本输入框
   - 发送按钮
   - Enter 键发送
   - 「开始游戏」按钮（未开始时显示）
   - 「刷新状态」按钮
5. **右侧调试面板**：
   - recent_memories 列表
   - world flags 列表
6. **错误提示区**：API 调用失败时在页面显示错误信息

### Requirement: 前端交互逻辑

`app.js` SHALL 实现以下功能：

1. **开始游戏**：调用 `POST /game/start`，显示 opening_narrative，更新状态面板
2. **发送输入**：调用 `POST /game/input`，显示玩家输入和 NPC 回复，更新状态面板
3. **刷新状态**：调用 `GET /game/state/{game_id}`，更新所有面板
4. **错误处理**：API 返回错误时在对话面板中显示红色错误提示，不在 console 中静默
5. **发送中禁用输入**：请求进行中禁用输入框和发送按钮，防止重复提交

### Requirement: 页面样式

`style.css` SHALL 使用纯 CSS（无框架）实现：

- 三栏布局（左状态 / 中对话 / 右调试）
- 深色主题（文字 RPG 氛围）
- 对话气泡区分玩家和 NPC
- 响应式：窄屏幕时单栏堆叠
- 滚动条样式美化

### Requirement: 测试

新增 `tests/test_web_ui.py`，包含：

1. `GET /` 返回 200 和 HTML 内容
2. `GET /static/style.css` 返回 200
3. `GET /static/app.js` 返回 200
4. 静态文件挂载不影响现有 API（`/game/start`、`/game/input`、`/game/state`）

---

## MODIFIED Requirements

### Requirement: main.py 启动配置

`app/main.py` 新增以下挂载代码（在现有 `app.include_router(router)` 之后）：

```python
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pathlib import Path

_static_dir = Path(__file__).resolve().parent / "static"
_templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return _templates.TemplateResponse("index.html", {"request": request})
```

- 不修改现有 `lifespan`、CORS、router 逻辑
- 需要 `from starlette.requests import Request` 导入

### Requirement: pyproject.toml dependencies

`jinja2` 加入 dependencies（FastAPI 安装时通常已包含 jinja2，但显式声明更清晰）。

### Requirement: README 更新

README 新增 Web UI 启动说明，包括截图描述和访问地址。

---

## REMOVED Requirements

无删除项。
