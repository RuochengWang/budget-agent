# 案例归属：E

`dev.jsonl` 现有 10 个开发案例，覆盖主要正常与异常情形，用于反复调试界面与流程；
它不是最终评测集。`test.jsonl` 已起草 30 例候选输入（见下方覆盖矩阵），
原定 11 月 16 日冻结，当前仍待 E 组织至少两人独立人工复核；冻结前只修数据错误，不得据此调参。
`labels.jsonl` 现有 40 条标签（dev 10 例 + test 30 例），均为 `review_status=draft` 草案，
通过 `case_id` 关联案例；标签不进入模型输入，也不能让模型看答案。
集成检查已修正 2 条测试草案和 1 条开发草案的基本支出；新增测试独立按输入公式检查全部 40 条基本支出。
优惠等其余客观字段仍须独立人工复核，不能沿用“全部数值无差异”的结论。
人工复核后才改为 `reviewed`，记录实际复核日期；评测运行器默认拒绝未复核标签。

## dev.jsonl 覆盖范围

| 案例 | 情形 | 关键点 |
|---|---|---|
| sneakers_wait | 优惠后仍超预算 | 满减后 650 元 > 可支配 300 元 |
| tissue_buy | 凑单省钱 | 280+25 元满减后 255 元，比单买少 25 元 |
| missing_profile | 缺预留金 | 缺失字段不能当作 0 |
| unknown_shipping | 运费未知 | 总付款不能确认 |
| exact_budget | 恰好达到预算边界 | 280 元 = 可支配 280 元 |
| sneakers_owned_similar | 已有相似物品 | 重复需求影响必要性讨论，不影响算术 |
| addon_not_worth_it | 凑单反而多花 | 加凑单品后 310 元 > 单买 280 元 |
| promo_expired | 活动已过期 | 评估时点在活动结束之后 |
| shipping_known | 运费已知 | 运费计入总付款 |
| missing_essential | 缺每日基本开支 | 天数为 20 也不能自动补默认值 |

## test.jsonl 覆盖矩阵（30 例候选，未冻结）

30 例均为 `CaseInput`，`case_id` 与 dev 不重复；金额一律整数分，`as_of` 一律带时区。
表中只描述输入情形与需要覆盖的边界，不写最终建议；客观标签见 `labels.jsonl`（test 标签另行复核冻结）。

