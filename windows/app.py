from __future__ import annotations

import json
import math
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


APP_HOST = "127.0.0.1"
APP_PORT = 8765
APP_MUTEX_NAME = "Local\\NotchiWindowsSingleton"
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


class DataStore:
    _DEFAULTS: dict[str, Any] = {
        "window_x": -1,
        "window_y": -1,
        "opacity": 1.0,
        "break_enabled": True,
        "break_interval_minutes": 50,
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
    }

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, Any] = dict(self._DEFAULTS)
        self._path = Path.home() / ".notchi" / "notchi_data.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
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
                "name": "Notchi",
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
                "name": name.strip() or "Notchi",
                "xp": 0,
                "level": 1,
                "xp_enabled": True,
                "tint": "original",
                "outline": "ninguno",
                "floating_item": "ninguno",
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


class XPSystem:
    XP_PER_LEVEL = 100

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
            self._level_up_callback(new_level)

    def get_level(self) -> int:
        char = self._store.get_active_character()
        return char.get("level", 1) if char else 1

    def get_xp(self) -> int:
        char = self._store.get_active_character()
        return char.get("xp", 0) if char else 0

    def get_name(self) -> str:
        char = self._store.get_active_character()
        return char.get("name", "Notchi") if char else "Notchi"

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
        return f"{name}  Lv.{level}  {bar}  {current}/{self.XP_PER_LEVEL}"


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

    def is_enabled(self) -> bool:
        return bool(self._store.get("break_enabled"))

    def interval_seconds(self) -> float:
        return float(self._store.get("break_interval_minutes")) * 60.0

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

            if event_name == "UserPromptSubmit":
                prompt = (payload.get("user_prompt") or "").strip()
                if prompt:
                    session.last_prompt = prompt[:120]
                    EmotionAnalyzer.update_session_emotion(session, prompt, source="prompt")
                session.messages = []
                session.state = "working"
                session.current_tool = ""
                self._parser.mark_current_position(session_id, session.cwd)
            elif event_name == "PreToolUse":
                session.state = "working"
                session.current_tool = tool
            elif event_name == "PermissionRequest":
                session.state = "waiting"
                session.current_tool = tool
            elif event_name == "PreCompact":
                session.state = "compacting"
            elif event_name in {"PostToolUse", "Stop", "SubagentStop"}:
                if event_name in {"Stop", "SubagentStop"} or status == "waiting_for_input":
                    session.state = "idle"
                    session.current_tool = ""
                    if event_name in {"Stop", "SubagentStop"} and self._xp_system is not None:
                        self._xp_system.add_xp(10, char_id=session.character_id)
                new_messages = self._parser.parse_incremental(session_id, session.cwd)
            elif event_name == "SessionStart":
                session.state = "working" if status != "waiting_for_input" else "idle"
            elif event_name == "SessionEnd":
                if self._xp_system is not None:
                    self._xp_system.add_xp(5, char_id=session.character_id)
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
        self.installed_hook = self.hooks_dir / "notchi-hook.ps1"

    def install(self) -> tuple[bool, str]:
        if not self.claude_dir.exists():
            return False, f"Claude config directory not found: {self.claude_dir}"

        self.hooks_dir.mkdir(parents=True, exist_ok=True)
        hook_source = self.app_dir / "notchi-hook.ps1"
        hook_text = hook_source.read_text(encoding="utf-8")
        hook_text = hook_text.replace("__NOTCHI_APP_DIR__", str(self.app_dir))
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
            if not any(self._contains_notchi_hook(item) for item in existing):
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
            self._contains_notchi_hook(item)
            for event_entries in hooks.values()
            for item in event_entries
        )

    @staticmethod
    def _contains_notchi_hook(entry: dict[str, Any]) -> bool:
        for hook in entry.get("hooks", []):
            command = hook.get("command", "")
            if "notchi-hook.ps1" in command:
                return True
        return False


class SpriteRenderer:
    def __init__(self, assets_dir: Path) -> None:
        self.assets_dir = assets_dir
        self._cache: dict[tuple[str, int, int], ImageTk.PhotoImage] = {}
        self._grass_cache: dict[int, ImageTk.PhotoImage] = {}

    def get_frame(self, state: str, emotion: str, frame_index: int, scale: float = 2.0,
                  tint: tuple[int, int, int] | None = None,
                  outline_rgb: tuple[int, int, int] | None = None) -> ImageTk.PhotoImage:
        frame_count = 5 if state == "compacting" else 6
        normalized = frame_index % frame_count
        scale_key = int(scale * 100)
        cache_key = (f"{state}:{emotion}", normalized, scale_key, tint, outline_rgb)
        if cache_key not in self._cache:
            image = self._load_frame_image(state, emotion, normalized, scale, tint, outline_rgb)
            self._cache[cache_key] = ImageTk.PhotoImage(image)
        return self._cache[cache_key]

    def get_grass(self, scale: float = 1.0) -> ImageTk.PhotoImage:
        scale_key = int(scale * 100)
        if scale_key not in self._grass_cache:
            path = self.assets_dir / "GrassIsland.imageset" / "grass.png"
            image = Image.open(path).convert("RGBA")
            width = max(96, int(172 * scale))
            height = max(40, int(70 * scale))
            image = image.resize((width, height), Image.Resampling.NEAREST)
            self._grass_cache[scale_key] = ImageTk.PhotoImage(image)
        return self._grass_cache[scale_key]

    def _load_frame_image(self, state: str, emotion: str, frame_index: int, scale: float,
                          tint: tuple[int, int, int] | None = None,
                          outline_rgb: tuple[int, int, int] | None = None) -> Image.Image:
        columns = 5 if state == "compacting" else 6
        sprite_name = self._sprite_name_for(state, emotion)
        path = self.assets_dir / f"{sprite_name}.imageset" / "sprite_sheet.png"
        sheet = Image.open(path).convert("RGBA")
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
        scaled_width = max(48, int(frame.width * scale))
        scaled_height = max(48, int(frame.height * scale))
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

    def _sprite_name_for(self, state: str, emotion: str) -> str:
        requested = f"{state}_{emotion}"
        fallback_order = [requested]
        if emotion == "sob":
            fallback_order.append(f"{state}_sad")
        fallback_order.append(f"{state}_neutral")
        # States without dedicated sprites (e.g. resting) fall back to sleeping
        if state not in {"idle", "working", "waiting", "compacting", "sleeping"}:
            fallback_order.append(f"sleeping_{emotion}")
            fallback_order.append("sleeping_neutral")
            fallback_order.append("idle_neutral")

        for name in fallback_order:
            if (self.assets_dir / f"{name}.imageset" / "sprite_sheet.png").exists():
                return name
        return "idle_neutral"


