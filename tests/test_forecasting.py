import numpy as np
import pandas as pd
import pytest

pytest.importorskip("statsmodels")

from forecasting import backtest_and_forecast, rolling_origins, to_monthly_series  # noqa: E402


def test_forecast(bronze_pdf):
    gold = bronze_pdf[bronze_pdf.commodity == "Gold"]
    df = pd.DataFrame({"date": pd.to_datetime(gold["period"].str.replace("M", "-") + "-01"),
                       "price": pd.to_numeric(gold["raw_value"])})
    out = backtest_and_forecast(to_monthly_series(df))
    assert len(out["forecast"]) == 12
    assert str(out["forecast"]["forecast_date"].iloc[0]) == "2026-11-01"
    assert (out["forecast"]["forecast_price"] > 0).all()
    assert out["backtest_mape_pct"] >= 0 and out["naive_mape_pct"] >= 0
    assert out["backtest_windows"] > 1


def test_rolling_origins():
    # 100 months, 12-month horizon: last window trains on 88 months and tests on the final 12
    origins = rolling_origins(100, 12, years=5, step=3)
    assert origins[-1] == 88 and origins[0] == 28
    assert np.all(np.diff(origins) == 3)
    assert rolling_origins(30, 12, years=5, step=3)[0] >= 12  # never trains on less than one horizon


def test_beats_naive_on_trending_series():
    rng = np.random.default_rng(0)
    idx = pd.date_range("2000-01-01", periods=180, freq="MS")
    s = pd.Series(np.exp(np.log(50) + 0.01 * np.arange(180) + rng.normal(0, 0.01, 180)), index=idx)
    out = backtest_and_forecast(s)
    assert np.isfinite(out["backtest_mape_pct"])
    assert out["backtest_mape_pct"] < out["naive_mape_pct"]
