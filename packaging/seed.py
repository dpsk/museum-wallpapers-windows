"""Fetch the data built into a release: for each `fame` level ("famous",
"known"), the painters and all their paintings on Wikidata, as
fame-<level>.json.gz. The app starts from these, so its first painting does
not wait 30-60 s for Wikidata, and refreshes them in the background.

    python packaging/seed.py [--out packaging/build/seed]

packaging/build.py runs it before PyInstaller (any OS; it needs only the
network)."""

import argparse
import gzip
import json
import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
# A throwaway home and the stand-in platform: no desktop, settings or cache touched.
os.environ.setdefault("MUSEUM_WALLPAPERS_HOME", tempfile.mkdtemp(prefix="museum-wallpapers-seed-"))
os.environ["MUSEUM_WALLPAPERS_PLATFORM"] = "dev"

from museum_wallpapers import core  # noqa: E402

LEVELS = ("famous", "known")
# Less than this means Wikidata answered with a cut-off list.
MIN_PAINTERS = 100
MIN_PAINTINGS = 10000


def fetch(level, attempts, wait):
    for attempt in range(1, attempts + 1):
        try:
            bundle = core.build_fame_bundle(level)
            if len(bundle["painters"]) < MIN_PAINTERS or len(bundle["items"]) < MIN_PAINTINGS:
                raise ValueError(f"only {len(bundle['painters'])} painters, {len(bundle['items'])} paintings")
            return bundle
        except Exception as exc:  # noqa: BLE001 - Wikidata is flaky under load; try again
            print(f"fame {level}, attempt {attempt}/{attempts}: {exc}", file=sys.stderr)
            if attempt < attempts:
                time.sleep(wait)
    raise SystemExit(f"could not fetch the painters and paintings for fame level {level}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=HERE / "build" / "seed")
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--wait", type=float, default=30)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for name in LEVELS:
        level = core.FAME[name]
        bundle = fetch(level, args.attempts, args.wait)
        path = args.out / f"fame-{level}.json.gz"
        tmp = path.with_suffix(".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=9) as handle:
            json.dump(bundle, handle, ensure_ascii=False, separators=(",", ":"))
        tmp.replace(path)
        print(f"{name}: {len(bundle['painters'])} painters, {len(bundle['items'])} paintings, "
              f"{path.stat().st_size / 1e6:.2f} MB -> {path}")


if __name__ == "__main__":
    main()
