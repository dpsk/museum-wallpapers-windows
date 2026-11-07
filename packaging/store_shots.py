"""Microsoft Store screenshots: the desktop with a well-known painting, made by
the app's own code (Commons scan, Wikidata/Wikipedia labels, blur framing,
the caption in the listing's language). A desktop-only screenshot is exactly
the wallpaper the app sets, so this is that wallpaper at 1920x1080.

    python packaging/store_shots.py [--out dist/store-shots]

Writes <out>/<language>/<n>-<slug>.png for every interface language. Runs on
the CI's Windows runner (.github/workflows/store-shots.yml) for its fonts;
anywhere else the caption uses whatever fonts the platform layer finds."""

import argparse
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
os.environ.setdefault("MUSEUM_WALLPAPERS_HOME", tempfile.mkdtemp(prefix="museum-wallpapers-shots-"))

from PIL import Image  # noqa: E402

from museum_wallpapers import core, framing, platforms, strings  # noqa: E402

# Recognizable paintings the app can show itself: Wikidata "painting",
# landscape between minRatio 1.3 and maxRatio 2.0.
PAINTINGS = [
    ("Q151047", "birth-of-venus"),       # Botticelli, Uffizi (1.59)
    ("Q1070896", "ninth-wave"),          # Aivazovsky, Russian Museum (1.49)
    ("Q500985", "hunters-in-the-snow"),  # Bruegel, Kunsthistorisches Museum (1.41)
]
SIZE = (1920, 1080)


def caption_fonts():
    if sys.platform == "win32":
        from museum_wallpapers.platforms.windows import WindowsPlatform
        return WindowsPlatform().caption_fonts()
    return platforms.DevPlatform().caption_fonts()


def original(qid, folder):
    """The painting's Commons scan (its Wikidata image), 3840 px wide."""
    claims = core.entities([qid], props="claims")[qid]["claims"]
    title = "File:" + claims["P18"][0]["mainsnak"]["datavalue"]["value"]
    page = core.image_infos([title])[title]
    data = core.mw_api(core.COMMONS_API, action="query", prop="imageinfo", iiprop="url",
                       iiurlwidth=3840, pageids=page["pageid"])
    url = data["query"]["pages"][0]["imageinfo"][0]["thumburl"]
    path = folder / f"{qid}.jpg"
    core.download(url, path)
    return page, path


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=HERE.parent / "dist" / "store-shots")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # titles in every script, on a cp1252 console
    fonts = caption_fonts()
    with tempfile.TemporaryDirectory() as tmp:
        for n, (qid, slug) in enumerate(PAINTINGS, 1):
            page, path = original(qid, Path(tmp))
            with Image.open(path) as image:
                canvas = framing.compose(image, "blur", SIZE)
            for language in strings.STRINGS:
                info = core.describe(page, qid, language)
                caption = {"title": info["title"], "byline": core.byline(info), "museum": info.get("museum") or ""}
                shot = framing.draw_caption(canvas.copy(), caption, "bottom-right", (0, 0, 0, 0), fonts)
                out = args.out / language / f"{n}-{slug}.png"
                out.parent.mkdir(parents=True, exist_ok=True)
                shot.save(out, "PNG", optimize=True)
                print(f"{out}: {caption['title']} — {caption['byline']} — {caption['museum']}")


if __name__ == "__main__":
    main()
