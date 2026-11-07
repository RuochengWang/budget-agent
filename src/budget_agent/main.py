"""A：统一命令行入口。默认无网络；只有 check-model/正式角色才可能联网。"""

import argparse
from pathlib import Path

from pydantic import ValidationError

from budget_agent.config import load_config
from budget_agent.errors import AgentError
from budget_agent.model_client import ChatModelClient
from budget_agent.schemas import CaseInput
from budget_agent.storage import load_record, save_record
from budget_agent.workflow import run_case


def load_cases(path: Path) -> list[CaseInput]:
    return [
        CaseInput.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="消费决策 Agent 协作骨架")
    parser.add_argument("--config", type=Path, default=None)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list-cases", help="列出演示案例")
    run = commands.add_parser("run", help="运行案例；默认使用演示替身")
    run.add_argument("--mode", choices=["demo", "real"], default="demo")
    run.add_argument("--case", default="sneakers_wait")
    run.add_argument("--input", type=Path, help="自定义 CaseInput JSON，覆盖 --case")
    commands.add_parser("check-model", help="显式发送一次学校模型连通性请求")
    replay = commands.add_parser("replay", help="回放本地记录，不调用模型")
    replay.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config, mode=getattr(args, "mode", None))
        if args.command == "list-cases":
            for case in load_cases(config.data_dir / "cases/dev.jsonl"):
                print(f"{case.case_id}: {case.title}")
            return 0
        if args.command == "check-model":
            print(ChatModelClient(config).check_connection())
            return 0
        if args.command == "replay":
            record = load_record(args.path)
            print(f"历史回放 | 原模式={record.mode} | 原开始时间={record.started_at.isoformat()}")
        else:
            if args.input:
                case = CaseInput.model_validate_json(args.input.read_text(encoding="utf-8"))
            else:
                cases = {c.case_id: c for c in load_cases(config.data_dir / "cases/dev.jsonl")}
                if args.case not in cases:
                    parser.error("未知案例；使用 list-cases 查看 ID")
                case = cases[args.case]
            record = run_case(case, config)
            path = save_record(record, config.output_dir)
            print(f"记录已保存：{path}")
        print(f"模式={record.mode} | 状态={record.status} | 模型={record.model}")
        if record.mode == "demo":
            print("演示替身：脚本角色 + 手工优惠 fixture，不代表真实模型或求解器效果。")
        if record.final_decision:
            print(f"建议={record.final_decision.action} | {record.final_decision.reason_summary}")
        for error in record.errors:
            print(error)
        return 0 if record.status in {"completed", "needs_input"} else 2
    except (AgentError, OSError, ValidationError, ValueError) as exc:
        # 配置验证异常可能携带用户填写的值，只展示错误类型。
        print(
            str(exc) if isinstance(exc, AgentError) else f"输入或配置错误（{type(exc).__name__}）"
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
