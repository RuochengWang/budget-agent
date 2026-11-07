"""C：最多八个候选、每件最多一件的有限穷举优惠求解。"""

from budget_agent.errors import ModuleNotReady
from budget_agent.schemas import OfferResult, OptimizationInput


def optimize_basket(request: OptimizationInput) -> OfferResult:
    """TODO(C)：比较目标单买基准与所有合法购物篮，返回明细。

    顺序、门槛、叠加、退款边界和并列解规则见 docs/common/contracts.md。
    运费未知不得把它当零；verified 仅在规则和算术均检查后设置。
    """
    raise ModuleNotReady("TODO(C): tools.optimizer.optimize_basket 尚未实现")
