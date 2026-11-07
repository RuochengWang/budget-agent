# A · 组长：总控、模型与集成

先读 README、architecture.md、contracts.md、roadmap.md。你是公共接口协调人。

刚接触此项目时，先从 [组长导览](../leader_guide.md) 看运行过程、数据交接与逐文件说明。

## 文件与已提供基础

主责：`schemas.py`、`config.py`、`model_client.py`、`workflow.py`、`storage.py`、
`main.py`、`agents/base.py`、`tools/registry.py`、依赖与 CI。
这些基础已提供。正式模式当前在 B 的预算入口中止，这是明确的开发状态。

不要把“能启动 demo”当成完整系统完成。model_client 已按学校截图实现文本适配，
尚未真实连通；需要你在本机填 .env 后验证，不把密钥提交到仓库。

## 第一项任务

1. 让全员按 README 启动同一个演示案例并运行 pytest。
2. 组织共同确认 schemas.py，特别是预算的两次调用与优惠输入。
3. 运行 `uv run budget-agent check-model`，确认校园网络、文本输出、用量和调用额度。
4. 在 Issue 中分配 docs/tasks.md 的任务，记录每人的首次可验收日期。

## 集成方式

依赖关系：B 提供预算；C 提供数据/求解工具；D 提供角色；E 调用 run_case。
各模块完成后，正式工厂已指向这些函数，不需要 E 修改界面。
单模块调试可以使用 `Services` 注入替身，但必须标记为开发实验，不能报告为正式系统效果。
每次运行创建新 Services；不要缓存跨运行的工具额度、上下文或模型轨迹。

公共协议变更按“提出字段/语义→列出调用方→全员确认→修改协议、示例、文档和测试”处理。
新增模型原生 tool calling 前确认学校服务支持，保留本地参数校验和白名单。

## 验收

- 两个正式案例可结束：超预算球鞋、合理日用品凑单。
- 缺字段、模型格式错误、连接失败、超时、工具上限都返回明确状态。
- 不存在无限调用，不自动切换模型，不把 partial 伪装为完成。
- RunRecord 有原始建议、最终建议、否决原因、提示词版本与轨迹，无密钥。
- 新环境能按锁文件安装，CI 通过；Windows/macOS 还需各找组员实机启动一次。

检查命令：`uv run pytest tests/test_workflow.py tests/test_model_client.py tests/test_registry.py`。
全量：`uv run pytest`、`uv run ruff check .`。

报告提交：架构、模型接入、异常控制与集成局限。展示时说明哪些是角色节点、
哪些具备工具选择能力，避免将固定提示词等同于自主 agent。
