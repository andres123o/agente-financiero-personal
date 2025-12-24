# 🔗 ¿Qué es un Webhook de Telegram?

## Concepto Simple

Un **webhook** es como darle a Telegram tu dirección (URL) para que cuando alguien escriba a tu bot, Telegram envíe esa información directamente a tu servidor.

## Analogía del Correo

Imagina que tienes un buzón (tu bot de Telegram):
- **Sin webhook**: Tienes que ir constantemente a revisar si hay mensajes nuevos (polling)
- **Con webhook**: El cartero (Telegram) trae los mensajes directamente a tu casa (tu servidor) cuando llegan

## ¿Cómo Funciona?

```
Usuario escribe → Telegram → Webhook (tu servidor) → Tu código procesa → Respuesta al usuario
```

1. **Usuario escribe** un mensaje a tu bot en Telegram
2. **Telegram** recibe el mensaje
3. **Telegram envía** el mensaje a tu webhook (tu URL de servidor)
4. **Tu servidor** recibe el mensaje en `/api/webhook`
5. **Tu código** procesa el mensaje (clasifica, guarda en DB, etc.)
6. **Tu código** envía una respuesta de vuelta a Telegram
7. **Usuario recibe** la respuesta en Telegram

## ¿Por Qué Necesitas Configurarlo?

Sin webhook configurado, Telegram no sabe dónde enviar los mensajes que recibe tu bot. Es como tener un teléfono sin número.

## ¿Cómo Configurarlo?

### Paso 1: Tener tu URL del Servidor

Tienes dos opciones:

#### Opción A: Servidor Local (para pruebas)
Usa **ngrok** para exponer tu servidor local:
```bash
# Ejecuta tu servidor
uvicorn api.index:app --reload

# En otra terminal, ejecuta ngrok
ngrok http 8000
```

Ngrok te dará una URL como: `https://abc123.ngrok.io`

#### Opción B: Servidor en Producción (Vercel)
Después de hacer `vercel`, obtienes una URL como: `https://tu-proyecto.vercel.app`

### Paso 2: Configurar el Webhook

Abre esta URL en tu navegador (reemplaza los valores):

```
https://api.telegram.org/botTU_TOKEN_AQUI/setWebhook?url=https://TU_URL_AQUI/api/webhook
```

**Ejemplo real:**
```
https://api.telegram.org/bot123456789:ABCdefGHIjklMNOpqrsTUVwxyz/setWebhook?url=https://kepler-cfo.vercel.app/api/webhook
```

### Paso 3: Verificar que Funcionó

Abre esta URL para verificar:
```
https://api.telegram.org/botTU_TOKEN_AQUI/getWebhookInfo
```

Deberías ver algo como:
```json
{
  "ok": true,
  "result": {
    "url": "https://tu-url.com/api/webhook",
    "has_custom_certificate": false,
    "pending_update_count": 0
  }
}
```

## Flujo Completo Visual

```
┌─────────────┐
│   Usuario   │
│  en Telegram│
└──────┬──────┘
       │ Escribe: "Gasté 50000"
       ▼
┌─────────────┐
│  Telegram   │
│   Servers   │
└──────┬──────┘
       │ Webhook POST
       │ a tu URL
       ▼
┌─────────────────────────┐
│  Tu Servidor (Vercel)   │
│  /api/webhook           │
│  ┌───────────────────┐  │
│  │ api/index.py      │  │
│  │ - Recibe mensaje  │  │
│  │ - Clasifica       │  │
│  │ - Guarda en DB    │  │
│  │ - Genera respuesta│  │
│  └───────────────────┘  │
└──────┬──────────────────┘
       │ POST a Telegram API
       │ sendMessage
       ▼
┌─────────────┐
│  Telegram   │
│   Servers   │
└──────┬──────┘
       │ Entrega mensaje
       ▼
┌─────────────┐
│   Usuario   │
│  recibe:    │
│ "Gasto      │
│ registrado" │
└─────────────┘
```

## ¿Qué Pasa en Tu Código?

Cuando Telegram envía un mensaje a tu webhook, tu código en `api/index.py` hace esto:

```python
@app.post("/api/webhook")
async def webhook(request: Request):
    # 1. Recibe el mensaje de Telegram
    update = await request.json()
    message = update.get("message")
    user_text = message.get("text")
    
    # 2. Clasifica con OpenAI
    classification = classify_expense(user_text)
    
    # 3. Guarda en base de datos
    insert_transaction(...)
    
    # 4. Genera respuesta
    response_text = generate_response(...)
    
    # 5. Envía respuesta a Telegram
    await send_message(chat_id, response_text)
```

## Comandos Útiles

### Ver información del webhook actual
```
https://api.telegram.org/botTU_TOKEN/getWebhookInfo
```

### Eliminar el webhook (para desactivar)
```
https://api.telegram.org/botTU_TOKEN/deleteWebhook
```

### Configurar webhook
```
https://api.telegram.org/botTU_TOKEN/setWebhook?url=TU_URL/api/webhook
```

## Resumen

- **Webhook** = Dirección donde Telegram envía los mensajes de tu bot
- **Sin webhook** = Tu bot no puede recibir mensajes
- **Con webhook** = Telegram envía mensajes directamente a tu servidor
- **Configuración** = Una sola vez, usando `setWebhook` con tu URL

## Próximos Pasos

1. Despliega tu código en Vercel: `vercel`
2. Obtén tu URL: `https://tu-proyecto.vercel.app`
3. Configura el webhook con la URL completa
4. Prueba enviando un mensaje a tu bot

¡Eso es todo! Una vez configurado, Telegram automáticamente enviará todos los mensajes a tu servidor.