class BackgroundRenderer:
    def __init__(self, assets_dir: Path) -> None:
        self._bg_path = assets_dir / "backgrounds" / "bg_default.png"
        self._cache: dict[tuple, ImageTk.PhotoImage] = {}

    def draw(self, canvas: tk.Canvas, width: int, height: int,
             theme: str = "oficina",
             ground_color: tuple[int, int, int] | None = None) -> None:
        key = (width, height, theme, ground_color)
        if key not in self._cache:
            self._cache[key] = self._build(width, height, theme, ground_color)
        canvas.create_image(0, 0, image=self._cache[key], anchor="nw")

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
        wx, wy = int(width * 0.06), int(height * 0.07)
        ww, wh = int(width * 0.26), int(height * 0.40)
        d.rectangle([wx, wy, wx + ww, wy + wh], fill=(178, 218, 238, 255))
        d.rectangle([wx, wy, wx + ww, wy + wh], outline=(110, 90, 72, 255), width=2)
        mx, my = wx + ww // 2, wy + wh // 2
        d.rectangle([mx - 1, wy + 2, mx + 1, wy + wh - 2], fill=(110, 90, 72, 255))
        d.rectangle([wx + 2, my - 1, wx + ww - 2, my + 1], fill=(110, 90, 72, 255))
        sx = int(width * 0.78)
        sw = int(width * 0.18)
        sh = int(height * 0.42)
        d.rectangle([sx, wy, sx + sw, wy + sh], fill=(158, 130, 100, 255))
        d.rectangle([sx, wy, sx + sw, wy + sh], outline=(110, 90, 72, 255), width=1)
        book_colors = [(180, 80, 60), (80, 130, 180), (90, 160, 90), (200, 170, 60)]
        bw = sw // len(book_colors) - 1
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
        tree_positions = [0.08, 0.22, 0.72, 0.88]
        for xr in tree_positions:
            tx = int(width * xr)
            th = int(height * 0.48)
            tw = int(width * 0.07)
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
        rng = random.Random(42)
        for _ in range(55):
            sx = rng.randint(0, width)
            sy = rng.randint(0, floor_y - 4)
            br = rng.randint(140, 255)
            d.ellipse([sx - 1, sy - 1, sx + 1, sy + 1], fill=(br, br, br, 255))
        mx, my, mr = int(width * 0.82), int(height * 0.14), int(height * 0.10)
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
        sx, sy, sr = int(width * 0.18), int(height * 0.12), int(height * 0.09)
        d.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(255, 220, 60, 255))
        return img

    @staticmethod
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
        # Far mountains (grey-blue, snowy)
        rng = random.Random(42)
        for i in range(5):
            mx = int(width * (0.05 + i * 0.22))
            mh = int(height * (0.32 + rng.random() * 0.18))
            mw = int(width * (0.14 + rng.random() * 0.10))
            pts = [mx - mw, floor_y, mx, floor_y - mh, mx + mw, floor_y]
            d.polygon(pts, fill=(155, 170, 195, 255))
            # Snow cap
            snow_h = int(mh * 0.30)
            sp = [mx - mw * snow_h // mh, floor_y - mh + snow_h,
                  mx, floor_y - mh,
                  mx + mw * snow_h // mh, floor_y - mh + snow_h]
            d.polygon(sp, fill=(240, 245, 255, 255))
        # Near mountains (darker)
        for i in range(3):
            mx = int(width * (0.12 + i * 0.34))
            mh = int(height * (0.28 + rng.random() * 0.14))
            mw = int(width * (0.18 + rng.random() * 0.08))
            pts = [mx - mw, floor_y, mx, floor_y - mh, mx + mw, floor_y]
            d.polygon(pts, fill=(110, 130, 155, 255))
            snow_h = int(mh * 0.28)
            sp = [mx - mw * snow_h // mh, floor_y - mh + snow_h,
                  mx, floor_y - mh,
                  mx + mw * snow_h // mh, floor_y - mh + snow_h]
            d.polygon(sp, fill=(235, 242, 255, 255))
        # Ground / snow floor
        d.rectangle([0, floor_y, width, height], fill=(*gc, 255))
        # Snow texture bumps
        for i in range(8):
            bx = int(width * (i / 8 + rng.random() * 0.08))
            d.ellipse([bx, floor_y - 3, bx + int(width * 0.14), floor_y + 6],
                      fill=(230, 238, 248, 200))
        # Small pine trees silhouettes
        for i in range(4):
            tx = int(width * (0.06 + i * 0.26 + rng.random() * 0.10))
            th = int(height * 0.16)
            tw = int(th * 0.55)
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
            sx = rng.randint(0, width)
            sy = rng.randint(0, height)
            br = rng.randint(120, 255)
            col = rng.choice([(br, br, br), (br, br - 20, br + 20), (br + 10, br, br - 20)])
            d.point([sx, sy], fill=(*col, 255))
        px, py, pr = int(width * 0.76), int(height * 0.28), int(height * 0.18)
        d.ellipse([px - pr, py - pr, px + pr, py + pr], fill=(80, 60, 140, 220))
        rw = int(pr * 1.7)
        d.ellipse([px - rw, py - int(pr * 0.22), px + rw, py + int(pr * 0.22)],
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


class NotchiWindowsApp:
    def __init__(self) -> None:
        self.base_dir = Path(__file__).resolve().parent
        self.instance_mutex = self._acquire_single_instance()
        self.data_store = DataStore()
        self.xp_system = XPSystem(self.data_store)
        self.xp_system.on_level_up(self._on_level_up)
        self.break_system = BreakSystem(self.data_store)
        self._levelup_message = ""
        self._levelup_until = 0.0
        self._break_confirm_until = 0.0
        self._banner_shown_at = 0.0
        self._break_banner_bounds: tuple[int, int, int, int] | None = None
        self._pending_picker_session: str | None = None
        self.parser = ConversationParser()
        self.store = SessionStore(self.parser, self.xp_system)
        self.installer = HookInstaller(self.base_dir)
        self.sprite_renderer = SpriteRenderer(self.base_dir / "assets" / "sprites")
        self.bg_renderer = BackgroundRenderer(self.base_dir / "assets")
        self.dec_renderer = DecorationRenderer()
        self.float_renderer = FloatingItemRenderer()
        self.drag_origin: tuple[int, int] | None = None
        self._is_dragging = False
        self.details_visible = False
        self.animation_phase = 0.0
        self.frame_tick = 0.0
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

        self.root = tk.Tk()
        self.root.title("Notchi for Windows")
        self.root.geometry("420x180+730+30")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=TRANSPARENT_KEY)

        self.server = EventTCPServer((APP_HOST, APP_PORT), EventHandler)
        self.server.app = self
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)

        self.status_var = tk.StringVar(value="Starting listener...")
        self.toggle_var = tk.StringVar(value="Details")
        self._build_ui()
        wx = self.data_store.get("window_x")
        wy = self.data_store.get("window_y")
        if wx >= 0 and wy >= 0:
            self.root.geometry(f"+{wx}+{wy}")
        opacity = float(self.data_store.get("opacity"))
        if opacity < 1.0:
            self.root.wm_attributes("-alpha", opacity)
        self._auto_install_hook()
        if not self.data_store.get("characters"):
            self.root.after(600, self._show_first_use_popup)

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

    def _on_level_up(self, new_level: int) -> None:
        self._levelup_message = f"Level Up!  Lv.{new_level}"
        self._levelup_until = time.time() + 3.5
        self._levelup_sparkles_until = time.time() + 3.5
        threading.Thread(target=self._play_levelup_sound, daemon=True).start()

    @staticmethod
    def _play_levelup_sound() -> None:
        try:
            for freq, dur in [(523, 90), (659, 90), (784, 90), (1047, 280)]:
                winsound.Beep(freq, dur)
        except Exception:
            pass

    def _build_ui(self) -> None:
        self.frame = tk.Frame(self.root, bg=TRANSPARENT_KEY, bd=0, highlightthickness=0)
        self.frame.pack(fill="both", expand=True, padx=6, pady=6)

        self.header = tk.Frame(self.frame, bg="#111827")
        self.header.pack(fill="x", padx=14, pady=(12, 8))
        self.header.bind("<ButtonPress-1>", self.start_drag)
        self.header.bind("<B1-Motion>", self.do_drag)

        title = tk.Label(self.header, text="Notchi", fg="#f8fafc", bg="#111827", font=("Microsoft YaHei UI", 14, "bold"))
        title.pack(side="left")
        title.bind("<ButtonPress-1>", self.start_drag)
        title.bind("<B1-Motion>", self.do_drag)

        actions = tk.Frame(self.header, bg="#111827")
        actions.pack(side="right")

        tk.Button(actions, textvariable=self.toggle_var, command=self.toggle_details, bg="#0f172a", fg="#cbd5e1", activebackground="#1e293b", activeforeground="#f8fafc", relief="flat", padx=8, pady=4).pack(side="left", padx=(0, 6))
        tk.Button(actions, text="Hook", command=self.install_hook, bg="#2563eb", fg="white", activebackground="#1d4ed8", activeforeground="white", relief="flat", padx=10, pady=4).pack(side="left", padx=(0, 6))
        tk.Button(actions, text="Casa", command=self.open_house_editor, bg="#1f2937", fg="#cbd5e1", activebackground="#374151", activeforeground="#f8fafc", relief="flat", padx=8, pady=4).pack(side="left", padx=(0, 6))
        tk.Button(actions, text="Personaje", command=self.open_character_editor, bg="#1f2937", fg="#cbd5e1", activebackground="#374151", activeforeground="#f8fafc", relief="flat", padx=8, pady=4).pack(side="left", padx=(0, 6))
        tk.Button(actions, text="⚙", command=self.open_settings, bg="#1f2937", fg="#cbd5e1", activebackground="#374151", activeforeground="#f8fafc", relief="flat", padx=8, pady=4).pack(side="left", padx=(0, 6))
        tk.Button(actions, text="Close", command=self.shutdown, bg="#1f2937", fg="#cbd5e1", activebackground="#374151", activeforeground="#f8fafc", relief="flat", padx=10, pady=4).pack(side="left")

        self.floating_actions = tk.Frame(self.frame, bg="#111827", bd=0, highlightthickness=1, highlightbackground="#334155")
        self.floating_install = tk.Button(
            self.floating_actions,
            text="Install",
            command=self.install_hook,
            bg="#2563eb",
            fg="white",
            activebackground="#1d4ed8",
            activeforeground="white",
            relief="flat",
            padx=8,
            pady=3,
        )
        self.floating_install.pack(side="left", padx=(6, 4), pady=6)
        self.floating_details = tk.Button(
            self.floating_actions,
            textvariable=self.toggle_var,
            command=self.toggle_details,
            bg="#0f172a",
            fg="#cbd5e1",
            activebackground="#1e293b",
            activeforeground="#f8fafc",
            relief="flat",
            padx=8,
            pady=3,
            width=7,
        )
        self.floating_details.pack(side="left", padx=(0, 4), pady=6)
        tk.Button(
            self.floating_actions,
            text="✕",
            command=self.shutdown,
            bg="#7f1d1d",
            fg="#fca5a5",
            activebackground="#991b1b",
            activeforeground="#fee2e2",
            relief="flat",
            padx=7,
            pady=3,
        ).pack(side="left", padx=(0, 6), pady=6)

        self.status_label = tk.Label(self.frame, textvariable=self.status_var, fg="#94a3b8", bg="#111827", anchor="w", justify="left", font=("Microsoft YaHei UI", 9))

        self.hero = tk.Canvas(self.frame, width=472, height=110, bg=TRANSPARENT_KEY, highlightthickness=0, relief="flat")
        self.hero.pack(fill="x", padx=14, pady=(10, 8))
        self.hero.bind("<ButtonPress-1>", self.start_drag)
        self.hero.bind("<B1-Motion>", self.do_drag)
        self.hero.bind("<ButtonRelease-1>", self.on_hero_release)
        self.hero.bind("<Double-Button-1>", self.on_hero_double_click)
        self.hero.bind("<Button-3>", self.on_hero_right_click)

        self.body_frame = tk.Frame(self.frame, bg="#111827")
        self.body_scrollbar = tk.Scrollbar(self.body_frame, orient="vertical")
        self.body = tk.Text(
            self.body_frame,
            bg="#0f172a",
            fg="#e2e8f0",
            insertbackground="#e2e8f0",
            relief="flat",
            wrap="word",
            state="disabled",
            font=("Microsoft YaHei UI", 10),
            padx=12,
            pady=10,
            yscrollcommand=self.body_scrollbar.set,
        )
        self.body_scrollbar.configure(command=self.body.yview)
        self.body.pack(side="left", fill="both", expand=True)
        self.body_scrollbar.pack(side="right", fill="y")

        self.xp_label = tk.Label(
            self.frame,
            text="",
            fg="#64748b",
            bg="#1e293b",
            font=("Microsoft YaHei UI", 8),
            padx=10,
            pady=3,
        )

        self._configure_transparency()
        self.update_layout()

    def _configure_transparency(self) -> None:
        try:
            self.root.wm_attributes("-transparentcolor", TRANSPARENT_KEY)
        except tk.TclError:
            pass
        self._set_tool_window_style()

    def _auto_install_hook(self) -> None:
        ok, message = self.installer.install()
        self.status_var.set(message if ok else f"Auto-install skipped: {message}")

    def _set_tool_window_style(self) -> None:
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            exstyle = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, exstyle | 0x00000080)
        except Exception:
            pass

    def start_drag(self, event: tk.Event) -> None:
        if not self.details_visible:
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
        self.header.pack_forget()
        self.floating_actions.place_forget()
        self.status_label.pack_forget()
        self.body_frame.pack_forget()
        self.xp_label.pack_forget()
        if self.details_visible:
            self.frame.configure(bg="#111827", highlightthickness=1, highlightbackground="#334155")
            self.root.configure(bg="#111827")
            self.hero.configure(bg="#111827")
            self.hero.configure(width=500, height=110)
            self.header.pack(fill="x", padx=14, pady=(12, 8))
            self.status_label.pack(fill="x", padx=14)
            self.body_frame.pack(fill="both", expand=True, padx=14, pady=(8, 12))
            self.root.geometry("570x430")
            self.toggle_var.set("Hide")
        else:
            self.frame.configure(bg=TRANSPARENT_KEY, highlightthickness=0)
            self.root.configure(bg=TRANSPARENT_KEY)
            self.hero.configure(bg=TRANSPARENT_KEY)
            self.hero.configure(width=372, height=110)
            self.root.geometry("420x180")
            self.toggle_var.set("Details")
            self.floating_actions.place(relx=1.0, x=-18, y=10, anchor="ne")
            self.xp_label.configure(bg="#1e293b")
            self.xp_label.pack(pady=(0, 6))
        self._configure_transparency()

    def on_hero_click(self, event: tk.Event) -> None:
        if self._picker_win is not None and self._picker_win.winfo_exists():
            self._picker_win.lift()
            self._picker_win.focus_set()
            return
        if self._break_banner_bounds is not None:
            bx1, by1, bx2, by2 = self._break_banner_bounds
            if bx1 <= event.x <= bx2 and by1 <= event.y <= by2:
                self._take_break()
                return
        session_id = self._session_id_at_point(event.x, event.y)
        if session_id is not None:
            self.store.select_session(session_id)
            sessions = self.store.snapshot()
            target = next((s for s in sessions if s.session_id == session_id), None)
            if target:
                self._cwd_label_text = target.cwd or target.project_name
                self._cwd_label_until = time.time() + 3.0
                self._focus_session_window(target)
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
        label = f"Eliminar  {target.project_name}"
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

    def _take_break(self) -> None:
        self.break_system.mark_taken()
        self._break_confirm_until = time.time() + 3.0
        self.xp_system.add_xp(5)

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
            self.toggle_details()
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
        installed = "installed" if self.installer.is_installed() else "not installed"
        self.status_var.set(f"Listening on {APP_HOST}:{APP_PORT} | Claude hook {installed} | Active sessions: {len(sessions)}")
        if focused and focused.character_id:
            xp_text = self.xp_system.bar_text_for(focused.character_id)
        else:
            xp_text = self.xp_system.bar_text()
        self.xp_label.configure(text=xp_text)

        if self._pending_picker_session is None:
            pending = self.store.sessions_needing_character()
            if pending:
                self._pending_picker_session = pending[0]
                self.root.after(100, lambda sid=pending[0]: self._show_character_picker(sid))

        if self.break_system.banner_visible():
            if self._banner_shown_at == 0.0:
                self._banner_shown_at = time.time()
            elif time.time() - self._banner_shown_at > 30.0:
                self.break_system.snooze()
                self._banner_shown_at = 0.0
        else:
            self._banner_shown_at = 0.0

        self.render_mascot(sessions)

        lines: list[str] = []
        if not sessions:
            lines.append("No active Claude Code sessions yet.")
            lines.append("")
            lines.append("1. Start this app.")
            lines.append("2. Click 'Install Hook'.")
            lines.append("3. Open Claude Code and use it normally.")
        elif focused is not None:
            lines.append(self.xp_system.bar_text())
            lines.append("")
            lines.append(f"Selected: {focused.project_name} [{focused.state}]")
            lines.append(f"Duration: {focused.duration}")
            lines.append(f"Emotion: {focused.emotion}")
            if focused.last_prompt:
                lines.append(f"Prompt: {focused.last_prompt}")
            if focused.current_tool:
                lines.append(f"Tool: {focused.current_tool}")
            lines.append(f"Mode: {focused.permission_mode}")
            if focused.messages:
                lines.append("Claude:")
                for message in focused.messages[-2:]:
                    preview = message.replace("\n", " ").strip()
                    if len(preview) > 180:
                        preview = preview[:177] + "..."
                    lines.append(f"  {preview}")
            lines.append("Recent:")
            for entry in focused.events[-4:]:
                lines.append(f"  - {entry}")
            if len(sessions) > 1:
                lines.append("")
                lines.append("Other Sessions:")
                for session in sessions:
                    if session.session_id == focused.session_id:
                        continue
                    lines.append(f"  {session.project_name} [{session.state}] {session.emotion}")

        if self.details_visible:
            self.body.configure(state="normal")
            self.body.delete("1.0", "end")
            self.body.insert("1.0", "\n".join(lines).rstrip())
            self.body.configure(state="disabled")
        self.root.after(REFRESH_MS, self.render)

    def animate(self) -> None:
        sessions = self.store.snapshot()
        active = sessions[0] if sessions else None
        state = active.state if active else "idle"
        emotion = active.emotion if active else "neutral"

        self.animation_phase += self._phase_step_for(state, emotion)
        self.frame_tick += self._frame_step_for(state, emotion)
        self.render_mascot(sessions)
        self.root.after(self._animation_delay_for(state, emotion), self.animate)

    def render_mascot(self, sessions: list[SessionData]) -> None:
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
            self.bg_renderer.draw(canvas, width, height, theme=bg_theme, ground_color=ground_rgb)
            self.decoration_bounds = {}
            for dec in active_decorations:
                img = self.dec_renderer.get(dec, height)
                if img is None:
                    continue
                default_pos = _DEFAULT_DEC_POSITIONS.get(dec, [0.5, 0.5])
                stored = dec_positions.get(dec, default_pos)
                if self._dragging_decoration == dec and self._dec_drag_pos is not None:
                    dx, dy = self._dec_drag_pos
                else:
                    dx = stored[0] * width
                    dy = stored[1] * height
                dw, dh = self.dec_renderer.size(dec, height)
                canvas.create_image(int(dx), int(dy), image=img, anchor="center")
                self.decoration_bounds[dec] = (dx - dw / 2, dy - dh / 2,
                                               dx + dw / 2, dy + dh / 2)

        sparkles_active = time.time() < self._levelup_sparkles_until
        ordered_sessions = sorted(sessions, key=lambda item: item.sprite_x)
        for index, session in enumerate(ordered_sessions):
            state = session.state
            emotion = session.emotion
            bob = self._bob_offset(state, emotion)
            pet_x = self._sprite_canvas_x(index, len(ordered_sessions), width)
            is_selected = focused is not None and focused.session_id == session.session_id
            session_char = self.data_store.get_character(session.character_id) if session.character_id else None
            char_level = session_char.get("level", 1) if session_char else 1
            level_mult = self._level_scale_mult(char_level)
            char_tint_key = session_char.get("tint", "original") if session_char else "original"
            tint_rgb = next((t[2] for t in MASCOT_TINTS if t[0] == char_tint_key), None)
            outline_key = session_char.get("outline", "ninguno") if session_char else "ninguno"
            outline_rgb = next((o[2] for o in OUTLINE_OPTIONS if o[0] == outline_key), None)
            float_key = session_char.get("floating_item", "ninguno") if session_char else "ninguno"
            sprite_scale = sprite_base_scale * level_mult * (1.04 if is_selected else 1.0)
            sprite = self.sprite_renderer.get_frame(
                state, emotion, int(self.frame_tick),
                scale=sprite_scale, tint=tint_rgb, outline_rgb=outline_rgb,
            )
            sprite_width = sprite.width()
            sprite_height = sprite.height()
            # Adjust y so feet stay at the same ground level regardless of size
            y_ground_offset = (1.0 - level_mult) * 20
            sprite_y = 70 + y_ground_offset + session.sprite_y_offset * 0.22 + bob

            # Draw floating item above sprite bounding box (canvas-level, animation-safe)
            float_img = self.float_renderer.get(float_key, sprite_scale)
            if float_img is not None:
                item_h = float_img.height()
                item_bob = math.sin(self.animation_phase * 1.6 + index) * 2.5
                item_y = sprite_y - sprite_height / 2 - item_h / 2 - 3 + item_bob
                canvas.create_image(int(pet_x), int(item_y), image=float_img, anchor="center")

            canvas.create_image(pet_x, sprite_y, image=sprite)
            self.sprite_bounds[session.session_id] = (
                pet_x - sprite_width / 2,
                sprite_y - sprite_height / 2,
                pet_x + sprite_width / 2,
                sprite_y + sprite_height / 2,
            )

            if is_selected and sparkles_active:
                phase = self.animation_phase * 2.5
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
                    name_y = sprite_y - sprite_height / 2 - 9
                    name_color = "#ffffff" if is_selected else "#e2e8f0"
                    font = ("Microsoft YaHei UI", 9, "bold") if is_selected else ("Microsoft YaHei UI", 8)
                    canvas.create_text(pet_x + 1, name_y + 1, text=name,
                                       fill="#000000", font=font, anchor="center")
                    canvas.create_text(pet_x, name_y, text=name,
                                       fill=name_color, font=font, anchor="center")

        if self.details_visible and focused is None:
            canvas.create_text(156, 60, text="Install the hook and start a session.", anchor="w", fill="#cbd5e1", font=("Segoe UI", 10), width=290)

        if not self.details_visible and self.break_system.banner_visible():
            # Pulsing border color
            pulse = 0.5 + 0.5 * math.sin(self.animation_phase * 1.2)
            r_c = int(59 + pulse * 30)
            g_c = int(130 + pulse * 40)
            b_c = 255
            outline_col = f"#{r_c:02x}{g_c:02x}{b_c:02x}"
            bx1, by1 = 8, height - 44
            bx2, by2 = width - 8, height - 4
            # Shadow
            canvas.create_rectangle(bx1 + 2, by1 + 2, bx2 + 2, by2 + 2,
                                     fill="#000000", outline="", stipple="gray50")
            # Background panel
            canvas.create_rectangle(bx1, by1, bx2, by2,
                                     fill="#0f172a", outline=outline_col, width=2)
            # Inner accent line
            canvas.create_line(bx1 + 2, by1 + 14, bx2 - 2, by1 + 14,
                                fill="#1e3a5f", width=1)
            # Icon + message
            canvas.create_text(bx1 + 14, (by1 + by2) // 2,
                                text="☕", font=("Segoe UI Emoji", 10), anchor="w",
                                fill="#fbbf24")
            canvas.create_text(bx1 + 34, by1 + 10,
                                text=self.break_system.banner_text(),
                                fill="#e2e8f0", font=("Microsoft YaHei UI", 8, "bold"),
                                anchor="w")
            canvas.create_text(bx1 + 34, by1 + 26,
                                text="Clic aquí para marcar descanso",
                                fill="#64748b", font=("Microsoft YaHei UI", 7),
                                anchor="w")
            self._break_banner_bounds = (bx1, by1, bx2, by2)
        else:
            self._break_banner_bounds = None

        if time.time() < self._break_confirm_until:
            cx_w = width // 2
            canvas.create_rectangle(cx_w - 80, height // 2 - 18,
                                     cx_w + 80, height // 2 + 14,
                                     fill="#064e3b", outline="#34d399", width=1)
            canvas.create_text(cx_w, height // 2 - 2,
                                text="Que descanses  ☀",
                                fill="#6ee7b7",
                                font=("Microsoft YaHei UI", 9, "bold"),
                                anchor="center")

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

    def _bob_offset(self, state: str, emotion: str) -> float:
        amplitudes = {
            "working": 3.5,
            "waiting": 1.5,
            "compacting": 1.0,
            "sleeping": 0.5,
            "resting": 0.6,
            "idle": 2.0,
        }
        amplitude = amplitudes.get(state, 2.0) * self._emotion_motion_multiplier(emotion)
        return math.sin(self.animation_phase) * amplitude

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
        win.title("Quien trabaja hoy?")
        win.configure(bg="#111827")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        x = self.root.winfo_x() + 10
        y = self.root.winfo_y() + 40
        height = max(160, 120 + len(chars) * 44)
        win.geometry(f"270x{height}+{x}+{y}")

        tk.Label(win, text="Quien trabaja en", fg="#64748b", bg="#111827",
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

        tk.Button(new_btn_frame, text="+ Nuevo personaje", command=show_create,
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

    def _show_first_use_popup(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Bienvenido")
        win.configure(bg="#111827")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        x = self.root.winfo_x() + 10
        y = self.root.winfo_y() + 40
        win.geometry(f"280x190+{x}+{y}")
        win.grab_set()

        tk.Label(win, text="Bienvenido", fg="#f8fafc", bg="#111827",
                 font=("Microsoft YaHei UI", 14, "bold")).pack(pady=(22, 4))
        tk.Label(win, text="Dale un nombre a tu companero:", fg="#94a3b8",
                 bg="#111827", font=("Microsoft YaHei UI", 9)).pack(pady=(0, 8))

        name_var = tk.StringVar(value="Notchi")
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
        tk.Button(win, text="Comenzar", command=confirm,
                  bg="#2563eb", fg="white", activebackground="#1d4ed8",
                  activeforeground="white", relief="flat",
                  padx=14, pady=6).pack(pady=14)

    def open_house_editor(self) -> None:
        if self.details_visible:
            self.toggle_details()

        current_level = self.xp_system.get_level()
        house = self.data_store.get_house()
        active_char = self.data_store.get_active_character() or {}

        win = tk.Toplevel(self.root)
        win.title("Tu Casa")
        win.configure(bg="#111827")
        win.resizable(False, True)
        win.attributes("-topmost", True)
        x = self.root.winfo_x() + 10
        y = self.root.winfo_y() + 40
        win.geometry(f"350x480+{x}+{y}")

        # ── Header (fixed, outside scroll) ────────────────────────────────────
        hdr = tk.Frame(win, bg="#0f172a")
        hdr.pack(fill="x")
        tk.Label(hdr, text="Tu Casa", fg="#f8fafc", bg="#0f172a",
                 font=("Microsoft YaHei UI", 12, "bold")).pack(side="left", padx=14, pady=10)
        tk.Label(hdr, text=f"Lv.{current_level}", fg="#fbbf24", bg="#0f172a",
                 font=("Microsoft YaHei UI", 10, "bold")).pack(side="right", padx=14)

        # ── Scrollable body ────────────────────────────────────────────────────
        scroll_canvas = tk.Canvas(win, bg="#111827", highlightthickness=0)
        scrollbar = tk.Scrollbar(win, orient="vertical", command=scroll_canvas.yview)
        scroll_canvas.configure(yscrollcommand=scrollbar.set)
        # Cerrar must be packed before the expanding canvas so it stays visible
        tk.Button(win, text="Cerrar", command=win.destroy, bg="#1f2937", fg="#cbd5e1",
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
        win.bind("<Destroy>", lambda _: scroll_canvas.unbind_all("<MouseWheel>"))

        def section_label(text: str) -> None:
            tk.Label(body, text=text, fg="#64748b", bg="#111827",
                     font=("Microsoft YaHei UI", 8)).pack(anchor="w", padx=16, pady=(10, 3))

        def separator() -> None:
            tk.Frame(body, height=1, bg="#1e293b").pack(fill="x", padx=12, pady=(4, 0))

        # ── Fondo ─────────────────────────────────────────────────────────────
        separator()
        section_label("FONDO")
        bg_frame = tk.Frame(body, bg="#111827")
        bg_frame.pack(fill="x", padx=14, pady=(0, 4))
        current_bg = [house.get("background", "oficina")]

        def refresh_bg_buttons() -> None:
            for w in bg_frame.winfo_children():
                w.destroy()
            row = tk.Frame(bg_frame, bg="#111827")
            row.pack(anchor="w")
            for key, label, min_lev in BG_THEMES:
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
                lbl = label if not locked else f"{label}\nLv.{min_lev}"
                tk.Button(row, text=lbl, command=on_bg, bg=bg_color, fg=fg_color,
                          activebackground="#1e293b", activeforeground="#f8fafc",
                          relief="flat", padx=6, pady=4,
                          font=("Microsoft YaHei UI", 8),
                          state="normal" if not locked else "disabled").pack(side="left", padx=2)

        refresh_bg_buttons()

        # ── Suelo ─────────────────────────────────────────────────────────────
        separator()
        section_label("SUELO")
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
                tk.Button(btn_frame, text=label, command=on_grass,
                          bg=hex_col, fg=fg_col,
                          activebackground=hex_col, activeforeground=fg_col,
                          relief="flat", padx=6, pady=3,
                          font=("Microsoft YaHei UI", 8)).pack()

        refresh_grass_buttons()

        # ── Decoraciones ──────────────────────────────────────────────────────
        separator()
        section_label("DECORACIONES  (arrastrá para mover)")
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
                tk.Button(dec_frame, text=f"{check_char}  {label}{lock_txt}",
                          command=on_dec, bg=btn_bg, fg=btn_fg,
                          activebackground="#1e293b", activeforeground="#f8fafc",
                          relief="flat", anchor="w", padx=8, pady=3,
                          font=("Microsoft YaHei UI", 9),
                          state="normal" if not locked else "disabled").pack(fill="x", pady=1)

        refresh_dec_buttons()

        separator()
        tk.Label(body, text="El color y estilo del personaje se configuran\ndesde el botón \"Personaje\".",
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
        win.title(f"Personaje: {char.get('name', 'Notchi')}")
        win.configure(bg="#111827")
        win.resizable(False, False)
        x = self.root.winfo_x() + 10
        y = self.root.winfo_y() + 40
        win.geometry(f"320x480+{x}+{y}")
        win.attributes("-topmost", True)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(win, bg="#0f172a")
        hdr.pack(fill="x")
        tk.Label(hdr, text=char.get("name", "Notchi"), fg="#f8fafc", bg="#0f172a",
                 font=("Microsoft YaHei UI", 12, "bold")).pack(side="left", padx=14, pady=10)
        tk.Label(hdr, text=f"Lv.{current_level}", fg="#fbbf24", bg="#0f172a",
                 font=("Microsoft YaHei UI", 10, "bold")).pack(side="right", padx=14)

        tk.Button(win, text="Cerrar", command=win.destroy, bg="#1f2937", fg="#cbd5e1",
                  activebackground="#374151", activeforeground="#f8fafc",
                  relief="flat", padx=12, pady=4).pack(side="bottom", pady=8)

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
            sprite = self.sprite_renderer.get_frame(
                "idle", "happy", 0, scale=2.2, tint=tint_rgb, outline_rgb=outline_rgb,
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

            # Tinte
            section_label("COLOR")
            make_option_row(
                [(k, l, rgb) for k, l, rgb, _ in MASCOT_TINTS if rgb is not None or k == "original"],
                lambda: (self.data_store.get_active_character() or {}).get("tint", "original"),
                lambda k: (self.data_store.update_active_character(char_id=char_id, tint=k),
                           self.sprite_renderer._cache.clear()),
                cols=3,
            )

            # Contorno
            section_label("CONTORNO")
            make_option_row(
                OUTLINE_OPTIONS,
                lambda: (self.data_store.get_active_character() or {}).get("outline", "ninguno"),
                lambda k: (self.data_store.update_active_character(char_id=char_id, outline=k),
                           self.sprite_renderer._cache.clear()),
                cols=4,
            )

            # Objeto flotante
            section_label("OBJETO FLOTANTE")
            tk.Label(body, text="Flota sobre la mascota en todas las animaciones.",
                     fg="#475569", bg="#111827",
                     font=("Microsoft YaHei UI", 7)).pack(anchor="w", padx=16)
            make_option_row(
                FLOATING_ITEMS,
                lambda: (self.data_store.get_active_character() or {}).get("floating_item", "ninguno"),
                lambda k: self.data_store.update_active_character(char_id=char_id, floating_item=k),
                cols=4,
            )

            tk.Frame(body, height=8, bg="#111827").pack()

        refresh_buttons()
        refresh_preview()

    def open_settings(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Configuracion")
        win.configure(bg="#111827")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        x = self.root.winfo_x() + 10
        y = self.root.winfo_y() + 40
        win.geometry(f"270x240+{x}+{y}")

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

        # XP
        section("SISTEMA DE XP")
        _char = self.data_store.get_active_character()
        xp_var = tk.BooleanVar(value=bool(_char.get("xp_enabled", True) if _char else True))
        def on_xp(*_: Any) -> None:
            self.data_store.update_active_character(xp_enabled=xp_var.get())
        tk.Checkbutton(win, text="XP activado", variable=xp_var, command=on_xp,
                       bg="#111827", fg="#f8fafc", activebackground="#111827",
                       activeforeground="#f8fafc", selectcolor="#0f172a",
                       relief="flat").pack(anchor="w", padx=24)

        # Breaks
        section("DESCANSOS")
        break_var = tk.BooleanVar(value=bool(self.data_store.get("break_enabled")))
        def on_break(*_: Any) -> None:
            self.data_store.set("break_enabled", break_var.get())
        tk.Checkbutton(win, text="Recordatorios activados", variable=break_var,
                       command=on_break, bg="#111827", fg="#f8fafc",
                       activebackground="#111827", activeforeground="#f8fafc",
                       selectcolor="#0f172a", relief="flat").pack(anchor="w", padx=24)

        interval_map = {"15 min": 15, "30 min": 30, "50 min": 50, "90 min": 90}
        cur_min = int(self.data_store.get("break_interval_minutes"))
        interval_var = tk.StringVar(value=f"{cur_min} min")
        def on_interval(*_: Any) -> None:
            self.data_store.set("break_interval_minutes", interval_map.get(interval_var.get(), 50))
        interval_var.trace_add("write", on_interval)
        r1 = row_frame()
        tk.Label(r1, text="Intervalo:", fg="#cbd5e1", bg="#111827",
                 font=("Microsoft YaHei UI", 9)).pack(side="left")
        styled_menu(r1, interval_var, list(interval_map.keys())).pack(side="left", padx=(6, 0))

        # Appearance
        section("APARIENCIA")
        opacity_map = {"60%": 0.6, "80%": 0.8, "100%": 1.0}
        cur_op = float(self.data_store.get("opacity"))
        closest = min(opacity_map, key=lambda k: abs(opacity_map[k] - cur_op))
        opacity_var = tk.StringVar(value=closest)
        def on_opacity(*_: Any) -> None:
            val = opacity_map.get(opacity_var.get(), 1.0)
            self.data_store.set("opacity", val)
            self.root.wm_attributes("-alpha", val)
        opacity_var.trace_add("write", on_opacity)
        r2 = row_frame()
        tk.Label(r2, text="Opacidad:", fg="#cbd5e1", bg="#111827",
                 font=("Microsoft YaHei UI", 9)).pack(side="left")
        styled_menu(r2, opacity_var, list(opacity_map.keys())).pack(side="left", padx=(6, 0))

        tk.Button(win, text="Cerrar", command=win.destroy, bg="#1f2937", fg="#cbd5e1",
                  activebackground="#374151", activeforeground="#f8fafc",
                  relief="flat", padx=12, pady=4).pack(side="bottom", pady=10)

    def run(self) -> None:
        self.server_thread.start()
        self.render()
        self.animate()
        self.root.mainloop()

    def shutdown(self) -> None:
        self.data_store.set("window_x", self.root.winfo_x())
        self.data_store.set("window_y", self.root.winfo_y())
        self.server.shutdown()
        self.server.server_close()
        if self.instance_mutex:
            ctypes.windll.kernel32.CloseHandle(self.instance_mutex)
        self.root.destroy()


if __name__ == "__main__":
    app = NotchiWindowsApp()
    app.run()
