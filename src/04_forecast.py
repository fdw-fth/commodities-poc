# Databricks notebook source
# MAGIC %md
# MAGIC # 04 · Forecast — 12-month baseline, tracked in MLflow
# MAGIC One MLflow run per commodity: rolling-origin backtest MAPE (last 5 years) vs a naive "last value" forecast, plus the forecast.
# MAGIC Results go to `gold_forecast` for the dashboard.

# COMMAND ----------

# MAGIC %pip install -q statsmodels mlflow-skinny

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "commodities")
# Exact names from silver_prices, separated by "|" (names contain commas).
dbutils.widgets.text("commodities", "Crude oil, Brent|Gold|Copper|Coffee, Arabica")
t = f"{dbutils.widgets.get('catalog')}.{dbutils.widgets.get('schema')}"
wanted = [c.strip() for c in dbutils.widgets.get("commodities").split("|") if c.strip()]

# COMMAND ----------

import os
import sys

import mlflow
import pandas as pd

sys.path.append(os.getcwd())
from forecasting import backtest_and_forecast, to_monthly_series  # noqa: E402

mlflow.set_experiment(f"/Users/{spark.sql('SELECT current_user()').first()[0]}/commodities_forecast")

results = []
for name in wanted:
    pdf = spark.sql(f"SELECT date, price FROM {t}.silver_prices WHERE commodity = :c", args={"c": name}).toPandas()
    if pdf.empty:
        print(f"Skipping '{name}': not found in silver_prices")
        continue
    out = backtest_and_forecast(to_monthly_series(pdf))
    with mlflow.start_run(run_name=name) as run:
        mlflow.log_params({"commodity": name, "model": "Theta on log prices", "horizon_months": 12,
                           "backtest": "rolling origin, last 5y, every 3 months", "backtest_windows": out["backtest_windows"]})
        mlflow.log_metrics({k: out[k] for k in ("backtest_mape_pct", "naive_mape_pct")})
        mlflow.log_text(out["forecast"].to_csv(index=False), "forecast.csv")
    results.append(out["forecast"].assign(commodity=name, backtest_mape_pct=out["backtest_mape_pct"],
                                          naive_mape_pct=out["naive_mape_pct"], mlflow_run_id=run.info.run_id))

assert results, "No forecasts produced"
spark.createDataFrame(pd.concat(results, ignore_index=True)) \
     .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{t}.gold_forecast")
spark.sql(f"COMMENT ON TABLE {t}.gold_forecast IS '12-month baseline forecasts (Theta), rolling-origin backtest MAPE vs naive. Demo only, not investment advice.'")
display(spark.table(f"{t}.gold_forecast"))
