"""Prespecified Spark experiment with resumable phases and locked validation selection."""
import argparse
from array import array
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from pyspark import StorageLevel
from pyspark.ml import Pipeline, PipelineModel
from pyspark.ml.classification import LogisticRegression, LogisticRegressionModel, RandomForestClassifier, RandomForestClassificationModel
from pyspark.ml.feature import StringIndexer, OneHotEncoder, VectorAssembler
from pyspark.sql import SparkSession, functions as F
from ml.features import (load_arrivals, planned_features, add_history, add_baseline, cutoff_for,
                         assert_feature_columns, BASE_INPUTS, ENHANCED_INPUTS, CATEGORICAL, NUMERIC)
from ml.metrics import choose_threshold, evaluate
from ml.spark_compat import vector_to_array

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "ml/experiment.json"
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
CONFIG_HASH = hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest()
OUT = ROOT / "artifacts/ml" / CONFIG["version"]
HDFS = "hdfs://127.0.0.1:19000/flight-risk/ml/" + CONFIG["version"]


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def progress(event, **values):
    record = {"event": event, "utc": datetime.now(timezone.utc).isoformat(), **values}
    print(json.dumps(record, ensure_ascii=False), flush=True)
    save_json(OUT / "progress.json", record)


def check_config(record):
    if record.get("config_sha256") != CONFIG_HASH:
        raise ValueError("Configuration changed; use a new version instead of mixing experiments")


