"""Chronological history features; all transformations use explicit input allowlists."""
from functools import reduce
from pyspark.sql import functions as F

IDENTITY = ["FlightDate", "Reporting_Airline", "Flight_Number_Reporting_Airline", "Origin", "Dest", "CRSDepTime"]
CATEGORICAL = ["Reporting_Airline", "Origin", "Dest"]
NUMERIC = ["dep_hour", "dep_sin", "dep_cos", "arr_sin", "arr_cos", "weekday_sin", "weekday_cos", "day_of_month", "Distance", "CRSElapsedTime"]
HISTORY_KEYS = {"origin": ["Origin"], "dest": ["Dest"], "carrier": ["Reporting_Airline"], "route": ["Origin", "Dest"]}
HISTORY_NUMERIC = [f"hist_{key}_{suffix}" for key in HISTORY_KEYS for suffix in ["rate", "log_count", "missing"]]
BASE_INPUTS = [f"{key}_idx" for key in CATEGORICAL] + NUMERIC
ENHANCED_INPUTS = BASE_INPUTS + HISTORY_NUMERIC


def assert_feature_columns(columns):
    unknown = set(columns) - set(ENHANCED_INPUTS)
    if unknown:
        raise ValueError(f"Unapproved feature columns: {sorted(unknown)}")


def load_arrivals(spark, base="hdfs://127.0.0.1:19000/flight-risk/runs"):
    frames = [spark.read.parquet(f"{base}/2024-{i:02}/silver") for i in range(1, 7)]
    frame = reduce(lambda a, b: a.unionByName(b), frames)
    # Actual delays/status are never retained in this model frame.
    return frame.where("arrival_valid").select(*IDENTITY, "CRSArrTime", "Distance", "CRSElapsedTime", "DayOfWeek", "month", F.col("ArrDel15").alias("label"))


def planned_features(frame):
    def minutes(name):
        return F.when(F.col(name) == 2400, F.lit(0)).when(
            F.col(name).between(0, 2359) & ((F.col(name) % 100) < 60),
            F.floor(F.col(name) / 100) * 60 + F.col(name) % 100)
    frame = frame.withColumn("dep_minutes", minutes("CRSDepTime")).withColumn("arr_minutes", minutes("CRSArrTime"))
    frame = frame.withColumn("model_eligible", F.col("dep_minutes").isNotNull() & F.col("arr_minutes").isNotNull()
                             & F.col("Distance").isNotNull() & ~F.isnan("Distance") & (F.col("Distance") > 0) & (F.col("Distance") != float("inf"))
                             & F.col("CRSElapsedTime").isNotNull() & ~F.isnan("CRSElapsedTime") & (F.col("CRSElapsedTime") > 0) & (F.col("CRSElapsedTime") != float("inf"))
                             & F.col("DayOfWeek").isin(*range(1, 8)))
    frame = frame.withColumn("dep_hour", F.floor(F.col("dep_minutes") / 60).cast("int"))
    for prefix, value, period in [("dep", F.col("dep_minutes"), 1440), ("arr", F.col("arr_minutes"), 1440), ("weekday", F.col("DayOfWeek") - 1, 7)]:
        angle = value * (2 * 3.141592653589793 / period)
        frame = frame.withColumn(prefix + "_sin", F.sin(angle)).withColumn(prefix + "_cos", F.cos(angle))
    return (frame.withColumn("day_of_month", F.dayofmonth("FlightDate"))
            .withColumn("flight_id", F.sha2(F.concat_ws("|", *[F.col(name).cast("string") for name in IDENTITY]), 256)))


def cutoff_for(month):
    if month in {"2024-05", "2024-06"}:
        return "2024-04"
    year, value = month.split("-")
    return f"{year}-{int(value)-1:02}"


def add_history(target, arrivals, cutoff, alpha=100.0):
    if alpha <= 0:
        raise ValueError("Smoothing strength must be positive")
    minimum_target = target.agg(F.min("month")).first()[0]
    if minimum_target is None or cutoff >= minimum_target:
        raise ValueError("History cutoff must precede every target month")
    history = arrivals.where(F.col("month") <= cutoff)
    prior = history.agg(F.avg("label").alias("rate"), F.max("month").alias("max_month"), F.count("*").alias("n")).first()
    if not prior.n or prior.max_month > cutoff:
        raise ValueError("Empty or invalid history snapshot")
    target = target.withColumn("history_max_month", F.lit(prior.max_month)).withColumn("history_cutoff_month", F.lit(cutoff))
    target = target.withColumn("hist_global_rate", F.lit(float(prior.rate)))
    for name, keys in HISTORY_KEYS.items():
        count, positives = f"hist_{name}_count", f"hist_{name}_positives"
        table = history.groupBy(keys).agg(F.count("*").alias(count), F.sum("label").alias(positives))
        target = target.join(F.broadcast(table), keys, "left").fillna({count: 0, positives: 0.0})
        target = target.withColumn(f"hist_{name}_rate", (F.col(positives) + alpha * prior.rate) / (F.col(count) + alpha))
        target = target.withColumn(f"hist_{name}_log_count", F.log1p(F.col(count)))
        target = target.withColumn(f"hist_{name}_missing", (F.col(count) == 0).cast("double"))
        target = target.drop(positives)
    return target


def add_baseline(target, training_arrivals, min_support=100):
    prior = float(training_arrivals.agg(F.avg("label")).first()[0])
    result = target
    for name, keys in [("pair", ["Reporting_Airline", "Origin"]), ("origin", ["Origin"]), ("carrier", ["Reporting_Airline"])]:
        table = training_arrivals.groupBy(keys).agg(F.count("*").alias(f"b0_{name}_n"), F.avg("label").alias(f"b0_{name}_rate"))
        result = result.join(F.broadcast(table), keys, "left")
    return result.withColumn("score_B0", F.coalesce(*[F.when(F.col(f"b0_{name}_n") >= min_support, F.col(f"b0_{name}_rate")) for name in ["pair", "origin", "carrier"]], F.lit(prior)))
