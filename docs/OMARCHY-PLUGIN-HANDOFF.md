# Handoff: bring the Windows 0.1.2–0.1.3 speed-ups to the Omarchy plugin

**Status: done** — ported in the plugin's 0.1.2 (2026-11-06), with
improvements of its own that came back to Windows in 0.1.4 (see HANDOFF.md).

Goal (sections 1–8 from 0.1.2, section 9 from 0.1.3): [omarchy-museum-wallpapers](https://github.com/dpsk/omarchy-museum-wallpapers)
(0.1.1) and this Windows app should behave the same. The Windows app forked
the plugin's `museum.py` as `src/museum_wallpapers/core.py`; version 0.1.2
changed the core to make **Next** fast. Port those changes back to
`museum.py` (and its tests), keeping the plugin's standard-library-only rule.

`docs/omarchy-port-0.1.2.diff` in this repo is the exact core diff (0.1.1 →
0.1.2) of `core.py` and `framing.py`; the Windows-only parts are marked below
as "skip".

## Why Next was slow

With `prefetchCount: 3`, two or three quick Next presses empty the queue,
which refills one painting at a time. A Next with an empty queue then did
everything inline: 1–3 Commons searches, 4–5 *sequential* Wikidata/Wikipedia
requests in `describe`, the image download (after waiting for the
prefetcher's own download to finish, under `.download.lock`), and framing.
Worse, `enqueue` asked Commons for a thumbnail `min(original width, 3840)`
wide — usually a **non-standard width**: Wikimedia's CDN keeps only the
standard steps ready (…, 1280, 1920, 3840; `$wgThumbnailSteps`, see
[T402792](https://phabricator.wikimedia.org/T402792)), so other widths are
rendered on demand and, since February 2026, rate limited.

## Changes to port (in order of effect)

### 1. Standard thumbnail widths — `enqueue`

```python
THUMB_STEPS = (1280, 1920, 3840)

def thumb_width(screen_width):
    target = min(screen_width, MAX_THUMB_WIDTH) * 0.95
    return next((step for step in THUMB_STEPS if step >= target), THUMB_STEPS[-1])
```

In `enqueue`: `iiurlwidth=thumb_width(screen_size()[0])` instead of
`min(page["imageinfo"][0]["width"], MAX_THUMB_WIDTH)`. When the step is wider
than the original, Commons returns the original as `thumburl`. `usable()` is
unchanged.

### 2. Claims instead of `.download.lock`; parallel prefetch

- New `claim(name, key, allow_shown=False)`: under a short `.claim.lock`,
  returns `"queued"` if `QUEUE/<name>.json|.jpg` exists, `"shown"` if
  `CACHE/<name>.jpg` exists (unless `allow_shown`), else writes the sidecar
  `{"filter": key, "claimedBy": os.getpid()}` and returns `"claimed"`.
- `fetch_next`: drop the up-front `queue_claims/shown/seen` snapshot; for each
  candidate call `claim()` and branch on its answer (queued →
  `queued_matched`; shown → `current_matched` or `repeats`); the repeats loop
  claims with `allow_shown=True`. Searching stays outside any lock.
- `enqueue`: assumes the claim exists; on every failure path (no
  `thumburl`, describe/download exceptions) removes the sidecar; writes
  `info["claimedBy"] = os.getpid()` with the final sidecar.
- `in_flight(key)`: sidecars without an image for this key, counted when
  `claimedBy` is this process or the sidecar is younger than
  `IN_FLIGHT_AGE = 120` s (a killed process's claim must not stall anything).
- `prefetch`: rounds of up to `PREFETCH_WORKERS = 2` `_prefetch_one` calls in a
  `ThreadPoolExecutor`; `missing = prefetchCount - len(queue_items) -
  in_flight(key)`; same stamps as before (`"small pool"` on
  `OnlyCurrent/AllQueued`, failure stamp per key). `cmd_prefetch` keeps
  `.prefetcher.lock` (one prefetching process, two threads inside).
- `switch`: `image = queued(config) or wait_for_download(config)` — when the
  queue is empty but a download for this key is in flight, poll (0.25 s, up
  to 60 s) until it lands; only then fetch inline. `.download.lock` is gone.
- Plugin: `fcntl.flock` locks are per open file description, so `lock()`
  already excludes threads too (each call opens its own handle) — no change
  needed there.

### 3. Frame ahead — `prefetch`, `render`, `prune`, `info_for`

- `_prefetch_one` calls `prerender(image, config)` after a download: frame
  the queued image now (skip when `fit == "cover"`; for the plugin there is
  one screen size, `screen_size()`).
- `render`: if the target file in `DISPLAY` already exists, return it (the
  file name encodes stem and fit; it is made from the same original).
  Plugin name today: `DISPLAY/<stem>.<fit>.jpg`.
- `prune`: keep `DISPLAY` copies whose stem is the current painting **or any
  image in `QUEUE`** (it deleted everything but the shown file).
- `info_for`: read the sidecar when `image.parent in (CACHE, QUEUE)`
  (Windows needs it for the caption drawn while framing ahead; harmless for
  the plugin).

### 4. Parallel `describe`

After the painting's entity, fetch in a 3-thread pool: the related entities
(creator, collection, genre), the painting's movement label, and the
painting's own Wikipedia summary (it only needs the painting's sitelinks).
Then, only if needed, the artist's movement and the artist's summary.
Helper `_summary(found)` returns `("", None)` on errors. Order of summary
sources is unchanged: own article → Commons description → "About the artist".

### 5. `prefetchCount` default 6

`DEFAULTS["prefetchCount"] = 6`; in the plugin also `manifest.json`
(`defaults` and the schema `defaultValue`) and the README table.

### 6. Timing in the log

`timed(stage)` context manager printing
`museum-wallpapers: timing <stage>: 1.23s [<thread>]` to stderr around
search, thumbnail url, describe, download, frame, show, prefetch rounds and
"fetch on demand (queue empty)". In the plugin this lands in the journal
(`journalctl --user | grep timing`).

### 7. Caption text (optional for the plugin)

`framing.clean_text()` (NFKC, every `Z*` space → " ", drop `Cf/Cc/Co/Cs/Cn`)
fixed boxes in Windows captions ("Sea coast" with a thin space + zero-width
space in its Wikidata label). The plugin's placard is QML text with
fontconfig fallback, so it does not show boxes, but `notify-send` bodies and
titles benefit from the same cleanup: apply it to `info["title"]` in
`describe`, or where the placard and notifications read it. Skip the
fontTools font picking (Windows only, and not standard library).

### 8. Metadata fallbacks (both apps showed these)

Seen on "The Disembarkation of Christopher Columbus…" (Aivazovsky), a painting
whose Wikidata item has no date and no English label:

- `object_name`: cut at 120 characters on a word boundary with "…" (it cut
  mid-word: "…At Sunrise, o").
- `describe`: `"year"` from Commons `DateTimeOriginal` only through
  `painting_date()`, which drops the value when every 4-digit year in it is
  after `LATEST_PAINTING_YEAR = 1950` — that is the scan or upload date
  ("10 April 2008"), not the painting's.

Tests: `test_long_object_names_end_on_a_word`,
`test_scan_dates_are_not_painting_years`.

### 9. Built-in painter lists (Windows 0.1.3)

The first run waited ~60 s for Wikidata: `famous_painters(60)` is a ~28 s
query, the pool of their paintings another 9–20 s (both measured
2026-11-04: 282 painters / 38 390 paintings for 60+ sitelinks, 1200 /
94 079 for 30+). The Windows app now ships them and refreshes behind the
user's back:

- `painter_ids(level)` (the old query), `query_pool(filters)` (the SPARQL
  part of `_load_pool`), `build_fame_bundle(level)` →
  `{"at", "level", "painters", "items"}`.
- `fame_bundle(level)`: `cache/pools/fame-<level>.json` if valid (parsed once,
  re-read when its mtime changes); refresh in a daemon thread when it is
  older than `POOL_MAX_AGE`; else the built-in `SEED/fame-<level>.json.gz` and
  a refresh; else build it inline under `pools/.fame-<level>.lock`.
  `refresh_fame_in_background`: one thread per level, `lock(..., wait=False)`
  across processes, `REFRESH_RETRY = 600` s after a failure.
- `famous_painters(level)` = `fame_bundle(level)["painters"]`;
  `fetch_next` sets `filters["fameLevel"]`, and adds `fameArtists` only when
  other filters are set (`fame_only()`); `entity_pool` returns the bundle's
  items for `fame_only` filters; `has_entity_filters` counts `fameLevel`.
- `write_json(..., compact=True)` for pools.
- Packaging: `packaging/seed.py` (standard library; refuses fewer than 100
  painters or 10 000 paintings, 4 attempts 30 s apart). For the plugin: the
  seed can live in the repo (`seed/fame-60.json.gz`, `seed/fame-30.json.gz`,
  ~3 MB) refreshed by a scheduled GitHub Action, or be fetched on install;
  `SEED` points there. In the plugin, CLI calls are short-lived processes
  (systemd timer), so the daemon thread dies with them: run the refresh as a
  detached `museum.py refresh-pools` process instead of a thread.

The exact core diff (0.1.2 → 0.1.3) is `docs/omarchy-port-0.1.3.diff`.

Tests: `FameBundleTest` in `tests/test_core.py` and
`test_seed_script_*` in `tests/test_layer.py`.

## Skip (Windows only)

Per-monitor framing and `screens_key`, `caption` drawn into the wallpaper,
fontTools font fallback, `RUNNER` threads, MSIX/StartupTask, `PLATFORM`.

## Tests to port

From `tests/test_core.py` (adapt `self.platform` → the plugin's patched
`set_background`/`CURRENT_LINK`):
`test_parallel_claims_take_each_painting_once`,
`test_shown_paintings_are_not_claimed_unless_repeating`,
`test_stale_claims_from_other_processes_do_not_count`,
`test_switch_waits_for_a_download_in_flight`,
`test_thumbnail_widths_are_standard_steps`,
`test_queued_paintings_are_framed_ahead_and_kept` (with the `fake_magick`
helper instead of Pillow),
`test_queued_paintings_are_described_by_their_sidecar`,
`test_describe_fetches_in_parallel_and_falls_back`, and the updated
`test_prefetch_fills_the_queue_to_count` /
`test_prefetch_falls_back_to_random_and_backs_off_on_failure` (two workers).
From `tests/test_layer.py`: `CaptionTextTest.test_clean_text` if 7 is ported.

## Check after porting

`make check`; then on Omarchy press Next 5–6 times quickly and read
`journalctl --user | grep "timing"`: downloads should be the `prefetch`
threads', and "fetch on demand" should not appear while the queue has
images. Bump the plugin to 0.1.2 with a CHANGELOG entry mirroring this one.
