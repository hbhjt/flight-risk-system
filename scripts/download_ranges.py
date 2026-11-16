"""Bounded parallel HTTP range download; bootstrap verifies Apache checksum after assembly."""
import argparse
import concurrent.futures
import time
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("target", type=Path)
    parser.add_argument("--size", type=int, required=True)
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    chunk_size = 4 * 1024 * 1024
    chunks = args.target.with_suffix(".chunks")
    chunks.mkdir(parents=True, exist_ok=True)
    count = (args.size + chunk_size - 1) // chunk_size

    def one(index):
        start = index * chunk_size
        end = min(args.size - 1, start + chunk_size - 1)
        target = chunks / str(index)
        if target.exists() and target.stat().st_size == end - start + 1:
            return index
        for retry in range(3):
            try:
                request = urllib.request.Request(args.url, headers={"Range": f"bytes={start}-{end}"})
                with urllib.request.urlopen(request, timeout=45) as response:
                    if response.status != 206 or response.headers.get("Content-Range") != f"bytes {start}-{end}/{args.size}":
                        raise ValueError("Server did not honor the requested byte range")
                    payload = response.read()
                if len(payload) != end - start + 1:
                    raise ValueError("Incomplete chunk")
                target.write_bytes(payload)
                return index
            except Exception:
                if retry == 2:
                    raise
                time.sleep(1 + retry)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for done, future in enumerate(concurrent.futures.as_completed([pool.submit(one, i) for i in range(count)]), 1):
            future.result()
            if done % 10 == 0 or done == count:
                print(f"Verified range lengths: {done}/{count}", flush=True)
    stage = args.target.with_suffix(".assembled")
    with stage.open("wb") as stream:
        for i in range(count):
            stream.write((chunks / str(i)).read_bytes())
    stage.replace(args.target)
    print(f"Assembled {args.target}; official checksum verification required", flush=True)


if __name__ == "__main__":
    main()
