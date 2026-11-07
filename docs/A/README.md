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
| [src/budget_agent/model_client.py](../../src/budget_agent/model_client.py) | 已有适配层，基础文本和真实 JSON 自检已通过 | 继续验证失败与超时行为，并参与正式角色联调；按实测修补 |
| [src/budget_agent/workflow.py](../../src/budget_agent/workflow.py) | 已有串行总控与正式接口接线 | 集成 B/C/D，跑通正式闭环；与 D 配合开启一轮交叉回应 |
| [src/budget_agent/schemas.py](../../src/budget_agent/schemas.py) | 已有公共数据模型 | 协调必要的字段变更，并同步调用方、样例与文档 |
| [src/budget_agent/config.py](../../src/budget_agent/config.py)、[configs/default.toml](../../configs/default.toml) | 已有配置读取与默认配置 | 根据实测确定模型、上限、路径和正式展示配置 |
| [src/budget_agent/agents/base.py](../../src/budget_agent/agents/base.py) | 已有角色调用辅助 | 支持 B/D 接入；根据联调问题完善公共调用与校验 |
| [src/budget_agent/tools/registry.py](../../src/budget_agent/tools/registry.py) | 已有工具白名单与限制 | 集成 C/D 的工具使用，维护参数校验、调用上限与轨迹 |
| [src/budget_agent/storage.py](../../src/budget_agent/storage.py)、[src/budget_agent/main.py](../../src/budget_agent/main.py) | 已有保存、回放与命令入口 | 验证正式记录、失败状态、回放和命令行运行 |
| [tests/test_workflow.py](../../tests/test_workflow.py)、[tests/test_model_client.py](../../tests/test_model_client.py)、[tests/test_registry.py](../../tests/test_registry.py)、[tests/test_contracts.py](../../tests/test_contracts.py)、[tests/test_cli_encoding.py](../../tests/test_cli_encoding.py) | 已有基础与编码回归检查 | 新增实际集成中发现的必要回归案例，保持公共检查通过 |
| [pyproject.toml](../../pyproject.toml)、[uv.lock](../../uv.lock)、[requirements.lock](../../requirements.lock)、[.github/workflows/checks.yml](../../.github/workflows/checks.yml) | 已有安装与检查配置 | 统一依赖；有变动时同步锁文件，检查远程 CI 和跨平台运行 |
| [docs/A/model_setup.md](model_setup.md) | 已有接入说明 | 补充真实连接验证结果与实际支持的接口能力 |

本机密钥填在 `.env`，不提交。公共任务与进度见 [任务清单](../common/tasks.md)。

不要把“能启动 demo”当成完整系统完成。model_client 已按学校截图实现文本适配，
A 已确认基础文本连通和 `uv run budget-agent check-model --json` 自检成功。
密钥仅在本机配置，不提交到仓库。

## A 的分步验收进度

- [x] 第一步：学校模型基础文本连接（A 于 2026-11-07 确认成功）。
- [x] 第二步：真实 JSON 输出通过 DecisionProposal 格式校验（A 于 2026-11-07 确认成功）。
- [x] 第三步：在本机检查数据格式、模型适配、工具管理和总控基础（A 于 2026-11-07 确认成功）。
- [x] 第四步：运行球鞋演示案例，核对工具轨迹与最终结果（2026-11-07，本机记录已核对）。
- [x] 第五步：正式模式接线检查通过，当前在 B 预算占位函数处返回 partial（2026-11-07，本机记录已核对）。
- [x] 第六步：保存提交 c88032a、上传分支并创建 PR #1（2026-11-07）。
- [x] 第七步：Windows 修复提交 d816e84 的三系统检查通过；PR #1 按 A 要求直接合并，合并提交 841c881。
- [x] 第八步：模型请求超时检查通过，错误有记录且仅请求一次（A 于 2026-11-07 确认）。
- [x] 第九步：任务到期停止后续步骤并保留部分结果的检查通过（A 于 2026-11-07 确认）。
- [x] 第十步：真实 JSON 自检用量已确认，1 次请求，输入 265、输出 62、合计 327 tokens。
- [x] 第十一步：确认学校每日赠送 100 元额度，并记录当日平台定价快照。
- [ ] 第十二步：提交并上传本轮运行保护、用量显示与验证记录。

第三步执行：

```text
uv run pytest tests/test_contracts.py tests/test_model_client.py tests/test_registry.py tests/test_workflow.py tests/test_cli_encoding.py -q
```

这组检查使用演示或模拟服务，不调用真实学校模型。最初 24 个案例已由 A 确认通过，
后续继续补充必要回归，覆盖非法输入、JSON 重试、工具白名单/上限、
失败状态、记录回放与 Windows 中文输出等；案例数量以实际 pytest 输出为准。
通过后继续对照流程图阅读 run_case()，再集成 B/C/D 的正式模块。

第四步执行：

```text
uv run budget-agent run --mode demo --case sneakers_wait
```

该命令使用独立演示替身，不调用学校模型。预期 `mode=demo`、`status=completed`、
最终 `action=wait`。打开终端提示的本地 JSON 记录，重点看：

