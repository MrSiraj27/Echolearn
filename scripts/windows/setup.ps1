# EchoLearn one-command setup for Windows 10/11.
# Run it through setup.bat in the project folder. It is safe to run again: every step
# checks what is already there and only does what is missing.
#
#  1. Installs Python 3.11, Node.js LTS, PostgreSQL 16 and the VC++ runtime with winget (if missing)
#  2. Installs the frontend (npm) and backend (Python venv) dependencies
#  3. Creates the PostgreSQL database and login, and writes backend/.env
#  4. Asks for the Groq / Gemini API keys
#  5. Creates the tables (alembic), downloads the default voice, creates your login
#  6. Starts the app
param(
    [switch]$Unattended,   # no questions: keep existing values, skip account creation and start
    [switch]$NoStart
)

# "Continue": in Windows PowerShell 5.1, "Stop" turns any stderr line of pip/npm/python into a
# fatal error. Every step below checks its own exit code instead.
$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$EnvFile = Join-Path $Backend ".env"
$VenvPy = Join-Path $Backend "venv\Scripts\python.exe"
$PgSuperPass = "echolearn_pg_admin"   # only used when this script installs PostgreSQL itself

function Step($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function Ok($msg) { Write-Host "    $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "    $msg" -ForegroundColor Yellow }
function Fail($msg) {
    Write-Host ""; Write-Host "SETUP STOPPED: $msg" -ForegroundColor Red
    Write-Host "Fix the problem above and run setup.bat again (finished steps are skipped)."
    exit 1
}
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
}
function Has-Command($name) { return [bool](Get-Command $name -ErrorAction SilentlyContinue) }
function Run($exe, [string[]]$argList, $cwd) {
    Push-Location $cwd
    try { & $exe @argList; if ($LASTEXITCODE -ne 0) { Fail "'$exe $($argList -join ' ')' failed (exit $LASTEXITCODE)." } }
    finally { Pop-Location }
}
function Winget-Install($id, [string[]]$extra) {
    if (-not (Has-Command "winget")) {
        Fail "winget is not available. Install 'App Installer' from the Microsoft Store, then run setup.bat again."
    }
    Write-Host "    Installing $id with winget (Windows may ask for permission)..."
    & winget install -e --id $id --accept-source-agreements --accept-package-agreements --silent @extra
    # winget returns non-zero for "already installed"; the checks after each install decide.
    Refresh-Path
}
function Port-Open($port) {
    $c = New-Object Net.Sockets.TcpClient
    try { $iar = $c.BeginConnect("127.0.0.1", $port, $null, $null); return ($iar.AsyncWaitHandle.WaitOne(1500) -and $c.Connected) }
    catch { return $false } finally { $c.Close() }
}
function Random-Hex($bytes) {
    $b = New-Object byte[] $bytes
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
    return (($b | ForEach-Object { $_.ToString("x2") }) -join "")
}
function Read-EnvValue($key) {
    if (-not (Test-Path $EnvFile)) { return "" }
    foreach ($line in [IO.File]::ReadAllLines($EnvFile)) {
        if ($line -match "^\s*$([regex]::Escape($key))\s*=(.*)$") { return $Matches[1].Trim() }
    }
    return ""
}
function Set-EnvValue($key, $value) {
    $lines = New-Object Collections.Generic.List[string]
    if (Test-Path $EnvFile) { $lines.AddRange([string[]][IO.File]::ReadAllLines($EnvFile)) }
    $found = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^\s*$([regex]::Escape($key))\s*=") { $lines[$i] = "$key=$value"; $found = $true }
    }
    if (-not $found) { $lines.Add("$key=$value") }
    [IO.File]::WriteAllLines($EnvFile, $lines, (New-Object Text.UTF8Encoding $false))
}
function Ask($prompt, $default) {
    if ($Unattended) { return $default }
    $suffix = if ($default) { " [press Enter to keep the current one]" } else { "" }
    $v = Read-Host "$prompt$suffix"
    if ([string]::IsNullOrWhiteSpace($v)) { return $default } else { return $v.Trim() }
}

