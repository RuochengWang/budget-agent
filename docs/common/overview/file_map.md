# 全员文件地图：系统如何运行、每个文件做什么

供 A—E 查阅。先阅读 [总体结构](README.md) 与 [系统流程图](flowcharts.md)，
再用本页对照职责和文件；A 可按第 4 节继续深入总控代码。
本文描述当前骨架，正式业务仍需 B/C/D/E 完成。

## 1. 先明确：五个人在开发一个怎样的系统

用户提供想买的商品、需求和生活费情况。系统先计算可支配预算，再讨论需求、
查优惠，最后根据实际付款额给建议，并保存依据。

五个人是开发分工；运行时有欲望、理性、优惠、裁判四个角色。
四个角色可以共用同一个学校模型，通过不同提示词和上下文承担不同职责。
预算、价格和优惠由程序计算；模型负责需求分析、取舍解释和工具选择。

| 开发者 | 交付给整个系统的能力 |
|---|---|
| A | 规定各模块如何交流、安排执行顺序、连接学校模型、处理异常并集成 |
| B | 预算计算与理性角色 |
| C | 商品/活动数据与优惠计算工具 |
| D | 欲望角色、优惠工具调用策略、裁判与最终约束检查 |
| E | 用户界面、测试案例、评测与展示材料 |

## 2. 一次点击之后，代码如何流动

主线是：输入 → 初算预算 → 商品资料 → 欲望/理性观点 → 优惠工具 →
按最终付款复核预算 → 可选交叉回应 → 裁判 → 程序检查 → 展示与保存。
完整图统一维护在 [flowcharts.md](flowcharts.md)，避免多份流程图出现分歧。

这里展示正常路径；每一步都可能因为缺信息、未实现或调用失败而提前结束，
workflow.py 会在运行记录中说明状态与原因。当前节点按顺序执行。

角色调用学校模型时，共用 `agents/base.py → model_client.py` 这条通路。
这些是底层支持，不是在裁判之后额外执行的两个步骤。

## 3. 用球鞋案例把文件串起来

输入：现金 1200 元，20 天后再拿生活费，每天基本开支 40 元，固定支出 0，
预留金 100 元，想买 800 元球鞋，优惠后 650 元。

| 发生什么 | 对应文件 | 交给下一步什么 |
|---|---|---|
| 用户填写表单 | app.py | 用户输入 |
| 检查并统一字段 | schemas.py | CaseInput：预算资料和购买请求 |
| 开始按顺序执行 | workflow.py | 给各模块分配输入、收集结果 |
| 计算 1200−20×40−100=300 元 | tools/budget.py | BudgetResult：可支配预算 300 元 |
| 读取球鞋及活动 | tools/catalog.py、promotions.py | Product、PromotionRule |
| 分析喜欢的理由与必要性 | agents/desire.py、rational.py | Argument：观点和证据引用 |
| 选择查询/求解工具并取得 650 元方案 | agents/deal.py 调 tools/optimizer.py | DealResult，其中含 OfferResult |
| 用 650 元重新检查生活费是否够 | tools/budget.py | within_budget=false |
| 综合观点，建议等待 | agents/judge.py | DecisionProposal：原始建议 |
| 如果模型误说“买”，将其调整并记原因 | decision_policy.py | Decision：经基础约束检查的最终建议 |
| 形成整次记录并保存 | workflow.py、storage.py | outputs/ 中的本地 JSON 文件 |

上表是正式模块完成后的职责分配。当前离线演示由 demo.py 提供预算参考公式、
脚本观点和手工优惠方案；正式同名业务函数尚待实现。

## 4. A 先读这几个文件，按这个顺序

1. 本页：先看清整次运行与分工。
2. [schemas.py](../../../src/budget_agent/schemas.py)：看“各模块交接什么”。先认对象名，再看字段。
3. [workflow.py](../../../src/budget_agent/workflow.py)：先读 `run_case()`，对照第 2 节流程；
   再读 `build_services()`，看它如何选择演示/正式模块。
4. [contracts.md](../contracts.md)：看“字段与函数必须遵守什么含义”，例如金额用分、缺失不能当零。
5. [A 开发指南](../../A/README.md)：看 A 需要完成与验收什么。
6. [tasks.md](../tasks.md)、[roadmap.md](../roadmap.md)：安排任务和集成日期。

`schemas.py` 中先认这条数据链即可：

```text
CaseInput                本次输入
  ├─ UserProfile         现金、天数、开支、预留金等
  └─ PurchaseRequest     想买什么、为什么、凑单需求、运费和时点

BudgetResult             预算工具结果
Product / PromotionRule  商品与优惠规则
OfferResult              购物篮、折扣、运费与最终付款
Argument                 一位角色的观点与证据 ID
RoleContext              传给角色的“截至目前已知资料”
DecisionProposal         裁判的原始建议
Decision                 程序检查后的最终建议
RunRecord                将输入、过程、依据和结果装在一起的运行记录
```