def prepare(spark):
    assert_feature_columns(BASE_INPUTS)
    assert_feature_columns(ENHANCED_INPUTS)
    started = time.perf_counter()
    arrivals = load_arrivals(spark)
    planned = planned_features(arrivals)
    quality = [row.asDict() for row in planned.groupBy("month", "model_eligible").count().orderBy("month", "model_eligible").collect()]
    progress("source_audit", quality=quality)
    training_history = arrivals.where(F.col("month").isin(CONFIG["baseline_history_months"]))
    for month in CONFIG["train_months"] + [CONFIG["validation_month"], CONFIG["test_month"]]:
        target = planned.where((F.col("month") == month) & F.col("model_eligible"))
        frame = add_history(target, arrivals, cutoff_for(month), CONFIG["smoothing_strength"])
        if month in {CONFIG["validation_month"], CONFIG["test_month"]}:
            frame = add_baseline(frame, training_history, CONFIG["baseline_min_support"])
        else:
            frame = frame.withColumn("score_B0", F.lit(None).cast("double"))
        # Materialize before model fitting. History metadata accompanies every row.
        keep = ["flight_id", "FlightDate", "month", "Reporting_Airline", "Flight_Number_Reporting_Airline", "Origin", "Dest", "CRSDepTime", "CRSArrTime", "label", "history_max_month", "history_cutoff_month", "hist_global_rate", "score_B0"]
        keep += NUMERIC + [name for name in frame.columns if name.startswith("hist_") and name not in keep]
        keep = list(dict.fromkeys(keep))
        frame.select(*keep).drop("month").write.mode("overwrite").parquet(f"{HDFS}/features/month={month}")
        progress("history_written", month=month, cutoff=cutoff_for(month))
    features = spark.read.parquet(HDFS + "/features")
    training = features.where(F.col("month").isin(CONFIG["train_months"]))
    fit_months = sorted(row.month for row in training.select("month").distinct().collect())
    if fit_months != CONFIG["train_months"]:
        raise ValueError("Unexpected preprocessing fit cohort")
    history_names = [name for name in features.columns if name.startswith("hist_")]
    evaluation_features = features.where(F.col("month").isin(CONFIG["validation_month"], CONFIG["test_month"]))
    inconsistent_snapshots = evaluation_features.groupBy(*CATEGORICAL).agg(F.countDistinct(F.struct(*history_names)).alias("variants")).where("variants > 1").count()
    if inconsistent_snapshots:
        raise ValueError("May/June shared entities have inconsistent frozen history")
    index_columns = [key + "_idx" for key in CATEGORICAL]
    onehot_columns = [key + "_onehot" for key in CATEGORICAL]
    pipeline = Pipeline(stages=[
        StringIndexer(inputCols=CATEGORICAL, outputCols=index_columns, handleInvalid="keep", stringOrderType="alphabetAsc"),
        OneHotEncoder(inputCols=index_columns, outputCols=onehot_columns, dropLast=False, handleInvalid="keep"),
        VectorAssembler(inputCols=onehot_columns + NUMERIC, outputCol="lr_features"),
        VectorAssembler(inputCols=BASE_INPUTS, outputCol="base_features"),
        VectorAssembler(inputCols=ENHANCED_INPUTS, outputCol="enhanced_features"),
    ])
    preprocessing = pipeline.fit(training)
    preprocessing.write().overwrite().save(HDFS + "/preprocessing")
    indexed = preprocessing.transform(features)
    max_categories = max(len(labels)+1 for labels in preprocessing.stages[0].labelsArray)
    if max_categories > CONFIG["forest_fixed"]["maxBins"]:
        raise ValueError("Prespecified RF maxBins cannot encode all training categories")
    indexed.write.mode("overwrite").partitionBy("month").parquet(HDFS + "/encoded")
    snapshots = [r.asDict() for r in indexed.groupBy("month", "history_cutoff_month", "history_max_month").agg(F.count("*").alias("count"), F.sum("label").cast("long").alias("positives")).orderBy("month").collect()]
    if any(r["history_max_month"] > r["history_cutoff_month"] or r["history_cutoff_month"] >= r["month"] for r in snapshots):
        raise ValueError("Temporal leakage audit failed")
    category_audit = {}
    for month in [CONFIG["validation_month"], CONFIG["test_month"]]:
        row = indexed.where(F.col("month") == month).agg(*[F.sum((F.col(column) == len(labels)).cast("long")).alias(key) for key, column, labels in zip(CATEGORICAL, index_columns, preprocessing.stages[0].labelsArray)]).first()
        category_audit[month] = row.asDict()
    manifests = []
    for file in sorted((ROOT / "data/raw/manifests").glob("2024-0[1-6].json")):
        source = json.loads(file.read_text(encoding="utf-8"))
        manifests.append({key: source[key] for key in ["month", "source_url", "archive_sha256", "csv_sha256", "rows"]})
    if len(manifests) != 6:
        raise ValueError("Six source manifests required for traceability")
    audit = {"config_sha256": CONFIG_HASH, "configuration": CONFIG, "quality": quality, "snapshots": snapshots,
             "source_manifests": manifests, "python_version": sys.version, "numpy_version": np.__version__,
             "code_sha256": {file: hashlib.sha256((ROOT / "ml" / file).read_bytes()).hexdigest() for file in ["features.py", "metrics.py", "run_experiment.py"]},
             "max_training_categories_including_unknown": max_categories, "unknown_category_counts": category_audit,
             "base_vector_inputs": BASE_INPUTS, "enhanced_vector_inputs": ENHANCED_INPUTS,
             "lr_vector_inputs": onehot_columns + NUMERIC, "preprocessor_fit_months": fit_months,
             "may_june_inconsistent_history_groups": inconsistent_snapshots,
             "spark_master": spark.sparkContext.master, "spark_version": spark.version,
             "application_id": spark.sparkContext.applicationId, "prepare_seconds": time.perf_counter()-started}
    save_json(OUT / "feature_audit.json", audit)
    progress("prepare_complete", seconds=audit["prepare_seconds"], snapshots=snapshots)


def read_encoded(spark):
    audit = json.loads((OUT / "feature_audit.json").read_text(encoding="utf-8"))
    check_config(audit)
    return spark.read.parquet(HDFS + "/encoded")


def estimator(code, candidate):
    if code == "B1":
        return LogisticRegression(featuresCol="lr_features", labelCol="label", **CONFIG["logistic_fixed"], **candidate)
    return RandomForestClassifier(featuresCol="base_features" if code == "B2" else "enhanced_features", labelCol="label", seed=CONFIG["seed"], **CONFIG["forest_fixed"], **candidate)


def score_arrays(frame, score_column):
    labels, scores = array("b"), array("d")
    for row in frame.select("label", score_column).toLocalIterator():
        labels.append(int(row[0]))
        scores.append(float(row[1]))
    return np.frombuffer(labels, dtype=np.int8), np.frombuffer(scores, dtype=np.float64)


