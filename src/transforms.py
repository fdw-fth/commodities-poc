"""
Silver and gold transformations as Spark SQL SELECT statements.

Plain Python module (NOT a notebook) so the same SQL is:
  * wrapped in CREATE OR REPLACE TABLE ... AS by the Databricks notebooks, and
  * run against local temp views by tests/test_transforms.py.

Each function takes fully-qualified (or temp-view) table names and returns SQL.
Notes:
  * try_divide / try_cast avoid ANSI-mode errors on serverless.
  * YoY and 5y changes use exact calendar joins (add_months), not LAG(n),
    so gaps in a series never produce a wrong comparison.
"""

# Ordered: first match wins (e.g. "Crude oil" is Energy, not "Oils & meals").
COMMODITY_GROUPS = [
    ("Energy",          r"crude|coal|natural gas|liquefied|\\blng\\b"),
    ("Beverages",       r"cocoa|coffee|\\btea\\b"),
    ("Oils & meals",    r"\\boil\\b|groundnut|soybean|copra|fish meal|rapeseed|sunflower"),
    ("Grains",          r"barley|maize|sorghum|\\brice\\b|wheat"),
    ("Other food",      r"banana|orange|beef|chicken|lamb|shrimp|sugar|meat"),
    ("Raw materials",   r"tobacco|\\blogs?\\b|sawnwood|plywood|cotton|rubber|timber"),
    ("Fertilizers",     r"phosphate|\\bdap\\b|\\btsp\\b|urea|potassium"),
    ("Base metals",     r"alumin|iron ore|copper|\\blead\\b|\\btin\\b|nickel|zinc"),
    ("Precious metals", r"gold|platinum|silver"),
]


def comment_on_table_sql(table: str, comment: str) -> str:
    """COMMENT ON TABLE statement; quotes in the text are escaped so they can't end the SQL string."""
    escaped = comment.replace("'", "''")
    return f"COMMENT ON TABLE {table} IS '{escaped}'"


def _group_case(col: str = "commodity") -> str:
    """SQL CASE expression that maps a commodity name to its group (see COMMODITY_GROUPS)."""
    whens = "\n".join(
        f"    WHEN lower({col}) RLIKE '{pattern}' THEN '{group}'"
        for group, pattern in COMMODITY_GROUPS
    )
    return f"CASE\n{whens}\n    ELSE 'Other'\n  END"


def silver_prices_sql(bronze: str) -> str:
    """Latest bronze batch -> typed, one row per (commodity, month)."""
    return f"""
WITH latest AS (SELECT MAX(ingested_at) AS ts FROM {bronze}),
typed AS (
  SELECT
    to_date(concat(substr(period, 1, 4), '-', substr(period, 6, 2), '-01')) AS date,
    CAST(substr(period, 1, 4) AS INT) AS year,
    CAST(substr(period, 6, 2) AS INT) AS month,
    commodity,
    -- 'Crude oil, Brent' -> 'crude_oil_brent'
    regexp_replace(regexp_replace(lower(commodity), '[^a-z0-9]+', '_'), '^_+|_+$', '') AS commodity_id,
    unit,
    {_group_case()} AS commodity_group,
    try_cast(raw_value AS DOUBLE) AS price,
    source_file,
    ingested_at
  FROM {bronze} b
  JOIN latest l ON b.ingested_at = l.ts
)
SELECT * FROM typed
WHERE price IS NOT NULL AND date IS NOT NULL
"""


def gold_monthly_metrics_sql(silver: str) -> str:
    """Per commodity-month: MoM, YoY, 12m moving average, 12m annualized volatility."""
    return f"""
WITH with_prev AS (
  SELECT *,
    LAG(price) OVER (PARTITION BY commodity ORDER BY date) AS prev_price,
    LAG(date)  OVER (PARTITION BY commodity ORDER BY date) AS prev_date
  FROM {silver}
),
with_returns AS (
  -- Only compare with the previous row if it really is the previous month.
  SELECT *,
    CASE WHEN prev_date = add_months(date, -1) THEN prev_price END AS price_1m_ago,
    CASE WHEN prev_date = add_months(date, -1) AND price > 0 AND prev_price > 0
         THEN ln(try_divide(price, prev_price)) END AS log_return_1m
  FROM with_prev
)
SELECT
  cur.date, cur.year, cur.month, cur.commodity, cur.commodity_id, cur.commodity_group, cur.unit, cur.price,
  ROUND(100 * (try_divide(cur.price, cur.price_1m_ago) - 1), 2)  AS mom_pct,
  ROUND(100 * (try_divide(cur.price, year_ago.price) - 1), 2)    AS yoy_pct,
  cur.log_return_1m,
  AVG(cur.price) OVER last_12m                                   AS ma_12m,
  STDDEV(cur.log_return_1m) OVER last_12m * SQRT(12)             AS vol_12m_annualized
FROM with_returns cur
LEFT JOIN {silver} year_ago
  ON year_ago.commodity = cur.commodity AND year_ago.date = add_months(cur.date, -12)
WINDOW last_12m AS (PARTITION BY cur.commodity ORDER BY cur.date
                    ROWS BETWEEN 11 PRECEDING AND CURRENT ROW)
"""


def gold_latest_snapshot_sql(silver: str, metrics: str) -> str:
    """One row per commodity: latest price, YoY, 5y change, distance from all-time high."""
    return f"""
WITH ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY commodity ORDER BY date DESC) AS recency_rank
  FROM {metrics}
),
latest AS (
  SELECT * FROM ranked WHERE recency_rank = 1
),
ath AS (
  SELECT commodity, MAX(price) AS all_time_high, MAX_BY(date, price) AS all_time_high_date
  FROM {silver}
  GROUP BY commodity
)
SELECT
  cur.commodity, cur.commodity_id, cur.commodity_group, cur.unit,
  cur.date  AS latest_date,
  cur.price AS latest_price,
  cur.mom_pct, cur.yoy_pct,
  ROUND(cur.vol_12m_annualized, 4)                                AS vol_12m_annualized,
  ROUND(100 * (try_divide(cur.price, five_years_ago.price) - 1), 2) AS change_5y_pct,
  ath.all_time_high, ath.all_time_high_date,
  ROUND(100 * (try_divide(cur.price, ath.all_time_high) - 1), 2)  AS pct_from_ath,
  -- Active = reported within 3 months of the newest data point in the file.
  cur.date >= add_months(MAX(cur.date) OVER (), -3)               AS is_active
FROM latest cur
JOIN ath ON ath.commodity = cur.commodity
LEFT JOIN {silver} five_years_ago
  ON five_years_ago.commodity = cur.commodity AND five_years_ago.date = add_months(cur.date, -60)
"""
