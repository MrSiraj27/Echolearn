# Starts the EchoLearn backend (port 8000) and frontend (port 3000) in their own windows
# and opens the app in the browser. Close those two windows to stop the app.
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"

if (-not (Test-Path (Join-Path $Backend "venv\Scripts\python.exe"))) {
    Write-Host "EchoLearn is not set up yet - run setup.bat first." -ForegroundColor Red; exit 1
}

function Port-Open($port) {
    $c = New-Object Net.Sockets.TcpClient
    try { $iar = $c.BeginConnect("127.0.0.1", $port, $null, $null); return ($iar.AsyncWaitHandle.WaitOne(1000) -and $c.Connected) }
    catch { return $false } finally { $c.Close() }
}

if (Port-Open 8000) { Write-Host "Backend already running on port 8000." }
else {
    Start-Process powershell -WorkingDirectory $Backend -ArgumentList @("-NoExit", "-Command",
        "`$host.UI.RawUI.WindowTitle='EchoLearn backend (keep open)'; .\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000")
}
if (Port-Open 3000) { Write-Host "Frontend already running on port 3000." }
else {
    Start-Process powershell -WorkingDirectory $Frontend -ArgumentList @("-NoExit", "-Command",
        "`$host.UI.RawUI.WindowTitle='EchoLearn frontend (keep open)'; npm run dev")
}

Write-Host "Waiting for EchoLearn to start (the first start can take a minute)..."
for ($i = 0; $i -lt 90 -and -not ((Port-Open 8000) -and (Port-Open 3000)); $i++) { Start-Sleep 2 }
if ((Port-Open 8000) -and (Port-Open 3000)) {
    Start-Process "http://localhost:3000"
    Write-Host "EchoLearn is running at http://localhost:3000" -ForegroundColor Green
} else {
    Write-Host "EchoLearn did not start within 3 minutes. Look at the two EchoLearn windows for the error." -ForegroundColor Red
}
