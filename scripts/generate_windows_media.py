from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent.parent
SPRITE_ROOT = ROOT / "windows" / "assets" / "sprites" / "Dino"
OUTPUT_GIF = ROOT / "assets" / "preview.gif"

# Canvas
W, H = 540, 300
FRAME_MS = 100

# Colors
BG = "#0d1117"
CARD_BG = "#161b22"
CARD_BORDER = "#30363d"
TEXT_PRIMARY = "#f0f6fc"
TEXT_DIM = "#8b949e"
TEXT_ACCENT_YELLOW = "#f0b429"
TEXT_ACCENT_GREEN = "#3fb950"
TEXT_ACCENT_BLUE = "#58a6ff"
TEXT_ACCENT_PURPLE = "#d2a8ff"
PROMPT_BG = "#1c2128"
PROMPT_BORDER = "#388bfd"

# Grass
GRASS_DARK = "#1a2e1a"
GRASS_MID = "#2d4a2d"
GRASS_LIGHT = "#3a5c3a"

# The narrative sequence
# Each beat: (state, caption_lines, accent, sprite_frames, hold_extra_frames)
BEATS = [
    {
        "state": "idle",
        "phase": "idle",
        "caption": ["Dino is waiting...", ""],
        "accent": TEXT_ACCENT_BLUE,
        "hold": 18,
    },
    {
        "state": "idle",
        "phase": "prompt",
        "caption": ["", ""],
        "accent": TEXT_ACCENT_YELLOW,
        "hold": 22,
        "show_prompt": True,
        "prompt_text": '> fix the auth bug',
    },
    {
        "state": "working",
        "phase": "working",
        "caption": ["Working...", "Running tools"],
        "accent": TEXT_ACCENT_YELLOW,
        "hold": 30,
    },
    {
        "state": "waiting",
        "phase": "waiting",
        "caption": ["Waiting for approval", "bash: run migrations?"],
        "accent": TEXT_ACCENT_GREEN,
        "hold": 26,
    },
    {
        "state": "working",
        "phase": "working2",
        "caption": ["Back at it...", "Applying changes"],
        "accent": TEXT_ACCENT_YELLOW,
        "hold": 22,
    },
    {
        "state": "idle",
        "phase": "done",
        "caption": ["Done!", "Session ended"],
        "accent": TEXT_ACCENT_GREEN,
        "hold": 20,
    },
    {
        "state": "sleeping",
        "phase": "sleeping",
        "caption": ["Dino fell asleep", "Step away for a bit"],
        "accent": TEXT_ACCENT_PURPLE,
        "hold": 24,
    },
]

# Activity log entries that accumulate
LOG_LINES = [
    ("#8b949e", "  Waiting for session..."),
    ("#388bfd", "> fix the auth bug"),
    ("#3fb950", "✓ Read auth/middleware.py"),
    ("#3fb950", "✓ Edit auth/token.py"),
    ("#f0b429", "⚠ bash: run migrations?"),
    ("#3fb950", "✓ Approved"),
    ("#3fb950", "✓ Edit db/schema.sql"),
    ("#3fb950", "✓ Session complete"),
]

PHASE_LOG_CUTOFF = {
    "idle": 1,
    "prompt": 2,
    "working": 4,
    "waiting": 5,
    "working2": 7,
    "done": 8,
    "sleeping": 8,
}


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/consola.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _font_mono(size: int) -> ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/cour.ttf",
        "C:/Windows/Fonts/lucon.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _load_sprite(state: str, frame_index: int, scale: float = 3.5) -> Image.Image:
    path = SPRITE_ROOT / f"{state}_neutral.imageset" / "sprite_sheet.png"
    sheet = Image.open(path).convert("RGBA")
    fw = sheet.width // 6
    frame = sheet.crop((frame_index * fw, 0, (frame_index + 1) * fw, sheet.height))
    box = frame.getchannel("A").getbbox()
    if box:
        l, t, r, b = box
        frame = frame.crop((max(0, l - 1), max(0, t - 1), min(frame.width, r + 1), min(frame.height, b + 1)))
    new_w = max(32, int(frame.width * scale))
    new_h = max(32, int(frame.height * scale))
    return frame.resize((new_w, new_h), Image.Resampling.NEAREST)


