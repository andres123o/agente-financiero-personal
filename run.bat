@echo off
REM Script para ejecutar el servidor usando el entorno virtual
call venv\Scripts\activate.bat
uvicorn api.index:app --reload
pause



