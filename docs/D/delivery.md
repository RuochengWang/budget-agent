# D 部分交付说明

对应 `docs/D/README.md` 的 9 个文件。所有改动都能在无 API、无 C/B 正式实现的情况下验证。

```bash
uv run pytest tests/test_d_agents.py tests/test_decision_policy.py
```

本机等价命令（未装 uv 时）：

```bash
PYTHONPATH=src python -m pytest tests -q --ignore=tests/test_ui.py
# 当前结果：67 passed, 4 xfailed（xfail 全部来自 C 未完成的求解器）
```

## 一、改动清单

| 文件 | 状态 | 做了什么 | 为什么 |
|---|---|---|---|
| `agents/desire.py` | 实现 | 剔除 `budget` 字段后再发上下文 → 校验 role → 剔除不存在的证据 ID 并写进 `unknowns` | 角色隔离要结构性；编造的引用静默删掉就统计不出「虚构引用率」 |
| `agents/deal.py` | 实现 | 固定序列「查规则 → 求解」+ 额度预留 + 规则/方案入证据表 | 见下面第二节「为什么不交给模型选工具」 |
| `agents/judge.py` | 实现 | `call_role` 取建议 → 剔除伪造证据 ID，剔除记录写进 `next_steps` | 留痕；同时把硬约束判断留给 policy |
| `agents/cross_response.py` | 实现 | 每个角色最多一条，必须回应他人，复读丢弃，证据必须存在 | 结构上不可能无限辩论 |
| `decision_policy.py` | 扩展 | 保留骨架全部检查，新增三项（见第三节） | 骨架缺「内容级」核对与留痕 |
| `prompts/desire.md` `deal.md` `judge.md` | 完善 | 补角色边界、金额禁令、must-not 清单 | 提示词与代码校验一一对应，不是装饰 |
| `prompts/cross_response.md` | 新增 | 交叉回应的输出协议 | 原骨架没有这份提示词 |
| `tests/test_decision_policy.py` | 扩充 | 2 个骨架用例 → 14 个 | 每个新增保护都有对应用例 |
| `tests/test_d_agents.py` | 新增 | 12 个用例，直接测 D 的四个节点 | 总控在 demo 模式下走的是替身，测不到我的模块 |

## 二、两个关键决策

**1. 工具额度必须预留 1 次给 A。**
`ToolRegistry.traces` 是全流程共享的：A 的 `calculate_budget` + `get_products` 各占 1 次，
优惠节点之后 A 还要用最终 `payable_cents` 再算一次预算。默认 `max_tool_calls=6` 时，
D 实际只有 2 次可用（`rules` + `optimize`）。所以 `deal.remaining_calls()` 主动减掉
`RESERVED_FOR_FINAL_BUDGET = 1`，额度不够就抛 `ToolLimitReached` 明确退出。
第 5 次调用是这个设计的直接结果，`test_workflow.py` 里 `len(tool_calls) == 5` 可以印证。

**2. 第一版不让模型选工具。**
候选商品已由用户确认（`needed_addon_ids`），求解器一次穷举就能给出最优解。
让模型「选工具」只会增加调用次数、降低可复现性，还会在额度紧张时把预算花在试探上。
按 `docs/D/README.md` 的开发顺序第 2 条，先固定合法序列跑通；补查留给下一版，
且必须满足「额度尚有余量 + 中间结果确实缺信息」两条，否则带 `unknowns` 退出，不重试。

## 三、`decision_policy.py` 新增的三项

| 检查 | 触发条件 | 处理 |
|---|---|---|
| 论点与证据内容一致性 | `action=buy` 时，`reason_summary` 或角色主张里的「X 元 / X 块 / ¥X」在证据里找不到出处 | 否决 → `need_info` |
| 购买建议缺事实类证据 | `action=buy` 但只引用了 `input:*`（用户自述） | 否决 → `need_info` |
| 无观点 | `action=buy` 且 `context.arguments` 为空 | 否决 → `need_info` |
| 必要性策略 | `action=buy` + `urgency=low` + 已有同类物品 | 只追加 `next_steps`，**不改结论** |
| 保留原始理由 | 任何否决 | `reason_summary` 追加原话，不再整段替换 |

**降级分两级，这是与骨架原实现最大的差别。** 骨架把所有问题一律降成 `need_info`；
D 改成「否决级」与「相关级」：

- 否决级（证据引用不存在、证据重复、预算字段缺失）：任何结论都不成立 → 一律降级；
- 相关级（方案未验证、运费未知、明细不一致、规则未知）：**只有 `buy` 依赖它**。
  模型已经说 `skip`（需求不成立）或 `wait`（现在不行）时，方案验证与否不改变结论，
  此时只记账、不改结论。否则用户会被要求去补一个与"这次不该买"完全无关的运费信息。

**为什么金额检查要放开「差值」**：`offer:chosen` 里的 `subtotal=30500`、`payable=25500`，
"少付 25 元" 这个 2500 只存在于两者之差里。只允许证据里出现过的数值会把正确解释判成编造。
所以允许集合 = 证据中的金额字段 ∪ offer 内部各金额的两两差值；差值只在 offer 证据内部算，
范围可控，也不会让「500 元」这种编造数字蒙混过关（有单测锁住）。

