# v0.2 OpenAI-compatible LLMAdapter 接入方案 Spec

## Why

当前 MVP 使用 MockProvider 生成 NPC 回复——基于 NPC 角色模板的 15 条预设回复，不是真正的 AI 生成。为了让 NPC 对话具备真正的多样性和上下文理解能力，需要新增一个可选的 OpenAI-compatible provider，在保留 MockProvider 作为 fallback 的前提下接入真实 LLM。

## What Changes

- 新增 `OpenAIProvider(BaseLLMProvider)`，通过 `httpx.AsyncClient` 调用 OpenAI Chat Completions API
- 新增 `ProviderFactory`，根据环境变量自动选择 provider，支持 fallback
- 修改 `GameEngine.__init__`，通过 factory 获取 provider 替代硬编码 `MockProvider()`
- 修改 `pyproject.toml`，将 `httpx` 加入 dependencies（当前仅在 dev 依赖中）
- 增强 `NPCAgent.build_prompt` 中的输出格式约束，确保 LLM 严格遵守 `[INSTRUCTIONS]` 格式

## Impact

- Affected specs: LLMAdapter、NPCAgent、GameEngine 初始化
- Affected code: `app/engine/llm_adapter.py`、`app/engine/game_engine.py`、`app/agents/npc_agent.py`、`pyproject.toml`

---

## ADDED Requirements

### Requirement: OpenAIProvider

系统 SHALL 提供 `OpenAIProvider(BaseLLMProvider)` 类，实现 `generate(system_prompt, user_message) -> str` 方法。

- 通过 `httpx.AsyncClient` 调用 OpenAI Chat Completions API（`/v1/chat/completions`）
- 兼容所有 OpenAI-compatible API（通过自定义 base_url）
- 请求参数：`model`、`temperature=0.7`、`max_tokens=500`、`messages=[{system}, {user}]`
- 超时设置：连接 10s，读取 30s
- 不引入 openai SDK，仅用 httpx 直接调用 REST API

#### Scenario: 正常调用

- **WHEN** `OpenAIProvider.generate(system_prompt, user_message)` 被调用
- **AND** API 返回 200 + 有效 JSON
- **THEN** 返回 `choices[0].message.content` 字符串

#### Scenario: API 返回错误

- **WHEN** API 返回非 200 状态码或 JSON 解析失败
- **THEN** 抛出 `LLMProviderError`

#### Scenario: 网络超时

- **WHEN** 请求超过 30s 读取超时
- **THEN** 抛出 `LLMProviderError`

### Requirement: 环境变量配置

系统 SHALL 从以下环境变量读取配置：

| 环境变量 | 必填 | 默认值 | 说明 |
|----------|------|--------|------|
| `LLM_PROVIDER` | 否 | `mock` | provider 类型：`mock` 或 `openai` |
| `LLM_API_KEY` | `openai` 时必填 | 无 | API Key |
| `LLM_BASE_URL` | 否 | `https://api.openai.com/v1` | API Base URL，支持自定义端点 |
| `LLM_MODEL` | 否 | `gpt-4o-mini` | 模型名称 |
| `LLM_TIMEOUT` | 否 | `30` | 读取超时（秒） |

- 未设置 `LLM_PROVIDER` 或值为 `mock` 时，使用 MockProvider
- `LLM_PROVIDER=openai` 但未设置 `LLM_API_KEY` 时，启动时打印警告并降级到 MockProvider

### Requirement: ProviderFactory + Fallback

系统 SHALL 提供 `create_provider() -> BaseLLMProvider` 工厂函数：

1. 读取 `LLM_PROVIDER` 环境变量
2. 若为 `openai`：尝试创建 `OpenAIProvider`，若配置不完整则打印警告并降级到 MockProvider
3. 若为 `mock` 或未设置：直接返回 MockProvider

`GameEngine.__init__` SHALL 使用 `create_provider()` 替代 `MockProvider()`。

### Requirement: FallbackProvider

系统 SHALL 提供 `FallbackProvider(BaseLLMProvider)` 包装器：

- `__init__(primary: BaseLLMProvider, fallback: BaseLLMProvider)`
- `generate()` 先尝试 primary，若抛出任何异常则静默降级到 fallback
- 降级时打印警告日志（`logging.warning`），包含异常信息
- **不重试**，一次失败立即降级

#### Scenario: Primary 成功

- **WHEN** primary provider 返回有效结果
- **THEN** 返回 primary 的结果

#### Scenario: Primary 失败

- **WHEN** primary provider 抛出异常
- **THEN** 自动调用 fallback provider
- **AND** 返回 fallback 的结果
- **AND** 通过 logging.warning 记录降级事件

### Requirement: Prompt 输出格式强化

`NPCAgent.build_prompt` 中的输出格式说明 SHALL 增加以下约束，确保 LLM 输出可解析：

1. 在 `[INSTRUCTIONS]` 块中增加示例，展示正确格式
2. 明确要求：对话内容在 `[INSTRUCTIONS]` 之前，指令在 `[INSTRUCTIONS]` 之后
3. 明确要求：`TRUST` delta 范围为 -5 到 +5
4. 明确要求：不要在对话内容中包含 `[INSTRUCTIONS]` 标记
5. 增加一条 few-shot 示例（完整的对话 + 指令输出）

### Requirement: LLMProviderError 异常

系统 SHALL 定义 `LLMProviderError(Exception)` 异常类，用于封装所有 LLM 调用失败场景：

- 网络错误（httpx 异常）
- HTTP 错误（非 200 状态码）
- JSON 解析失败
- 响应格式不符预期

---

## MODIFIED Requirements

### Requirement: GameEngine 初始化

原：`self.npc_agent = NPCAgent(MockProvider())`

改为：

```python
self.npc_agent = NPCAgent(create_provider())
```

- 不改变 `GameEngine` 的任何对外接口（`start_game`、`process_input`、`get_state` 签名不变）
- 不改变 `NPCAgent` 的构造签名（仍接受 `BaseLLMProvider`）

### Requirement: httpx 依赖

`pyproject.toml` 的 `dependencies` 中增加 `httpx`（从 dev 依赖提升为运行时依赖）。

---

## REMOVED Requirements

无删除项。MockProvider 完整保留，作为默认和 fallback provider。
