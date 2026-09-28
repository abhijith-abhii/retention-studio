"""Download the exact public IBM revision and verify before replacing raw data."""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'data/raw/source.json').read_text())
with urlopen(manifest['download_url'],timeout=60) as response:
    body=response.read()
actual=hashlib.sha256(body).hexdigest()
if actual != manifest['sha256']:
    raise SystemExit('Source hash mismatch. Existing raw dataset was preserved.')
target=root/'data/raw/telco.csv'
temp=target.with_suffix('.tmp');temp.write_bytes(body);temp.replace(target)
print(f'Verified {len(body):,} bytes: {actual}')
