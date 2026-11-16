"""Fetch reproducible local public-domain map/airport snapshots with provenance."""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from ingestion.download import fetch, sha256


def main():
    output = Path("frontend/public/maps")
    output.mkdir(parents=True, exist_ok=True)
    raw = Path("data/geography")
    raw.mkdir(parents=True, exist_ok=True)
    sources = {
        "airports.csv": "https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/airports.csv",
        "states.geojson": "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_1_states_provinces.geojson",
        "ourairports-license.txt": "https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/LICENSE",
    }
    for name, url in sources.items():
        if not (raw / name).exists():
            fetch(url, raw / name)
    airports = {}
    with (raw / "airports.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            code = row["iata_code"]
            if len(code) != 3 or row["iso_country"] not in {"US", "PR", "VI", "GU", "AS", "MP"}:
                continue
            score = (row["scheduled_service"] == "yes", row["type"] == "large_airport", row["type"] == "medium_airport")
            if code not in airports or score > airports[code][0]:
                airports[code] = (score, {"code": code, "name": row["name"], "city": row["municipality"], "region": row["iso_region"], "lon": float(row["longitude_deg"]), "lat": float(row["latitude_deg"])})
    (output / "airports.json").write_text(json.dumps({key: value[1] for key, value in airports.items()}, ensure_ascii=False), encoding="utf-8")
    geo = json.loads((raw / "states.geojson").read_text(encoding="utf-8"))
    features = [feature for feature in geo["features"] if feature["properties"].get("adm0_a3") == "USA" and feature["properties"].get("name") not in {"Alaska", "Hawaii"}]
    if not features:
        raise ValueError("Natural Earth schema changed: no mainland states")
    (output / "us-contiguous.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
    (output / "ourairports-license.txt").write_bytes((raw / "ourairports-license.txt").read_bytes())
    metadata = {"snapshot_utc": datetime.now(timezone.utc).isoformat(), "sources": {key: {"url": url, "sha256": sha256(raw / key)} for key, url in sources.items()}, "licenses": {"airports": "Unlicense", "basemap": "Public domain; https://www.naturalearthdata.com/about/terms-of-use/"}, "note": "Current geography snapshot used only for historical visualization; not historical feature inputs"}
    (output / "sources.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(airports)} airport coordinates and {len(features)} mainland state features")


if __name__ == "__main__":
    main()
