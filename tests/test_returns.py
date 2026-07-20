import numpy as np
import pandas as pd

from src.analysis.returns import compute_log_returns


def test_log_returns_basic_values():
    prices = pd.DataFrame({"A": [100.0, 110.0, 121.0]})
    returns = compute_log_returns(prices)

    assert len(returns) == 2
    assert np.isclose(returns["A"].iloc[0], np.log(110.0 / 100.0))
    assert np.isclose(returns["A"].iloc[1], np.log(121.0 / 110.0))


def test_log_returns_drops_first_row():
    prices = pd.DataFrame({"A": [100.0, 105.0], "B": [50.0, 49.0]})
    returns = compute_log_returns(prices)
    assert len(returns) == 1
    assert list(returns.columns) == ["A", "B"]
