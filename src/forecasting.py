"""
Baseline 12-month forecast: Theta method on log prices.
Scored with a rolling-origin backtest (a new 12-month forecast every few months over the last
5 years) against a naive "last value" forecast. A demo baseline, not investment advice.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from statsmodels.tsa.forecasting.theta import ThetaModel


def to_monthly_series(df: pd.DataFrame, min_year: int = 2000) -> pd.Series:
    """Columns date, price for ONE commodity -> month-start series with gaps interpolated."""
    s = df.assign(date=pd.to_datetime(df["date"])).set_index("date")["price"].astype(float).sort_index()
    s = s[(s.index.year >= min_year) & (s > 0)]
    return s.asfreq("MS").interpolate(limit_direction="both")


def _forecast(series: pd.Series, horizon: int) -> pd.Series:
    model = ThetaModel(np.log(series), period=12, deseasonalize=False).fit()
    return np.exp(model.forecast(horizon))


def _mape(actual, predicted) -> float:
    actual = np.asarray(actual, dtype=float)
    return float(np.mean(np.abs((actual - np.asarray(predicted, dtype=float)) / actual)) * 100)


def rolling_origins(n: int, horizon: int, years: int = 5, step: int = 3) -> list[int]:
    """Train-set lengths for each backtest window; the last window ends at the last observation."""
    last = n - horizon
    first = max(horizon, last - 12 * years)
    return sorted(range(last, first - 1, -step))


def backtest_and_forecast(series: pd.Series, horizon: int = 12, years: int = 5, step: int = 3) -> dict:
    if len(series) < 5 * horizon:
        raise ValueError(f"Need at least {5 * horizon} months, got {len(series)}")
    origins = rolling_origins(len(series), horizon, years, step)
    model_err, naive_err = [], []
    for o in origins:
        train, test = series.iloc[:o], series.iloc[o:o + horizon]
        model_err.append(_mape(test, _forecast(train, horizon)))
        naive_err.append(_mape(test, [train.iloc[-1]] * horizon))
    forecast = _forecast(series, horizon)
    return {
        "backtest_mape_pct": round(float(np.mean(model_err)), 2),
        "naive_mape_pct": round(float(np.mean(naive_err)), 2),
        "backtest_windows": len(origins),
        "forecast": pd.DataFrame({"forecast_date": forecast.index.date, "forecast_price": forecast.values}),
    }
