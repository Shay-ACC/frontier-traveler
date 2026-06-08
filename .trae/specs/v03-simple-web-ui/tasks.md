# Tasks

- [x] Task 1: 创建前端文件
  - [x] 1.1: 创建 `app/templates/index.html` — 三栏布局页面结构
  - [x] 1.2: 创建 `app/static/style.css` — 深色主题、三栏布局、对话气泡、响应式
  - [x] 1.3: 创建 `app/static/app.js` — 开始游戏、发送输入、刷新状态、错误处理

- [x] Task 2: 修改 main.py 挂载静态文件和页面路由
  - [x] 2.1: 挂载 StaticFiles 中间件
  - [x] 2.2: 添加 GET / 路由返回 index.html（使用 HTMLResponse 直接读取，无需 Jinja2）
  - [x] 2.3: pyproject.toml 中无需新增 jinja2 依赖（不使用模板引擎）

- [x] Task 3: 新增测试
  - [x] 3.1: 创建 `tests/test_web_ui.py`
  - [x] 3.2: 测试 GET / 返回 200
  - [x] 3.3: 测试静态资源可访问
  - [x] 3.4: 测试现有 API 不受影响

- [x] Task 4: 更新 README
  - [x] 4.1: 新增 Web UI 启动说明
  - [x] 4.2: 更新「当前限制」和 Roadmap

- [x] Task 5: 运行 pytest 全量验证
  - [x] 5.1: 确保全部测试通过（原有 75 + 新增 6 = 81）

# Task Dependencies
- Task 1 和 Task 2 可并行
- Task 3 依赖 Task 1 + Task 2 完成
- Task 4 依赖 Task 1-3 完成
- Task 5 依赖全部完成
