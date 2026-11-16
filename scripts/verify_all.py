"""Independent native-Python reconciliation of all six raw files and monthly SQL totals."""
import csv
import json
import sqlite3
from collections import Counter
from pathlib import Path


def main():
    results = []
    with sqlite3.connect("artifacts/flight.sqlite") as db:
        etl = json.loads(db.execute("SELECT value FROM metadata WHERE key='etl'").fetchone()[0])
        assert len(etl["runs"]) == 6
        for report in etl["runs"]:
            assert report["exact_duplicate_rows"] == 0 and report["business_key_conflict_groups"] == 0
            assert not report["dispositions"].get("invalid_key_or_status")
        for month in etl["months"]:
            counts = Counter()
            delay_sum = 0.0
            files = list(Path("data/raw/csv", month).glob("*.csv"))
            assert len(files) == 1
            with files[0].open(encoding="utf-8-sig", newline="") as source:
                for row in csv.DictReader(source):
                    assert row["FlightDate"][:7] == month
                    counts["planned"] += 1
                    if float(row["Cancelled"]) == 1:
                        counts["cancelled"] += 1
                    elif float(row["Diverted"]) == 1:
                        counts["diverted"] += 1
                    elif row["ArrDel15"] and float(row["ArrDel15"]) in (0, 1):
                        counts["eligible"] += 1
                        counts["delayed"] += int(float(row["ArrDel15"]))
                        if row["ArrDelay"]:
                            counts["arr_delay_count"] += 1
                            delay_sum += float(row["ArrDelay"])
            for key, expected in counts.items():
                actual = db.execute(f"SELECT SUM({key}) FROM aggregates WHERE month=?", (month,)).fetchone()[0]
                assert actual == expected, (month, key, actual, expected)
            actual_sum = db.execute("SELECT SUM(arr_delay_sum) FROM aggregates WHERE month=?", (month,)).fetchone()[0]
            assert abs(actual_sum - delay_sum) < 1e-6
            result = {"month": month, "counts": dict(counts), "arr_delay_sum": delay_sum, "passed": True}
            results.append(result)
            print(json.dumps(result), flush=True)
    Path("artifacts/reconciliation-all.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
