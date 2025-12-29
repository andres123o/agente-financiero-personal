# Script para ejecutar el servidor usando el entorno virtual (PowerShell)
& .\venv\Scripts\Activate.ps1
uvicorn api.index:app --reload



