#!/usr/bin/env python3
"""
Laptop-side helper (standard library + Databricks CLI).

  python scripts/poc.py download          # World Bank Pink Sheet -> data/
  python scripts/poc.py upload            # create schema + volume if missing, upload the file
  python scripts/poc.py sql "SELECT ..."  # run SQL on the workspace SQL warehouse
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

CATALOG, SCHEMA, VOLUME = "workspace", "commodities", "raw"
FILE = "CMO-Historical-Data-Monthly.xlsx"
LOCAL = Path(__file__).resolve().parents[1] / "data" / FILE
PAGE = "https://www.worldbank.org/en/research/commodity-markets"
FALLBACK = f"https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/{FILE}"


def cli(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    exe = shutil.which("databricks") or sys.exit("Install the Databricks CLI first: https://docs.databricks.com/dev-tools/cli/install.html")
    res = subprocess.run([exe, *args], text=True, capture_output=True)
    if check and res.returncode != 0:
        sys.exit(f"databricks {' '.join(args)} failed:\n{res.stderr or res.stdout}")
    return res


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def download() -> None:
    try:  # the link changes yearly, so look it up on the commodities page first
        html = fetch(PAGE).decode("utf-8", "ignore")
        url = re.findall(r'https?://thedocs\.worldbank\.org/[^"\'\s<>]*' + FILE, html)[0]
    except Exception:
        url = FALLBACK
    print("Downloading", url)
    try:
        data = fetch(url)
    except Exception as exc:
        sys.exit(f"Download failed ({exc}). Get 'Monthly prices (XLS)' from "
                 f"https://www.worldbank.org/commodities and save it as {LOCAL}")
    if not data.startswith(b"PK"):  # .xlsx is a zip file
        sys.exit("That wasn't an .xlsx file. Download it manually (see above).")
    LOCAL.parent.mkdir(exist_ok=True)
    LOCAL.write_bytes(data)
    print(f"Saved {LOCAL} ({len(data) / 1e6:.1f} MB)")


def upload() -> None:
    if not LOCAL.exists():
        sys.exit("Run `python scripts/poc.py download` first.")
    if cli("schemas", "get", f"{CATALOG}.{SCHEMA}", check=False).returncode:
        cli("schemas", "create", SCHEMA, CATALOG)
    if cli("volumes", "read", f"{CATALOG}.{SCHEMA}.{VOLUME}", check=False).returncode:
        cli("volumes", "create", CATALOG, SCHEMA, VOLUME, "MANAGED")
    target = f"dbfs:/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}/{FILE}"
    cli("fs", "cp", str(LOCAL), target, "--overwrite")
    print("Uploaded to", target)


def sql(statement: str) -> None:
    warehouses = json.loads(cli("warehouses", "list", "-o", "json").stdout or "[]")
    if not warehouses:
        sys.exit("No SQL warehouse found. Open 'SQL Warehouses' in the UI once.")
    body = {"warehouse_id": warehouses[0]["id"], "statement": statement,
            "wait_timeout": "50s", "on_wait_timeout": "CONTINUE"}
    res = json.loads(cli("api", "post", "/api/2.0/sql/statements", "--json", json.dumps(body)).stdout)
    while res["status"]["state"] in ("PENDING", "RUNNING"):
        time.sleep(3)
        res = json.loads(cli("api", "get", f"/api/2.0/sql/statements/{res['statement_id']}").stdout)
    if res["status"]["state"] != "SUCCEEDED":
        sys.exit(res["status"].get("error", {}).get("message", res["status"]["state"]))
    print(" | ".join(c["name"] for c in res["manifest"]["schema"]["columns"]))
    for row in (res.get("result") or {}).get("data_array", [])[:50]:
        print(" | ".join("" if v is None else str(v) for v in row))


if __name__ == "__main__":
    cmd, *rest = sys.argv[1:] or ["help"]
    if cmd == "download":
        download()
    elif cmd == "upload":
        upload()
    elif cmd == "sql" and rest:
        sql(" ".join(rest))
    else:
        print(__doc__)
