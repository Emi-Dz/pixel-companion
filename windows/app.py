from __future__ import annotations

import calendar
import datetime
import json
import math
import random
import shutil
import socketserver
import subprocess
import sys
import threading
import time
import ctypes
import winsound
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tkinter as tk
from PIL import Image, ImageDraw, ImageTk, ImageFilter, ImageChops
from tkinter import messagebox
try:
    import pygame as _pygame
    _pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=512)
    _pygame.mixer.init()
    _PYGAME_OK = True
except Exception:
    _PYGAME_OK = False


APP_HOST = "127.0.0.1"
APP_PORT = 8765
APP_MUTEX_NAME = "Local\\MascotaSingleton"
REFRESH_MS = 500
ANIMATION_MS = 120
MAX_EVENTS = 8
MAX_MESSAGES = 5
EMOTION_DECAY = 0.92
PROMPT_EMOTION_DAMPEN = 0.55
REPLY_EMOTION_DAMPEN = 0.3
HAPPY_THRESHOLD = 0.3
SAD_THRESHOLD = 0.42
SOB_THRESHOLD = 0.8
TRANSPARENT_KEY = "#00ff00"
SESSION_SLEEP_SECONDS = 180
AUTO_CLOSE_MINUTES_DEFAULT = 5
BG_SCROLL_SPEED = 3.0

SPRITE_SET_SCALE_DEFAULTS: dict[str, float] = {
    "Dino": 3.0,
}

# House customization options — (key, label, rgb)
GRASS_COLORS: list[tuple[str, str, tuple[int, int, int]]] = [
    ("verde",  "Verde",  (93,  124, 103)),
    ("azul",   "Azul",   (61,  101, 117)),
    ("tierra", "Tierra", (122,  92,  66)),
    ("nieve",  "Nieve",  (184, 200, 216)),
    ("morado", "Morado", (107,  77, 122)),
    ("arena",  "Arena",  (198, 174, 130)),
    ("oscuro",   "Oscuro",   ( 30,  36,  48)),
    ("amarillo", "Amarillo", (198, 172,  60)),
    ("negro",    "Negro",    ( 18,  18,  18)),
    ("piedra",   "Piedra",   (130, 125, 118)),
]


def _lighten(rgb: tuple[int, int, int], amount: int = 28) -> tuple[int, int, int]:
    return tuple(min(255, c + amount) for c in rgb)  # type: ignore[return-value]

# (key, label, min_level)
BG_THEMES: list[tuple[str, str, int]] = [
    ("oficina",   "Oficina",   1),
    ("bosque",    "Bosque",    1),
    ("montanas",  "Montañas",  2),
    ("noche",     "Noche",     3),
    ("playa",     "Playa",     5),
    ("espacio",   "Espacio",   10),
]

# (key, label, rgb_or_None)
OUTLINE_OPTIONS: list[tuple[str, str, tuple[int, int, int] | None]] = [
    ("ninguno", "Sin borde", None),
    ("blanco",  "Blanco",   (255, 255, 255)),
    ("negro",   "Negro",    (20,  20,  20)),
    ("dorado",  "Dorado",   (220, 175, 30)),
    ("rosa",    "Rosa",     (255, 110, 170)),
    ("cyan",    "Cyan",     (50,  200, 220)),
    ("rojo",    "Rojo",     (220, 55,  55)),
]

# (key, label)
FLOATING_ITEMS: list[tuple[str, str]] = [
    ("ninguno",  "Ninguno"),
    ("corona",   "Corona"),
    ("estrella", "Estrella"),
    ("halo",     "Halo"),
    ("rayo",     "Rayo"),
    ("corazon",  "Corazon"),
    ("nota",     "Nota"),
    ("zzz",      "Zzz"),
    ("fuego",    "Fuego"),
    ("calavera", "Calavera"),
    ("arcoiris", "Arcoiris"),
    ("explosion","Explosion"),
    ("diamante", "Diamante"),
    ("luna",     "Luna"),
]

DECORATIONS: list[tuple[str, str, int]] = [
    ("planta",       "Planta",       3),
    ("alfombra",     "Alfombra",     5),
    ("lampara",      "Lampara",      8),
    ("globos",       "Globos",       15),
    ("cactus",       "Cactus",       2),
    ("computadora",  "Computadora",  4),
    ("cofre",        "Cofre",        10),
    ("nave",         "Nave",         6),
    ("acuario",      "Acuario",      7),
    # playa
    ("sombrilla",    "Sombrilla",    3),
    ("tabla",        "Tabla surf",   6),
    # camping
    ("fogata",       "Fogata",       2),
    ("carpa",        "Carpa",        4),
]

# (key, label, rgb_or_None, min_level)
MASCOT_TINTS: list[tuple[str, str, tuple[int, int, int] | None, int]] = [
    ("original",    "Original",    None,            1),
    ("azul",        "Azul",        (100, 160, 255), 8),
    ("rosa",        "Rosa",        (255, 130, 170), 8),
    ("dorado",      "Dorado",      (255, 200, 80),  10),
    ("verde claro", "Verde claro", (100, 220, 130), 12),
]


_DEFAULT_DEC_POSITIONS: dict[str, list[float]] = {
    "planta":      [0.88, 0.74],
    "alfombra":    [0.50, 0.82],
    "lampara":     [0.08, 0.66],
    "globos":      [0.50, 0.28],
    "cactus":      [0.12, 0.72],
    "computadora": [0.82, 0.76],
    "cofre":       [0.14, 0.80],
    "nave":        [0.50, 0.22],
    "acuario":     [0.18, 0.72],
    "sombrilla":   [0.82, 0.70],
    "tabla":       [0.90, 0.72],
    "fogata":      [0.50, 0.82],
    "carpa":       [0.78, 0.74],
}


# ── i18n ─────────────────────────────────────────────────────────────────────

_LANG: str = "en"

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "settings_title": "Settings",
        "settings_xp_section": "XP SYSTEM",
        "settings_xp_enabled": "XP enabled",
        "settings_appearance_section": "APPEARANCE",
        "settings_opacity": "Opacity:",
        "settings_claude_section": "CLAUDE CODE INTEGRATION",
        "settings_hook_status_ok": "✓ Installed",
        "settings_hook_status_no": "✗ Not installed",
        "settings_hook_install_btn": "Install / Reinstall hook",
        "settings_codex_section": "CODEX INTEGRATION (OpenAI)",
        "settings_shortcut_section": "SHORTCUT",
        "settings_shortcut_btn": "Create Desktop shortcut",
        "settings_lang_section": "LANGUAGE",
        "settings_close": "Close",
        "picker_title": "Who's working today?",
        "picker_working_on": "Who's working on",
        "picker_new_char": "+ New character",
        "game_offer_title": "Level Up!",
        "game_offer_body_fmt": "{name} reached level {level}! 🎉",
        "game_offer_question": "Want to go for a run?",
        "game_offer_yes": "Let's go!",
        "game_offer_no": "Not now",
        "greeting_title": "Good morning",
        "greeting_msg": "Good morning! 👋",
        "greeting_question": "What are your plans for today?",
        "greeting_alarms_btn": "Set alarms",
        "greeting_skip": "Not now",
        "welcome_title": "Welcome",
        "welcome_msg": "Welcome",
        "welcome_name_prompt": "Give your companion a name:",
        "welcome_start": "Start",
        "house_title": "Your House",
        "house_level_fmt": "Lv.{level} (best character)",
        "house_section_bg": "BACKGROUND",
        "house_section_floor": "FLOOR",
        "house_section_decs": "DECORATIONS  (drag to move)",
        "house_char_hint": "Character color and style are configured\nfrom the \"Character\" button.",
        "house_close": "Close",
        "char_title_fmt": "Character: {name}",
        "char_section_sprite": "SPRITE (visual character)",
        "char_section_color": "COLOR",
        "char_section_outline": "OUTLINE",
        "char_section_float": "FLOATING ITEM",
        "char_float_hint": "Floats above the mascot in all animations.",
        "char_close": "Close",
        "char_delete": "Delete character",
        "char_delete_confirm_title": "Delete character",
        "char_delete_confirm_fmt": "Delete {name}?",
        "char_delete_error_title": "Cannot delete",
        "char_delete_error_msg": "There must be at least one character.",
        "alarms_title": "Alarms & Breaks",
        "alarms_header": "Planning",
        "alarms_tab_alarms": "Alarms 🔔",
        "alarms_tab_breaks": "Breaks ☕",
        "alarms_add_label": "Add alarm",
        "alarms_placeholder": "Label",
        "alarms_default_lbl": "Reminder",
        "alarms_add_btn": "Add",
        "alarms_empty": "No alarms configured.",
        "alarms_repeat_label": "Repeat:",
        "alarms_repeat_once": "Once",
        "alarms_repeat_daily": "Every day",
        "alarms_repeat_weekly": "Weekdays",
        "alarms_repeat_monthly": "Days of month",
        "alarms_weekday_letters": "MTWTFSS",
        "alarms_days_label": "Days of month:",
        "alarms_days_hint": "1,15",
        "alarms_days_badge": "day",
        "alarms_badge_once": "once",
        "alarms_badge_daily": "every day",
        "alarms_break_section": "BREAK REMINDERS",
        "alarms_break_enabled": "Enable break reminders",
        "alarms_interval_label": "Work interval:",
        "alarms_duration_label": "Break duration:",
        "alarms_auto_close_section": "AUTO-CLOSE",
        "alarms_auto_close_enabled": "Auto-close after inactivity",
        "alarms_auto_close_after": "After:",
        "alarms_close": "Close",
        "ctx_remove_fmt": "Remove  {name}",
        "hook_installed_title": "Hook installed",
        "hook_error_title": "Error",
        "shortcut_ok_fmt": "Shortcut created in:\n{path}",
        "shortcut_ok_title": "Done",
        "shortcut_err_no_vbs": "Could not find 'Iniciar Mascota.vbs'",
        "shortcut_err_no_desktop": "Desktop folder not found.",
        "levelup_msg_fmt": "Level Up!  Lv.{level}",
        "codex_not_detected": " (Codex not detected)",
    },
    "es": {
        "settings_title": "Configuracion",
        "settings_xp_section": "SISTEMA DE XP",
        "settings_xp_enabled": "XP activado",
        "settings_appearance_section": "APARIENCIA",
        "settings_opacity": "Opacidad:",
        "settings_claude_section": "INTEGRACIÓN CLAUDE CODE",
        "settings_hook_status_ok": "✓ Instalado",
        "settings_hook_status_no": "✗ No instalado",
        "settings_hook_install_btn": "Instalar / Reinstalar hook",
        "settings_codex_section": "INTEGRACIÓN CODEX (OpenAI)",
        "settings_shortcut_section": "ACCESO DIRECTO",
        "settings_shortcut_btn": "Crear acceso directo en Escritorio",
        "settings_lang_section": "IDIOMA",
        "settings_close": "Cerrar",
        "picker_title": "Quien trabaja hoy?",
        "picker_working_on": "Quien trabaja en",
        "picker_new_char": "+ Nuevo personaje",
        "game_offer_title": "¡Subiste de nivel!",
        "game_offer_body_fmt": "¡{name} llegó al nivel {level}! 🎉",
        "game_offer_question": "¿Querés salir a correr un poco?",
        "game_offer_yes": "¡Vamos!",
        "game_offer_no": "Ahora no",
        "greeting_title": "Buenos días",
        "greeting_msg": "¡Buenos días! 👋",
        "greeting_question": "¿Qué planes tenés para hoy?",
        "greeting_alarms_btn": "Configurar alarmas",
        "greeting_skip": "Ahora no",
        "welcome_title": "Bienvenido",
        "welcome_msg": "Bienvenido",
        "welcome_name_prompt": "Dale un nombre a tu companero:",
        "welcome_start": "Comenzar",
        "house_title": "Tu Casa",
        "house_level_fmt": "Lv.{level} (mejor personaje)",
        "house_section_bg": "FONDO",
        "house_section_floor": "SUELO",
        "house_section_decs": "DECORACIONES  (arrastrá para mover)",
        "house_char_hint": "El color y estilo del personaje se configuran\ndesde el botón \"Personaje\".",
        "house_close": "Cerrar",
        "char_title_fmt": "Personaje: {name}",
        "char_section_sprite": "SPRITE (personaje visual)",
        "char_section_color": "COLOR",
        "char_section_outline": "CONTORNO",
        "char_section_float": "OBJETO FLOTANTE",
        "char_float_hint": "Flota sobre la mascota en todas las animaciones.",
        "char_close": "Cerrar",
        "char_delete": "Borrar personaje",
        "char_delete_confirm_title": "Borrar personaje",
        "char_delete_confirm_fmt": "¿Borrar a {name}?",
        "char_delete_error_title": "No se puede borrar",
        "char_delete_error_msg": "Debe haber al menos un personaje.",
        "alarms_title": "Alarmas y Descansos",
        "alarms_header": "Planificación",
        "alarms_tab_alarms": "Alarmas 🔔",
        "alarms_tab_breaks": "Descansos ☕",
        "alarms_add_label": "Agregar alarma",
        "alarms_placeholder": "Etiqueta",
        "alarms_default_lbl": "Recordatorio",
        "alarms_add_btn": "Agregar",
        "alarms_empty": "No hay alarmas configuradas.",
        "alarms_repeat_label": "Repetir:",
        "alarms_repeat_once": "Una vez",
        "alarms_repeat_daily": "Todos los días",
        "alarms_repeat_weekly": "Días de semana",
        "alarms_repeat_monthly": "Días del mes",
        "alarms_weekday_letters": "LMXJVSD",
        "alarms_days_label": "Días del mes:",
        "alarms_days_hint": "1,15",
        "alarms_days_badge": "día",
        "alarms_badge_once": "una vez",
        "alarms_badge_daily": "todos los días",
        "alarms_break_section": "RECORDATORIOS DE DESCANSO",
        "alarms_break_enabled": "Activar recordatorios de descanso",
        "alarms_interval_label": "Intervalo de trabajo:",
        "alarms_duration_label": "Duración del descanso:",
        "alarms_auto_close_section": "AUTO-CIERRE",
        "alarms_auto_close_enabled": "Cerrar automáticamente por inactividad",
        "alarms_auto_close_after": "Después de:",
        "alarms_close": "Cerrar",
        "ctx_remove_fmt": "Eliminar  {name}",
        "hook_installed_title": "Hook instalado",
        "hook_error_title": "Error",
        "shortcut_ok_fmt": "Acceso directo creado en:\n{path}",
        "shortcut_ok_title": "Listo",
        "shortcut_err_no_vbs": "No se encontró 'Iniciar Mascota.vbs'",
        "shortcut_err_no_desktop": "No se encontró la carpeta Desktop.",
        "levelup_msg_fmt": "Level Up!  Lv.{level}",
        "codex_not_detected": " (Codex no detectado)",
    },
}

_EN_LABELS: dict[str, str] = {
    "verde": "Green", "azul": "Blue", "tierra": "Dirt",
    "nieve": "Snow", "morado": "Purple", "arena": "Sand",
    "oscuro": "Dark", "amarillo": "Yellow", "negro": "Black", "piedra": "Stone",
    "oficina": "Office", "bosque": "Forest", "montanas": "Mountains",
    "noche": "Night", "playa": "Beach", "espacio": "Space",
    "ninguno": "None", "blanco": "White", "dorado": "Gold",
    "rosa": "Pink", "cyan": "Cyan", "rojo": "Red",
    "corona": "Crown", "estrella": "Star", "halo": "Halo",
    "rayo": "Lightning", "corazon": "Heart", "nota": "Note",
    "zzz": "Zzz", "fuego": "Fire", "calavera": "Skull",
    "arcoiris": "Rainbow", "explosion": "Explosion", "diamante": "Diamond",
    "luna": "Moon",
    "planta": "Plant", "alfombra": "Rug", "lampara": "Lamp",
    "globos": "Balloons", "cactus": "Cactus", "computadora": "Computer",
    "cofre": "Chest", "nave": "Spaceship", "acuario": "Aquarium",
    "sombrilla": "Umbrella", "tabla": "Surfboard",
    "fogata": "Campfire", "carpa": "Tent",
    "original": "Original", "verde claro": "Light green",
}


def T(key: str) -> str:
    d = TRANSLATIONS.get(_LANG, TRANSLATIONS["en"])
    return d.get(key, TRANSLATIONS["en"].get(key, key))


def TL(key: str, fallback: str) -> str:
    if _LANG == "en":
        return _EN_LABELS.get(key, fallback)
    return fallback


def _xlate_opts(opts: list) -> list:
    if _LANG == "es":
        return opts
    return [((opt[0], TL(opt[0], opt[1])) + tuple(opt[2:])) for opt in opts]


def _get_all_monitors() -> list[tuple[int, int, int, int]]:
    class _RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
    monitors: list[tuple[int, int, int, int]] = []
    _EnumProc = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.c_ulong, ctypes.c_ulong,
        ctypes.POINTER(_RECT), ctypes.c_double,
    )
    def _cb(hmonitor, hdc, lprect, lparam):
        r = lprect.contents
        monitors.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
        return True
    ctypes.windll.user32.EnumDisplayMonitors(None, None, _EnumProc(_cb), 0)
    if not monitors:
        w = ctypes.windll.user32.GetSystemMetrics(0)
        h = ctypes.windll.user32.GetSystemMetrics(1)
        monitors = [(0, 0, w, h)]
    monitors.sort(key=lambda m: (0 if (m[0] == 0 and m[1] == 0) else 1, m[0], m[1]))
    return monitors


class DataStore:
    _DEFAULTS: dict[str, Any] = {
        "window_x": -1,
        "window_y": -1,
        "opacity": 1.0,
        "break_enabled": True,
        "break_interval_minutes": 50,
        "break_duration_minutes": 5,
        "last_break_time": 0.0,
        "house": {
            "background": "oficina",
            "grass_color": "verde",
            "decorations": [],
            "mascot_tint": "original",
            "decoration_positions": {},
        },
        "characters": [],
        "active_character_id": None,
        "auto_close_enabled": True,
        "auto_close_minutes": AUTO_CLOSE_MINUTES_DEFAULT,
        "alarms": [],
        "greeted_date": "",
        "game_scores": [],
        "language": "en",
        "bg_visible": True,
    }

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, Any] = dict(self._DEFAULTS)
        legacy_path = Path.home() / ".pixel-mascot" / "pixel-mascot_data.json"
        self._path = Path.home() / ".mascota" / "mascota_data.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if legacy_path.exists() and not self._path.exists():
            import shutil as _shutil
            _shutil.copy(str(legacy_path), str(self._path))
        if self._path.exists():
            try:
                loaded = json.loads(self._path.read_text(encoding="utf-8"))
                self._data = {**self._DEFAULTS, **loaded}
                self._migrate()
            except (json.JSONDecodeError, OSError):
                pass

    def _migrate(self) -> None:
        # v1 → v2: move top-level xp/level/xp_enabled into a character
        if "xp" in self._data and not self._data.get("characters"):
            char: dict[str, Any] = {
                "id": "char_001",
                "name": "Mascota",
                "xp": self._data.pop("xp", 0),
                "level": self._data.pop("level", 1),
                "xp_enabled": self._data.pop("xp_enabled", True),
            }
            self._data["characters"] = [char]
            self._data.setdefault("active_character_id", "char_001")
            self._data.setdefault("house", {"level": 1})
            self._save()
        # Clean any leftover legacy keys
        for key in ("xp", "level", "xp_enabled"):
            self._data.pop(key, None)
        # v2 → v3: migrate house-level tint into the active character
        house = self._data.get("house", {})
        if "mascot_tint" in house:
            active_id = self._data.get("active_character_id")
            for c in self._data.get("characters", []):
                if c.get("id") == active_id:
                    c.setdefault("tint", house.pop("mascot_tint", "original"))
                    break
            house.pop("mascot_accessories", None)
            house.pop("accessory_config", None)
            self._data["house"] = house
            self._save()
        # v3 → v4: add sprite_set to existing characters
        changed = False
        for c in self._data.get("characters", []):
            if "sprite_set" not in c:
                c["sprite_set"] = "Dino"
                changed = True
        if changed:
            self._save()
        # v4 → v5: rename old sprite sets; ensure valid sprite_set for all chars
        changed = False
        renames = {"neo": "Dino", "pixel": "Dino", "dino": "Dino", "Max Power": "Dino", "Hongui": "Dino"}
        for c in self._data.get("characters", []):
            sset = c.get("sprite_set", "Dino")
            if sset in renames or sset not in ("Dino",):
                c["sprite_set"] = renames.get(sset, "Dino")
                changed = True
        if changed:
            self._save()

    def _save(self) -> None:
        try:
            self._path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def get(self, key: str) -> Any:
        with self._lock:
            return self._data.get(key, self._DEFAULTS.get(key))

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value
            self._save()

    # ── Character helpers ──────────────────────────────────────────────────

    def get_active_character(self) -> dict[str, Any] | None:
        with self._lock:
            chars: list[dict[str, Any]] = self._data.get("characters", [])
            active_id = self._data.get("active_character_id")
            for c in chars:
                if c.get("id") == active_id:
                    return dict(c)
            return dict(chars[0]) if chars else None

    def get_characters(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(c) for c in self._data.get("characters", [])]

    def add_character(self, name: str) -> dict[str, Any]:
        with self._lock:
            chars: list[dict[str, Any]] = self._data.get("characters", [])
            new_id = f"char_{len(chars) + 1:03d}"
            char: dict[str, Any] = {
                "id": new_id,
                "name": name.strip() or "Mascota",
                "xp": 0,
                "level": 1,
                "xp_enabled": True,
                "tint": "original",
                "outline": "ninguno",
                "floating_item": "ninguno",
                "sprite_set": "Dino",
                "scale_multiplier": 1.0,
            }
            chars.append(char)
            self._data["characters"] = chars
            if not self._data.get("active_character_id"):
                self._data["active_character_id"] = new_id
            self._save()
            return dict(char)

    def get_house(self) -> dict[str, Any]:
        with self._lock:
            stored = self._data.get("house", {})
            defaults = self._DEFAULTS["house"]
            return {**defaults, **stored}

    def update_house(self, **kwargs: Any) -> None:
        with self._lock:
            house = {**self._DEFAULTS["house"], **self._data.get("house", {})}
            house.update(kwargs)
            self._data["house"] = house
            self._save()

    def set_active_character(self, char_id: str) -> None:
        self.set("active_character_id", char_id)

    def delete_character(self, char_id: str) -> None:
        with self._lock:
            chars = [c for c in self._data.get("characters", []) if c.get("id") != char_id]
            self._data["characters"] = chars
            if self._data.get("active_character_id") == char_id:
                self._data["active_character_id"] = chars[0]["id"] if chars else None
            self._save()

    def get_character(self, char_id: str) -> dict[str, Any] | None:
        with self._lock:
            for c in self._data.get("characters", []):
                if c.get("id") == char_id:
                    return dict(c)
            return None

    def update_active_character(self, char_id: str | None = None, **kwargs: Any) -> None:
        with self._lock:
            target_id = char_id or self._data.get("active_character_id")
            for c in self._data.get("characters", []):
                if c.get("id") == target_id:
                    c.update(kwargs)
                    break
            self._save()

    def add_game_score(self, char_id: str, char_name: str, score: int) -> None:
        with self._lock:
            scores: list[dict] = list(self._data.get("game_scores", []))
            scores.append({
                "char_id": char_id,
                "char_name": char_name,
                "score": score,
                "date": time.strftime("%Y-%m-%d"),
            })
            self._data["game_scores"] = scores
            self._save()

    def get_top_scores(self, n: int = 3) -> list[dict]:
        with self._lock:
            scores: list[dict] = list(self._data.get("game_scores", []))
        return sorted(scores, key=lambda x: x.get("score", 0), reverse=True)[:n]


class XPSystem:
    XP_PER_LEVEL = 300

    def __init__(self, store: DataStore) -> None:
        self._store = store
        self._level_up_callback: Any = None

    def on_level_up(self, callback: Any) -> None:
        self._level_up_callback = callback

    def add_xp(self, amount: int, char_id: str | None = None) -> None:
        char = self._store.get_character(char_id) if char_id else self._store.get_active_character()
        if char is None or not char.get("xp_enabled", True):
            return
        old_level = char.get("level", 1)
        new_xp = char.get("xp", 0) + amount
        new_level = new_xp // self.XP_PER_LEVEL + 1
        self._store.update_active_character(char_id=char_id or char.get("id"), xp=new_xp, level=new_level)
        if new_level > old_level and self._level_up_callback is not None:
            self._level_up_callback(new_level, char_id or char.get("id"))

    def get_level(self) -> int:
        char = self._store.get_active_character()
        return char.get("level", 1) if char else 1

    def max_level(self) -> int:
        chars = self._store.get_characters()
        return max((c.get("level", 1) for c in chars), default=1)

    def get_xp(self) -> int:
        char = self._store.get_active_character()
        return char.get("xp", 0) if char else 0

    def get_name(self) -> str:
        char = self._store.get_active_character()
        return char.get("name", "Mascota") if char else "Mascota"

    def xp_in_current_level(self) -> int:
        return self.get_xp() % self.XP_PER_LEVEL

    def bar_text(self) -> str:
        return self._format_bar(self._store.get_active_character())

    def bar_text_for(self, char_id: str) -> str:
        return self._format_bar(self._store.get_character(char_id))

    def _format_bar(self, char: dict[str, Any] | None) -> str:
        if char is None:
            return "Sin personaje"
        name = char.get("name", "?")
        level = char.get("level", 1)
        current = char.get("xp", 0) % self.XP_PER_LEVEL
        filled = current * 8 // self.XP_PER_LEVEL
        bar = "█" * filled + "░" * (8 - filled)
        return f"{name}  Lv.{level}  {bar}"


class BreakSystem:
    MESSAGES = [
        "Hora de estirar las piernas",
        "Toma un vaso de agua",
        "Descansa los ojos un momento",
        "Sal a respirar aire fresco",
        "Levantate y movete un poco",
    ]

    def __init__(self, store: DataStore) -> None:
        self._store = store
        self._snooze_until: float = 0.0
        self._msg_index = 0
        self._store.set("last_break_time", time.time())

    def is_enabled(self) -> bool:
        return bool(self._store.get("break_enabled"))

    def interval_seconds(self) -> float:
        return float(self._store.get("break_interval_minutes")) * 60.0

    def duration_seconds(self) -> float:
        return float(self._store.get("break_duration_minutes")) * 60.0

    def is_due(self) -> bool:
        if not self.is_enabled():
            return False
        elapsed = time.time() - float(self._store.get("last_break_time"))
        return elapsed >= self.interval_seconds()

    def is_snoozed(self) -> bool:
        return time.time() < self._snooze_until

    def banner_visible(self) -> bool:
        return self.is_due() and not self.is_snoozed()

    def mark_taken(self) -> None:
        self._store.set("last_break_time", time.time())
        self._snooze_until = 0.0
        self._msg_index = (self._msg_index + 1) % len(self.MESSAGES)

    def snooze(self) -> None:
        self._snooze_until = time.time() + 600.0

    def banner_text(self) -> str:
        return self.MESSAGES[self._msg_index % len(self.MESSAGES)]


