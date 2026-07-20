"""Shared DataFrame -> pydantic model conversion for services.

`DataFrame.where(df.notna(), None)` looks like it should turn NaN cells into
Python `None`, but for a float64 column pandas can't actually store a `None`
in the underlying array — it silently coerces the replacement back to NaN,
and NaN (or +-inf, e.g. from a near-zero denominator in partial correlation)
then breaks strict JSON serialization ("Out of range float values are not
JSON compliant"). Converting to plain dicts first and cleaning value-by-value
sidesteps the dtype issue entirely.
"""

from __future__ import annotations

import math
from typing import TypeVar

import pandas as pd
from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


def dataframe_to_models(df: pd.DataFrame, model_cls: type[ModelT]) -> list[ModelT]:
    if df.empty:
        return []
    records = df.to_dict(orient="records")
    cleaned = [{key: (None if _is_non_finite(value) else value) for key, value in record.items()} for record in records]
    return [model_cls(**record) for record in cleaned]


def _is_non_finite(value: object) -> bool:
    return isinstance(value, float) and not math.isfinite(value)
