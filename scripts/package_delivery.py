"""Package tracked source/materials; optionally add published data for local demo."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--with-data', action='store_true', help='Include published SQLite and built frontend, never raw data/runtime')
    args = parser.parse_args()
    files = {Path(p) for p in subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0') if p}
    files.update(p.relative_to(ROOT) for p in (ROOT/'delivery').glob('*') if p.is_file() and p.suffix not in {'.zip'} and p.name != 'package-manifest.json')
    if args.with_data:
        files.update([Path('artifacts/flight.sqlite'), Path('artifacts/predictions.sqlite')])
        files.update(p.relative_to(ROOT) for p in (ROOT/'frontend/dist').rglob('*') if p.is_file())
    name = 'flight-risk-demo-package.zip' if args.with_data else 'flight-risk-source-package.zip'
    target = ROOT/'delivery'/name
    entries = []
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=3) as archive:
        for rel in sorted(files):
            source = ROOT/rel
            if not source.is_file() or source.suffix == '.zip':
                continue
            archive.write(source, 'flight-risk-system/'+rel.as_posix())
            entries.append({'path':rel.as_posix(),'bytes':source.stat().st_size,'sha256':hashlib.file_digest(source.open('rb'), 'sha256').hexdigest()} if hasattr(hashlib,'file_digest') else {'path':rel.as_posix(),'bytes':source.stat().st_size,'sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
        manifest = {'package':name,'with_published_data':args.with_data,'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),'files':entries}
        archive.writestr('flight-risk-system/delivery/package-manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
    print(f'{target}: {target.stat().st_size} bytes; {len(entries)} files; ZIP CRC passed')

if __name__ == '__main__':
    main()
