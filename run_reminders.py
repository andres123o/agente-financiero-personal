"""
Script local para enviar recordatorios del Plan Kepler.
100% gratis: corre en tu PC o en cualquier servidor donde lo ejecutes.

Uso: python run_reminders.py

Déjalo corriendo (o úsalo con un gestor de procesos como pm2/supervisor).
Necesita .env con SUPABASE_URL, SUPABASE_KEY, TELEGRAM_BOT_TOKEN.
"""
import asyncio
import os
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

# Timezone (default Colombia)
def get_now():
    tz_name = os.getenv("KEPLER_TZ", "America/Bogota")
    try:
        import pytz
        tz = pytz.timezone(tz_name)
        return datetime.now(tz)
    except Exception:
        return datetime.now()


async def run_reminders():
    from core.db import get_pending_schedule_reminders, mark_reminder_sent
    from core.telegram import send_message

    now = get_now()
    current_date = now.date().isoformat()
    current_weekday = now.weekday()  # 0=Lunes, 6=Domingo

    pending = await get_pending_schedule_reminders(
        current_hour=now.hour,
        current_minute=now.minute,
        current_weekday=current_weekday,
        current_date=current_date,
    )

    sent = 0
    for rem in pending:
        chat_id = rem.get("chat_id")
        message = rem.get("message", "")
        rem_id = rem.get("id")
        if chat_id and message:
            await send_message(chat_id=int(chat_id), text=message)
            await mark_reminder_sent(rem_id, current_date)
            sent += 1
            print(f"[{now.strftime('%H:%M')}] Enviado a {chat_id}: {message[:50]}...")

    return sent


async def main():
    interval_minutes = 15
    print(f"Recordatorios Kepler - cada {interval_minutes} min. Ctrl+C para salir.")
    while True:
        try:
            await run_reminders()
        except Exception as e:
            print(f"Error: {e}")
        await asyncio.sleep(interval_minutes * 60)


if __name__ == "__main__":
    asyncio.run(main())
