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

## Background visibility

The toolbar includes a **BG** button that toggles the house scene (background, decorations, and floor) on or off:

- **BG on** (button lit blue) — the full scene is visible behind the characters.
- **BG off** (button dark) — only the characters float over your desktop; the scene is completely hidden.

The characters are always rendered at 100% opacity regardless of this setting. When the background is off, clicks on that area pass through to whatever is underneath the app.

Opening the **🏠 House editor** automatically enables the background so you can see the scene while editing.

The last-used state is saved and restored on the next launch.

## Notes

- Only one instance runs at a time (enforced via Windows mutex).
- The app minimizes to a small window on startup; it does not use the system tray.
