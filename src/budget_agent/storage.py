"""A：运行记录是本地文件，不提交到 Git；回放保持原始模式与时间。"""

import re
from pathlib import Path

from budget_agent.schemas import RunRecord


def save_record(record: RunRecord, output_dir: Path) -> Path:
    """保存一份 JSON；即使导入外部 RunRecord 也不允许 run_id 穿越目录。"""
    if not re.fullmatch(r"[a-f0-9]{32}", record.run_id):
        raise ValueError("run_id 格式不合法")
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{record.run_id}.json"
    path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_record(path: Path) -> RunRecord:
    return RunRecord.model_validate_json(path.read_text(encoding="utf-8"))
