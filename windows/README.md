# pixel-companion — Windows

This folder contains the tray app, its hook scripts and the status line segment.

## Run

```powershell
git clone https://github.com/Emi-Dz/pixel-companion.git
cd pixel-companion/windows
pip install -r ../requirements.txt
pythonw tray.py
```

## Files

| File | Purpose |
|---|---|
| `tray.py` | Tray app: one icon, session menu, terminal focus |
| `mascota-hook.ps1` | Claude Code hook (auto-installed) |
| `codex-hook.ps1` | Codex hook (auto-installed) |
| `statusline.ps1` | Claude Code status line segment (Dino + session name + state) |
| `Iniciar Mascota.vbs` | Starts the tray app silently, for the Startup folder |
| `assets/sprites/Dino/` | Dino sprite sheets for all 4 states |
| `app.py` | Previous floating-window version (scenes, mini-game). Not launched by the hooks. |

## Hooks

On launch, the tray app makes sure these are installed:

- `~/.claude/hooks/mascota-hook.ps1` + entries in `~/.claude/settings.json` — Claude Code hook
- `~/.codex/mascota-codex-hook.ps1` + entries in `~/.codex/hooks.json` — Codex hook

Both hooks send events to `127.0.0.1:8765` and start the tray app if it is not running. The Claude hook also resolves which `claude.exe` process owns the session (once per session), so the tray can follow it.

## Data

Everything lives under `%USERPROFILE%\.mascota\`:

| Path | Content |
|---|---|
| `sessions\<session_id>.json` | Current state of each session (written by the hook) |
| `sessions\<session_id>.title` | Resolved session name (written by the tray, read by the status line) |
| `tray.json` | Tray settings (`sound`, `language`) |
| `python.txt` | Python interpreter the hooks use to start the tray app |

`python.txt` matters when a virtual environment is active in your terminal: the hooks start the tray app with the interpreter that has `pystray` installed, not whatever `pythonw` comes first on `PATH`.

## Notes

- Only one instance runs at a time (enforced via a Windows mutex).
- Session files are removed automatically when their Claude process exits.
