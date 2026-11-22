# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Gold — tables for the dashboard and Genie
# MAGIC - `gold_monthly_metrics` (commodity × month): MoM / YoY %, 12m moving average, 12m volatility
# MAGIC - `gold_latest_snapshot` (one row per commodity): latest price, YoY, 5y change, distance from all-time high

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "commodities")
t = f"{dbutils.widgets.get('catalog')}.{dbutils.widgets.get('schema')}"

# COMMAND ----------

import os
import sys

sys.path.append(os.getcwd())
from transforms import gold_latest_snapshot_sql, gold_monthly_metrics_sql  # noqa: E402

tables = {  # order matters: the snapshot reads the metrics table
    "gold_monthly_metrics": (gold_monthly_metrics_sql(f"{t}.silver_prices"),
        "Monthly metrics per commodity: MoM/YoY %, 12m moving average, 12m annualized volatility."),
    "gold_latest_snapshot": (gold_latest_snapshot_sql(f"{t}.silver_prices", f"{t}.gold_monthly_metrics"),
        "One row per commodity: latest price, YoY, 5-year change, all-time high. is_active = still updated."),
}
for name, (sql, comment) in tables.items():
    spark.sql(f"CREATE OR REPLACE TABLE {t}.{name} AS {sql}")
    spark.sql(f"COMMENT ON TABLE {t}.{name} IS '{comment}'")
    n = spark.table(f"{t}.{name}").count()
    assert n > 0, f"{name} is empty"
    print(f"{name}: {n:,} rows")

# COMMAND ----------

display(spark.sql(f"""
  SELECT commodity, latest_date, latest_price, unit, yoy_pct
  FROM {t}.gold_latest_snapshot
  WHERE is_active AND yoy_pct IS NOT NULL
  ORDER BY abs(yoy_pct) DESC LIMIT 15
"""))
