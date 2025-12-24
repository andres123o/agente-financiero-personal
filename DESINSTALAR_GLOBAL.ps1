# Script para desinstalar las dependencias instaladas globalmente (PowerShell)
Write-Host "Desinstalando dependencias globales..." -ForegroundColor Yellow
Write-Host ""

pip uninstall -y python-dotenv
pip uninstall -y fastapi
pip uninstall -y uvicorn
pip uninstall -y openai
pip uninstall -y httpx
pip uninstall -y pydantic

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Dependencias globales desinstaladas." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Ahora usa el entorno virtual:" -ForegroundColor Cyan
Write-Host "  .\run.bat  (Windows CMD)" -ForegroundColor White
Write-Host "  .\run.ps1  (PowerShell)" -ForegroundColor White
Write-Host ""

