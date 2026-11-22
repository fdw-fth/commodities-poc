"""
Build a small FAKE Pink Sheet workbook that mimics the real layout, so tests and CI
run without downloading anything. Values are synthetic random walks — not real prices.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from openpyxl import Workbook

COMMODITIES = [
    ("Crude oil, average", "$/bbl", 20), ("Crude oil,\nBrent", "$/bbl", 20),
    ("Crude oil, WTI", "$/bbl", 20), ("Coal, Australian", "$/mt", 40),
    ("Natural gas, US", "$/mmbtu", 2), ("Natural gas, Europe", "$/mmbtu", 3),
    ("Cocoa", "$/kg", 1.5), ("Coffee, Arabica", "$/kg", 3), ("Tea, avg 3 auctions", "$/kg", 2),
    ("Palm oil", "$/mt", 400), ("Soybeans", "$/mt", 250), ("Maize", "$/mt", 120),
    ("Rice, Thai 5%", "$/mt", 300), ("Wheat, US HRW", "$/mt", 150), ("Sugar, world", "$/kg", 0.3),
    ("Beef", "$/kg", 2.5), ("Cotton, A Index", "$/kg", 1.6), ("Rubber, TSR20", "$/kg", 1.2),
    ("Logs, Malaysian", "$/cubic meter", 250), ("Urea", "$/mt", 150), ("DAP", "$/mt", 200),
    ("Aluminum", "$/mt", 1500), ("Iron ore, cfr spot", "$/dmtu", 30), ("Copper", "$/mt", 2500),
    ("Lead", "$/mt", 700), ("Tin", "$/mt", 6000), ("Nickel", "$/mt", 8000), ("Zinc", "$/mt", 1000),
    ("Gold", "$/troy oz", 380), ("Silver", "$/troy oz", 5), ("Platinum", "$/troy oz", 450),
    ("Tobacco, US import u.v.", "$/mt", 3000),
]
DISCONTINUED = "Coal, Australian"   # stops in 2015 to exercise is_active
START_YEAR, END_YEAR, END_MONTH = 1990, 2026, 10


def periods():
    for y in range(START_YEAR, END_YEAR + 1):
        for m in range(1, 13):
            if (y, m) > (END_YEAR, END_MONTH):
                return
            yield f"{y}M{m:02d}"


def build(path: Path, seed: int = 42) -> Path:
    rng = np.random.default_rng(seed)
    wb = Workbook()
    ws = wb.active
    ws.title = "Monthly Prices"
    ws.append(["World Bank Commodity Price Data (The Pink Sheet)"])
    ws.append(["monthly prices in nominal US dollars, 1960 to present"])
    ws.append(["(monthly series are available only in nominal US dollars)"])
    ws.append(["Updated on November 04, 2026 (SYNTHETIC TEST FIXTURE)"])
    ws.append([None, *[name for name, _, _ in COMMODITIES]])
    ws.append([None, *[f"({unit})" for _, unit, _ in COMMODITIES]])

    plist = list(periods())
    paths = {}
    for name, _, start in COMMODITIES:
        steps = rng.normal(0.003, 0.05, len(plist))
        paths[name] = start * np.exp(np.cumsum(steps))

    for i, p in enumerate(plist):
        row = [p]
        for name, _, _ in COMMODITIES:
            year = int(p[:4])
            if name.startswith("Crude oil, WTI") and year < 1995:
                row.append("..")                       # series starts later
            elif name == DISCONTINUED and year > 2015:
                row.append("..")                       # discontinued series
            elif name == "Cocoa" and p == "2010M06":
                row.append("..")                       # one-off gap
            else:
                row.append(round(float(paths[name][i]), 4))
        ws.append(row)

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


if __name__ == "__main__":
    out = build(Path(__file__).parent / "fixtures" / "pinksheet_fixture.xlsx")
    print("wrote", out)
