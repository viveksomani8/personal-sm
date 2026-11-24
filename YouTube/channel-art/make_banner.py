"""Build the YouTube channel banner (2560x1440) from the wide family portrait.

YouTube shows different parts of the banner per device: TVs show all of it, desktop a
2560x423 band across the middle, phones only the central 1546x423. The family strip is
sized and placed so all four faces sit inside that central area; the rest is a blurred,
darkened copy of the same picture with the channel name above, as in the Shorts.

Run (from this folder):
    uv run --system-certs --no-project --python 3.12 --with pillow python make_banner.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = Path(__file__).parent
SOURCE = HERE / "options" / "banner-logo-man-2.png"
W, H = 2560, 1440
SAFE_W, SAFE_H = 1546, 423          # the part every device shows, centred
STRIP_H = 600                       # height the family picture is shown at
STRIP_TOP = (H - SAFE_H) // 2 - 6   # its top edge sits just above the safe area
CHANNEL = "Jokes Apart"


def main():
    art = Image.open(SOURCE).convert("RGB")
    strip = art.resize((round(art.width * STRIP_H / art.height), STRIP_H), Image.LANCZOS)

    scale = max(W / art.width, H / art.height) * 1.1
    big = art.resize((round(art.width * scale), round(art.height * scale)), Image.BICUBIC)
    x, y = (big.width - W) // 2, (big.height - H) // 2
    banner = ImageEnhance.Brightness(big.crop((x, y, x + W, y + H)).filter(ImageFilter.GaussianBlur(40))).enhance(0.4)

    left = (W - strip.width) // 2
    banner.paste(strip, (left, STRIP_TOP))
    draw = ImageDraw.Draw(banner)
    draw.rectangle([left - 6, STRIP_TOP - 6, left + strip.width + 5, STRIP_TOP + STRIP_H + 5], outline="white", width=6)

    font = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 150)
    box = draw.textbbox((0, 0), CHANNEL, font=font)
    tx, ty = (W - (box[2] - box[0])) // 2 - box[0], 190
    draw.text((tx + 4, ty + 4), CHANNEL, font=font, fill=(0, 0, 0))
    draw.text((tx, ty), CHANNEL, font=font, fill=(255, 214, 77))

    banner.save(HERE / "channel-banner.png")
    # A preview with the desktop band and the all-devices safe area outlined.
    preview = banner.copy()
    d = ImageDraw.Draw(preview)
    d.rectangle([0, (H - SAFE_H) // 2, W - 1, (H + SAFE_H) // 2], outline=(0, 255, 255), width=4)
    d.rectangle([(W - SAFE_W) // 2, (H - SAFE_H) // 2, (W + SAFE_W) // 2, (H + SAFE_H) // 2], outline=(255, 0, 0), width=4)
    preview.resize((1280, 720)).save(HERE / "options" / "banner-safe-area-preview.jpg", quality=88)
    print("wrote channel-banner.png", banner.size, "strip", strip.size, "at", (left, STRIP_TOP))


if __name__ == "__main__":
    main()
