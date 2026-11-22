# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Bronze — raw Pink Sheet ingest
# MAGIC Reads the Excel file from the Unity Catalog Volume, unpivots it to one row per (period, commodity)
# MAGIC and **appends** it as raw strings. Each run is a batch tagged with `ingested_at`, so raw history is kept.

# COMMAND ----------

# MAGIC %pip install -q openpyxl

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "commodities")
db = f"{dbutils.widgets.get('catalog')}.{dbutils.widgets.get('schema')}"
source = f"/Volumes/{db.replace('.', '/')}/raw/CMO-Historical-Data-Monthly.xlsx"

# COMMAND ----------

import os
import sys

sys.path.append(os.getcwd())
from pinksheet_parser import parse_monthly_prices, summarize  # noqa: E402
from transforms import comment_on_table_sql  # noqa: E402

if not os.path.exists(source):
    raise FileNotFoundError(f"{source} not found. On your laptop run: "
                            "python scripts/poc.py download && python scripts/poc.py upload")

bronze = parse_monthly_prices(source)
print(summarize(bronze))

all_strings = ", ".join(f"{col} STRING" for col in bronze.columns)
spark.createDataFrame(bronze, schema=all_strings) \
     .write.mode("append").saveAsTable(f"{db}.bronze_pinksheet_monthly")
spark.sql(comment_on_table_sql(
    f"{db}.bronze_pinksheet_monthly",
    "Raw Pink Sheet monthly prices, unpivoted, untyped, one batch per ingested_at.",
))
