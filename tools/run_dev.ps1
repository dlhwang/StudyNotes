# 개발용 실행: BE와 화면을 각각 새 PowerShell 창으로 띄운다.
#   .\tools\run_dev.ps1            # BE(Agent 같은 프로세스) + 화면
#   .\tools\run_dev.ps1 -Aegra     # Aegra + BE(aegra 모드) + 화면. PostgreSQL과 .env 필요
param([switch]$Aegra)

$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"

function Start-Window([string]$title, [string]$command) {
    Start-Process powershell -WorkingDirectory $root -ArgumentList @(
        "-NoExit", "-Command", "`$Host.UI.RawUI.WindowTitle = '$title'; $command"
    )
}

if ($Aegra) {
    Start-Window "aegra" "& '$root\.venv\Scripts\aegra.exe' serve --host 127.0.0.1 --port 2026"
    Start-Window "be" "`$env:NOTES_API_AGENT_MODE = 'aegra'; & '$py' -m uvicorn notes_api.main:app --host 127.0.0.1 --port 8000"
} else {
    Start-Window "be" "& '$py' -m uvicorn notes_api.main:app --host 127.0.0.1 --port 8000"
}
Start-Window "ui" "& '$py' -m streamlit run app/streamlit_app.py --server.port 8501"
Write-Output "BE http://127.0.0.1:8000/docs · 화면 http://localhost:8501"
