# D · 多角色协作与最终决策

B 负责 rational；C 负责优惠求解；A 负责模型适配和总控。
先取得最新仓库，阅读 [总体结构](../common/overview/README.md)、
[系统流程图](../common/overview/flowcharts.md) 和 [接口约定](../common/contracts.md)，再按本文开发。

## 需要完成的文件

以下路径相对于项目根目录。先跑通欲望、优惠与裁判节点，再补交叉回应和完整校验。

| 文件 | 当前状态 | D 要完成什么 |
|---|---|---|
| [src/budget_agent/agents/desire.py](../../src/budget_agent/agents/desire.py) | **待实现**，目前为占位函数 | 根据需求、偏好和商品事实生成购买价值观点与证据引用 |
| [src/budget_agent/agents/deal.py](../../src/budget_agent/agents/deal.py) | **待实现**，目前为占位函数 | 选择并调用 C 的工具、必要时补查、返回方案与证据，控制终止 |
| [src/budget_agent/agents/judge.py](../../src/budget_agent/agents/judge.py) | **待实现**，目前为占位函数 | 综合论点与最终预算，输出原始建议、反方观点和下一步 |
| [src/budget_agent/agents/cross_response.py](../../src/budget_agent/agents/cross_response.py) | **待实现**，当前关闭 | 完成有依据的一轮回应，与 A 配合启用 |
| [src/budget_agent/prompts/desire.md](../../src/budget_agent/prompts/desire.md) | 已有起始提示词，**待完善** | 明确购买价值、偏好、事实和未知项的表达要求 |
| [src/budget_agent/prompts/deal.md](../../src/budget_agent/prompts/deal.md) | 已有起始提示词，**待完善** | 明确工具选择协议、补查条件和停止条件 |
| [src/budget_agent/prompts/judge.md](../../src/budget_agent/prompts/judge.md) | 已有起始提示词，**待完善** | 明确取舍、引用、信息不足和建议结构 |
| [src/budget_agent/decision_policy.py](../../src/budget_agent/decision_policy.py) | 已有最低保护，**待扩展** | 补充论点与证据内容一致性、必要性策略和失败处理，保留否决原因 |
| [tests/test_decision_policy.py](../../tests/test_decision_policy.py) | 已有基础检查，**待补充** | 为新增保护补必要案例，并和 A 通过工作流检查确认端到端约束 |

C 负责计算最优优惠金额，D 负责怎样调用计算工具。理性角色及其提示词由 B 完成。

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
