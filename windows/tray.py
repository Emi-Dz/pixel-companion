"""Pixel Companion — system tray edition.

A single tray icon (next to the clock) shows a pixel dino reflecting the most
urgent Claude Code / Codex session. The menu lists every session by its name
(the same one printed in each terminal's status line), and clicking an entry
brings that terminal to the front.

Sessions are tied to the lifetime of their Claude process: when the process
exits (terminal closed, crash, kill) the session disappears on its own, even
if Claude never sent SessionEnd.
"""
from __future__ import annotations

import ctypes
import json
import socketserver
import sys
import threading
import time
import winsound
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pystray
from PIL import Image, ImageDraw, ImageEnhance

APP_HOST = "127.0.0.1"
APP_PORT = 8765
APP_MUTEX_NAME = "Local\\MascotaSingleton"
ANIMATION_MS = 160
LIVENESS_SECONDS = 5
SESSION_SLEEP_SECONDS = 180
ORPHAN_SESSION_SECONDS = 2 * 60 * 60  # sessions without a PID (Codex) expire after this
ICON_SIZE = 32

BASE_DIR = Path(__file__).resolve().parent
SPRITES_DIR = BASE_DIR / "assets" / "sprites" / "Dino"
DATA_DIR = Path.home() / ".mascota"
STATE_DIR = DATA_DIR / "sessions"
SETTINGS_PATH = DATA_DIR / "tray.json"
LEGACY_DATA_PATH = DATA_DIR / "mascota_data.json"
CLAUDE_SESSIONS_DIR = Path.home() / ".claude" / "sessions"  # Claude's own <pid>.json registry

# Higher number wins when picking which dino to show in the tray.
STATE_PRIORITY = {"waiting": 4, "working": 3, "compacting": 3, "idle": 2, "sleeping": 1}
STATE_SPRITE = {
    "waiting": "waiting",
    "working": "working",
    "compacting": "working",
    "idle": "idle",
    "sleeping": "sleeping",
}

TEXTS = {
    "es": {
        "working": "trabajando",
        "compacting": "compactando",
        "waiting": "espera tu OK",
        "idle": "lista",
        "sleeping": "durmiendo",
        "no_sessions": "Sin sesiones activas",
        "sound": "Sonido cuando espera aprobación",
        "cleanup": "Quitar sesiones cerradas",
        "quit": "Salir",
        "title_none": "Pixel · sin sesiones",
    },
    "en": {
        "working": "working",
        "compacting": "compacting",
        "waiting": "needs your OK",
        "idle": "ready",
        "sleeping": "sleeping",
        "no_sessions": "No active sessions",
        "sound": "Sound when waiting for approval",
        "cleanup": "Remove closed sessions",
        "quit": "Quit",
        "title_none": "Pixel · no sessions",
    },
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _language() -> str:
    lang = _load_json(SETTINGS_PATH).get("language") or _load_json(LEGACY_DATA_PATH).get("language")
    return lang if lang in TEXTS else "en"


LANG = _language()


def T(key: str) -> str:
    return TEXTS[LANG].get(key, key)


# ---------------------------------------------------------------------------
# Win32 helpers
# ---------------------------------------------------------------------------

kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32
kernel32.OpenProcess.restype = ctypes.c_void_p
kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p


def _acquire_single_instance() -> int:
    mutex = kernel32.CreateMutexW(None, False, APP_MUTEX_NAME)
    if not mutex:
        return 0
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(mutex)
        sys.exit(0)
    return mutex


def _process_name(pid: int) -> str | None:
    """Image name of a running process, or None when it no longer exists."""
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    try:
        code = ctypes.c_ulong(0)
        if not kernel32.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code)) or code.value != 259:
            return None  # 259 == STILL_ACTIVE
        buf = ctypes.create_unicode_buffer(1024)
        size = ctypes.c_ulong(len(buf))
        if kernel32.QueryFullProcessImageNameW(ctypes.c_void_p(handle), 0, buf, ctypes.byref(size)):
            return Path(buf.value).name.lower()
        return ""
    finally:
        kernel32.CloseHandle(ctypes.c_void_p(handle))


