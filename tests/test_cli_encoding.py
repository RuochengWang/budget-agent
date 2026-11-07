"""A：复现 Windows CI 的 cp1252 标准流，确认成功与错误提示都可输出中文。"""

import os
import subprocess
import sys

import pytest

from budget_agent.config import PROJECT_ROOT


@pytest.mark.parametrize(
    "arguments,code,stream,expected",
    [
        (["list-cases"], 0, "stdout", "优惠后的球鞋仍超预算"),
        (["run", "--case", "sneakers_wait"], 0, "stdout", "建议=wait"),
        (["run", "--case", "does_not_exist"], 2, "stderr", "未知案例"),
    ],
)
def test_chinese_cli_with_non_utf8_standard_streams(arguments, code, stream, expected):
    # 创建独立进程，覆盖真实 Python 标准流，避免 pytest 内存捕获掩盖编码问题。
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "cp1252"
    env["PYTHONUTF8"] = "0"
    result = subprocess.run(
        [sys.executable, "-m", "budget_agent", *arguments],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == code, result.stderr.decode("utf-8", errors="replace")
    assert expected in getattr(result, stream).decode("utf-8")
    assert b"UnicodeEncodeError" not in result.stderr