| 案例 ID | 专题 | 情形与关键输入 |
|---|---|---|
| t_exact_budget_daily | 预算恰好边界 | 单买日用品应付 28000 分；可支配 28000 分，两者恰好相等 |
| t_exact_budget_sneakers | 预算恰好边界 | 球鞋满减后应付 65000 分；可支配 65000 分；as_of 恰为活动 valid_from |
| t_over_budget_one_cent | 超预算 | 可支配 27999 分，应付 28000 分，差 1 分 |
| t_over_budget_large_gap | 超预算 | 可支配 5000 分，球鞋满减后应付 65000 分，缺口大 |
| t_over_budget_after_discount | 超预算 | 球鞋满减后应付 65000 分，可支配 45000 分 |
| t_negative_discretionary | 负可支配预算 | 现金 50000 分、必要开支 78000 分、预留 5000 分，可支配为 -33000 分，不能截断为 0 |
| t_missing_cash | 缺字段 | `cash_cents=null`，其余预算字段齐全 |
| t_missing_days | 缺字段 | `days_remaining=null` |
| t_missing_daily_essential | 缺字段 | `daily_essential_cents=null` |
| t_missing_fixed_expenses | 缺字段 | `fixed_expenses_cents=null` |
| t_missing_reserve | 缺字段 | `reserve_cents=null`，不能按 0 处理 |
| t_shipping_unknown_single | 运费未知 | `shipping_cents=null`，单买日用品 |
| t_shipping_unknown_basket | 运费未知 | `shipping_cents=null`，纸巾+日用品合单 |
| t_shipping_zero_known | 运费为 0 | `shipping_cents=0`，与未知运费区分 |
| t_shipping_positive_single | 运费正数 | 运费 800 分计入总付款 |
| t_shipping_positive_sneakers | 运费正数 | 运费 1500 分，叠加球鞋满减 |
| t_promo_expired_late | 优惠已过期 | as_of 2026-12-10，晚于 valid_to |
| t_promo_expired_boundary | 优惠已过期 | as_of 恰为 valid_to 2026-12-01T00:00:00+08:00，半开区间外 |
| t_promo_not_started_early | 优惠未开始 | as_of 2026-10-25，早于 valid_from |
| t_promo_not_started_boundary | 优惠未开始 | as_of 2026-10-31T23:59:59+08:00，早于有效期 1 秒 |
| t_threshold_short_no_candidate | 门槛不足 | 日用品单买 28000 分 < 门槛 30000 分，且没有凑单候选 |
| t_threshold_short_with_addon | 门槛不足 | 高价凑单品 8000 分 + 纸巾 2500 分 = 10500 分 < 门槛 30000 分 |
| t_addon_cheaper_than_single | 凑单省钱 | 日用品+纸巾单笔应付 25500 分，单买日用品 28000 分 |
| t_addon_cheaper_with_shipping | 凑单省钱 | 日用品+纸巾 25500 分 + 运费 1000 分，单买为 29000 分 |
| t_addon_more_expensive | 凑单多花 | 日用品+高价凑单品应付 31000 分，单买日用品 28000 分 |
| t_addon_more_expensive_sneakers | 凑单多花 | 球鞋+日用品应付 93000 分，单买球鞋 65000 分 |
| t_owned_similar_sneakers | 已有相似物品 | `owned_similar_items` 有两双同类鞋；只影响必要性讨论，不改算术 |
| t_owned_similar_daily | 已有相似物品 | 已囤纸巾与洗衣液，仍提出补日用品需求 |
| t_zero_days | 零天数 | `days_remaining=0`，每日开支仍显式给 4000 分，不得自动补默认值 |
| t_zero_reserve | 零预留 | `reserve_cents=0` 与 `null` 区分，不能当作缺失 |

覆盖统计（按专题，合计 30）：预算恰好边界 2、超预算 3（1 分差、大额缺口、满减后仍超各 1）、
负可支配预算 1、缺字段 5（五个预算字段各 1）、运费 5（未知 2、0 元 1、正数 2）、
优惠时点 4（已过期 2、未开始 2）、门槛不足 2（其中 1 例无凑单候选）、凑单省钱 2、凑单多花 2、
已有相似物品 2、零天数 1、零预留 1。紧迫程度 low 9 / medium 13 / high 8，三档全覆盖。

其它约定：

- 商品与活动只取自 `data/catalog/` 的 4 个商品与 2 条满减活动快照；不引入快照外商品。
- 活动有效期按半开区间 `[valid_from, valid_to)`；矩阵中的两个边界时点专门验证这个语义。
- 凑单候选满足 `target` 不出现在 `needed_addon_ids`、≤8 个、不重复、均为用户确认确实需要。
- 数值与时点与 dev 不重复；同场景换数字/时点，避免只记住 dev 答案。
- test 集不依赖离线 demo fixture；demo 模式跑不通属预期，正式评测必须用正式实现。

## test.jsonl 冻结流程（候选，仍待人工复核）

1. 起草：E 提交 30 例候选输入与本节矩阵（当前状态：**候选，未冻结**）。
2. 独立复核：至少两人分别复核，复核人不得只看矩阵结论，须逐例自己复算：
   - `essential = days_remaining × daily_essential_cents + fixed_expenses_cents`；
   - `discretionary = cash_cents - essential - reserve_cents`（可为负，不截断）；
   - 优惠是否在 `[valid_from, valid_to)` 内、门槛是否达到、应付是否含运费；
   - 缺字段是否为 `null` 而非 0；凑单候选约束是否成立。
