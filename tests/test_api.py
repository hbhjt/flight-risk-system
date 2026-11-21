"""Synthetic fixtures verify denominators, empty filters and input safety."""
import sqlite3
from fastapi.testclient import TestClient
from backend.app import create_app


def test_missing_database(tmp_path):
    client = TestClient(create_app(tmp_path / "missing.sqlite"))
    assert client.get("/api/health").json()["data_ready"] is False
    assert client.get("/api/overview").status_code == 503


def test_aggregation_and_filters(tmp_path):
    path = tmp_path / "synthetic.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE aggregates (month TEXT, carrier TEXT, origin TEXT, dest TEXT, weekday INTEGER, dep_hour INTEGER, planned INTEGER, eligible INTEGER, delayed INTEGER, cancelled INTEGER, diverted INTEGER, arr_delay_sum REAL, arr_delay_count INTEGER)")
        db.executemany("INSERT INTO aggregates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", [
            ("2024-01", "AA", "AAA", "BBB", 1, 8, 10, 8, 2, 1, 1, -16, 8),
            ("2024-01", "BB", "CCC", "DDD", 1, 9, 20, 20, 10, 0, 0, 200, 20),
        ])
    client = TestClient(create_app(path))
    all_data = client.get("/api/overview").json()["data"]
    assert all_data["planned"] == 30
    assert all_data["delay_rate"] == 12 / 28
    assert all_data["cancellation_rate"] == 1 / 30
    filtered = client.get("/api/overview?origin=AAA").json()["data"]
    assert filtered["mean_arrival_delay"] == -2
    assert filtered["delay_rate"] == 0.25
    assert client.get("/api/overview?origin=ZZZ").json()["data"]["delay_rate"] is None
    assert client.get("/api/overview?month=2024-13").status_code == 422
    assert client.get("/api/overview?origin='OR1=1").status_code == 422
    assert client.get("/api/breakdown/invalid").status_code == 422
    assert len(client.get("/api/breakdown/carrier").json()["data"]) == 2
    dashboard = client.get("/api/dashboard").json()
    assert dashboard["summary"]["delay_rate"] == 12 / 28
    assert len(dashboard["routes"]) == 2
    assert client.get("/api/dashboard?hour=8").json()["summary"]["planned"] == 10
    playback = client.get("/api/dashboard?hour=8").json()
    assert [r["dep_hour"] for r in playback["hours"]] == [8]
    assert [r["dep_hour"] for r in playback["comparison_hours"]] == [8, 9]
    no_hour_match = client.get("/api/dashboard?origin=AAA&dest=BBB&hour=9").json()
    assert no_hour_match["summary"]["planned"] == 0
    assert [r["planned"] for r in no_hour_match["comparison_hours"]] == [10]
    assert client.get("/api/dashboard?origin=AAA&dest=DDD").json()["summary"]["delay_rate"] is None
    assert client.get("/api/dashboard?hour=24").status_code == 422
