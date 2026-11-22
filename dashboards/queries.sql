-- AI/BI dashboard datasets: Dashboards → Create → Data → "Create from SQL", one dataset per block.
-- Test one from the terminal: python scripts/poc.py sql "<paste query>"

-- name: kpis  (counter tiles)
SELECT MAX(latest_date) AS data_as_of,
       ROUND(MAX(IF(commodity = 'Crude oil, Brent', latest_price, NULL)), 2) AS brent_usd_bbl,
       ROUND(MAX(IF(commodity = 'Crude oil, Brent', yoy_pct, NULL)), 1)      AS brent_yoy_pct,
       ROUND(MAX(IF(commodity = 'Gold', latest_price, NULL)), 0)             AS gold_usd_toz,
       ROUND(MAX(IF(commodity = 'Gold', yoy_pct, NULL)), 1)                  AS gold_yoy_pct
FROM workspace.commodities.gold_latest_snapshot;

-- name: price_history  (line: x=date, y=price, color=commodity; add filters on commodity and commodity_group)
SELECT date, commodity, commodity_group, unit, price, ma_12m
FROM workspace.commodities.gold_monthly_metrics
WHERE date >= DATE'2000-01-01';

-- name: top_movers  (bar: x=yoy_pct, y=commodity)
SELECT commodity, commodity_group, latest_price, unit, yoy_pct
FROM workspace.commodities.gold_latest_snapshot
WHERE is_active AND yoy_pct IS NOT NULL
ORDER BY ABS(yoy_pct) DESC
LIMIT 15;

-- name: yoy_heatmap  (heatmap: x=year, y=commodity_group, color=avg_yoy_pct)
SELECT year, commodity_group, ROUND(AVG(yoy_pct), 1) AS avg_yoy_pct
FROM workspace.commodities.gold_monthly_metrics
WHERE year >= 2005 AND yoy_pct IS NOT NULL
GROUP BY year, commodity_group;

-- name: forecast_vs_actual  (line: x=date, y=price, color=series; filter on commodity)
SELECT date, commodity, 'actual' AS series, price
FROM workspace.commodities.silver_prices
WHERE date >= DATE'2018-01-01'
  AND commodity IN (SELECT commodity FROM workspace.commodities.gold_forecast)
UNION ALL
SELECT forecast_date, commodity, 'forecast', forecast_price
FROM workspace.commodities.gold_forecast;

-- name: snapshot  (table)
SELECT commodity, commodity_group, unit, latest_date, latest_price, mom_pct, yoy_pct,
       change_5y_pct, all_time_high, pct_from_ath
FROM workspace.commodities.gold_latest_snapshot
WHERE is_active
ORDER BY commodity_group, commodity;
