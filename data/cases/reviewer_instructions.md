# 复核人操作说明（给第二位复核人，可直接转发）

> 你正在核的是「标准答案」，不是代码。请**独立算**，不要直接照抄参考表的结论列。

## 你要做什么

1. 打开 [review_sheet.md](review_sheet.md) 的「参考公式」，按里面的契约公式，
   把 30 道 test 案例逐例用纸笔/计算器算一遍：
   - `essential`、`discretionary`（负数保留，不截断）；
   - 最优应付、单买基准、最优购物篮、使用的规则；
   - 运费未知 → 应付 `None`；缺预算字段 → 依赖该字段的结果为 `None`。
     基本支出只依赖天数、每日基本开支、固定支出，现金或预留金缺失时仍可计算基本支出；
     任一必填预算字段缺失时，流程在初算阶段要求补信息，不生成购买方案；
   - 活动有效期 `[2026-11-01, 2026-12-01)`：起始时刻生效、结束时刻不生效。
2. 再对照 [labels.jsonl](labels.jsonl) 里对应的 30 条测试标签。开发集 10 条不在本轮冻结内。
   有分歧就直接改 `labels.jsonl` 里那条数值，并在工作表「分歧/修正」里记一笔。
3. 两人各自独立完成后，把分歧对齐。然后由 E 运行一次收尾工具（**只改状态，不改数值**）：
   ```text
   uv run python -m evaluation.finalize_labels --cases data/cases/test.jsonl --reviewers A C --date YYYY-MM-DD
   ```
   `A C` 仅为示例，请换成实际成员和日期。默认只检查；两人真的确认后再加 `--apply` 写入复核元数据。
4. 在 [review_sheet.md](review_sheet.md) 末尾填复核人、日期、冻结 commit，标签才算冻结。

## 三条纪律

- **不要让 C 的求解器或任何 AI 模型替你生成答案**：它们正是被考核的对象。
- **不要把答案塞进 `test.jsonl` 或提示词**：案例文件只放输入，标签单独放 `labels.jsonl`，靠 `case_id` 配对。
- `reference_action`（买/等待）只是参考，不作为评分真值；评分比的是客观数字。

## 完成后 E 会做什么

- 评测运行器默认要求 `review_status=reviewed`，冻结后才会放行；
- 用 [离线探针](../../evaluation/integration_probe.py) 做离线联调（模拟模型，不调真实 API）；
- 复核后按 A 确认的实验范围跑真实对照，把实测结果填进 [报告](../../docs/E/report.md)。
