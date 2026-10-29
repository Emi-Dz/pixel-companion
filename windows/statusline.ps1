# Pixel Companion status line segment for Claude Code.
# Prints "<dino> <session name> <state>" for the session this terminal belongs to.
#
# Use it as your whole status line:
#   "statusLine": { "type": "command",
#     "command": "powershell -NoProfile -ExecutionPolicy Bypass -File \"C:\\path\\to\\windows\\statusline.ps1\"" }
# or copy the block below into your own status line script.

$raw = [Console]::In.ReadToEnd()
try { $data = $raw | ConvertFrom-Json -ErrorAction Stop } catch { exit 0 }
$sessionId = [string]$data.session_id
if (-not $sessionId) { exit 0 }

$ESC = [char]27
$RESET = "$ESC[0m"; $BOLD = "$ESC[1m"; $DIM = "$ESC[2m"
$GREEN = "$ESC[32m"; $YELLOW = "$ESC[33m"; $CYAN = "$ESC[36m"

$mascotaDir = Join-Path $env:USERPROFILE ".mascota"
$lang = "en"
foreach ($cfg in "tray.json", "mascota_data.json") {
    $path = Join-Path $mascotaDir $cfg
    if (Test-Path $path) {
        try { $value = (Get-Content $path -Raw -Encoding UTF8 | ConvertFrom-Json).language } catch { $value = $null }
        if ($value) { $lang = $value; break }
    }
}
$labels = @{
    en = @{ working = "working"; compacting = "compacting"; waiting = "needs your OK"; idle = "ready"; sleeping = "sleeping" }
    es = @{ working = "trabajando"; compacting = "compactando"; waiting = "espera tu OK"; idle = "lista"; sleeping = "durmiendo" }
}
$L = if ($labels.ContainsKey($lang)) { $labels[$lang] } else { $labels.en }

# Session name is resolved by the tray app (same name as in its menu).
$sessionsDir = Join-Path $mascotaDir "sessions"
$name = $null
$titleFile = Join-Path $sessionsDir "$sessionId.title"
if (Test-Path $titleFile) {
    try { $name = (Get-Content $titleFile -Raw -Encoding UTF8).Trim() } catch {}
}
if (-not $name) { $name = $sessionId.Substring(0, [Math]::Min(8, $sessionId.Length)) }

$stateText = ""
$stateFile = Join-Path $sessionsDir "$sessionId.json"
if (Test-Path $stateFile) {
    try { $state = Get-Content $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json } catch { $state = $null }
    if ($state) {
        $age = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - [long]$state.updated
        switch ($state.state) {
            "working"    { $stateText = "$GREEN$($L.working)$RESET"; if ($state.tool) { $stateText += "$DIM ($($state.tool))$RESET" } }
            "compacting" { $stateText = "$GREEN$($L.compacting)$RESET" }
            "waiting"    { $stateText = "$YELLOW$BOLD$($L.waiting)$RESET" }
            default      { $stateText = if ($age -gt 180) { "$DIM$($L.sleeping)$RESET" } else { "$CYAN$($L.idle)$RESET" } }
        }
    }
}

$segment = "$([char]::ConvertFromUtf32(0x1F996)) $BOLD$name$RESET"
if ($stateText) { $segment += " $stateText" }

[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::Out.Write($segment)