def _draw_rounded_rect(draw: ImageDraw.ImageDraw, xy: tuple, radius: int, fill: str, outline: str | None = None, width: int = 1) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def _render_frame(beat: dict, tick: int) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # ── background subtle gradient blobs ──────────────────────────────────
    draw.ellipse((-60, -60, 200, 160), fill="#111820")
    draw.ellipse((W - 180, H - 160, W + 80, H + 60), fill="#111820")

    # ── left panel: activity log ───────────────────────────────────────────
    panel_x, panel_y = 16, 16
    panel_w, panel_h = 248, H - 32
    _draw_rounded_rect(draw, (panel_x, panel_y, panel_x + panel_w, panel_y + panel_h), 10, CARD_BG, CARD_BORDER)

    # Panel header
    header_font = _font(11, bold=True)
    draw.text((panel_x + 14, panel_y + 12), "pixel-companion", fill=TEXT_PRIMARY, font=header_font)
    dot_color = beat["accent"]
    draw.ellipse((panel_x + panel_w - 22, panel_y + 14, panel_x + panel_w - 12, panel_y + 24), fill=dot_color)

    # Divider
    draw.line([(panel_x + 10, panel_y + 34), (panel_x + panel_w - 10, panel_y + 34)], fill=CARD_BORDER, width=1)

    # Log lines
    mono = _font_mono(10)
    cutoff = PHASE_LOG_CUTOFF.get(beat["phase"], 1)
    log_y = panel_y + 46
    for i, (color, text) in enumerate(LOG_LINES[:cutoff]):
        if log_y + 16 > panel_y + panel_h - 14:
            break
        draw.text((panel_x + 14, log_y), text, fill=color, font=mono)
        log_y += 15

    # Typing cursor on last log line during prompt phase
    if beat["phase"] == "prompt" and beat.get("show_prompt"):
        cursor_visible = (tick // 5) % 2 == 0
        if cursor_visible:
            draw.text((panel_x + 14, log_y - 15 + 1), "_", fill=TEXT_ACCENT_BLUE, font=mono)

    # ── right panel: Dino + state ──────────────────────────────────────────
    right_x = panel_x + panel_w + 14
    right_w = W - right_x - 16
    right_h = H - 32

    # State badge top
    badge_font = _font(11, bold=True)
    state_label = beat["state"].upper()
    badge_color = beat["accent"]
    bw = 90
    bx = right_x + (right_w - bw) // 2
    _draw_rounded_rect(draw, (bx, panel_y + 8, bx + bw, panel_y + 28), 9, badge_color)
    draw.text((bx + bw // 2 - 20, panel_y + 12), state_label, fill="#0d1117", font=badge_font)

    # Grass platform
    ground_y = H - 58
    grass_cx = right_x + right_w // 2
    draw.ellipse((grass_cx - 68, ground_y - 4, grass_cx + 68, ground_y + 14), fill=GRASS_DARK)
    draw.ellipse((grass_cx - 64, ground_y - 14, grass_cx + 64, ground_y + 4), fill=GRASS_MID)
    draw.ellipse((grass_cx - 56, ground_y - 16, grass_cx + 56, ground_y - 6), fill=GRASS_LIGHT)

    # Dino sprite
    frame_idx = tick % 6
    bob_amp = {"working": 6, "idle": 3, "waiting": 2, "sleeping": 1}.get(beat["state"], 3)
    bob = int(((frame_idx - 2.5) / 6) * bob_amp)
    sprite = _load_sprite(beat["state"], frame_idx)
    sx = grass_cx - sprite.width // 2
    sy = ground_y - sprite.height + bob - 4
    img.alpha_composite(sprite, (sx, sy))

    # Caption below grass
    cap_font = _font(11, bold=True)
    sub_font = _font(10)
    cap1, cap2 = beat["caption"]
    cx = right_x + right_w // 2
    if cap1:
        draw.text((cx - 60, ground_y + 22), cap1, fill=TEXT_PRIMARY, font=cap_font)
    if cap2:
        draw.text((cx - 60, ground_y + 38), cap2, fill=TEXT_DIM, font=sub_font)

    return img


def build_gif() -> None:
    frames: list[Image.Image] = []

    for beat in BEATS:
        total_ticks = beat["hold"]
        for tick in range(total_ticks):
            frame = _render_frame(beat, tick)
            frames.append(frame.convert("P", palette=Image.Palette.ADAPTIVE, dither=Image.Dither.NONE))

    OUTPUT_GIF.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        OUTPUT_GIF,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_MS,
        loop=0,
        disposal=2,
    )
    print(f"GIF saved: {OUTPUT_GIF}  ({len(frames)} frames)")


if __name__ == "__main__":
    build_gif()
