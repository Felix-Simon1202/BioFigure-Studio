"""Fetch only license texts from release-specific official repository commits."""
import concurrent.futures
import json
from pathlib import Path
import tomllib
import urllib.request

root = Path(__file__).resolve().parents[1]
inventory = json.loads((root / 'work/third-party/inventory.json').read_text(encoding='utf-8'))

def fetch(item):
    if item['ecosystem'] != 'cargo' or item.get('files') != []:
        return None
    package = next((root / 'work/tooling/cargo/registry/src').glob(f"*/{item['name']}-{item['version']}"))
    meta = tomllib.loads((package / 'Cargo.toml').read_text(encoding='utf-8'))['package']
    sha = json.loads((package / '.cargo_vcs_info.json').read_text())['git']['sha1']
    repo = meta['repository'].rstrip('/').removesuffix('.git')
    assert repo.startswith('https://github.com/')
    for name in ['LICENSE', 'LICENSE-MIT', 'LICENSE.md', 'LICENSE.txt', 'COPYING', 'LICENCE', 'LICENSE-MIT.md']:
        url = f"https://raw.githubusercontent.com/{repo.removeprefix('https://github.com/')}/{sha}/{name}"
        try:
            data = urllib.request.urlopen(url, timeout=15).read()
        except Exception:
            continue
        destination = root / 'licenses/desktop' / f"{item['name']}-{item['version']}"
        destination.mkdir(parents=True, exist_ok=True)
        (destination / name).write_bytes(data)
        (destination / 'SOURCE.txt').write_text(url + '\n', encoding='utf-8')
        return item['name'], 'collected'
    return item['name'], 'missing'

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    for result in pool.map(fetch, inventory):
        if result:
            print(*result, flush=True)
