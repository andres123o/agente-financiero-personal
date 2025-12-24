# Kepler CFO - Telegram Bot Backend

Backend serverless para el bot de Telegram "Kepler CFO" que ayuda a gestionar un presupuesto estricto 40/40/20.

## Stack Tecnológico

- **Python 3.9** + **FastAPI**: Framework web para el webhook
- **OpenAI GPT-4o-mini**: Procesamiento de lenguaje natural y clasificación de gastos
- **Supabase**: Base de datos para transacciones y presupuestos
- **Vercel**: Hosting serverless

## Estructura del Proyecto

```
.
├── api/
│   └── index.py          # Webhook handler principal
├── core/
│   ├── __init__.py
│   ├── brain.py          # Lógica de OpenAI (clasificación y respuestas)
│   ├── db.py             # Operaciones CRUD con Supabase
│   └── telegram.py       # Integración con Telegram API
├── requirements.txt      # Dependencias Python
├── vercel.json           # Configuración de Vercel
└── README.md
```

## Configuración

### Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto con:

```env
# Supabase
SUPABASE_URL=https://mrsfgxnpgjcumaoplrey.supabase.co
SUPABASE_KEY=sb_publishable_1Pk9yRAA3yX3qtbxgwUM1g_qithlrwQ

# OpenAI
OPENAI_API_KEY=tu_api_key_de_openai

# Telegram
TELEGRAM_BOT_TOKEN=tu_token_del_bot_de_telegram
```

### Base de Datos Supabase

Asegúrate de tener las siguientes tablas en Supabase:

#### Tabla `transactions`
```sql
CREATE TABLE transactions (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  amount DECIMAL(10, 2) NOT NULL,
  category VARCHAR(50) NOT NULL,
  description TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### Tabla `budgets`
```sql
CREATE TABLE budgets (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  category VARCHAR(50) UNIQUE NOT NULL,
  monthly_limit DECIMAL(10, 2) NOT NULL,
  current_spent DECIMAL(10, 2) DEFAULT 0,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**Categorías válidas:**
- `fixed_survival`: Comida básica, servicios, arriendo, transporte
- `debt_offensive`: Pagos a deudas por encima del mínimo
- `kepler_growth`: Gastos del negocio (servidores, dominios, ads)
- `networking_life`: Salidas, cafés, cine, ocio
- `stupid_expenses`: Lujos innecesarios, gastos hormiga

## Despliegue en Vercel

1. Instala Vercel CLI:
```bash
npm i -g vercel
```

2. Inicia sesión:
```bash
vercel login
```

3. Despliega:
```bash
vercel
```

4. Configura las variables de entorno en el dashboard de Vercel:
   - Ve a tu proyecto en Vercel
   - Settings → Environment Variables
   - Agrega todas las variables del `.env`

5. Configura el webhook de Telegram:
   - Ve a `https://api.telegram.org/bot<TOKEN>/setWebhook`
   - Reemplaza `<TOKEN>` con tu token de Telegram
   - Reemplaza `<URL>` con tu URL de Vercel: `https://tu-proyecto.vercel.app/api/webhook`

## Uso del Bot

El bot procesa mensajes naturales del usuario:

- **Gastos**: "Gasté 50000 en comida", "Compré un café por 5000"
- **Ingresos**: "Ingresé 200000", "Recibí 500000"
- **Consultas**: "¿Cuánto me queda en fixed_survival?"

El bot clasifica automáticamente los gastos y responde con:
- Alertas si se rompe el presupuesto
- Insultos sarcásticos para gastos tontos
- Felicitaciones para pagos de deudas
- Estado del presupuesto restante

## Desarrollo Local

### Configuración Inicial

1. **Crea un entorno virtual** (IMPORTANTE - no instales en tu Python global):
```bash
# Windows
py -m venv venv

# Linux/Mac
python3 -m venv venv
```

2. **Activa el entorno virtual**:
```bash
# Windows CMD
venv\Scripts\activate.bat

# Windows PowerShell
.\venv\Scripts\Activate.ps1

# Linux/Mac
source venv/bin/activate
```

3. **Instala las dependencias** (solo dentro del venv):
```bash
pip install -r requirements.txt
```

### Ejecutar el Servidor

**Opción 1: Usando los scripts incluidos**
```bash
# Windows CMD
run.bat

# Windows PowerShell
.\run.ps1
```

**Opción 2: Manualmente**
```bash
# Asegúrate de que el venv esté activado (verás "(venv)" en tu prompt)
uvicorn api.index:app --reload
```

El servidor estará disponible en: http://127.0.0.1:8000

### Limpiar Dependencias Globales (si las instalaste por error)

Si instalaste dependencias en tu Python global por error, ejecuta:

```bash
# Windows CMD
DESINSTALAR_GLOBAL.bat

# Windows PowerShell
.\DESINSTALAR_GLOBAL.ps1
```

O manualmente:
```bash
pip uninstall -y python-dotenv fastapi uvicorn openai httpx pydantic
```

3. Usa ngrok para exponer el webhook localmente:
```bash
ngrok http 8000
```

4. Configura el webhook de Telegram con la URL de ngrok.

## Flujo de Procesamiento

1. Usuario envía mensaje a Telegram
2. Telegram envía webhook a `/api/webhook`
3. OpenAI clasifica el mensaje (acción, monto, categoría)
4. Se inserta la transacción en Supabase
5. Se actualiza el presupuesto (`current_spent`)
6. Se calcula el restante (`monthly_limit - current_spent`)
7. OpenAI genera respuesta contextual
8. Se envía respuesta al usuario en Telegram

## Notas Importantes

- El bot es robusto: si no entiende un mensaje, pregunta en lugar de crashear
- Las categorías deben coincidir exactamente con las de la base de datos
- El sistema usa JSON mode de OpenAI para asegurar respuestas estructuradas
- Los montos se manejan en COP (pesos colombianos)

