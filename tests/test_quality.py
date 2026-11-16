"""Opt-in JVM integration checks against explicit synthetic edge cases."""
import os
import pytest

pytestmark = pytest.mark.skipif(os.environ.get("FLIGHT_SPARK_TESTS") != "1", reason="Set FLIGHT_SPARK_TESTS=1 with a Java runtime")


def test_status_partition_and_local_clock():
    from datetime import date
    from pyspark.sql import SparkSession
    from spark_jobs.etl import classify
    spark = SparkSession.builder.master("local[1]").appName("SyntheticQualityTest").config("spark.ui.enabled", "false").getOrCreate()
    try:
        schema = "FlightDate date, Reporting_Airline string, Origin string, Dest string, Flight_Number_Reporting_Airline string, CRSDepTime int, Cancelled double, Diverted double, ArrDel15 double"
        records = [
            (date(2024, 1, 1), "AA", "AAA", "BBB", "1", 2400, 0., 0., 1.),
            (date(2024, 1, 1), "AA", "AAA", "BBB", "2", 960, 0., 0., 0.),
            (date(2024, 1, 1), "AA", "AAA", "BBB", "3", 900, 1., 0., None),
            (date(2024, 1, 1), "AA", "AAA", "BBB", "4", 900, 0., 1., None),
            (date(2024, 1, 1), "AA", "AAA", "BBB", "5", 900, 0., 0., None),
            (None, "AA", "AAA", "BBB", "6", 900, 0., 0., 1.),
            (date(2024, 1, 1), "AA", "AAA", "BBB", "7", 900, None, 0., 1.),
        ]
        rows = {r.Flight_Number_Reporting_Airline: r for r in classify(spark.createDataFrame(records, schema)).collect()}
        assert rows["1"].dep_hour == 0 and rows["1"].arrival_valid
        assert rows["2"].dep_hour is None
        assert rows["3"].disposition == "cancelled" and not rows["3"].arrival_valid
        assert rows["4"].disposition == "diverted" and not rows["4"].arrival_valid
        assert rows["5"].disposition == "arrival_label_missing"
        assert rows["6"].disposition == "invalid_key_or_status"
        assert rows["7"].disposition == "invalid_key_or_status"
    finally:
        spark.stop()
