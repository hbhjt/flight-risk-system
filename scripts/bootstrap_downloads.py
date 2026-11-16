"""Fetch isolated Linux runtime archives; verify Hadoop against Apache SHA512."""
import hashlib
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ingestion.download import fetch, sha256


def sha512(path):
    digest = hashlib.sha512()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", nargs="?", default="D:/flight-risk-runtime")
    parser.add_argument("--hadoop-url", default="https://archive.apache.org/dist/hadoop/common/hadoop-3.3.6/hadoop-3.3.6.tar.gz")
    args = parser.parse_args()
    base = Path(args.directory)
    base.mkdir(parents=True, exist_ok=True)
    sources = {
        "hadoop-3.3.6.tar.gz": args.hadoop_url,
        "hadoop-3.3.6.tar.gz.sha512": "https://archive.apache.org/dist/hadoop/common/hadoop-3.3.6/hadoop-3.3.6.tar.gz.sha512",
        "jre11.tar.gz": "https://github.com/adoptium/temurin11-binaries/releases/download/jdk-11.0.33%2B10/OpenJDK11U-jre_x64_linux_hotspot_11.0.33_10.tar.gz",
    }
    def one(item):
        name, url = item
        if not (base / name).exists():
            fetch(url, base / name)
        print(f"Downloaded {name}: {(base / name).stat().st_size} bytes", flush=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(one, sources.items()))
    raw = (base / "hadoop-3.3.6.tar.gz.sha512").read_text().lower()
    digest = sha512(base / "hadoop-3.3.6.tar.gz")
    if digest not in raw:
        raise ValueError("Apache Hadoop SHA512 mismatch")
    records = {name: {"source": url, "sha256": sha256(base / name)} for name, url in sources.items()}
    (base / "downloads.json").write_text(json.dumps(records, indent=2))
    print("Apache Hadoop SHA512 verified", flush=True)


if __name__ == "__main__":
    main()
