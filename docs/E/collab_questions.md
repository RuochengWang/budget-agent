# 给 A 的确认清单（E 侧，直接复制发送即可；我没有代发）

以下 4 项都只影响"评测怎么跑"，不需要你现在改公共代码；确认后 E 可以按已写好的
`register_baseline()` 接口接入，不碰 `workflow.py` / `schemas.py` / `configs/`。

1. **B0/B1/B2 的 Services 注入方式**：E 需要为三个基线替换角色或工具组合，
   但 A 的 `build_services()` 目前只按 mode 选 demo/real。请确认：
   - 是允许 E 在评测进程里自己组装 `Services(tools, model, desire, rational, deal, judge, cross_response)`
     再调 `run_case(case, config, services)`，还是由 A 提供一个 `build_baseline_services(name, config)`？
   - 无论哪种，E 的 `evaluation/baselines.py` 都已留好注册钩子，不会改 A 的文件。

2. **评测统一配置**：`configs/default.toml` 由 A 维护。请确认实验期间用哪一个
   `--config`（或就用默认 + 环境变量）。E 的运行器会把配置快照写进
   `outputs/*.summary.json`，但不会替 A 新增配置文件。

3. **同模型 / 数据快照 / 工具额度**：请确认 B0/B1/B2/M/M_no_cross 统一使用
   `qwen3.8-chat`、当前 `data/catalog/` 快照、`max_tool_calls=6`；
   B0 不调用模型但仍必须使用 B 的正式预算与 C 的正式求解器。

4. **交叉回应开关**：`cross_response_enabled` 目前为 `false`（A 的配置）。
   M 用配置值、M_no_cross 强制关闭。请确认 D 完成后由 A 打开为 `true` 的时间点，
   否则 M 与 M_no_cross 消融没有区分度。

## 另外两条知会（不需要回复）

- E 的运行器已加硬守卫：标签未 `reviewed`、`demo` 记录、`partial/failed` 记录、
  缺标签案例一律 exit 2，不写成绩文件；`--allow-draft-labels` 只用于本地自测。
- `evaluation/rehearsal_check.py` 会读 `git status --porcelain`，只报告事实，
  不会替任何人提交、推送或修改业务文件。
