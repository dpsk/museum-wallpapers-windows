"""The app icon (a small gilt frame around a landscape), drawn with Pillow so
the repository needs no binary art; packaging writes it out as icon.ico."""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

GOLD = (201, 158, 72, 255)
GOLD_DARK = (128, 92, 34, 255)
GOLD_LIGHT = (240, 206, 128, 255)
SKY = (120, 168, 214, 255)
SKY_LOW = (236, 196, 140, 255)
HILL = (70, 112, 74, 255)
HILL_FAR = (112, 150, 110, 255)
SUN = (255, 236, 170, 255)


def icon_image(size=256):
    """The icon at `size` px, drawn at 4x and scaled down for smooth edges."""
    s = size * 4
    image = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    u = s / 64
    # Frame: dark outer edge, gold body, light inner bevel.
    draw.rounded_rectangle((2 * u, 6 * u, 62 * u, 58 * u), radius=3 * u, fill=GOLD_DARK)
    draw.rounded_rectangle((4 * u, 8 * u, 60 * u, 56 * u), radius=2 * u, fill=GOLD)
    draw.rectangle((10 * u, 14 * u, 54 * u, 50 * u), fill=GOLD_LIGHT)
    # Canvas: a sky fading to evening light, a sun, two hills.
    top, bottom = 15 * u, 49 * u
    for y in range(int(top), int(bottom)):
        t = (y - top) / (bottom - top)
        color = tuple(int(a + (b - a) * t) for a, b in zip(SKY, SKY_LOW))
        draw.line((11 * u, y, 53 * u, y), fill=color)
    draw.ellipse((38 * u, 20 * u, 46 * u, 28 * u), fill=SUN)
    draw.polygon([(11 * u, 40 * u), (24 * u, 30 * u), (36 * u, 38 * u), (53 * u, 32 * u), (53 * u, 49 * u),
                  (11 * u, 49 * u)], fill=HILL_FAR)
    draw.polygon([(11 * u, 46 * u), (22 * u, 39 * u), (34 * u, 44 * u), (46 * u, 40 * u), (53 * u, 43 * u),
                  (53 * u, 49 * u), (11 * u, 49 * u)], fill=HILL)
    return image.resize((size, size), Image.Resampling.LANCZOS)


ICO_SIZES = [(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)]


def write_ico(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    icon_image(256).save(path, format="ICO", sizes=ICO_SIZES)
    return path


# MSIX visual assets: name -> (width, height). The icon is centred with a
# margin on a transparent canvas, as Windows plates tiles itself.
MSIX_ASSETS = {
    "StoreLogo.png": (50, 50),
    "Square44x44Logo.png": (44, 44),
    "Square150x150Logo.png": (150, 150),
    "Wide310x150Logo.png": (310, 150),
}


def write_msix_assets(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for name, (width, height) in MSIX_ASSETS.items():
        side = min(width, height)
        icon = icon_image(side if side <= 50 else int(side * 0.66))
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        canvas.paste(icon, ((width - icon.width) // 2, (height - icon.height) // 2), icon)
        canvas.save(folder / name)
    return folder


def icon_file(folder):
    """An .ico for toasts and shortcuts: the bundled one in the build, else
    one written into `folder`."""
    bundled = Path(getattr(sys, "_MEIPASS", "")) / "icon.ico"
    if getattr(sys, "frozen", False) and bundled.exists():
        return bundled
    target = Path(folder) / "icon.ico"
    if not target.exists():
        write_ico(target)
    return target


if __name__ == "__main__":
    print(write_ico(sys.argv[1] if len(sys.argv) > 1 else "icon.ico"))
