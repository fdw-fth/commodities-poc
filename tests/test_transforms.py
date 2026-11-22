"""Runs the exact SQL from src/transforms.py on local Spark with ANSI mode on."""
import pytest

pytest.importorskip("pyspark")

from transforms import (  # noqa: E402
    comment_on_table_sql,
    gold_latest_snapshot_sql,
    gold_monthly_metrics_sql,
    silver_prices_sql,
)


def test_comment_escapes_quotes():
    sql = comment_on_table_sql("db.prices", "Brent's monthly price")
    assert sql == "COMMENT ON TABLE db.prices IS 'Brent''s monthly price'"


@pytest.fixture(scope="module")
def tables(spark, bronze_pdf):
    """Temp views bronze -> silver -> metrics -> snapshot, built with the production SQL."""
    all_strings = ", ".join(f"{col} STRING" for col in bronze_pdf.columns)
    old_batch = bronze_pdf.assign(ingested_at="2000-01-01T00:00:00Z", raw_value="999999")
    spark.createDataFrame(old_batch, all_strings).unionByName(spark.createDataFrame(bronze_pdf, all_strings)) \
         .createOrReplaceTempView("bronze")
    spark.sql(silver_prices_sql("bronze")).cache().createOrReplaceTempView("silver")
    spark.sql(gold_monthly_metrics_sql("silver")).cache().createOrReplaceTempView("metrics")
    spark.sql(gold_latest_snapshot_sql("silver", "metrics")).createOrReplaceTempView("snapshot")
    return spark


def value(spark, table: str, column: str, commodity: str, date: str):
    """One cell for (commodity, month)."""
    return spark.sql(f"SELECT {column} FROM {table} "
                     f"WHERE commodity = '{commodity}' AND date = DATE'{date}'").first()[0]


def test_silver(tables):
    silver = tables.table("silver")
    assert silver.filter("price = 999999").count() == 0             # only the latest batch
    assert silver.filter("price IS NULL").count() == 0              # '..' dropped
    assert silver.count() == silver.select("commodity", "date").distinct().count()
    assert dict(silver.dtypes)["date"] == "date"


def test_groups(tables):
    group = dict(tables.sql("SELECT DISTINCT commodity, commodity_group FROM silver").collect())
    assert (group["Crude oil, Brent"], group["Palm oil"], group["Tin"], group["Gold"]) == \
           ("Energy", "Oils & meals", "Base metals", "Precious metals")
    assert "Other" not in group.values()


def test_yoy_and_gaps(tables):
    now, year_ago = (value(tables, "silver", "price", "Gold", d) for d in ("2020-05-01", "2019-05-01"))
    yoy = value(tables, "metrics", "yoy_pct", "Gold", "2020-05-01")
    assert yoy == pytest.approx(100 * (now / year_ago - 1), abs=0.01)
    # Cocoa 2010-06 is missing, so 2010-07 has no month-over-month change
    assert value(tables, "metrics", "mom_pct", "Cocoa", "2010-07-01") is None


def test_snapshot(tables):
    snap = {row.commodity: row for row in tables.table("snapshot").collect()}
    assert len(snap) == 32
    assert snap["Coal, Australian"].is_active is False             # discontinued in the fixture
    assert snap["Gold"].is_active and snap["Gold"].pct_from_ath <= 0
