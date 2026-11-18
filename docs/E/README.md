# E · 界面、评测与展示

先取得最新仓库，阅读 [总体结构](../common/overview/README.md)、
[系统流程图](../common/overview/flowcharts.md) 和 [接口约定](../common/contracts.md)，再按本文开发。
当前界面、10 个开发案例、30 例测试集候选、评测指标/运行器/评分流程与展示脚本已就绪；
B/C/D 和 A 的真实联调修复均已合并；正式实验仍待两人独立复核、有效模型配置以及 A 确认实验范围和额度。

## 需要完成的文件

以下路径相对于项目根目录。先完成界面与开发案例，正式集成后再运行对照实验。

| 文件 | 当前状态 | E 要完成什么 |
|---|---|---|
| [app.py](../../app.py) | 已补齐表单、展示与回放基础版，**待联调完善** | 商品、已有物品、紧迫程度与凑单输入已接入；结果、失败与回放展示已实现，正式模块接入后补对照视图 |
| [evaluation/baselines.py](../../evaluation/baselines.py) | 契约与 M/M_no_cross 已实现 | B0/B1/B2 待 A 确认 Services 注入点后由负责人 register_baseline() 注册；未注册时明确报错 |
| [evaluation/metrics.py](../../evaluation/metrics.py) | 客观指标已实现 | 与独立标签比较，每项含 total/valid/correct/not_run/rate；单元测试见 tests/test_evaluation.py |
| [evaluation/run.py](../../evaluation/run.py) | 已完善 | 复核标签校验、real 模式守卫、拒绝 partial/demo 记录、配置/哈希/commit 快照与汇总 JSON |
| [evaluation/rehearsal_check.py](../../evaluation/rehearsal_check.py) | 已新增 | 11/20 彩排只读自检：冻结 commit、标签复核状态、历史记录、录像、界面两页、展示脚本 TODO；`--strict` 有阻塞项退出 2 |
| [evaluation/human_rubric.md](../../evaluation/human_rubric.md) | 流程已落实 | 匿名化映射、双 seed 随机排序、评分记录格式、汇总披露；评分数据待 11/17—18 生成 |
| [data/cases/dev.jsonl](../../data/cases/dev.jsonl) | 已有 10 个开发案例 | 已覆盖预算不足/恰好、重复需求、凑单省钱/多花、活动过期、运费未知、缺字段；继续补真实场景 |
| [data/cases/test.jsonl](../../data/cases/test.jsonl) | 已有 30 例候选，**待两人独立人工复核** | 逐例复算并记录复核人、实际日期和冻结 commit；冻结后不再改数值 |
| [data/cases/labels.jsonl](../../data/cases/labels.jsonl) | 已有 40 条草案（dev 10 + test 30，全部 `draft`） | 集成修正 3 条基本支出并补独立公式回归；其余客观字段仍待复核，标签不传给模型 |
| [data/cases/README.md](../../data/cases/README.md) | 已补覆盖矩阵与冻结流程 | dev 10 例、test 30 例候选、labels 格式、11/16 双人复核占位表；另见 [review_sheet.md](../../data/cases/review_sheet.md) 的 30 例逐例参考算术 |
| [tests/test_ui.py](../../tests/test_ui.py) | 已补关键输入、缺失值与回放验收 | 覆盖空白与 0 的区分、案例切换、正式模式 partial 与历史回放 |
| [docs/E/demo.md](demo.md) | 已完善 20 分钟脚本 | 实验数字、展示人分配与录像路径为 TODO，11/19–20 填入 |
| [docs/E/report.md](report.md) | 已扩成可填写结构 | 实验数字、成员供稿、贡献记录为 TODO，11/19 整合 |

实验输出写在 `outputs/`，默认不入库。报告方法与局限段落由 A—E 各自供稿，E 负责整合。

## 界面开发

