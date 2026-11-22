"""Runs the exact SQL from src/transforms.py on local Spark with ANSI mode on."""
import pytest

pytest.importorskip("pyspark")

from transforms import gold_latest_snapshot_sql, gold_monthly_metrics_sql, silver_prices_sql  # noqa: E402


@pytest.fixture(scope="module")
def t(spark, bronze_pdf):
    ddl = ", ".join(f"{c} STRING" for c in bronze_pdf.columns)
    old_batch = bronze_pdf.assign(ingested_at="2000-01-01T00:00:00Z", raw_value="999999")
    spark.createDataFrame(old_batch, ddl).unionByName(spark.createDataFrame(bronze_pdf, ddl)) \
         .createOrReplaceTempView("bronze")
    spark.sql(silver_prices_sql("bronze")).cache().createOrReplaceTempView("silver")
    spark.sql(gold_monthly_metrics_sql("silver")).cache().createOrReplaceTempView("metrics")
    spark.sql(gold_latest_snapshot_sql("silver", "metrics")).createOrReplaceTempView("snapshot")
    return spark


def test_silver(t):
    s = t.table("silver")
    assert s.filter("price = 999999").count() == 0                 # only the latest batch
    assert s.filter("price IS NULL").count() == 0                   # '..' dropped
    assert s.count() == s.select("commodity", "date").distinct().count()
    assert dict(s.dtypes)["date"] == "date"


def test_groups(t):
    g = dict(t.sql("SELECT DISTINCT commodity, commodity_group FROM silver").collect())
    assert (g["Crude oil, Brent"], g["Palm oil"], g["Tin"], g["Gold"]) == \
           ("Energy", "Oils & meals", "Base metals", "Precious metals")
    assert "Other" not in g.values()


def test_yoy_and_gaps(t):
    price = lambda d: t.sql(f"SELECT price FROM silver WHERE commodity='Gold' AND date=DATE'{d}'").first()[0]  # noqa: E731
    yoy = t.sql("SELECT yoy_pct FROM metrics WHERE commodity='Gold' AND date=DATE'2020-05-01'").first()[0]
    assert yoy == pytest.approx(100 * (price("2020-05-01") / price("2019-05-01") - 1), abs=0.01)
    # Cocoa 2010-06 is missing, so 2010-07 has no month-over-month change
    assert t.sql("SELECT mom_pct FROM metrics WHERE commodity='Cocoa' AND date=DATE'2010-07-01'").first()[0] is None


def test_snapshot(t):
    snap = {r.commodity: r for r in t.table("snapshot").collect()}
    assert len(snap) == 32
    assert snap["Coal, Australian"].is_active is False             # discontinued in the fixture
    assert snap["Gold"].is_active and snap["Gold"].pct_from_ath <= 0
