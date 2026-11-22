def test_shape(bronze_pdf):
    assert list(bronze_pdf.columns) == ["period", "commodity", "unit", "raw_value", "source_file", "ingested_at"]
    assert bronze_pdf["commodity"].nunique() == 32
    assert (bronze_pdf["period"].min(), bronze_pdf["period"].max()) == ("1990M01", "2026M10")


def test_cleaning(bronze_pdf):
    units = dict(zip(bronze_pdf["commodity"], bronze_pdf["unit"]))
    assert "Crude oil, Brent" in units          # newline in the header collapsed
    assert units["Gold"] == "$/troy oz"         # parentheses stripped
    wti = bronze_pdf.query("commodity == 'Crude oil, WTI' and period == '1990M01'")
    assert wti["raw_value"].iloc[0] == ".."     # missing values kept raw for bronze


def test_values_are_plain_strings(bronze_pdf):
    assert all(v is None or isinstance(v, str) for v in bronze_pdf.to_numpy().ravel())
