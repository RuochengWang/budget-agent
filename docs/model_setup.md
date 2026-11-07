# 学校模型接入（A）

来源：组长 2026-11-07 提供的学校平台截图。协议为 OpenAI 兼容文本接口。

- Base URL：`https://api.llm.ustc.edu.cn/v1`
- 请求地址：`https://api.llm.ustc.edu.cn/v1/chat/completions`
- 初始模型：`qwen3.8-chat`
- 本地变量：`BUDGET_AGENT_API_KEY`、`BUDGET_AGENT_BASE_URL`、`BUDGET_AGENT_MODEL`

真实密钥没有写入此仓库，也没有执行实际计费调用。由 A 在本机 .env 中配置后运行：

```text
uv run budget-agent check-model
```

适配层仅使用截图确认的 model/messages 请求字段。暂不假定工具原生调用、JSON Schema 模式、
temperature、特定推理参数或 token 上限字段受支持。结构化 JSON 由提示词与本地校验约束。
HTTP 不跟随重定向，不打印认证头、响应正文或完整底层异常。
推理模型若只返回 reasoning_content 而没有有效 content，会明确失败，不把内部推理当展示观点。

用户提供的模型标识（尚未逐个验证可用性）：

```text
qwen-chat
qwen-reasoner
deepseek-v4-flash-ascend1
unlimited-ocr
qwen3.8-reasoner
qwen3.8-chat
glm-5.3-flash
deepseek-flash
smart/default
smart/reasoning
deepseek-flash-2
qwen3.8-flash-next
qwen3.8-flash-next-2
qwen-image-2.1
```

第一轮固定 qwen3.8-chat，所有角色共用一个模型适配实例。
OCR、图像和不同推理模型需分别确认接口；模型列表不表示所有类型都能接入当前文本适配层。
超时/HTTP 401 检查校园网络和本机配置；不得把 .env 发到群里或加进 Git。
更换模型或地址后先用最小请求检查，再做 1 个完整案例；全量评测前确认调用额度。
