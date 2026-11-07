# 赛博节俭局 · 消费决策 Agent

五人课程项目的**可运行协作骨架**。课堂展示为 **2026 年 11 月 21 日下午（北京时间）**。

目前完成公共协议、串行流程、工具白名单、记录与回放、学校模型适配层和最小界面。
预算、通用优惠求解、正式角色策略与评测仍由 A—E 开发。
离线演示采用脚本角色和手工复算的优惠 fixture，**不代表正式算法或模型效果**。

## A—E 统一上手顺序

**每位同学都先了解整个项目，再进入自己的模块开发。**

1. **获取最新仓库。** A 首次建仓并分享地址；B—E 首次使用先克隆到本机。A 在自己的现有仓库工作。
   已有本机仓库的同学，先保存手头改动，再更新 main；具体命令见 [Git 协作指南](CONTRIBUTING.md)。
2. **看共同框架。** 先读 [总体结构](docs/common/overview/README.md) 和
   [系统流程图](docs/common/overview/flowcharts.md)，了解各模块与负责人；
   需要查具体文件时看 [文件地图](docs/common/overview/file_map.md)。
3. **看接口与个人任务。** 阅读 [公共接口约定](docs/common/contracts.md)，
   再进入自己的 `docs/A/`、`docs/B/`、`docs/C/`、`docs/D/` 或 `docs/E/`，阅读对应 README。
4. **进入开发。** 按下方说明安装环境、跑通离线示例，再从最新 main 创建任务分支，完成开发、检查与 PR。

首次克隆（地址由 A 提供，命令将本机目录统一命名为 budget-agent）：

```text
git clone 替换为实际仓库地址 budget-agent
cd budget-agent
```

公共资料统一入口：[docs/common/README.md](docs/common/README.md)。个人开发入口见下方“成员入口”。

## 第一次启动（Windows / macOS / Linux）

