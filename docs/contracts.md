# 接口契约 v0.1（所有成员必读）

权威定义为 `src/budget_agent/schemas.py`。本页说明语义；接口变更由 A 协调。
模型不得直接写金额、来源或预算字段覆盖工具输出。

## 通用约定

- 金额是严格整数分，拒绝浮点、字符串金额和 bool。显示时才转元。
- 不知道的数字用 None；已确认没有支出才填 0。负可支配预算不能截断。
- 时间含时区，输入示例 `2026-11-07T16:00:00+08:00`，记录时间用 UTC。
- Pydantic 拒绝未声明字段。列表和字典使用 default_factory，避免共享状态。
- 目标商品必选；最多 8 个不重复的凑单候选，每个最多一件，均已由用户确认需要。
- 第一版同商家单订单，固定价格与固定运费，不处理跨店、退款或动态运费。

## 公共调用

| 接口 | 负责人 | 输入 → 输出 |
|---|---|---|
| `run_case(case, config, services=None)` | A | CaseInput → RunRecord |
| `calculate_budget(profile, payable_cents=None)` | B | UserProfile、可选付款额 → BudgetResult |
| `search_products(query, limit=5, *, data_dir)` | C | 查询 → list[Product] |
| `get_products(product_ids, *, data_dir)` | C | 精确 ID → list[Product] |
| `get_promotion_rules(product_ids, as_of, *, data_dir)` | C | 商品和时点 → list[PromotionRule] |
| `optimize_basket(request)` | C | OptimizationInput → OfferResult |
| `desire/rational.run(context, model)` | D/B | RoleContext → Argument |
| `deal.run(context, model, tools)` | D | RoleContext → DealResult |
| `judge.run(context, model)` | D | RoleContext → DecisionProposal |
| `cross_response.run(context, model)` | D | RoleContext → list[Argument]，最多一轮 |
| `apply_decision_policy(proposal, context)` | D | 原始建议 → (Decision, list[str] 调整原因) |

`data_dir` 是程序注入的关键字参数，不暴露给模型。工具注册时参数和返回类型都校验。
新增工具须由 A 显式注册并补齐参数模型。不能由模型传文件路径、函数代码或任意 URL 执行。
完整调用示例见 `demo.run_demo_deal()`；正式模块不要导入 demo。

## 预算的两次计算

```text
essential = days_remaining * daily_essential_cents + fixed_expenses_cents
discretionary = cash_cents - essential - reserve_cents
remaining_cash = cash_cents - payable_cents
within_budget = remaining_cash >= essential + reserve_cents
```

第一次 `payable_cents=None`：可以计算 essential/discretionary；
remaining_cash 和 within_budget 必须是 None。
第二次传最终 OfferResult.payable_cents，不能使用标价或单买基准。
任一必填预算字段缺失，返回 missing_fields，未能可靠计算的结果均为 None。
所有关键字段都必须明确提供，即使剩余天数为 0 也不自动补每日开支。

## 优惠规则的计算顺序（C/D 共同遵守）

1. 活动有效时间为半开区间 `[valid_from, valid_to)`；商品与活动商家须一致。
2. 枚举候选子集；对每个篮子枚举不使用优惠、一次满减、一张券和合法组合。
3. 满减先算：门槛按参与商品原价之和，达到门槛才生效。
4. 优惠券后算。`original_eligible` 按券参与商品原价；
   `after_reduction_eligible` 需分摊满减后再检查券门槛。
5. 当满减参与商品不同于券参与商品，满减按参与商品价格比例分摊为整数分：
   先取各项比例的向下整数分，剩余分按“小数余数降序、商品 ID 升序”分配。
   每件分摊不得超过该件原价。用整数除法与余数实现，避免浮点不一致。
6. 同时使用两条活动需双方 stackable=true；最多各一种活动一条。
   每一步减免不能超过对应参与商品当时可减金额。
7. 运费不参与门槛、不被优惠减免，最后加上。未知运费返回未确认方案，不能设零。
8. 单买基准也需枚举合法优惠。最终比较总付款，不比较券面值。
9. 并列最优按“付款额、凑单件数、basket_ids 排序后的字典序、rule_ids 排序后的字典序”选择。

这是项目自定义的有限规则，不代表所有真实商家的结算机制。
遇到无法映射的真实规则应返回 unknowns，不把本规则假装成平台规则。
如果上述分摊导致 C 的工作量超期，应在实现前由 A 协调收缩支持范围，并同步模型与测试。

## OfferResult 与证据

`subtotal - discount + shipping = payable`。商品缺失、规则未知、活动过期或
运费未知，不能 verified=true。`baseline_payable_cents` 为只买目标商品时的最优总付款。
`excluded_reasons` 记录跳过的规则或方案理由，避免返回一个无法解释的数字。
折扣为零也是合法方案；没有可用优惠不等于没有可行方案。

来源字段与采集时间在 Product/PromotionRule 中保留，展示数据必须 is_demo=true。
D 的 DealResult 返回实际使用的规则证据和 `offer:chosen`；引用 ID 必须能在证据表找到。
基础 policy 检查引用存在性和算术，不验证论点的语义支持程度；D/E 仍需补充检查与人工抽查。

## 未完成与异常

未实现函数抛 `ModuleNotReady`，不要返回占位成功对象。
缺少用户信息属于可处理业务状态，用 missing_fields/unknowns 表达。
模型格式错误由 ModelClient 最多重试一次；模型调用/HTTP 错误不写服务响应正文。
禁止在记录、异常和提示词里加入 API 密钥。
