import os
import pytest

pytestmark = pytest.mark.skipif(os.environ.get("FLIGHT_SPARK_TESTS") != "1", reason="Set FLIGHT_SPARK_TESTS=1 with Java")


def test_future_label_mutation_and_cutoff_guards():
    from pyspark.sql import SparkSession, functions as F
    from ml.features import add_history, cutoff_for, assert_feature_columns, ENHANCED_INPUTS
    from ml.spark_compat import vector_to_array
    from pyspark.ml.linalg import Vectors
    spark = SparkSession.builder.master("local[1]").appName("SyntheticHistoryLeakageTest").config("spark.ui.enabled", "false").getOrCreate()
    try:
        vectors = spark.createDataFrame([(Vectors.dense(.2, .8),), (Vectors.sparse(2, {1: 1.}),)], ["probability"])
        assert [r[0] for r in vectors.select(vector_to_array("probability")[1]).collect()] == [.8, 1.]
        history = spark.createDataFrame([
            ("2024-01", "AAA", "BBB", "AA", 0.), ("2024-02", "AAA", "BBB", "AA", 1.),
            ("2024-03", "AAA", "BBB", "AA", 0.), ("2024-04", "AAA", "BBB", "AA", 1.),
            ("2024-05", "AAA", "BBB", "AA", 0.), ("2024-06", "AAA", "BBB", "AA", 1.),
        ], "month string, Origin string, Dest string, Reporting_Airline string, label double")
        target = spark.createDataFrame([("2024-06", "AAA", "BBB", "AA"), ("2024-06", "CCC", "DDD", "BB")], "month string, Origin string, Dest string, Reporting_Airline string")
        original = add_history(target, history, cutoff_for("2024-06")).orderBy("Origin").collect()
        mutated = history.withColumn("label", F.when(F.col("month") >= "2024-05", 1-F.col("label")).otherwise(F.col("label")))
        changed = add_history(target, mutated, cutoff_for("2024-06")).orderBy("Origin").collect()
        assert original == changed
        assert original[0].hist_route_count == 4 and original[0].hist_route_rate == .5
        assert original[1].hist_route_missing == 1 and original[1].hist_route_count == 0
        assert original[1].hist_route_rate == .5
        assert original[0].history_max_month == "2024-04"
        assert cutoff_for("2024-02") == "2024-01"
        assert cutoff_for("2024-05") == cutoff_for("2024-06") == "2024-04"
        with pytest.raises(ValueError, match="precede"):
            add_history(target, history, "2024-06")
        assert_feature_columns(ENHANCED_INPUTS)
        with pytest.raises(ValueError, match="Unapproved"):
            assert_feature_columns(ENHANCED_INPUTS + ["ArrDelay"])
    finally:
        spark.stop()