推荐 Python 3.12，支持 3.11—3.13。终端先进入本仓库目录。
推荐安装 [uv](https://docs.astral.sh/uv/getting-started/installation/)，然后：

```text
uv sync --frozen --extra dev --extra ui
uv run budget-agent list-cases
uv run budget-agent run --case sneakers_wait
uv run budget-agent run --case tissue_buy
uv run streamlit run app.py
```

不需要激活虚拟环境。`uv.lock` 统一依赖版本；普通成员不要单独重新锁定依赖。
CLI 会在 `outputs/` 保存记录。默认无网络、无 API 消耗。

不用 uv 的同学可使用已安装的 Python 3.12：

```text
python -m venv .venv
```

macOS / Linux：

```text
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m budget_agent run --case sneakers_wait
.venv/bin/python -m streamlit run app.py
```

Windows PowerShell：

```text
.venv\Scripts\python.exe -m pip install -r requirements.lock
.venv\Scripts\python.exe -m pip install --no-deps -e .
.venv\Scripts\python.exe -m budget_agent run --case sneakers_wait
.venv\Scripts\python.exe -m streamlit run app.py
```

Windows 若 `python` 不是 3.12，可用 `py -3.12 -m venv .venv`。
依赖下载需要联网；学校模型若校外访问受限，按学校要求连接校园网络。

## 当前能运行什么

| 内容 | 当前状态 |
|---|---|
| `demo` 离线闭环、最小输入表单、证据/调用轨迹、JSON 回放 | 可用，明确标注演示 |
| 数据模型、工具参数校验、上限与基础决策保护 | 可用，成员继续扩展 |
| 学校文本模型适配层与 `check-model` | 基础文本和 JSON 自检已由 A 确认通过；正式集成待验证 |
| B 的正式预算与理性节点 | 接口待实现 |
| C 的正式数据加载与通用优惠求解 | 接口待实现 |
| D 的正式角色、工具选择与交叉回应 | 接口待实现 |
| E 的完整界面、基线与指标、冻结测试集 | 最小入口已提供，业务待实现 |

```text
uv run budget-agent run --case missing_profile
uv run budget-agent run --case unknown_shipping
uv run budget-agent run --case exact_budget
uv run budget-agent run --mode real --case sneakers_wait
```

最后一条当前会明确返回 `partial` 和 TODO，退出码为 2；不会偷偷使用演示逻辑。
`completed` 只描述流程状态，是否演示由 `mode` 与模型标识单独说明。

## 学校模型配置（A）

把 `.env.example` 复制为 `.env`，仅在本机填写密钥。
macOS 可用 `cp .env.example .env`；PowerShell 可用 `Copy-Item .env.example .env`。

```dotenv
BUDGET_AGENT_API_KEY=在本机填写
BUDGET_AGENT_BASE_URL=https://api.llm.ustc.edu.cn/v1
BUDGET_AGENT_MODEL=qwen3.8-chat
```

地址与模型名来自 A 提供的学校平台截图。适配层发送到 `/chat/completions`。
以下命令**明确发起一次真实请求**，用于连接检查：

```text
uv run budget-agent check-model
```

基础连接通过后，再检查项目所需的 JSON 数据格式（格式失败最多重试一次）：

```text
uv run budget-agent check-model --json
```

当前 A 已确认基础文本和真实 JSON 自检通过。该检查独立于 B/C/D 的正式业务模块。

连接成功不等于正式业务已完成。第一阶段先统一一个文本 chat 模型；推理、OCR、
图像模型不是可随意替换的同类接口，其他模型需由 A 实测后配置。
完整的用户提供列表见 [模型接入说明](docs/A/model_setup.md)。

## 成员入口

| 成员 | 主责 | 开始阅读 |
|---|---|---|
| A | 协议、流程、模型与集成 | [A 开发指南](docs/A/README.md) |
| B | 预算与理性分析 | [B 开发指南](docs/B/README.md) |
| C | 数据与优惠求解 | [C 开发指南](docs/C/README.md) |
| D | 角色协作、优惠工具策略与裁判 | [D 开发指南](docs/D/README.md) |
| E | 界面、案例、评测与展示 | [E 开发指南](docs/E/README.md) |

共同阅读：[总体结构](docs/common/overview/README.md) · [系统流程图](docs/common/overview/flowcharts.md) · [接口契约](docs/common/contracts.md) ·
[Git 协作](CONTRIBUTING.md) · [排期](docs/common/roadmap.md) · [任务清单](docs/common/tasks.md)。

**每个人需要修改哪些文件？** 各成员指南前部都有“需要完成的文件”表，列出完整路径、当前状态和具体任务。
全组索引见 [文件分工与任务清单](docs/common/tasks.md)。

## 检查与回放

```text
uv run pytest
uv run ruff check .
uv run budget-agent replay outputs/替换成真实记录文件名.json
uv run python -m evaluation.run --baseline M --cases data/cases/test.jsonl
```

最后一条是待实现评测入口，当前因测试集为空退出 2，不输出虚假的评测结果。
业务验收测试暂用严格 `xfail(raises=ModuleNotReady)` 标记；完成对应模块后应移除标记。
不要只看测试是否全绿，要区分 `passed` 和尚待实现的 `xfailed`。

本次交付的具体检查结果见 [验证记录](docs/common/verification.md)。

回放不调用模型，CLI 会标明历史运行时间与模式。没有随仓库提供“真实模型运行记录”。

## 目录

```text
configs/                 A：TOML 配置
src/budget_agent/        正式包、公共协议、流程、角色与工具
src/budget_agent/demo.py 专用离线替身，正式模块不得依赖
data/catalog/           C：明确标记为演示的商品与活动
data/cases/             E：开发案例与待冻结测试集
evaluation/             E：评测接口与评分标准
tests/                  公共检查与 B/C/D/A 的验收起点
docs/A/ 至 docs/E/      各成员自己的开发文档
docs/common/           全员共读的接口、任务、排期与验证记录
docs/common/overview/  总体结构、流程图与逐文件地图
outputs/                本地记录，默认忽略
.github/                CI 与 PR/任务模板
```

采用 `src` 包布局，须先按上述命令安装；不要手动复制文件或修改 `sys.path`。
原始五人方案保留在本仓库的上一级，本仓库 README 和协议记录实施阶段的具体约定。
