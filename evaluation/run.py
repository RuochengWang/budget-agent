"""运行器骨架：python -m evaluation.run --baseline M --cases data/cases/test.jsonl。"""

import argparse
import json
from pathlib import Path

from budget_agent.errors import ModuleNotReady
from budget_agent.main import load_cases
from evaluation.baselines import BASELINES, run_baseline


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True, choices=BASELINES)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("outputs/evaluation.jsonl"))
    args = parser.parse_args()
    cases = load_cases(args.cases)
    if not cases:
        print("评测集为空：请先由 E 编写、复核并冻结案例。没有产生评测结果。")
        return 2
    try:
        records = [run_baseline(args.baseline, case) for case in cases]
    except ModuleNotReady as exc:
        print(str(exc))
        return 2
    if any(
        r.mode == "demo"
        or r.model == "fake/scripted"
        or (
            r.final_decision
            and r.final_decision.offer_result
            and r.final_decision.offer_result.verification_method == "demo_fixture"
        )
        for r in records
    ):
        print("拒绝将演示替身或手工优惠 fixture 当作正式实验结果。")
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "\n".join(json.dumps(r.model_dump(mode="json"), ensure_ascii=False) for r in records)
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
