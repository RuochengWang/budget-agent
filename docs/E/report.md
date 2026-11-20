# 报告：赛博节俭局 · 消费决策 Agent（E 整合，全员供稿）

> 状态（2026-11-15）：**结构与评测口径已就位，尚无正式实验结果**。
> 所有 `TODO(...)` 必须由对应负责人在真实运行后填写；不得把演示替身、手工 fixture
> 或未复核标签产生的数字写成结论。A—E 各自供稿，E 只负责整合与标注来源。

## 1. 任务与范围（A 供稿）

- 目标用户与典型场景：TODO(A)（大学生生活费约束下的单件购买决策）。
- 输入输出：TODO(A)（`CaseInput` → `RunRecord`，唯一业务入口 `workflow.run_case`）。
- 第一版支持的优惠：同商家单订单、固定价格与固定运费、一次满减 + 一张券 +
  合法叠加、最多 8 个用户确认需要的凑单候选；见 [contracts.md](../common/contracts.md)。
- 明确不支持：跨店、退款、动态运费、实时价格、真实平台全部优惠规则、联网抓取。
- 数据来源：本地商品/活动快照，`is_demo=true`；正式评测使用正式实现，不引用演示 fixture。

## 2. 方法（各负责人供稿，E 整合）

| 成员 | 方法段落 | 边界/局限段落 | 状态 |
|---|---|---|---|
| A | 数据契约、串行流程、学校模型适配、异常与记录 | TODO(A) | TODO(A) |
| B | 预算公式（两次计算）、理性角色策略 | TODO(B) | TODO(B) |
| C | 商品/活动查询、有限优惠枚举与分摊、来源与时点 | TODO(C) | TODO(C) |
| D | 欲望/优惠/裁判角色、工具选择、一轮交叉回应、程序约束 | TODO(D) | TODO(D) |
| E | 界面、案例与独立标签、基线与指标、人工评分、展示 | 见第 7 节 | 已可填写 |

**E 方法（已实现，待真实数据检验）**：
- 界面只调用 `run_case`，不重写计算；历史回放与本次推理明确分离。
- 10 个开发案例用于调试；30 例 `test.jsonl` 候选需 11/16 前两人独立复核冻结。
- `labels.jsonl` 现有 40 条客观标签草案（dev 10 + test 30，全部 `review_status=draft`）：
  预算、最优总付款、购物篮/规则、可行性、缺失字段；通过 `case_id` 关联，
  **不进入模型输入、提示词或界面**；不用 C 求解器给自己出标准答案。
  逐例人工参考算术见 [review_sheet.md](../../data/cases/review_sheet.md)。
- 基线：B0 规则、B1 单模型、B2 单 Agent+工具、M 完整系统、M_no_cross 消融；
  口径见 `evaluation/baselines.py` 的 `baseline_plan()`。
- 客观指标：`evaluation/metrics.py`，每项自带 `total / valid / correct / not_run / rate`；
  存在有效样本时 `rate=correct/total`，未运行或无最终建议的样本保留在分母；有效样本为 0 时 `rate=None`。
- 主观评分：`evaluation/human_rubric.md`，两人盲评、匿名输出、随机顺序、披露组内评价。
- 成本：只报告 tokens 与耗时；任一请求缺某字段，该字段的完整合计写"未提供"，不以部分和代替，**不自行换算费用**。

## 3. 实验设置（E 填写，A 确认）

| 项目 | 值 |
|---|---|
| 冻结 commit / tag | `2bcee375ff09a80180bfca7433afb8af02da2945` / `demo-2026-11-21`（2026-11-20 冻结，E 记录） |
| 数据文件 SHA-256 | 由 `evaluation/run.py` 汇总自动写入 `outputs/*.summary.json` |
| 提示词 SHA-256 | 每条 `RunRecord.prompt_hashes` 自动保存 |
| 模型 ID / base_url | TODO(A)：与 `check-model` 自检一致 |
| 配置快照 | `evaluation/run.py` 自动写入汇总（不含密钥） |
| 开发/测试划分 | dev 10 例调试 / test 30 例候选；测试集已冻结（2026-11-20），复核人与复核日期待两位组员签字后填写 |
| 独立标签 | 40 条全部 `draft`、`reviewers` 为空（2026-11-20 状态）；复核后由 E 运行 `finalize_labels.py` 填写；`--allow-draft-labels` 只用于本地自测 |
| 统一工具额度 | `max_tool_calls=6`（A 维护，实验期间不得单组调高） |
| 随机化设置 | 人工评分两个 seed；TODO(E)：11/17 生成映射时记录 |
| 运行命令 | 见 `evaluation/run.py --help`；输出 `outputs/evaluation-<baseline>.jsonl` 与 `.summary.json` |