角色读取 RoleContext，产生新观点或方案；总控收集这些输出，再交给后续节点。
这就是“接口”：大家约定接收什么、返回什么。函数内部可以各自实现，交接格式保持一致。

## 5. 文件地图：按用途找，而不是从目录第一项往下读

以下路径均相对于项目根目录。点文件名可查看文件。

### 5.1 用户入口与 A 的基础设施

| 文件 | 用普通话解释 | 负责人 / 当前状态 |
|---|---|---|
| [app.py](../../../app.py) | 用户看到的网页表单、结果、观点与记录展示 | E，已有最小界面 |
| [src/budget_agent/main.py](../../../src/budget_agent/main.py) | 接收终端命令：运行案例、回放、检查模型连接 | A，已有 |
| [src/budget_agent/__main__.py](../../../src/budget_agent/__main__.py) | 让 `python -m budget_agent` 能找到命令入口 | A，已有 |
| [src/budget_agent/schemas.py](../../../src/budget_agent/schemas.py) | 全组通用的数据表格模板和格式检查 | A 协调，全组遵守，已有 |
| [src/budget_agent/workflow.py](../../../src/budget_agent/workflow.py) | 安排每一步的顺序、选择演示/正式模块、收集运行结果 | A，已有基础 |
| [src/budget_agent/model_client.py](../../../src/budget_agent/model_client.py) | 向学校服务发送请求、接收与检查模型返回；另含假模型 | A，已编写，真实连接待验证 |
| [src/budget_agent/config.py](../../../src/budget_agent/config.py) | 读取配置和本机环境变量，处理跨平台路径 | A，已有 |
| [src/budget_agent/storage.py](../../../src/budget_agent/storage.py) | 保存、读取整次运行的 JSON 记录 | A，已有 |
| [src/budget_agent/errors.py](../../../src/budget_agent/errors.py) | 统一错误类型，例如“模块未完成”“调用次数用完” | A，已有 |
| [src/budget_agent/agents/base.py](../../../src/budget_agent/agents/base.py) | 读取角色提示词，把角色上下文交给模型 | A，已有辅助函数 |
| [src/budget_agent/tools/registry.py](../../../src/budget_agent/tools/registry.py) | 工具白名单：检查名称、参数、返回值、次数与时间 | A，已有 |
| [src/budget_agent/demo.py](../../../src/budget_agent/demo.py) | 专用演示替身，方便业务未完成时联调 | 骨架已有，不作为正式业务实现 |

### 5.2 B/C/D 要开发的核心业务

角色代码负责“怎么执行这项职责”；提示词负责“怎么向模型说明要求”。
工具代码负责确定性计算和数据读取。比如优惠 Agent 可以选择调用求解器，
具体枚举购物篮、算门槛与金额由求解器完成。

| 文件 | 作用 | 负责人 / 当前状态 |
|---|---|---|
| [tools/budget.py](../../../src/budget_agent/tools/budget.py) | 计算基本支出、可支配预算、购买后余额与是否够用 | B，待实现 |
| [agents/rational.py](../../../src/budget_agent/agents/rational.py) | 必要性、替代选择、机会成本与重复购买分析 | B，待实现 |
| [prompts/rational.md](../../../src/budget_agent/prompts/rational.md) | 理性角色的模型指令 | B，已有起始提示词，待完善 |
| [tools/catalog.py](../../../src/budget_agent/tools/catalog.py) | 查找商品、按 ID 精确读取商品 | C，待实现 |
| [tools/promotions.py](../../../src/budget_agent/tools/promotions.py) | 读取并筛选商品适用的活动 | C，待实现 |
| [tools/optimizer.py](../../../src/budget_agent/tools/optimizer.py) | 枚举合法购物篮和活动，比较总付款，返回明细 | C，待实现 |
| [agents/desire.py](../../../src/budget_agent/agents/desire.py) | 讨论使用价值、偏好与购买理由 | D，待实现 |
| [agents/deal.py](../../../src/budget_agent/agents/deal.py) | 决定查什么优惠、用什么工具、是否需要补查 | D，待实现 |
| [agents/judge.py](../../../src/budget_agent/agents/judge.py) | 综合需求、预算、方案与观点，提出建议 | D，待实现 |
| [agents/cross_response.py](../../../src/budget_agent/agents/cross_response.py) | 针对已有证据进行最多一轮回应 | D，待实现，当前关闭 |
| [decision_policy.py](../../../src/budget_agent/decision_policy.py) | 对裁判建议检查预算、引用和方案明细，记录调整原因 | D，已有最低保护，待扩展 |
| [prompts/desire.md](../../../src/budget_agent/prompts/desire.md) | 欲望角色的模型指令 | D，待完善 |
| [prompts/deal.md](../../../src/budget_agent/prompts/deal.md) | 优惠角色的模型指令 | D，待完善 |
| [prompts/judge.md](../../../src/budget_agent/prompts/judge.md) | 裁判角色的模型指令 | D，待完善 |

