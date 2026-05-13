from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent.parent
SPRITE_ROOT = ROOT / "windows" / "assets" / "sprites" / "Dino"
OUTPUT_GIF = ROOT / "assets" / "preview.gif"

CANVAS_SIZE = (640, 260)
SPRITE_SCALE = 2.0
SCENE_FRAMES = 12
FRAME_DURATION_MS = 120

SCENES = [
    {
        "state": "working",
        "title": "Working",
        "subtitle": "Claude is actively running",
        "accent": "#f59e0b",
    },
    {
        "state": "idle",
        "title": "Idle",
        "subtitle": "No active session",
        "accent": "#60a5fa",
    },
    {
        "state": "waiting",
        "title": "Waiting",
        "subtitle": "Waiting for your approval",
        "accent": "#34d399",
    },
    {
        "state": "sleeping",
        "title": "Sleeping",
        "subtitle": "You've been away a while",
        "accent": "#c084fc",
    },
]

STATE_CHIPS = ["working", "idle", "waiting", "sleeping"]


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _load_frame(state: str, frame_index: int) -> Image.Image:
    path = SPRITE_ROOT / f"{state}_neutral.imageset" / "sprite_sheet.png"
    sheet = Image.open(path).convert("RGBA")
    frame_width = sheet.width // 6
    frame = sheet.crop((frame_index * frame_width, 0, (frame_index + 1) * frame_width, sheet.height))
    alpha_box = frame.getchannel("A").getbbox()
    if alpha_box is not None:
        l, t, r, b = alpha_box
        frame = frame.crop((max(0, l - 2), max(0, t - 2), min(frame.width, r + 2), min(frame.height, b + 2)))
    scaled = (max(48, int(frame.width * SPRITE_SCALE)), max(48, int(frame.height * SPRITE_SCALE)))
    return frame.resize(scaled, Image.Resampling.NEAREST)


def _background(accent: str) -> Image.Image:
    width, height = CANVAS_SIZE
    image = Image.new("RGBA", CANVAS_SIZE, "#08111f")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, height), fill="#08111f")
    draw.ellipse((-140, -80, 220, 220), fill="#0e2640")
    draw.ellipse((width - 230, 20, width + 30, 220), fill="#132d2d")
    draw.rounded_rectangle((20, 18, width - 20, height - 18), radius=24, outline="#20304a", width=2, fill="#0b1526")
    draw.rounded_rectangle((32, 32, 178, 62), radius=15, fill=accent)
    draw.rounded_rectangle((188, 32, width - 32, 62), radius=15, fill="#101c31")
    return image


def _draw_grass_band(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    left, right = 144, width - 120
    base_y = height - 52
    draw.ellipse((left + 22, base_y - 2, right - 22, base_y + 16), fill="#0b1020")
    draw.ellipse((left, base_y - 14, right, base_y + 8), fill="#5d7c67")
    draw.ellipse((left + 10, base_y - 16, right - 10, base_y - 4), fill="#86a390")


def _draw_scene_labels(draw: ImageDraw.ImageDraw, scene: dict[str, str]) -> None:
    title_font = _font(16, bold=True)
    subtitle_font = _font(13)
    label_font = _font(28, bold=True)
    small_font = _font(12)

    draw.text((48, 38), "pixel-companion", fill="#f8fafc", font=title_font)
    draw.text((196, 40), "Desktop companion for Claude Code and Codex", fill="#8fb2d8", font=subtitle_font)
    draw.text((48, 88), scene["title"], fill="#ffffff", font=label_font)
    draw.text((48, 128), scene["subtitle"], fill="#b9c8dc", font=subtitle_font)

    x = 48
    for chip in STATE_CHIPS:
        active = chip == scene["state"]
        fill = scene["accent"] if active else "#101c31"
        text_fill = "#0b1526" if active else "#94a3b8"
        chip_width = 96
        draw.rounded_rectangle((x, 170, x + chip_width, 198), radius=14, fill=fill)
        draw.text((x + 16, 176), chip.title(), fill=text_fill, font=small_font)
        x += chip_width + 10


def _compose_frame(scene: dict[str, str], frame_index: int) -> Image.Image:
    image = _background(scene["accent"])
    draw = ImageDraw.Draw(image)
    _draw_scene_labels(draw, scene)
    _draw_grass_band(draw, *CANVAS_SIZE)

    sprite = _load_frame(scene["state"], frame_index % 6)
    bob_amplitude = {"working": 7, "idle": 4, "waiting": 3, "sleeping": 1}.get(scene["state"], 3)
    bob = ((frame_index % 6) - 2.5) * bob_amplitude / 6
    sprite_x, sprite_y = 486, 164 + int(bob)
    image.alpha_composite(sprite, (int(sprite_x - sprite.width / 2), int(sprite_y - sprite.height / 2)))
    return image


def build_gif() -> None:
    frames: list[Image.Image] = []
    for scene in SCENES:
        for frame_index in range(SCENE_FRAMES):
            frames.append(_compose_frame(scene, frame_index).convert("P", palette=Image.Palette.ADAPTIVE))

    OUTPUT_GIF.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        OUTPUT_GIF,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_DURATION_MS,
        loop=0,
        disposal=2,
    )
    print(f"GIF saved to {OUTPUT_GIF}")


if __name__ == "__main__":
    build_gif()
