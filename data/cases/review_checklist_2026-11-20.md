# 30 例冻结测试集复核速查单（E 生成，2026-11-20）

> **用法**：复核人先按 [复核工作表](review_sheet.md) 的公式**自己算**，再对照本表期望列；
> 一致就在最后一列打勾，不一致写进 [review_sheet.md](review_sheet.md) 的复核记录。
> **期望列直接取自 [labels.jsonl](labels.jsonl) 的 draft 草案**，不是人工已确认结论；
> 照着抄不算复核，也不会让正式评测出成绩。金额已换算成**元**（标签内部存**分**）。
> 两位复核人签字后，再按 [reviewer_instructions.md](reviewer_instructions.md) 执行收尾命令。

公式：essential = 天数 × 每日基本开支 + 固定支出；discretionary = 现金 − essential − 预留（可为负）；
应付 = 购物篮原价 − 适用满减 + 运费（门槛只算参与商品原价，运费不参与）；运费未知或缺预算字段 → 应付 None、期望 need_info。

| # | case_id | 现金 / 天数 / 每日 / 固定 / 预留（元） | 目标 · 候选 · 运费 · 时点 | 期望 essential / 可支配 | 期望 应付 / 篮 / 规则 | 动作 | 复核 |
|---|---|---|---|---|---|---|---|
| 1 | t_exact_budget_daily | 1300 / 25 / 40 / 0 / 20 | daily_goods · 无 · 0 · 2026-11-10 | 1000 / 280 | 280 / daily_goods / — | buy | ☐ |
| 2 | t_exact_budget_sneakers | 2000 / 30 / 40 / 50 / 100 | sneakers · 无 · 0 · 2026-11-01 | 1250 / 650 | 650 / sneakers / shoes-150 | buy | ☐ |
| 3 | t_over_budget_one_cent | 999.99 / 20 / 25 / 20 / 200 | daily_goods · 无 · 0 · 2026-11-08 | 520 / 279.99 | 280 / daily_goods / — | wait | ☐ |
| 4 | t_over_budget_large_gap | 1000 / 40 / 20 / 0 / 150 | sneakers · 无 · 0 · 2026-11-14 | 800 / 50 | 650 / sneakers / shoes-150 | wait | ☐ |
| 5 | t_over_budget_after_discount | 1250 / 20 / 35 / 0 / 100 | sneakers · 无 · 0 · 2026-11-09 | 700 / 450 | 650 / sneakers / shoes-150 | wait | ☐ |
| 6 | t_negative_discretionary | 500 / 30 / 25 / 30 / 50 | tissue · 无 · 0 · 2026-11-11 | 780 / -330 | 25 / tissue / — | wait | ☐ |
| 7 | t_missing_cash | —（缺 cash_cents） / 22 / 38 / 12 / 150 | daily_goods · 无 · 0 · 2026-11-13 | 848 / None | None / — / — | need_info | ☐ |
| 8 | t_missing_days | 1500 / 缺失 / 40 / 0 / 100 | daily_goods · 无 · 0 · 2026-11-15 | None / None | None / — / — | need_info | ☐ |
| 9 | t_missing_daily_essential | 1500 / 18 / —（缺 daily_essential_cents） / 0 / 120 | daily_goods · 无 · 0 · 2026-11-16 | None / None | None / — / — | need_info | ☐ |
| 10 | t_missing_fixed_expenses | 1500 / 20 / 40 / —（缺 fixed_expenses_cents） / 100 | daily_goods · 无 · 0 · 2026-11-18 | None / None | None / — / — | need_info | ☐ |
| 11 | t_missing_reserve | 1400 / 24 / 40 / 0 / —（缺 reserve_cents） | daily_goods · 无 · 0 · 2026-11-20 | 960 / None | None / — / — | need_info | ☐ |
| 12 | t_shipping_unknown_single | 1600 / 25 / 40 / 0 / 200 | daily_goods · 无 · 未知 · 2026-11-17 | 1000 / 400 | 未知 / — / — | need_info | ☐ |
| 13 | t_shipping_unknown_basket | 1800 / 30 / 35 / 50 / 100 | tissue · daily_goods · 未知 · 2026-11-19 | 1100 / 600 | 未知 / — / — | need_info | ☐ |
| 14 | t_shipping_zero_known | 1520 / 25 / 35 / 25 / 120 | daily_goods · 无 · 0 · 2026-11-03 | 900 / 500 | 280 / daily_goods / — | buy | ☐ |
| 15 | t_shipping_positive_single | 1500 / 26 / 40 / 20 / 100 | daily_goods · 无 · 8 · 2026-11-22 | 1060 / 340 | 288 / daily_goods / — | buy | ☐ |
| 16 | t_shipping_positive_sneakers | 2000 / 20 / 35 / 0 / 200 | sneakers · 无 · 15 · 2026-11-25 | 700 / 1100 | 665 / sneakers / shoes-150 | buy | ☐ |
| 17 | t_promo_expired_late | 1400 / 20 / 40 / 0 / 150 | daily_goods · tissue · 0 · 2026-12-10 | 800 / 450 | 280 / daily_goods / — | buy | ☐ |
| 18 | t_promo_expired_boundary | 1800 / 20 / 40 / 0 / 100 | sneakers · 无 · 0 · 2026-12-01 | 800 / 900 | 800 / sneakers / — | buy | ☐ |
| 19 | t_promo_not_started_early | 1600 / 25 / 38 / 10 / 140 | daily_goods · tissue · 0 · 2026-10-25 | 960 / 500 | 280 / daily_goods / — | buy | ☐ |
| 20 | t_promo_not_started_boundary | 1900 / 30 / 40 / 0 / 200 | sneakers · 无 · 0 · 2026-10-31 | 1200 / 500 | 800 / sneakers / — | wait | ☐ |
| 21 | t_threshold_short_no_candidate | 1400 / 20 / 40 / 0 / 200 | daily_goods · 无 · 0 · 2026-11-06 | 800 / 400 | 280 / daily_goods / — | buy | ☐ |
| 22 | t_threshold_short_with_addon | 1200 / 20 / 35 / 0 / 150 | large_addon · tissue · 0 · 2026-11-23 | 700 / 350 | 80 / large_addon / — | buy | ☐ |
| 23 | t_addon_cheaper_than_single | 1500 / 25 / 35 / 25 / 100 | daily_goods · tissue · 0 · 2026-11-05 | 900 / 500 | 255 / daily_goods、tissue / daily-50 | buy | ☐ |
| 24 | t_addon_cheaper_with_shipping | 1300 / 24 / 35 / 0 / 160 | daily_goods · tissue · 10 · 2026-11-19 | 840 / 300 | 265 / daily_goods、tissue / daily-50 | buy | ☐ |
| 25 | t_addon_more_expensive | 1400 / 22 / 35 / 20 / 110 | daily_goods · large_addon · 0 · 2026-11-13 | 790 / 500 | 280 / daily_goods / — | buy | ☐ |
| 26 | t_addon_more_expensive_sneakers | 2600 / 30 / 40 / 0 / 300 | sneakers · daily_goods · 0 · 2026-11-16 | 1200 / 1100 | 650 / sneakers / shoes-150 | buy | ☐ |
| 27 | t_owned_similar_sneakers | 2200 / 30 / 40 / 0 / 200 | sneakers · 无 · 0 · 2026-11-24 | 1200 / 800 | 650 / sneakers / shoes-150 | buy | ☐ |
| 28 | t_owned_similar_daily | 1420 / 20 / 40 / 0 / 220 | daily_goods · 无 · 0 · 2026-11-21 | 800 / 400 | 280 / daily_goods / — | buy | ☐ |
| 29 | t_zero_days | 400 / 0 / 40 / 0 / 50 | daily_goods · 无 · 0 · 2026-11-26 | 0 / 350 | 280 / daily_goods / — | buy | ☐ |
| 30 | t_zero_reserve | 1250 / 20 / 40 / 20 / 0 | daily_goods · 无 · 0 · 2026-11-27 | 820 / 430 | 280 / daily_goods / — | buy | ☐ |

## 复核要点（逐例都要过一遍）

- [ ] 五个预算字段任一缺失时没有当成 0；days_remaining=0 与预留 0 元分别成立。
- [ ] discretionary 负值保留，没有截断成 0。
- [ ] 活动按半开区间：开始当天生效、截止当天不生效、开始前 1 秒不生效。
- [ ] 满减门槛按参与商品原价；运费既不参与门槛也不被减免，最后加上。
- [ ] 运费未知 → 应付 None；缺预算字段 → within_budget=None，期望 need_info。
- [ ] 并列最优按「付款额 → 凑单件数 → basket_ids → rule_ids」字典序选择。
- [ ] 题目里没有答案字段；标签不进入模型输入。

## 复核签字（两人独立，缺一不可）

| 复核人（A—E 标识） | 独立复算日期 | 是否有分歧 | 签字 |
|---|---|---|---|
|  |  |  |  |
|  |  |  |  |

> 签字后由 E 执行收尾命令（见 [reviewer_instructions.md](reviewer_instructions.md)），只把 draft 改为 reviewed 并写复核人/日期，不修改任何金额。
