# 🔍 Guía de Verificación - Kepler CFO

Sigue estos pasos para verificar que todo está configurado correctamente.

## Paso 1: Verificar Variables de Entorno

Abre el archivo `.env` y verifica que todas las variables estén configuradas (no deben tener placeholders como `tu_...`):

```bash
# Debe tener valores reales, no placeholders
SUPABASE_URL=https://mrsfgxnpgjcumaoplrey.supabase.co
SUPABASE_KEY=sb_publishable_1Pk9yRAA3yX3qtbxgwUM1g_qithlrwQ
OPENAI_API_KEY=sk-... (tu clave real)
TELEGRAM_BOT_TOKEN=123456:ABC... (tu token real)
```

## Paso 2: Verificar Base de Datos Supabase

1. Ve a tu proyecto en Supabase: https://mrsfgxnpgjcumaoplrey.supabase.co
2. Ve a **SQL Editor**
3. Ejecuta el script `database/schema.sql` para crear las tablas
4. Verifica que existan las tablas:
   - `transactions`
   - `budgets`
5. Asegúrate de tener al menos un registro en `budgets` para cada categoría con sus límites mensuales

## Paso 3: Probar Conexiones (Opcional)

Si tienes Python instalado, puedes ejecutar el script de verificación:

```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar verificación
python test_connections.py
```

O prueba manualmente cada servicio:

### Probar Supabase
```python
from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()
client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
result = client.table("budgets").select("*").execute()
print(result.data)
```

### Probar OpenAI
```python
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hola"}]
)
print(response.choices[0].message.content)
```

### Probar Telegram
Abre en tu navegador (reemplaza `TU_TOKEN`):
```
https://api.telegram.org/botTU_TOKEN/getMe
```

Deberías ver información de tu bot en JSON.

## Paso 4: Probar el Servidor Localmente

```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar servidor
uvicorn api.index:app --reload
```

Deberías ver:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

Visita http://127.0.0.1:8000 - deberías ver:
```json
{"status": "ok", "service": "Kepler CFO"}
```

## Paso 5: Configurar Webhook de Telegram (Local)

Si quieres probar localmente, usa ngrok:

```bash
# Instalar ngrok: https://ngrok.com/download
ngrok http 8000
```

Copia la URL HTTPS que ngrok te da (ej: `https://abc123.ngrok.io`)

Configura el webhook:
```
https://api.telegram.org/botTU_TOKEN/setWebhook?url=https://abc123.ngrok.io/api/webhook
```

## Paso 6: Desplegar en Vercel

```bash
# Instalar Vercel CLI
npm i -g vercel

# Desplegar
vercel

# Configurar variables de entorno en Vercel Dashboard
# Settings → Environment Variables
```

Después del despliegue, configura el webhook con tu URL de Vercel:
```
https://api.telegram.org/botTU_TOKEN/setWebhook?url=https://tu-proyecto.vercel.app/api/webhook
```

## Paso 7: Probar el Bot

Envía un mensaje a tu bot en Telegram:
- "Gasté 50000 en comida"
- "Ingresé 200000"
- "¿Cuánto me queda en fixed_survival?"

El bot debería responder automáticamente.

## ✅ Checklist Final

- [ ] Variables de entorno configuradas en `.env`
- [ ] Tablas creadas en Supabase
- [ ] Presupuestos inicializados en la tabla `budgets`
- [ ] OpenAI API key válida
- [ ] Telegram bot token válido
- [ ] Servidor local funciona (opcional)
- [ ] Webhook configurado en Telegram
- [ ] Bot responde a mensajes

## 🆘 Solución de Problemas

### Error: "OPENAI_API_KEY must be set"
- Verifica que el archivo `.env` exista y tenga la variable configurada

### Error: "Budget not found for category"
- Ejecuta el SQL de `database/schema.sql` en Supabase
- Asegúrate de tener registros en la tabla `budgets`

### Error: "Unauthorized" en Telegram
- Verifica que el bot token sea correcto
- Prueba con `getMe` endpoint

### El bot no responde
- Verifica que el webhook esté configurado correctamente
- Revisa los logs en Vercel o en tu servidor local
- Verifica que el endpoint `/api/webhook` esté accesible

