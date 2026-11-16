"""Actual HDFS/Spark ETL with auditable, mutually exclusive dispositions."""
import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from pyspark.sql import SparkSession, functions as F

FIELDS = {
    "FlightDate": "date", "Reporting_Airline": "string", "Origin": "string", "Dest": "string",
    "Flight_Number_Reporting_Airline": "string", "CRSDepTime": "int", "CRSArrTime": "int",
    "Distance": "double", "CRSElapsedTime": "double", "ArrDel15": "double", "ArrDelay": "double",
    "Cancelled": "double", "Diverted": "double", "DayOfWeek": "int",
}
KEY = ["FlightDate", "Reporting_Airline", "Flight_Number_Reporting_Airline", "Origin", "Dest", "CRSDepTime"]


def classify(df):
    """Priority partitions records; invalid arrival labels remain in planned-flight counts."""
    critical = F.col("FlightDate").isNull()
    for name in ["Reporting_Airline", "Origin", "Dest", "Flight_Number_Reporting_Airline"]:
        critical = critical | F.col(name).isNull() | (F.trim(F.col(name)) == "")
    critical = critical | ~F.coalesce(F.col("Cancelled").isin(0.0, 1.0), F.lit(False))
    critical = critical | ~F.coalesce(F.col("Diverted").isin(0.0, 1.0), F.lit(False))
    return (df.withColumn("disposition", F.when(critical, "invalid_key_or_status")
            .when(F.col("Cancelled") == 1, "cancelled")
            .when(F.col("Diverted") == 1, "diverted")
            .when(F.col("ArrDel15").isin(0.0, 1.0), "arrival_valid")
            .otherwise("arrival_label_missing"))
            .withColumn("month", F.date_format("FlightDate", "yyyy-MM"))
            .withColumn("dep_hour", F.when(F.col("CRSDepTime") == 2400, 0)
                        .when((F.col("CRSDepTime").between(0, 2359)) & ((F.col("CRSDepTime") % 100) < 60),
                              F.floor(F.col("CRSDepTime") / 100).cast("int")))
            .withColumn("arrival_valid", F.col("disposition") == "arrival_valid")
            .withColumn("delayed", F.when(F.col("arrival_valid"), F.col("ArrDel15")).otherwise(0)))


def run(args):
    spark = (SparkSession.builder.appName("FlightRisk-ETL")
             .config("spark.sql.shuffle.partitions", "4")
             .config("spark.sql.session.timeZone", "UTC").getOrCreate())
    spark.sparkContext.setLogLevel("WARN")
    raw = spark.read.option("header", True).option("mode", "FAILFAST").csv(args.input)
    missing = set(FIELDS) - set(raw.columns)
    if missing:
        raise ValueError(f"Missing required source fields: {sorted(missing)}")
    # Remove only the empty trailing CSV header; preserve all substantive columns for exact deduplication.
    raw = raw.select([F.col(name) for name in raw.columns if name and not name.startswith("_c")]).cache()
    total = raw.count()
    exact = raw.dropDuplicates().cache()
    exact_count = exact.count()
    typed = exact.select([F.to_date(F.substring(F.col(name), 1, 10)).alias(name) if dtype == "date"
                          else F.col(name).cast(dtype).alias(name) for name, dtype in FIELDS.items()])
    classified = classify(typed).cache()
    conflict_groups = classified.groupBy(KEY).count().where("count > 1").count()
    # Conflicts must be investigated rather than silently selecting an outcome.
    if conflict_groups:
        raise ValueError(f"Found {conflict_groups} business-key conflicts; inspect before publishing")
    dispositions = {row["disposition"]: row["count"] for row in classified.groupBy("disposition").count().collect()}
    assert sum(dispositions.values()) == exact_count
    classified.write.mode("overwrite").partitionBy("month").parquet(args.output + "/silver")
    valid = classified.where("disposition != 'invalid_key_or_status'")
    group_cols = ["month", "Reporting_Airline", "Origin", "Dest", "DayOfWeek", "dep_hour"]
    aggregates = valid.groupBy(group_cols).agg(
        F.count("*").alias("planned"), F.sum(F.col("arrival_valid").cast("long")).alias("eligible"),
        F.sum("delayed").cast("long").alias("delayed"),
        F.sum("Cancelled").cast("long").alias("cancelled"), F.sum("Diverted").cast("long").alias("diverted"),
        F.sum(F.when(F.col("arrival_valid"), F.col("ArrDelay"))).alias("arr_delay_sum"),
        F.count(F.when(F.col("arrival_valid"), F.col("ArrDelay"))).alias("arr_delay_count"),
    ).cache()
    aggregates.write.mode("overwrite").parquet(args.output + "/gold/aggregates")
    dbpath = Path(args.database)
    dbpath.parent.mkdir(parents=True, exist_ok=True)
    stage = dbpath.with_suffix(".building.sqlite")
    with sqlite3.connect(stage) as db:
        db.execute("DROP TABLE IF EXISTS aggregates")
        db.execute("CREATE TABLE aggregates (month TEXT, carrier TEXT, origin TEXT, dest TEXT, weekday INTEGER, dep_hour INTEGER, planned INTEGER, eligible INTEGER, delayed INTEGER, cancelled INTEGER, diverted INTEGER, arr_delay_sum REAL, arr_delay_count INTEGER)")
        # Stream aggregate rows; do not collect raw flight data into driver memory.
        db.executemany("INSERT INTO aggregates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (tuple(row) for row in aggregates.toLocalIterator()))
        db.execute("CREATE INDEX IF NOT EXISTS idx_filters ON aggregates(month, carrier, origin)")
        db.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)")
        report = {"input": args.input, "output": args.output, "raw_rows": total,
                  "exact_duplicate_rows": total - exact_count, "distinct_rows": exact_count,
                  "business_key_conflict_groups": conflict_groups, "dispositions": dispositions,
                  "spark_master": spark.sparkContext.master, "spark_version": spark.version,
                  "application_id": spark.sparkContext.applicationId,
                  "generated_at_utc": datetime.now(timezone.utc).isoformat()}
        db.execute("INSERT OR REPLACE INTO metadata VALUES ('etl', ?)", (json.dumps(report),))
    stage.replace(dbpath)
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report), flush=True)
    spark.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="hdfs://127.0.0.1:19000/flight-risk")
    parser.add_argument("--database", default="artifacts/flight.sqlite")
    parser.add_argument("--report", default="artifacts/quality.json")
    run(parser.parse_args())
