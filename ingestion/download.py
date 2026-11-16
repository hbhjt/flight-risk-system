"""Download immutable official monthly archives and write verifiable manifests."""
import argparse
import csv
import hashlib
import json
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = "https://www.transtats.bts.gov/PREZIP/"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(url, target, attempts=3):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    for attempt in range(attempts):
        try:
            with requests.get(url, stream=True, timeout=(20, 90)) as response:
                response.raise_for_status()
                size = 0
                with temporary.open("wb") as output:
                    for chunk in response.iter_content(1024 * 1024):
                        output.write(chunk)
                        size += len(chunk)
                expected = response.headers.get("Content-Length")
                if expected and not response.headers.get("Content-Encoding") and size != int(expected):
                    raise ValueError("Incomplete download")
            temporary.replace(target)
            return
        except (requests.RequestException, ValueError, OSError):
            if attempt + 1 == attempts:
                raise
            time.sleep(2 ** attempt)


def import_month(archive, month, source, output):
    output = Path(output)
    target = output / "manifests" / f"{month}.json"
    archive_digest = sha256(archive)
    if target.exists():
        previous = json.loads(target.read_text(encoding="utf-8"))
        if previous["archive_sha256"] != archive_digest:
            raise ValueError("Archive changed: use a separate versioned data directory")
    directory = output / "csv" / month
    directory.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zipped:
        bad = zipped.testzip()
        if bad:
            raise ValueError(f"ZIP integrity failure: {bad}")
        members = [x for x in zipped.namelist() if x.lower().endswith(".csv")]
        if len(members) != 1:
            raise ValueError(f"Expected one CSV, got {members}")
        # Never trust archive paths for extraction.
        path = directory / Path(members[0]).name
        with zipped.open(members[0]) as src, path.open("wb") as dst:
            import shutil
            shutil.copyfileobj(src, dst)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        header = next(reader)
        rows = sum(1 for row in reader if any(row))
    manifest = {
        "month": month, "source_url": source,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "archive": str(Path(archive).resolve()), "archive_bytes": Path(archive).stat().st_size,
        "archive_sha256": archive_digest, "csv": str(path.resolve()),
        "csv_sha256": sha256(path), "csv_bytes": path.stat().st_size,
        "rows": rows, "columns": header, "field_count": len(header),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    # Preserve first acquisition provenance when importing an unchanged file again.
    if target.exists():
        previous = json.loads(target.read_text(encoding="utf-8"))
        if previous["archive_sha256"] != manifest["archive_sha256"]:
            raise ValueError("Archive changed: use a separate versioned data directory")
        manifest["retrieved_at_utc"] = previous["retrieved_at_utc"]
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", nargs="+", default=["2024-01"])
    parser.add_argument("--output", type=Path, default=Path("data/raw"))
    parser.add_argument("--import-zip", type=Path)
    args = parser.parse_args()
    if args.import_zip and len(args.months) != 1:
        parser.error("--import-zip needs exactly one month")
    for month in args.months:
        date = datetime.strptime(month, "%Y-%m")
        name = f"On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{date.year}_{date.month}.zip"
        url = BASE + name
        archive = args.import_zip or args.output / "zip" / name
        if not archive.exists():
            fetch(url, archive)
        manifest = import_month(archive, month, url, args.output)
        print(json.dumps({key: manifest[key] for key in ("month", "rows", "archive_bytes", "archive_sha256")}), flush=True)


if __name__ == "__main__":
    main()
