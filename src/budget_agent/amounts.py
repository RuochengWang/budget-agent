"""共享金额文本处理；用 Decimal 转整数分，不解释任意自然语言。"""

import re
from dataclasses import dataclass
from decimal import Decimal

_NUMBER = r"-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?"
_AMOUNT = re.compile(
    rf"(?<![\d.])(?:[¥￥]\s*(?P<prefix>{_NUMBER})(?:\s*(?:元|块钱|块))?"
    rf"|(?P<suffix>{_NUMBER})\s*(?:元|块钱|块))"
)


@dataclass(frozen=True)
class AmountMention:
    cents: int
    start: int
    end: int


def find_amounts(text: str) -> list[AmountMention]:
    """识别阿拉伯数字金额，包含零和负值；中文数词不在支持范围内。"""
    return [
        AmountMention(
            cents=int(
                Decimal((match.group("prefix") or match.group("suffix")).replace(",", "")) * 100
            ),
            start=match.start(),
            end=match.end(),
        )
        for match in _AMOUNT.finditer(text)
    ]


def redact_amounts(text: str) -> str:
    """欲望角色只接收其他角色的观点含义，不接收其中的具体金额。"""
    return _AMOUNT.sub("（金额省略）", text)
