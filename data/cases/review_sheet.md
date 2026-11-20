# 冻结复核工作表（E 组织，至少两人独立复算）

> 用途：两位复核人**不要看本表的结论列**，先按公式自己算，
> 再把结果与「参考」列对照；分歧写入「复核记录」。
> 本表与 [标签草案](labels.jsonl) 依据 [接口契约](../../docs/common/contracts.md) 的公式整理。
> 2026-11-18 集成检查修正了 `t_missing_cash`、`t_missing_reserve` 的基本支出标签与本表；
> 开发集 `missing_profile` 同步修正。原“30/30 条客观字段一致”的结论不再沿用。
> 新增的独立公式回归检查全部 40 条基本支出，不验证优惠最优性；未调用 C 求解器或学校模型。
> **这不是两位组员的人工复核，也不是模型准确率。**
> 两位复核人必须独立复算并修正草案后，才能把 `review_status` 改为 `reviewed`；
> 复核通过后再填写本文件末尾的冻结记录。
> 金额单位均为**分**，时间均为 `+08:00`，活动有效期半开区间
> `[2026-11-01, 2026-12-01)`。

## 参考公式

```text
essential      = days_remaining × daily_essential_cents + fixed_expenses_cents
discretionary  = cash_cents − essential − reserve_cents      （可为负，不截断）
单买基准       = 目标商品最优合法总付款（含运费）
方案总付款     = 购物篮原价 − 适用满减 + 运费
优惠            = 有效期内、同商家、达到门槛；两条满减不可叠加，取更优者
并列最优        = 付款额 → 凑单件数 → basket_ids 字典序 → rule_ids 字典序
运费未知        = 应付总额 None，feasible=None，期望 need_info；最优购物篮/规则留空（方案未确认，不作评分项）
缺任一预算字段  = missing_fields 列出缺项，依赖该字段的结果为 None，期望 need_info
基本支出         = 只依赖天数、每日基本开支、固定支出；现金/预留金缺失不影响 essential
缺字段提前停止   = 未调用方案求解，discretionary/remaining_cash/within_budget 无法确认
```

商品：`sneakers=80000`、`daily_goods=28000`、`tissue=2500`、`large_addon=8000`。
活动：`shoes-150`（球鞋满 70000 减 15000）、`daily-50`
（日用品/纸巾/高价凑单品参与商品满 30000 减 5000）。

## 逐例参考值

| case_id | essential | discretionary | 应付 | 最优购物篮 | 规则 | 备注 |
|---|---:|---:|---:|---|---|---|
| t_exact_budget_daily | 100000 | 28000 | 28000 | daily_goods | — | 恰好边界 |
| t_exact_budget_sneakers | 125000 | 65000 | 65000 | sneakers | shoes-150 | as_of 恰为 valid_from（左闭） |
| t_over_budget_one_cent | 52000 | 27999 | 28000 | daily_goods | — | 差 1 分 |
| t_over_budget_large_gap | 80000 | 5000 | 65000 | sneakers | shoes-150 | 大额缺口 |
| t_over_budget_after_discount | 70000 | 45000 | 65000 | sneakers | shoes-150 | 满减后仍超 |
| t_negative_discretionary | 78000 | -33000 | 2500 | tissue | — | 不可截断为 0 |
| t_missing_cash | 84800 | None | None | — | — | missing=cash_cents，不影响基本支出 |
| t_missing_days | None | None | None | — | — | missing=days_remaining |
| t_missing_daily_essential | None | None | None | — | — | missing=daily_essential_cents |
| t_missing_fixed_expenses | None | None | None | — | — | missing=fixed_expenses_cents |
| t_missing_reserve | 96000 | None | None | — | — | missing=reserve_cents，不影响基本支出 |
| t_shipping_unknown_single | 100000 | 40000 | None | — | — | 运费未知 |
| t_shipping_unknown_basket | 110000 | 60000 | None | — | — | 运费未知 |
| t_shipping_zero_known | 90000 | 50000 | 28000 | daily_goods | — | 0 ≠ 未知 |
| t_shipping_positive_single | 106000 | 34000 | 28800 | daily_goods | — | 运费 800 |
| t_shipping_positive_sneakers | 70000 | 110000 | 66500 | sneakers | shoes-150 | 运费 1500，不参与门槛 |
| t_promo_expired_late | 80000 | 45000 | 28000 | daily_goods | — | 活动失效 |
| t_promo_expired_boundary | 80000 | 90000 | 80000 | sneakers | — | as_of 恰为 valid_to（右开） |
| t_promo_not_started_early | 96000 | 50000 | 28000 | daily_goods | — | 活动未开始 |
| t_promo_not_started_boundary | 120000 | 50000 | 80000 | sneakers | — | valid_from 前 1 秒 |
| t_threshold_short_no_candidate | 80000 | 40000 | 28000 | daily_goods | — | 无候选，未满门槛 |
| t_threshold_short_with_addon | 70000 | 35000 | 8000 | large_addon | — | 仅买目标最优；候选仍不足门槛 |
| t_addon_cheaper_than_single | 90000 | 50000 | 25500 | daily_goods+tissue | daily-50 | 省 2500 |
| t_addon_cheaper_with_shipping | 84000 | 30000 | 26500 | daily_goods+tissue | daily-50 | 运费不参与门槛 |
| t_addon_more_expensive | 79000 | 50000 | 28000 | daily_goods | — | 加购 31000 > 单买 |
| t_addon_more_expensive_sneakers | 120000 | 110000 | 65000 | sneakers | shoes-150 | 跨规则不叠加 |
| t_owned_similar_sneakers | 120000 | 80000 | 65000 | sneakers | shoes-150 | 已有物品不改算术 |
| t_owned_similar_daily | 80000 | 40000 | 28000 | daily_goods | — | 同上 |
| t_zero_days | 0 | 35000 | 28000 | daily_goods | — | days=0 仍显式给每日开支 |
| t_zero_reserve | 82000 | 43000 | 28000 | daily_goods | — | reserve=0 ≠ null |

