import json

import pytest

from budget_agent.config import PROJECT_ROOT, AppConfig
from budget_agent.main import load_cases
from budget_agent.schemas import Product, PromotionRule


@pytest.fixture
def config(tmp_path):
    return AppConfig(output_dir=tmp_path / "outputs")


@pytest.fixture
def cases():
    return {c.case_id: c for c in load_cases(PROJECT_ROOT / "data/cases/dev.jsonl")}


@pytest.fixture
def products():
    rows = json.loads((PROJECT_ROOT / "data/catalog/products.json").read_text(encoding="utf-8"))
    return [Product.model_validate(row) for row in rows]


@pytest.fixture
def rules():
    rows = json.loads((PROJECT_ROOT / "data/catalog/promotions.json").read_text(encoding="utf-8"))
    return [PromotionRule.model_validate(row) for row in rows]
