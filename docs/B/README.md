# B · 预算与理性分析

先取得最新仓库，阅读 [总体结构](../common/overview/README.md)、
[系统流程图](../common/overview/flowcharts.md) 和 [接口约定](../common/contracts.md)，再按本文开发。

## 需要完成的文件

以下路径相对于项目根目录。先实现预算，再实现理性角色；正式任务在这些文件中完成。

| 文件 | 当前状态 | B 要完成什么 |
|---|---|---|
| [src/budget_agent/tools/budget.py](../../src/budget_agent/tools/budget.py) | **待实现**，目前为占位函数 | 写预算公式、缺字段处理、最终付款复核，保留负可支配金额 |
| [src/budget_agent/agents/rational.py](../../src/budget_agent/agents/rational.py) | **待实现**，目前为占位函数 | 接入模型，分析必要性、替代与机会成本，引用预算和其他证据 |
| [src/budget_agent/prompts/rational.md](../../src/budget_agent/prompts/rational.md) | 已有起始提示词，**待完善** | 补齐理性策略、未知信息处理和输出要求 |
| [tests/test_budget.py](../../tests/test_budget.py) | 已有验收起点，当前严格 xfail | 实现预算后移除对应标记，补足必要边界，确保测试真正通过 |

`demo.py` 是独立演示替身，修改它不会完成 B 的正式任务。

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
