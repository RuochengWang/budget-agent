# A · 总控、模型与集成

你负责总控、模型接入、公共接口协调与集成。先在本机取得最新仓库，再依次阅读
[总体结构](../common/overview/README.md)、[系统流程图](../common/overview/flowcharts.md)、
[接口约定](../common/contracts.md)，然后按本文开始开发。

具体文件与交接过程可查 [全员文件地图](../common/overview/file_map.md)。
学校模型配置见本目录 [model_setup.md](model_setup.md)，共同排期见 [roadmap.md](../common/roadmap.md)。

## 文件与已提供基础

### 需要完成的文件

以下路径相对于项目根目录。A 的文件已有基础实现，主要工作是验证、集成和必要修补；
验收发现问题时修改对应文件，保留已可用的基础。正式模式当前在 B 的预算入口中止。

| 文件 | 当前状态 | A 要完成什么 |
|---|---|---|
| [src/budget_agent/model_client.py](../../src/budget_agent/model_client.py) | 已有适配层，真实连接待验证 | 确认学校服务可用、结构化输出、失败与超时行为；按实测修补 |
| [src/budget_agent/workflow.py](../../src/budget_agent/workflow.py) | 已有串行总控与正式接口接线 | 集成 B/C/D，跑通正式闭环；与 D 配合开启一轮交叉回应 |
| [src/budget_agent/schemas.py](../../src/budget_agent/schemas.py) | 已有公共数据模型 | 协调必要的字段变更，并同步调用方、样例与文档 |
| [src/budget_agent/config.py](../../src/budget_agent/config.py)、[configs/default.toml](../../configs/default.toml) | 已有配置读取与默认配置 | 根据实测确定模型、上限、路径和正式展示配置 |
| [src/budget_agent/agents/base.py](../../src/budget_agent/agents/base.py) | 已有角色调用辅助 | 支持 B/D 接入；根据联调问题完善公共调用与校验 |
| [src/budget_agent/tools/registry.py](../../src/budget_agent/tools/registry.py) | 已有工具白名单与限制 | 集成 C/D 的工具使用，维护参数校验、调用上限与轨迹 |
| [src/budget_agent/storage.py](../../src/budget_agent/storage.py)、[src/budget_agent/main.py](../../src/budget_agent/main.py) | 已有保存、回放与命令入口 | 验证正式记录、失败状态、回放和命令行运行 |
| [tests/test_workflow.py](../../tests/test_workflow.py)、[tests/test_model_client.py](../../tests/test_model_client.py)、[tests/test_registry.py](../../tests/test_registry.py)、[tests/test_contracts.py](../../tests/test_contracts.py) | 已有基础检查 | 新增实际集成中发现的必要回归案例，保持公共检查通过 |
| [pyproject.toml](../../pyproject.toml)、[uv.lock](../../uv.lock)、[requirements.lock](../../requirements.lock)、[.github/workflows/checks.yml](../../.github/workflows/checks.yml) | 已有安装与检查配置 | 统一依赖；有变动时同步锁文件，检查远程 CI 和跨平台运行 |
| [docs/A/model_setup.md](model_setup.md) | 已有接入说明 | 补充真实连接验证结果与实际支持的接口能力 |

本机密钥填在 `.env`，不提交。公共任务与进度见 [任务清单](../common/tasks.md)。

不要把“能启动 demo”当成完整系统完成。model_client 已按学校截图实现文本适配，
尚未真实连通；需要你在本机填 .env 后验证，不把密钥提交到仓库。

## 第一项任务

1. 让全员按 README 启动同一个演示案例并运行 pytest。
2. 组织共同确认 schemas.py，特别是预算的两次调用与优惠输入。
3. 运行 `uv run budget-agent check-model`，确认校园网络、文本输出、用量和调用额度。
4. 在 Issue 中分配 [公共任务清单](../common/tasks.md) 的任务，记录每人的首次可验收日期。

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
