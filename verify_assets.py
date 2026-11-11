"""Verify every bundled model and texture against the release manifest."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent


def verify():
    manifest = json.loads((ROOT / 'asset_manifest.json').read_text(encoding='utf-8'))
    failures = []
    for item in manifest['files']:
        path = (ROOT / item['path']).resolve()
        if not path.is_relative_to(ROOT / 'assets'):
            failures.append(item['path'] + ': invalid asset path')
            continue
        if not path.is_file():
            failures.append(item['path'] + ': missing')
            continue
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if path.stat().st_size != item['bytes'] or digest != item['sha256']:
            failures.append(item['path'] + ': checksum mismatch')
    for failure in failures:
        print(failure)
    if failures:
        print('Download and extract hotel705-random-clutter-v1.0.0-full.zip from GitHub Releases.')
        return 1
    print(f"PASS: {len(manifest['files'])} model, source and texture files verified.")
    return 0


if __name__ == '__main__':
    sys.exit(verify())
