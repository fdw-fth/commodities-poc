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


def _group_case(col: str = "commodity") -> str:
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
WITH base AS (
  SELECT s.*,
    LAG(price) OVER (PARTITION BY commodity ORDER BY date) AS price_prev,
    LAG(date)  OVER (PARTITION BY commodity ORDER BY date) AS date_prev
  FROM {silver} s
),
ret AS (
  SELECT b.*,
    CASE WHEN date_prev = add_months(date, -1) THEN price_prev END AS price_prev_1m,
    CASE WHEN date_prev = add_months(date, -1) AND price > 0 AND price_prev > 0
         THEN ln(try_divide(price, price_prev)) END AS log_return_1m
  FROM base b
)
SELECT
  r.date, r.year, r.month, r.commodity, r.commodity_id, r.commodity_group, r.unit, r.price,
  ROUND(100 * (try_divide(r.price, r.price_prev_1m) - 1), 2) AS mom_pct,
  ROUND(100 * (try_divide(r.price, y.price) - 1), 2)         AS yoy_pct,
  r.log_return_1m,
  AVG(r.price) OVER w12                                      AS ma_12m,
  STDDEV(r.log_return_1m) OVER w12 * SQRT(12)                AS vol_12m_annualized
FROM ret r
LEFT JOIN {silver} y
  ON y.commodity = r.commodity AND y.date = add_months(r.date, -12)
WINDOW w12 AS (PARTITION BY r.commodity ORDER BY r.date
               ROWS BETWEEN 11 PRECEDING AND CURRENT ROW)
"""


def gold_latest_snapshot_sql(silver: str, metrics: str) -> str:
    """One row per commodity: latest price, YoY, 5y change, distance from all-time high."""
    return f"""
WITH ranked AS (
  SELECT m.*, ROW_NUMBER() OVER (PARTITION BY commodity ORDER BY date DESC) AS rn
  FROM {metrics} m
),
ath AS (
  SELECT commodity, MAX(price) AS all_time_high, MAX_BY(date, price) AS all_time_high_date
  FROM {silver}
  GROUP BY commodity
)
SELECT
  r.commodity, r.commodity_id, r.commodity_group, r.unit,
  r.date  AS latest_date,
  r.price AS latest_price,
  r.mom_pct, r.yoy_pct,
  ROUND(r.vol_12m_annualized, 4) AS vol_12m_annualized,
  ROUND(100 * (try_divide(r.price, f.price) - 1), 2) AS change_5y_pct,
  a.all_time_high, a.all_time_high_date,
  ROUND(100 * (try_divide(r.price, a.all_time_high) - 1), 2) AS pct_from_ath,
  r.date >= add_months(MAX(r.date) OVER (), -3) AS is_active
FROM ranked r
JOIN ath a ON a.commodity = r.commodity
LEFT JOIN {silver} f
  ON f.commodity = r.commodity AND f.date = add_months(r.date, -60)
WHERE r.rn = 1
"""
