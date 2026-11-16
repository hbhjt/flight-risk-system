"""Independent streaming CSV reconciliation against the published aggregate database."""
import argparse
import csv
import json
import sqlite3
from collections import Counter
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", default="2024-01")
    parser.add_argument("--database", default="artifacts/flight.sqlite")
    parser.add_argument("--require-standalone", action="store_true")
    args = parser.parse_args()
    files = list(Path("data/raw/csv", args.month).glob("*.csv"))
    if len(files) != 1:
        raise ValueError("Expected one monthly CSV")
    counts = Counter()
    delay_sum = 0.0
    with files[0].open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            counts["planned"] += 1
            if float(row["Cancelled"]) == 1:
                counts["cancelled"] += 1
            elif float(row["Diverted"]) == 1:
                counts["diverted"] += 1
            elif row["ArrDel15"] in {"0.00", "1.00", "0", "1", "0.0", "1.0"}:
                counts["eligible"] += 1
                counts["delayed"] += int(float(row["ArrDel15"]))
                if row["ArrDelay"]:
                    counts["arr_delay_count"] += 1
                    delay_sum += float(row["ArrDelay"])
    with sqlite3.connect(args.database) as db:
        etl = json.loads(db.execute("SELECT value FROM metadata WHERE key='etl'").fetchone()[0])
        if etl["exact_duplicate_rows"] or etl["dispositions"].get("invalid_key_or_status", 0):
            raise ValueError("Independent verifier needs explicit adjustment for quarantined/duplicate records")
        if args.require_standalone:
            assert etl["spark_master"] == "spark://127.0.0.1:17077"
            assert etl["input"].startswith("hdfs://")
        for name in ["planned", "eligible", "delayed", "cancelled", "diverted", "arr_delay_count"]:
            actual = db.execute(f"SELECT SUM({name}) FROM aggregates WHERE month=?", (args.month,)).fetchone()[0]
            assert actual == counts[name], (name, actual, counts[name])
        actual_sum = db.execute("SELECT SUM(arr_delay_sum) FROM aggregates WHERE month=?", (args.month,)).fetchone()[0]
        assert abs(actual_sum - delay_sum) < 1e-6
    report = {"month": args.month, "counts": dict(counts), "arrival_delay_sum": delay_sum,
              "independent_csv_reconciliation": "passed", "spark_master": etl["spark_master"],
              "application_id": etl["application_id"]}
    Path("artifacts/reconciliation.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