def _claude_alive(pid: int) -> bool:
    name = _process_name(pid)
    if name is None:
        return False
    # Guard against PID reuse: the PID must still belong to Claude (or node for npm installs).
    return name == "" or name.startswith("claude") or name.startswith("node")


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


def _parent_map() -> dict[int, int]:
    parents: dict[int, int] = {}
    snap = kernel32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if not snap or snap == ctypes.c_void_p(-1).value:
        return parents
    try:
        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
        ok = kernel32.Process32First(ctypes.c_void_p(snap), ctypes.byref(entry))
        while ok:
            parents[entry.th32ProcessID] = entry.th32ParentProcessID
            ok = kernel32.Process32Next(ctypes.c_void_p(snap), ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(ctypes.c_void_p(snap))
    return parents


def _visible_window_for_pid(pid: int) -> int | None:
    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
    found: list[int] = []

    def _cb(hwnd: int, _: int) -> bool:
        if user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd) > 0:
            wpid = ctypes.c_ulong(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
            if wpid.value == pid:
                found.append(hwnd)
                return False
        return True

    user32.EnumWindows(EnumProc(_cb), 0)
    return found[0] if found else None


def focus_terminal(claude_pid: int) -> bool:
    """Walk up from the Claude process to the first ancestor that owns a window
    (Windows Terminal, VS Code, conhost...) and bring it to the front."""
    parents = _parent_map()
    pid = claude_pid
    for _ in range(8):
        hwnd = _visible_window_for_pid(pid)
        if hwnd:
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
            return True
        parent = parents.get(pid)
        if not parent or parent == pid:
            break
        pid = parent
    return False


# ---------------------------------------------------------------------------
# Hook installation
# ---------------------------------------------------------------------------

def _install_hook(template: Path, target: Path, config_path: Path, events: dict[str, list]) -> None:
    if not target.parent.exists() or not template.exists():
        return
    text = template.read_text(encoding="utf-8").replace("__MASCOTA_APP_DIR__", str(BASE_DIR))
    try:
        if not target.exists() or target.read_text(encoding="utf-8") != text:
            target.write_text(text, encoding="utf-8")
    except OSError:
        return

    data = _load_json(config_path) if config_path.exists() else {}
    if config_path.exists() and not data:
        return  # unreadable config: never overwrite it
    hooks = data.setdefault("hooks", {})
    command = f'powershell -NoProfile -ExecutionPolicy Bypass -File "{target}"'
    changed = False
    for event_name, matchers in events.items():
        existing = hooks.setdefault(event_name, [])
        present = any(target.name in h.get("command", "") for item in existing for h in item.get("hooks", []))
        if not present:
            for matcher in matchers:
                entry: dict[str, Any] = {"hooks": [{"type": "command", "command": command}]}
                if matcher is not None:
                    entry["matcher"] = matcher
                existing.append(entry)
            changed = True
    if changed:
        config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def install_hooks() -> None:
    claude_dir = Path.home() / ".claude"
    _install_hook(
        BASE_DIR / "mascota-hook.ps1",
        claude_dir / "hooks" / "mascota-hook.ps1",
        claude_dir / "settings.json",
        {
            "UserPromptSubmit": [None],
            "SessionStart": [None],
            "PreToolUse": ["*"],
            "PostToolUse": ["*"],
            "PermissionRequest": ["*"],
            "PreCompact": ["auto", "manual"],
            "Stop": [None],
            "SubagentStop": [None],
            "SessionEnd": [None],
        },
    )
    codex_dir = Path.home() / ".codex"
    _install_hook(
        BASE_DIR / "codex-hook.ps1",
        codex_dir / "mascota-codex-hook.ps1",
        codex_dir / "hooks.json",
        {
            "UserPromptSubmit": [None],
            "SessionStart": [None],
            "PreToolUse": ["*"],
            "PostToolUse": ["*"],
            "PermissionRequest": ["*"],
            "Stop": [None],
        },
    )


# ---------------------------------------------------------------------------
# Session titles
# ---------------------------------------------------------------------------

# Claude Code keeps re-appending these records to the transcript; a /rename
# (customTitle) wins over an agent name, which wins over the auto title.
TITLE_KEYS = (("custom-title", "customTitle"), ("agent-name", "agentName"), ("ai-title", "aiTitle"))
TITLE_TAIL_BYTES = 512 * 1024
TITLE_FULL_SCAN_LIMIT = 64 * 1024 * 1024
TITLE_REFRESH_SECONDS = 30
TITLE_MAX_CHARS = 48


def _titles_in(lines: list[bytes]) -> dict[str, str]:
    found: dict[str, str] = {}
    for line in lines:
        if b'-title"' not in line and b'"agent-name"' not in line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        for record_type, field in TITLE_KEYS:
            if record.get("type") == record_type and record.get(field):
                found[record_type] = str(record[field])  # later records overwrite earlier ones
    return found


def _transcript_titles(transcript_path: str) -> dict[str, str]:
    path = Path(transcript_path) if transcript_path else None
    if path is None or not path.is_file():
        return {}
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            fh.seek(max(0, size - TITLE_TAIL_BYTES))
            found = _titles_in(fh.read().splitlines())
            if not found and TITLE_TAIL_BYTES < size <= TITLE_FULL_SCAN_LIMIT:
                fh.seek(0)
                found = _titles_in(fh.read().splitlines())
    except OSError:
        return {}
    return found


def read_session_title(transcript_path: str, claude_pid: int = 0, launch_name: str = "") -> str:
    """Best human name for a session, most explicit first:
    name the user gave (Claude's per-PID registry) > name passed at launch
    (--remote-control <name>) > /rename > agent name > auto title > derived name."""
    registry = _load_json(CLAUDE_SESSIONS_DIR / f"{claude_pid}.json") if claude_pid else {}
    user_name = registry.get("name") if registry.get("nameSource") == "user" else ""
    titles = _transcript_titles(transcript_path)
    candidates = [user_name, launch_name, *(titles.get(t) for t, _f in TITLE_KEYS), registry.get("name")]
    for candidate in candidates:
        if candidate:
            title = " ".join(str(candidate).split())
            return title if len(title) <= TITLE_MAX_CHARS else title[:TITLE_MAX_CHARS - 1] + "…"
    return ""


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

@dataclass
class Session:
    session_id: str
    cwd: str = ""
    state: str = "idle"
    tool: str = ""
    claude_pid: int = 0
    agent: str = "claude"
    last_activity: float = 0.0
    transcript_path: str = ""
    launch_name: str = ""
    title: str = ""
    title_checked: float = 0.0

    @property
    def project(self) -> str:
        return Path(self.cwd).name or self.cwd or "?"

    @property
    def name(self) -> str:
        return self.title or self.project

    @property
    def display_state(self) -> str:
        if self.state == "idle" and time.time() - self.last_activity > SESSION_SLEEP_SECONDS:
            return "sleeping"
        return self.state


class SessionStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, Session] = {}
        self.on_waiting: Any = None

    def load_from_disk(self) -> None:
        """Pick up sessions that were already running before the tray started."""
        if not STATE_DIR.exists():
            return
        for path in STATE_DIR.glob("*.json"):
            data = _load_json(path)
            pid = int(data.get("claude_pid") or 0)
            if not pid or not _claude_alive(pid):
                path.unlink(missing_ok=True)
                path.with_suffix(".title").unlink(missing_ok=True)
                continue
            sid = data.get("session_id") or path.stem
            with self._lock:
                self._sessions[sid] = Session(
                    session_id=sid,
                    cwd=data.get("cwd", ""),
                    state=data.get("state", "idle"),
                    tool=data.get("tool", ""),
                    claude_pid=pid,
                    last_activity=float(data.get("updated") or time.time()),
                    transcript_path=data.get("transcript_path", ""),
                    launch_name=data.get("launch_name", ""),
                )

    def process(self, payload: dict[str, Any]) -> None:
        sid = payload.get("session_id") or "unknown"
        event = payload.get("event", "")
        tool = payload.get("tool") or ""
        became_waiting = None

        with self._lock:
            if event == "SessionEnd":
                self._sessions.pop(sid, None)
                return
            session = self._sessions.get(sid)
            if session is None:
                session = Session(session_id=sid)
                self._sessions[sid] = session
            session.cwd = payload.get("cwd") or session.cwd
            session.agent = payload.get("agent_type", "claude")
            session.last_activity = time.time()
            pid = int(payload.get("claude_pid") or 0)
            if pid:
                session.claude_pid = pid
            session.transcript_path = payload.get("transcript_path") or session.transcript_path
            if payload.get("launch_name") and payload["launch_name"] != session.launch_name:
                session.launch_name = payload["launch_name"]
                session.title_checked = 0.0
            if event in {"UserPromptSubmit", "Stop"}:
                session.title_checked = 0.0  # the auto title usually appears right after a prompt

            previous = session.state
            if event in {"UserPromptSubmit", "PreToolUse"}:
                session.state = "working"
                session.tool = tool if event == "PreToolUse" else ""
            elif event == "PermissionRequest":
                session.state = "waiting"
                session.tool = tool
            elif event == "PreCompact":
                session.state = "compacting"
            elif event == "PostToolUse":
                if session.state in {"waiting", "idle"}:
                    session.state = "working"
                session.tool = ""
            elif event in {"Stop", "SessionStart"}:
                session.state = "idle"
                session.tool = ""
            if session.state == "waiting" and previous != "waiting":
                became_waiting = session

        if became_waiting is not None and self.on_waiting:
            self.on_waiting(became_waiting)

    def prune_dead(self) -> bool:
        now = time.time()
        with self._lock:
            dead = [
                sid for sid, s in self._sessions.items()
                if (s.claude_pid and not _claude_alive(s.claude_pid))
                or (not s.claude_pid and now - s.last_activity > ORPHAN_SESSION_SECONDS)
            ]
            for sid in dead:
                self._sessions.pop(sid, None)
        for sid in dead:
            (STATE_DIR / f"{sid}.json").unlink(missing_ok=True)
            (STATE_DIR / f"{sid}.title").unlink(missing_ok=True)
        return bool(dead)

    def refresh_titles(self) -> bool:
        """Re-read session names from the transcripts. Returns True if any changed."""
        now = time.time()
        with self._lock:
            due = [(s.session_id, s.transcript_path, s.claude_pid, s.launch_name) for s in self._sessions.values()
                   if now - s.title_checked > TITLE_REFRESH_SECONDS]
        changed = False
        for sid, transcript_path, claude_pid, launch_name in due:
            title = read_session_title(transcript_path, claude_pid, launch_name)
            with self._lock:
                session = self._sessions.get(sid)
                if session is None:
                    continue
                session.title_checked = now
                if not title or title == session.title:
                    continue
                session.title = title
                changed = True
            # Shared with the status line so the terminal shows the same name as the tray.
            try:
                (STATE_DIR / f"{sid}.title").write_text(title, encoding="utf-8")
            except OSError:
                pass
        return changed

    def snapshot(self) -> list[Session]:
        with self._lock:
            sessions = [Session(**vars(s)) for s in self._sessions.values()]
        sessions.sort(key=lambda s: (-STATE_PRIORITY.get(s.display_state, 0), s.name.lower()))
        return sessions


class EventTCPServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = False  # on Windows SO_REUSEADDR would let a second copy share the port


class EventHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        self.request.settimeout(2.0)
        chunks: list[bytes] = []
        try:
            while True:
                data = self.request.recv(4096)
                if not data:
                    break
                chunks.append(data)
        except OSError:
            return
        try:
            payload = json.loads(b"".join(chunks).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return
        if isinstance(payload, dict):
            self.server.app.on_event(payload)


# ---------------------------------------------------------------------------
# Icon rendering
# ---------------------------------------------------------------------------

class DinoIcons:
    BADGE = {"waiting": (245, 158, 11)}

    def __init__(self) -> None:
        self.frames: dict[str, list[Image.Image]] = {}
        for state in ("idle", "working", "waiting", "sleeping"):
            sheet_path = SPRITES_DIR / f"{state}_neutral.imageset" / "sprite_sheet.png"
            sheet = Image.open(sheet_path).convert("RGBA")
            size = sheet.height
            frames = [sheet.crop((i * size, 0, (i + 1) * size, size)) for i in range(sheet.width // size)]
            # One crop box for the whole animation so the dino does not jitter between frames.
            boxes = [f.getbbox() for f in frames if f.getbbox()]
            box = (min(b[0] for b in boxes), min(b[1] for b in boxes),
                   max(b[2] for b in boxes), max(b[3] for b in boxes)) if boxes else (0, 0, size, size)
            self.frames[state] = [self._fit(f.crop(box)) for f in frames]
        empty = ImageEnhance.Color(self.frames["sleeping"][0]).enhance(0.0)
        self.empty = ImageEnhance.Brightness(empty).enhance(0.7)
        self._cache: dict[tuple[str, int], Image.Image] = {}

    @staticmethod
    def _fit(cropped: Image.Image) -> Image.Image:
        scale = ICON_SIZE / max(cropped.width, cropped.height)
        cropped = cropped.resize((max(1, round(cropped.width * scale)), max(1, round(cropped.height * scale))),
                                 Image.NEAREST)
        canvas = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
        canvas.paste(cropped, ((ICON_SIZE - cropped.width) // 2, ICON_SIZE - cropped.height), cropped)
        return canvas

    def frame_count(self, state: str) -> int:
        return len(self.frames[STATE_SPRITE.get(state, "idle")])

    def get(self, state: str | None, index: int) -> Image.Image:
        if state is None:
            return self.empty
        key = (state, index)
        if key not in self._cache:
            frames = self.frames[STATE_SPRITE.get(state, "idle")]
            img = frames[index % len(frames)].copy()
            color = self.BADGE.get(STATE_SPRITE.get(state, ""))
            if color:
                draw = ImageDraw.Draw(img)
                draw.ellipse((ICON_SIZE - 12, ICON_SIZE - 12, ICON_SIZE - 1, ICON_SIZE - 1),
                             fill=color + (255,), outline=(17, 24, 39, 255))
            self._cache[key] = img
        return self._cache[key]


# ---------------------------------------------------------------------------
# Tray app
# ---------------------------------------------------------------------------

class TrayApp:
    def __init__(self) -> None:
        self.instance_mutex = _acquire_single_instance()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.settings = _load_json(SETTINGS_PATH)
        self.store = SessionStore()
        self.store.on_waiting = self._on_waiting
        self.icons = DinoIcons()
        self._stop = threading.Event()
        self._menu_key: tuple = ()
        self._frame = 0
        self._shown: tuple[str | None, int] | None = None

        try:
            install_hooks()
        except Exception:
            pass
        # The hook relaunches us with this interpreter: a bare "pythonw" on PATH may
        # be an activated venv that lacks pystray.
        try:
            (DATA_DIR / "python.txt").write_text(sys.executable, encoding="utf-8")
        except OSError:
            pass
        self.store.load_from_disk()
        self.store.refresh_titles()

        self.server = EventTCPServer((APP_HOST, APP_PORT), EventHandler)
        self.server.app = self

        self.icon = pystray.Icon(
            "pixel-companion",
            icon=self.icons.get(None, 0),
            title=T("title_none"),
            menu=pystray.Menu(self._menu_items),
        )

    # -- settings -------------------------------------------------------
    @property
    def sound_enabled(self) -> bool:
        return bool(self.settings.get("sound", True))

    def _toggle_sound(self, _icon: Any = None, _item: Any = None) -> None:
        self.settings["sound"] = not self.sound_enabled
        try:
            SETTINGS_PATH.write_text(json.dumps(self.settings, indent=2), encoding="utf-8")
        except OSError:
            pass

    # -- events ---------------------------------------------------------
    def on_event(self, payload: dict[str, Any]) -> None:
        self.store.process(payload)
        self._refresh()

    def _on_waiting(self, _session: Session) -> None:
        if self.sound_enabled:
            threading.Thread(target=winsound.MessageBeep, args=(winsound.MB_ICONASTERISK,), daemon=True).start()

    # -- menu -----------------------------------------------------------
    @staticmethod
    def _session_label(s: Session) -> str:
        state = s.display_state
        text = f"{s.name}  —  {T(state)}"
        if s.tool and state in {"working", "waiting"}:
            text += f" ({s.tool})"
        if s.agent == "codex":
            text += "  [Codex]"
        return text

    def _focus(self, session: Session) -> None:
        if session.claude_pid:
            threading.Thread(target=focus_terminal, args=(session.claude_pid,), daemon=True).start()

    def _focus_action(self, session: Session) -> Any:
        # pystray only accepts callbacks with 0-2 positional args, so bind the session in a closure.
        return lambda: self._focus(session)

    def _focus_most_urgent(self, _icon: Any = None, _item: Any = None) -> None:
        sessions = self.store.snapshot()
        if sessions:
            self._focus(sessions[0])

    def _menu_items(self) -> list[pystray.MenuItem]:
        sessions = self.store.snapshot()
        items: list[pystray.MenuItem] = [
            # Hidden default item: left-click on the tray icon jumps to the most urgent session.
            pystray.MenuItem("focus", self._focus_most_urgent, default=True, visible=False),
        ]
        if sessions:
            for s in sessions:
                items.append(pystray.MenuItem(self._session_label(s), self._focus_action(s)))
        else:
            items.append(pystray.MenuItem(T("no_sessions"), None, enabled=False))
        items += [
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(T("sound"), self._toggle_sound, checked=lambda _item: self.sound_enabled),
            pystray.MenuItem(T("cleanup"), self._cleanup),
            pystray.MenuItem(T("quit"), self._quit),
        ]
        return items

    def _cleanup(self, _icon: Any = None, _item: Any = None) -> None:
        self.store.prune_dead()
        self._refresh()

    # -- rendering ------------------------------------------------------
    def _refresh(self) -> None:
        sessions = self.store.snapshot()
        key = tuple((s.session_id, s.display_state, s.tool, s.name) for s in sessions)
        if key != self._menu_key:
            self._menu_key = key
            if sessions:
                counts: dict[str, int] = {}
                for s in sessions:
                    counts[s.display_state] = counts.get(s.display_state, 0) + 1
                summary = " · ".join(f"{n} {T(st)}" for st, n in counts.items())
                self.icon.title = f"Pixel · {summary}"[:127]
            else:
                self.icon.title = T("title_none")
            try:
                self.icon.update_menu()
            except Exception:
                pass

    def _animate(self) -> None:
        while not self._stop.wait(ANIMATION_MS / 1000):
            sessions = self.store.snapshot()
            state = sessions[0].display_state if sessions else None
            # Only working/waiting dinos move; idle ones blink slowly, sleeping/empty stay still.
            if state in {"working", "waiting", "compacting"}:
                self._frame += 1
            elif state == "idle" and int(time.time() * 1000 / ANIMATION_MS) % 4 == 0:
                self._frame += 1
            index = self._frame % self.icons.frame_count(state) if state else 0
            if (state, index) != self._shown:
                self._shown = (state, index)
                self.icon.icon = self.icons.get(state, index)
            if state == "sleeping" or state == "idle":
                self._refresh()  # idle -> sleeping transition is time based

    def _watch_liveness(self) -> None:
        while not self._stop.wait(LIVENESS_SECONDS):
            pruned = self.store.prune_dead()
            if self.store.refresh_titles() or pruned:
                self._refresh()

    # -- lifecycle ------------------------------------------------------
    def _setup(self, icon: pystray.Icon) -> None:
        icon.visible = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        threading.Thread(target=self._animate, daemon=True).start()
        threading.Thread(target=self._watch_liveness, daemon=True).start()
        self._refresh()

    def _quit(self, _icon: Any = None, _item: Any = None) -> None:
        self._stop.set()
        self.server.shutdown()
        self.server.server_close()
        self.icon.stop()

    def run(self) -> None:
        try:
            self.icon.run(setup=self._setup)
        finally:
            if self.instance_mutex:
                kernel32.CloseHandle(self.instance_mutex)


if __name__ == "__main__":
    TrayApp().run()
