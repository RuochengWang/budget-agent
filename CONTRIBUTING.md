# Git 协作指南

组长为 A。只把 budget-agent 作为单独仓库，不要上传整个课程目录。
当前交付没有创建远程仓库、没有推送，也没有提交真实密钥。

## 组长首次上传

在 budget-agent 目录执行，先在代码托管平台创建空仓库：

```text
git init -b main
git add .
git status --short
git diff --cached --stat
git commit -m "chore: initialize collaborative scaffold"
git remote add origin 替换为实际仓库地址
git push -u origin main
```

提交前查看暂存文件，确认没有 .env、outputs 记录和个人材料。
不要复制 `.env.example` 的占位字符串当真密钥，也不要共享包含密钥的截图。
建议 main 禁止直接推送，合并需一次组员审阅与 CI 通过；由 A 在平台设置。

## 成员日常流程

```text
git clone 替换为实际仓库地址
cd budget-agent
uv sync --frozen --extra dev --extra ui
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
schemas.py 改动必须更新 contracts.md、调用方和案例；不要把同名协议复制到私人文件。

## 完成业务 TODO

先实现正式模块，再移除相应 `xfail(raises=ModuleNotReady, strict=True)` 标记。
严格 xfail 的意外通过会让 CI 失败，提醒将验收测试转为普通测试。
如改变验收条件，PR 中说明原因；不要用宽泛 xfail 掩盖真实错误。