Write-Host "EchoLearn setup - project folder: $Root" -ForegroundColor Cyan

# ---------------------------------------------------------------- 1. prerequisites
Step "Checking Python 3.11"
$pyOk = $false
if (Has-Command "py") { & py -3.11 --version *> $null; $pyOk = ($LASTEXITCODE -eq 0) }
if (-not $pyOk) {
    Winget-Install "Python.Python.3.11" @("--scope", "user")
    if (Has-Command "py") { & py -3.11 --version *> $null; $pyOk = ($LASTEXITCODE -eq 0) }
    if (-not $pyOk) { Fail "Python 3.11 is still missing. Install it from https://www.python.org/downloads/release/python-3119/ (tick 'Add to PATH'), then run setup.bat again." }
}
Ok (& py -3.11 --version)

Step "Checking Node.js (18 or newer)"
$nodeOk = $false
if (Has-Command "node") { $nodeOk = ([int]((& node --version).TrimStart("v").Split(".")[0]) -ge 18) }
if (-not $nodeOk) {
    Winget-Install "OpenJS.NodeJS.LTS" @()
    if (Has-Command "node") { $nodeOk = ([int]((& node --version).TrimStart("v").Split(".")[0]) -ge 18) }
    if (-not $nodeOk) { Fail "Node.js is still missing. Install the LTS version from https://nodejs.org, then run setup.bat again." }
}
Ok ("Node " + (& node --version))

Step "Checking the Microsoft Visual C++ runtime (needed by the AI libraries)"
if (Test-Path "$env:SystemRoot\System32\vcruntime140_1.dll") { Ok "Present" }
else { Winget-Install "Microsoft.VCRedist.2015+.x64" @() ; Ok "Installed" }

Step "Checking PostgreSQL"
$installedPg = $false
if (Port-Open 5432) {
    Ok "A PostgreSQL server is already running on port 5432"
} else {
    $svc = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($svc) {
        Warn "PostgreSQL service '$($svc.Name)' is stopped - starting it"
        try { Start-Service $svc.Name -ErrorAction Stop } catch { Fail "Could not start $($svc.Name). Start it from the Services app, then run setup.bat again." }
    } else {
        Winget-Install "PostgreSQL.PostgreSQL.16" @("--override",
            "--mode unattended --unattendedmodeui minimal --superpassword $PgSuperPass --serverport 5432")
        $installedPg = $true
    }
    for ($i = 0; $i -lt 30 -and -not (Port-Open 5432); $i++) { Start-Sleep 2 }
    if (-not (Port-Open 5432)) { Fail "PostgreSQL is not answering on port 5432. Install PostgreSQL 16 from https://www.postgresql.org/download/windows/ (port 5432), then run setup.bat again." }
    Ok "PostgreSQL is running on port 5432"
}

# ---------------------------------------------------------------- 2. dependencies
Step "Creating the Python environment (backend\venv)"
if (-not (Test-Path $VenvPy)) { Run "py" @("-3.11", "-m", "venv", "venv") $Backend; Ok "Created" }
else { Ok "Already there" }

Step "Installing frontend and backend packages (first time takes 5-15 minutes)"
$env:ECHOLEARN_ONE_CLICK = "1"
Run "node" @((Join-Path $Root "scripts\setup.mjs")) $Root
if (-not (Test-Path $EnvFile)) { Copy-Item (Join-Path $Backend ".env.example") $EnvFile }

