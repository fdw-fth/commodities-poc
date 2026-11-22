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
t = f"{dbutils.widgets.get('catalog')}.{dbutils.widgets.get('schema')}"
source = f"/Volumes/{t.replace('.', '/')}/raw/CMO-Historical-Data-Monthly.xlsx"

# COMMAND ----------

import os
import sys

sys.path.append(os.getcwd())
from pinksheet_parser import parse_monthly_prices, summarize  # noqa: E402

if not os.path.exists(source):
    raise FileNotFoundError(f"{source} not found. On your laptop run: "
                            "python scripts/poc.py download && python scripts/poc.py upload")

pdf = parse_monthly_prices(source)
print(summarize(pdf))

spark.createDataFrame(pdf, schema=", ".join(f"{c} STRING" for c in pdf.columns)) \
     .write.mode("append").saveAsTable(f"{t}.bronze_pinksheet_monthly")
spark.sql(f"COMMENT ON TABLE {t}.bronze_pinksheet_monthly IS 'Raw Pink Sheet monthly prices, unpivoted, untyped, one batch per ingested_at.'")
