# Git 协作指南

成员统一以 A—E 标识。远程仓库由 A 维护并向组员提供地址。密钥与本地运行记录不提交。

## 每位成员先按此顺序上手

1. **先获取最新仓库。** 首次使用先克隆；已经克隆的先保存手头工作，再更新 main。
2. **再看整体框架。** 全员先读 [总体结构](docs/common/overview/README.md) 和
   [系统流程图](docs/common/overview/flowcharts.md)，用 [文件地图](docs/common/overview/file_map.md) 定位上下游。
3. **再看自己的开发文档。** 共同遵守 [接口约定](docs/common/contracts.md)，然后按角色进入：
   [A](docs/A/README.md)、[B](docs/B/README.md)、[C](docs/C/README.md)、[D](docs/D/README.md)、[E](docs/E/README.md)。
4. **最后进入开发。** 安装环境、跑通示例、从最新 main 创建任务分支，按个人指南开发与验收，再提 PR。

A 首次完成建仓和分享后，也按同一阅读路径确认公共接口与自己的任务。

## 首次拉取与开始开发

首次使用：

```text
git clone https://github.com/RuochengWang/budget-agent.git
cd budget-agent
```

已经克隆仓库的同学，先提交或妥善保存手头改动，再更新本机 main：

```text
git switch main
git pull --ff-only origin main
```

**到这里先阅读公共总览、流程图、接口约定与自己的开发指南。**
确认任务后再安装环境、跑示例和创建分支。以下以 B 开发预算为例，其他成员替换分支名：

```text
uv sync --frozen --extra dev --extra ui
uv run budget-agent run --case sneakers_wait
git switch main
git switch -c feat/B-budget
```

分支建议：feat/A-integration、feat/B-budget、feat/C-optimizer、feat/D-agents、feat/E-ui。
每次 PR 围绕一个可验收任务，提交前：

```text
uv run pytest
uv run ruff check .
git add 明确要提交的文件路径
git commit -m "feat(B): implement budget calculation"
git push -u origin feat/B-budget
```

然后在托管平台创建 PR，使用模板说明行为、验证、接口变化和未完成事项。
至少另一位组员检查，A 集成公共接口变化。C 的优惠测试建议 B 参与复核。
不要为绕过测试而删除保护或把失败改成返回演示结果。

更新自己分支前先保存工作，再执行 `git fetch origin`、`git merge origin/main`。
发生冲突先读双方修改，协议冲突找 A 协调；不要直接覆盖对方版本或强制推送。
README 的命令以已经进入项目根目录为前提，终端路径有空格时记得加引号。

## 依赖与公共文件

A 统一维护 pyproject.toml 与 uv.lock；确需新增依赖先讨论，再由 A 更新两个锁文件。
requirements.lock 是 pip 备用锁，使用 `uv export --frozen --extra dev --extra ui --no-emit-project --output-file requirements.lock` 同步导出。
schemas.py 改动必须更新 [公共接口约定](docs/common/contracts.md)、调用方和案例；不要把同名协议复制到私人文件。

文档只分为 `docs/A/`—`docs/E/` 和 `docs/common/` 六个一级目录。
个人实现与交付资料放对应角色目录；全员规则放 common；项目总览与流程图放 common/overview。
移动或新增文档时同步 README、个人指南、公共文件地图和引用链接。

## 完成业务 TODO

先实现正式模块，再移除相应 `xfail(raises=ModuleNotReady, strict=True)` 标记。
严格 xfail 的意外通过会让 CI 失败，提醒将验收测试转为普通测试。
如改变验收条件，PR 中说明原因；不要用宽泛 xfail 掩盖真实错误。
