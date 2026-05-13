# pixel-companion — Windows

This folder contains the Windows desktop app and its hook scripts.

## Run

```powershell
git clone https://github.com/Emi-Dz/pixel-companion.git
cd pixel-companion/windows
pip install -r ../requirements.txt
python app.py
```

## Files

| File | Purpose |
|---|---|
| `app.py` | Main application |
| `mascota-hook.ps1` | Claude Code hook payload (auto-installed) |
| `codex-hook.ps1` | Codex hook payload (auto-installed) |
| `Iniciar Mascota.vbs` | Helper to create a desktop shortcut |
| `assets/sprites/Dino/` | Dino sprite sheets for all 4 states |
| `sounds/` | Sound effects used by the app and mini-game |

## Hooks

On first launch, the app automatically installs:

- `~/.claude/hooks/mascota-hook.ps1` — Claude Code hook
- `~/.codex/mascota-codex-hook.ps1` + entry in `~/.codex/hooks.json` — Codex hook

Both hooks connect to `127.0.0.1:8765` and auto-launch the app if it's not running.

To reinstall hooks manually, open **Settings → Reinstall hooks** from the app.

## Data

User data is stored at `%USERPROFILE%\.mascota\mascota_data.json`.

Legacy data from `.pixel-mascot` is automatically migrated on first launch.

## Notes

- Only one instance runs at a time (enforced via Windows mutex).
- The app minimizes to a small window on startup; it does not use the system tray.