**为什么只查 `*_cents` 字段**：`days_remaining=20` 这类计数如果被当成金额，会变成 20 分
（0.2 元），凭空给一个毫无依据的数字发通行证。金额字段的命名约定（`Money` + `*_cents`）
正好可以用来精准过滤。

## 四、自查发现并修掉的问题

| 问题 | 表现 | 修法 |
|---|---|---|
| 角色隔离名不副实 | 注释写"欲望角色看不到余额"，实际 `budget` 整个字段都发给了模型 | `desire.build_payload()` 删掉该键；`cross_response` 对 desire 同样处理；单测锁住 |
| 降级过宽 | `skip`/`wait` 也被"方案未验证"改成 `need_info` | 引入 `blocks` 标记，相关级问题只在 `buy` 时否决 |
| 假金额漏检 | `500块`、`¥500` 完全不被识别 | 正则扩到「元 / 块 / 块钱 / ¥ / ￥」 |
| 非金额整数误当金额 | `days_remaining=20` → 允许「0.2 元」 | 只收集 `*_cents` 键 |
| 误伤正确结论 | `counterargument` 按设计要写假设性数字（"如果还压着 600 元支出"），纳入检查会系统性否决正确建议 | 只检查 `reason_summary` + 角色主张 |
| 违规归因噪音 | 预算字段缺失提前退出时，额外记一条"没有任何角色观点"（工作流根本没跑到角色节点） | 该检查只在 `buy` 时成立 |
| 提醒用错动作 | 结论已被降级，仍按原 `action` 追加"买之前先想想" | `advisory_steps` 接收校验后的动作 |

## 五、给报告的三段素材

**角色分工的实质**：欲望角色拿到的上下文里**根本没有 `budget` 这个字段**（程序剔除，不是提示词约束），
理性角色只引用预算工具的结论，优惠节点只解释求解器的数字、不自己算，裁判只做取舍解释、不做自我校验。
一句话：**四个角色里没有一个有权算出金额，金额只有一个来源。**

**与固定工作流的区别**：工作流是确定的（串行、有界、可重放），"Agent" 的部分集中在优惠节点
——它决定查什么、查几次、什么时候停。但第一版连这个决策也固化了，所以报告里应当如实写：
**本系统的智能体现在结构化观点生成与工具编排的边界控制，而不是自主规划。**

**校验前后违规**：`RunRecord.proposed_decision` 是模型原话，`final_decision` 是校验后结果。
因为 D 把问题分成「否决级」和「相关级」，报告里可以给出两个不同的数，而不是糊成一个：

- **命中率** = `policy_violations` 非空的运行数 / 总数，衡量模型出错的频率；
- **否决率** = `proposed_decision.action != final_decision.action` 的运行数 / 总数，
  衡量这些错误里有多少真的改变了结论（相关级问题在 `skip`/`wait` 下不否决）；
- **校验后违规率** = `final_decision.action == "buy"` 且硬约束不成立的比例，**必须是 0**。

三个数分开报，正好体现 D 的核心立场：**记录违规 ≠ 必须改结论，改不改取决于这条问题
是否真的影响这个结论。**

## 六、已知限制

1. **real 模式还没端到端跑通**：`tools/catalog.py`、`tools/optimizer.py`（C）与
   `tools/budget.py`（B）仍是 `ModuleNotReady`。目前 real 模式在第一步就 partial。
   D 的四个节点用 `FakeModel + DemoCatalog` 单独验证过，装配也验证过
   （`build_services(AppConfig(mode="real"))` 返回的就是本文件的四个函数，签名与契约一致）。
2. **`cross_response` 只有单测覆盖**：默认 `cross_response_enabled=false`，demo 模式注入的是
   空 lambda，real 模式又依赖 B/C。开启后需要在集成阶段用真实模型复测一次。
3. **金额检查不解析中文数词**：「约两百块」不会被识别为 200 元。中文数词边界太多
   （「一百二」是 120 还是 102），错解析比不解析更危险，所以宁可漏报不误报，
   这一条漏口靠 `judge.md` 的「不改写金额、不做换算」约束 + 真实模型复测兜住。
   统计这条规则的真实命中率是集成阶段要看的指标。

## 七、需要和 A 确认的三件事

1. `deal` 预留 1 次额度这个约定，是否写进 `docs/common/contracts.md`？否则别人改
   `max_tool_calls` 时会悄悄踩到上限。
2. `cross_response.md` 是新增提示词文件，`workflow.prompt_hashes` 会自动收录（按目录 glob），
   但 `call_role` 的白名单不含该角色名，所以 `cross_response.py` 直接读文件调
   `model.generate_json("cross_response", ...)`，ModelTrace 的 role 会显示为 `cross_response`。
   如果 A 希望统一走 `call_role`，需要把该角色名加进白名单。
3. `desire.py` 为了做结构性隔离，绕过了 `call_role`（它固定发 `context.model_dump()`），
   改为自己拼 payload 并删掉 `budget`。如果 A 愿意给 `call_role` 加一个
   `exclude={"budget"}` 之类的参数，这条就可以收回统一封装。