先运行 `uv sync --frozen --extra dev --extra ui`，再运行 `uv run streamlit run app.py`。
UI 统一调用 `run_case()`，不在界面重写预算或优惠计算。默认离线演示；选择「正式模块」后使用
[A 的验证配置](../../configs/validation.toml)（单次模型请求 90 秒、全流程 540 秒、默认关闭交叉回应）。
如需真实模型，在运行机器本地配置密钥；缺密钥不会自动回退到演示。见 [A 真实联调记录](../A/live_validation.md)。
完善目标商品、需求紧迫程度、已有物品、确实需要的凑单品等输入。
表单金额以元显示，内部用 Decimal 转整数分；空白与零必须区分。
按“输入→客观计算→观点→结论→证据/轨迹”展示，明确标记演示、正式与历史回放。
实时接口失败时保留可用结果，不显示假的成功；历史记录不能冒充正在推理。

## 案例与评测

现有 dev.jsonl 已有 10 个开发案例；test.jsonl 已有 30 例候选，
原计划 11/16 冻结；当前仍需至少两位组员独立复核案例和标签，记录实际日期（见 [案例说明](../../data/cases/README.md)）。
独立标签不进入模型输入，不用 C 求解器给自己出标准答案。
覆盖预算不足/恰好、重复需求、凑单省钱/多花、互斥/过期、运费未知、缺字段等。

基线接口见 baselines.py：B0 规则、B1 单模型、B2 单 Agent+工具、M 完整系统、M_no_cross 消融。
与 A 商定同模型/快照/工具额度；B0 可不调用模型，但仍需正式预算与求解器。
预算正确率、优惠可行/最优金额、约束违规、证据、缺信息识别、耗时/调用用量分别报告。
每个指标写清分母、有效样本数；存在有效样本时 `rate=correct/total`，未运行或无最终建议的样本保留在分母，
有效样本为零时 `rate=None`。任一请求缺少用量字段，该字段的完整总量为 `None`，不显示部分和。
人工评分使用 human_rubric.md，两人盲评、随机顺序，披露组内评价。
没有价格依据就报告 tokens，不自行换算费用。

两位复核人都确认后，再按 [复核操作说明](../../data/cases/reviewer_instructions.md) 使用收尾工具。
`--cases data/cases/test.jsonl` 只选 30 条测试标签，不替开发案例签字；默认 dry-run，仅 `--apply` 写入复核元数据，不改数值。
正式实验前可用 `.venv/bin/python -m evaluation.integration_probe` 做离线端到端联调（模拟模型、不调真实 API、不发网络请求），
验证 B/C/D 正式模块与 E 评测框架衔接；探针结论只说明接口通，不代表模型效果。

运行入口（已补齐标签参数）：
`uv run python -m evaluation.run --baseline M --cases data/cases/test.jsonl --labels data/cases/labels.jsonl --output outputs/evaluation-M.jsonl`。
运行器会拒绝未复核标签、demo 记录、partial/failed 记录与缺标签案例；
`--allow-draft-labels` 仅供本地自测，绝不用于正式成绩。
B0/B1/B2 未注册时明确退出 2；M/M_no_cross 在缺少模型密钥或运行失败时也会因 partial 被拒绝。
不能提交演示数据生成的“正式成绩”。

## 协作与验收

UI 可用 demo 独立开发；正式评测等待可用的本地模型密钥、A 确认实验配置和额度，以及两人独立复核。
你整合报告，每人仍需提交方法、结果和局限段落，不能由你独自补写全部贡献。
验收：可加载案例、缺失值清楚、错误可见、同一案例可对照、真实指标可复现、能回放。
运行 `uv run pytest tests/test_ui.py tests/test_cases.py tests/test_evaluation.py`；Windows/macOS 各找组员实际启动一次。
11/20 准备离线替身、真实历史回放与备用录像，展示状态要如实标明。

PR #7 的导入、指标、标签与彩排自检修正见 [集成修正记录](integration_fixes.md)。
