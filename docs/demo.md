# 展示脚本（E 完善）

展示日 2026-11-21 下午；建议 20 分钟，具体以课堂要求为准。

1. 2 分钟：大学生消费痛点与项目范围。
2. 3 分钟：流程、工具与程序约束；说明固定角色节点和工具 agent 的区别。
3. 6 分钟：球鞋优惠后仍超预算；日用品加确需纸巾后总付款更低。
4. 3 分钟：支持范围内的观众输入，未知信息如实显示。
5. 4 分钟：对照/消融、成本、一个失败案例。
6. 2 分钟：五人实际贡献与局限。

当前骨架练习：

```text
uv run budget-agent run --case sneakers_wait
uv run budget-agent run --case tissue_buy
uv run budget-agent run --case unknown_shipping
uv run streamlit run app.py
```

当前命令是演示替身；正式课堂展示前应按 roadmap 完成正式模块。
网络失败备选：使用 `budget-agent replay outputs/实际文件名.json`，明确说“历史回放”。
本地演示替身仅说明架构如何衔接，不能替代真实实验结论。
E 在 11/20 补上冻结 commit、真实历史记录路径、备用录像和实际展示人分配。