本表中的 tools/、agents/、prompts/、decision_policy.py 均位于 `src/budget_agent/` 内。

### 5.3 数据、评测和结果

| 文件/目录 | 作用 | 负责人 / 当前状态 |
|---|---|---|
| [data/catalog/products.json](../../../data/catalog/products.json) | 商品快照，包括价格、来源和采集时间 | C，已有演示数据 |
| [data/catalog/promotions.json](../../../data/catalog/promotions.json) | 活动快照，包括门槛、减免、时效与叠加条件 | C，已有演示数据 |
| [data/demo_offers.json](../../../data/demo_offers.json) | 离线演示使用的手工优惠结果 | 专用演示资料，不是正式算法成绩 |
| [data/cases/dev.jsonl](../../../data/cases/dev.jsonl) | 开发时反复使用的输入案例，每行一个 | E，已有 5 例 |
| [data/cases/test.jsonl](../../../data/cases/test.jsonl) | 最终冻结的评测输入，避免一直按测试答案调系统 | E，当前为空 |
| [data/cases/README.md](../../../data/cases/README.md) | 案例格式、独立标签与冻结要求 | E 的数据说明 |
| [evaluation/run.py](../../../evaluation/run.py) | 对一批案例运行指定实验方案并写结果 | E，已有入口，依赖基线实现 |
| [evaluation/baselines.py](../../../evaluation/baselines.py) | 定义规则系统、单模型、单 Agent、完整系统等对照组 | E，待实现 |
| [evaluation/metrics.py](../../../evaluation/metrics.py) | 与独立标签比较，计算准确率等指标 | E，待实现 |
| [evaluation/human_rubric.md](../../../evaluation/human_rubric.md) | 人工如何给解释质量评分 | E，已有评分起点 |
| `outputs/` | 本机运行记录和实验输出，不提交 Git | A 提供保存，E 使用 |
| [outputs/.gitkeep](../../../outputs/.gitkeep) | 让空 outputs 目录能随仓库保留 | 占位文件，无业务逻辑 |

### 5.4 tests：用小例子检查程序，而不是给模型评分

| 文件 | 检查什么 | 主要负责人 |
|---|---|---|
| [tests/conftest.py](../../../tests/conftest.py) | 给测试准备配置、商品、活动与案例 | A 提供基础 |
| [tests/test_contracts.py](../../../tests/test_contracts.py) | 金额格式、缺失值、时区、候选数量等公共约定 | A |
| [tests/test_budget.py](../../../tests/test_budget.py) | 预算公式和边界，预期金额事先人工写明 | B，正式函数待实现 |
| [tests/test_optimizer.py](../../../tests/test_optimizer.py) | 凑单是否真少付、单买基准、未知运费 | C，B 协助，正式函数待实现 |
| [tests/test_decision_policy.py](../../../tests/test_decision_policy.py) | 伪造引用、不合法购物篮和不一致金额是否被拦住 | D |
| [tests/test_workflow.py](../../../tests/test_workflow.py) | 整条演示链、缺信息、上限、原始/最终建议与模式隔离 | A |
| [tests/test_registry.py](../../../tests/test_registry.py) | 未知工具、非法参数和超时是否被阻止 | A |
| [tests/test_model_client.py](../../../tests/test_model_client.py) | 用模拟服务检查请求路径、输出重试与错误处理 | A，不调用真实模型 |
| [tests/test_ui.py](../../../tests/test_ui.py) | 界面能否加载、提交并展示结果 | E |

`tests/` 检查“实现是否符合约定”；`evaluation/` 研究“完整系统的效果如何”。
当前 11 个严格 xfail 是 B/C 业务未完成的标记，不能当作已经通过。

### 5.5 配置、安装与 Git 支持文件

