# B · 预算与理性分析

先读 README 与 contracts.md。主责文件：`tools/budget.py`、`agents/rational.py`、
`prompts/rational.md`、`tests/test_budget.py`。不要修改 demo.py 来完成正式任务。

## 第一项任务：预算函数

```python
calculate_budget(profile: UserProfile, payable_cents: int | None = None) -> BudgetResult
```

输入示例：现金 120000 分、20 天、每日 4000 分、固定支出 0、预留 10000 分。
预期基本支出 80000 分，可支配 30000 分。
未给付款额时 remaining_cash/within_budget 为 None；付款 65000 分时，
购买后现金 55000 分，within_budget=false。付款 30000 分时恰好通过。

关键行为：
- 任何必填预算字段缺失，都列入 missing_fields；不要自动补零。
- 可支配金额可以为负，剩余天数可以为 0，明确给定的零预留金有效。
- 不原地修改输入；函数不调用模型、不读 .env、不查商品。
- 金额和天数已由公共模型校验；不要悄悄改单位。

运行 `uv run pytest tests/test_budget.py`。初始测试有严格 xfail 标记，表示正式实现尚缺。
实现后移除对应标记和不再需要的导入，让这些案例成为普通通过的测试。

## 第二项任务：理性角色

`run(context: RoleContext, model: ModelClient) -> Argument`，输出 role=rational。
可复用 `agents.base.call_role("rational", context, model, Argument)`，然后检查角色与引用。
你的策略要分析必要性、替代选择、重复购买和机会成本；不能只重复预算数字。
初次理性发言发生在优惠方案之前，within_budget=None 是正常状态，不可声称已复核付款。
后续一轮回应由 D 组织，可针对最终报价补充观点。

引用：`input:profile`、`input:request`、`budget:initial`、`product:<id>`。
缺少某类个人偏好时用 unknowns 说明；不要把模型估计当确定预算。

## 协作与验收

A 调用你的预算两次；D 使用结果做最终校验；C 请你协助独立复算小规模优惠样例。
预算函数不依赖其他成员即可开发。角色可用 FakeModel 测试 JSON 契约，真实样例由 A 提供连接。

验收：正常、恰好够、负预算、固定支出、零预留、零天数、缺字段与最终付款复算均正确；
理性观点引用真实证据，无自算或编造金额。
报告提交：预算公式、边界表、理性策略和独立复核记录；展示一个超预算案例。
