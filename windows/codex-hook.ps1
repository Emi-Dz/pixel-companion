$ErrorActionPreference = "SilentlyContinue"
$appDir = "__MASCOTA_APP_DIR__"

function Send-MascotaPayload {
    param(
        [string]$JsonPayload
    )

    $client = [System.Net.Sockets.TcpClient]::new("127.0.0.1", 8765)
    $stream = $client.GetStream()
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($JsonPayload)
    $stream.Write($bytes, 0, $bytes.Length)
    $stream.Dispose()
    $client.Dispose()
}

function Start-MascotaApp {
    if ([string]::IsNullOrWhiteSpace($appDir)) {
        return $false
    }

    $appPath = Join-Path $appDir "app.py"
    if (-not (Test-Path $appPath)) {
        return $false
    }

    $candidates = @("pythonw", "pyw", "python", "py")
    foreach ($name in $candidates) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if (-not $command) {
            continue
        }

        $arguments = @()
        if ($name -eq "py" -or $name -eq "pyw") {
            $arguments += "-3"
        }
        $arguments += "`"$appPath`""

        Start-Process -FilePath $command.Source -ArgumentList $arguments -WindowStyle Hidden | Out-Null
        return $true
    }

    return $false
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

$statusMap = @{
    "UserPromptSubmit" = "processing"
    "SessionStart"     = "waiting_for_input"
    "PreToolUse"       = "running_tool"
    "PostToolUse"      = "processing"
    "PermissionRequest"= "waiting_for_input"
    "Stop"             = "waiting_for_input"
}

$output = @{
    session_id      = $inputObject.session_id
    cwd             = $inputObject.cwd
    event           = $inputObject.hook_event_name
    status          = if ($statusMap.ContainsKey($inputObject.hook_event_name)) { $statusMap[$inputObject.hook_event_name] } else { "processing" }
    interactive     = $true
    permission_mode = "default"
    agent_type      = "codex"
    model           = if ($inputObject.model) { $inputObject.model } else { "" }
    transcript_path = if ($inputObject.transcript_path) { $inputObject.transcript_path } else { "" }
}

if ($inputObject.prompt) {
    $output.user_prompt = $inputObject.prompt
}

if ($inputObject.tool_name) {
    $output.tool = $inputObject.tool_name
}

if ($inputObject.tool_use_id) {
    $output.tool_use_id = $inputObject.tool_use_id
}

$jsonPayload = $output | ConvertTo-Json -Depth 8 -Compress

try {
    Send-MascotaPayload -JsonPayload $jsonPayload
    exit 0
} catch {
}

if (Start-MascotaApp) {
    Start-Sleep -Milliseconds 1200
    try {
        Send-MascotaPayload -JsonPayload $jsonPayload
        exit 0
    } catch {
    }
}
