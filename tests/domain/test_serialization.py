from __future__ import annotations

import pandas as pd
from pydantic import BaseModel

from src.domain.serialization import dataframe_to_models


class _Model(BaseModel):
    ticker: str
    value: float | None = None


def test_nan_converted_to_none():
    df = pd.DataFrame({"ticker": ["A"], "value": [float("nan")]})
    models = dataframe_to_models(df, _Model)
    assert models[0].value is None


def test_infinity_converted_to_none():
    df = pd.DataFrame({"ticker": ["A", "B"], "value": [float("inf"), float("-inf")]})
    models = dataframe_to_models(df, _Model)
    assert models[0].value is None
    assert models[1].value is None


def test_finite_value_passes_through_unchanged():
    df = pd.DataFrame({"ticker": ["A"], "value": [0.42]})
    models = dataframe_to_models(df, _Model)
    assert models[0].value == 0.42


def test_empty_dataframe_returns_empty_list():
    df = pd.DataFrame(columns=["ticker", "value"])
    assert dataframe_to_models(df, _Model) == []


def test_result_is_json_serializable():
    import json

    df = pd.DataFrame({"ticker": ["A"], "value": [float("nan")]})
    models = dataframe_to_models(df, _Model)
    # Would raise ValueError("Out of range float values are not JSON compliant")
    # before the fix — NaN survived DataFrame.where(notna, None) unchanged.
    json.dumps(models[0].model_dump())