def pilot(spark):
    frame = read_encoded(spark)
    training = frame.where(F.col("month").isin(CONFIG["train_months"]))
    validation = frame.where(F.col("month") == CONFIG["validation_month"])
    # Hash-defined smoke sample; performance is never used to choose parameters.
    training = training.where(F.pmod(F.xxhash64("flight_id"), F.lit(1000)) < 12).cache()
    validation = validation.where(F.pmod(F.xxhash64("flight_id"), F.lit(1000)) < 9).cache()
    counts = {"training": training.count(), "validation": validation.count()}
    timings = []
    for code, parameters in [("B1", CONFIG["logistic_candidates"][0]), ("B3", CONFIG["forest_candidates"][0])]:
        start = time.perf_counter()
        model = estimator(code, parameters).fit(training)
        fit_seconds = time.perf_counter()-start
        start = time.perf_counter()
        scored = model.transform(validation).select(vector_to_array("probability")[1].alias("score"))
        # Force probability evaluation, not just count (Catalyst could prune predictions).
        summary = scored.agg(F.count("*"), F.min("score"), F.max("score")).first()
        timings.append({"model": code, "parameters": parameters, "fit_seconds": fit_seconds, "score_seconds": time.perf_counter()-start, "scored_rows": summary[0]})
        progress("pilot_model_complete", **timings[-1])
    record = {"config_sha256": CONFIG_HASH, "rows": counts, "timings": timings, "used_for_selection": False}
    save_json(OUT / "pilot.json", record)
    training.unpersist(); validation.unpersist()
    progress("pilot_complete", **record)


def formal(spark):
    frame = read_encoded(spark)
    training = frame.where(F.col("month").isin(CONFIG["train_months"]))
    validation = frame.where(F.col("month") == CONFIG["validation_month"])
    counts = {"train": training.count(), "validation": validation.count()}
    all_trials = []
    baseline_path = OUT / "trials/B0.json"
    if baseline_path.exists():
        baseline = json.loads(baseline_path.read_text(encoding="utf-8")); check_config(baseline)
    else:
        labels, scores = score_arrays(validation, "score_B0")
        threshold = choose_threshold(labels, scores)
        baseline = {"config_sha256": CONFIG_HASH, "model": "B0", "candidate": 0, "parameters": {"min_support": CONFIG["baseline_min_support"], "history_months": CONFIG["baseline_history_months"]}, "validation": evaluate(labels, scores, threshold), "fit_seconds": 0, "rows": counts}
        save_json(baseline_path, baseline)
    all_trials.append(baseline)
    selected = {"B0": baseline}
    for code in ["B1", "B2", "B3"]:
        candidates = CONFIG["logistic_candidates"] if code == "B1" else CONFIG["forest_candidates"]
        trials = []
        for index, parameters in enumerate(candidates):
            trial_path = OUT / f"trials/{code}-c{index}.json"
            if trial_path.exists():
                record = json.loads(trial_path.read_text(encoding="utf-8")); check_config(record)
                progress("resume_completed_trial", model=code, candidate=index)
            else:
                progress("fit_start", model=code, candidate=index, parameters=parameters, rows=counts)
                start = time.perf_counter()
                model = estimator(code, parameters).fit(training)
                fit_seconds = time.perf_counter()-start
                model_path = f"{HDFS}/models/{code}-c{index}"
                model.write().overwrite().save(model_path)
                start = time.perf_counter()
                scored = model.transform(validation).withColumn("score", vector_to_array("probability")[1])
                labels, scores = score_arrays(scored, "score")
                threshold = choose_threshold(labels, scores)
                result = evaluate(labels, scores, threshold)
                np.savez_compressed(OUT / f"validation-{code}-c{index}.npz", labels=labels, scores=scores)
                record = {"config_sha256": CONFIG_HASH, "model": code, "candidate": index, "parameters": {**(CONFIG["logistic_fixed"] if code == "B1" else CONFIG["forest_fixed"]), **parameters}, "model_path": model_path, "fit_seconds": fit_seconds, "validation_seconds": time.perf_counter()-start, "validation": result, "rows": counts}
                record["num_features"] = int(model.numFeatures)
                if code == "B1":
                    record["iterations"] = int(model.summary.totalIterations)
                if code != "B1":
                    columns = BASE_INPUTS if code == "B2" else ENHANCED_INPUTS
                    record["feature_importance"] = dict(zip(columns, map(float, model.featureImportances.toArray())))
                save_json(trial_path, record)
                progress("trial_complete", model=code, candidate=index, fit_seconds=fit_seconds, validation_pr_auc=result["pr_auc"], validation_f1=result["f1"])
            trials.append(record)
        # Stable tie-break picks the first candidate. No test data consulted.
        selected[code] = max(trials, key=lambda item: item["validation"]["pr_auc"])
        all_trials.extend(trials)
    locked = {"config_sha256": CONFIG_HASH, "selection_data": "2024-05 only", "selected": selected,
              "recommended_model": max(selected, key=lambda code: selected[code]["validation"]["pr_auc"]),
              "trials": all_trials, "locked_at_utc": datetime.now(timezone.utc).isoformat(), "application_id": spark.sparkContext.applicationId, "spark_master": spark.sparkContext.master}
    save_json(OUT / "selection.json", locked)
    progress("validation_selection_locked", choices={code: item["candidate"] for code, item in selected.items()})