def parse_days_of_month(text: str) -> list[int]:
    """'1, 15' -> [1, 15]. Anything unparseable is dropped, not an error: this comes
    straight from a text box and a typo should not lose the whole alarm."""
    days: list[int] = []
    for chunk in str(text or "").replace(";", ",").replace(" ", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            n = int(chunk)
        except ValueError:
            continue
        if 1 <= n <= 31 and n not in days:
            days.append(n)
    return sorted(days)


# How often an alarm repeats. Monday is 0, like time.struct_time.tm_wday.
REPEAT_ONCE = "once"
REPEAT_DAILY = "daily"
REPEAT_WEEKLY = "weekly"
REPEAT_MONTHLY = "monthly"
REPEAT_MODES = (REPEAT_ONCE, REPEAT_DAILY, REPEAT_WEEKLY, REPEAT_MONTHLY)


def alarm_repeat(alarm: dict) -> str:
    """How often an alarm repeats, including alarms saved before the field existed.

    An old alarm with days of the month is monthly; one with nothing configured is a
    one-off. That last one used to be *described* as "every day" and the engine did
    fire it every day — but the first launch of the next day wiped it, so in practice
    it was a reminder for today and nothing more. Calling it `once` is what actually
    happened. `daily` now means daily and survives the morning.
    """
    mode = str(alarm.get("repeat") or "")
    if mode in REPEAT_MODES:
        return mode
    if alarm.get("days_of_month"):
        return REPEAT_MONTHLY
    if alarm.get("days_of_week"):
        return REPEAT_WEEKLY
    return REPEAT_ONCE


def _clean_days(values: Any, low: int, high: int) -> list[int]:
    out: list[int] = []
    for v in (values or []):
        try:
            n = int(v)
        except (TypeError, ValueError):
            continue
        if low <= n <= high and n not in out:
            out.append(n)
    return sorted(out)


class AlarmSystem:
    def __init__(self, store: DataStore) -> None:
        self._store = store

    def get_alarms(self) -> list[dict]:
        return list(self._store.get("alarms") or [])

    def add_alarm(self, label: str, time_str: str,
                  days_of_month: list[int] | None = None,
                  repeat: str | None = None,
                  days_of_week: list[int] | None = None) -> None:
        dom = _clean_days(days_of_month, 1, 31)
        dow = _clean_days(days_of_week, 0, 6)
        if repeat not in REPEAT_MODES:
            # Callers written before the field existed said it with the arguments.
            repeat = (REPEAT_MONTHLY if dom
                      else REPEAT_WEEKLY if dow
                      else REPEAT_ONCE)
        # A weekly alarm with no weekday ticked and a monthly one with an empty box can
        # never fire. Daily is the honest fallback and the badge in the list says so, so
        # it is a visible choice rather than an alarm that quietly never goes off.
        if (repeat == REPEAT_MONTHLY and not dom) or (repeat == REPEAT_WEEKLY and not dow):
            repeat = REPEAT_DAILY
        alarms = self.get_alarms()
        existing_ids = {a["id"] for a in alarms}
        counter = len(alarms) + 1
        new_id = f"alarm_{counter:03d}"
        while new_id in existing_ids:
            counter += 1
            new_id = f"alarm_{counter:03d}"
        alarms.append({
            "id": new_id,
            "label": label.strip() or "Recordatorio",
            "time": time_str,
            # Written down explicitly instead of inferred from an empty list: an empty
            # list used to mean "every day" to the engine and "delete me tomorrow" to
            # the daily greeting, and the greeting won.
            "repeat": repeat,
            "days_of_month": dom,
            "days_of_week": dow,
            "enabled": True,
            "triggered_date": "",
            # Only used by the catch-up: without it, an alarm added on the 20th for
            # day 15 would fire the moment you saved it, because the catch-up below
            # would see the 15th as a missed run.
            "created_date": time.strftime("%Y-%m-%d"),
            "snooze_until": 0.0,
        })
        self._store.set("alarms", alarms)

    def remove_alarm(self, alarm_id: str) -> None:
        alarms = [a for a in self.get_alarms() if a["id"] != alarm_id]
        self._store.set("alarms", alarms)

    def toggle_alarm(self, alarm_id: str) -> None:
        alarms = self.get_alarms()
        for a in alarms:
            if a["id"] == alarm_id:
                a["enabled"] = not a.get("enabled", True)
                break
        self._store.set("alarms", alarms)

    @staticmethod
    def _recent_months(now: time.struct_time) -> list[tuple[int, int]]:
        y, m = now.tm_year, now.tm_mon
        prev = (y - 1, 12) if m == 1 else (y, m - 1)
        return [prev, (y, m)]

    @staticmethod
    def _already_passed(stamp: str, hm: str, today: str,
                        now_hm: str, created: str) -> bool:
        if stamp > today:
            return False
        if stamp == today and hm > now_hm:
            return False
        if created and stamp < created:
            return False
        return True

    def _last_scheduled(self, alarm: dict, now: time.struct_time) -> str | None:
        """For a weekly or monthly alarm, the date it was last supposed to go off, or
        None if that moment has not come yet.

        This is the catch-up, and it is the whole reason monthly alarms work here:
        Pixel Companion only runs while you are working, so an alarm set for the 1st
        would never fire at all if you did not open the app that day. Looking back at
        the last scheduled date instead of just "is it today" means it fires the next
        time you do open it, and stops as soon as it fires, because triggered_date
        moves past this date. It looks back one month at most, so a laptop that was
        off for a season does not queue up a year of alarms.
        """
        mode = alarm_repeat(alarm)
        hm = alarm.get("time", "")
        created = str(alarm.get("created_date", ""))
        today = time.strftime("%Y-%m-%d", now)
        now_hm = time.strftime("%H:%M", now)

        if mode == REPEAT_WEEKLY:
            wanted = set(alarm.get("days_of_week") or [])
            if not wanted:
                return None
            base = datetime.date(now.tm_year, now.tm_mon, now.tm_mday)
            # Walk back a week at most, so a PC that was off for a month does not
            # queue up four Mondays. The first match going backwards is the latest.
            for back in range(7):
                day = base - datetime.timedelta(days=back)
                if day.weekday() not in wanted:
                    continue
                stamp = day.isoformat()
                if self._already_passed(stamp, hm, today, now_hm, created):
                    return stamp
            return None

        days = alarm.get("days_of_month") or []
        if not days:
            return None
        best: str | None = None
        for year, month in self._recent_months(now):
            last_day = calendar.monthrange(year, month)[1]
            for d in days:
                # Day 31 in a 30-day month lands on the last day of that month. The
                # alternative is that it silently never fires, which is the worst kind
                # of reminder: one you think you set.
                stamp = f"{year:04d}-{month:02d}-{min(d, last_day):02d}"
                if not self._already_passed(stamp, hm, today, now_hm, created):
                    continue
                if best is None or stamp > best:
                    best = stamp
        return best

    def check_due(self) -> dict | None:
        now = time.localtime()
        today = time.strftime("%Y-%m-%d", now)
        now_hm = time.strftime("%H:%M", now)
        for a in self.get_alarms():
            if not a.get("enabled", True):
                continue
            if time.time() < float(a.get("snooze_until", 0.0)):
                continue

            if alarm_repeat(a) in (REPEAT_WEEKLY, REPEAT_MONTHLY):
                due = self._last_scheduled(a, now)
                if due and str(a.get("triggered_date", "")) < due:
                    return a
                continue

            # Once and daily: both fire when the clock passes the hour, at most once a
            # day. What separates them is whether tomorrow's greeting deletes them.
            if a.get("triggered_date") == today:
                continue
            if a.get("time", "") <= now_hm:
                return a
        return None

    def mark_triggered(self, alarm_id: str) -> None:
        today = time.strftime("%Y-%m-%d")
        alarms = self.get_alarms()
        for a in alarms:
            if a["id"] == alarm_id:
                a["triggered_date"] = today
                a["snooze_until"] = 0.0
                break
        self._store.set("alarms", alarms)

    def snooze_alarm(self, alarm_id: str, minutes: int = 10) -> None:
        alarms = self.get_alarms()
        for a in alarms:
            if a["id"] == alarm_id:
                a["snooze_until"] = time.time() + minutes * 60.0
                a["triggered_date"] = ""
                break
        self._store.set("alarms", alarms)


@dataclass
class SessionData:
    session_id: str
    cwd: str
    sprite_x: float = 0.5
    sprite_y_offset: float = 0.0
    started_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    state: str = "idle"
    last_prompt: str = ""
    current_tool: str = ""
    permission_mode: str = "default"
    interactive: bool = True
    emotion: str = "neutral"
    emotion_scores: dict[str, float] = field(default_factory=lambda: {"happy": 0.0, "sad": 0.0})
    last_emotion_update: float = field(default_factory=time.time)
    events: list[str] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    character_id: str | None = None
    needs_character_selection: bool = False
    claude_pid: int = 0
    agent_type: str = "claude"
    transcript_path: str = ""

    @property
    def project_name(self) -> str:
        path = Path(self.cwd)
        return path.name or self.cwd or "unknown"

    @property
    def duration(self) -> str:
        total = int(time.time() - self.started_at)
        minutes, seconds = divmod(total, 60)
        return f"{minutes}m {seconds:02d}s"


class ConversationParser:
    def __init__(self) -> None:
        self._offsets: dict[str, int] = {}
        self._seen_ids: dict[str, set[str]] = {}
        self._lock = threading.Lock()

    def mark_current_position(self, session_id: str, cwd: str) -> None:
        path = self.session_file_path(session_id, cwd)
        with self._lock:
            if not path.exists():
                self._offsets[session_id] = 0
                self._seen_ids[session_id] = set()
                return
            self._offsets[session_id] = path.stat().st_size
            self._seen_ids[session_id] = set()

    def reset(self, session_id: str) -> None:
        with self._lock:
            self._offsets.pop(session_id, None)
            self._seen_ids.pop(session_id, None)

    def parse_incremental(self, session_id: str, cwd: str) -> list[str]:
        path = self.session_file_path(session_id, cwd)
        if not path.exists():
            return []

        with self._lock:
            offset = self._offsets.get(session_id, 0)
            seen_ids = self._seen_ids.setdefault(session_id, set())
            file_size = path.stat().st_size
            if file_size < offset:
                offset = 0
                seen_ids.clear()

            if file_size == offset:
                return []

            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                handle.seek(offset)
                chunk = handle.read()

            self._offsets[session_id] = file_size

        messages: list[str] = []
        for line in chunk.splitlines():
            line = line.strip()
            if not line:
                continue

            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue

            if payload.get("type") != "assistant":
                continue

            message_id = payload.get("uuid")
            if not message_id or message_id in seen_ids:
                continue

            if payload.get("isMeta") is True:
                continue

            message = payload.get("message", {})
            content = message.get("content")
            text = self._extract_text(content)
            if not text:
                continue

            seen_ids.add(message_id)
            messages.append(text)

        return messages

    @staticmethod
    def _extract_text(content: Any) -> str:
        if isinstance(content, str):
            text = content.strip()
            return text if text and not text.startswith("[Request interrupted") else ""

        if not isinstance(content, list):
            return ""

        parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "text":
                continue
            text = str(block.get("text", "")).strip()
            if text and not text.startswith("[Request interrupted"):
                parts.append(text)
        return "\n".join(parts).strip()

    def parse_incremental_codex(self, session_id: str, transcript_path: str) -> list[str]:
        if not transcript_path:
            return []
        path = Path(transcript_path)
        if not path.exists():
            return []

        with self._lock:
            offset = self._offsets.get(session_id, 0)
            seen_ids = self._seen_ids.setdefault(session_id, set())
            file_size = path.stat().st_size
            if file_size < offset:
                offset = 0
                seen_ids.clear()
            if file_size == offset:
                return []
            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                handle.seek(offset)
                chunk = handle.read()
            self._offsets[session_id] = file_size

        messages: list[str] = []
        for line in chunk.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Codex uses OpenAI conversation format: {"role": "assistant", ...}
            if payload.get("role") != "assistant":
                continue

            message_id = payload.get("id") or payload.get("turn_id")
            if message_id and message_id in seen_ids:
                continue

            content = payload.get("content")
            text = self._extract_text(content)
            if not text:
                continue

            if message_id:
                seen_ids.add(message_id)
            messages.append(text)

        return messages

    def mark_current_position_from_path(self, session_id: str, transcript_path: str) -> None:
        if not transcript_path:
            return
        path = Path(transcript_path)
        with self._lock:
            if not path.exists():
                self._offsets[session_id] = 0
                self._seen_ids[session_id] = set()
                return
            self._offsets[session_id] = path.stat().st_size
            self._seen_ids[session_id] = set()

    @staticmethod
    def session_file_path(session_id: str, cwd: str) -> Path:
        project_dir = cwd.replace("/", "-").replace("\\", "-").replace(".", "-").replace(":", "")
        return Path.home() / ".claude" / "projects" / project_dir / f"{session_id}.jsonl"


class EmotionAnalyzer:
    HAPPY_WORDS = {
        "thanks", "thank you", "great", "awesome", "nice", "perfect", "love", "happy",
        "good", "cool", "excellent", "yay", "success", "worked", "win",
    }
    SAD_WORDS = {
        "error", "fail", "failed", "broken", "bug", "sad", "frustrated", "stuck",
        "annoying", "bad", "issue", "problem", "hate", "wrong", "sob", "can't", "cannot",
    }
    CALM_WORDS = {
        "okay", "ok", "sure", "sounds good", "fixed", "resolved", "done", "complete",
        "completed", "all set", "no worries", "works now",
    }

    @classmethod
    def update_session_emotion(cls, session: SessionData, text: str, source: str) -> None:
        cls.decay_session_emotion(session)
        emotion, intensity = cls.analyze(text)
        dampen = PROMPT_EMOTION_DAMPEN if source == "prompt" else REPLY_EMOTION_DAMPEN
        if emotion == "neutral":
            session.emotion_scores["happy"] *= 0.9
            session.emotion_scores["sad"] *= 0.9
        else:
            session.emotion_scores[emotion] = min(
                1.0,
                session.emotion_scores.get(emotion, 0.0) + intensity * dampen,
            )
            other = "sad" if emotion == "happy" else "happy"
            cross_decay = 0.9 if source == "reply" else 0.85
            session.emotion_scores[other] *= cross_decay

        session.last_emotion_update = time.time()
        cls.resolve_session_emotion(session)

    @classmethod
    def decay_session_emotion(cls, session: SessionData) -> None:
        now = time.time()
        elapsed = max(0.0, now - session.last_emotion_update)
        if elapsed <= 0:
            return

        # Roughly match the macOS app's gradual fade by decaying per minute.
        factor = EMOTION_DECAY ** (elapsed / 60.0)
        for key in list(session.emotion_scores):
            value = session.emotion_scores[key] * factor
            session.emotion_scores[key] = 0.0 if value < 0.01 else value
        session.last_emotion_update = now
        cls.resolve_session_emotion(session)

    @classmethod
    def resolve_session_emotion(cls, session: SessionData) -> None:
        happy = session.emotion_scores.get("happy", 0.0)
        sad = session.emotion_scores.get("sad", 0.0)
        if sad >= SOB_THRESHOLD:
            session.emotion = "sob"
        elif sad >= SAD_THRESHOLD:
            session.emotion = "sad"
        elif happy >= HAPPY_THRESHOLD:
            session.emotion = "happy"
        else:
            session.emotion = "neutral"

    @classmethod
    def analyze(cls, text: str) -> tuple[str, float]:
        lowered = text.lower()
        happy_hits = sum(1 for word in cls.HAPPY_WORDS if word in lowered)
        sad_hits = sum(1 for word in cls.SAD_WORDS if word in lowered)
        calm_hits = sum(1 for word in cls.CALM_WORDS if word in lowered)

        if calm_hits > 0 and happy_hits == sad_hits == 0:
            return "neutral", 0.0
        if happy_hits == sad_hits == 0:
            return "neutral", 0.0
        if sad_hits > happy_hits:
            return "sad", min(1.0, 0.35 + sad_hits * 0.2)
        if happy_hits > sad_hits:
            return "happy", min(1.0, 0.35 + happy_hits * 0.18)
        return "neutral", 0.0


class SessionStore:
    def __init__(self, parser: ConversationParser, xp_system: "XPSystem | None" = None) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, SessionData] = {}
        self._parser = parser
        self._selected_session_id: str | None = None
        self._xp_system = xp_system

    def process(self, payload: dict[str, Any]) -> None:
        session_id = payload.get("session_id") or "unknown"
        cwd = payload.get("cwd") or ""
        event_name = payload.get("event", "")
        status = payload.get("status", "")
        tool = payload.get("tool") or ""
        new_messages: list[str] = []

        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                sprite_x, sprite_y_offset = self._resolve_sprite_position(
                    session_id,
                    [item.sprite_x for item in self._sessions.values()],
                )
                session = SessionData(
                    session_id=session_id,
                    cwd=cwd,
                    sprite_x=sprite_x,
                    sprite_y_offset=sprite_y_offset,
                    needs_character_selection=True,
                )
                self._sessions[session_id] = session
                if self._selected_session_id is None:
                    self._selected_session_id = session_id

            session.cwd = cwd or session.cwd
            session.last_activity = time.time()
            session.permission_mode = payload.get("permission_mode", session.permission_mode)
            session.interactive = payload.get("interactive", session.interactive)
            pid = int(payload.get("claude_pid") or 0)
            if pid:
                session.claude_pid = pid
            agent_type = payload.get("agent_type", "claude")
            session.agent_type = agent_type
            transcript_path = payload.get("transcript_path") or ""
            if transcript_path:
                session.transcript_path = transcript_path

            if event_name == "UserPromptSubmit":
                prompt = (payload.get("user_prompt") or "").strip()
                if prompt:
                    session.last_prompt = prompt[:120]
                    EmotionAnalyzer.update_session_emotion(session, prompt, source="prompt")
                session.messages = []
                session.state = "working"
                session.current_tool = ""
                if agent_type == "codex":
                    self._parser.mark_current_position_from_path(session_id, session.transcript_path)
                else:
                    self._parser.mark_current_position(session_id, session.cwd)
            elif event_name == "PreToolUse":
                session.state = "working"
                session.current_tool = tool
            elif event_name == "PermissionRequest":
                session.state = "waiting"
                session.current_tool = tool
            elif event_name == "PreCompact":
                if agent_type != "codex":
                    session.state = "compacting"
            elif event_name in {"PostToolUse", "Stop", "SubagentStop"}:
                if event_name in {"Stop", "SubagentStop"} or status == "waiting_for_input":
                    session.state = "idle"
                    session.current_tool = ""
                    if event_name in {"Stop", "SubagentStop"} and self._xp_system is not None:
                        self._xp_system.add_xp(3, char_id=session.character_id)
                elif session.state == "waiting":
                    session.state = "working"
                    session.current_tool = ""
                if agent_type == "codex":
                    new_messages = self._parser.parse_incremental_codex(session_id, session.transcript_path)
                    if event_name == "PostToolUse" and self._xp_system is not None:
                        self._xp_system.add_xp(3, char_id=session.character_id)
                else:
                    new_messages = self._parser.parse_incremental(session_id, session.cwd)
            elif event_name == "SessionStart":
                session.state = "working" if status != "waiting_for_input" else "idle"
            elif event_name == "SessionEnd":
                if agent_type != "codex":
                    if self._xp_system is not None:
                        self._xp_system.add_xp(2, char_id=session.character_id)
                    self._sessions.pop(session_id, None)
                    self._parser.reset(session_id)
                    if self._selected_session_id == session_id:
                        self._selected_session_id = next(iter(self._sessions), None)
                    return
            elif status == "waiting_for_input":
                session.state = "idle"

            line = self._format_event_line(event_name, tool, status)
            if line:
                session.events.append(line)
                session.events = session.events[-MAX_EVENTS:]

            if new_messages:
                session.messages.extend(new_messages)
                session.messages = session.messages[-MAX_MESSAGES:]
                for message in new_messages:
                    EmotionAnalyzer.update_session_emotion(session, message, source="reply")
            else:
                EmotionAnalyzer.decay_session_emotion(session)

    def snapshot(self) -> list[SessionData]:
        with self._lock:
            for session in self._sessions.values():
                self._apply_sleep_state_locked(session)
                EmotionAnalyzer.decay_session_emotion(session)
            return sorted(
                [self._copy_session(session) for session in self._sessions.values()],
                key=lambda item: item.last_activity,
                reverse=True,
            )

    def selected_session_id(self) -> str | None:
        with self._lock:
            return self._selected_session_id

    def sessions_needing_character(self) -> list[str]:
        with self._lock:
            return [sid for sid, s in self._sessions.items() if s.needs_character_selection]

    def assign_character(self, session_id: str, char_id: str) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.character_id = char_id
                session.needs_character_selection = False

    def unassign_character_by_id(self, char_id: str) -> None:
        with self._lock:
            for session in self._sessions.values():
                if session.character_id == char_id:
                    session.character_id = None
                    session.needs_character_selection = True

    def remove_session(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
            self._parser.reset(session_id)
            if self._selected_session_id == session_id:
                self._selected_session_id = next(iter(self._sessions), None)

    def select_session(self, session_id: str | None) -> None:
        with self._lock:
            if session_id is None or session_id in self._sessions:
                self._selected_session_id = session_id

    def effective_session(self) -> SessionData | None:
        with self._lock:
            for session in self._sessions.values():
                self._apply_sleep_state_locked(session)
            target = self._sessions.get(self._selected_session_id or "")
            if target is not None:
                return self._copy_session(target)
            if not self._sessions:
                return None
            session = max(self._sessions.values(), key=lambda item: item.last_activity)
            return self._copy_session(session)

    @staticmethod
    def _copy_session(session: SessionData) -> SessionData:
        return SessionData(
            session_id=session.session_id,
            cwd=session.cwd,
            sprite_x=session.sprite_x,
            sprite_y_offset=session.sprite_y_offset,
            started_at=session.started_at,
            last_activity=session.last_activity,
            state=session.state,
            last_prompt=session.last_prompt,
            current_tool=session.current_tool,
            permission_mode=session.permission_mode,
            interactive=session.interactive,
            emotion=session.emotion,
            emotion_scores=dict(session.emotion_scores),
            last_emotion_update=session.last_emotion_update,
            events=list(session.events),
            messages=list(session.messages),
            character_id=session.character_id,
            needs_character_selection=session.needs_character_selection,
        )

    @staticmethod
    def _resolve_sprite_position(session_id: str, existing_positions: list[float]) -> tuple[float, float]:
        x_position_min = 0.08
        x_position_range = 0.82
        x_min_separation = 0.14
        x_nudge_step = 0.23

        hashed = abs(hash(session_id))
        candidate = x_position_min + (hashed % 820) / 1000.0
        for _ in range(10):
            too_close = any(abs(current - candidate) < x_min_separation for current in existing_positions)
            if not too_close:
                break
            candidate = ((candidate - x_position_min + x_nudge_step) % x_position_range) + x_position_min

        y_offset = -float((hashed >> 8) % 18)
        return candidate, y_offset

    @staticmethod
    def _apply_sleep_state_locked(session: SessionData) -> None:
        if time.time() - session.last_activity > SESSION_SLEEP_SECONDS and session.state == "idle":
            session.state = "sleeping"

    @staticmethod
    def _format_event_line(event_name: str, tool: str, status: str) -> str:
        labels = {
            "UserPromptSubmit": "Prompt submitted",
            "SessionStart": "Session started",
            "PreToolUse": f"Running {tool or 'tool'}",
            "PostToolUse": f"Finished {tool or 'tool'}",
            "PermissionRequest": f"Permission requested for {tool or 'tool'}",
            "PreCompact": "Compacting context",
            "Stop": "Claude is waiting",
            "SubagentStop": "Subagent is waiting",
            "SessionEnd": "Session ended",
        }
        suffix = " (error)" if status == "error" else ""
        return labels.get(event_name, event_name) + suffix


class HookInstaller:
    def __init__(self, app_dir: Path) -> None:
        self.app_dir = app_dir
        self.claude_dir = Path.home() / ".claude"
        self.hooks_dir = self.claude_dir / "hooks"
        self.settings_path = self.claude_dir / "settings.json"
        self.installed_hook = self.hooks_dir / "mascota-hook.ps1"

    def install(self) -> tuple[bool, str]:
        if not self.claude_dir.exists():
            return False, f"Claude config directory not found: {self.claude_dir}"

        self.hooks_dir.mkdir(parents=True, exist_ok=True)
        hook_source = self.app_dir / "mascota-hook.ps1"
        hook_text = hook_source.read_text(encoding="utf-8")
        hook_text = hook_text.replace("__MASCOTA_APP_DIR__", str(self.app_dir))
        self.installed_hook.write_text(hook_text, encoding="utf-8")

        data: dict[str, Any] = {}
        if self.settings_path.exists():
            try:
                data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = {}

        hooks = data.get("hooks", {})
        command = f'powershell -NoProfile -ExecutionPolicy Bypass -File "{self.installed_hook}"'
        entry = [{"type": "command", "command": command}]
        with_matcher = [{"matcher": "*", "hooks": entry}]
        without_matcher = [{"hooks": entry}]
        precompact = [{"matcher": "auto", "hooks": entry}, {"matcher": "manual", "hooks": entry}]

        config_by_event = {
            "UserPromptSubmit": without_matcher,
            "SessionStart": without_matcher,
            "PreToolUse": with_matcher,
            "PostToolUse": with_matcher,
            "PermissionRequest": with_matcher,
            "PreCompact": precompact,
            "Stop": without_matcher,
            "SubagentStop": without_matcher,
            "SessionEnd": without_matcher,
        }

        for event_name, config in config_by_event.items():
            existing = hooks.get(event_name, [])
            if not any(self._contains_mascota_hook(item) for item in existing):
                existing.extend(config)
            hooks[event_name] = existing

        data["hooks"] = hooks
        self.settings_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        return True, f"Installed hook into {self.installed_hook}"

    def is_installed(self) -> bool:
        if not self.settings_path.exists():
            return False
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False
        hooks = data.get("hooks", {})
        return any(
            self._contains_mascota_hook(item)
            for event_entries in hooks.values()
            for item in event_entries
        )

    @staticmethod
    def _contains_mascota_hook(entry: dict[str, Any]) -> bool:
        for hook in entry.get("hooks", []):
            command = hook.get("command", "")
            if "mascota-hook.ps1" in command:
                return True
        return False


class CodexHookInstaller:
    def __init__(self, app_dir: Path) -> None:
        self.app_dir = app_dir
        self.codex_dir = Path.home() / ".codex"
        self.hooks_path = self.codex_dir / "hooks.json"
        self.installed_hook = self.codex_dir / "mascota-codex-hook.ps1"

    def install(self) -> tuple[bool, str]:
        if not self.codex_dir.exists():
            return False, f"Codex config directory not found: {self.codex_dir}"

        hook_source = self.app_dir / "codex-hook.ps1"
        if not hook_source.exists():
            return False, f"Hook source not found: {hook_source}"

        hook_text = hook_source.read_text(encoding="utf-8")
        hook_text = hook_text.replace("__MASCOTA_APP_DIR__", str(self.app_dir))
        self.installed_hook.write_text(hook_text, encoding="utf-8")

        data: dict[str, Any] = {}
        if self.hooks_path.exists():
            try:
                data = json.loads(self.hooks_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = {}

        hooks = data.get("hooks", {})
        command = f'powershell -NoProfile -ExecutionPolicy Bypass -File "{self.installed_hook}"'
        entry = [{"type": "command", "command": command}]
        with_matcher = [{"matcher": "*", "hooks": entry}]
        without_matcher = [{"hooks": entry}]

        config_by_event = {
            "UserPromptSubmit": without_matcher,
            "SessionStart": without_matcher,
            "PreToolUse": with_matcher,
            "PostToolUse": with_matcher,
            "PermissionRequest": with_matcher,
            "Stop": without_matcher,
        }

        for event_name, config in config_by_event.items():
            existing = hooks.get(event_name, [])
            if not any(self._contains_mascota_hook(item) for item in existing):
                existing.extend(config)
            hooks[event_name] = existing

        data["hooks"] = hooks
        self.hooks_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        return True, f"Installed Codex hook into {self.installed_hook}"

    def is_installed(self) -> bool:
        if not self.hooks_path.exists():
            return False
        try:
            data = json.loads(self.hooks_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False
        hooks = data.get("hooks", {})
        return any(
            self._contains_mascota_hook(item)
            for event_entries in hooks.values()
            for item in event_entries
        )

    @staticmethod
    def _contains_mascota_hook(entry: dict[str, Any]) -> bool:
        for hook in entry.get("hooks", []):
            command = hook.get("command", "")
            if "mascota-codex-hook.ps1" in command:
                return True
        return False


class SpriteRenderer:
    def __init__(self, assets_dir: Path) -> None:
        self.assets_dir = assets_dir
        self._cache: dict[tuple, ImageTk.PhotoImage] = {}
        self._frame_count_cache: dict[tuple, int] = {}

    def invalidate(self) -> None:
        self._cache.clear()
        self._frame_count_cache.clear()

    def available_sets(self) -> list[str]:
        sets = []
        for item in sorted(self.assets_dir.iterdir()):
            if item.is_dir() and (item / "idle_neutral.imageset" / "sprite_sheet.png").exists():
                sets.append(item.name)
        return sets or ["Dino"]

    def _frame_count_for(self, sprite_set: str, state: str, emotion: str) -> int:
        """Auto-detect frame count from spritesheet width. Prefers 6, falls back to 5."""
        key = (sprite_set, state, emotion)
        if key in self._frame_count_cache:
            return self._frame_count_cache[key]
        if state == "compacting":
            count = 5
        else:
            sprite_dir = self.assets_dir / sprite_set
            sprite_name = self._sprite_name_for(state, emotion, sprite_dir)
            path = sprite_dir / f"{sprite_name}.imageset" / "sprite_sheet.png"
            count = 6
            try:
                with Image.open(path) as img:
                    w = img.width
                if w % 6 == 0:
                    count = 6
                elif w % 5 == 0:
                    count = 5
            except Exception:
                pass
        self._frame_count_cache[key] = count
        return count

    def get_frame(self, state: str, emotion: str, frame_index: int, scale: float = 2.0,
                  tint: tuple[int, int, int] | None = None,
                  outline_rgb: tuple[int, int, int] | None = None,
                  sprite_set: str = "Dino") -> ImageTk.PhotoImage:
        frame_count = self._frame_count_for(sprite_set, state, emotion)
        normalized = frame_index % frame_count
        scale_key = int(scale * 100)
        cache_key = (sprite_set, f"{state}:{emotion}", normalized, scale_key, tint, outline_rgb)
        if cache_key not in self._cache:
            image = self._load_frame_image(state, emotion, normalized, scale, tint, outline_rgb, sprite_set)
            self._cache[cache_key] = ImageTk.PhotoImage(image)
        return self._cache[cache_key]

    def _load_frame_image(self, state: str, emotion: str, frame_index: int, scale: float,
                          tint: tuple[int, int, int] | None = None,
                          outline_rgb: tuple[int, int, int] | None = None,
                          sprite_set: str = "Dino") -> Image.Image:
        sprite_dir = self.assets_dir / sprite_set
        sprite_name = self._sprite_name_for(state, emotion, sprite_dir)
        path = sprite_dir / f"{sprite_name}.imageset" / "sprite_sheet.png"
        sheet = Image.open(path).convert("RGBA")
        if state == "compacting":
            columns = 5
        elif sheet.width % 6 == 0:
            columns = 6
        elif sheet.width % 5 == 0:
            columns = 5
        else:
            columns = 6
        frame_width = sheet.width // columns
        frame = sheet.crop((frame_index * frame_width, 0, (frame_index + 1) * frame_width, sheet.height))
        alpha_box = frame.getchannel("A").getbbox()
        if alpha_box is not None:
            left, top, right, bottom = alpha_box
            padding = 2
            frame = frame.crop((
                max(0, left - padding),
                max(0, top - padding),
                min(frame.width, right + padding),
                min(frame.height, bottom + padding),
            ))
        scaled_width = max(4, int(frame.width * scale))
        scaled_height = max(4, int(frame.height * scale))
        frame = frame.resize((scaled_width, scaled_height), Image.Resampling.NEAREST)
        if tint is not None:
            frame = SpriteRenderer._apply_tint_hsv(frame, tint)
        if outline_rgb is not None:
            frame = self._add_outline(frame, outline_rgb)
        return frame

    @staticmethod
    def _apply_tint_hsv(frame: Image.Image, tint_rgb: tuple[int, int, int]) -> Image.Image:
        import colorsys
        tr, tg, tb = tint_rgb
        th, ts, _ = colorsys.rgb_to_hsv(tr / 255, tg / 255, tb / 255)
        pixels = list(frame.getdata())
        out = []
        for r, g, b, a in pixels:
            if a < 12:
                out.append((r, g, b, a))
                continue
            ph, ps, pv = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            nr, ng, nb = colorsys.hsv_to_rgb(th, max(0.25, ts * 0.8 + ps * 0.2), pv)
            out.append((int(nr * 255), int(ng * 255), int(nb * 255), a))
        result = frame.copy()
        result.putdata(out)
        return result

    @staticmethod
    def _add_outline(frame: Image.Image, rgb: tuple[int, int, int]) -> Image.Image:
        alpha = frame.getchannel("A")
        expanded = alpha.filter(ImageFilter.MaxFilter(3))
        outline_mask = ImageChops.subtract(expanded, alpha)
        r, g, b = rgb
        outline_layer = Image.new("RGBA", frame.size, (r, g, b, 0))
        outline_layer.putalpha(outline_mask)
        return Image.alpha_composite(outline_layer, frame)

    def _sprite_name_for(self, state: str, emotion: str, sprite_dir: Path | None = None) -> str:
        base = sprite_dir or (self.assets_dir / "Dino")
        requested = f"{state}_{emotion}"
        fallback_order = [requested]
        if emotion == "sob":
            fallback_order.append(f"{state}_sad")
        fallback_order.append(f"{state}_neutral")
        # States without dedicated sprites fall back to sleeping
        if state not in {"idle", "working", "waiting", "compacting", "sleeping"}:
            fallback_order.append(f"sleeping_{emotion}")
            fallback_order.append("sleeping_neutral")
            fallback_order.append("idle_neutral")

        for name in fallback_order:
            if (base / f"{name}.imageset" / "sprite_sheet.png").exists():
                return name
        return "idle_neutral"


class BackgroundRenderer:
    def __init__(self, assets_dir: Path) -> None:
        self._bg_path = assets_dir / "backgrounds" / "bg_default.png"
        self._cache: dict[tuple, ImageTk.PhotoImage] = {}

    def draw(self, canvas: tk.Canvas, width: int, height: int,
             theme: str = "oficina",
             ground_color: tuple[int, int, int] | None = None,
             x_offset: int = 0) -> None:
        key = (width, height, theme, ground_color)
        if key not in self._cache:
            self._cache[key] = self._build(width, height, theme, ground_color)
        img = self._cache[key]
        off = x_offset % width
        if off == 0:
            canvas.create_image(0, 0, image=img, anchor="nw")
        else:
            canvas.create_image(-off, 0, image=img, anchor="nw")
            canvas.create_image(-off + width, 0, image=img, anchor="nw")

    def invalidate(self) -> None:
        self._cache.clear()

    def _build(self, width: int, height: int, theme: str,
               ground_color: tuple[int, int, int] | None) -> ImageTk.PhotoImage:
        if self._bg_path.exists():
            try:
                img = Image.open(self._bg_path).convert("RGBA")
                img = img.resize((width, height), Image.Resampling.NEAREST)
                return ImageTk.PhotoImage(img)
            except OSError:
                pass
        builders = {
            "oficina":  self._build_oficina,
            "bosque":   self._build_bosque,
            "montanas": self._build_montanas,
            "noche":    self._build_noche,
            "playa":    self._build_playa,
            "espacio":  self._build_espacio,
        }
        img = builders.get(theme, self._build_oficina)(width, height, ground_color)
        return ImageTk.PhotoImage(img)

    @staticmethod
    def _build_oficina(width: int, height: int,
                       ground_color: tuple[int, int, int] | None = None) -> Image.Image:
        gc = ground_color or (138, 116, 96)
        img = Image.new("RGBA", (width, height))
        d = ImageDraw.Draw(img)
        floor_y = int(height * 0.62)
        d.rectangle([0, 0, width, floor_y], fill=(192, 182, 170, 255))
        d.rectangle([0, floor_y - 5, width, floor_y - 1], fill=(158, 145, 128, 255))
        d.rectangle([0, floor_y, width, height], fill=(*gc, 255))
        d.rectangle([0, floor_y, width, floor_y + 2], fill=(*_lighten(gc), 255))
        wy = int(height * 0.07)
        ww, wh = int(width * 0.22), int(height * 0.40)
        sh = int(height * 0.42)
        sw = int(width * 0.14)
        book_colors = [(180, 80, 60), (80, 130, 180), (90, 160, 90), (200, 170, 60)]
        bw = sw // len(book_colors) - 1
        # Draw window+shelf pairs every half-width, tiled at -width/0/+width offsets
        for base in [int(width * 0.00), int(width * 0.50)]:
            for ox in [-width, 0, width]:
                wx = base + int(width * 0.08) + ox
                d.rectangle([wx, wy, wx + ww, wy + wh], fill=(178, 218, 238, 255))
                d.rectangle([wx, wy, wx + ww, wy + wh], outline=(110, 90, 72, 255), width=2)
                mx, my = wx + ww // 2, wy + wh // 2
                d.rectangle([mx - 1, wy + 2, mx + 1, wy + wh - 2], fill=(110, 90, 72, 255))
                d.rectangle([wx + 2, my - 1, wx + ww - 2, my + 1], fill=(110, 90, 72, 255))
                sx = base + int(width * 0.36) + ox
                d.rectangle([sx, wy, sx + sw, wy + sh], fill=(158, 130, 100, 255))
                d.rectangle([sx, wy, sx + sw, wy + sh], outline=(110, 90, 72, 255), width=1)
                for i, color in enumerate(book_colors):
                    bx = sx + 2 + i * (bw + 1)
                    d.rectangle([bx, wy + 4, bx + bw, wy + sh // 2 - 2], fill=(*color, 255))
        return img

    @staticmethod
    def _build_bosque(width: int, height: int,
                      ground_color: tuple[int, int, int] | None = None) -> Image.Image:
        gc = ground_color or (72, 110, 72)
        img = Image.new("RGBA", (width, height))
        d = ImageDraw.Draw(img)
        floor_y = int(height * 0.62)
        d.rectangle([0, 0, width, floor_y], fill=(168, 210, 238, 255))
        d.rectangle([0, floor_y, width, height], fill=(*gc, 255))
        th = int(height * 0.48)
        tw = int(width * 0.07)
        # Trees evenly spaced every 25%, tiled at -width/0/+width
        for xr in [0.12, 0.37, 0.62, 0.87]:
            for ox in [-width, 0, width]:
                tx = int(width * xr) + ox
                d.polygon([tx, floor_y - th, tx - tw, floor_y - th // 3, tx + tw, floor_y - th // 3],
                          fill=(48, 90, 48, 255))
                d.polygon([tx, floor_y - int(th * 0.72), tx - int(tw * 1.2), floor_y - int(th * 0.22),
                           tx + int(tw * 1.2), floor_y - int(th * 0.22)], fill=(60, 110, 60, 255))
                d.rectangle([tx - 2, floor_y - int(th * 0.22), tx + 2, floor_y], fill=(90, 60, 40, 255))
        return img

    @staticmethod
    def _build_noche(width: int, height: int,
                     ground_color: tuple[int, int, int] | None = None) -> Image.Image:
        import random
        gc = ground_color or (28, 36, 28)
        img = Image.new("RGBA", (width, height))
        d = ImageDraw.Draw(img)
        floor_y = int(height * 0.62)
        d.rectangle([0, 0, width, floor_y], fill=(18, 22, 50, 255))
        d.rectangle([0, floor_y, width, height], fill=(*gc, 255))
        # Stars seeded across the full width (seamless: random within width)
        rng = random.Random(42)
        for _ in range(55):
            sx = rng.randint(0, width - 1)
            sy = rng.randint(0, floor_y - 4)
            br = rng.randint(140, 255)
            d.ellipse([sx - 1, sy - 1, sx + 1, sy + 1], fill=(br, br, br, 255))
        # Moon centered at 30%, tiled so it wraps seamlessly
        mr = int(height * 0.10)
        my = int(height * 0.14)
        for ox in [-width, 0, width]:
            mx = int(width * 0.30) + ox
            d.ellipse([mx - mr, my - mr, mx + mr, my + mr], fill=(240, 238, 210, 255))
            d.ellipse([mx + mr // 3, my - mr, mx + mr + mr // 2, my + mr // 2],
                      fill=(18, 22, 50, 255))
        return img

    @staticmethod
    def _build_playa(width: int, height: int,
                     ground_color: tuple[int, int, int] | None = None) -> Image.Image:
        gc = ground_color or (198, 174, 130)
        img = Image.new("RGBA", (width, height))
        d = ImageDraw.Draw(img)
        floor_y = int(height * 0.62)
        horizon = int(floor_y * 0.65)
        d.rectangle([0, 0, width, horizon], fill=(132, 196, 232, 255))
        d.rectangle([0, horizon, width, floor_y], fill=(68, 140, 192, 255))
        d.rectangle([0, floor_y, width, height], fill=(*gc, 255))
        d.line([0, horizon, width, horizon], fill=(90, 160, 210, 255), width=1)
        # Sun at 25% tiled so it wraps seamlessly
        sy_pos, sr = int(height * 0.12), int(height * 0.09)
        for ox in [-width, 0, width]:
            sx = int(width * 0.25) + ox
            d.ellipse([sx - sr, sy_pos - sr, sx + sr, sy_pos + sr], fill=(255, 220, 60, 255))
        return img

    @staticmethod
    def _build_montanas(width: int, height: int,
                        ground_color: tuple[int, int, int] | None = None) -> Image.Image:
        import random
        gc = ground_color or (210, 225, 240)
        img = Image.new("RGBA", (width, height))
        d = ImageDraw.Draw(img)
        sky_top = (170, 210, 240, 255)
        sky_bot = (220, 235, 250, 255)
        for y in range(height):
            t = y / height
            r = int(sky_top[0] + (sky_bot[0] - sky_top[0]) * t)
            g = int(sky_top[1] + (sky_bot[1] - sky_top[1]) * t)
            b = int(sky_top[2] + (sky_bot[2] - sky_top[2]) * t)
            d.line([(0, y), (width, y)], fill=(r, g, b, 255))
        floor_y = int(height * 0.68)
        rng = random.Random(42)

        def draw_mountain(cx: int, mh: int, mw: int, fill: tuple, snow_fill: tuple, snow_frac: float) -> None:
            for ox in [-width, 0, width]:
                mx = cx + ox
                pts = [mx - mw, floor_y, mx, floor_y - mh, mx + mw, floor_y]
                d.polygon(pts, fill=fill)
                snow_h = int(mh * snow_frac)
                if snow_h > 0 and mh > 0:
                    sp = [mx - mw * snow_h // mh, floor_y - mh + snow_h,
                          mx, floor_y - mh,
                          mx + mw * snow_h // mh, floor_y - mh + snow_h]
                    d.polygon(sp, fill=snow_fill)

        # Far mountains evenly spaced every 20%
        far_params = [(int(width * (0.10 + i * 0.20)),
                       int(height * (0.32 + rng.random() * 0.18)),
                       int(width * (0.12 + rng.random() * 0.08))) for i in range(5)]
        for mx, mh, mw in far_params:
            draw_mountain(mx, mh, mw, (155, 170, 195, 255), (240, 245, 255, 255), 0.30)

        # Near mountains evenly spaced every 33%
        near_params = [(int(width * (0.17 + i * 0.33)),
                        int(height * (0.28 + rng.random() * 0.14)),
                        int(width * (0.16 + rng.random() * 0.07))) for i in range(3)]
        for mx, mh, mw in near_params:
            draw_mountain(mx, mh, mw, (110, 130, 155, 255), (235, 242, 255, 255), 0.28)

        d.rectangle([0, floor_y, width, height], fill=(*gc, 255))

        # Snow bumps evenly distributed (8 per tile, tiled)
        bump_w = int(width * 0.14)
        for i in range(8):
            bx = int(width * (i / 8))
            for ox in [-width, 0, width]:
                d.ellipse([bx + ox, floor_y - 3, bx + ox + bump_w, floor_y + 6],
                          fill=(230, 238, 248, 200))

        # Pine trees every 25%, tiled
        th = int(height * 0.16)
        tw = int(th * 0.55)
        for xr in [0.10, 0.35, 0.60, 0.85]:
            for ox in [-width, 0, width]:
                tx = int(width * xr) + ox
                d.polygon([tx, floor_y - th, tx - tw, floor_y, tx + tw, floor_y],
                          fill=(55, 80, 70, 220))
        return img

    @staticmethod
    def _build_espacio(width: int, height: int,
                       ground_color: tuple[int, int, int] | None = None) -> Image.Image:
        import random
        gc = ground_color or (6, 4, 20)
        img = Image.new("RGBA", (width, height))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, width, height], fill=(*gc, 255))
        rng = random.Random(7)
        for _ in range(90):
            sx = rng.randint(0, width - 1)
            sy = rng.randint(0, height - 1)
            br = rng.randint(120, 255)
            col = rng.choice([(br, br, br), (br, br - 20, br + 20), (br + 10, br, br - 20)])
            d.point([sx, sy], fill=(*col, 255))
        # Planet at 30% tiled so it wraps seamlessly
        py_pos, pr = int(height * 0.28), int(height * 0.18)
        rw = int(pr * 1.7)
        for ox in [-width, 0, width]:
            px = int(width * 0.30) + ox
            d.ellipse([px - pr, py_pos - pr, px + pr, py_pos + pr], fill=(80, 60, 140, 220))
            d.ellipse([px - rw, py_pos - int(pr * 0.22), px + rw, py_pos + int(pr * 0.22)],
                      outline=(140, 110, 200, 160), width=2)
        return img

class DecorationRenderer:
    _NATURAL_H = 110
    _SIZES: dict[str, tuple[int, int]] = {
        "planta":      (44,  64),
        "alfombra":    (90,  26),
        "lampara":     (28,  76),
        "globos":      (110, 88),
        "cactus":      (36,  68),
        "computadora": (70,  58),
        "cofre":       (52,  44),
        "nave":        (100, 52),
        "acuario":     (72,  56),
        "sombrilla":   (60,  80),
        "tabla":       (22,  80),
        "fogata":      (48,  52),
        "carpa":       (80,  62),
    }

    def __init__(self) -> None:
        self._cache: dict[tuple, ImageTk.PhotoImage] = {}

    def get(self, key: str, canvas_height: int) -> ImageTk.PhotoImage | None:
        ck = (key, canvas_height)
        if ck not in self._cache:
            img = self._render(key, canvas_height)
            if img is None:
                return None
            self._cache[ck] = ImageTk.PhotoImage(img)
        return self._cache[ck]

    def size(self, key: str, canvas_height: int) -> tuple[int, int]:
        scale = canvas_height / self._NATURAL_H
        nw, nh = self._SIZES.get(key, (40, 40))
        return max(8, int(nw * scale)), max(8, int(nh * scale))

    def _render(self, key: str, canvas_height: int) -> Image.Image | None:
        scale = canvas_height / self._NATURAL_H
        nw, nh = self._SIZES.get(key, (40, 40))
        w, h = max(8, int(nw * scale)), max(8, int(nh * scale))
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        cx = w // 2

        if key == "planta":
            pot_h = int(h * 0.32)
            pot_w = int(w * 0.36)
            pot_y = h - pot_h
            d.rectangle([cx - pot_w, pot_y, cx + pot_w, h], fill=(140, 80, 50, 255))
            d.ellipse([cx - pot_w - 3, pot_y - 4, cx + pot_w + 3, pot_y + 4], fill=(110, 60, 40, 255))
            lw = max(1, int(2 * scale))
            d.line([cx, pot_y, cx, int(h * 0.40)], fill=(60, 110, 60, 255), width=lw)
            d.ellipse([cx - int(w * 0.40), int(h * 0.04), cx + int(w * 0.12), int(h * 0.44)],
                      fill=(70, 140, 70, 220))
            d.ellipse([cx - int(w * 0.06), 0, cx + int(w * 0.46), int(h * 0.40)],
                      fill=(60, 120, 60, 200))

        elif key == "alfombra":
            d.ellipse([0, 0, w, h], fill=(160, 60, 80, 200))
            d.ellipse([int(w * 0.09), int(h * 0.15), int(w * 0.91), int(h * 0.85)],
                      fill=(190, 90, 110, 200))

        elif key == "lampara":
            shade_h = int(h * 0.18)
            base_h = int(h * 0.08)
            lw = max(2, int(3 * scale))
            d.line([cx, shade_h + base_h, cx, h], fill=(80, 70, 60, 255), width=lw)
            d.rectangle([cx - int(w * 0.42), 0, cx + int(w * 0.42), shade_h],
                        fill=(230, 200, 120, 240))
            d.rectangle([cx - int(w * 0.26), shade_h, cx + int(w * 0.26), shade_h + base_h],
                        fill=(80, 70, 60, 255))

        elif key == "globos":
            import random
            rng = random.Random(99)
            colors_list = [(220, 60, 60), (60, 140, 220), (60, 200, 100),
                           (220, 180, 40), (180, 60, 200)]
            r = max(4, int(h * 0.18))
            for i in range(4):
                bx = int(w * (0.12 + i * 0.22))
                by = int(h * (0.06 + rng.random() * 0.28))
                col = colors_list[i % len(colors_list)]
                d.ellipse([bx - r, by - r, bx + r, by + r], fill=(*col, 220))
                d.line([bx, by + r, bx + rng.randint(-5, 5), h - 2],
                       fill=(80, 80, 80, 180), width=1)

        elif key == "cactus":
            trunk_x = cx
            trunk_w = max(3, int(w * 0.18))
            d.rectangle([trunk_x - trunk_w, int(h * 0.26), trunk_x + trunk_w, h],
                        fill=(60, 130, 60, 255))
            arm_y = int(h * 0.48)
            arm_w = max(2, int(w * 0.14))
            d.rectangle([int(w * 0.12), arm_y, trunk_x - trunk_w, arm_y + arm_w],
                        fill=(60, 130, 60, 255))
            d.rectangle([int(w * 0.12), int(h * 0.30), int(w * 0.12) + arm_w, arm_y + arm_w],
                        fill=(60, 130, 60, 255))
            d.rectangle([trunk_x + trunk_w, int(h * 0.38), int(w * 0.84), arm_y + arm_w],
                        fill=(60, 130, 60, 255))
            d.rectangle([int(w * 0.84) - arm_w, int(h * 0.22), int(w * 0.84), arm_y + arm_w],
                        fill=(60, 130, 60, 255))
            d.ellipse([trunk_x - trunk_w, int(h * 0.20),
                       trunk_x + trunk_w, int(h * 0.32)], fill=(70, 140, 70, 255))

        elif key == "computadora":
            scr_x1, scr_y1 = int(w * 0.08), int(h * 0.04)
            scr_x2, scr_y2 = int(w * 0.92), int(h * 0.62)
            d.rectangle([scr_x1, scr_y1, scr_x2, scr_y2], fill=(30, 35, 45, 255),
                        outline=(80, 90, 110, 255), width=max(1, int(2 * scale)))
            d.rectangle([scr_x1 + int(w * 0.04), scr_y1 + int(h * 0.04),
                         scr_x2 - int(w * 0.04), scr_y2 - int(h * 0.04)],
                        fill=(14, 22, 40, 255))
            for lx_off, col in [(int(w * 0.12), (80, 200, 120, 200)),
                                 (int(w * 0.30), (60, 150, 220, 180)),
                                 (int(w * 0.50), (200, 120, 60, 160))]:
                d.rectangle([scr_x1 + lx_off, scr_y1 + int(h * 0.14),
                              scr_x1 + lx_off + int(w * 0.14), scr_y1 + int(h * 0.20)],
                             fill=col)
            d.line([cx, scr_y2, cx, int(h * 0.72)], fill=(80, 90, 110, 255),
                   width=max(1, int(3 * scale)))
            d.rectangle([int(w * 0.20), int(h * 0.72), int(w * 0.80), h],
                        fill=(50, 55, 65, 255), outline=(80, 90, 110, 255),
                        width=max(1, int(2 * scale)))

        elif key == "cofre":
            lid_h = int(h * 0.38)
            d.rectangle([int(w * 0.06), lid_h, int(w * 0.94), h],
                        fill=(120, 75, 30, 255), outline=(80, 50, 15, 255),
                        width=max(1, int(2 * scale)))
            d.rectangle([int(w * 0.06), int(h * 0.06), int(w * 0.94), lid_h],
                        fill=(100, 60, 20, 255), outline=(80, 50, 15, 255),
                        width=max(1, int(2 * scale)))
            d.rectangle([int(w * 0.06), lid_h - max(1, int(2 * scale)),
                         int(w * 0.94), lid_h + max(1, int(2 * scale))],
                        fill=(180, 140, 50, 255))
            for bx in [int(w * 0.22), int(w * 0.50), int(w * 0.78)]:
                d.rectangle([bx - int(w * 0.06), int(h * 0.10),
                              bx + int(w * 0.06), int(h * 0.90)],
                             fill=(180, 140, 50, 200))
            lock_x, lock_y = cx, lid_h
            lr = max(3, int(w * 0.08))
            d.ellipse([lock_x - lr, lock_y - lr, lock_x + lr, lock_y + lr],
                      fill=(200, 170, 60, 255), outline=(140, 110, 30, 255))

        elif key == "nave":
            body_y = int(h * 0.28)
            body_h = int(h * 0.44)
            body_w = int(w * 0.38)
            d.ellipse([cx - body_w, body_y, cx + body_w, body_y + body_h],
                      fill=(200, 210, 230, 235), outline=(150, 160, 185, 255),
                      width=max(1, int(2 * scale)))
            dome_r = int(w * 0.22)
            dome_y = body_y - int(h * 0.10)
            d.ellipse([cx - dome_r, dome_y, cx + dome_r, body_y + int(h * 0.08)],
                      fill=(100, 180, 240, 200), outline=(80, 160, 220, 220),
                      width=max(1, int(2 * scale)))
            wing_pts_l = [(cx - body_w, body_y + int(body_h * 0.6)),
                          (int(w * 0.02), body_y + body_h),
                          (cx - int(body_w * 0.4), body_y + body_h)]
            d.polygon(wing_pts_l, fill=(170, 180, 210, 220))
            wing_pts_r = [(cx + body_w, body_y + int(body_h * 0.6)),
                          (int(w * 0.98), body_y + body_h),
                          (cx + int(body_w * 0.4), body_y + body_h)]
            d.polygon(wing_pts_r, fill=(170, 180, 210, 220))
            flame_y = body_y + body_h - max(1, int(h * 0.04))
            for fx, col in [(cx - int(body_w * 0.3), (255, 160, 40, 220)),
                            (cx, (255, 220, 60, 230)),
                            (cx + int(body_w * 0.3), (255, 160, 40, 220))]:
                fr = max(2, int(w * 0.05))
                d.ellipse([fx - fr, flame_y, fx + fr, flame_y + int(h * 0.20)],
                          fill=col)

        elif key == "pizza":
            import math as _math
            r_out = min(w, h) // 2 - 2
            d.ellipse([cx - r_out, int(h * 0.04), cx + r_out, int(h * 0.96)],
                      fill=(220, 170, 60, 255))
            d.ellipse([cx - int(r_out * 0.82), int(h * 0.14),
                       cx + int(r_out * 0.82), int(h * 0.86)],
                      fill=(210, 80, 40, 240))
            for ang in range(0, 360, 72):
                tx = cx + int(r_out * 0.45 * _math.cos(_math.radians(ang)))
                ty = h // 2 + int(r_out * 0.38 * _math.sin(_math.radians(ang)))
                tr = max(3, int(r_out * 0.14))
                d.ellipse([tx - tr, ty - tr, tx + tr, ty + tr], fill=(230, 230, 230, 240))
            for ang in range(36, 360, 72):
                gx = cx + int(r_out * 0.52 * _math.cos(_math.radians(ang)))
                gy = h // 2 + int(r_out * 0.44 * _math.sin(_math.radians(ang)))
                gr = max(2, int(r_out * 0.09))
                d.ellipse([gx - gr, gy - gr, gx + gr, gy + gr], fill=(60, 140, 60, 230))
            for i in range(6):
                ang = i * 60
                d.line([cx, h // 2,
                        cx + int(r_out * _math.cos(_math.radians(ang))),
                        h // 2 + int(r_out * _math.sin(_math.radians(ang)))],
                       fill=(180, 130, 40, 180), width=max(1, int(scale)))

        elif key == "acuario":
            glass_x1, glass_y1 = int(w * 0.04), int(h * 0.06)
            glass_x2, glass_y2 = int(w * 0.96), int(h * 0.88)
            d.rectangle([glass_x1, glass_y1, glass_x2, glass_y2],
                        fill=(40, 100, 160, 80), outline=(100, 160, 220, 200),
                        width=max(2, int(3 * scale)))
            water_y = glass_y1 + int((glass_y2 - glass_y1) * 0.18)
            d.rectangle([glass_x1 + max(2, int(3 * scale)), water_y,
                         glass_x2 - max(2, int(3 * scale)), glass_y2 - max(2, int(3 * scale))],
                        fill=(30, 80, 140, 120))
            sand_y = glass_y2 - int((glass_y2 - glass_y1) * 0.18)
            d.rectangle([glass_x1 + max(2, int(3 * scale)), sand_y,
                         glass_x2 - max(2, int(3 * scale)), glass_y2 - max(2, int(3 * scale))],
                        fill=(180, 150, 80, 200))
            import math as _math
            for fx, fy, fc in [(int(w * 0.28), int((water_y + sand_y) * 0.5),
                                 (255, 140, 40)),
                                (int(w * 0.68), int((water_y + sand_y) * 0.42),
                                 (80, 180, 220))]:
                fr = max(3, int(w * 0.10))
                d.ellipse([fx - fr, fy - int(fr * 0.6), fx + fr, fy + int(fr * 0.6)],
                          fill=(*fc, 220))
                d.polygon([fx + fr, fy, fx + int(fr * 1.6), fy - int(fr * 0.5),
                            fx + int(fr * 1.6), fy + int(fr * 0.5)], fill=(*fc, 200))
            for px in range(glass_x1 + int(w * 0.08), glass_x2, int(w * 0.14)):
                ph = int((glass_y2 - sand_y) * (0.4 + (px % 3) * 0.15))
                d.rectangle([px - max(1, int(w * 0.03)), sand_y - ph,
                              px + max(1, int(w * 0.03)), sand_y],
                             fill=(60, 140, 80, 200))
            d.rectangle([glass_x1, glass_y1 - int(h * 0.08),
                         glass_x2, glass_y1],
                        fill=(60, 70, 80, 240))
        elif key == "sombrilla":
            pole_x = cx + int(w * 0.06)
            lw = max(2, int(2 * scale))
            d.line([pole_x, int(h * 0.20), pole_x, h], fill=(180, 140, 80, 255), width=lw)
            # Canopy as wedge slices alternating colors
            cr = int(w * 0.46)
            canopy_y = int(h * 0.20)
            cols = [(220, 60, 60), (240, 240, 60), (60, 140, 220), (60, 200, 100)]
            import math as _math
            for i in range(8):
                a1 = _math.radians(180 + i * 22.5)
                a2 = _math.radians(180 + (i + 1) * 22.5)
                col = cols[i % len(cols)]
                d.polygon([
                    pole_x, canopy_y,
                    pole_x + int(cr * _math.cos(a1)), canopy_y + int(cr * 0.38 * _math.sin(a1)),
                    pole_x + int(cr * _math.cos(a2)), canopy_y + int(cr * 0.38 * _math.sin(a2)),
                ], fill=(*col, 230))
            d.ellipse([pole_x - cr, canopy_y - int(cr * 0.08),
                       pole_x + cr, canopy_y + int(cr * 0.08)],
                      outline=(60, 40, 20, 180), width=lw)

        elif key == "tabla":
            lw = max(2, int(2 * scale))
            bw = int(w * 0.38)
            d.rounded_rectangle([cx - bw, int(h * 0.04), cx + bw, int(h * 0.92)],
                                 radius=int(w * 0.36), fill=(220, 90, 40, 240))
            d.rounded_rectangle([cx - int(bw * 0.6), int(h * 0.08),
                                  cx + int(bw * 0.6), int(h * 0.88)],
                                 radius=int(w * 0.28), fill=(240, 130, 60, 200))
            d.ellipse([cx - int(bw * 0.22), int(h * 0.44),
                       cx + int(bw * 0.22), int(h * 0.56)], fill=(255, 200, 50, 230))

        elif key == "fogata":
            # Log base
            lw = max(2, int(2 * scale))
            log_y = int(h * 0.72)
            d.ellipse([int(w * 0.08), log_y, cx - int(w * 0.06), log_y + int(h * 0.16)],
                      fill=(100, 65, 30, 255))
            d.ellipse([cx + int(w * 0.06), log_y, int(w * 0.92), log_y + int(h * 0.16)],
                      fill=(100, 65, 30, 255))
            d.ellipse([cx - int(w * 0.18), log_y + int(h * 0.06),
                       cx + int(w * 0.18), log_y + int(h * 0.22)],
                      fill=(80, 50, 20, 255))
            # Flames
            import math as _math
            for fx, fw, fh, fc in [
                (cx - int(w * 0.10), int(w * 0.18), int(h * 0.56), (220, 80,  20, 220)),
                (cx + int(w * 0.08), int(w * 0.14), int(h * 0.46), (240, 140, 30, 210)),
                (cx - int(w * 0.02), int(w * 0.12), int(h * 0.62), (255, 200, 50, 200)),
            ]:
                d.polygon([
                    fx - fw, log_y,
                    fx, log_y - fh,
                    fx + fw, log_y,
                ], fill=fc)
            # Embers
            for ex, ey in [(cx - int(w*0.08), log_y - int(h*0.12)),
                           (cx + int(w*0.12), log_y - int(h*0.08))]:
                r = max(1, int(w * 0.04))
                d.ellipse([ex - r, ey - r, ex + r, ey + r], fill=(255, 160, 40, 200))

        elif key == "carpa":
            ground_y = int(h * 0.80)
            # Main tent body
            d.polygon([int(w * 0.04), ground_y,
                       cx, int(h * 0.08),
                       int(w * 0.96), ground_y],
                      fill=(60, 120, 80, 235))
            # Door flap (darker triangle)
            d.polygon([cx - int(w * 0.14), ground_y,
                       cx, int(h * 0.44),
                       cx + int(w * 0.14), ground_y],
                      fill=(40, 90, 60, 240))
            # Door opening
            d.polygon([cx - int(w * 0.08), ground_y,
                       cx, int(h * 0.52),
                       cx + int(w * 0.08), ground_y],
                      fill=(25, 20, 15, 220))
            # Tent lines
            lw = max(1, int(scale))
            d.line([cx, int(h * 0.08), int(w * 0.04), ground_y],
                   fill=(40, 100, 60, 180), width=lw)
            d.line([cx, int(h * 0.08), int(w * 0.96), ground_y],
                   fill=(40, 100, 60, 180), width=lw)
            # Pegs
            for px in [int(w * 0.04), int(w * 0.96)]:
                d.line([px, ground_y, px - int(w * 0.04 * (1 if px < cx else -1)),
                        ground_y + int(h * 0.10)], fill=(180, 140, 80, 200), width=lw)

        else:
            return None

        return img


class FloatingItemRenderer:
    _BASE = 22

    def __init__(self) -> None:
        self._cache: dict[tuple, ImageTk.PhotoImage] = {}

    def get(self, key: str, sprite_scale: float) -> ImageTk.PhotoImage | None:
        if key == "ninguno":
            return None
        size = max(12, int(self._BASE * sprite_scale))
        ck = (key, size)
        if ck not in self._cache:
            img = self._render(key, size)
            if img is None:
                return None
            self._cache[ck] = ImageTk.PhotoImage(img)
        return self._cache[ck]

    @staticmethod
    def _render(key: str, size: int) -> Image.Image | None:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        cx, cy = size // 2, size // 2

        if key == "corona":
            bw = int(size * 0.42)
            bh = max(3, size // 4)
            by = cy + size // 8
            d.rectangle([cx - bw, by, cx + bw, by + bh], fill=(210, 170, 15, 240))
            for px in [cx - bw, cx, cx + bw]:
                ph = max(3, size // 4)
                pw = max(2, size // 7)
                d.polygon([px - pw, by, px, by - ph, px + pw, by], fill=(210, 170, 15, 240))
            for px in [cx - bw // 2, cx, cx + bw // 2]:
                r = max(1, size // 9)
                d.ellipse([px - r, by + r, px + r, by + r * 3], fill=(220, 70, 70, 230))

        elif key == "estrella":
            r_out = size * 0.46
            r_in = r_out * 0.42
            pts: list[float] = []
            for i in range(10):
                angle = math.pi / 2 + i * math.pi / 5
                r = r_out if i % 2 == 0 else r_in
                pts.append(cx + r * math.cos(angle))
                pts.append(cy - r * math.sin(angle))
            d.polygon(pts, fill=(255, 220, 40, 245), outline=(200, 155, 10, 200))

        elif key == "halo":
            rx, ry = int(size * 0.44), int(size * 0.20)
            lw = max(2, size // 7)
            d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry],
                      outline=(230, 200, 60, 245), width=lw)

        elif key == "rayo":
            w2 = size // 5
            pts = [
                cx + w2, 1,
                cx - w2 // 2, cy,
                cx + w2 // 2, cy,
                cx - w2, size - 1,
                cx + w2, cy + w2,
                cx, cy + w2,
            ]
            d.polygon(pts, fill=(255, 225, 30, 245), outline=(200, 150, 0, 180))

        elif key == "corazon":
            r = max(3, size // 4)
            d.ellipse([cx - r * 2 + 1, cy - r, cx, cy + r], fill=(220, 45, 75, 245))
            d.ellipse([cx, cy - r, cx + r * 2 - 1, cy + r], fill=(220, 45, 75, 245))
            d.polygon([cx - r * 2 + 1, cy, cx + r * 2 - 1, cy, cx, cy + r * 2],
                      fill=(220, 45, 75, 245))

        elif key == "nota":
            lw = max(2, size // 7)
            nr = max(3, size // 5)
            ny = cy + nr
            d.ellipse([cx - nr, ny, cx + nr, ny + nr * 2], fill=(30, 30, 30, 245))
            d.line([cx + nr - lw // 2, ny + nr,
                    cx + nr - lw // 2, cy - size // 3],
                   fill=(30, 30, 30, 245), width=lw)
            d.line([cx + nr - lw // 2, cy - size // 3,
                    cx + nr + size // 5, cy - size // 6],
                   fill=(30, 30, 30, 245), width=lw)

        elif key == "zzz":
            for i, (ox, oy_off, s_frac) in enumerate([
                (-size // 5, size // 5,  0.40),
                (0,          size // 10, 0.60),
                (size // 6,  0,          0.80),
            ]):
                zs = max(2, int(size * s_frac * 0.22))
                zx, zy = cx + ox, cy + oy_off
                col = (100, 150, 255, 200)
                lw = max(1, zs // 3)
                d.line([zx - zs, zy - zs, zx + zs, zy - zs], fill=col, width=lw)
                d.line([zx - zs, zy - zs, zx + zs, zy + zs], fill=col, width=lw)
                d.line([zx - zs, zy + zs, zx + zs, zy + zs], fill=col, width=lw)

        elif key == "fuego":
            for fx, fw, fh, fc in [
                (cx - size//6, size//4, int(size*0.9), (220, 70,  10, 215)),
                (cx + size//7, size//5, int(size*0.7), (240, 130, 20, 205)),
                (cx,           size//5, int(size*1.0), (255, 190, 40, 200)),
            ]:
                base = size - 2
                d.polygon([fx - fw, base, fx, base - fh, fx + fw, base], fill=fc)

        elif key == "calavera":
            r = size // 3
            # Cranium
            d.ellipse([cx - r, cy - r, cx + r, cy + int(r*0.6)], fill=(230, 225, 220, 240))
            # Jaw
            d.rectangle([cx - int(r*0.7), cy, cx + int(r*0.7), cy + int(r*0.7)],
                         fill=(220, 215, 210, 240))
            # Eyes
            er = max(2, r//3)
            d.ellipse([cx - int(r*0.5) - er, cy - int(r*0.3) - er,
                       cx - int(r*0.5) + er, cy - int(r*0.3) + er], fill=(30, 25, 25, 255))
            d.ellipse([cx + int(r*0.5) - er, cy - int(r*0.3) - er,
                       cx + int(r*0.5) + er, cy - int(r*0.3) + er], fill=(30, 25, 25, 255))
            # Teeth
            tw = max(2, r//4)
            for i in range(3):
                tx = cx - int(r*0.45) + i * int(r*0.45)
                d.rectangle([tx, cy + int(r*0.05), tx + tw, cy + int(r*0.55)],
                             fill=(30, 25, 25, 240))

        elif key == "arcoiris":
            cols = [(220,50,50),(240,140,30),(240,220,30),(60,190,60),(50,130,220),(130,60,210)]
            for i, col in enumerate(cols):
                r_out = int(size * (0.46 - i * 0.055))
                r_in  = r_out - max(2, size // 12)
                if r_in < 1:
                    break
                d.arc([cx - r_out, cy - r_out, cx + r_out, cy + r_out],
                      start=180, end=0, fill=(*col, 230), width=max(1, r_out - r_in))

        elif key == "explosion":
            spikes = 8
            r_out = size * 0.46
            r_in  = r_out * 0.55
            pts: list[float] = []
            for i in range(spikes * 2):
                angle = math.pi / 2 + i * math.pi / spikes
                r = r_out if i % 2 == 0 else r_in
                pts.append(cx + r * math.cos(angle))
                pts.append(cy - r * math.sin(angle))
            d.polygon(pts, fill=(255, 200, 30, 245), outline=(220, 100, 10, 200))
            d.ellipse([cx - int(size*0.22), cy - int(size*0.22),
                       cx + int(size*0.22), cy + int(size*0.22)],
                      fill=(255, 240, 120, 240))

        elif key == "diamante":
            hw = int(size * 0.40)
            top_h = int(size * 0.30)
            bot_h = int(size * 0.46)
            mid_y = cy - int(size * 0.10)
            # Top facets
            d.polygon([cx, mid_y - top_h, cx - hw, mid_y, cx, mid_y], fill=(100, 200, 255, 240))
            d.polygon([cx, mid_y - top_h, cx + hw, mid_y, cx, mid_y], fill=(60, 160, 240, 240))
            d.polygon([cx - hw, mid_y - top_h//2, cx, mid_y - top_h,
                       cx - hw, mid_y], fill=(140, 220, 255, 230))
            # Bottom facets
            d.polygon([cx - hw, mid_y, cx, mid_y + bot_h, cx, mid_y], fill=(50, 140, 220, 240))
            d.polygon([cx + hw, mid_y, cx, mid_y + bot_h, cx, mid_y], fill=(80, 170, 245, 240))

        elif key == "luna":
            r = int(size * 0.40)
            # Full circle
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(250, 230, 80, 240))
            # Bite out
            offset = int(r * 0.42)
            d.ellipse([cx - r + offset, cy - r, cx + r + offset, cy + r],
                      fill=(0, 0, 0, 0))

        else:
            return None

        return img


class EventTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True


class EventHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        chunks: list[bytes] = []
        while True:
            data = self.request.recv(4096)
            if not data:
                break
            chunks.append(data)

        if not chunks:
            return

        try:
            payload = json.loads(b"".join(chunks).decode("utf-8"))
        except json.JSONDecodeError:
            return

        self.server.app.store.process(payload)


class BreakOverlayWindow:
    def __init__(self, root: tk.Tk, duration_seconds: int,
                 on_complete: Any, on_cancel: Any) -> None:
        monitors = _get_all_monitors()
        mx, my, mw, mh = monitors[0]

        self._win = tk.Toplevel(root)
        self._win.attributes("-topmost", True)
        self._win.overrideredirect(True)
        self._win.geometry(f"{mw}x{mh}+{mx}+{my}")
        self._win.configure(bg="#060b14")
        self._remaining = duration_seconds
        self._total = duration_seconds
        self._on_complete = on_complete
        self._on_cancel = on_cancel
        self._finished = False
        self._after_id: str | None = None
        self._canvas = tk.Canvas(self._win, bg="#060b14", highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)

        self._secondary_wins: list[tk.Toplevel] = []
        for sx, sy, sw, sh in monitors[1:]:
            sec = tk.Toplevel(root)
            sec.attributes("-topmost", True)
            sec.overrideredirect(True)
            sec.geometry(f"{sw}x{sh}+{sx}+{sy}")
            sec.configure(bg="#060b14")
            sc = tk.Canvas(sec, bg="#060b14", highlightthickness=0)
            sc.pack(fill="both", expand=True)
            sec.update_idletasks()
            sc.create_text(sw // 2, sh // 2,
                           text="Tiempo de descanso",
                           fill="#334155", font=("Microsoft YaHei UI", 24),
                           anchor="center")
            self._secondary_wins.append(sec)

        self._win.update_idletasks()
        self._draw()
        self._after_id = self._win.after(1000, self._tick)

    def _format_time(self, secs: int) -> str:
        m, s = divmod(max(0, secs), 60)
        return f"{m:02d}:{s:02d}"

    def _draw(self) -> None:
        c = self._canvas
        c.delete("all")
        w = c.winfo_width() or c.winfo_screenwidth()
        h = c.winfo_height() or c.winfo_screenheight()
        c.create_rectangle(0, 0, w, h, fill="#060b14", outline="")

        if not self._finished:
            c.create_text(w // 2, h // 2 - 90,
                          text="Tiempo de descanso",
                          fill="#94a3b8", font=("Microsoft YaHei UI", 24),
                          anchor="center")
            c.create_text(w // 2, h // 2,
                          text=self._format_time(self._remaining),
                          fill="#f8fafc", font=("Microsoft YaHei UI", 72, "bold"),
                          anchor="center")
            bw, bh = 300, 46
            bx1 = w // 2 - bw // 2
            bx2 = w // 2 + bw // 2
            by1 = h // 2 + 90
            by2 = by1 + bh
            c.create_rectangle(bx1, by1, bx2, by2,
                                fill="#1e293b", outline="#334155", width=1,
                                tags="cancel_area")
            c.create_text(w // 2, (by1 + by2) // 2,
                          text="Cancelar descanso (emergencia)",
                          fill="#94a3b8", font=("Microsoft YaHei UI", 11),
                          tags="cancel_area", anchor="center")
            c.tag_bind("cancel_area", "<Button-1>", lambda _e: self._cancel())
        else:
            c.create_text(w // 2, h // 2 - 60,
                          text="¡Descansaste!",
                          fill="#34d399", font=("Microsoft YaHei UI", 40, "bold"),
                          anchor="center")
            c.create_text(w // 2, h // 2 + 10,
                          text="Es hora de volver al trabajo.",
                          fill="#94a3b8", font=("Microsoft YaHei UI", 18),
                          anchor="center")
            bw, bh = 180, 50
            bx1 = w // 2 - bw // 2
            bx2 = w // 2 + bw // 2
            by1 = h // 2 + 80
            by2 = by1 + bh
            c.create_rectangle(bx1, by1, bx2, by2,
                                fill="#064e3b", outline="#34d399", width=2,
                                tags="accept_area")
            c.create_text(w // 2, (by1 + by2) // 2,
                          text="Aceptar",
                          fill="#6ee7b7", font=("Microsoft YaHei UI", 14, "bold"),
                          tags="accept_area", anchor="center")
            c.tag_bind("accept_area", "<Button-1>", lambda _e: self._accept_done())

    def _tick(self) -> None:
        if self._finished:
            return
        if self._remaining > 0:
            self._remaining -= 1
            self._draw()
            self._after_id = self._win.after(1000, self._tick)
        else:
            self._time_up()

    def _time_up(self) -> None:
        self._finished = True
        self._draw()
        threading.Thread(target=self._play_alarm, daemon=True).start()

    @staticmethod
    def _play_alarm() -> None:
        try:
            for _ in range(3):
                winsound.Beep(880, 350)
                time.sleep(0.15)
            winsound.Beep(1047, 700)
        except Exception:
            pass

    def _destroy_secondary(self) -> None:
        for sw in self._secondary_wins:
            try:
                sw.destroy()
            except Exception:
                pass
        self._secondary_wins.clear()

    def _cancel(self) -> None:
        if self._after_id:
            self._win.after_cancel(self._after_id)
            self._after_id = None
        self._destroy_secondary()
        try:
            self._win.destroy()
        except Exception:
            pass
        self._on_cancel()

    def _accept_done(self) -> None:
        self._destroy_secondary()
        try:
            self._win.destroy()
        except Exception:
            pass
        self._on_complete()

    def destroy(self) -> None:
        if self._after_id:
            try:
                self._win.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self._destroy_secondary()
        try:
            self._win.destroy()
        except Exception:
            pass


class AlarmOverlayWindow:
    def __init__(self, root: tk.Tk, alarm: dict, on_dismiss: Any, on_snooze: Any) -> None:
        self._alarm = alarm
        self._on_dismiss = on_dismiss
        self._on_snooze = on_snooze

        self._win = tk.Toplevel(root)
        self._win.attributes("-topmost", True)
        self._win.overrideredirect(True)
        self._win.configure(bg="#1c1508")

        root.update_idletasks()
        rx = root.winfo_x()
        ry = root.winfo_y()
        rh = root.winfo_height()
        self._win.geometry(f"400x140+{rx}+{ry + rh + 4}")

        self._build()
        threading.Thread(target=self._play_alarm_sound, daemon=True).start()

    def _build(self) -> None:
        border = tk.Frame(self._win, bg="#d97706", padx=2, pady=2)
        border.pack(fill="both", expand=True)
        inner = tk.Frame(border, bg="#1c1508")
        inner.pack(fill="both", expand=True)

        hdr = tk.Frame(inner, bg="#1c1508")
        hdr.pack(fill="x", padx=10, pady=(10, 2))
        tk.Label(hdr, text="🔔 ¡Recordatorio!", fg="#fbbf24", bg="#1c1508",
                 font=("Microsoft YaHei UI", 11, "bold")).pack(side="left")
        tk.Label(hdr, text=self._alarm.get("time", ""), fg="#fcd34d", bg="#1c1508",
                 font=("Microsoft YaHei UI", 11, "bold")).pack(side="right")

        tk.Label(inner, text=self._alarm.get("label", "Recordatorio"),
                 fg="#f8fafc", bg="#1c1508",
                 font=("Microsoft YaHei UI", 13, "bold"),
                 wraplength=360).pack(padx=10, pady=(4, 8))

        btn_row = tk.Frame(inner, bg="#1c1508")
        btn_row.pack(pady=(0, 10))
        tk.Button(btn_row, text="OK", command=self._dismiss,
                  bg="#92400e", fg="#fef3c7",
                  activebackground="#b45309", activeforeground="#fef3c7",
                  relief="flat", padx=18, pady=5,
                  font=("Microsoft YaHei UI", 9, "bold")).pack(side="left", padx=(0, 8))
        tk.Button(btn_row, text="Posponer 10 min", command=self._snooze,
                  bg="#1c1508", fg="#a3a3a3",
                  activebackground="#292015", activeforeground="#d4d4d4",
                  relief="flat", padx=10, pady=5,
                  font=("Microsoft YaHei UI", 9),
                  highlightbackground="#44403c", highlightthickness=1).pack(side="left")

    @staticmethod
    def _play_alarm_sound() -> None:
        try:
            for base in [600, 700, 800]:
                winsound.Beep(base, 180)
                time.sleep(0.05)
                winsound.Beep(base + 150, 280)
                time.sleep(0.18)
        except Exception:
            pass

    def _dismiss(self) -> None:
        try:
            self._win.destroy()
        except Exception:
            pass
        self._on_dismiss()

    def _snooze(self) -> None:
        try:
            self._win.destroy()
        except Exception:
            pass
        self._on_snooze()

    def destroy(self) -> None:
        try:
            self._win.destroy()
        except Exception:
            pass


class MiniGame:
    GRAVITY = 0.75
    JUMP_VEL = -11.5
    TICK_MS = 30
    CHAR_X = 90
    BASE_SPEED = 4.5
    MAX_SPEED = 14.0
    SPEED_ACCEL = 0.005
    FRAMES_PER_TICK = 4

    _SOUNDS_DIR = Path(__file__).parent / "sounds"

    def __init__(
        self,
        root: tk.Tk,
        char: dict,
        house: dict,
        sprite_renderer: SpriteRenderer,
        bg_renderer: BackgroundRenderer,
        data_store: DataStore,
        on_done: Any,
    ) -> None:
        self._char = char
        self._house = house
        self._sprite_renderer = sprite_renderer
        self._bg_renderer = bg_renderer
        self._data_store = data_store
        self._on_done = on_done

        self._W, self._H = 600, 200
        self._ground_y = int(self._H * 0.78)

        self._running = False
        self._game_over = False
        self._speed = self.BASE_SPEED
        self._score_px = 0.0
        self._ticks = 0
        self._char_y = float(self._ground_y)
        self._char_vy = 0.0
        self._on_ground = True
        self._obstacles: list[dict] = []
        self._next_obs_in = 45
        self._sprite_frame = 0
        self._frame_timer = 0
        self._bg_offset = 0.0
        self._after_id: str | None = None
        self._img_refs: list = []
        self._snd_jump: Any = None
        self._snd_crash: Any = None
        self._music_ready = False
        self._init_audio()

        self._sprite_set = char.get("sprite_set", "Dino")
        self._game_scale = SPRITE_SET_SCALE_DEFAULTS.get(self._sprite_set, 1.0) * 0.85

        self._win = tk.Toplevel(root)
        self._win.title(f"¡Corre, {char.get('name', 'Mascota')}!")
        self._win.configure(bg="#0f172a")
        self._win.resizable(False, False)
        root.attributes("-topmost", False)
        self._win.attributes("-topmost", True)
        self._win.lift()
        x = root.winfo_x() + (root.winfo_width() - self._W) // 2
        y = root.winfo_y() + root.winfo_height() + 8
        self._win.geometry(f"{self._W}x{self._H}+{x}+{max(0, y)}")

        self._canvas = tk.Canvas(self._win, width=self._W, height=self._H,
                                  bg="#0f172a", highlightthickness=0)
        self._canvas.pack()

        self._win.bind("<space>", self._on_input)
        self._win.bind("<Return>", self._on_input)
        self._win.bind("<Destroy>", lambda e: self._cleanup() if e.widget is self._win else None)
        self._win.focus_set()
        self._draw_start_screen()

    def _draw_start_screen(self) -> None:
        self._img_refs.clear()
        c = self._canvas
        c.delete("all")
        self._draw_bg(0)
        self._draw_character(self._ground_y, frame=0)
        c.create_line(0, self._ground_y, self._W, self._ground_y, fill="#475569", width=2)
        c.create_text(self._W // 2, self._H // 2 - 16,
                      text="Presioná  ESPACIO  para empezar",
                      fill="#f8fafc", font=("Microsoft YaHei UI", 12, "bold"), anchor="center")

    def _init_audio(self) -> None:
        if not _PYGAME_OK:
            return
        try:
            f_music = self._SOUNDS_DIR / "game_music.wav"
            if f_music.exists():
                _pygame.mixer.music.load(str(f_music))
                self._music_ready = True
            f_jump = self._SOUNDS_DIR / "jump.wav"
            if f_jump.exists():
                self._snd_jump = _pygame.mixer.Sound(str(f_jump))
            f_crash = self._SOUNDS_DIR / "game_over.wav"
            if f_crash.exists():
                self._snd_crash = _pygame.mixer.Sound(str(f_crash))
        except Exception:
            pass

    def _start_music(self) -> None:
        if self._music_ready:
            try:
                _pygame.mixer.music.play(-1)
            except Exception:
                pass

    def _stop_music(self) -> None:
        try:
            _pygame.mixer.music.stop()
        except Exception:
            pass

    def _play_crash(self) -> None:
        if self._snd_crash:
            try:
                self._snd_crash.play()
            except Exception:
                pass

    def _play_jump(self) -> None:
        if self._snd_jump:
            try:
                self._snd_jump.play()
            except Exception:
                pass

    def _on_input(self, _: Any = None) -> None:
        if self._game_over:
            return
        if not self._running:
            self._running = True
            self._start_music()
            self._tick()
            return
        if self._on_ground:
            self._char_vy = self.JUMP_VEL
            self._on_ground = False
            self._play_jump()

    def _tick(self) -> None:
        if self._game_over or not self._running:
            return
        self._ticks += 1
        self._speed = min(self.MAX_SPEED, self.BASE_SPEED + self._ticks * self.SPEED_ACCEL)

        # Physics
        self._char_vy += self.GRAVITY
        self._char_y += self._char_vy
        if self._char_y >= self._ground_y:
            self._char_y = float(self._ground_y)
            self._char_vy = 0.0
            self._on_ground = True

        # Scroll & score
        self._score_px += self._speed
        self._bg_offset += self._speed

        # Spawn obstacle
        self._next_obs_in -= 1
        if self._next_obs_in <= 0:
            h = random.randint(22, 50)
            w = random.randint(14, 22)
            self._obstacles.append({"x": float(self._W + 10), "h": h, "w": w})
            gap = max(22, int(72 - self._speed * 3.2))
            self._next_obs_in = gap + random.randint(-4, 10)

        for obs in self._obstacles:
            obs["x"] -= self._speed
        self._obstacles = [o for o in self._obstacles if o["x"] + o["w"] > 0]

        # Sprite animation
        self._frame_timer += 1
        if self._frame_timer >= self.FRAMES_PER_TICK:
            self._frame_timer = 0
            fc = self._sprite_renderer._frame_count_for(self._sprite_set, "working", "neutral")
            self._sprite_frame = (self._sprite_frame + 1) % fc

        if self._check_collision():
            self._end_game()
            return

        self._render_frame()
        self._after_id = self._win.after(self.TICK_MS, self._tick)

    def _check_collision(self) -> bool:
        try:
            spr = self._sprite_renderer.get_frame(
                "working", "neutral", self._sprite_frame,
                scale=self._game_scale, sprite_set=self._sprite_set)
            sw, sh = spr.width(), spr.height()
        except Exception:
            sw, sh = 28, 40
        mg = 10
        cl = self.CHAR_X - sw // 2 + mg
        cr = self.CHAR_X + sw // 2 - mg
        ct = self._char_y - sh + mg
        cb = self._char_y - mg
        for obs in self._obstacles:
            ol, or_ = obs["x"], obs["x"] + obs["w"]
            ot, ob = self._ground_y - obs["h"], float(self._ground_y)
            if cl < or_ and cr > ol and ct < ob and cb > ot:
                return True
        return False

    def _render_frame(self) -> None:
        self._img_refs.clear()
        c = self._canvas
        c.delete("all")
        self._draw_bg(int(self._bg_offset))
        c.create_line(0, self._ground_y, self._W, self._ground_y, fill="#475569", width=2)
        theme = self._house.get("background", "oficina")
        for obs in self._obstacles:
            self._draw_obstacle(c, int(obs["x"]), obs["h"], obs["w"], theme)
        self._draw_character(self._char_y, self._sprite_frame)
        meters = int(self._score_px / 30)
        c.create_text(self._W - 10, 10, text=f"{meters} m",
                      fill="#fbbf24", font=("Microsoft YaHei UI", 10, "bold"), anchor="ne")

    def _draw_obstacle(self, c: tk.Canvas, x: int, h: int, w: int, theme: str) -> None:
        gy = self._ground_y
        if theme == "oficina":
            # Caja de cartón
            c.create_rectangle(x, gy - h, x + w, gy,
                                fill="#b45309", outline="#92400e", width=1)
            c.create_line(x, gy - h, x + w, gy, fill="#92400e", width=1)
            c.create_line(x + w, gy - h, x, gy, fill="#92400e", width=1)
            c.create_line(x, gy - h // 2, x + w, gy - h // 2, fill="#92400e", width=1)
        elif theme == "bosque":
            # Tronco de árbol
            c.create_rectangle(x, gy - h, x + w, gy,
                                fill="#78350f", outline="#57220a", width=1)
            ring_step = max(6, h // 4)
            for ry in range(gy - h + ring_step, gy, ring_step):
                c.create_line(x + 2, ry, x + w - 2, ry, fill="#57220a", width=1)
        elif theme == "montanas":
            # Piedra
            cx_ = x + w // 2
            pts = [x, gy, x + w // 4, gy - h, cx_, gy - int(h * 1.1),
                   x + int(w * 0.78), gy - int(h * 0.85), x + w, gy]
            c.create_polygon(pts, fill="#6b7280", outline="#4b5563", width=1)
            c.create_oval(x + w // 4, gy - int(h * 0.6),
                          x + int(w * 0.6), gy - int(h * 0.3),
                          fill="#9ca3af", outline="")
        elif theme == "noche":
            # Luz/farol
            pole_w = max(3, w // 4)
            cx_ = x + w // 2
            c.create_rectangle(cx_ - pole_w // 2, gy - h, cx_ + pole_w // 2, gy,
                                fill="#374151", outline="#1f2937", width=1)
            lamp_h = max(8, h // 3)
            c.create_rectangle(x, gy - h, x + w, gy - h + lamp_h,
                                fill="#fef08a", outline="#fde047", width=1)
            c.create_oval(x + 2, gy - h + 2, x + w - 2, gy - h + lamp_h - 2,
                          fill="#fef9c3", outline="")
        elif theme == "playa":
            # Pelota de playa
            r = min(w, h) // 2
            cx_, cy_ = x + w // 2, gy - r
            c.create_oval(cx_ - r, cy_ - r, cx_ + r, cy_ + r,
                          fill="#ef4444", outline="#dc2626", width=1)
            c.create_arc(cx_ - r, cy_ - r, cx_ + r, cy_ + r,
                         start=30, extent=120, fill="#f8fafc", outline="")
            c.create_arc(cx_ - r, cy_ - r, cx_ + r, cy_ + r,
                         start=210, extent=120, fill="#3b82f6", outline="")
        else:
            # Espacio → estrella
            cx_, cy_ = x + w // 2, gy - h // 2
            pts = []
            import math as _m
            for i in range(10):
                angle = _m.radians(i * 36 - 90)
                r = (w // 2) if i % 2 == 0 else (w // 4)
                pts += [cx_ + r * _m.cos(angle), cy_ + r * _m.sin(angle)]
            c.create_polygon(pts, fill="#fef08a", outline="#fde047", width=1)

    def _draw_bg(self, offset: int) -> None:
        bg_theme = self._house.get("background", "oficina")
        grass_key = self._house.get("grass_color", "verde")
        ground_rgb = next((g[2] for g in GRASS_COLORS if g[0] == grass_key), None)
        self._bg_renderer.draw(self._canvas, self._W, self._H,
                                theme=bg_theme, ground_color=ground_rgb, x_offset=offset)

    def _draw_character(self, feet_y: float, frame: int = 0) -> None:
        try:
            spr = self._sprite_renderer.get_frame(
                "working", "neutral", frame,
                scale=self._game_scale, sprite_set=self._sprite_set)
            self._canvas.create_image(self.CHAR_X, int(feet_y), image=spr, anchor="s")
            self._img_refs.append(spr)
        except Exception:
            pass

    def _end_game(self) -> None:
        self._game_over = True
        self._running = False
        self._stop_music()
        self._play_crash()
        if self._after_id:
            try:
                self._win.after_cancel(self._after_id)
            except Exception:
                pass

        meters = int(self._score_px / 30)
        char_id = self._char.get("id", "")
        char_name = self._char.get("name", "Mascota")
        self._data_store.add_game_score(char_id, char_name, meters)
        top = self._data_store.get_top_scores(3)

        self._render_frame()
        c = self._canvas
        c.create_rectangle(0, 0, self._W, self._H, fill="#000000", stipple="gray50", outline="")
        c.create_text(self._W // 2, 44, text="GAME OVER",
                      fill="#ef4444", font=("Microsoft YaHei UI", 22, "bold"), anchor="center")
        c.create_text(self._W // 2, 78, text=f"{meters} metros",
                      fill="#f8fafc", font=("Microsoft YaHei UI", 14, "bold"), anchor="center")
        c.create_text(self._W // 2, 102, text="— TOP 3 —",
                      fill="#64748b", font=("Microsoft YaHei UI", 8), anchor="center")
        medals = ["🥇", "🥈", "🥉"]
        for i, entry in enumerate(top):
            is_new = entry.get("char_id") == char_id and entry.get("score") == meters
            color = "#fbbf24" if is_new else "#e2e8f0"
            medal = medals[i] if i < len(medals) else "   "
            c.create_text(self._W // 2, 116 + i * 16,
                          text=f"{medal}  {entry['char_name']}  —  {entry['score']} m",
                          fill=color, font=("Microsoft YaHei UI", 9), anchor="center")
        bx1, by1 = self._W // 2 - 55, self._H - 26
        bx2, by2 = self._W // 2 + 55, self._H - 8
        c.create_rectangle(bx1, by1, bx2, by2, fill="#1e293b", outline="#334155",
                            width=1, tags="close_btn")
        c.create_text((bx1 + bx2) // 2, (by1 + by2) // 2, text="Cerrar",
                      fill="#cbd5e1", font=("Microsoft YaHei UI", 9),
                      tags="close_btn", anchor="center")
        c.tag_bind("close_btn", "<Button-1>", lambda _: self._close())

    def _cleanup(self) -> None:
        self._stop_music()
        if self._after_id:
            try:
                self._win.after_cancel(self._after_id)
            except Exception:
                pass
        if self._on_done:
            self._on_done()

    def _close(self) -> None:
        try:
            self._win.destroy()
        except Exception:
            pass


class MascotaApp:
    def __init__(self) -> None:
        self.base_dir = Path(__file__).resolve().parent
        self.instance_mutex = self._acquire_single_instance()
        self.data_store = DataStore()
        self.xp_system = XPSystem(self.data_store)
        self.xp_system.on_level_up(self._on_level_up)
        self.break_system = BreakSystem(self.data_store)
        self.alarm_system = AlarmSystem(self.data_store)
        self._alarm_overlay: AlarmOverlayWindow | None = None
        self._current_alarm: dict | None = None
        self._levelup_message = ""
        self._levelup_until = 0.0
        self._break_overlay: BreakOverlayWindow | None = None
        self._break_accept_bounds: tuple[int, int, int, int] | None = None
        self._break_cancel_bounds: tuple[int, int, int, int] | None = None
        self._pending_picker_session: str | None = None
        self.parser = ConversationParser()
        self.store = SessionStore(self.parser, self.xp_system)
        self.installer = HookInstaller(self.base_dir)
        self.codex_installer = CodexHookInstaller(self.base_dir)
        self.sprite_renderer = SpriteRenderer(self.base_dir / "assets" / "sprites")
        self.bg_renderer = BackgroundRenderer(self.base_dir / "assets")
        self.dec_renderer = DecorationRenderer()
        self.float_renderer = FloatingItemRenderer()
        self.drag_origin: tuple[int, int] | None = None
        self._is_dragging = False
        self.details_visible = False
        self.animation_phase = 0.0
        self.frame_tick = 0.0
        self._session_phases: dict[str, float] = {}
        self._session_frames: dict[str, float] = {}
        self._bg_scroll_x: float = 0.0
        self.sprite_bounds: dict[str, tuple[float, float, float, float]] = {}
        self._cwd_label_text: str = ""
        self._cwd_label_until: float = 0.0
        self._pending_click: tk.Event | None = None
        self._click_after_id: str | None = None
        self._absorb_next_release: bool = False
        self._waiting_notified: dict[str, float] = {}
        self._no_sessions_since: float = 0.0
        self._picker_win: tk.Toplevel | None = None
        self._levelup_sparkles_until: float = 0.0
        self.decoration_bounds: dict[str, tuple[float, float, float, float]] = {}
        self._dragging_decoration: str | None = None
        self._dec_drag_offset: tuple[float, float] = (0.0, 0.0)
        self._dec_drag_pos: tuple[float, float] | None = None
        self._house_win_open: bool = False

        global _LANG
        _LANG = str(self.data_store.get("language") or "en")

        self.root = tk.Tk()
        self.root.title("Mascota")
        self.root.geometry("420x178")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=TRANSPARENT_KEY)

        # house_win: renders background scene (BG image + decorations).
        # Click-through so users interact with sprite_shield (above) and desktop below.
        self.bg_visible: bool = bool(self.data_store.get("bg_visible"))
        self.house_win = tk.Toplevel()
        self.house_win.overrideredirect(True)
        self.house_win.attributes("-topmost", True)
        self.house_win.configure(bg="#0a0f1a")
        self.house_win.geometry("420x132")
        self.house_win.wm_attributes("-alpha", 1.0 if self.bg_visible else 0.0)

        # Sprite shield: layered above house_win. Never gets alpha applied so
        # characters are always 100% opaque. Renders ONLY sprites & labels.
        self.sprite_shield = tk.Toplevel()
        self.sprite_shield.overrideredirect(True)
        self.sprite_shield.attributes("-topmost", True)
        self.sprite_shield.configure(bg=TRANSPARENT_KEY)
        self.sprite_shield.geometry("420x132")

        self.server = EventTCPServer((APP_HOST, APP_PORT), EventHandler)
        self.server.app = self
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)

        self.status_var = tk.StringVar(value="Starting listener...")
        self.toggle_var = tk.StringVar(value="Details")
        self._build_ui()
        wx = self.data_store.get("window_x")
        wy = self.data_store.get("window_y")
        if wx >= 0 and wy >= 0:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            if wx < sw and wy < sh:
                self.root.geometry(f"+{wx}+{wy}")
        else:
            self.root.update_idletasks()
            mx, my, mw, mh = _get_all_monitors()[0]
            ww = self.root.winfo_width() or 420
            wh = self.root.winfo_height() or 178
            cx = mx + (mw - ww) // 2
            cy = my + (mh - wh) // 2
            self.root.geometry(f"+{cx}+{cy}")
        # Reposition overlays below the toolbar using the actual widget coordinates
        self.root.update_idletasks()
        self.update_layout()
        self._auto_install_hook()
        if not self.data_store.get("characters"):
            self.root.after(600, self._show_first_use_popup)
        if self.data_store.get("greeted_date") != time.strftime("%Y-%m-%d"):
            # The first launch of a new day clears the day's one-off reminders, and only
            # those: anything that repeats has to survive it. Keeping only the alarms
            # with days of the month deleted the daily and weekly ones the morning after
            # they were created, while the field said "empty means every day" — the
            # worst kind of reminder, one you think you set.
            self.data_store.set("alarms", [
                a for a in (self.data_store.get("alarms") or [])
                if alarm_repeat(a) != REPEAT_ONCE
            ])
            self.root.after(800, self._show_daily_greeting)

    @staticmethod
    def _acquire_single_instance() -> int:
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, APP_MUTEX_NAME)
        if not mutex:
            return 0

        already_exists = ctypes.windll.kernel32.GetLastError() == 183
        if already_exists:
            ctypes.windll.kernel32.CloseHandle(mutex)
            sys.exit(0)
        return mutex

    def _on_level_up(self, new_level: int, char_id: str | None = None) -> None:
        self._levelup_message = T("levelup_msg_fmt").format(level=new_level)
        self._levelup_until = time.time() + 3.5
        self._levelup_sparkles_until = time.time() + 3.5
        threading.Thread(target=self._play_levelup_sound, daemon=True).start()
        if new_level >= 2:
            char = self.data_store.get_character(char_id) if char_id else self.data_store.get_active_character()
            if char:
                self.root.after(3800, lambda: self._show_game_offer(new_level, char["id"]))

    def toggle_background(self) -> None:
        self.bg_visible = not self.bg_visible
        self.data_store.set("bg_visible", self.bg_visible)
        self.house_win.wm_attributes("-alpha", 1.0 if self.bg_visible else 0.0)
        if self.bg_visible:
            self._bg_btn.configure(bg="#1d4ed8", fg="white")
        else:
            self._bg_btn.configure(bg="#161b22", fg="#8b949e")

    @staticmethod
    def _play_levelup_sound() -> None:
        try:
            for freq, dur in [(523, 90), (659, 90), (784, 90), (1047, 280)]:
                winsound.Beep(freq, dur)
        except Exception:
            pass

    def _build_ui(self) -> None:
        # ── Outer transparent frame ──────────────────────────────────
        self.frame = tk.Frame(self.root, bg=TRANSPARENT_KEY, bd=0, highlightthickness=0)
        self.frame.pack(fill="both", expand=True, padx=4, pady=4)

        # ── Hero canvas (mascots) ────────────────────────────────────
        # _root_hero: layout placeholder in root frame (also the render target in expanded mode)
        self._root_hero = tk.Canvas(self.frame, width=412, height=132,
                                    bg=TRANSPARENT_KEY, highlightthickness=0, relief="flat")
        self._root_hero.pack(fill="x")
        # house_canvas: renders ONLY background + decorations (in house_win, opacity-controlled)
        self.house_canvas = tk.Canvas(self.house_win, width=420, height=132,
                                      bg="#0a0f1a", highlightthickness=0, relief="flat")
        self.house_canvas.pack(fill="both", expand=True)
        # _shield_hero: renders ONLY mascot sprites (in sprite_shield, always 100% opaque)
        self._shield_hero = tk.Canvas(self.sprite_shield, width=420, height=132,
                                      bg=TRANSPARENT_KEY, highlightthickness=0, relief="flat")
        self._shield_hero.pack(fill="both", expand=True)
        # In compact mode (default), all sprite rendering goes to the shield canvas
        self.hero = self._shield_hero
        # Bind events to both hero canvases
        for _hc in [self._root_hero, self._shield_hero]:
            _hc.bind("<ButtonPress-1>", self.start_drag)
            _hc.bind("<B1-Motion>", self.do_drag)
            _hc.bind("<ButtonRelease-1>", self.on_hero_release)
            _hc.bind("<Double-Button-1>", self.on_hero_double_click)
            _hc.bind("<Button-3>", self.on_hero_right_click)

        # ── Bottom toolbar (always visible) ─────────────────────────
        C_TOOLBAR = "#0d1117"
        C_BTN     = "#161b22"
        C_HOVER   = "#21262d"
        C_TEXT    = "#8b949e"

        self.toolbar = tk.Frame(self.frame, bg=C_TOOLBAR, height=38)
        self.toolbar.pack(fill="x")   # toolbar is at the TOP
        self.toolbar.pack_propagate(False)
        # Make toolbar draggable (the dark area between buttons)
        self.toolbar.bind("<ButtonPress-1>", self.start_drag)
        self.toolbar.bind("<B1-Motion>", self.do_drag)
        self.toolbar.bind("<ButtonRelease-1>", self.on_hero_release)

        # Divider + buttons on the right (packed first to guarantee fixed space)
        right = tk.Frame(self.toolbar, bg=C_TOOLBAR)
        right.pack(side="right", padx=(0, 4), fill="y")

        # XP label on the left (draggable)
        self.xp_label = tk.Label(self.toolbar, text="", fg="#58a6ff", bg=C_TOOLBAR,
                                  font=("Microsoft YaHei UI", 8), anchor="w")
        self.xp_label.pack(side="left", padx=(8, 2), fill="y")
        self.xp_label.bind("<ButtonPress-1>", self.start_drag)
        self.xp_label.bind("<B1-Motion>", self.do_drag)
        self.xp_label.bind("<ButtonRelease-1>", self.on_hero_release)

        def _btn(txt: str, cmd: Any, fg: str = C_TEXT, bg: str = C_BTN,
                 emoji: bool = False) -> tk.Button:
            fnt = ("Segoe UI Emoji", 10) if emoji else ("Microsoft YaHei UI", 9)
            b = tk.Button(right, text=txt, command=cmd,
                          bg=bg, fg=fg,
                          activebackground=C_HOVER, activeforeground="#e6edf3",
                          relief="flat", padx=7, pady=3,
                          font=fnt, bd=0, highlightthickness=0)
            b.pack(side="left", padx=2, pady=4)
            return b

        _btn("🏠", self.open_house_editor, emoji=True)
        _btn("👤", self.open_character_editor, emoji=True)
        _btn("⏰", self.open_alarms, fg="#e3b341", emoji=True)
        _btn("⚙", self.open_settings)
        # Background toggle: shows/hides the house scene behind the characters
        _bg_init_bg = "#1d4ed8" if self.bg_visible else C_BTN
        _bg_init_fg = "white" if self.bg_visible else C_TEXT
        self._bg_btn = tk.Button(right, text="BG", command=self.toggle_background,
                                  bg=_bg_init_bg, fg=_bg_init_fg,
                                  activebackground=C_HOVER, activeforeground="#e6edf3",
                                  relief="flat", padx=6, pady=3,
                                  font=("Microsoft YaHei UI", 9), bd=0, highlightthickness=0)
        self._bg_btn.pack(side="left", padx=2, pady=4)
        self.floating_install = tk.Button(right)   # dummy ref, hook moved to settings
        _btn("✕", self.shutdown, fg="#fee2e2", bg="#7f1d1d")

        # ── Status label (shown in details mode) ────────────────────
        self.status_label = tk.Label(self.frame, textvariable=self.status_var,
                                      fg="#30363d", bg=C_TOOLBAR,
                                      anchor="w", font=("Microsoft YaHei UI", 7))

        # ── Header (shown in details mode, draggable) ────────────────
        self.header = tk.Frame(self.frame, bg=C_TOOLBAR)
        accent_bar = tk.Frame(self.header, bg="#7c3aed", width=3)
        accent_bar.pack(side="left", fill="y", padx=(0, 8))
        accent_bar.bind("<ButtonPress-1>", self.start_drag)
        accent_bar.bind("<B1-Motion>", self.do_drag)
        hdr_lbl = tk.Label(self.header, text="Pixel Companion",
                            fg="#e6edf3", bg=C_TOOLBAR,
                            font=("Microsoft YaHei UI", 10, "bold"))
        hdr_lbl.pack(side="left", pady=8)
        hdr_lbl.bind("<ButtonPress-1>", self.start_drag)
        hdr_lbl.bind("<B1-Motion>", self.do_drag)
        self.header.bind("<ButtonPress-1>", self.start_drag)
        self.header.bind("<B1-Motion>", self.do_drag)

        # ── Details body (canvas-based, distinct from the mascot view) ────────
        self.body_frame = tk.Frame(self.frame, bg="#0d1117")
        self.body_canvas = tk.Canvas(self.body_frame, bg="#0d1117",
                                      highlightthickness=0, relief="flat")
        self.body_canvas.pack(fill="both", expand=True)
        # Keep self.body as hidden dummy so render loop references don't crash
        self.body_scrollbar = tk.Scrollbar(self.body_frame, orient="vertical")
        self.body = tk.Text(self.body_frame, state="disabled")

        # Dummy refs kept for legacy update_layout calls
        self.floating_actions = tk.Frame(self.frame, bg=C_TOOLBAR)
        self.floating_details = tk.Button(self.floating_actions)

        self._configure_transparency()
        self.update_layout()

    def _configure_transparency(self) -> None:
        for win in [self.root, self.sprite_shield]:
            try:
                win.wm_attributes("-transparentcolor", TRANSPARENT_KEY)
            except tk.TclError:
                pass
        self._set_tool_window_style()
        self._set_tool_window_style(self.sprite_shield)
        self._set_tool_window_style(self.house_win, click_through=True)

    def _auto_install_hook(self) -> None:
        ok, message = self.installer.install()
        self.status_var.set(message if ok else f"Auto-install skipped: {message}")
        self.codex_installer.install()

    def _set_tool_window_style(self, win: tk.Misc | None = None,
                               click_through: bool = False) -> None:
        try:
            target = win if win is not None else self.root
            hwnd = ctypes.windll.user32.GetParent(target.winfo_id())
            exstyle = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            new_style = exstyle | 0x00000080  # WS_EX_TOOLWINDOW (no taskbar entry)
            if click_through:
                new_style |= 0x00000020  # WS_EX_TRANSPARENT (mouse pass-through)
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, new_style)
        except Exception:
            pass

    def start_drag(self, event: tk.Event) -> None:
        # Banner buttons fire immediately on press (no drag delay)
        if self._break_accept_bounds is not None:
            bx1, by1, bx2, by2 = self._break_accept_bounds
            if bx1 <= event.x <= bx2 and by1 <= event.y <= by2:
                self._absorb_next_release = True
                self._start_break()
                return
        if self._break_cancel_bounds is not None:
            bx1, by1, bx2, by2 = self._break_cancel_bounds
            if bx1 <= event.x <= bx2 and by1 <= event.y <= by2:
                self._absorb_next_release = True
                self.break_system.snooze()
                return
        if not self.details_visible and self._house_win_open:
            dec = self._decoration_at_point(event.x, event.y)
            if dec is not None:
                self._dragging_decoration = dec
                bounds = self.decoration_bounds.get(dec)
                if bounds:
                    cx = (bounds[0] + bounds[2]) / 2
                    cy = (bounds[1] + bounds[3]) / 2
                    self._dec_drag_offset = (event.x - cx, event.y - cy)
                else:
                    self._dec_drag_offset = (0.0, 0.0)
                return
        self.drag_origin = (event.x_root, event.y_root)
        self._is_dragging = False

    def do_drag(self, event: tk.Event) -> None:
        if self._dragging_decoration is not None:
            ox, oy = self._dec_drag_offset
            self._dec_drag_pos = (event.x - ox, event.y - oy)
            return
        if self.drag_origin is None:
            return
        dx = event.x_root - self.drag_origin[0]
        dy = event.y_root - self.drag_origin[1]
        if abs(dx) > 4 or abs(dy) > 4:
            self._is_dragging = True
        x = self.root.winfo_x() + dx
        y = self.root.winfo_y() + dy
        self.root.geometry(f"+{x}+{y}")
        if not self.details_visible:
            # Move overlays by the same delta — preserves their Y offset from toolbar
            self.house_win.geometry(
                f"+{self.house_win.winfo_x() + dx}+{self.house_win.winfo_y() + dy}")
            self.sprite_shield.geometry(
                f"+{self.sprite_shield.winfo_x() + dx}+{self.sprite_shield.winfo_y() + dy}")
        self.drag_origin = (event.x_root, event.y_root)

    def _decoration_at_point(self, x: float, y: float) -> str | None:
        for dec, (x1, y1, x2, y2) in self.decoration_bounds.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                return dec
        return None

    def on_hero_release(self, event: tk.Event) -> None:
        if self._dragging_decoration is not None:
            cw = int(self.hero.cget("width"))
            ch = int(self.hero.cget("height"))
            ox, oy = self._dec_drag_offset
            fx = max(0.0, min(1.0, (event.x - ox) / cw))
            fy = max(0.0, min(1.0, (event.y - oy) / ch))
            house = self.data_store.get_house()
            positions = dict(house.get("decoration_positions", {}))
            positions[self._dragging_decoration] = [fx, fy]
            self.data_store.update_house(decoration_positions=positions)
            self._dragging_decoration = None
            self._dec_drag_pos = None
            return
        # The second ButtonRelease of a double-click must be swallowed so it
        # doesn't schedule a spurious single-click after the double-click ran.
        if self._absorb_next_release:
            self._absorb_next_release = False
            self._is_dragging = False
            self.drag_origin = None
            return
        if not self._is_dragging:
            self._pending_click = event
            self._click_after_id = self.root.after(250, self._fire_single_click)
        self._is_dragging = False
        self.drag_origin = None

    def _fire_single_click(self) -> None:
        self._click_after_id = None
        if self._pending_click is not None:
            self.on_hero_click(self._pending_click)
            self._pending_click = None

    def toggle_details(self) -> None:
        self.details_visible = not self.details_visible
        self.update_layout()

    def update_layout(self) -> None:
        C_TOOLBAR = "#0d1117"
        # Forget dynamic elements
        self.header.pack_forget()
        self.status_label.pack_forget()
        self.body_frame.pack_forget()
        self.floating_actions.place_forget()
        self.toolbar.pack_forget()
        self._root_hero.pack_forget()

        if self.details_visible:
            # Expanded mode: render to root's canvas, hide overlay windows
            self.hero = self._root_hero
            # Clear stale content from overlay canvases before hiding them
            self._shield_hero.delete("all")
            self.house_canvas.delete("all")
            self.house_win.withdraw()
            self.sprite_shield.withdraw()
            self.frame.configure(bg=C_TOOLBAR, highlightthickness=1,
                                  highlightbackground="#30363d")
            self.root.configure(bg=C_TOOLBAR)
            self._root_hero.configure(bg=C_TOOLBAR, width=510, height=110)
            # Pack order: toolbar → header → hero → status → body
            self.toolbar.pack(fill="x")
            self.header.pack(fill="x")
            self._root_hero.pack(fill="x", pady=(0, 2))
            self.status_label.pack(fill="x", padx=10)
            self.body_frame.pack(fill="both", expand=True, padx=8, pady=(4, 6))
            self.root.geometry("570x450")
            self.toggle_var.set("▲ Ocultar")
        else:
            # Compact mode: toolbar at TOP, overlay windows below it
            self.hero = self._shield_hero
            self.frame.configure(bg=TRANSPARENT_KEY, highlightthickness=0)
            self.root.configure(bg=TRANSPARENT_KEY)
            self._root_hero.configure(bg=TRANSPARENT_KEY, width=412, height=132)
            # Pack order: toolbar first (top), then transparent hero spacer below
            self.toolbar.pack(fill="x")
            self._root_hero.pack(fill="x")
            self.root.geometry("420x178")
            # Position overlay windows starting exactly where the hero area is on screen
            self.root.update_idletasks()
            rx = self.root.winfo_x()
            ry = self.root.winfo_y()
            # winfo_rooty() gives the absolute screen Y of the widget — most reliable
            overlay_y = self._root_hero.winfo_rooty()
            if overlay_y <= 1:
                overlay_y = ry + 42  # fallback: approx frame-pad(4) + toolbar(38)
            self.house_win.geometry(f"420x132+{rx}+{overlay_y}")
            self.house_win.deiconify()
            self.sprite_shield.geometry(f"420x132+{rx}+{overlay_y}")
            self.sprite_shield.deiconify()
            self.sprite_shield.lift()  # sprite_shield always above house_win
            self.toggle_var.set("▼ Info")
        self._configure_transparency()

    def on_hero_click(self, event: tk.Event) -> None:
        if self._picker_win is not None and self._picker_win.winfo_exists():
            self._picker_win.lift()
            self._picker_win.focus_set()
            return
        if self._break_accept_bounds is not None:
            bx1, by1, bx2, by2 = self._break_accept_bounds
            if bx1 <= event.x <= bx2 and by1 <= event.y <= by2:
                self._start_break()
                return
        if self._break_cancel_bounds is not None:
            bx1, by1, bx2, by2 = self._break_cancel_bounds
            if bx1 <= event.x <= bx2 and by1 <= event.y <= by2:
                self.break_system.snooze()
                return
        session_id = self._session_id_at_point(event.x, event.y)
        if session_id is not None:
            self.store.select_session(session_id)
            sessions = self.store.snapshot()
            target = next((s for s in sessions if s.session_id == session_id), None)
            if target:
                self._cwd_label_text = target.cwd or target.project_name
                self._cwd_label_until = time.time() + 3.0
            return
        if self.details_visible:
            self.toggle_details()

    def on_hero_right_click(self, event: tk.Event) -> None:
        session_id = self._session_id_at_point(event.x, event.y)
        if session_id is None:
            return
        sessions = self.store.snapshot()
        target = next((s for s in sessions if s.session_id == session_id), None)
        if target is None:
            return
        menu = tk.Menu(
            self.root, tearoff=0,
            bg="#111827", fg="#f8fafc",
            activebackground="#1e293b", activeforeground="#f8fafc",
            relief="flat", bd=0,
        )
        label = T("ctx_remove_fmt").format(name=target.project_name)
        menu.add_command(label=label, command=lambda: self._remove_session(session_id, target))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _remove_session(self, session_id: str, session: "SessionData") -> None:
        self._close_session_terminal(session)
        self.store.remove_session(session_id)
        if self._pending_picker_session == session_id:
            self._pending_picker_session = None

    def _close_session_terminal(self, session: "SessionData") -> None:
        project = session.project_name
        if not project or project == "unknown":
            return
        user32 = ctypes.windll.user32
        WM_CLOSE = 0x0010
        EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
        terminal_classes = {"CASCADIA_HOSTING_WINDOW_CLASS", "ConsoleWindowClass", "PseudoConsoleWindow"}
        proj_lower = project.lower()

        def _cb(hwnd: int, _: int) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True
            cls_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls_buf, 256)
            if cls_buf.value not in terminal_classes:
                return True
            n = user32.GetWindowTextLengthW(hwnd)
            if n == 0:
                return True
            title_buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, title_buf, n + 1)
            if proj_lower in title_buf.value.lower():
                user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
            return True

        try:
            user32.EnumWindows(EnumProc(_cb), 0)
        except Exception:
            pass

    def _focus_session_window(self, session: SessionData) -> None:
        if session.claude_pid:
            if self._focus_terminal_by_pid(session.claude_pid):
                return
        # Fallback: search visible terminal windows by project name in title
        project = session.project_name
        if not project or project == "unknown":
            return
        user32 = ctypes.windll.user32
        EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
        terminal_classes = {"CASCADIA_HOSTING_WINDOW_CLASS", "ConsoleWindowClass", "PseudoConsoleWindow"}
        candidates: list[tuple[int, int]] = []

        def _cb(hwnd: int, _: int) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True
            cls_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls_buf, 256)
            is_terminal = cls_buf.value in terminal_classes
            n = user32.GetWindowTextLengthW(hwnd)
            if n == 0:
                return True
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if project.lower() in buf.value.lower():
                candidates.append((2 if is_terminal else 1, hwnd))
            return True

        try:
            user32.EnumWindows(EnumProc(_cb), 0)
            if candidates:
                candidates.sort(reverse=True)
                hwnd = candidates[0][1]
                user32.ShowWindow(hwnd, 9)
                user32.SetForegroundWindow(hwnd)
        except Exception:
            pass

    def _focus_terminal_by_pid(self, start_pid: int) -> bool:
        """Walk process tree up from start_pid until we find a visible window."""
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32

        class PROCESSENTRY32(ctypes.Structure):
            _fields_ = [
                ("dwSize", ctypes.c_uint32),
                ("cntUsage", ctypes.c_uint32),
                ("th32ProcessID", ctypes.c_uint32),
                ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", ctypes.c_uint32),
                ("cntThreads", ctypes.c_uint32),
                ("th32ParentProcessID", ctypes.c_uint32),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", ctypes.c_uint32),
                ("szExeFile", ctypes.c_char * 260),
            ]

        def get_parent_pid(pid: int, snap: int) -> int | None:
            entry = PROCESSENTRY32()
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
            if not kernel32.Process32First(snap, ctypes.byref(entry)):
                return None
            while True:
                if entry.th32ProcessID == pid:
                    return entry.th32ParentProcessID
                if not kernel32.Process32Next(snap, ctypes.byref(entry)):
                    return None

        def find_hwnd_for_pid(pid: int) -> int | None:
            EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
            found: list[int] = []

            def _cb(hwnd: int, _: int) -> bool:
                if user32.IsWindowVisible(hwnd):
                    wpid = ctypes.c_ulong(0)
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
                    if wpid.value == pid:
                        found.append(hwnd)
                return True

            user32.EnumWindows(EnumProc(_cb), 0)
            return found[0] if found else None

        try:
            TH32CS_SNAPPROCESS = 0x2
            snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
            if snap == ctypes.c_void_p(-1).value:
                return False
            try:
                pid = start_pid
                for _ in range(6):
                    hwnd = find_hwnd_for_pid(pid)
                    if hwnd:
                        user32.ShowWindow(hwnd, 9)
                        user32.SetForegroundWindow(hwnd)
                        return True
                    parent = get_parent_pid(pid, snap)
                    if not parent or parent == pid:
                        break
                    pid = parent
            finally:
                kernel32.CloseHandle(snap)
        except Exception:
            pass
        return False

    def _check_waiting_beeps(self, sessions: list[SessionData]) -> None:
        now = time.time()
        waiting_ids = {s.session_id for s in sessions if s.state == "waiting"}
        for sid in list(self._waiting_notified):
            if sid not in waiting_ids:
                del self._waiting_notified[sid]
        for session in sessions:
            if session.state != "waiting":
                continue
            last = self._waiting_notified.get(session.session_id, 0.0)
            if now - last >= 30.0:
                self._waiting_notified[session.session_id] = now
                threading.Thread(target=self._play_permission_beep, daemon=True).start()

    @staticmethod
    def _play_permission_beep() -> None:
        try:
            winsound.Beep(880, 160)
            time.sleep(0.09)
            winsound.Beep(1100, 200)
        except Exception:
            pass

    def _start_break(self) -> None:
        if self._break_overlay is not None:
            return
        duration = max(1, int(self.break_system.duration_seconds()))
        self._break_overlay = BreakOverlayWindow(
            self.root, duration,
            on_complete=self._on_break_complete,
            on_cancel=self._on_break_cancel,
        )

    def _on_break_complete(self) -> None:
        self._break_overlay = None
        self.break_system.mark_taken()
        self.xp_system.add_xp(5)

    def _on_break_cancel(self) -> None:
        self._break_overlay = None
        self.break_system.mark_taken()

    def _on_alarm_dismiss(self) -> None:
        if self._current_alarm:
            self.alarm_system.mark_triggered(self._current_alarm["id"])
        self._alarm_overlay = None
        self._current_alarm = None

    def _on_alarm_snooze(self) -> None:
        if self._current_alarm:
            self.alarm_system.snooze_alarm(self._current_alarm["id"], minutes=10)
        self._alarm_overlay = None
        self._current_alarm = None

    def on_hero_double_click(self, event: tk.Event) -> None:
        # Cancel the single-click that was scheduled by the first ButtonRelease.
        if self._click_after_id is not None:
            self.root.after_cancel(self._click_after_id)
            self._click_after_id = None
        self._pending_click = None
        # The second ButtonRelease fires after this event; swallow it.
        self._absorb_next_release = True

        session_id = self._session_id_at_point(event.x, event.y)
        if session_id is not None:
            self.store.select_session(session_id)
            sessions = self.store.snapshot()
            target = next((s for s in sessions if s.session_id == session_id), None)
            if target:
                self._focus_session_window(target)
            return
        if not self.details_visible:
            self.toggle_details()

    def _session_id_at_point(self, x: float, y: float) -> str | None:
        for session_id, bounds in reversed(list(self.sprite_bounds.items())):
            left, top, right, bottom = bounds
            if left <= x <= right and top <= y <= bottom:
                return session_id
        return None

    def install_hook(self) -> None:
        ok, message = self.installer.install()
        self.status_var.set(message)
        if not ok:
            messagebox.showerror("Hook install failed", message)

    def render(self) -> None:
        sessions = self.store.snapshot()
        self._check_waiting_beeps(sessions)
        focused = self.store.effective_session()
        claude_hook = "✓" if self.installer.is_installed() else "✗"
        codex_hook = "✓" if self.codex_installer.is_installed() else "✗"
        self.status_var.set(f":{APP_PORT} | Claude {claude_hook} | Codex {codex_hook} | Sessions: {len(sessions)}")
        if focused and focused.character_id and self.data_store.get_character(focused.character_id):
            xp_text = self.xp_system.bar_text_for(focused.character_id)
            if self.data_store.get("active_character_id") != focused.character_id:
                self.data_store.set_active_character(focused.character_id)
        else:
            xp_text = self.xp_system.bar_text()
        self.xp_label.configure(text=xp_text)

        if self._pending_picker_session is None:
            pending = self.store.sessions_needing_character()
            if pending:
                self._pending_picker_session = pending[0]
                self.root.after(100, lambda sid=pending[0]: self._show_character_picker(sid))

        self.render_mascot(sessions)

        if self.details_visible:
            self._draw_details(sessions, focused)

        due_alarm = self.alarm_system.check_due()
        if due_alarm and self._alarm_overlay is None:
            self._current_alarm = due_alarm
            self._alarm_overlay = AlarmOverlayWindow(
                self.root, due_alarm,
                on_dismiss=self._on_alarm_dismiss,
                on_snooze=self._on_alarm_snooze,
            )

        self.root.after(REFRESH_MS, self.render)

    def animate(self) -> None:
        sessions = self.store.snapshot()
        active_ids = {s.session_id for s in sessions}

        for session in sessions:
            sid = session.session_id
            self._session_phases[sid] = (
                self._session_phases.get(sid, 0.0)
                + self._phase_step_for(session.state, session.emotion)
            )
            self._session_frames[sid] = (
                self._session_frames.get(sid, 0.0)
                + self._frame_step_for(session.state, session.emotion)
            )

        # Clean up ended sessions
        for sid in list(self._session_phases.keys()):
            if sid not in active_ids:
                self._session_phases.pop(sid, None)
                self._session_frames.pop(sid, None)

        # Global phase for effects independent of sessions (banner pulse, etc.)
        self.animation_phase += self._phase_step_for("idle", "neutral")

        if any(s.state == "working" for s in sessions):
            self._bg_scroll_x += BG_SCROLL_SPEED

        self.render_mascot(sessions)
        self.root.after(ANIMATION_MS, self.animate)

    def _draw_details(self, sessions: list[SessionData], focused: SessionData | None) -> None:
        c = self.body_canvas
        c.update_idletasks()
        w = c.winfo_width() or 510
        c.delete("all")
        STATE_COLOR = {
            "working":    "#3fb950",
            "waiting":    "#e3b341",
            "compacting": "#58a6ff",
            "sleeping":   "#8b949e",
            "idle":       "#58a6ff",
        }
        EMOTION_COLOR = {
            "happy":   "#f0883e",
            "sad":     "#79c0ff",
            "sob":     "#f85149",
            "neutral": "#8b949e",
        }
        if not sessions:
            c.create_text(w // 2, 48, anchor="center",
                          text="Sin sesiones activas",
                          fill="#30363d", font=("Microsoft YaHei UI", 11))
            c.create_text(w // 2, 70, anchor="center",
                          text="Abrí Claude Code para que aparezcan tus personajes",
                          fill="#21262d", font=("Microsoft YaHei UI", 8))
            return
        pad, gap = 8, 6
        card_h = 80
        y = pad
        for session in sessions[:5]:
            is_focused = focused is not None and focused.session_id == session.session_id
            sc = STATE_COLOR.get(session.state, "#58a6ff")
            ec = EMOTION_COLOR.get(session.emotion, "#8b949e")
            border = sc if is_focused else "#21262d"
            c.create_rectangle(pad, y, w - pad, y + card_h,
                                fill="#161b22", outline=border, width=1 + is_focused)
            # Left state stripe
            c.create_rectangle(pad, y, pad + 4, y + card_h, fill=sc, outline="")
            # Project name
            c.create_text(pad + 12, y + 12, anchor="w",
                          text=session.project_name,
                          fill="#e6edf3", font=("Microsoft YaHei UI", 9, "bold"))
            # State + emotion badges (right)
            badge = f"{session.state}  {session.emotion}"
            c.create_text(w - pad - 6, y + 12, anchor="e",
                          text=session.state.upper(),
                          fill=sc, font=("Microsoft YaHei UI", 7, "bold"))
            c.create_text(w - pad - 6, y + 24, anchor="e",
                          text=session.emotion,
                          fill=ec, font=("Microsoft YaHei UI", 7))
            # Duration
            c.create_text(pad + 12, y + 28, anchor="w",
                          text=f"⏱  {session.duration}",
                          fill="#6e7681", font=("Microsoft YaHei UI", 8))
            # Last prompt
            if session.last_prompt:
                prompt = session.last_prompt[:55] + ("…" if len(session.last_prompt) > 55 else "")
                c.create_text(pad + 12, y + 46, anchor="w",
                              text=f"›  {prompt}",
                              fill="#8b949e", font=("Microsoft YaHei UI", 8))
            # Tool
            if session.current_tool:
                c.create_text(pad + 12, y + 62, anchor="w",
                              text=f"⚙  {session.current_tool}",
                              fill="#7c3aed", font=("Microsoft YaHei UI", 8))
            elif session.messages:
                preview = session.messages[-1].replace("\n", " ")[:55]
                c.create_text(pad + 12, y + 62, anchor="w",
                              text=f"✦  {preview}",
                              fill="#30363d", font=("Microsoft YaHei UI", 8))
            y += card_h + gap

    def render_mascot(self, sessions: list[SessionData]) -> None:
        # Sprite canvas (sprite_shield) — always 100% opaque, draws only mascots
        canvas = self.hero
        canvas.delete("all")
        self.sprite_bounds = {}

        width = int(canvas.cget("width"))
        height = int(canvas.cget("height"))
        focused = self.store.effective_session()
        sprite_base_scale = self._base_sprite_scale(len(sessions))

        house = self.data_store.get_house()
        bg_theme = house.get("background", "oficina")
        active_decorations: list[str] = house.get("decorations", [])
        dec_positions: dict[str, list[float]] = house.get("decoration_positions", {})
        grass_key = house.get("grass_color", "verde")
        ground_rgb = next((g[2] for g in GRASS_COLORS if g[0] == grass_key), None)

        if not self.details_visible:
            # Background scene goes to house_canvas (opacity-controlled window)
            hc = self.house_canvas
            hc.delete("all")
            hc_w = int(hc.cget("width")) or width
            hc_h = int(hc.cget("height")) or height
            self.bg_renderer.draw(hc, hc_w, hc_h, theme=bg_theme, ground_color=ground_rgb,
                                   x_offset=int(self._bg_scroll_x))
            self.decoration_bounds = {}
            for dec in active_decorations:
                img = self.dec_renderer.get(dec, hc_h)
                if img is None:
                    continue
                default_pos = _DEFAULT_DEC_POSITIONS.get(dec, [0.5, 0.5])
                stored = dec_positions.get(dec, default_pos)
                if self._dragging_decoration == dec and self._dec_drag_pos is not None:
                    dx, dy = self._dec_drag_pos
                else:
                    dx = stored[0] * hc_w
                    dy = stored[1] * hc_h
                draw_dx = (dx - self._bg_scroll_x) % hc_w
                dw, dh = self.dec_renderer.size(dec, hc_h)
                hc.create_image(int(draw_dx), int(dy), image=img, anchor="center")
                self.decoration_bounds[dec] = (draw_dx - dw / 2, dy - dh / 2,
                                               draw_dx + dw / 2, dy + dh / 2)

        sparkles_active = time.time() < self._levelup_sparkles_until
        ordered_sessions = sorted(sessions, key=lambda item: item.sprite_x)
        for index, session in enumerate(ordered_sessions):
            state = session.state
            emotion = session.emotion
            sid = session.session_id
            sess_phase = self._session_phases.get(sid, 0.0)
            sess_frame = self._session_frames.get(sid, 0.0)
            bob = self._bob_offset(state, emotion, sess_phase)
            pet_x = self._sprite_canvas_x(index, len(ordered_sessions), width)
            if state != "working":
                pet_x = (pet_x - self._bg_scroll_x) % width
            is_selected = focused is not None and focused.session_id == session.session_id
            session_char = self.data_store.get_character(session.character_id) if session.character_id else None
            char_level = session_char.get("level", 1) if session_char else 1
            level_mult = self._level_scale_mult(char_level)
            char_tint_key = session_char.get("tint", "original") if session_char else "original"
            tint_rgb = next((t[2] for t in MASCOT_TINTS if t[0] == char_tint_key), None)
            outline_key = session_char.get("outline", "ninguno") if session_char else "ninguno"
            outline_rgb = next((o[2] for o in OUTLINE_OPTIONS if o[0] == outline_key), None)
            float_key = session_char.get("floating_item", "ninguno") if session_char else "ninguno"
            sprite_set = session_char.get("sprite_set", "Dino") if session_char else "Dino"
            scale_multiplier = SPRITE_SET_SCALE_DEFAULTS.get(sprite_set, 1.0)
            sprite_scale = sprite_base_scale * level_mult * scale_multiplier * (1.04 if is_selected else 1.0)
            sprite = self.sprite_renderer.get_frame(
                state, emotion, int(sess_frame),
                scale=sprite_scale, tint=tint_rgb, outline_rgb=outline_rgb,
                sprite_set=sprite_set,
            )
            sprite_width = sprite.width()
            sprite_height = sprite.height()
            # Adjust y so feet stay at the same ground level regardless of size
            y_ground_offset = (1.0 - level_mult) * 20
            effective_bob = 0.0
            sprite_y = 82 + y_ground_offset + session.sprite_y_offset * 0.22 + effective_bob
            # Clamp so the sprite is always fully visible within the canvas bounds
            half_sh = sprite_height / 2
            sprite_y = max(half_sh + 1, min(height - half_sh - 1, sprite_y))

            canvas.create_image(pet_x, sprite_y, image=sprite)
            self.sprite_bounds[session.session_id] = (
                pet_x - sprite_width / 2,
                sprite_y - sprite_height / 2,
                pet_x + sprite_width / 2,
                sprite_y + sprite_height / 2,
            )

            if is_selected and sparkles_active:
                phase = sess_phase * 2.5
                colors = ["#fbbf24", "#f472b6", "#60a5fa", "#34d399", "#a78bfa"]
                for i in range(6):
                    angle = (i / 6) * 2 * math.pi + phase
                    dist = sprite_width * 0.65 + math.sin(phase + i) * 5
                    sx = pet_x + math.cos(angle) * dist
                    sy = sprite_y + math.sin(angle) * dist * 0.55
                    col = colors[i % len(colors)]
                    r = 3 + int(math.sin(phase * 1.5 + i) * 1.5)
                    canvas.create_oval(sx - r, sy - r, sx + r, sy + r, fill=col, outline="")

            if session_char:
                char = session_char
                if char:
                    name = char.get("name", "")
                    raw_name_y = sprite_y - sprite_height / 2 - 9
                    name_y = max(14, raw_name_y)
                    # Draw floating accessory behind the name at name position (smaller scale)
                    if float_key and float_key != "ninguno":
                        item_scale = min(sprite_scale * 0.42, 1.5)
                        float_img = self.float_renderer.get(float_key, item_scale)
                        if float_img is not None:
                            item_bob = math.sin(sess_phase * 1.6) * 1.5
                            canvas.create_image(int(pet_x), int(name_y + item_bob),
                                                image=float_img, anchor="center")
                    name_color = "#ffffff" if is_selected else "#e2e8f0"
                    font = ("Microsoft YaHei UI", 9, "bold") if is_selected else ("Microsoft YaHei UI", 8)
                    for ox, oy in [(-1, 1), (1, 1), (0, 2)]:
                        canvas.create_text(pet_x + ox, name_y + oy, text=name,
                                           fill="#000000", font=font, anchor="center")
                    canvas.create_text(pet_x, name_y, text=name,
                                       fill=name_color, font=font, anchor="center")

        if self.details_visible and focused is None:
            canvas.create_text(156, 60, text="Install the hook and start a session.", anchor="w", fill="#cbd5e1", font=("Segoe UI", 10), width=290)

        if self._house_win_open and not self.details_visible:
            canvas.create_rectangle(0, height - 16, width, height, fill="#0f172a", outline="")
            canvas.create_text(width // 2, height - 8,
                                text="✦ Arrastrá las decoraciones para moverlas ✦",
                                fill="#64748b", font=("Microsoft YaHei UI", 7), anchor="center")

        if not self.details_visible and self.break_system.banner_visible() and self._break_overlay is None:
            pulse = 0.5 + 0.5 * math.sin(self.animation_phase * 1.2)
            r_c = int(59 + pulse * 30)
            g_c = int(130 + pulse * 40)
            b_c = 255
            outline_col = f"#{r_c:02x}{g_c:02x}{b_c:02x}"
            bx1, by1 = 8, height - 48
            bx2, by2 = width - 8, height - 4
            canvas.create_rectangle(bx1 + 2, by1 + 2, bx2 + 2, by2 + 2,
                                     fill="#000000", outline="", stipple="gray50")
            canvas.create_rectangle(bx1, by1, bx2, by2,
                                     fill="#0f172a", outline=outline_col, width=2)
            canvas.create_text(bx1 + 14, (by1 + by2) // 2,
                                text="☕", font=("Segoe UI Emoji", 10), anchor="w",
                                fill="#fbbf24")
            canvas.create_text(bx1 + 34, by1 + 10,
                                text=self.break_system.banner_text(),
                                fill="#e2e8f0", font=("Microsoft YaHei UI", 8, "bold"),
                                anchor="w")
            canvas.create_text(bx1 + 34, by1 + 26,
                                text="¿Tomamos un descanso?",
                                fill="#64748b", font=("Microsoft YaHei UI", 7),
                                anchor="w")
            # Accept button
            abx1 = bx2 - 142
            abx2 = bx2 - 76
            aby1 = by1 + 8
            aby2 = by2 - 8
            canvas.create_rectangle(abx1, aby1, abx2, aby2,
                                     fill="#064e3b", outline="#34d399", width=1)
            canvas.create_text((abx1 + abx2) // 2, (aby1 + aby2) // 2,
                                text="Aceptar", fill="#6ee7b7",
                                font=("Microsoft YaHei UI", 7, "bold"), anchor="center")
            self._break_accept_bounds = (abx1, aby1, abx2, aby2)
            # Cancel button
            cbx1 = bx2 - 70
            cbx2 = bx2 - 4
            cby1 = aby1
            cby2 = aby2
            canvas.create_rectangle(cbx1, cby1, cbx2, cby2,
                                     fill="#1e293b", outline="#475569", width=1)
            canvas.create_text((cbx1 + cbx2) // 2, (cby1 + cby2) // 2,
                                text="Ahora no", fill="#94a3b8",
                                font=("Microsoft YaHei UI", 7), anchor="center")
            self._break_cancel_bounds = (cbx1, cby1, cbx2, cby2)
        else:
            self._break_accept_bounds = None
            self._break_cancel_bounds = None

        if self._levelup_message and time.time() < self._levelup_until:
            canvas.create_text(
                width // 2, 16,
                text=self._levelup_message,
                fill="#fbbf24",
                font=("Microsoft YaHei UI", 10, "bold"),
                anchor="center",
            )

        if self._cwd_label_text and time.time() < self._cwd_label_until:
            label = self._cwd_label_text
            if len(label) > 55:
                label = "..." + label[-52:]
            canvas.create_rectangle(6, 2, width - 6, 18, fill="#0f172a", outline="#334155")
            canvas.create_text(
                width // 2, 10,
                text=label,
                fill="#93c5fd",
                font=("Microsoft YaHei UI", 7),
                anchor="center",
            )

        # Keep sprite_shield always visually above house_win
        if not self.details_visible:
            self.sprite_shield.lift()

    @staticmethod
    def _draw_grass_band(canvas: tk.Canvas, width: int, height: int,
                         body_color: str = "#5d7c67", ridge_color: str = "#7f9a86") -> None:
        left = 26
        right = width - 26
        base_y = height - 18
        canvas.create_oval(left + 18, base_y - 4, right - 18, base_y + 12, fill="#111827", outline="")
        canvas.create_oval(left, base_y - 12, right, base_y + 8, fill=body_color, outline="")
        canvas.create_oval(left + 10, base_y - 14, right - 10, base_y - 2, fill=ridge_color, outline="")

    def _subtitle_for(self, session: SessionData) -> str:
        if session.messages:
            preview = session.messages[-1].replace("\n", " ").strip()
            return preview[:72] + ("..." if len(preview) > 72 else "")
        if session.current_tool:
            return f"Using {session.current_tool}"
        if session.last_prompt:
            return session.last_prompt[:72] + ("..." if len(session.last_prompt) > 72 else "")
        return f"Mode: {session.permission_mode}"

    @staticmethod
    def _sprite_canvas_x(index: int, total: int, width: int) -> float:
        if total <= 1:
            return width * 0.5
        left_margin = 76
        right_margin = 92
        usable_width = max(120, width - left_margin - right_margin)
        step = usable_width / max(1, total - 1)
        return left_margin + (step * index)

    def _bob_offset(self, state: str, emotion: str, phase: float) -> float:
        amplitudes = {
            "working": 3.5,
            "waiting": 1.5,
            "compacting": 1.0,
            "sleeping": 0.5,
            "resting": 0.6,
            "idle": 2.0,
        }
        amplitude = amplitudes.get(state, 2.0) * self._emotion_motion_multiplier(emotion)
        return math.sin(phase) * amplitude

    @staticmethod
    def _level_scale_mult(level: int) -> float:
        """Level 1 = baby (0.5x), Level 20 = full size (1.0x)."""
        return 0.5 + (max(1, min(20, level)) - 1) / 19 * 0.5

    @staticmethod
    def _base_sprite_scale(session_count: int) -> float:
        return {
            0: 1.2,
            1: 1.2,
            2: 1.08,
            3: 0.96,
            4: 0.86,
        }.get(session_count, 0.78)

    @staticmethod
    def _base_grass_scale(session_count: int) -> float:
        return {
            0: 0.62,
            1: 0.62,
            2: 0.56,
            3: 0.5,
            4: 0.46,
        }.get(session_count, 0.42)

    @staticmethod
    def _emotion_motion_multiplier(emotion: str) -> float:
        return {
            "happy": 1.35,
            "neutral": 1.0,
            "sad": 0.72,
            "sob": 0.3,
        }.get(emotion, 1.0)

    def _phase_step_for(self, state: str, emotion: str) -> float:
        base = {
            "working": 0.42,
            "waiting": 0.24,
            "compacting": 0.18,
            "sleeping": 0.08,
            "resting": 0.06,
            "idle": 0.28,
        }.get(state, 0.28)
        return base * self._emotion_motion_multiplier(emotion)

    def _frame_step_for(self, state: str, emotion: str) -> float:
        base = {
            "working": 0.9,
            "waiting": 0.45,
            "compacting": 0.55,
            "sleeping": 0.15,
            "resting": 0.12,
            "idle": 0.35,
        }.get(state, 0.35)
        return max(0.08, base * self._emotion_motion_multiplier(emotion))

    def _animation_delay_for(self, state: str, emotion: str) -> int:
        base = {
            "working": 95,
            "waiting": 120,
            "compacting": 140,
            "sleeping": 220,
            "resting": 260,
            "idle": 130,
        }.get(state, ANIMATION_MS)
        multiplier = {
            "happy": 0.85,
            "neutral": 1.0,
            "sad": 1.18,
            "sob": 1.45,
        }.get(emotion, 1.0)
        return max(80, int(base * multiplier))

    @staticmethod
    def _state_label(state: str) -> str:
        labels = {
            "working": "working",
            "waiting": "waiting",
            "compacting": "compacting",
            "sleeping": "sleeping",
            "idle": "idle",
        }
        return labels.get(state, state)

    def _show_character_picker(self, session_id: str) -> None:
        # If picker already open, just raise it
        if self._picker_win is not None and self._picker_win.winfo_exists():
            self._picker_win.lift()
            self._picker_win.focus_set()
            return

        sessions = self.store.snapshot()
        target = next((s for s in sessions if s.session_id == session_id), None)
        if target is None:
            self._pending_picker_session = None
            return
        project = target.project_name
        chars = self.data_store.get_characters()

        win = tk.Toplevel(self.root)
        self._picker_win = win
        win.title(T("picker_title"))
        win.configure(bg="#111827")
        self._register_dialog(win)
        win.resizable(False, False)

        x, y = self._dialog_xy()
        height = max(200, 140 + len(chars) * 46)
        win.geometry(f"270x{height}+{x}+{y}")
        win.focus_set()

        tk.Label(win, text=T("picker_working_on"), fg="#64748b", bg="#111827",
                 font=("Microsoft YaHei UI", 8)).pack(pady=(14, 0))
        tk.Label(win, text=project, fg="#f8fafc", bg="#111827",
                 font=("Microsoft YaHei UI", 10, "bold")).pack(pady=(0, 8))

        def _close_picker() -> None:
            self._picker_win = None
            self._pending_picker_session = None
            if win.winfo_exists():
                win.destroy()

        def pick(char_id: str) -> None:
            self.store.assign_character(session_id, char_id)
            self.data_store.set_active_character(char_id)
            _close_picker()

        for char in chars:
            name = char.get("name", "?")
            level = char.get("level", 1)
            xp_cur = char.get("xp", 0) % self.xp_system.XP_PER_LEVEL
            filled = xp_cur * 6 // self.xp_system.XP_PER_LEVEL
            bar = "█" * filled + "░" * (6 - filled)
            cid = char["id"]
            tk.Button(win, text=f"{name}  Lv.{level}  {bar}",
                      command=lambda c=cid: pick(c),
                      bg="#1e293b", fg="#f8fafc", activebackground="#334155",
                      activeforeground="#f8fafc", relief="flat",
                      padx=10, pady=6, anchor="w",
                      font=("Microsoft YaHei UI", 9),
                      width=26).pack(fill="x", padx=14, pady=2)

        tk.Frame(win, height=1, bg="#334155").pack(fill="x", padx=14, pady=(6, 2))

        new_btn_frame = tk.Frame(win, bg="#111827")
        new_btn_frame.pack(fill="x", padx=14, pady=2)

        def show_create() -> None:
            for w in new_btn_frame.winfo_children():
                w.destroy()
            name_var = tk.StringVar()
            entry = tk.Entry(new_btn_frame, textvariable=name_var, bg="#0f172a",
                             fg="#f8fafc", insertbackground="#f8fafc", relief="flat",
                             font=("Microsoft YaHei UI", 9),
                             highlightthickness=1, highlightbackground="#334155")
            entry.pack(side="left", fill="x", expand=True, ipady=4)
            entry.focus_set()

            def create_and_pick() -> None:
                name = name_var.get().strip()
                if name:
                    char = self.data_store.add_character(name)
                    pick(char["id"])

            entry.bind("<Return>", lambda _: create_and_pick())
            tk.Button(new_btn_frame, text="OK", command=create_and_pick,
                      bg="#2563eb", fg="white", relief="flat",
                      padx=8, pady=4).pack(side="left", padx=(4, 0))

        tk.Button(new_btn_frame, text=T("picker_new_char"), command=show_create,
                  bg="#111827", fg="#475569", activebackground="#111827",
                  activeforeground="#64748b", relief="flat",
                  padx=10, pady=4,
                  font=("Microsoft YaHei UI", 8)).pack(anchor="w")

        def on_close() -> None:
            if chars:
                pick(chars[0]["id"])
            else:
                _close_picker()

        win.protocol("WM_DELETE_WINDOW", on_close)

    def _show_game_offer(self, level: int, char_id: str) -> None:
        char = self.data_store.get_character(char_id)
        if char is None:
            return
        win = tk.Toplevel(self.root)
        win.title(T("game_offer_title"))
        win.configure(bg="#111827")
        self._register_dialog(win)
        win.resizable(False, False)
        x, y = self._dialog_xy()
        win.geometry(f"320x150+{x}+{y}")

        tk.Label(win, text=T("game_offer_body_fmt").format(name=char.get("name", "Mascota"), level=level),
                 fg="#f8fafc", bg="#111827",
                 font=("Microsoft YaHei UI", 11, "bold")).pack(pady=(18, 4))
        tk.Label(win, text=T("game_offer_question"),
                 fg="#94a3b8", bg="#111827",
                 font=("Microsoft YaHei UI", 9)).pack(pady=(0, 14))

        btn_row = tk.Frame(win, bg="#111827")
        btn_row.pack()

        def play() -> None:
            win.destroy()
            self.open_mini_game(char_id)

        tk.Button(btn_row, text=T("game_offer_yes"),
                  command=play,
                  bg="#2563eb", fg="white",
                  activebackground="#1d4ed8", activeforeground="white",
                  relief="flat", padx=12, pady=6,
                  font=("Microsoft YaHei UI", 9)).pack(side="left", padx=(0, 8))
        tk.Button(btn_row, text=T("game_offer_no"),
                  command=win.destroy,
                  bg="#1f2937", fg="#cbd5e1",
                  activebackground="#374151", activeforeground="#f8fafc",
                  relief="flat", padx=12, pady=6,
                  font=("Microsoft YaHei UI", 9)).pack(side="left")

    def open_mini_game(self, char_id: str) -> None:
        char = self.data_store.get_character(char_id)
        if char is None:
            return
        house = self.data_store.get_house()
        def on_done() -> None:
            self.root.attributes("-topmost", True)
        MiniGame(self.root, char, house,
                 self.sprite_renderer, self.bg_renderer,
                 self.data_store, on_done)

    def _show_daily_greeting(self) -> None:
        today = time.strftime("%Y-%m-%d")
        self.data_store.set("greeted_date", today)

        win = tk.Toplevel(self.root)
        win.title(T("greeting_title"))
        win.configure(bg="#111827")
        self._register_dialog(win)
        win.resizable(False, False)

        x, y = self._dialog_xy()
        win.geometry(f"380x160+{x}+{y}")

        tk.Label(win, text=T("greeting_msg"),
                 fg="#f8fafc", bg="#111827",
                 font=("Microsoft YaHei UI", 13, "bold")).pack(pady=(18, 4))
        tk.Label(win, text=T("greeting_question"),
                 fg="#94a3b8", bg="#111827",
                 font=("Microsoft YaHei UI", 10)).pack(pady=(0, 14))

        btn_row = tk.Frame(win, bg="#111827")
        btn_row.pack()

        def open_alarms_and_close() -> None:
            win.destroy()
            self.open_alarms()

        tk.Button(btn_row, text=T("greeting_alarms_btn"),
                  command=open_alarms_and_close,
                  bg="#2563eb", fg="white",
                  activebackground="#1d4ed8", activeforeground="white",
                  relief="flat", padx=12, pady=6,
                  font=("Microsoft YaHei UI", 9)).pack(side="left", padx=(0, 8))
        tk.Button(btn_row, text=T("greeting_skip"),
                  command=win.destroy,
                  bg="#1f2937", fg="#cbd5e1",
                  activebackground="#374151", activeforeground="#f8fafc",
                  relief="flat", padx=12, pady=6,
                  font=("Microsoft YaHei UI", 9)).pack(side="left")

    def _show_first_use_popup(self) -> None:
        win = tk.Toplevel(self.root)
        win.title(T("welcome_title"))
        win.configure(bg="#111827")
        self._register_dialog(win)
        win.resizable(False, False)

        x, y = self._dialog_xy()
        win.geometry(f"280x190+{x}+{y}")
        win.grab_set()

        tk.Label(win, text=T("welcome_msg"), fg="#f8fafc", bg="#111827",
                 font=("Microsoft YaHei UI", 14, "bold")).pack(pady=(22, 4))
        tk.Label(win, text=T("welcome_name_prompt"), fg="#94a3b8",
                 bg="#111827", font=("Microsoft YaHei UI", 9)).pack(pady=(0, 8))

        name_var = tk.StringVar(value="Mascota")
        entry = tk.Entry(win, textvariable=name_var, bg="#0f172a", fg="#f8fafc",
                         insertbackground="#f8fafc", relief="flat",
                         font=("Microsoft YaHei UI", 11), justify="center",
                         highlightthickness=1, highlightbackground="#334155")
        entry.pack(padx=34, ipady=6, fill="x")
        entry.select_range(0, "end")
        entry.focus_set()

        def confirm() -> None:
            self.data_store.add_character(name_var.get())
            win.destroy()

        entry.bind("<Return>", lambda _: confirm())
        tk.Button(win, text=T("welcome_start"), command=confirm,
                  bg="#2563eb", fg="white", activebackground="#1d4ed8",
                  activeforeground="white", relief="flat",
                  padx=14, pady=6).pack(pady=14)

    def open_house_editor(self) -> None:
        if self.details_visible:
            self.toggle_details()

        # Auto-enable background so the user can see what they're editing
        if not self.bg_visible:
            self.bg_visible = True
            self.data_store.set("bg_visible", True)
            self.house_win.wm_attributes("-alpha", 1.0)
            if hasattr(self, "_bg_btn"):
                self._bg_btn.configure(bg="#1d4ed8", fg="white")

        current_level = self.xp_system.max_level()
        house = self.data_store.get_house()
        active_char = self.data_store.get_active_character() or {}

        win = tk.Toplevel(self.root)
        win.title(T("house_title"))
        win.configure(bg="#111827")
        self._register_dialog(win)
        win.resizable(False, True)

        self._house_win_open = True
        x, y = self._dialog_xy()
        win.geometry(f"480x480+{x}+{y}")

        # ── Header (fixed, outside scroll) ────────────────────────────────────
        hdr = tk.Frame(win, bg="#0f172a")
        hdr.pack(fill="x")
        tk.Label(hdr, text=T("house_title"), fg="#f8fafc", bg="#0f172a",
                 font=("Microsoft YaHei UI", 12, "bold")).pack(side="left", padx=14, pady=10)
        tk.Label(hdr, text=T("house_level_fmt").format(level=current_level), fg="#fbbf24", bg="#0f172a",
                 font=("Microsoft YaHei UI", 9)).pack(side="right", padx=14)

        # ── Scrollable body ────────────────────────────────────────────────────
        scroll_canvas = tk.Canvas(win, bg="#111827", highlightthickness=0)
        scrollbar = tk.Scrollbar(win, orient="vertical", command=scroll_canvas.yview)
        scroll_canvas.configure(yscrollcommand=scrollbar.set)
        # Close must be packed before the expanding canvas so it stays visible
        tk.Button(win, text=T("house_close"), command=win.destroy, bg="#1f2937", fg="#cbd5e1",
                  activebackground="#374151", activeforeground="#f8fafc",
                  relief="flat", padx=12, pady=4).pack(side="bottom", pady=8)

        scrollbar.pack(side="right", fill="y")
        scroll_canvas.pack(side="left", fill="both", expand=True)

        body = tk.Frame(scroll_canvas, bg="#111827")
        body_id = scroll_canvas.create_window((0, 0), window=body, anchor="nw")

        def _on_body_configure(_: Any) -> None:
            scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all"))

        def _on_canvas_configure(e: tk.Event) -> None:
            scroll_canvas.itemconfig(body_id, width=e.width)

        body.bind("<Configure>", _on_body_configure)
        scroll_canvas.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(e: tk.Event) -> None:
            scroll_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

        scroll_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        win.bind("<Destroy>", lambda e: (
            scroll_canvas.unbind_all("<MouseWheel>"),
            setattr(self, "_house_win_open", False),
        ) if e.widget is win else None)

        def section_label(text: str) -> None:
            tk.Label(body, text=text, fg="#64748b", bg="#111827",
                     font=("Microsoft YaHei UI", 8)).pack(anchor="w", padx=16, pady=(10, 3))

        def separator() -> None:
            tk.Frame(body, height=1, bg="#1e293b").pack(fill="x", padx=12, pady=(4, 0))

        # ── Fondo ─────────────────────────────────────────────────────────────
        separator()
        section_label(T("house_section_bg"))
        bg_frame = tk.Frame(body, bg="#111827")
        bg_frame.pack(fill="x", padx=14, pady=(0, 4))
        current_bg = [house.get("background", "oficina")]
        PER_ROW_BG = 3

        def refresh_bg_buttons() -> None:
            for w in bg_frame.winfo_children():
                w.destroy()
            row: tk.Frame | None = None
            for i, (key, label, min_lev) in enumerate(BG_THEMES):
                if i % PER_ROW_BG == 0:
                    row = tk.Frame(bg_frame, bg="#111827")
                    row.pack(anchor="w", pady=(0, 2))
                locked = current_level < min_lev
                selected = current_bg[0] == key
                def on_bg(k=key, lv=min_lev):
                    if current_level >= lv:
                        current_bg[0] = k
                        self.data_store.update_house(background=k)
                        self.bg_renderer.invalidate()
                        refresh_bg_buttons()
                bg_color = "#2563eb" if selected else ("#1e293b" if not locked else "#0f172a")
                fg_color = "white" if selected else ("#f8fafc" if not locked else "#334155")
                tlbl = TL(key, label)
                lbl = tlbl if not locked else f"{tlbl}\nLv.{min_lev}"
                tk.Button(row, text=lbl, command=on_bg, bg=bg_color, fg=fg_color,
                          activebackground="#1e293b", activeforeground="#f8fafc",
                          relief="flat", padx=6, pady=4, width=12,
                          font=("Microsoft YaHei UI", 8),
                          state="normal" if not locked else "disabled").pack(side="left", padx=2)

        refresh_bg_buttons()

        # ── Suelo ─────────────────────────────────────────────────────────────
        separator()
        section_label(T("house_section_floor"))
        grass_frame = tk.Frame(body, bg="#111827")
        grass_frame.pack(fill="x", padx=14, pady=(0, 4))
        current_grass = [house.get("grass_color", "verde")]

        PER_ROW_GRASS = 5

        def refresh_grass_buttons() -> None:
            for w in grass_frame.winfo_children():
                w.destroy()
            row: tk.Frame | None = None
            for i, (key, label, rgb) in enumerate(GRASS_COLORS):
                if i % PER_ROW_GRASS == 0:
                    row = tk.Frame(grass_frame, bg="#111827")
                    row.pack(anchor="w", pady=(0, 2))
                selected = current_grass[0] == key
                hex_col = "#{:02x}{:02x}{:02x}".format(*rgb)
                fg_col = "white" if sum(rgb) < 400 else "#111827"
                def on_grass(k=key):
                    current_grass[0] = k
                    self.data_store.update_house(grass_color=k)
                    self.bg_renderer.invalidate()
                    refresh_grass_buttons()
                border = "#2563eb" if selected else "#334155"
                btn_frame = tk.Frame(row, bg=border, padx=2, pady=2)
                btn_frame.pack(side="left", padx=3)
                tk.Button(btn_frame, text=TL(key, label), command=on_grass,
                          bg=hex_col, fg=fg_col,
                          activebackground=hex_col, activeforeground=fg_col,
                          relief="flat", padx=6, pady=3,
                          font=("Microsoft YaHei UI", 8)).pack()

        refresh_grass_buttons()

        # ── Decoraciones ──────────────────────────────────────────────────────
        separator()
        section_label(T("house_section_decs"))
        dec_frame = tk.Frame(body, bg="#111827")
        dec_frame.pack(fill="x", padx=14, pady=(0, 4))
        current_decs = list(house.get("decorations", []))

        def refresh_dec_buttons() -> None:
            for w in dec_frame.winfo_children():
                w.destroy()
            for key, label, min_lev in DECORATIONS:
                locked = current_level < min_lev
                active = key in current_decs
                def on_dec(k=key, lv=min_lev):
                    if current_level < lv:
                        return
                    if k in current_decs:
                        current_decs.remove(k)
                    else:
                        current_decs.append(k)
                    self.data_store.update_house(decorations=list(current_decs))
                    refresh_dec_buttons()
                check_char = "☑" if active else "☐"
                lock_txt = f"  (Lv.{min_lev})" if locked else ""
                btn_bg = "#1e293b" if (active and not locked) else "#111827"
                btn_fg = "#f8fafc" if not locked else "#334155"
                tk.Button(dec_frame, text=f"{check_char}  {TL(key, label)}{lock_txt}",
                          command=on_dec, bg=btn_bg, fg=btn_fg,
                          activebackground="#1e293b", activeforeground="#f8fafc",
                          relief="flat", anchor="w", padx=8, pady=3,
                          font=("Microsoft YaHei UI", 9),
                          state="normal" if not locked else "disabled").pack(fill="x", pady=1)

        refresh_dec_buttons()

        separator()
        tk.Label(body, text=T("house_char_hint"),
                 fg="#475569", bg="#111827",
                 font=("Microsoft YaHei UI", 8)).pack(anchor="w", padx=16, pady=(8, 10))

        tk.Frame(body, height=4, bg="#111827").pack()

    def open_character_editor(self) -> None:
        char = self.data_store.get_active_character()
        if char is None:
            return
        char_id = char["id"]
        current_level = char.get("level", 1)

        win = tk.Toplevel(self.root)
        win.title(T("char_title_fmt").format(name=char.get("name", "Mascota")))
        win.configure(bg="#111827")
        self._register_dialog(win)
        win.resizable(False, False)
        x, y = self._dialog_xy()
        win.geometry(f"320x480+{x}+{y}")


        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(win, bg="#0f172a")
        hdr.pack(fill="x")
        tk.Label(hdr, text=char.get("name", "Mascota"), fg="#f8fafc", bg="#0f172a",
                 font=("Microsoft YaHei UI", 12, "bold")).pack(side="left", padx=14, pady=10)
        tk.Label(hdr, text=f"Lv.{current_level}", fg="#fbbf24", bg="#0f172a",
                 font=("Microsoft YaHei UI", 10, "bold")).pack(side="right", padx=14)

        btn_row = tk.Frame(win, bg="#111827")
        btn_row.pack(side="bottom", pady=8)
        tk.Button(btn_row, text=T("char_close"), command=win.destroy, bg="#1f2937", fg="#cbd5e1",
                  activebackground="#374151", activeforeground="#f8fafc",
                  relief="flat", padx=12, pady=4).pack(side="left", padx=(0, 6))

        def confirm_delete() -> None:
            chars = self.data_store.get_characters()
            if len(chars) <= 1:
                messagebox.showwarning(T("char_delete_error_title"),
                                       T("char_delete_error_msg"), parent=win)
                return
            if messagebox.askyesno(T("char_delete_confirm_title"),
                                   T("char_delete_confirm_fmt").format(name=char.get("name", "?")),
                                   parent=win):
                self.data_store.delete_character(char_id)
                self.store.unassign_character_by_id(char_id)
                win.destroy()

        tk.Button(btn_row, text=T("char_delete"), command=confirm_delete,
                  bg="#1f2937", fg="#ef4444",
                  activebackground="#374151", activeforeground="#fca5a5",
                  relief="flat", padx=12, pady=4).pack(side="left")

        # ── Live preview ──────────────────────────────────────────────────────
        preview_frame = tk.Frame(win, bg="#1e293b", width=120, height=120)
        preview_frame.pack(pady=(10, 6))
        preview_frame.pack_propagate(False)
        preview_canvas = tk.Canvas(preview_frame, width=120, height=120,
                                   bg="#1e293b", highlightthickness=0)
        preview_canvas.pack()
        preview_ref: list[Any] = []  # keep image reference

        def refresh_preview() -> None:
            ch = self.data_store.get_active_character() or {}
            tint_key = ch.get("tint", "original")
            tint_rgb = next((t[2] for t in MASCOT_TINTS if t[0] == tint_key), None)
            outline_key = ch.get("outline", "ninguno")
            outline_rgb = next((o[2] for o in OUTLINE_OPTIONS if o[0] == outline_key), None)
            float_key = ch.get("floating_item", "ninguno")
            sprite_set = ch.get("sprite_set", "Dino")
            preview_scale = 2.2 * SPRITE_SET_SCALE_DEFAULTS.get(ch.get("sprite_set", "Dino"), 1.0)
            sprite = self.sprite_renderer.get_frame(
                "idle", "happy", 0, scale=preview_scale, tint=tint_rgb, outline_rgb=outline_rgb,
                sprite_set=sprite_set,
            )
            preview_canvas.delete("all")
            preview_canvas.create_image(60, 70, image=sprite, anchor="center")
            preview_ref.clear()
            preview_ref.append(sprite)
            float_img = self.float_renderer.get(float_key, 2.2)
            if float_img is not None:
                item_y = 70 - sprite.height() // 2 - float_img.height() // 2 - 3
                preview_canvas.create_image(60, max(6, item_y), image=float_img, anchor="center")
                preview_ref.append(float_img)

        # ── Scrollable body ───────────────────────────────────────────────────
        scroll_canvas = tk.Canvas(win, bg="#111827", highlightthickness=0)
        scrollbar = tk.Scrollbar(win, orient="vertical", command=scroll_canvas.yview)
        scroll_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        scroll_canvas.pack(side="left", fill="both", expand=True)
        body = tk.Frame(scroll_canvas, bg="#111827")
        body_id = scroll_canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda _: scroll_canvas.configure(
            scrollregion=scroll_canvas.bbox("all")))
        scroll_canvas.bind("<Configure>", lambda e: scroll_canvas.itemconfig(
            body_id, width=e.width))
        scroll_canvas.bind_all("<MouseWheel>",
            lambda e: scroll_canvas.yview_scroll(int(-1 * e.delta / 120), "units"))
        win.bind("<Destroy>", lambda _: scroll_canvas.unbind_all("<MouseWheel>"))

        def section_label(text: str) -> None:
            tk.Frame(body, height=1, bg="#1e293b").pack(fill="x", padx=12, pady=(6, 0))
            tk.Label(body, text=text, fg="#64748b", bg="#111827",
                     font=("Microsoft YaHei UI", 8)).pack(anchor="w", padx=16, pady=(4, 2))

        def make_option_row(options: list[tuple], get_key: Any,
                            on_select: Any, cols: int = 4) -> None:
            frame = tk.Frame(body, bg="#111827")
            frame.pack(fill="x", padx=14, pady=(0, 4))
            for i, opt in enumerate(options):
                key, label = opt[0], opt[1]
                color = opt[2] if len(opt) > 2 else None

                def make_cb(k: str) -> Any:
                    def cb() -> None:
                        on_select(k)
                        refresh_buttons()
                        refresh_preview()
                    return cb

                sel = get_key() == key
                bg = "#2563eb" if sel else "#1f2937"
                fg = "white" if sel else "#cbd5e1"
                if color is not None:
                    hex_col = "#{:02x}{:02x}{:02x}".format(*color)
                    btn = tk.Button(frame, text=label, command=make_cb(key),
                                    bg=hex_col, fg="white",
                                    activebackground=hex_col, activeforeground="white",
                                    relief="flat", padx=5, pady=3,
                                    font=("Microsoft YaHei UI", 8),
                                    highlightbackground="#2563eb" if sel else hex_col,
                                    highlightthickness=2 if sel else 0)
                else:
                    btn = tk.Button(frame, text=label, command=make_cb(key),
                                    bg=bg, fg=fg, activebackground="#1e293b",
                                    activeforeground="#f8fafc", relief="flat",
                                    padx=6, pady=3, font=("Microsoft YaHei UI", 8))
                btn.grid(row=i // cols, column=i % cols, padx=2, pady=2, sticky="ew")
            for c in range(cols):
                frame.columnconfigure(c, weight=1)

        refresh_refs: list[Any] = []

        def refresh_buttons() -> None:
            for w in body.winfo_children():
                w.destroy()
            ch = self.data_store.get_active_character() or {}

            # Sprite set
            section_label(T("char_section_sprite"))
            available = self.sprite_renderer.available_sets()
            make_option_row(
                [(s, s) for s in available],
                lambda: (self.data_store.get_active_character() or {}).get("sprite_set", "Dino"),
                lambda k: (self.data_store.update_active_character(
                               char_id=char_id, sprite_set=k,
                               scale_multiplier=SPRITE_SET_SCALE_DEFAULTS.get(k, 1.0)),
                           self.sprite_renderer.invalidate()),
                cols=3,
            )

            # Tinte
            section_label(T("char_section_color"))
            make_option_row(
                _xlate_opts([(k, l, rgb) for k, l, rgb, _ in MASCOT_TINTS if rgb is not None or k == "original"]),
                lambda: (self.data_store.get_active_character() or {}).get("tint", "original"),
                lambda k: (self.data_store.update_active_character(char_id=char_id, tint=k),
                           self.sprite_renderer.invalidate()),
                cols=3,
            )

            # Contorno
            section_label(T("char_section_outline"))
            make_option_row(
                _xlate_opts(OUTLINE_OPTIONS),
                lambda: (self.data_store.get_active_character() or {}).get("outline", "ninguno"),
                lambda k: (self.data_store.update_active_character(char_id=char_id, outline=k),
                           self.sprite_renderer.invalidate()),
                cols=4,
            )

            # Objeto flotante
            section_label(T("char_section_float"))
            tk.Label(body, text=T("char_float_hint"),
                     fg="#475569", bg="#111827",
                     font=("Microsoft YaHei UI", 7)).pack(anchor="w", padx=16)
            make_option_row(
                _xlate_opts(FLOATING_ITEMS),
                lambda: (self.data_store.get_active_character() or {}).get("floating_item", "ninguno"),
                lambda k: self.data_store.update_active_character(char_id=char_id, floating_item=k),
                cols=4,
            )

            tk.Frame(body, height=8, bg="#111827").pack()

        refresh_buttons()
        refresh_preview()

    def open_alarms(self) -> None:
        win = tk.Toplevel(self.root)
        win.title(T("alarms_title"))
        win.configure(bg="#111827")
        self._register_dialog(win)
        win.resizable(False, True)

        x, y = self._dialog_xy()
        win.geometry(f"380x460+{x}+{y}")

        # ── Header ────────────────────────────────────────────────
        hdr = tk.Frame(win, bg="#0f172a")
        hdr.pack(fill="x")
        today_str = time.strftime("%A %d/%m/%Y")
        tk.Label(hdr, text=T("alarms_header"), fg="#f8fafc", bg="#0f172a",
                 font=("Microsoft YaHei UI", 12, "bold")).pack(side="left", padx=14, pady=10)
        tk.Label(hdr, text=today_str, fg="#64748b", bg="#0f172a",
                 font=("Microsoft YaHei UI", 9)).pack(side="right", padx=14)

        # ── Tab bar ───────────────────────────────────────────────
        tab_bar = tk.Frame(win, bg="#0f172a")
        tab_bar.pack(fill="x")
        tk.Frame(tab_bar, height=1, bg="#334155").pack(fill="x", side="bottom")

        tab_alarm_btn = tk.Button(tab_bar, text=T("alarms_tab_alarms"), relief="flat",
                                  bg="#0f172a", fg="#fbbf24", padx=14, pady=7,
                                  font=("Microsoft YaHei UI", 9, "bold"),
                                  activebackground="#111827", activeforeground="#fbbf24",
                                  bd=0, highlightthickness=0)
        tab_alarm_btn.pack(side="left")
        tab_break_btn = tk.Button(tab_bar, text=T("alarms_tab_breaks"), relief="flat",
                                  bg="#0f172a", fg="#64748b", padx=14, pady=7,
                                  font=("Microsoft YaHei UI", 9),
                                  activebackground="#111827", activeforeground="#94a3b8",
                                  bd=0, highlightthickness=0)
        tab_break_btn.pack(side="left")

        # ── Content area ──────────────────────────────────────────
        content = tk.Frame(win, bg="#111827")
        content.pack(fill="both", expand=True)

        # ── Alarmas tab ───────────────────────────────────────────
        alarm_tab = tk.Frame(content, bg="#111827")

        add_frame = tk.Frame(alarm_tab, bg="#0f172a")
        add_frame.pack(side="bottom", fill="x")
        tk.Frame(add_frame, height=1, bg="#334155").pack(fill="x")
        add_inner = tk.Frame(add_frame, bg="#0f172a")
        add_inner.pack(fill="x", padx=10, pady=8)
        tk.Label(add_inner, text=T("alarms_add_label"), fg="#64748b", bg="#0f172a",
                 font=("Microsoft YaHei UI", 8)).pack(anchor="w", pady=(0, 4))

        input_row = tk.Frame(add_inner, bg="#0f172a")
        input_row.pack(fill="x")

        hour_var = tk.StringVar(value="09")
        minute_var = tk.StringVar(value="00")
        label_var = tk.StringVar()

        tk.Label(input_row, text="H:", fg="#94a3b8", bg="#0f172a",
                 font=("Microsoft YaHei UI", 9)).pack(side="left")
        tk.Spinbox(input_row, from_=0, to=23, textvariable=hour_var,
                   format="%02.0f", width=3,
                   bg="#1e293b", fg="#f8fafc", insertbackground="#f8fafc",
                   relief="flat", font=("Microsoft YaHei UI", 10),
                   buttonbackground="#334155").pack(side="left", padx=(2, 6))

        tk.Label(input_row, text="M:", fg="#94a3b8", bg="#0f172a",
                 font=("Microsoft YaHei UI", 9)).pack(side="left")
        tk.Spinbox(input_row,
                   values=["00", "05", "10", "15", "20", "25", "30",
                            "35", "40", "45", "50", "55"],
                   textvariable=minute_var, width=3,
                   bg="#1e293b", fg="#f8fafc", insertbackground="#f8fafc",
                   relief="flat", font=("Microsoft YaHei UI", 10),
                   buttonbackground="#334155").pack(side="left", padx=(2, 8))

        label_entry = tk.Entry(input_row, textvariable=label_var,
                               bg="#1e293b", fg="#f8fafc",
                               insertbackground="#f8fafc",
                               relief="flat", font=("Microsoft YaHei UI", 9),
                               highlightthickness=1, highlightbackground="#334155",
                               width=14)
        label_entry.pack(side="left", ipady=4, padx=(0, 6))
        _placeholder = T("alarms_placeholder")
        label_entry.insert(0, _placeholder)

        def _clear_placeholder(e: Any) -> None:
            if label_var.get() == _placeholder:
                label_entry.delete(0, "end")
        label_entry.bind("<FocusIn>", _clear_placeholder)

        def add_alarm_action() -> None:
            h = str(hour_var.get()).zfill(2)
            m = str(minute_var.get()).zfill(2)
            lbl = label_var.get().strip()
            if not lbl or lbl == _placeholder:
                lbl = T("alarms_default_lbl")
            self.alarm_system.add_alarm(
                lbl, f"{h}:{m}",
                parse_days_of_month(days_var.get()),
                repeat=repeat_var.get(),
                days_of_week=[i for i, v in enumerate(weekday_vars) if v.get()])
            label_var.set(_placeholder)
            days_var.set("")
            for v in weekday_vars:
                v.set(False)
            refresh_list()

        tk.Button(input_row, text=T("alarms_add_btn"), command=add_alarm_action,
                  bg="#2563eb", fg="white",
                  activebackground="#1d4ed8", activeforeground="white",
                  relief="flat", padx=8, pady=4,
                  font=("Microsoft YaHei UI", 9)).pack(side="left")

        # How often it repeats, on its own row: the row above is already full, and this
        # is the field that decides whether the alarm is still there tomorrow, so it is
        # written down instead of guessed from an empty box.
        repeat_var = tk.StringVar(value=REPEAT_DAILY)
        repeat_row = tk.Frame(add_inner, bg="#0f172a")
        repeat_row.pack(fill="x", pady=(6, 0))
        tk.Label(repeat_row, text=T("alarms_repeat_label"), fg="#64748b", bg="#0f172a",
                 font=("Microsoft YaHei UI", 8)).pack(side="left")

        # Only the row that the chosen mode needs is shown, so there is never a box on
        # screen that does nothing.
        detail_row = tk.Frame(add_inner, bg="#0f172a")
        detail_row.pack(fill="x", pady=(4, 0))

        # Weekday toggles, Monday first to match time.struct_time.tm_wday.
        week_frame = tk.Frame(detail_row, bg="#0f172a")
        _letters = T("alarms_weekday_letters")
        weekday_vars: list[tk.BooleanVar] = []
        for _i in range(7):
            _v = tk.BooleanVar(value=False)
            weekday_vars.append(_v)
            tk.Checkbutton(week_frame, text=_letters[_i:_i + 1] or str(_i + 1),
                           variable=_v, indicatoron=False, width=2,
                           bg="#1e293b", fg="#94a3b8", selectcolor="#2563eb",
                           activebackground="#334155", activeforeground="#f8fafc",
                           relief="flat", borderwidth=0, highlightthickness=0,
                           font=("Microsoft YaHei UI", 8)).pack(side="left", padx=1)

        dom_frame = tk.Frame(detail_row, bg="#0f172a")
        days_var = tk.StringVar()
        tk.Label(dom_frame, text=T("alarms_days_label"), fg="#64748b", bg="#0f172a",
                 font=("Microsoft YaHei UI", 8)).pack(side="left")
        days_entry = tk.Entry(dom_frame, textvariable=days_var, width=8,
                              bg="#1e293b", fg="#f8fafc",
                              insertbackground="#f8fafc",
                              relief="flat", font=("Microsoft YaHei UI", 9),
                              highlightthickness=1, highlightbackground="#334155")
        days_entry.pack(side="left", ipady=3, padx=(6, 0))
        tk.Label(dom_frame, text=T("alarms_days_hint"), fg="#475569", bg="#0f172a",
                 font=("Microsoft YaHei UI", 8)).pack(side="left", padx=(6, 0))

        def _sync_detail() -> None:
            week_frame.pack_forget()
            dom_frame.pack_forget()
            mode = repeat_var.get()
            if mode == REPEAT_WEEKLY:
                week_frame.pack(side="left")
            elif mode == REPEAT_MONTHLY:
                dom_frame.pack(side="left")

        for _mode, _key in ((REPEAT_ONCE, "alarms_repeat_once"),
                            (REPEAT_DAILY, "alarms_repeat_daily"),
                            (REPEAT_WEEKLY, "alarms_repeat_weekly"),
                            (REPEAT_MONTHLY, "alarms_repeat_monthly")):
            tk.Radiobutton(repeat_row, text=T(_key), variable=repeat_var, value=_mode,
                           command=_sync_detail,
                           bg="#0f172a", fg="#94a3b8", selectcolor="#1e293b",
                           activebackground="#0f172a", activeforeground="#f8fafc",
                           borderwidth=0, highlightthickness=0,
                           font=("Microsoft YaHei UI", 8)).pack(side="left", padx=(6, 0))
        _sync_detail()

        label_entry.bind("<Return>", lambda _e: add_alarm_action())
        days_entry.bind("<Return>", lambda _e: add_alarm_action())

        scroll_canvas = tk.Canvas(alarm_tab, bg="#111827", highlightthickness=0)
        scrollbar = tk.Scrollbar(alarm_tab, orient="vertical", command=scroll_canvas.yview)
        scroll_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        scroll_canvas.pack(side="left", fill="both", expand=True)

        list_frame = tk.Frame(scroll_canvas, bg="#111827")
        list_id = scroll_canvas.create_window((0, 0), window=list_frame, anchor="nw")

        list_frame.bind("<Configure>", lambda _e: scroll_canvas.configure(
            scrollregion=scroll_canvas.bbox("all")))
        scroll_canvas.bind("<Configure>", lambda e: scroll_canvas.itemconfig(
            list_id, width=e.width))
        scroll_canvas.bind_all("<MouseWheel>",
            lambda e: scroll_canvas.yview_scroll(int(-1 * e.delta / 120), "units"))
        win.bind("<Destroy>", lambda e: scroll_canvas.unbind_all("<MouseWheel>")
                 if e.widget is win else None)

        def refresh_list() -> None:
            for w in list_frame.winfo_children():
                w.destroy()
            alarms = self.alarm_system.get_alarms()
            today = time.strftime("%Y-%m-%d")
            if not alarms:
                tk.Label(list_frame, text=T("alarms_empty"),
                         fg="#475569", bg="#111827",
                         font=("Microsoft YaHei UI", 9)).pack(pady=20)
                return
            for alarm in alarms:
                row = tk.Frame(list_frame, bg="#1e293b",
                               highlightthickness=1, highlightbackground="#334155")
                row.pack(fill="x", padx=10, pady=3, ipady=4)

                triggered = alarm.get("triggered_date") == today
                snoozed = time.time() < float(alarm.get("snooze_until", 0.0))
                enabled = alarm.get("enabled", True)

                time_lbl = alarm.get("time", "--:--")
                if triggered:
                    time_lbl = "✓ " + time_lbl
                time_color = "#94a3b8" if (not enabled or triggered) else "#fbbf24"
                tk.Label(row, text=time_lbl, fg=time_color, bg="#1e293b",
                         font=("Microsoft YaHei UI", 10, "bold"),
                         width=8, anchor="w").pack(side="left", padx=(8, 4))

                # Every alarm gets a badge now, one-offs included: an alarm that will be
                # gone tomorrow has to say so while you can still change it.
                mode = alarm_repeat(alarm)
                if mode == REPEAT_MONTHLY:
                    days = alarm.get("days_of_month") or []
                    badge = f"{T('alarms_days_badge')} {','.join(str(d) for d in days)}"
                elif mode == REPEAT_WEEKLY:
                    letters = T("alarms_weekday_letters")
                    badge = ",".join(letters[d:d + 1] or str(d + 1)
                                     for d in (alarm.get("days_of_week") or []))
                elif mode == REPEAT_DAILY:
                    badge = T("alarms_badge_daily")
                else:
                    badge = T("alarms_badge_once")
                tk.Label(row, text=badge,
                         fg="#64748b" if (not enabled or triggered) else "#38bdf8",
                         bg="#1e293b", font=("Microsoft YaHei UI", 8),
                         anchor="w").pack(side="left", padx=(0, 4))

                lbl_text = alarm.get("label", "")
                if snoozed:
                    lbl_text = f"💤 {lbl_text}"
                lbl_color = "#475569" if (not enabled or triggered) else "#e2e8f0"
                tk.Label(row, text=lbl_text, fg=lbl_color, bg="#1e293b",
                         font=("Microsoft YaHei UI", 9),
                         anchor="w").pack(side="left", fill="x", expand=True, padx=4)

                toggle_text = "ON" if enabled else "OFF"
                toggle_bg = "#064e3b" if enabled else "#1f2937"
                toggle_fg = "#34d399" if enabled else "#64748b"
                tk.Button(row, text=toggle_text,
                          command=lambda aid=alarm["id"]: (
                              self.alarm_system.toggle_alarm(aid), refresh_list()),
                          bg=toggle_bg, fg=toggle_fg,
                          activebackground="#1e293b", activeforeground="#f8fafc",
                          relief="flat", padx=6, pady=2,
                          font=("Microsoft YaHei UI", 8)).pack(side="right", padx=(0, 4))

                tk.Button(row, text="✕",
                          command=lambda aid=alarm["id"]: (
                              self.alarm_system.remove_alarm(aid), refresh_list()),
                          bg="#1f2937", fg="#ef4444",
                          activebackground="#374151", activeforeground="#fca5a5",
                          relief="flat", padx=6, pady=2,
                          font=("Microsoft YaHei UI", 8)).pack(side="right", padx=(0, 2))

        refresh_list()

        # ── Descansos tab ─────────────────────────────────────────
        break_tab = tk.Frame(content, bg="#111827")

        def brk_section(text: str) -> None:
            tk.Label(break_tab, text=text, fg="#64748b", bg="#111827",
                     font=("Microsoft YaHei UI", 8)).pack(anchor="w", padx=16, pady=(14, 2))

        def brk_row() -> tk.Frame:
            f = tk.Frame(break_tab, bg="#111827")
            f.pack(anchor="w", padx=24, pady=2)
            return f

        def brk_menu(parent: tk.Frame, var: tk.StringVar, options: list[str]) -> tk.OptionMenu:
            m = tk.OptionMenu(parent, var, *options)
            m.configure(bg="#0f172a", fg="#f8fafc", activebackground="#1e293b",
                        activeforeground="#f8fafc", relief="flat", bd=0,
                        highlightthickness=0, padx=6)
            m["menu"].configure(bg="#0f172a", fg="#f8fafc", activebackground="#1e293b")
            return m

        brk_section(T("alarms_break_section"))
        break_var = tk.BooleanVar(value=bool(self.data_store.get("break_enabled")))
        def on_break(*_: Any) -> None:
            self.data_store.set("break_enabled", break_var.get())
        tk.Checkbutton(break_tab, text=T("alarms_break_enabled"),
                       variable=break_var, command=on_break,
                       bg="#111827", fg="#f8fafc", activebackground="#111827",
                       activeforeground="#f8fafc", selectcolor="#0f172a",
                       relief="flat").pack(anchor="w", padx=24)

        interval_map = {"15 min": 15, "30 min": 30, "50 min": 50, "90 min": 90}
        cur_min = int(self.data_store.get("break_interval_minutes"))
        interval_var = tk.StringVar(value=f"{cur_min} min")
        def on_interval(*_: Any) -> None:
            self.data_store.set("break_interval_minutes", interval_map.get(interval_var.get(), 50))
        interval_var.trace_add("write", on_interval)
        r1 = brk_row()
        tk.Label(r1, text=T("alarms_interval_label"), fg="#cbd5e1", bg="#111827",
                 font=("Microsoft YaHei UI", 9)).pack(side="left")
        brk_menu(r1, interval_var, list(interval_map.keys())).pack(side="left", padx=(6, 0))

        duration_map = {"3 min": 3, "5 min": 5, "10 min": 10, "15 min": 15}
        cur_dur = int(self.data_store.get("break_duration_minutes"))
        closest_dur = min(duration_map, key=lambda k: abs(duration_map[k] - cur_dur))
        duration_var = tk.StringVar(value=closest_dur)
        def on_duration(*_: Any) -> None:
            self.data_store.set("break_duration_minutes", duration_map.get(duration_var.get(), 5))
        duration_var.trace_add("write", on_duration)
        r_dur = brk_row()
        tk.Label(r_dur, text=T("alarms_duration_label"), fg="#cbd5e1", bg="#111827",
                 font=("Microsoft YaHei UI", 9)).pack(side="left")
        brk_menu(r_dur, duration_var, list(duration_map.keys())).pack(side="left", padx=(6, 0))

        # ── Tab switching ─────────────────────────────────────────
        def show_alarm_tab() -> None:
            break_tab.pack_forget()
            alarm_tab.pack(fill="both", expand=True)
            tab_alarm_btn.configure(bg="#111827", fg="#fbbf24", font=("Microsoft YaHei UI", 9, "bold"))
            tab_break_btn.configure(bg="#0f172a", fg="#64748b", font=("Microsoft YaHei UI", 9))

        def show_break_tab() -> None:
            alarm_tab.pack_forget()
            break_tab.pack(fill="both", expand=True)
            tab_break_btn.configure(bg="#111827", fg="#94a3b8", font=("Microsoft YaHei UI", 9, "bold"))
            tab_alarm_btn.configure(bg="#0f172a", fg="#64748b", font=("Microsoft YaHei UI", 9))

        tab_alarm_btn.configure(command=show_alarm_tab)
        tab_break_btn.configure(command=show_break_tab)

        show_alarm_tab()

        # ── Close button ──────────────────────────────────────────
        tk.Button(win, text=T("alarms_close"), command=win.destroy,
                  bg="#1f2937", fg="#cbd5e1",
                  activebackground="#374151", activeforeground="#f8fafc",
                  relief="flat", padx=12, pady=4).pack(side="bottom", pady=8)

    def open_settings(self) -> None:
        win = tk.Toplevel(self.root)
        win.title(T("settings_title"))
        win.configure(bg="#111827")
        self._register_dialog(win)
        win.resizable(False, False)

        x, y = self._dialog_xy()
        win.geometry(f"270x390+{x}+{y}")

        def section(text: str) -> None:
            tk.Label(win, text=text, fg="#64748b", bg="#111827",
                     font=("Microsoft YaHei UI", 8)).pack(anchor="w", padx=16, pady=(12, 2))

        def row_frame() -> tk.Frame:
            f = tk.Frame(win, bg="#111827")
            f.pack(anchor="w", padx=24, pady=2)
            return f

        def styled_menu(parent: tk.Frame, var: tk.StringVar, options: list[str]) -> tk.OptionMenu:
            m = tk.OptionMenu(parent, var, *options)
            m.configure(bg="#0f172a", fg="#f8fafc", activebackground="#1e293b",
                        activeforeground="#f8fafc", relief="flat", bd=0,
                        highlightthickness=0, padx=6)
            m["menu"].configure(bg="#0f172a", fg="#f8fafc", activebackground="#1e293b")
            return m

        # Language
        section(T("settings_lang_section"))
        lang_map = {"English": "en", "Español": "es"}
        cur_lang_key = next((k for k, v in lang_map.items() if v == _LANG), "English")
        lang_var = tk.StringVar(value=cur_lang_key)
        def on_lang(*_: Any) -> None:
            global _LANG
            new_lang = lang_map.get(lang_var.get(), "en")
            _LANG = new_lang
            self.data_store.set("language", new_lang)
        lang_var.trace_add("write", on_lang)
        r_lang = row_frame()
        styled_menu(r_lang, lang_var, list(lang_map.keys())).pack(side="left")

        # XP
        section(T("settings_xp_section"))
        _char = self.data_store.get_active_character()
        xp_var = tk.BooleanVar(value=bool(_char.get("xp_enabled", True) if _char else True))
        def on_xp(*_: Any) -> None:
            self.data_store.update_active_character(xp_enabled=xp_var.get())
        tk.Checkbutton(win, text=T("settings_xp_enabled"), variable=xp_var, command=on_xp,
                       bg="#111827", fg="#f8fafc", activebackground="#111827",
                       activeforeground="#f8fafc", selectcolor="#0f172a",
                       relief="flat").pack(anchor="w", padx=24)

        # Hook de Claude Code
        section(T("settings_claude_section"))
        def reinstall_hook() -> None:
            ok, msg = self.installer.install()
            if ok:
                messagebox.showinfo(T("hook_installed_title"), msg, parent=win)
            else:
                messagebox.showerror(T("hook_error_title"), msg, parent=win)
        hook_ok = self.installer.is_installed()
        hook_status = T("settings_hook_status_ok") if hook_ok else T("settings_hook_status_no")
        tk.Label(win, text=f"Estado: {hook_status}",
                 fg="#3fb950" if hook_ok else "#f85149",
                 bg="#111827", font=("Microsoft YaHei UI", 8)).pack(anchor="w", padx=24)
        tk.Button(win, text=T("settings_hook_install_btn"),
                  command=reinstall_hook,
                  bg="#1f2937", fg="#cbd5e1",
                  activebackground="#374151", activeforeground="#f8fafc",
                  relief="flat", padx=8, pady=4).pack(anchor="w", padx=24, pady=(2, 0))

        # Hook de Codex
        section(T("settings_codex_section"))
        def reinstall_codex_hook() -> None:
            ok, msg = self.codex_installer.install()
            if ok:
                messagebox.showinfo(T("hook_installed_title"), msg, parent=win)
            else:
                messagebox.showerror(T("hook_error_title"), msg, parent=win)
        codex_ok = self.codex_installer.is_installed()
        codex_status = T("settings_hook_status_ok") if codex_ok else T("settings_hook_status_no")
        codex_available = (Path.home() / ".codex").exists()
        codex_hint = "" if codex_available else T("codex_not_detected")
        tk.Label(win, text=f"Estado: {codex_status}{codex_hint}",
                 fg="#3fb950" if codex_ok else "#f85149",
                 bg="#111827", font=("Microsoft YaHei UI", 8)).pack(anchor="w", padx=24)
        tk.Button(win, text=T("settings_hook_install_btn"),
                  command=reinstall_codex_hook,
                  bg="#1f2937", fg="#cbd5e1",
                  activebackground="#374151", activeforeground="#f8fafc",
                  relief="flat", padx=8, pady=4).pack(anchor="w", padx=24, pady=(2, 0))

        # Acceso directo / Shortcut
        section(T("settings_shortcut_section"))
        def create_shortcut() -> None:
            vbs_src = self.base_dir / "Iniciar Mascota.vbs"
            if not vbs_src.exists():
                messagebox.showerror(T("hook_error_title"), T("shortcut_err_no_vbs"), parent=win)
                return
            desktop = Path.home() / "Desktop"
            if not desktop.exists():
                desktop = Path.home() / "OneDrive" / "Escritorio"
            if not desktop.exists():
                desktop = Path.home() / "OneDrive" / "Desktop"
            if not desktop.exists():
                messagebox.showerror(T("hook_error_title"), T("shortcut_err_no_desktop"), parent=win)
                return
            try:
                shutil.copy(str(vbs_src), str(desktop / "Iniciar Mascota.vbs"))
                messagebox.showinfo(T("shortcut_ok_title"),
                                    T("shortcut_ok_fmt").format(path=desktop), parent=win)
            except Exception as exc:
                messagebox.showerror(T("hook_error_title"), str(exc), parent=win)

        tk.Button(win, text=T("settings_shortcut_btn"),
                  command=create_shortcut,
                  bg="#1f2937", fg="#cbd5e1",
                  activebackground="#374151", activeforeground="#f8fafc",
                  relief="flat", padx=8, pady=4).pack(anchor="w", padx=24, pady=(2, 0))

        tk.Button(win, text=T("settings_close"), command=win.destroy, bg="#1f2937", fg="#cbd5e1",
                  activebackground="#374151", activeforeground="#f8fafc",
                  relief="flat", padx=12, pady=4).pack(side="bottom", pady=10)

    def run(self) -> None:
        self.server_thread.start()
        self.render()
        self.animate()
        self.root.mainloop()

    def _register_dialog(self, win: tk.Toplevel) -> None:
        win.attributes("-topmost", True)
        win.lift()

    def _dialog_xy(self) -> tuple[int, int]:
        self.root.update_idletasks()
        return self.root.winfo_x(), self.root.winfo_y() + self.root.winfo_height() + 4

    def shutdown(self) -> None:
        self.data_store.set("window_x", self.root.winfo_x())
        self.data_store.set("window_y", self.root.winfo_y())
        self.server.shutdown()
        self.server.server_close()
        if self.instance_mutex:
            ctypes.windll.kernel32.CloseHandle(self.instance_mutex)
        for _w in [self.house_win, self.sprite_shield]:
            try:
                _w.destroy()
            except Exception:
                pass
        self.root.destroy()


if __name__ == "__main__":
    app = MascotaApp()
    app.run()
