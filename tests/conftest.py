import sys
from pathlib import Path

import pytest

sys.path[:0] = [str(Path(__file__).parents[1] / "src"), str(Path(__file__).parent)]

from make_fixture import build  # noqa: E402
from pinksheet_parser import parse_monthly_prices  # noqa: E402


@pytest.fixture(scope="session")
def bronze_pdf(tmp_path_factory):
    return parse_monthly_prices(str(build(tmp_path_factory.mktemp("fx") / "fixture.xlsx")))


@pytest.fixture(scope="session")
def spark():
    pytest.importorskip("pyspark")
    from pyspark.sql import SparkSession
    s = (SparkSession.builder.master("local[2]")
         .config("spark.sql.ansi.enabled", "true")   # same as Databricks serverless
         .config("spark.sql.shuffle.partitions", "4")
         .config("spark.ui.enabled", "false").getOrCreate())
    yield s
    s.stop()
