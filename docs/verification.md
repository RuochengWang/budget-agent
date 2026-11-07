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
