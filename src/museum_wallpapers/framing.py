"""Screen-sized copies of a painting with Pillow: framed by a blurred copy of
itself, on a dark wall, or filling the screen, optionally with a museum-style
caption (italic title, byline, museum) drawn into a corner."""

import functools
import os
import threading
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

WALL_COLOR = (0x1C, 0x1B, 0x19)
BOX_COLOR = (16, 15, 13, 168)
TITLE_COLOR = (247, 243, 235, 255)
BYLINE_COLOR = (214, 207, 195, 255)
MUSEUM_COLOR = (170, 163, 152, 255)
CORNERS = {"bottom-right", "bottom-left", "top-right", "top-left"}

# Huge scans are fine: Commons serves at most 3840 px wide thumbnails.
Image.MAX_IMAGE_PIXELS = 200_000_000


def crop_fraction(width, height, screen):
    """How much of a painting filling the screen would be cut off."""
    ratio, screen_ratio = width / height, screen[0] / screen[1]
    return 1 - min(ratio / screen_ratio, screen_ratio / ratio)


def image_size(path):
    with Image.open(path) as image:
        return image.size


def _contain(image, box):
    return ImageOps.contain(image, box, Image.Resampling.LANCZOS)


def compose(image, fit, size):
    """The painting on a canvas of `size` per `fit` (blur, wall or cover)."""
    width, height = size
    image = image.convert("RGB")
    if fit == "cover":
        return ImageOps.fit(image, size, Image.Resampling.LANCZOS)
    if fit == "wall":
        canvas = Image.new("RGB", size, WALL_COLOR)
        painting = _contain(image, (int(width * 0.94), int(height * 0.92)))
    else:
        # Blurred at a tenth of the size: as smooth, and far faster.
        small = (max(1, width // 10), max(1, height // 10))
        background = ImageOps.fit(image, small, Image.Resampling.BILINEAR)
        background = background.filter(ImageFilter.GaussianBlur(6))
        canvas = ImageEnhance.Brightness(background.resize(size, Image.Resampling.BICUBIC)).enhance(0.62)
        painting = _contain(image, size)
    canvas.paste(painting, ((width - painting.width) // 2, (height - painting.height) // 2))
    return canvas


def clean_text(text):
    """Text as a caption can draw it: compatibility forms folded (NFKC), every
    kind of space a plain space, invisible format characters (zero-width
    spaces, soft hyphens, direction marks) and control characters dropped."""
    text = unicodedata.normalize("NFKC", text or "")
    out = []
    for char in text:
        category = unicodedata.category(char)
        if category in ("Cf", "Cc", "Co", "Cs", "Cn"):
            continue
        out.append(" " if category.startswith("Z") else char)
    return " ".join("".join(out).split())


@functools.lru_cache(maxsize=32)
def _coverage(path):
    """The characters a font file has glyphs for; None when unknown."""
    if not path:
        return None
    try:
        from fontTools.ttLib import TTFont
        with TTFont(str(path), fontNumber=0, lazy=True) as font:
            return frozenset(font.getBestCmap() or {})
    except Exception:  # noqa: BLE001 - not readable: assume it covers everything
        return None


def missing(path, text):
    """How many characters of `text` the font has no glyph for."""
    covered = _coverage(path)
    if covered is None:
        return 0
    return sum(1 for char in set(text) if not char.isspace() and ord(char) not in covered)


def pick_font(paths, text):
    """The first font that can draw all of `text` (else the one missing the
    fewest characters), so a Chinese or Georgian title does not turn into
    boxes in a Latin-only font."""
    paths = [p for p in paths if p] or [None]
    best, best_missing = paths[0], None
    for path in paths:
        count = missing(path, text)
        if count == 0:
            return path
        if best_missing is None or count < best_missing:
            best, best_missing = path, count
    return best


def drawable(path, text):
    """`text` without the characters the font cannot draw (boxes otherwise)."""
    covered = _coverage(path)
    if covered is None:
        return text
    return " ".join("".join(c for c in text if c.isspace() or ord(c) in covered).split())


def _font(path, size):
    if path:
        try:
            return ImageFont.truetype(str(path), size)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def _fit_line(draw, text, font, max_width):
    if draw.textlength(text, font=font) <= max_width:
        return text
    while text and draw.textlength(text + "…", font=font) > max_width:
        text = text[:-1]
    return text.rstrip(" ,·-") + "…"


def _wrap(draw, text, font, max_width, max_lines):
    words, lines, line = text.split(), [], ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width or not line:
            line = candidate
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    if len(lines) > max_lines:
        lines = lines[:max_lines - 1] + [" ".join(lines[max_lines - 1:])]
    return [_fit_line(draw, x, font, max_width) for x in lines]


def draw_caption(canvas, caption, corner="bottom-right", inset=(0, 0, 0, 0), fonts=(None, None)):
    """A small translucent label with the title (italic), the byline and the
    museum in a corner, clear of the taskbar (`inset`). `fonts` is (title
    font, body font, *fallbacks for scripts those two lack)."""
    title = clean_text(caption.get("title"))
    if not title or corner not in CORNERS:
        return canvas
    lines_below = [clean_text(caption.get(key)) for key in ("byline", "museum")]
    width, height = canvas.size
    unit = min(width / 3840, height / 2160) * 2
    fallbacks = list(fonts[2:])
    title_path = pick_font([fonts[0], fonts[1], *fallbacks], title)
    body_path = pick_font([fonts[1], *fallbacks], " ".join(lines_below))
    title, lines_below = drawable(title_path, title), [drawable(body_path, text) for text in lines_below]
    if not title:
        return canvas
    title_font = _font(title_path, max(14, round(21 * unit)))
    body_font = _font(body_path, max(11, round(14 * unit)))
    pad, gap, margin = round(14 * unit), round(5 * unit), round(22 * unit)
    max_text = int(width * 0.3)

    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    rows = [(line, title_font, TITLE_COLOR) for line in _wrap(draw, title, title_font, max_text, 2)]
    for text, color in zip(lines_below, (BYLINE_COLOR, MUSEUM_COLOR)):
        if text:
            rows.append((_fit_line(draw, text, body_font, max_text), body_font, color))

    def line_height(font):
        ascent, descent = font.getmetrics()
        return ascent + descent

    text_w = max(draw.textlength(text, font=font) for text, font, _ in rows)
    text_h = sum(line_height(font) for _, font, _ in rows) + gap * (len(rows) - 1)
    box_w, box_h = int(text_w + 2 * pad), int(text_h + 2 * pad)
    left, top, right, bottom = inset
    x = left + margin if corner.endswith("left") else width - right - margin - box_w
    y = top + margin if corner.startswith("top") else height - bottom - margin - box_h
    draw.rounded_rectangle((x, y, x + box_w, y + box_h), radius=round(6 * unit), fill=BOX_COLOR)
    cursor = y + pad
    for text, font, color in rows:
        draw.text((x + pad, cursor), text, font=font, fill=color)
        cursor += line_height(font) + gap
    return Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")


def frame(src, dest, fit, size, caption=None, corner="bottom-right", inset=(0, 0, 0, 0), fonts=(None, None)):
    """Write a screen-sized JPEG of `src` to `dest` and return `dest`."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as image:
        image.draft("RGB", size)  # JPEG: decode at a reduced scale when that is still big enough
        canvas = compose(image, fit, size)
    if caption:
        canvas = draw_caption(canvas, caption, corner, inset, fonts)
    tmp = dest.with_name(f"{dest.name}.{os.getpid()}-{threading.get_ident()}.part")
    try:
        canvas.save(tmp, "JPEG", quality=92, subsampling=0)
        tmp.replace(dest)
    finally:
        tmp.unlink(missing_ok=True)
    return dest
