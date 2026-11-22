# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Silver — typed, clean prices
# MAGIC Latest bronze batch → real dates, DOUBLE prices, missing values (`..`) dropped, `commodity_group` added.
# MAGIC Fails the job if the data looks wrong, so bad data never reaches gold.

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "commodities")
t = f"{dbutils.widgets.get('catalog')}.{dbutils.widgets.get('schema')}"

# COMMAND ----------

import os
import sys

sys.path.append(os.getcwd())
from transforms import silver_prices_sql  # noqa: E402

spark.sql(f"CREATE OR REPLACE TABLE {t}.silver_prices AS {silver_prices_sql(f'{t}.bronze_pinksheet_monthly')}")
spark.sql(f"COMMENT ON TABLE {t}.silver_prices IS 'Typed monthly commodity prices (nominal USD), latest Pink Sheet batch.'")

# COMMAND ----------

dq = spark.sql(f"""
  SELECT COUNT(*) AS rows,
         COUNT(DISTINCT commodity) AS commodities,
         COUNT(*) - COUNT(DISTINCT commodity, date) AS duplicates,
         COUNT_IF(price < 0) AS negative_prices
  FROM {t}.silver_prices
""").first()
print(dq.asDict())
assert dq.rows > 10_000, "too few rows"
assert dq.commodities >= 30, "too few commodities"
assert dq.duplicates == 0, "duplicate (commodity, date) rows"
assert dq.negative_prices == 0, "negative prices"
