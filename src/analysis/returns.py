import numpy as np
import pandas as pd


def compute_log_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Convert a wide price DataFrame (date x ticker) into daily log-returns."""
    return np.log(prices / prices.shift(1)).dropna(how="all")
