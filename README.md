# 赛博节俭局

基于多角色协作与约束优化的大学生消费决策 Agent。用户输入商品、购买需求和生活费情况，系统计算可支配预算，比较单买与必要凑单的实际付款，再给出购买、等待、放弃或补充信息的建议。

预算与优惠金额由程序计算。欲望、理性、优惠和裁判四个角色分别分析需求、替代方案、优惠结果与最终取舍。程序按最终付款复核预算，并检查建议中的约束与证据。界面可保存运行记录，也可查看历史回放。

## 快速运行

使用 Python 3.11–3.13，推荐 Python 3.12。在终端运行：

```bash
git clone --branch submission --single-branch https://github.com/RuochengWang/budget-agent.git
cd budget-agent
uv sync --frozen --extra dev --extra ui
uv run streamlit run app.py
```

默认选择「离线演示替身」，它使用脚本角色和演示优惠，无需 API 密钥。运行页直接选商品、填预算与购买理由，然后提交。 [示例输入和演示步骤](docs/E/demo.md)

也可以从命令行运行预设案例：

```bash
uv run budget-agent run --case sneakers_wait
uv run budget-agent run --case tissue_buy
```

本次记录保存在本机的 `outputs/`。运行过一次后可在界面切到「历史回放」。

## 正式模型与交叉回应

将 `.env.example` 复制为 `.env`，在本机填入获授权的 API 密钥。默认模型为 `qwen3.8-chat`，可在 `.env` 中设置兼容接口地址和模型名。正式模式使用本地商品、活动样例和真实模型。界面上选择「正式模块」，需要交叉回应时勾选「一轮角色回应」。这两种正式配置的单次请求上限为 90 秒、整次运行上限为 540 秒。

```bash
uv run budget-agent check-model --json
uv run budget-agent --config configs/validation_cross.toml run --mode real --case sneakers_wait
```

报错或中断时，尽可能保存已取得的证据与调用轨迹。 [真实联调记录](docs/A/live_validation.md)

## 项目结构

| 路径 | 用途 |
|---|---|
| `app.py` | Streamlit 输入、结果与历史回放 |
| `src/budget_agent/` | 流程调度、模型接入、四角色、预算及优惠求解 |
| `data/catalog/` | 商品与活动快照 |
| `data/cases/` | 开发案例、测试案例与标签 |
| `evaluation/` | 评测入口、指标与复核工具 |
| `tests/` | 功能与边界测试 |

[系统流程图](docs/common/overview/flowcharts.md) · [接口契约](docs/common/contracts.md) · [案例与标签说明](data/cases/README.md)

## 测试与项目范围

```bash
uv run pytest -q
uv run ruff check .
uv run python -m evaluation.integration_probe
```

自动检查无需真实模型。当前支持已知商品、单商家及有限优惠组合。真实联调用例用于验证流程，正式评测需要先完成人工标签复核。API 密钥和个人运行记录保存在本机。
