# Debug: Recordatorios Kepler

## Flujo completo (paso a paso)

```
1. pg_cron (cada 15 min)
   └─> net.http_post(url)  →  POST a tu API Vercel

2. API /api/cron/reminders
   └─> get_pending_schedule_reminders(hora, minuto, día)
   └─> Para cada pendiente: send_message(chat_id, texto) + mark_reminder_sent()

3. Telegram
   └─> Llega el mensaje al usuario
```

## Checklist de verificación

### ✅ 1. Tabla existe
```sql
SELECT COUNT(*) FROM schedule_reminders;
```
Si da error → ejecuta `database/schedule_reminders.sql`

### ✅ 2. Hay recordatorios (y tienen tu chat_id)
```sql
SELECT id, chat_id, hour, minute, days_of_week, message FROM schedule_reminders;
```
- Si está vacío → di "activar recordatorios" al bot en Telegram
- Si hay filas pero chat_id es 0 o raro → el chat_id viene del webhook cuando envías un mensaje

### ✅ 3. pg_cron tiene tu URL real
```sql
SELECT * FROM cron.job;
```
Revisa que el job llame a `https://TU-PROYECTO.vercel.app/api/cron/reminders` (no el placeholder)

### ✅ 4. CRON_SECRET (si lo usas)
- Si tienes `CRON_SECRET` en Vercel env → el endpoint pide auth
- pg_net NO envía headers por defecto
- Opción A: Quita CRON_SECRET temporalmente para probar
- Opción B: Pasa el secret en la URL: `.../api/cron/reminders?secret=TU_SECRETO`

### ✅ 5. Endpoint de status (sin enviar nada)
```bash
curl "https://TU-URL.vercel.app/api/cron/reminders/status"
```
Muestra: hora actual, timezone, cuántos recordatorios hay en BD, cuántos están "pending" ahora.

### ✅ 6. Probar el endpoint que SÍ envía
```bash
curl -X POST "https://TU-URL.vercel.app/api/cron/reminders"
```
Respuesta esperada: `{"status":"ok","sent":N,"total":N}`

Si N=0 pero hay recordatorios → la hora actual no coincide con ningún recordatorio (solo coinciden en ventana de 15 min)

### ✅ 7. Probar con recordatorio "ahora"
- Ejecuta `database/test_reminder_now.sql` (ajusta chat_id, hour, minute)
- Vuelve a llamar al endpoint
- Deberías recibir el mensaje en Telegram

## Errores comunes

| Error | Causa | Solución |
|-------|-------|----------|
| 403 Unauthorized | CRON_SECRET requiere auth | Quita CRON_SECRET o pasa ?secret=X en la URL del cron |
| sent: 0 siempre | No hay recordatorios o la hora no coincide | "activar recordatorios" + verifica hora Colombia |
| 404 / 500 | URL mal o Vercel no deployado | Verifica la URL y el deploy |
| No llega a Telegram | TELEGRAM_BOT_TOKEN o chat_id mal | Verifica env vars y que el chat_id sea el tuyo |
