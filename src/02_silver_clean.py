# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Silver — typed, clean prices
# MAGIC Latest bronze batch → real dates, DOUBLE prices, missing values (`..`) dropped, `commodity_group` added.
# MAGIC Fails the job if the data looks wrong, so bad data never reaches gold.

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "commodities")
db = f"{dbutils.widgets.get('catalog')}.{dbutils.widgets.get('schema')}"

# COMMAND ----------

import os
import sys

sys.path.append(os.getcwd())
from transforms import comment_on_table_sql, silver_prices_sql  # noqa: E402

silver_sql = silver_prices_sql(f"{db}.bronze_pinksheet_monthly")
spark.sql(f"CREATE OR REPLACE TABLE {db}.silver_prices AS {silver_sql}")
spark.sql(comment_on_table_sql(
    f"{db}.silver_prices",
    "Typed monthly commodity prices (nominal USD), latest Pink Sheet batch.",
))

# COMMAND ----------

checks = spark.sql(f"""
  SELECT COUNT(*) AS rows,
         COUNT(DISTINCT commodity) AS commodities,
         COUNT(*) - COUNT(DISTINCT commodity, date) AS duplicates,
         COUNT_IF(price < 0) AS negative_prices
  FROM {db}.silver_prices
""").first()
print(checks.asDict())
assert checks.rows > 10_000, "too few rows"
assert checks.commodities >= 30, "too few commodities"
assert checks.duplicates == 0, "duplicate (commodity, date) rows"
assert checks.negative_prices == 0, "negative prices"
