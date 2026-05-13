from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SPRITE_ROOT = ROOT / "windows" / "assets" / "sprites" / "Dino"
OUTPUT = ROOT / "assets" / "juego.png"

W, H = 600, 200
FLOOR_Y = int(H * 0.62)   # background floor line (matches BackgroundRenderer)
GROUND_Y = int(H * 0.78)  # game ground line


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            return ImageFont.truetype(c, size=size)
    return ImageFont.load_default()


def _build_noche_bg() -> Image.Image:
    gc = (28, 36, 28)
    img = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, FLOOR_Y], fill=(18, 22, 50, 255))
    d.rectangle([0, FLOOR_Y, W, H], fill=(*gc, 255))
    rng = random.Random(42)
    for _ in range(55):
        sx = rng.randint(0, W - 1)
        sy = rng.randint(0, FLOOR_Y - 4)
        br = rng.randint(140, 255)
        d.ellipse([sx - 1, sy - 1, sx + 1, sy + 1], fill=(br, br, br, 255))
    mr = int(H * 0.10)
    my = int(H * 0.14)
    mx = int(W * 0.30)
    d.ellipse([mx - mr, my - mr, mx + mr, my + mr], fill=(240, 238, 210, 255))
    d.ellipse([mx + mr // 3, my - mr, mx + mr + mr // 2, my + mr // 2], fill=(18, 22, 50, 255))
    return img


def _draw_ground(draw: ImageDraw.ImageDraw) -> None:
    draw.line((0, GROUND_Y, W, GROUND_Y), fill="#475569", width=2)


def _draw_obstacle_farol(draw: ImageDraw.ImageDraw, x: int, h: int = 44, w: int = 18) -> None:
    gy = GROUND_Y
    pole_w = max(3, w // 4)
    cx = x + w // 2
    draw.rectangle([cx - pole_w // 2, gy - h, cx + pole_w // 2, gy],
                   fill="#374151", outline="#1f2937", width=1)
    lamp_h = max(8, h // 3)
    draw.rectangle([x, gy - h, x + w, gy - h + lamp_h],
                   fill="#fef08a", outline="#fde047", width=1)
    draw.ellipse([x + 2, gy - h + 2, x + w - 2, gy - h + lamp_h - 2],
                 fill="#fef9c3")
    # halo glow
    for radius, alpha in [(14, 30), (10, 50)]:
        draw.ellipse([cx - radius, gy - h + lamp_h // 2 - radius,
                      cx + radius, gy - h + lamp_h // 2 + radius],
                     fill=(254, 249, 195, alpha))


def _load_dino(frame: int = 2) -> Image.Image:
    path = SPRITE_ROOT / "working_neutral.imageset" / "sprite_sheet.png"
    sheet = Image.open(path).convert("RGBA")
    fw = sheet.width // 6
    frame_img = sheet.crop((frame * fw, 0, (frame + 1) * fw, sheet.height))
    box = frame_img.getchannel("A").getbbox()
    if box:
        l, t, r, b = box
        frame_img = frame_img.crop((max(0, l - 1), max(0, t - 1),
                                    min(frame_img.width, r + 1),
                                    min(frame_img.height, b + 1)))
    w2 = max(32, int(frame_img.width * 2.0))
    h2 = max(32, int(frame_img.height * 2.0))
    return frame_img.resize((w2, h2), Image.Resampling.NEAREST)


def _draw_score(draw: ImageDraw.ImageDraw, meters: int) -> None:
    draw.text((W - 12, 10), f"{meters} m", fill="#94a3b8",
              font=_font(11, bold=True), anchor="rt")


def _draw_levelup_badge(img: Image.Image) -> None:
    badge = Image.new("RGBA", (180, 32), (0, 0, 0, 0))
    bd = ImageDraw.Draw(badge)
    bd.rounded_rectangle((0, 0, 179, 31), radius=9,
                          fill=(30, 41, 80, 220), outline=(99, 120, 210, 255), width=1)
    bd.text((90, 16), "Level Up!  —  Play now", fill="#e0e8ff",
            font=_font(12, bold=True), anchor="mm")
    img.alpha_composite(badge, ((W - 180) // 2, 10))


def build() -> None:
    img = _build_noche_bg()
    draw = ImageDraw.Draw(img)

    _draw_ground(draw)
    _draw_obstacle_farol(draw, x=340, h=48, w=18)
    _draw_obstacle_farol(draw, x=430, h=36, w=14)
    _draw_obstacle_farol(draw, x=510, h=52, w=20)

    dino = _load_dino(frame=2)
    img.alpha_composite(dino, (80, GROUND_Y - dino.height))

    _draw_score(draw, meters=347)
    _draw_levelup_badge(img)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(OUTPUT, "PNG")
    print(f"Saved to {OUTPUT}")


if __name__ == "__main__":
    build()
