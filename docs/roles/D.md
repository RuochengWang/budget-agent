# D · 多角色协作与最终决策

主责 desire/deal/judge/cross_response 角色、相应提示词、decision_policy.py 与决策测试。
B 负责 rational；C 负责优惠求解；A 负责模型适配和总控。先读架构与接口契约。

## 开发顺序

1. 用 `call_role` 完成欲望、裁判的结构化输出与证据 ID 检查。
2. 优惠节点先使用固定合法工具序列跑通，再增加基于中间结果的选择与补查。
3. 扩展最终规则校验，覆盖原始模型建议被否决的情形。
4. 实现最多一轮交叉回应，由 A 开启配置；不能在节点中无限辩论。

欲望输出 Argument(role=desire)；裁判输出 DecisionProposal；
优惠节点返回 DealResult(argument、offer、evidence)。
所有观点简短可展示，不要求或存储内部完整推理。

## 优惠节点接口

```python
run(context: RoleContext, model: ModelClient, tools: ToolRegistry) -> DealResult
```

可调用 get_products/search_products/get_promotion_rules/optimize_basket。
参数定义在 workflow.py；新工具与 A 协调。候选只能取用户确认需要的 IDs。
工具通过 `tools.call(name, arguments)` 执行，调用名和参数需验证，不 eval。
正常流程总共 5 次工具调用，当前全流程上限 6，包含 A 的初算、查询与复算。
补查前检查剩余额度；工具错误后有明确退出，不能反复重试。
返回的规则须转成 `promotion:<id>` 证据；方案为 `offer:chosen`，不能覆盖旧 ID。

离线开发可注入 FakeModel 和演示工具来测衔接，但正式源码不得导入 demo.py。
`demo.run_demo_deal()` 仅作为接口用法参考，不包含自主工具策略。

## 裁判与保护

不做多数票，不改工具金额。必要性与偏好可以权衡，但超预算不得输出购买，
关键条件未知应 need_info。提供最强反方观点与下一步。
基础 decision_policy 已检查引用存在性、购物篮范围、算术、未知条件和预算门槛。
它不是完整的事实验证器；你需补充论点与证据内容匹配、必要性策略和失败测试。
原始建议放 proposed_decision；最终建议放 final_decision；调整理由不得省略。

运行 `uv run pytest tests/test_decision_policy.py tests/test_workflow.py`。
验收：不虚构来源/优惠、拒绝超预算购买、信息不足能结束、错误可追溯、一轮回应有实际信息。
报告提交：角色职责、工具选择逻辑、与固定工作流的区别、校验前后违规和消融解释。