| 文件 | 做什么 | A 需要掌握的程度 |
|---|---|---|
| [configs/default.toml](../../../configs/default.toml) | 运行模式、模型、调用/时间上限和数据路径 | 知道调整哪个字段；由 config.py 读取 |
| [.env.example](../../../.env.example) | 给组员看的本机密钥配置模板，不含真密钥 | 复制为 .env 后本机填写 |
| `.env` | 本机真实密钥与配置，当前骨架没有创建 | 不上传 Git |
| [pyproject.toml](../../../pyproject.toml) | 声明项目名、Python 范围、依赖、入口和检查工具设置 | A 统一维护 |
| [uv.lock](../../../uv.lock) | 自动生成的统一依赖版本清单 | 提交 Git，日常不手改 |
| [requirements.lock](../../../requirements.lock) | 不用 uv 的同学安装相同依赖的备用清单 | 从 uv.lock 同步生成 |
| [.python-version](../../../.python-version) | 指定推荐使用 Python 3.12 | 保持全组一致 |
| [.gitignore](../../../.gitignore) | 告诉 Git 忽略密钥、环境、缓存与运行记录 | 上传前确认规则生效 |
| [.gitattributes](../../../.gitattributes) | 统一不同系统的文本换行处理 | 已配置，日常少改 |
| [.github/workflows/checks.yml](../../../.github/workflows/checks.yml) | 上传 GitHub 后自动在三种系统上检查 | 了解 PR 页检查结果；尚未在远程运行 |
| [.github/PULL_REQUEST_TEMPLATE.md](../../../.github/PULL_REQUEST_TEMPLATE.md) | 提醒提交者说明改动与验证 | 审 PR 时用 |
| [.github/ISSUE_TEMPLATE/task.md](../../../.github/ISSUE_TEMPLATE/task.md) | 填写可认领的开发任务 | 分配任务时用 |

安装生成的 `.venv/` 是依赖环境；`__pycache__/`、`.pytest_cache/`、`.ruff_cache/`
是缓存；`*.egg-info/` 是安装元信息。它们已经被忽略，不属于组员要实现的功能。
几个 `__init__.py` 负责包标记或版本信息：包根目录、agents/、tools/、evaluation/ 中都有，
大部分没有业务逻辑。它们与 `__main__.py`（启动入口）的作用不同。

### 5.6 docs：遇到问题去哪里查

| 文件 | 回答的问题 |
|---|---|
| [README.md](../../../README.md) | 怎么安装、启动、当前哪些能用？ |
| [AGENTS.md](../../../AGENTS.md) | AI 编程助手在此仓库中遵守什么约定？ |
| [CONTRIBUTING.md](../../../CONTRIBUTING.md) | 怎么开分支、提交、提 PR 与集成？ |
| [common/README.md](../README.md) | 全员公共资料在哪里，先读哪份？ |
| [common/overview/README.md](README.md) | 整个项目的目标、目录与五人分工是什么？ |
| [common/overview/file_map.md](file_map.md) | 你正在看的逐文件地图 |
| [common/overview/flowcharts.md](flowcharts.md) | 系统流程图、模式、状态和记录的设计是什么？ |
| [contracts.md](../contracts.md) | 输入输出字段、金额和优惠规则具体怎么约定？ |
| [A/README.md](../../A/README.md) / [B/README.md](../../B/README.md) / [C/README.md](../../C/README.md) / [D/README.md](../../D/README.md) / [E/README.md](../../E/README.md) | 每个人从哪里动手，交什么，怎么验收？ |
| [tasks.md](../tasks.md) | 当前有哪些待认领、待完成任务？ |
| [roadmap.md](../roadmap.md) | 到展示前，什么日期完成什么？ |
| [model_setup.md](../../A/model_setup.md) | 学校模型地址、配置与连接检查怎么做？ |
| [verification.md](../verification.md) | 骨架交付时实际验证了什么，哪些未验证？ |
| [demo.md](../../E/demo.md) | 课堂怎么演示、故障时怎么回放？ |
| [report.md](../../E/report.md) | 报告各部分由谁提供，目前还缺什么？ |

## 6. 你如何知道大家写完的模块能接起来

以 B 完成预算为例：B 在正式 `tools/budget.py` 内实现约定函数，保持输入输出签名。
同一个函数在正式 `build_services()` 中已经接好。合并后正式运行就会调用新实现；
之后如果 C 的商品查询还未完成，会在 C 的入口报告 partial，便于看清下一处阻塞。

你在 PR 中重点确认四件事：

1. 改的是正式业务文件，输入输出仍符合 schemas.py 和 contracts.md。
2. 小例子算得对，测试真正通过；已实现部分对应的 xfail 已移除。
3. 修改公共字段时，所有调用方、示例和文档已经同步。
4. 合并后的整体流程能够走到更后一步，失败时能看到原因。

## 7. A 每天掌握的五个问题

| 问题 | 去哪里确认 |
|---|---|
| 这个模块谁负责、今天交什么？ | docs/A/—docs/E/、公共 tasks.md 与 Issue |
| 它收什么、返回什么？ | schemas.py、contracts.md |
| 它在整条流程的哪一步？ | workflow.py 的 run_case() |
| 怎样证明完成，而不是只说“写好了”？ | 对应 tests 与小型人工复算例子 |
| 当前正式流程卡在哪一步？ | `run --mode real` 的状态、错误与 outputs 轨迹 |

第一个共同目标：两个正式案例（超预算球鞋、合理纸巾凑单）都能从输入走到建议并保存依据。
这条正式闭环完成后，再验收更复杂优惠、交叉回应、评测和完整展示体验。
