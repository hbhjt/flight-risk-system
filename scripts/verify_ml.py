"""Recompute held-out metrics independently from the exported SQLite scores."""
from array import array
import json
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from ml.metrics import evaluate


def main():
    result = json.loads(Path("results/m3/metrics.json").read_text(encoding="utf-8"))
    selected = result["selection"]["selected"]
    labels = array("b")
    scores = {code: array("d") for code in selected}
    with sqlite3.connect("artifacts/predictions.sqlite") as db:
        total = db.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
        dates = db.execute("SELECT MIN(FlightDate), MAX(FlightDate) FROM predictions").fetchone()
        assert dates == ("2024-06-01", "2024-06-30")
        bad = db.execute("SELECT COUNT(*) FROM predictions WHERE history_cutoff_month IS NULL OR history_cutoff_month <> '2024-04' OR label NOT IN (0,1)").fetchone()[0]
        assert bad == 0
        assert total == result["exported_predictions"] == result["test"]["B3"]["n"]
        locked = json.loads(db.execute("SELECT value FROM metadata WHERE key='selection'").fetchone()[0])
        assert locked["config_sha256"] == result["config_sha256"]
        assert locked["selection_data"] == "2024-05 only"
        for row in db.execute("SELECT label,score_B0,score_B1,score_B2,score_B3 FROM predictions"):
            labels.append(row[0])
            for code, score in zip(["B0", "B1", "B2", "B3"], row[1:]):
                scores[code].append(score)
    labels = np.frombuffer(labels, dtype=np.int8)
    reports = {}
    for code, values in scores.items():
        threshold = selected[code]["validation"]["threshold"]
        recalculated = evaluate(labels, np.frombuffer(values, dtype=np.float64), threshold)
        expected = result["test"][code]
        assert expected["threshold"] == threshold
        assert recalculated["confusion"] == expected["confusion"]
        differences = {key: abs(recalculated[key]-expected[key]) for key in ["pr_auc", "average_precision", "roc_auc", "precision", "recall", "f1", "brier"]}
        assert max(differences.values()) <= 1e-12, (code, differences)
        assert sum(box["n"] for box in expected["reliability"]) == total
        reports[code] = {"passed": True, "max_metric_difference": max(differences.values())}
    counts = {code: sum(trial["model"] == code for trial in result["selection"]["trials"]) for code in ["B0", "B1", "B2", "B3"]}
    assert counts == {"B0": 1, "B1": 2, "B2": 2, "B3": 2}
    verification = {"passed": True, "source": "exported SQLite probabilities", "test_rows": total, "test_positives": int(labels.sum()), "date_range": list(dates), "historical_cutoff": "2024-04", "trial_counts": counts, "models": reports}
    Path("results/m3/verification.json").write_text(json.dumps(verification, indent=2), encoding="utf-8")
    print(json.dumps(verification), flush=True)


if __name__ == "__main__":
    main()
