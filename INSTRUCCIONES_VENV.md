# 🐍 Instrucciones para Entorno Virtual

## ⚠️ IMPORTANTE: Usa siempre el entorno virtual

**NUNCA instales dependencias en tu Python global.** Siempre usa el entorno virtual del proyecto.

## 📋 Pasos para Configurar

### 1. Crear el Entorno Virtual (solo la primera vez)

```bash
py -m venv venv
```

### 2. Activar el Entorno Virtual

**Windows CMD:**
```bash
venv\Scripts\activate.bat
```

**Windows PowerShell:**
```powershell
.\venv\Scripts\Activate.ps1
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

**✅ Verás `(venv)` al inicio de tu prompt cuando esté activado**

### 3. Instalar Dependencias (solo dentro del venv)

```bash
pip install -r requirements.txt
```

### 4. Ejecutar el Servidor

**Opción fácil - Usa los scripts:**
```bash
# Windows CMD
run.bat

# PowerShell
.\run.ps1
```

**Opción manual:**
```bash
# Asegúrate de que el venv esté activado primero
uvicorn api.index:app --reload
```

## 🧹 Limpiar Dependencias Globales

Si instalaste dependencias en tu Python global por error, ejecuta:

**Windows CMD:**
```bash
DESINSTALAR_GLOBAL.bat
```

**PowerShell:**
```powershell
.\DESINSTALAR_GLOBAL.ps1
```

**O manualmente:**
```bash
pip uninstall -y python-dotenv fastapi uvicorn openai httpx pydantic
```

## ✅ Verificar que Estás en el Venv

Antes de instalar o ejecutar, verifica que veas `(venv)` en tu prompt:

```
(venv) PS C:\Users\DELL\Documents\Agente Financiero Personal>
```

Si NO ves `(venv)`, activa el entorno virtual primero.

## 📝 Comandos Útiles

```bash
# Ver qué está instalado en el venv
pip list

# Desactivar el venv (cuando termines)
deactivate

# Verificar la ubicación de Python
which python  # Linux/Mac
where python  # Windows
```

## 🚨 Problemas Comunes

### "No se puede ejecutar scripts en este sistema"
En PowerShell, ejecuta como administrador:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### "python-dotenv no se encuentra"
Asegúrate de que el venv esté activado antes de instalar.

### "ModuleNotFoundError"
Verifica que instalaste las dependencias DENTRO del venv activado.

