"""共享金额文本处理；用 Decimal 转整数分，不解释任意自然语言。"""

import re
from dataclasses import dataclass
from decimal import Decimal

_INTEGER = r"-?(?:\d{1,3}(?:,\d{3})+|\d+)"
_NUMBER = rf"{_INTEGER}(?:\.\d{{1,2}})?"
_AMOUNT = re.compile(
    rf"(?<![\d.])(?:[¥￥]\s*(?P<prefix>{_NUMBER})(?:\s*(?:元|块钱|块))?"
    rf"|(?P<suffix>{_NUMBER})\s*(?:元|块钱|块)"
    rf"|(?P<cents>{_INTEGER})\s*分(?!钟|鐘|贝|貝|之|数|數))"
)


@dataclass(frozen=True)
class AmountMention:
    cents: int
    start: int
    end: int


def find_amounts(text: str) -> list[AmountMention]:
    """识别元与整数分，包含零和负值；不把“分钟”“分之一”当作钱。"""
    return [
        AmountMention(
            cents=(
                int(match.group("cents").replace(",", ""))
                if match.group("cents") is not None
                else int(
                    Decimal((match.group("prefix") or match.group("suffix")).replace(",", "")) * 100
                )
            ),
            start=match.start(),
            end=match.end(),
        )
        for match in _AMOUNT.finditer(text)
    ]


def redact_amounts(text: str) -> str:
    """欲望角色只接收其他角色的观点含义，不接收其中的具体金额。"""
    return _AMOUNT.sub("（金额省略）", text)