def error_groups(scored, threshold):
    prediction = F.col("score_B3") >= threshold
    frame = scored.withColumn("support_band", F.when(F.col("hist_route_count") == 0, "0").when(F.col("hist_route_count") < 100, "1-99").when(F.col("hist_route_count") < 1000, "100-999").otherwise("1000+"))
    result = {}
    for dimension in ["Origin", "dep_hour", "support_band"]:
        rows = frame.groupBy(dimension).agg(F.count("*").alias("n"), F.sum("label").alias("positives"), F.avg("score_B3").alias("mean_score"), F.avg(F.pow(F.col("score_B3")-F.col("label"), 2)).alias("brier"), F.sum(((F.col("label") == 1) & prediction).cast("long")).alias("tp"), F.sum(((F.col("label") == 0) & prediction).cast("long")).alias("fp"), F.sum(((F.col("label") == 1) & ~prediction).cast("long")).alias("fn"), F.sum(((F.col("label") == 0) & ~prediction).cast("long")).alias("tn")).orderBy(dimension).collect()
        result[dimension] = [row.asDict() for row in rows]
    return result


def export(spark):
    locked = json.loads((OUT / "selection.json").read_text(encoding="utf-8")); check_config(locked)
    frame = read_encoded(spark).where(F.col("month") == CONFIG["test_month"])
    for code in ["B1", "B2", "B3"]:
        selected = locked["selected"][code]
        cls = LogisticRegressionModel if code == "B1" else RandomForestClassificationModel
        model = cls.load(selected["model_path"])
        frame = model.transform(frame).withColumn("score_"+code, vector_to_array("probability")[1]).drop("probability", "rawPrediction", "prediction")
    columns = ["flight_id", "FlightDate", "Reporting_Airline", "Flight_Number_Reporting_Airline", "Origin", "Dest", "CRSDepTime", "CRSArrTime", "dep_hour", "Distance", "CRSElapsedTime", "label", "history_cutoff_month", "hist_route_count", "hist_origin_count", "hist_carrier_count", "hist_route_rate", "hist_origin_rate", "hist_carrier_rate"] + ["score_"+code for code in ["B0", "B1", "B2", "B3"]]
    frame.select(*columns).write.mode("overwrite").parquet(HDFS + "/scored_test")
    scored = spark.read.parquet(HDFS + "/scored_test")
    metrics = {}
    for code in ["B0", "B1", "B2", "B3"]:
        labels, scores = score_arrays(scored, "score_"+code)
        threshold = locked["selected"][code]["validation"]["threshold"]
        metrics[code] = evaluate(labels, scores, threshold)
        progress("test_evaluated", model=code, pr_auc=metrics[code]["pr_auc"], n=metrics[code]["n"])
    if len({value["n"] for value in metrics.values()}) != 1:
        raise ValueError("Test cohorts differ between models")
    groups = error_groups(scored, metrics["B3"]["threshold"])
    save_json(OUT / "error_groups.json", groups)
    dbpath = ROOT / "artifacts/predictions.sqlite"
    stage = dbpath.with_suffix(".building.sqlite")
    db = sqlite3.connect(stage)
    try:
        db.execute("PRAGMA cache_size=-131072")
        db.execute("PRAGMA temp_store=MEMORY")
        db.execute("DROP TABLE IF EXISTS predictions")
        types = ["TEXT PRIMARY KEY", "TEXT", "TEXT", "TEXT", "TEXT", "TEXT", "INTEGER", "INTEGER", "INTEGER", "REAL", "REAL", "INTEGER", "TEXT", "INTEGER", "INTEGER", "INTEGER", "REAL", "REAL", "REAL", "REAL", "REAL", "REAL", "REAL"]
        db.execute("CREATE TABLE predictions (" + ",".join(f'"{name}" {dtype}' for name, dtype in zip(columns, types)) + ")")
        def records():
            for row in scored.select(*columns).toLocalIterator():
                values = list(row); values[1] = values[1].isoformat(); values[11] = int(values[11]); yield values
        db.executemany("INSERT INTO predictions VALUES (" + ",".join("?" for _ in columns) + ")", records())
        db.execute("CREATE INDEX idx_scenario ON predictions(Origin,Dest,Reporting_Airline,FlightDate,CRSDepTime)")
        total = db.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
        if total != metrics["B3"]["n"]:
            raise ValueError("Prediction export count mismatch")
        db.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)")
        db.execute("INSERT OR REPLACE INTO metadata VALUES ('selection', ?)", (json.dumps(locked),))
        db.commit()
    finally:
        db.close()
    stage.replace(dbpath)
    # Deterministic illustrative cases, five per confusion category; not representative sampling.
    threshold = metrics["B3"]["threshold"]
    tagged = scored.withColumn("outcome", F.when((F.col("label") == 1) & (F.col("score_B3") >= threshold), "tp").when(F.col("label") == 1, "fn").when(F.col("score_B3") >= threshold, "fp").otherwise("tn"))
    cases = []
    for outcome in ["tp", "fp", "fn", "tn"]:
        for row in tagged.where(F.col("outcome") == outcome).orderBy("flight_id").limit(5).collect():
            record = row.asDict(); record["FlightDate"] = record["FlightDate"].isoformat(); cases.append(record)
    save_json(OUT / "cases.json", cases)
    audit = json.loads((OUT / "feature_audit.json").read_text(encoding="utf-8"))
    result = {"version": CONFIG["version"], "config_sha256": CONFIG_HASH, "configuration": CONFIG,
              "feature_audit": audit, "selection": locked, "test": metrics,
              "b3_minus_b2_pr_auc": metrics["B3"]["pr_auc"]-metrics["B2"]["pr_auc"],
              "exported_predictions": total, "application_id": spark.sparkContext.applicationId,
              "spark_master": spark.sparkContext.master, "finished_at_utc": datetime.now(timezone.utc).isoformat(),
              "limitations": ["Historical archive backtest, not reconstructed public-data availability", "Conditional on non-cancelled non-diverted flights", "One half-year split and one seed; no significance claim", "Gini importance is not causal explanation", "PR curve display is sampled; areas use full curves"]}
    save_json(OUT / "metrics.json", result)
    save_json(ROOT / "results/m3/metrics.json", result)
    save_json(ROOT / "results/m3/error_groups.json", groups)
    save_json(ROOT / "results/m3/cases.json", cases)
    progress("m3_complete", exported_predictions=total, b3_minus_b2_pr_auc=result["b3_minus_b2_pr_auc"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "pilot", "formal", "export"])
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    spark = (SparkSession.builder.appName("FlightRisk-M3-"+args.phase)
             .config("spark.sql.shuffle.partitions", "4").config("spark.sql.session.timeZone", "UTC")
             .config("spark.sql.adaptive.enabled", "false").getOrCreate())
    spark.sparkContext.setLogLevel("WARN")
    try:
        {"prepare": prepare, "pilot": pilot, "formal": formal, "export": export}[args.phase](spark)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
