"""Publish completed monthly Spark aggregates atomically, requiring all six months."""
import json
import sqlite3
from collections import Counter
from pathlib import Path


def main():
    reports = []
    target = Path("artifacts/flight.sqlite")
    stage = target.with_suffix(".merged.sqlite")
    with sqlite3.connect(stage) as output:
        output.execute("DROP TABLE IF EXISTS aggregates")
        output.execute("DROP TABLE IF EXISTS metadata")
        for month in [f"2024-{i:02}" for i in range(1, 7)]:
            path = Path("artifacts/months", month + ".sqlite")
            if not path.exists():
                raise ValueError(f"Missing completed monthly job: {month}")
            with sqlite3.connect(path) as source:
                report = json.loads(source.execute("SELECT value FROM metadata WHERE key='etl'").fetchone()[0])
                months = source.execute("SELECT DISTINCT month FROM aggregates").fetchall()
                if months != [(month,)]:
                    raise ValueError(f"Unexpected months in {path}: {months}")
                if not reports:
                    schema = source.execute("SELECT sql FROM sqlite_master WHERE name='aggregates'").fetchone()[0]
                    output.execute(schema)
                output.executemany("INSERT INTO aggregates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", source.execute("SELECT * FROM aggregates"))
                reports.append(report)
        counts = Counter()
        for report in reports:
            counts.update(report["dispositions"])
        summary = {"months": [f"2024-{i:02}" for i in range(1, 7)], "runs": reports,
                   "raw_rows": sum(r["raw_rows"] for r in reports), "dispositions": dict(counts),
                   "spark_master": reports[0]["spark_master"], "spark_version": reports[0]["spark_version"],
                   "generated_at_utc": max(r["generated_at_utc"] for r in reports)}
        output.execute("CREATE INDEX idx_filters ON aggregates(month, carrier, origin)")
        output.execute("CREATE INDEX idx_origin ON aggregates(origin, month, dep_hour)")
        output.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
        output.execute("INSERT INTO metadata VALUES ('etl', ?)", (json.dumps(summary),))
    output.close()
    stage.replace(target)
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
