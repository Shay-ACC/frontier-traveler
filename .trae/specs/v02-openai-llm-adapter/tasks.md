# Tasks

- [x] Task 1: 新增 LLMProviderError 异常 + OpenAIProvider 实现
  - [x] 1.1: 在 llm_adapter.py 中定义 `LLMProviderError(Exception)`
  - [x] 1.2: 实现 `OpenAIProvider(BaseLLMProvider)`，使用 httpx.AsyncClient 调用 `/v1/chat/completions`
  - [x] 1.3: 从环境变量读取 api_key / base_url / model / timeout
  - [x] 1.4: 错误处理：httpx 异常、非 200 状态码、JSON 解析失败均包装为 LLMProviderError

- [x] Task 2: 新增 FallbackProvider + create_provider 工厂函数
  - [x] 2.1: 实现 `FallbackProvider(BaseLLMProvider)`，primary 失败时静默降级到 fallback
  - [x] 2.2: 降级时通过 logging.warning 记录异常信息
  - [x] 2.3: 实现 `create_provider() -> BaseLLMProvider` 工厂函数，根据 LLM_PROVIDER 环境变量选择
  - [x] 2.4: LLM_PROVIDER=openai 但缺少 API_KEY 时，打印警告并降级到 MockProvider

- [x] Task 3: 修改 GameEngine 初始化 + pyproject.toml
  - [x] 3.1: GameEngine.__init__ 中 `MockProvider()` 替换为 `create_provider()`
  - [x] 3.2: pyproject.toml 的 dependencies 中增加 `httpx`

- [x] Task 4: 强化 NPCAgent prompt 输出格式
  - [x] 4.1: 在 build_prompt 的输出格式说明中增加 few-shot 示例
  - [x] 4.2: 明确约束 TRUST delta 范围 -5 到 +5
  - [x] 4.3: 明确约束对话内容与 [INSTRUCTIONS] 的分隔规则

- [x] Task 5: 新增测试
  - [x] 5.1: test_llm_adapter.py — OpenAIProvider 正常调用（mock httpx）
  - [x] 5.2: test_llm_adapter.py — OpenAIProvider 网络错误 → LLMProviderError
  - [x] 5.3: test_llm_adapter.py — OpenAIProvider HTTP 错误 → LLMProviderError
  - [x] 5.4: test_llm_adapter.py — FallbackProvider primary 成功 → 返回 primary 结果
  - [x] 5.5: test_llm_adapter.py — FallbackProvider primary 失败 → 返回 fallback 结果
  - [x] 5.6: test_llm_adapter.py — create_provider 环境变量 mock → mock provider
  - [x] 5.7: test_llm_adapter.py — create_provider 环境变量 openai + 无 API_KEY → 降级 mock
  - [x] 5.8: test_llm_adapter.py — create_provider 环境变量 openai + 有 API_KEY → FallbackProvider(OpenAIProvider, MockProvider)
  - [x] 5.9: test_game_engine.py — GameEngine 默认使用 mock provider（无环境变量时行为不变）

- [x] Task 6: 运行 pytest 全量验证
  - [x] 6.1: 确保全部测试通过（原有 56 + 新增测试）

# Task Dependencies
- Task 1 是 Task 2 的前置依赖（FallbackProvider 需要引用 OpenAIProvider）
- Task 2 是 Task 3 的前置依赖（GameEngine 需要 create_provider）
- Task 1 + Task 4 可并行
- Task 5 依赖 Task 1-3 全部完成
- Task 6 依赖 Task 5 完成