基线/消融清单：B0、B1、B2、M、M_no_cross（至少一个消融：关闭交叉回应）。
统一同模型、同数据快照、同工具额度、同提示词版本。

## 4. 结果（待 11/17—18 真实运行）

> 当前不得填入任何准确率、提升幅度或费用。以下表格只定义汇报格式。
>
> **2026-11-20 状态**：本机没有 `.env` 模型密钥（`real` 运行返回 `partial`），且标签 `reviewed = 0/30`，
> 因此 B0/B1/B2/M/M_no_cross 尚无任何正式结果，下表保持 TODO；冻结版本只验证了 demo 流程与 199 项自动测试。

| 指标 | 分母 | 有效样本 | 正确数 | 未运行 | 比率 |
|---|---|---|---|---|---|
| 预算正确率 | TODO | TODO | TODO | TODO | TODO |
| 优惠最优总付款 | TODO | TODO | TODO | TODO | TODO |
| 最优购物篮/规则 | TODO | TODO | TODO | TODO | TODO |
| 优惠可行性 | TODO | TODO | TODO | TODO | TODO |
| 证据引用有效性 | TODO | TODO | TODO | TODO | TODO |
| 缺信息识别 | TODO | TODO | TODO | TODO | TODO |
| 约束违规数 | TODO | — | TODO（违规数） | — | TODO |

| 基线 | 平均 tokens | 平均耗时 | 失败/partial 数 | 备注 |
|---|---|---|---|---|
| B0 | TODO | TODO | TODO | 不调用模型 |
| B1 | TODO | TODO | TODO | |
| B2 | TODO | TODO | TODO | |
| M | TODO | TODO | TODO | |
| M_no_cross | TODO | TODO | TODO | 与 M 同配置，仅关闭交叉回应 |

- 失败案例：TODO(E) 至少 1 例，写清输入、期望、实际与原因；不得隐藏 partial。
- 主观评分：三维度均值/中位数、有效评分数、两人一致率、分歧案例；披露组内评价。
- 禁止：用模型自评证明效果；把多角色输出更长当作质量更好；把未运行样本记为正确。
- 所有数字必须能追溯到一个 `outputs/*.summary.json` 与对应记录文件。

## 5. 展示与回放

- 展示脚本：[demo.md](demo.md)；展示时间 2026-11-21 下午，Asia/Shanghai。
- 现场状态：demo / real / 历史回放明确区分；失败时保留可用结果，不显示假成功。
- 备用：11/20 冻结版本生成的 3 条记录 —— `outputs/21aebf1d0dc3472ba8db0f34d9481d71.json`（sneakers_wait, demo）、
  `outputs/2b30e37ebc3944d88e6ec3bdf6447ce9.json`（tissue_buy, demo）、
  `outputs/ef3faca934c34b52a8d10f809496b4ff.json`（sneakers_wait, real partial）。录像仍待录制（TODO(E)）。

## 6. 局限（全员供稿）

- 数据：静态快照、4 个商品与 2 条活动，样本规模小；TODO(C)。
- 规则：自定义有限优惠，不代表真实平台结算；TODO(C)。
- 自主性：模型只提工具名与参数，程序白名单执行；不得 eval；TODO(A/D)。
- 开销：时间/调用/token 上限；TODO(A/E 实测)。
- 评测：标签与评分组内产生，存在偏差；TODO(E)。
- 其它：TODO(A/B/D)。

## 7. 贡献（按实际提交与验收记录）

| 成员 | 提交 / PR | 验收记录 | 报告段落 |
|---|---|---|---|
| A | TODO(A) | TODO(A) | 第 1、2、6 节 |
| B | TODO(B) | TODO(B) | 第 2、6 节 |
| C | TODO(C) | TODO(C) | 第 2、6 节 |
| D | TODO(D) | TODO(D) | 第 2、6 节 |
| E | TODO(E) | 界面/案例/评测/展示/报告 | 第 2、3、4、5 节 |

预定分工不等于最终贡献；按实际提交、PR 与验收记录填写，不代他人补写。