3. 记录：复核人、复核日期、冻结 commit 三项必须留档，不得只口头确认；逐例参考算术与工作表见 [review_sheet.md](review_sheet.md)（复核人先自己复算，再对照参考列）。
4. 冻结：冻结后不再改数值；如确需修正，说明原因并重新走两人复核。
5. test 标签另行冻结：`labels.jsonl` 中的 test 部分由人工独立填写并复核，
   在模型输入、提示词、界面或证据中一律不得出现；评测程序只在算分时读取。

| 记录项 | 值 |
|---|---|
| 复核人 1 | 待填（A—E 成员标识） |
| 复核日期 1 | 待填（实际日期） |
| 复核人 2 | 待填 |
| 复核日期 2 | 待填（实际日期） |
| 冻结 commit | 待填（由 A 合并后给出完整 hash） |
| 冻结后状态 | 待填（frozen / 修正记录） |

## labels.jsonl 格式

每行一个 JSON 对象，以 `case_id` 关联案例；当前 40 行全部为
`review_status=draft`、`reviewers=[]` 的草案，人工复核后改为 `reviewed`
并填写复核人与日期。`--allow-draft-labels` 只允许本地自测，不能用于正式成绩。

```json
{"case_id": "tissue_buy", "review_status": "draft", "reviewers": [], "reviewed_at": null,
 "budget": {"essential_total_cents": 80000, "discretionary_cents": 30000,
            "remaining_cash_cents": 94500, "within_budget": true, "missing_fields": []},
 "offer": {"feasible": true, "optimal_payable_cents": 25500,
           "optimal_basket_ids": ["daily_goods", "tissue"],
           "optimal_rule_ids": ["daily-50"], "baseline_payable_cents": 28000,
           "shipping_cents": 0},
 "reference_action": "buy",
 "notes": "人工复算：280+25=305 元，满 300 减 50，总付款 255 元；单买 280 元。"}
```

标签只记录客观项：预算三值与 `within_budget`、缺失字段、最优总付款与购物篮/规则、
优惠可行性、未知项。`reference_action` 仅作参考，不把“买不买”当作唯一真值。

两条约定（2026-11-20 由独立复算统一，见 `evaluation/verify_labels.py`）：

- **缺预算字段**：只计算依赖齐全字段的结果，其余为 `null`；`missing_fields` 非空、期望 `need_info`。
- **运费未知**：方案未确认，`optimal_payable_cents`、`baseline_payable_cents`、`shipping_cents` 为 `null`，
  `optimal_basket_ids` 与 `optimal_rule_ids` **留空**，`unknowns=["运费未知"]`，期望 `need_info`。
  购物篮不是可判定项，评测的购物篮指标也不因此扣分。

## 复核与冻结要求

- 至少两人独立复核 `test.jsonl` 与标签，并记录复核人、实际日期与冻结 commit。
- **程序复算不等于人工复核**：2026-11-20 E 用独立实现（`python -m evaluation.verify_labels`）
  对 40 条标签复算，结果 40/40 一致（此前 `unknown_shipping` 的购物篮/规则与 test 约定不一致，已统一）。
  这只能作为复核前的自检记录，`review_status` 仍为 `draft`，不替代两位组员的独立复算与签字。
- 不能用 C 的求解器给自己生成标准答案；可以事后用求解器交叉核对。
- `labels.jsonl` 的 30 条 test 标签是 E 按契约公式整理的**草案**，同样须两人独立复算；
  逐例参考值与复核工作表见 [review_sheet.md](review_sheet.md)，给第二位复核人的操作说明见 [reviewer_instructions.md](reviewer_instructions.md)。
- 新案例不支持离线 fixture 是正常现象；正式评测必须使用正式实现，不得用演示数据凑成绩。