## 复核人必须逐例确认

- [ ] 五个预算字段任一为 `null` 时，没有把缺失当 0；`days_remaining=0` 与 0 元预留也分别成立。
- [ ] `discretionary` 的负值保留，没有截断。
- [ ] 活动按半开区间判定；`valid_from` 生效、`valid_to` 不生效、开始前 1 秒不生效。
- [ ] 满减门槛按**参与商品原价**计算；运费不参与门槛、不被减免、最后加上。
- [ ] 运费未知时没有给出应付额；缺字段时 `within_budget=None`。
- [ ] 并列最优按契约顺序选择；单买基准也枚举合法优惠。
- [ ] 案例不含标签/答案字段；标签不进入模型输入。

## 2026-11-20 程序复算记录（**不是**人工复核）

E 用独立实现（不调用 C 的求解器、不读 C 的 catalog/promotions 模块，只用
`data/catalog/` 快照与本文公式）对 40 条标签做了一次全字段复算：

```bash
python -m evaluation.verify_labels          # 共 40 例，一致 40 例
python -m evaluation.verify_labels --json   # 机器可读，可直接贴进报告附录
```

| 项目 | 结果 |
|---|---|
| 覆盖 | dev 10 例 + test 30 例，逐字段比对（预算四值、missing_fields、offer 六项、reference_action） |
| 结果 | **40/40 一致** |
| 顺带修正 | 开发集 `unknown_shipping` 原来填了购物篮/规则，与 test 的「未确认方案留空」约定不一致；已统一为留空，并同步 `evaluation/metrics.py`：标签应付额为 `null` 时购物篮不作评分项 |
| 性质 | **机器复算，不是两位组员的人工复核**；`review_status` 仍为 `draft` |

> 结论：草案数值经独立实现复算后没有发现算术错误，可以放心作为人工复核的对照；
> 但「两人独立复算 + 签字」这一步没有因此完成，正式评测仍会拒绝出成绩。

## 冻结记录（复核后人工填写）

| 项目 | 复核人 1 | 复核人 2 |
|---|---|---|
| A—E 标识 | TODO | TODO |
| 实际复核日期 | TODO | TODO |
| 发现的分歧 / 修正 | TODO | TODO |
| 确认结论 | TODO（同意冻结 / 需修正） | TODO |

| 冻结 commit | 冻结日期 | 标签文件 SHA-256 | 备注 |
|---|---|---|---|
| TODO | TODO（实际日期） | TODO | 由 A 或 E 记录已冻结数据所对应的完整 commit |

> 不能让 C 的求解器给自己出标准答案；本表只作人工复核参考，
> 复核完成后 `test` 标签另行写入 `labels.jsonl` 并把 `review_status` 改为 `reviewed`。
