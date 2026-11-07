# C · 数据与优惠求解

主责 `tools/catalog.py`、`promotions.py`、`optimizer.py`、`data/catalog/`、
`tests/test_optimizer.py`。先读 contracts.md，尤其优惠顺序与整数分摊约定。

## 推荐开发顺序

1. 读取 JSON，用 Product/PromotionRule 验证；完成 get_products、search_products。
2. 完成活动按商品、商家和 `[valid_from, valid_to)` 过滤。
3. 完成只买目标商品的最优合法优惠。
4. 穷举最多 8 个候选的 256 个子集，比较实际总付款。
5. 补齐叠加、参与商品差异、运费、分摊和并列解。

`optimize_basket(request: OptimizationInput) -> OfferResult` 是纯计算函数，
所有商品、规则、时点、运费和候选从 request 进入；不要隐式读文件或调用模型。
data_dir 由 A 注入到数据工具，不属于模型参数。

## 必须能人工复算的案例

| 目标/规则/候选 | 预期 |
|---|---|
| 280 元目标，满 300 减 50，无候选、零运费 | 单买 280 元 |
| 同上，确认需要的 25 元纸巾 | 总付 255 元，单买基准 280 元 |
| 同上，确认需要的 80 元商品 | 选择单买 280 元；凑单实际需付 310 元 |
| 同上，运费未知 | 不得返回已确认到手价 |
| 规则恰好过期 | 不使用过期优惠，允许原价方案 |
| 两活动互斥 | 不得同时应用 |

初始测试只提供部分案例，且正式函数带严格 xfail。完成后移除标记，
再与 B 补充独立预期值；不要把你自己的求解器结果当标准答案。

## 返回结果

需要 subtotal、discount、shipping、payable、baseline、rule_ids、basket_ids、
verified、verification_method、unknowns、excluded_reasons。正式验证完成后使用 solver。
找不到优惠不等于无可行方案，原价单买仍是候选。
目标缺失、规则无法解释或运费未知时明确返回未知或受控错误。
新商品/活动保留来源、采集时间与演示标记；本仓库现有内容全是演示数据。

## 协作与验收

D 决定调用哪些工具、何时补查，你实现工具内部计算；不要重复写 agent 策略。
A 注册工具；B 协助复算；E 组织评测样例。
不依赖 API 即可完成大部分开发。运行 `uv run pytest tests/test_optimizer.py`。

验收：有限穷举有界、规则合法、总支付与基准正确、未知不造数、来源可追溯。
报告提交：规则假设、搜索空间、并列解、独立测试和不支持的真实活动类型。
若复杂优惠来不及，请尽早与 A 收缩协议，不要静默忽略已声明字段。
