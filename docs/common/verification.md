# 骨架交付验证记录

日期：2026-11-07。环境：macOS arm64、Python 3.12.14。

| 检查 | 实际结果 |
|---|---|
| 按 uv.lock 安装 dev/ui 依赖 | 成功 |
| `pytest -q` | 30 passed，11 xfailed；xfailed 均为 B/C 尚未实现的正式业务 |
| `ruff check .` | 通过 |
| `uv lock --check --offline` | 通过，配置与锁文件一致 |
| 球鞋案例 | demo / completed / wait；650 元仍超过 300 元预算 |
| 日用品与纸巾案例 | demo / completed / buy；fixture 总付款 255 元，单买基准 280 元 |
| 缺少预留金 | demo / needs_input；没有调用模型 |
| 运费未知 | demo / needs_input；没有伪造最终付款额 |
| 恰好达到预算 | demo / completed / buy；此处仅为脚本建议 |
| 正式模块未实现 | real / partial；不切换到 demo，CLI 退出码 2 |
| Streamlit AppTest | 页面加载与提交成功，显示演示状态、预算与结果 |
| 连接错误与输出格式重试 | MockTransport 模拟验证，最多一次格式重试，不打印服务正文 |
| 历史记录往返 | JSON 保存/读取一致，保留原始模式与时间 |

本机检查不等于 Windows/Linux 已实际运行。CI 已配置三系统 Python 3.12 检查，
首次上传 GitHub 后才会执行；需组员分别做 Windows/macOS 实机启动验收。

没有使用真实 API 密钥发起学校模型请求。没有正式评测结果，冻结测试集仍为空。
下一步由 A 在本机配置 .env 后执行 check-model，由 B/C/D/E 按各自指南完成业务。

## 后续 A 开发进度（2026-11-07）

A 已在本机运行 `uv run budget-agent check-model` 并报告成功。
随后 A 运行 `uv run budget-agent check-model --json` 并报告成功。
这补充了骨架交付时尚未进行的真实文本和 JSON 格式检查；不表示其他模型或角色业务已验收。
自动测试使用模拟服务验证该入口，不会读取密钥发起真实请求。
A 随后在本机运行个人指南中的公共基础检查并报告成功。
本组检查覆盖数据格式、模型适配、工具管理和演示总控，采用模拟模型/工具。
A 已运行球鞋演示案例。读取本机记录后确认：工具依次为预算初算、商品查询、活动查询、
优惠方案、预算复核，共 5 次；可支配预算 30000 分、付款 65000 分、购买后现金 55000 分，
within_budget=false，原始和最终建议均为 wait，错误与程序调整原因均为空。
该记录使用 fake/scripted 与演示优惠 fixture，不表示正式业务已完成。
A 继续运行正式模式。读取最近的正式球鞋记录确认 status=partial，
错误指向 B 的正式预算占位函数，模型调用次数为 0；与当前预期一致。
下一项保存当前 A 阶段代码、测试与验证记录，再上传分支并创建 PR。
