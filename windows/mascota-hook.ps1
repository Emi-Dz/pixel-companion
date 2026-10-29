$ErrorActionPreference = "SilentlyContinue"
$appDir = "__MASCOTA_APP_DIR__"
$stateDir = Join-Path $env:USERPROFILE ".mascota\sessions"

function Send-MascotaPayload {
    param(
        [string]$JsonPayload
    )

    $client = [System.Net.Sockets.TcpClient]::new()
    $connect = $client.BeginConnect("127.0.0.1", 8765, $null, $null)
    if (-not $connect.AsyncWaitHandle.WaitOne(300)) {
        $client.Dispose()
        throw "timeout"
    }
    $client.EndConnect($connect)
    $stream = $client.GetStream()
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($JsonPayload)
    $stream.Write($bytes, 0, $bytes.Length)
    $stream.Dispose()
    $client.Dispose()
}

function Test-MascotaRunning {
    $mutex = $null
    if ([System.Threading.Mutex]::TryOpenExisting("Local\MascotaSingleton", [ref]$mutex)) {
        $mutex.Dispose()
        return $true
    }
    return $false
}

function Start-MascotaApp {
    if ([string]::IsNullOrWhiteSpace($appDir)) {
        return $false
    }

    $appPath = Join-Path $appDir "tray.py"
    if (-not (Test-Path $appPath)) {
        return $false
    }

    # Interpreter recorded by the last successful tray run (has pystray installed).
    $knownPython = Join-Path $env:USERPROFILE ".mascota\python.txt"
    if (Test-Path $knownPython) {
        $exe = (Get-Content $knownPython -Raw).Trim()
        if ($exe -and (Test-Path $exe)) {
            Start-Process -FilePath $exe -ArgumentList "`"$appPath`"" -WindowStyle Hidden | Out-Null
            return $true
        }
    }

    $candidates = @("pythonw", "pyw")
    foreach ($name in $candidates) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if (-not $command) {
            continue
        }

        $arguments = @()
        if ($name -eq "pyw") {
            $arguments += "-3"
        }
        $arguments += "`"$appPath`""

        Start-Process -FilePath $command.Source -ArgumentList $arguments -WindowStyle Hidden | Out-Null
        return $true
    }

    return $false
}

# The hook runs as claude.exe -> cmd.exe -> powershell.exe, so the direct parent
# dies right away. Walk up until we find the long-lived Claude process.
function Find-ClaudeProcess {
    $procId = $PID
    for ($i = 0; $i -lt 6; $i++) {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $procId" -ErrorAction SilentlyContinue
        if (-not $proc) { break }
        if ($i -gt 0 -and $proc.Name -match '^(claude|node)(\.exe)?$') {
            return $proc
        }
        $procId = [int]$proc.ParentProcessId
        if ($procId -le 0) { break }
    }
    return $null
}

# Name given at launch, e.g. `claude --remote-control campos-29-10 "prompt"`.
# Long values are skipped: without a name the next argument is the prompt itself.
function Get-LaunchName {
    param([string]$CommandLine)
    if ($CommandLine -match '\s(?:--remote-control|--name|-n)\s+(?:"([^"]+)"|([^\s"-][^\s"]*))') {
        $name = if ($Matches[1]) { $Matches[1] } else { $Matches[2] }
        if ($name.Length -le 60) { return $name.Trim() }
    }
    return ""
}

$payload = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($payload)) {
    exit 0
}

try {
    $inputObject = $payload | ConvertFrom-Json
} catch {
    exit 0
}

$sessionId = [string]$inputObject.session_id
$eventName = [string]$inputObject.hook_event_name

$statusMap = @{
    "UserPromptSubmit" = "processing"
    "PreCompact" = "compacting"
    "SessionStart" = "waiting_for_input"
    "SessionEnd" = "ended"
    "PreToolUse" = "running_tool"
    "PostToolUse" = "processing"
    "PermissionRequest" = "waiting_for_input"
    "Stop" = "waiting_for_input"
    "SubagentStop" = "waiting_for_input"
}

$stateMap = @{
    "UserPromptSubmit" = "working"
    "PreCompact" = "compacting"
    "SessionStart" = "idle"
    "PreToolUse" = "working"
    "PostToolUse" = "working"
    "PermissionRequest" = "waiting"
    "Stop" = "idle"
}

# Per-session state file: read by the status line and survives tray restarts.
# The Claude PID and launch name are resolved once per session and cached here
# (the process lookup is slow).
$claudePid = 0
$launchName = $null
$stateFile = $null
$previous = $null
if ($sessionId -match '^[A-Za-z0-9_-]+$') {
    $stateFile = Join-Path $stateDir "$sessionId.json"
    if (Test-Path $stateFile) {
        try { $previous = Get-Content $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json } catch {}
        if ($previous -and $previous.claude_pid) { $claudePid = [int]$previous.claude_pid }
        if ($previous) { $launchName = $previous.launch_name }
    }
}
if (-not $claudePid -or $null -eq $launchName) {
    $claudeProc = Find-ClaudeProcess
    if ($claudeProc) {
        $claudePid = [int]$claudeProc.ProcessId
        $launchName = Get-LaunchName ([string]$claudeProc.CommandLine)
    }
    if ($null -eq $launchName) { $launchName = "" }
}

if ($stateFile) {
    if ($eventName -eq "SessionEnd") {
        Remove-Item $stateFile -Force -ErrorAction SilentlyContinue
    } elseif ($stateMap.ContainsKey($eventName) -or -not $previous) {
        $state = if ($stateMap.ContainsKey($eventName)) { $stateMap[$eventName] } else { "idle" }
        $tool = if ($eventName -eq "PreToolUse" -or $eventName -eq "PermissionRequest") { [string]$inputObject.tool_name } else { "" }
        $record = @{
            session_id = $sessionId
            cwd = [string]$inputObject.cwd
            state = $state
            tool = $tool
            claude_pid = $claudePid
            launch_name = [string]$launchName
            transcript_path = [string]$inputObject.transcript_path
            updated = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        }
        try {
            New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
            $tmp = "$stateFile.$PID.tmp"
            [System.IO.File]::WriteAllText($tmp, ($record | ConvertTo-Json -Compress), [System.Text.UTF8Encoding]::new($false))
            Move-Item -Path $tmp -Destination $stateFile -Force
        } catch {}
    }
}

$output = @{
    session_id = $inputObject.session_id
    cwd = $inputObject.cwd
    event = $inputObject.hook_event_name
    status = if ($inputObject.status) { $inputObject.status } else { $statusMap[$inputObject.hook_event_name] }
    interactive = $true
    permission_mode = if ($inputObject.permission_mode) { $inputObject.permission_mode } else { "default" }
    claude_pid = $claudePid
    launch_name = [string]$launchName
    transcript_path = [string]$inputObject.transcript_path
}

if ($inputObject.tool_name) {
    $output.tool = $inputObject.tool_name
}

$jsonPayload = $output | ConvertTo-Json -Depth 4 -Compress

try {
    Send-MascotaPayload -JsonPayload $jsonPayload
    exit 0
} catch {
}

# Only launch when nobody holds the singleton mutex; avoids racing hooks
# spawning several copies while the first one is still starting.
if ($eventName -ne "SessionEnd" -and -not (Test-MascotaRunning) -and (Start-MascotaApp)) {
    Start-Sleep -Milliseconds 1200
    try {
        Send-MascotaPayload -JsonPayload $jsonPayload
    } catch {
    }
}
exit 0