| 记录位置 | 该案例的预期值或含义 |
|---|---|
| `input` | 用户预算与球鞋购买请求，所有金额以分记录 |
| `tool_calls` | 初算预算 → 读取商品 → 读取活动 → 优惠方案 → 最终预算复核，共 5 次 |
| `arguments` | 欲望、理性、优惠三个角色的演示观点；裁判建议另存 |
| `proposed_decision` | 裁判的原始建议 |
| `final_decision.budget_result.discretionary_cents` | 30000，即 300 元 |
| `final_decision.offer_result.payable_cents` | 65000，即 650 元 |
| `final_decision.budget_result.within_budget` | false：优惠后总付款仍超预算 |
| `final_decision.action` | wait |
| `policy_violations` | 若程序调整原始建议，这里记录原因；当前正常球鞋案例应为空 |

对照 [workflow.py 的 run_case()](../../src/budget_agent/workflow.py)，确认预算为什么调用两次：
第一次算可支配金额；第二次用最终选定方案的总付款检查是否够用。
演示跑通验证调度与记录，正式预算、优惠求解与角色策略仍由各成员实现。

第五步先读 [workflow.py](../../src/budget_agent/workflow.py) 中两个函数：

1. `build_services()`：按 mode 选择演示替身或 B/C/D 的正式函数，并注册工具。
2. `run_case()`：沿同一套顺序调用已选择的函数，收集证据、观点与最终结果，处理错误。

随后执行：

```text
uv run budget-agent run --mode real --case sneakers_wait
```

按当前代码应返回 `mode=real`、`status=partial`，并指出 B 的正式预算尚未实现，退出码为 2。
这说明总控已使用正式函数；后续 B 完成预算、C/D 完成相关模块后，正式流程会继续前进。
保持公共签名即可沿用接线；若签名变化，A 需协调总控、注册参数和所有调用方同步修改。
当前预算占位函数即会中止该运行，尚不会调用学校模型。

第六步保存阶段成果。当前修改包括 JSON 自检入口、对应自动检查，以及 A 的验证进度文档。
以下命令只在本机记录版本：

```text
git add src/budget_agent/main.py tests/test_model_client.py README.md docs/A docs/common
git diff --cached --stat
git commit -m "feat(A): add JSON model check and validation progress"
git status --short --branch
```

`git add` 选择本次提交的文件；`git commit` 创建一个可追溯版本；最后一条检查保存后的状态。
本机提交完成后，再把 feat/A-integration 上传并创建 PR。正式业务集成仍需等待 B/C/D 的模块。

第七步处理 PR 自动检查发现的问题。PR #1 的 Windows 检查在 CLI 打印中文时
触发 UnicodeEncodeError：标准输出使用 cp1252，无法编码中文。
已在 main() 入口统一配置 stdout/stderr 为 UTF-8，并新增独立子进程回归检查，
模拟 cp1252 下的案例列表、正常运行与错误提示。其他模块逻辑保持现有接口。
修复推送后，Windows、Linux、macOS 的新一轮远程检查全部通过。
PR #1 已按 A 的明确要求直接合并，未进行人工审阅；本机 main 已同步。

第八步开始下一轮运行保护验收，分支为 `feat/A-runtime-checks`。
在 [tests/test_model_client.py](../../tests/test_model_client.py) 中新增
`test_timeout_is_reported_once_and_retains_trace`：模拟 HTTP 读取超时，
检查统一错误、仅一次请求和完整调用记录。单独运行：

```text
uv run pytest tests/test_model_client.py::test_timeout_is_reported_once_and_retains_trace -v
```

此测试让模拟服务直接抛出超时异常，验证适配层的错误处理，不验证真实网络会等待多少秒。
正常 JSON 格式失败允许重试一次；HTTP 超时不触发这项格式重试。

第九步在 [tests/test_workflow.py](../../tests/test_workflow.py) 中新增
`test_workflow_deadline_preserves_partial_record`，单独运行：

```text
uv run pytest tests/test_workflow.py::test_workflow_deadline_preserves_partial_record -v
```

测试设置 10 秒任务上限，在欲望节点完成后将模拟时钟从第 0 秒推进到第 11 秒。
期望总控在下一节点开始前返回 partial，保留已有预算、观点、证据与调用轨迹，
不继续执行理性/优惠/裁判节点，不产生最终建议；返回记录仍能保存与回放。
这个测试不联网、不实际等待。它验证步骤边界的截止时间检查；
当前同步流程不会强行打断正在执行的 Python 函数，联网操作仍需各自的请求超时。

第十步复用模型 JSON 自检，现在会显示每次请求的输入、输出和总 token 用量：

```text
uv run budget-agent check-model --json
```

用量由学校模型响应提供，缺失项目显示“未提供”，不当成零、不自行换算费用。
如果 JSON 格式触发重试，各次请求分别显示。此处仅展示本次调用用量，
账户剩余额度及其单位需到学校平台查询；两者分别记录。
A 已在 qwen3.8-chat 上确认：1 次请求，输入 265、输出 62、总计 327 tokens。
详细记录见 [model_setup.md](model_setup.md)。

第十一步已由 A 确认：学校每天赠送 100 元额度。平台模型用量表显示的是请求、tokens 与费用，
没有剩余额度字段；当天实际余额以平台显示为准，不从单次自检推算。
qwen3.8-chat 的当前价格快照及统计行已记入 [model_setup.md](model_setup.md)。

第十二步把本轮已验证成果保存并上传：

```text
git add src/budget_agent/main.py tests/test_model_client.py tests/test_workflow.py README.md docs/A docs/common
git commit -m "feat(A): verify runtime limits and report token usage"
git push -u origin feat/A-runtime-checks
```

本轮包含模型请求超时与整次任务到期的回归检查、JSON 自检逐次 token 用量显示、
以及实测与配额记录。正式业务仍等待 B/C/D 完成后集成。

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
