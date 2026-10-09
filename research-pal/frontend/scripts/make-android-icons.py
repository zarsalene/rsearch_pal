"""Makes the Android launcher icons and the splash screen from public/logo.png.
Run it from the frontend folder:  python scripts/make-android-icons.py   (needs Pillow: pip install pillow)
The background color is the dark blue of the logo."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "android/app/src/main/res"
BG = (16, 21, 49, 255)  # #101531, the dark blue of the logo
BG_HEX = "#101531"

logo = Image.open(ROOT / "public/logo.png").convert("RGBA")
logo = logo.crop(logo.split()[3].getbbox())


def fit(img, size):
    return img.resize((size, size), Image.LANCZOS)


def on_canvas(size, content_ratio, color=(0, 0, 0, 0), circle=False):
    canvas = Image.new("RGBA", (size, size), color)
    inner = round(size * content_ratio)
    canvas.alpha_composite(fit(logo, inner), ((size - inner) // 2, (size - inner) // 2))
    if circle:
        mask = Image.new("L", (size * 4, size * 4), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size * 4 - 1, size * 4 - 1), fill=255)
        canvas.putalpha(mask.resize((size, size), Image.LANCZOS))
    return canvas


# launcher icons: dp size x density factor
for name, f in {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}.items():
    d = RES / f"mipmap-{name}"
    fit(logo, round(48 * f)).save(d / "ic_launcher.png")  # old phones: the logo as it is
    on_canvas(round(48 * f), 0.8, BG, circle=True).save(d / "ic_launcher_round.png")
    # new phones (adaptive icon): the logo stays inside the safe zone (66 percent), the background layer is the blue color
    on_canvas(round(108 * f), 0.66).save(d / "ic_launcher_foreground.png")

(RES / "values/ic_launcher_background.xml").write_text(
    f'<?xml version="1.0" encoding="utf-8"?>\n<resources>\n    <color name="ic_launcher_background">{BG_HEX}</color>\n</resources>\n', encoding="utf-8")

# splash screen: the blue color with the logo in the middle
for d in RES.glob("drawable*/splash.png"):
    w, h = Image.open(d).size
    s = Image.new("RGBA", (w, h), BG)
    side = round(min(w, h) * 0.42)
    s.alpha_composite(fit(logo, side), ((w - side) // 2, (h - side) // 2))
    s.convert("RGB").save(d)
print("done")
