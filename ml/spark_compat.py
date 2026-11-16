"""Minimal JVM vector conversion for the pinned Spark 3.5.8 runtime.

Uses the same JVM function as pyspark.ml.functions.vector_to_array, without
importing that module's unrelated pandas/Arrow UDF helpers. Standalone only.
Reference: Apache Spark 3.5.8 pyspark/ml/functions.py, vector_to_array.
"""
from pyspark import SparkContext
from pyspark.sql.column import Column, _to_java_column


def vector_to_array(column):
    context = SparkContext._active_spark_context
    if context is None or context._jvm is None:
        raise RuntimeError("An active classic Spark context is required")
    return Column(context._jvm.org.apache.spark.ml.functions.vector_to_array(_to_java_column(column), "float64"))
