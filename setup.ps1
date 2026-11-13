# The Forgery Case: start everything and (re)load the workflows into n8n.
# Usage (from this folder):  powershell -ExecutionPolicy Bypass -File setup.ps1
# Safe to re-run: credentials are created only the first time, so pasted API keys are never overwritten.
# Re-running DOES overwrite the workflow with workflows/forgery_game.json (edit the build script, not the UI).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# on a new PC: say what is missing instead of failing halfway
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Python 3 is not installed (https://www.python.org/downloads/ - tick 'Add to PATH')." }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw "Docker Desktop is not installed (https://www.docker.com/products/docker-desktop/)." }
docker info *> $null
if ($LASTEXITCODE) { throw "Docker Desktop is installed but not running: start it, wait until it says 'Engine running', then re-run setup." }
if (-not (Test-Path keys.env)) { Write-Warning "keys.env not found: the experts will have no API keys. Copy keys.env into this folder and re-run setup." }

python tools/build_workflows.py
docker compose up -d

Write-Host "Waiting for n8n..."
do { Start-Sleep 2; try { $ok = (Invoke-WebRequest -UseBasicParsing http://localhost:5678/healthz).StatusCode -eq 200 } catch { $ok = $false } } until ($ok)

# plate_notes.sql is idempotent; init scripts only run on a fresh volume, so apply it to existing databases too
Get-Content db/plate_notes.sql -Raw | docker compose exec -T postgres psql -U forgery -d forgery -q -v ON_ERROR_STOP=1
if ($LASTEXITCODE) { throw "db/plate_notes.sql failed (exit $LASTEXITCODE): the Restorer needs this table" }

$existing = docker compose exec -T n8n n8n export:credentials --id=fcPostgres000001 2>$null
if (-not ($existing -match "fcPostgres000001")) {
    docker compose cp tools/credentials.template.json n8n:/tmp/creds.json
    docker compose exec -T n8n n8n import:credentials --input=/tmp/creds.json
} else { Write-Host "Credentials already exist, keeping your API keys." }
# the Restorer agent's chat-model credential is newer than the template import above
$resto = docker compose exec -T n8n n8n export:credentials --id=fcGeminiRestoAI1 2>$null
if (-not ($resto -match "fcGeminiRestoAI1") -and -not (Test-Path keys.env)) {
    Write-Warning "Credential 'Gemini - Restorer' (fcGeminiRestoAI1) is missing: fill GEMINI_KEY_RESTORER or GEMINI_KEY_CURATOR in keys.env and re-run setup, or the Restorer cannot answer."
}

# keys.env -> n8n credentials (only the keys you filled in; the temp file is deleted right after)
if (Test-Path keys.env) {
    python tools/apply_keys.py keys.env tools/.creds.tmp.json
    docker compose cp tools/.creds.tmp.json n8n:/tmp/keys.json | Out-Null
    Remove-Item tools/.creds.tmp.json
    docker compose exec -T n8n n8n import:credentials --input=/tmp/keys.json
    docker compose exec -T -u root n8n rm -f /tmp/keys.json  # docker cp leaves it root-owned
}

docker compose exec -T n8n n8n import:workflow --input=/workflows/forgery_game.json
docker compose exec -T n8n n8n publish:workflow --id=fcGame0000000001
# earlier builds had one workflow per agent; switch them off if present (delete them in the UI)
foreach ($old in "fcArchivist00001", "fcScientist00001", "fcRestorer000001", "fcCurator0000001") {
    docker compose exec -T n8n n8n unpublish:workflow --id=$old 2>$null | Out-Null
}
docker compose restart n8n
do { Start-Sleep 2; try { $ok = (Invoke-WebRequest -UseBasicParsing http://localhost:5678/healthz).StatusCode -eq 200 } catch { $ok = $false } } until ($ok)

Write-Host ""
Write-Host "Editor: http://localhost:5678"
Write-Host "Game:   http://localhost:5678/webhook/game"