# ---------------------------------------------------------------- 3. database + .env
Step "Setting up the database"
function Db-Works {
    Push-Location $Backend
    try {
        & $VenvPy -c "from app.core.database import engine; engine.connect().close()" *> $null
        return ($LASTEXITCODE -eq 0)
    } finally { Pop-Location }
}
if (Db-Works) {
    Ok "backend\.env already points to a working database"
} else {
    $dbPass = Random-Hex 16
    $superPass = if ($installedPg) { $PgSuperPass } else { "" }
    while ($true) {
        $env:ECHOLEARN_PG_SUPERPASS = $superPass
        $env:ECHOLEARN_DB_PASS = $dbPass
        Push-Location $Backend
        & $VenvPy "scripts\create_local_db.py" --db echolearn --user echolearn
        $code = $LASTEXITCODE
        Pop-Location
        if ($code -eq 0) { break }
        if ($code -ne 2 -or $Unattended) { Fail "Could not create the database." }
        Write-Host ""
        Write-Host "    PostgreSQL was already installed on this PC, so its admin password is needed once." -ForegroundColor Yellow
        $sec = Read-Host "    Password of the PostgreSQL 'postgres' user (the one chosen when it was installed)" -AsSecureString
        $superPass = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
    }
    Remove-Item Env:\ECHOLEARN_PG_SUPERPASS, Env:\ECHOLEARN_DB_PASS -ErrorAction SilentlyContinue
    Set-EnvValue "DATABASE_URL" "postgresql://echolearn:$dbPass@localhost:5432/echolearn"
    if (-not (Db-Works)) { Fail "The database was created but the app still cannot connect to it." }
    Ok "Database 'echolearn' is ready"
}

$jwt = Read-EnvValue "JWT_SECRET"
if (-not $jwt -or $jwt -eq "change_this_to_a_long_random_string") { Set-EnvValue "JWT_SECRET" (Random-Hex 32); Ok "Generated a new JWT_SECRET" }
if (-not (Read-EnvValue "FRONTEND_URL")) { Set-EnvValue "FRONTEND_URL" "http://localhost:3000" }

# ---------------------------------------------------------------- 4. API keys
Step "AI API keys (at least one of Groq or Gemini is needed)"
$groq = Ask "    Groq API key (starts with gsk_)" (Read-EnvValue "GROQ_API_KEY")
$gemini = Ask "    Gemini API key (starts with AIza)" (Read-EnvValue "GEMINI_API_KEY")
Set-EnvValue "GROQ_API_KEY" $groq
Set-EnvValue "GEMINI_API_KEY" $gemini
if (-not $groq -and -not $gemini) { Warn "No key entered: the app will open, but chat, quizzes and explanations will not work until you add a key to backend\.env and run setup.bat again." }
else { Ok "Saved in backend\.env" }

# ---------------------------------------------------------------- 5. tables, voice, account
Step "Creating the database tables"
Run $VenvPy @("-m", "alembic", "upgrade", "head") $Backend
Ok "Tables are up to date"

Step "Downloading the default reading voice (about 110 MB, once)"
$voiceDir = Join-Path $Backend "voices"
New-Item -ItemType Directory -Force $voiceDir | Out-Null
$voiceBase = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/high/en_US-lessac-high.onnx"
foreach ($ext in @(".json", "")) {
    $target = Join-Path $voiceDir ("en_US-lessac-high.onnx" + $ext)
    if (-not (Test-Path $target) -or (Get-Item $target).Length -eq 0) {
        try { Invoke-WebRequest -UseBasicParsing -Uri ($voiceBase + $ext) -OutFile $target }
        catch { Remove-Item $target -ErrorAction SilentlyContinue; Warn "Voice download failed ($($_.Exception.Message)). Everything else works; run setup.bat again later to retry." }
    }
}
if (Test-Path (Join-Path $voiceDir "en_US-lessac-high.onnx")) { Set-EnvValue "VOICE_MODEL_PATH" "./voices/en_US-lessac-high.onnx"; Ok "Voice ready" }

Step "Creating your EchoLearn login"
Write-Host "    Sign-up emails need an email service, so your account is created here instead (already verified, with admin rights)."
$email = Ask "    Email for your login (leave empty to skip)" ""
if ($email) {
    $name = Ask "    Your name" "EchoLearn User"
    $sec = Read-Host "    Choose a password (8+ characters)" -AsSecureString
    $pw = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
    Push-Location $Backend
    & $VenvPy "scripts\create_admin.py" $email --role superadmin --name $name --password $pw
    Pop-Location
    $pw = $null
} else { Ok "Skipped" }

Write-Host ""
Write-Host "Setup finished. Next time, just double-click start.bat." -ForegroundColor Green
if (-not $NoStart -and -not $Unattended) { & (Join-Path $PSScriptRoot "start.ps1") }
