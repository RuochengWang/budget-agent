# 全员公共文档

此目录供 A—E 共同阅读和遵守。个人任务与开发说明分别放在 `docs/A/`—`docs/E/`。

## 上手顺序

1. 首次使用先克隆仓库；已经克隆的同学先保存手头改动，再更新本机 main。
2. 阅读 [总体结构](overview/README.md)，理解项目目标、目录和五人分工。
3. 阅读 [系统流程图](overview/flowcharts.md)，理解从用户输入到最终建议的执行过程。
4. 对照 [文件地图](overview/file_map.md) 找到自己模块与上下游；该文可随时查阅。
5. 阅读 [公共接口约定](contracts.md)，明确输入输出、金额、优惠和异常的统一规则。
6. 进入自己的开发目录，阅读对应 README 后再安装环境、开分支、开始开发。

| 成员 | 个人开发入口 |
|---|---|
| A | [docs/A/README.md](../A/README.md) |
| B | [docs/B/README.md](../B/README.md) |
| C | [docs/C/README.md](../C/README.md) |
| D | [docs/D/README.md](../D/README.md) |
| E | [docs/E/README.md](../E/README.md) |

克隆、更新、分支与 PR 的具体操作见根目录 [CONTRIBUTING.md](../../CONTRIBUTING.md)。

## 共同维护的资料

| 文档 | 用途 | 维护方式 |
|---|---|---|
| [overview/](overview/README.md) | 总体结构、流程图与文件地图 | A 协调，各成员同步自己模块的变化 |
| [contracts.md](contracts.md) | 数据字段、函数与业务规则的共同约定 | A 协调；修改前说明上下游影响 |
| [tasks.md](tasks.md) | A—E 文件清单入口、可认领任务和验收清单 | 各自更新负责项，A 跟踪集成 |
| [roadmap.md](roadmap.md) | 11 月 21 日展示前的共同排期 | A 维护，全员确认进度 |
| [verification.md](verification.md) | 骨架交付时实际验证的内容与局限 | 保留历史事实，后续验证另补记录 |

新增文档时先确定读者：个人实现细节放个人目录，全员需要遵守的内容放 common。
同一项规则集中维护一份，其他文档用链接引用。
