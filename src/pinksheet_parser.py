"""
Parse the World Bank Pink Sheet monthly file (CMO-Historical-Data-Monthly.xlsx, sheet "Monthly Prices").
Plain module, used by the bronze notebook and by tests/test_parser.py.

The layout is detected, not hard-coded: the first row whose first cell looks like "1960M01" starts the data,
the row above it holds units ("($/bbl)") and the row above that holds commodity names.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

import pandas as pd

PERIOD_RE = re.compile(r"^\d{4}M\d{2}$")


def _clean(value) -> str | None:
    """Collapse whitespace/newlines; None for empty cells."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return " ".join(str(value).split()) or None


def parse_monthly_prices(path: str, sheet_name: str = "Monthly Prices") -> pd.DataFrame:
    """Return a long, all-string DataFrame: period, commodity, unit, raw_value, source_file, ingested_at."""
    raw = pd.read_excel(path, sheet_name=sheet_name, header=None, dtype=str, engine="openpyxl")
    is_data = raw.iloc[:, 0].map(_clean).fillna("").str.match(PERIOD_RE)
    if not is_data.any():
        raise ValueError(f"No '1960M01'-style rows in sheet '{sheet_name}'; the layout may have changed.")
    first = int(is_data.idxmax())
    names, units = raw.iloc[first - 2], raw.iloc[first - 1]

    cols = {c: (_clean(names[c]), (_clean(units[c]) or "").strip("()") or None)
            for c in raw.columns[1:] if _clean(names[c])}

    long = raw.loc[is_data, [raw.columns[0], *cols]].melt(id_vars=raw.columns[0], var_name="col",
                                                          value_name="raw_value")
    out = pd.DataFrame({
        "period": long.iloc[:, 0].map(_clean),
        "commodity": long["col"].map(lambda c: cols[c][0]),
        "unit": long["col"].map(lambda c: cols[c][1]),
        "raw_value": long["raw_value"].map(_clean),
        "source_file": str(path).rsplit("/", 1)[-1],
        "ingested_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    return out.astype(object).where(out.notna(), None).reset_index(drop=True)


def summarize(df: pd.DataFrame) -> str:
    values = pd.to_numeric(df["raw_value"], errors="coerce")
    return (f"rows={len(df):,} commodities={df['commodity'].nunique()} "
            f"periods={df['period'].min()}..{df['period'].max()} values={int(values.notna().sum()):,}")
