# Genie setup

Genie → New → "Commodities POC". Add `silver_prices`, `gold_monthly_metrics`, `gold_latest_snapshot`
and `gold_forecast` from `workspace.commodities`.

## Instructions

```
World Bank Pink Sheet monthly commodity prices, nominal USD, 1960 to present. `date` = first day of the month.
- Units differ by commodity (`unit` column). Never add or average prices across commodities; compare % changes.
- "Oil" means commodity = 'Crude oil, Brent' unless WTI or Dubai is named.
- For latest/current values use gold_latest_snapshot with is_active = true, and state the data month.
- yoy_pct and mom_pct are percentages; vol_12m_annualized is a fraction (×100 for %).
- gold_forecast is a simple statistical baseline; always say so.
```

## Sample questions

1. Which commodities rose the most over the last 12 months?
2. Show Brent crude since 2000 with its 12-month moving average.
3. How far is gold from its all-time high?
4. Which commodity group was most volatile in 2022?
5. What is the 12-month forecast for copper, and did it beat the naive baseline?
