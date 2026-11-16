"""Read-only serving of genuine Spark aggregates; no JVM in the request path."""
import json
import os
import sqlite3
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles


def create_app(database=None, predictions=None, results_dir=None):
    app = FastAPI(title="Flight Risk Analytics", version="0.3.0")
    path = Path(database or os.environ.get("FLIGHT_DB", "artifacts/flight.sqlite"))

    @lru_cache(maxsize=2)
    def memory_snapshot(version):
        # Immutable published databases fit in memory; load once per ETL version.
        # This removes NTFS random page reads from every interactive query.
        memory = sqlite3.connect(":memory:", check_same_thread=False)
        disk = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            disk.backup(memory)
        finally:
            disk.close()
        memory.row_factory = sqlite3.Row
        memory.execute("PRAGMA temp_store=MEMORY")
        return memory

    def connect():
        if not path.is_file():
            raise HTTPException(503, "Data not generated; run the Spark ETL first")
        return memory_snapshot(path.stat().st_mtime_ns)

    def filters(month, carrier, origin):
        clauses, values = [], []
        for key, value in [("month", month), ("carrier", carrier), ("origin", origin)]:
            if value:
                clauses.append(f"{key} = ?")
                values.append(value)
        return (" WHERE " + " AND ".join(clauses) if clauses else ""), values

    def metrics(row):
        result = dict(row)
        for field in ["planned", "eligible", "delayed", "cancelled", "diverted", "arr_delay_count"]:
            result[field] = result.get(field) or 0
        result["delay_rate"] = result["delayed"] / result["eligible"] if result["eligible"] else None
        result["cancellation_rate"] = result["cancelled"] / result["planned"] if result["planned"] else None
        result["mean_arrival_delay"] = result["arr_delay_sum"] / result["arr_delay_count"] if result["arr_delay_count"] else None
        return result

    sums = ", ".join(f"SUM({name}) AS {name}" for name in ["planned", "eligible", "delayed", "cancelled", "diverted", "arr_delay_sum", "arr_delay_count"])

    @lru_cache(maxsize=64)
    def dashboard_data(version, month, carrier, origin, dest, hour):
        clauses, values = [], []
        for key, value in [("month", month), ("carrier", carrier), ("origin", origin), ("dest", dest), ("dep_hour", hour)]:
            if value is not None:
                clauses.append(f"{key} = ?")
                values.append(value)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with connect() as db:
            def group(dimensions, order=None, limit=None):
                columns = ", ".join(dimensions)
                # A scan avoids millions of non-covering index lookups on WSL/NTFS.
                # Filters are applied within the same SQL query before aggregation.
                sql = f"SELECT {columns}, {sums} FROM aggregates NOT INDEXED" + where + f" GROUP BY {columns}"
                sql += " ORDER BY " + (order or columns)
                if limit:
                    sql += f" LIMIT {int(limit)}"
                return [metrics(row) for row in db.execute(sql, values)]
            result = {"summary": metrics(db.execute("SELECT " + sums + " FROM aggregates" + where, values).fetchone()),
                      "trend": group(["month"]), "carriers": group(["carrier"], "planned DESC"),
                      "airports": group(["origin"], "planned DESC"),
                      "heatmap": group(["weekday", "dep_hour"]), "hours": group(["dep_hour"]),
                      "routes": group(["origin", "dest"], "planned DESC", 20)}
            result["scope"] = {"months": [r[0] for r in db.execute("SELECT DISTINCT month FROM aggregates ORDER BY month")],
                               "filters": {"month": month, "carrier": carrier, "origin": origin, "dest": dest, "hour": hour}}
            return result

    @app.get("/api/dashboard")
    def dashboard(month: str | None = Query(None, pattern=r"^2024-0[1-6]$"),
                  carrier: str | None = Query(None, pattern=r"^[A-Z0-9()]{2,6}$"),
                  origin: str | None = Query(None, pattern=r"^[A-Z]{3}$"),
                  dest: str | None = Query(None, pattern=r"^[A-Z]{3}$"),
                  hour: int | None = Query(None, ge=0, le=23)):
        if not path.is_file():
            raise HTTPException(503, "Data not generated; run the Spark ETL first")
        return dashboard_data(path.stat().st_mtime_ns, month, carrier, origin, dest, hour)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "data_ready": path.is_file(), "version": app.version}

    @app.get("/api/metadata")
    def metadata():
        with connect() as db:
            return {row["key"]: json.loads(row["value"]) for row in db.execute("SELECT * FROM metadata")}

    @app.get("/api/filters")
    def choices():
        with connect() as db:
            return {key: [r[0] for r in db.execute(f"SELECT DISTINCT {key} FROM aggregates ORDER BY {key}")] for key in ["month", "carrier", "origin", "dest"]}

    @app.get("/api/overview")
    def overview(month: str | None = Query(None, pattern=r"^2024-0[1-6]$"),
                 carrier: str | None = Query(None, pattern=r"^[A-Z0-9()]{2,6}$"),
                 origin: str | None = Query(None, pattern=r"^[A-Z]{3}$")):
        where, values = filters(month, carrier, origin)
        with connect() as db:
            data = metrics(db.execute("SELECT " + sums + " FROM aggregates" + where, values).fetchone())
        return {"filters": {"month": month, "carrier": carrier, "origin": origin}, "data": data,
                "definitions": {"delay_rate": "delayed / eligible arrivals", "cancellation_rate": "cancelled / planned", "mean_arrival_delay": "signed ArrDelay; early arrivals are negative"}}

    @app.get("/api/breakdown/{dimension}")
    def breakdown(dimension: str, month: str | None = Query(None, pattern=r"^2024-0[1-6]$"),
                  carrier: str | None = Query(None, pattern=r"^[A-Z0-9()]{2,6}$"),
                  origin: str | None = Query(None, pattern=r"^[A-Z]{3}$")):
        if dimension not in {"month", "carrier", "origin", "dest", "weekday", "dep_hour"}:
            raise HTTPException(422, "Unsupported dimension")
        where, values = filters(month, carrier, origin)
        with connect() as db:
            rows = db.execute(f"SELECT {dimension} AS name, {sums} FROM aggregates" + where + f" GROUP BY {dimension} ORDER BY {dimension}", values).fetchall()
        return {"dimension": dimension, "data": [metrics(row) for row in rows]}

    from backend.ml_api import router
    app.include_router(router(predictions or os.environ.get("FLIGHT_PREDICTIONS", "artifacts/predictions.sqlite"), results_dir or "results/m3"))
    build = Path(__file__).resolve().parents[1] / "frontend" / "dist"
    if build.is_dir():
        app.mount("/", StaticFiles(directory=build, html=True), name="frontend")
    return app


app = create_app()
