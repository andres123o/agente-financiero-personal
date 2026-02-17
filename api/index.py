"""
FastAPI webhook handler for Telegram bot.
Main entry point for Kepler CFO.
"""
import os
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from core.brain import (
    analyze_intent,
    parse_schedule_reminder,
    classify_financial_action,
    generate_cfo_response,
    generate_spending_advice,
    generate_mentorship_advice,
    generate_transaction_query_response,
    generate_operational_response
)
from core.db import (
    insert_transaction, 
    update_budget_spent, 
    get_budget_status,
    get_all_debts,
    update_debt_balance,
    get_patrimony,
    calculate_monthly_patrimony,
    update_patrimony_end_of_month,
    reset_all_budgets,
    get_complete_financial_state,
    save_conversation_message,
    get_conversation_history,
    get_transactions,
    save_thought_reminder,
    get_thoughts_reminders,
    update_thought_completed,
    get_pending_schedule_reminders,
    mark_reminder_sent,
    ensure_default_reminders_for_chat,
    save_custom_schedule_reminder,
)
from core.telegram import send_message

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Kepler CFO Telegram Bot")


def parse_date_query(text: str) -> Optional[str]:
    """
    Parse Spanish date queries like "hoy", "ayer", "hace dos días", "viernes pasado", "hace dos meses"
    Returns date string in format 'YYYY-MM-DD', 'today', 'yesterday', or None
    """
    from datetime import datetime, timedelta
    import re
    
    text_lower = text.lower().strip()
    now = datetime.now()
    
    # Días específicos
    if "hoy" in text_lower or "today" in text_lower:
        return "today"
    elif "ayer" in text_lower or "yesterday" in text_lower:
        return "yesterday"
    elif "mañana" in text_lower or "tomorrow" in text_lower:
        tomorrow = (now + timedelta(days=1)).date().isoformat()
        return tomorrow
    
    # Números en palabras
    number_words = {
        'uno': 1, 'dos': 2, 'tres': 3, 'cuatro': 4, 'cinco': 5,
        'seis': 6, 'siete': 7, 'ocho': 8, 'nueve': 9, 'diez': 10,
        'once': 11, 'doce': 12, 'trece': 13, 'catorce': 14, 'quince': 15,
        'veinte': 20, 'treinta': 30
    }
    
    # "Hace X días" (números o palabras)
    match = re.search(r'hace\s+(\d+)\s+d[ií]a[s]?', text_lower)
    if match:
        days_ago = int(match.group(1))
        target_date = (now - timedelta(days=days_ago)).date().isoformat()
        return target_date
    
    # "Hace dos días", "hace tres días", etc. (palabras)
    for word, num in number_words.items():
        if f'hace {word} día' in text_lower or f'hace {word} dias' in text_lower:
            target_date = (now - timedelta(days=num)).date().isoformat()
            return target_date
    
    # "Hace X semanas"
    match = re.search(r'hace\s+(\d+)\s+semana[s]?', text_lower)
    if match:
        weeks_ago = int(match.group(1))
        target_date = (now - timedelta(weeks=weeks_ago)).date().isoformat()
        return target_date
    
    # "Hace dos semanas", etc. (palabras)
    for word, num in number_words.items():
        if f'hace {word} semana' in text_lower:
            target_date = (now - timedelta(weeks=num)).date().isoformat()
            return target_date
    
    # "Hace X meses"
    match = re.search(r'hace\s+(\d+)\s+mes[es]?', text_lower)
    if match:
        months_ago = int(match.group(1))
        # Aproximación: 30 días por mes
        target_date = (now - timedelta(days=months_ago * 30)).date().isoformat()
        return target_date
    
    # "Hace dos meses", etc. (palabras)
    for word, num in number_words.items():
        if f'hace {word} mes' in text_lower:
            target_date = (now - timedelta(days=num * 30)).date().isoformat()
            return target_date
    
    # Días de la semana pasados
    days_of_week = {
        'lunes': 0, 'martes': 1, 'miércoles': 2, 'miercoles': 2,
        'jueves': 3, 'viernes': 4, 'sábado': 5, 'sabado': 5, 'domingo': 6
    }
    
    for day_name, day_num in days_of_week.items():
        if day_name in text_lower:
            current_weekday = now.weekday()
            if "pasado" in text_lower or "pasada" in text_lower:
                # Día pasado: calcular cuántos días atrás está ese día
                days_since = (current_weekday - day_num) % 7
                if days_since == 0:
                    days_since = 7  # Si es hoy, buscar el de la semana pasada
                target_date = (now - timedelta(days=days_since)).date().isoformat()
                return target_date
            elif "próximo" in text_lower or "proximo" in text_lower or "siguiente" in text_lower:
                # Día próximo: calcular cuántos días adelante está ese día
                days_until = (day_num - current_weekday) % 7
                if days_until == 0:
                    days_until = 7  # Si es hoy, buscar el próximo
                target_date = (now + timedelta(days=days_until)).date().isoformat()
                return target_date
    
    # "La semana pasada" o "semana pasada"
    if "semana pasada" in text_lower or "la semana pasada" in text_lower:
        # Hace 7 días
        target_date = (now - timedelta(days=7)).date().isoformat()
        return target_date
    
    # "El mes pasado" o "mes pasado"
    if "mes pasado" in text_lower or "el mes pasado" in text_lower:
        # Aproximación: hace 30 días
        target_date = (now - timedelta(days=30)).date().isoformat()
        return target_date
    
    # Intentar parsear fecha en formato DD/MM/YYYY o DD-MM-YYYY
    date_patterns = [
        r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})',
        r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})',
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, text_lower)
        if match:
            try:
                if len(match.group(1)) == 4:  # YYYY-MM-DD
                    year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                else:  # DD-MM-YYYY
                    day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                target_date = datetime(year, month, day).date().isoformat()
                return target_date
            except:
                pass
    
    return None


def detect_debt_payment(description: str, category: str, amount: float) -> Optional[str]:
    """
    Detect if a payment is for Lumni or ICETEX debt.
    
    Args:
        description: Transaction description
        category: Transaction category
        amount: Payment amount
        
    Returns:
        'Lumni' or 'ICETEX' if detected, None otherwise
    """
    desc_lower = description.lower()
    
    # Check for explicit mentions
    if "lumni" in desc_lower:
        return "Lumni"
    if "icetex" in desc_lower:
        return "ICETEX"
    
    # Check by amount (approximate minimum payments)
    # ICETEX: ~$565k, Lumni: ~$546k
    if category == "fixed_survival":
        if 560000 <= amount <= 570000:
            return "ICETEX"
        elif 540000 <= amount <= 550000:
            return "Lumni"
    
    return None


def verify_telegram_token(request: Request) -> bool:
    """
    Verify that the request comes from Telegram.
    In production, you should verify the secret token.
    """
    # For now, we'll accept all requests
    # In production, verify TELEGRAM_BOT_TOKEN matches
    return True


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "Kepler CFO"}


@app.get("/api/cron/reminders/status")
async def cron_reminders_status():
    """
    Debug: muestra hora actual, timezone, y cuántos recordatorios hay.
    No envía nada, solo información.
    """
    from datetime import datetime, timezone
    try:
        tz_name = os.getenv("KEPLER_TZ", "America/Bogota")
        try:
            import pytz
            tz = pytz.timezone(tz_name)
        except Exception:
            tz = timezone.utc
        now = datetime.now(tz)
        current_date = now.date().isoformat()
        current_weekday = now.weekday()

        # Contar recordatorios en BD (sin filtrar por hora)
        headers = {
            "apikey": os.getenv("SUPABASE_KEY"),
            "Authorization": f"Bearer {os.getenv('SUPABASE_KEY')}",
        }
        import httpx
        url = f"{os.getenv('SUPABASE_URL').rstrip('/')}/rest/v1/schedule_reminders"
        async with httpx.AsyncClient() as client:
            r = await client.get(url, params={"select": "id,chat_id,hour,minute,days_of_week"}, headers=headers)
            total_in_db = len(r.json()) if r.status_code == 200 and isinstance(r.json(), list) else 0

        pending = await get_pending_schedule_reminders(
            current_hour=now.hour,
            current_minute=now.minute,
            current_weekday=current_weekday,
            current_date=current_date,
        )

        return {
            "status": "ok",
            "now": now.strftime("%Y-%m-%d %H:%M:%S"),
            "tz": tz_name,
            "weekday": current_weekday,
            "date": current_date,
            "total_reminders_in_db": total_in_db,
            "pending_right_now": len(pending),
            "would_send": [{"chat_id": r.get("chat_id"), "message_preview": (r.get("message", "")[:40] + "...")} for r in pending],
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.api_route("/api/cron/reminders", methods=["GET", "POST"])
async def cron_reminders(request: Request):
    """
    Endpoint para recordatorios proactivos. Llamado por cron cada 15 min.
    Envía recordatorios según el horario del Plan Kepler.
    Protegido por CRON_SECRET en header o query.
    """
    from datetime import datetime
    try:
        cron_secret = os.getenv("CRON_SECRET")
        if cron_secret:
            auth = request.headers.get("Authorization") or request.query_params.get("secret", "")
            if auth != f"Bearer {cron_secret}" and auth != cron_secret:
                raise HTTPException(status_code=403, detail="Unauthorized")
        
        tz_name = os.getenv("KEPLER_TZ", "America/Bogota")
        try:
            import pytz
            tz = pytz.timezone(tz_name)
        except Exception:
            from datetime import timezone
            tz = timezone.utc
        now = datetime.now(tz)
        current_date = now.date().isoformat()
        current_weekday = now.weekday()  # 0=Monday, 6=Sunday
        
        pending = await get_pending_schedule_reminders(
            current_hour=now.hour,
            current_minute=now.minute,
            current_weekday=current_weekday,
            current_date=current_date
        )
        
        sent = 0
        for rem in pending:
            chat_id = rem.get("chat_id")
            message = rem.get("message", "")
            rem_id = rem.get("id")
            is_one_time = rem.get("specific_date") is not None
            if chat_id and message:
                await send_message(chat_id=int(chat_id), text=message)
                await mark_reminder_sent(rem_id, current_date, is_one_time=is_one_time)
                sent += 1
        
        return JSONResponse({"status": "ok", "sent": sent, "total": len(pending)})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cron reminders error: {str(e)}", exc_info=True)
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.post("/api/webhook")
async def webhook(request: Request):
    """
    Main webhook handler for Telegram updates.
    
    Flow:
    1. Receive Telegram update
    2. Extract user message
    3. Classify with OpenAI
    4. Process transaction (if expense/income)
    5. Update budget
    6. Generate response
    7. Return response (Telegram will send it)
    """
    try:
        # Verify request
        if not verify_telegram_token(request):
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        # Parse Telegram update
        update = await request.json()
        logger.info(f"Received update: {update}")
        
        # Extract message
        message = update.get("message")
        if not message:
            # Handle other update types (edited_message, callback_query, etc.)
            return JSONResponse({"status": "ok", "message": "Update type not supported"})
        
        chat_id = message.get("chat", {}).get("id")
        if not chat_id:
            logger.warning("No chat_id found in message")
            return JSONResponse({"status": "ok", "message": "No chat_id found"})
        
        user_text = message.get("text", "").strip()
        
        if not user_text:
            if chat_id:
                await send_message(
                    chat_id=chat_id,
                    text="Por favor, envía un mensaje de texto. Ejemplo: 'Gasté 50000 en comida'"
                )
            return JSONResponse({
                "status": "ok",
                "response": "Por favor, envía un mensaje de texto. Ejemplo: 'Gasté 50000 en comida'"
            })
        
        # Step 1: Get conversation history (más mensajes para mentoría y operativo)
        conversation_history = []
        try:
            conversation_history = await get_conversation_history(chat_id, limit=20)
            logger.info(f"Retrieved {len(conversation_history)} messages from history")
        except Exception as e:
            logger.warning(f"Could not retrieve conversation history: {str(e)}")
        
        # Step 2: Analyze intent (Router Layer) - Now returns FINANCE, MENTORSHIP, or REMINDER
        logger.info(f"Analyzing intent for message: {user_text}")
        intent = analyze_intent(user_text)
        logger.info(f"Intent: {intent}")
        
        response_text = ""
        
        # Step 3: Route to appropriate layer
        if intent == "REMINDER":
            # Route to Reminder Layer - handles saving and querying thoughts/ideas/reminders/notes
            logger.info(f"Routing to Reminder Layer")
            
            desc_lower = user_text.lower()
            
            # Custom schedule reminder: "recuérdame a las 4 tal cosa"
            if ("recuérdame a las" in desc_lower or "recuerdame a las" in desc_lower or "recuerdame a la" in desc_lower) and chat_id:
                parsed = parse_schedule_reminder(user_text)
                if parsed:
                    saved = await save_custom_schedule_reminder(
                        chat_id=int(chat_id),
                        hour=parsed["hour"],
                        minute=parsed["minute"],
                        message=parsed["message"],
                        specific_date=parsed.get("specific_date"),
                    )
                    if saved:
                        min_str = f":{parsed['minute']:02d}" if parsed["minute"] else ""
                        fecha = f" el {parsed['specific_date']}" if parsed.get("specific_date") else ""
                        response_text = f"✅ Listo. Te recordaré a las {parsed['hour']}{min_str}{fecha}: {parsed['message']}"
                    else:
                        response_text = "No pude guardar el recordatorio. Verifica que la tabla schedule_reminders tenga la columna specific_date (ejecuta database/add_specific_date.sql)."
                else:
                    response_text = "No entendí la hora. Ejemplo: recuérdame a las 4 que tengo reunión"
            else:
                # Check if it starts with "reminder:" or "recordatorio:" prefix
                query_text = user_text
                if desc_lower.startswith("reminder:"):
                    query_text = user_text[9:].strip()  # Remove "reminder:"
                    desc_lower = query_text.lower()
                elif desc_lower.startswith("recordatorio:"):
                    query_text = user_text[13:].strip()  # Remove "recordatorio:"
                    desc_lower = query_text.lower()
                
                # Detect if it's a query (starts with prefix) or save command
                is_query = user_text.lower().startswith("reminder:") or user_text.lower().startswith("recordatorio:")
                
                if is_query:
                    # QUERY MODE: User wants to see reminders/thoughts
                    logger.info(f"Detected query request in REMINDER layer - query_text: '{query_text}'")
                    
                    try:
                        # Parse date from query (use query_text which has the prefix removed)
                        date_filter = parse_date_query(query_text)
                        logger.info(f"Parsed date filter: {date_filter}")
                        
                        # Extract type filter if mentioned
                        query_thought_type = None
                        if "recordatorio" in desc_lower or "reminder" in desc_lower:
                            query_thought_type = "reminder"
                        elif "idea" in desc_lower:
                            query_thought_type = "idea"
                        elif "nota" in desc_lower or "note" in desc_lower:
                            query_thought_type = "note"
                        elif "pensamiento" in desc_lower or "thought" in desc_lower:
                            query_thought_type = "thought"
                        
                        # Get thoughts/reminders
                        chat_id_int = int(chat_id) if chat_id else None
                        if not chat_id_int:
                            response_text = f"Error: Invalid chat_id: {chat_id}"
                        else:
                            thoughts = await get_thoughts_reminders(
                                chat_id=chat_id_int,
                                date=date_filter,
                                thought_type=query_thought_type,
                                limit=50
                            )
                            
                            logger.info(f"Found {len(thoughts)} thoughts/reminders")
                            
                            if not thoughts:
                                # Formatear mensaje según el filtro
                                date_msg = ""
                                if date_filter:
                                    if date_filter == "today":
                                        date_msg = " de hoy"
                                    elif date_filter == "yesterday":
                                        date_msg = " de ayer"
                                    else:
                                        date_msg = f" del {date_filter}"
                                type_msg = ""
                                if query_thought_type:
                                    type_names = {
                                        "reminder": "recordatorios",
                                        "idea": "ideas",
                                        "note": "notas",
                                        "thought": "pensamientos"
                                    }
                                    type_msg = f" {type_names.get(query_thought_type, 'elementos')}"
                                response_text = f"📭 No encontré{type_msg}{date_msg}."
                            else:
                                # Format response
                                type_names = {
                                    "reminder": "📅 Recordatorio",
                                    "idea": "💡 Idea",
                                    "note": "📝 Nota",
                                    "thought": "💭 Pensamiento"
                                }
                                
                                # Group by type if no specific type filter
                                if not query_thought_type:
                                    grouped = {}
                                    for thought in thoughts:
                                        t_type = thought.get("type", "thought")
                                        if t_type not in grouped:
                                            grouped[t_type] = []
                                        grouped[t_type].append(thought)
                                    
                                    response_parts = []
                                    for t_type, items in grouped.items():
                                        type_name = type_names.get(t_type, "📌 Elemento")
                                        response_parts.append(f"\n{type_name} ({len(items)}):")
                                        for item in items[:10]:  # Max 10 per type
                                            content = item.get("content", "Sin contenido")
                                            created = item.get("created_at", "")
                                            reminder_date_str = item.get("reminder_date", "")
                                            
                                            # Format date
                                            date_str = ""
                                            if reminder_date_str:
                                                date_str = f" [📅 {reminder_date_str}]"
                                            elif created:
                                                try:
                                                    from datetime import datetime
                                                    created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                                                    date_str = f" [{created_dt.strftime('%d/%m/%Y')}]"
                                                except:
                                                    pass
                                            
                                            response_parts.append(f"  • {content}{date_str}")
                                    
                                    response_text = "📋 Tus recordatorios/pensamientos:\n" + "\n".join(response_parts)
                                else:
                                    # Single type, show all
                                    type_name = type_names.get(query_thought_type, "📌 Elemento")
                                    response_parts = [f"\n{type_name} ({len(thoughts)}):"]
                                    
                                    for item in thoughts[:20]:  # Max 20 items
                                        content = item.get("content", "Sin contenido")
                                        created = item.get("created_at", "")
                                        reminder_date_str = item.get("reminder_date", "")
                                        
                                        # Format date
                                        date_str = ""
                                        if reminder_date_str:
                                            date_str = f" [📅 {reminder_date_str}]"
                                        elif created:
                                            try:
                                                from datetime import datetime
                                                created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                                                date_str = f" [{created_dt.strftime('%d/%m/%Y')}]"
                                            except:
                                                pass
                                        
                                        response_parts.append(f"  • {content}{date_str}")
                                    
                                    response_text = f"📋 {type_name}s encontrados:\n" + "\n".join(response_parts)
                                
                                if len(thoughts) > 20:
                                    response_text += f"\n\n... y {len(thoughts) - 20} más"
                    
                    except Exception as e:
                        logger.error(f"Error querying thoughts: {str(e)}", exc_info=True)
                        response_text = f"❌ Error consultando recordatorios: {str(e)}"
                else:
                    # SAVE MODE: User wants to save a thought/reminder/idea/note
                    logger.info(f"Detected save request in REMINDER layer")
                    
                    # Extract type from description
                    thought_type = "thought"  # default
                    
                    if "recordatorio" in desc_lower or "reminder" in desc_lower:
                        thought_type = "reminder"
                    elif "idea" in desc_lower:
                        thought_type = "idea"
                    elif "nota" in desc_lower or "note" in desc_lower:
                        thought_type = "note"
                    elif "pensamiento" in desc_lower or "thought" in desc_lower:
                        thought_type = "thought"
                    
                    # Extract date if mentioned (for reminders)
                    reminder_date = None
                    from datetime import datetime, timedelta
                    if "mañana" in desc_lower or "tomorrow" in desc_lower:
                        reminder_date = (datetime.now() + timedelta(days=1)).date().isoformat()
                    elif "hoy" in desc_lower or "today" in desc_lower:
                        reminder_date = datetime.now().date().isoformat()
                    
                    # Extract content - mejor lógica para preservar el contenido
                    content = user_text.strip()
                    
                    # Remover comandos del inicio de manera más inteligente
                    content_lower = content.lower()
                    
                    # Patrones comunes al inicio
                    if content_lower.startswith("guarda esta idea "):
                        content = content[17:].strip()
                    elif content_lower.startswith("guarda este idea "):
                        content = content[17:].strip()
                    elif content_lower.startswith("guarda esta "):
                        content = content[12:].strip()
                    elif content_lower.startswith("guarda este "):
                        content = content[12:].strip()
                    elif content_lower.startswith("guarda idea "):
                        content = content[12:].strip()
                    elif content_lower.startswith("guarda recordatorio "):
                        content = content[20:].strip()
                    elif content_lower.startswith("guarda pensamiento "):
                        content = content[19:].strip()
                    elif content_lower.startswith("guarda nota "):
                        content = content[12:].strip()
                    elif content_lower.startswith("guarda "):
                        content = content[7:].strip()
                    
                    # Remover "en la base de datos" si está presente
                    content = content.replace("en la base de datos", "").replace("en la bd", "").strip()
                    content = content.replace(":", "").strip()  # Remover dos puntos al final
                    
                    # Si después de remover el comando no queda nada, usar el texto original
                    if not content or len(content.strip()) == 0:
                        content = user_text.strip()
                        # Remover solo "guarda" del inicio si está
                        if content_lower.startswith("guarda "):
                            content = content[7:].strip()
                        # Si aún está vacío, usar el texto completo
                        if not content:
                            content = user_text.strip()
                    
                    # Validar que content no esté vacío
                    if not content or len(content.strip()) == 0:
                        content = user_text.strip()  # Usar el texto original como último recurso
                        if not content:
                            content = "Sin contenido"  # Fallback mínimo
                    
                    logger.info(f"Final content to save: '{content}' (length: {len(content)})")
                    
                    # Ensure chat_id is an integer
                    chat_id_int = int(chat_id) if chat_id else None
                    if not chat_id_int:
                        response_text = f"Error: Invalid chat_id: {chat_id}"
                    else:
                        logger.info(f"Attempting to save - chat_id: {chat_id_int} (type: {type(chat_id_int)}), content: '{content}' (length: {len(content)}), type: {thought_type}, reminder_date: {reminder_date}")
                    
                    try:
                        # Save thought/reminder
                        saved = await save_thought_reminder(
                            chat_id=chat_id_int,
                            content=content,
                            thought_type=thought_type,
                            reminder_date=reminder_date
                        )
                        
                        logger.info(f"Successfully saved thought - Response from DB: {saved}")
                        if not saved or (isinstance(saved, dict) and not saved.get('id')):
                            logger.warning(f"Save operation may have failed - no ID returned: {saved}")
                        
                        type_names = {
                            "reminder": "recordatorio",
                            "idea": "idea",
                            "note": "nota",
                            "thought": "pensamiento"
                        }
                        type_name = type_names.get(thought_type, "pensamiento")
                        
                        response_text = f"✅ Guardado exitosamente\n\n{type_name.capitalize()}: {content}"
                        if reminder_date:
                            response_text += f"\n\n📅 Recordatorio para: {reminder_date}"
                    except Exception as e:
                        logger.error(f"Error saving thought: {str(e)}", exc_info=True)
                        response_text = f"❌ Error guardando el pensamiento: {str(e)}"
        
        elif intent == "MENTORSHIP":
            # Route to Mentorship Layer - 100% mentoria, sin contexto financiero
            logger.info(f"Routing to Mentorship Layer")
            try:
                response_text = generate_mentorship_advice(user_text, conversation_history=conversation_history)
            except Exception as e:
                logger.error(f"Error generating mentorship advice: {str(e)}")
                response_text = f"Error procesando tu mensaje: {str(e)}"
        
        elif intent == "OPERATIONAL":
            # Route to Operational Layer - gestión del tiempo, plan Kepler, reorganización
            logger.info(f"Routing to Operational Layer")
            try:
                chat_id_int = int(chat_id) if chat_id else None
                user_lower = user_text.lower().strip()
                activate_keywords = ["activar recordatorios", "activa recordatorios", "quiero recordatorios", "activa los recordatorios", "recordatorios del plan"]
                if chat_id_int and any(kw in user_lower for kw in activate_keywords):
                    inserted = await ensure_default_reminders_for_chat(chat_id_int)
                    if inserted > 0:
                        response_text = f"✅ Recordatorios activados. Te enviaré {inserted} recordatorios según tu plan (5:50, 6:00, 8:00, 5PM, 10PM, y domingo música). Configura un cron que llame a /api/cron/reminders cada 15 min."
                    else:
                        response_text = "Ya tienes los recordatorios activados. Te llegarán según el horario del plan."
                else:
                    thoughts_context = []
                    if chat_id_int:
                        thoughts_context = await get_thoughts_reminders(
                            chat_id=chat_id_int,
                            date=None,
                            thought_type=None,
                            limit=10
                        )
                    response_text = generate_operational_response(
                        user_message=user_text,
                        conversation_history=conversation_history,
                        thoughts_context=thoughts_context
                    )
            except Exception as e:
                logger.error(f"Error generating operational response: {str(e)}", exc_info=True)
                if "schedule_reminders" in str(e).lower() or "relation" in str(e).lower():
                    response_text = "Primero crea la tabla schedule_reminders en Supabase (database/schedule_reminders.sql) y vuelve a intentar."
                else:
                    response_text = f"Error procesando tu mensaje operativo: {str(e)}"
        
        else:  # intent == "FINANCE"
            # Route to Finance Layer (CFO)
            logger.info(f"Routing to Finance Layer")
            
            # Classify financial action (save_thought is now handled before intent analysis)
            classification = classify_financial_action(user_text)
            logger.info(f"Classification from LLM: {classification}")
            
            action = classification.get("action", "unknown")
            amount = float(classification.get("amount", 0))
            category = classification.get("category")
            description = classification.get("description", "")
            
            logger.info(f"Action detected: {action}, description: {description}, chat_id: {chat_id}, user_text: {user_text}")
            
            # Step 3: Handle different financial actions
            budget_status = None
            
            if action == "unknown":
                # OpenAI couldn't understand the message
                response_text = description or "No entendí. Si es dinero, sé específico (ej: 'Gasté 20k'). Si es consejo, dime qué sientes."
            
            elif action == "check_budget":
                # User wants to check budget
                if category:
                    budget_status = await get_budget_status(category)
                    response_text = generate_cfo_response(
                        action=action,
                        amount=0,
                        category=category,
                        description="Consulta de presupuesto",
                        budget_status=budget_status,
                        conversation_history=conversation_history
                    )
                else:
                    response_text = "¿Qué categoría quieres consultar? (fixed_survival, debt_offensive, kepler_growth, networking_life, stupid_expenses)"
            
            elif action == "income":
                # Handle income
                try:
                    await insert_transaction(amount=amount, category="income", description=description, transaction_type="income")
                    response_text = generate_cfo_response(
                        action=action,
                        amount=amount,
                        category=None,
                        description=description,
                        budget_status=None,
                        conversation_history=conversation_history
                    )
                except Exception as e:
                    logger.error(f"Error processing income: {str(e)}")
                    response_text = f"Error registrando el ingreso: {str(e)}"
            
            elif action == "expense":
                # Handle expense
                if not category:
                    response_text = "No pude determinar la categoría del gasto. Por favor, sé más específico."
                elif amount <= 0:
                    response_text = "El monto debe ser mayor a 0. Por favor, indica cuánto gastaste."
                else:
                    try:
                        # Step 3: Insert transaction
                        await insert_transaction(
                            amount=amount,
                            category=category,
                            description=description,
                            transaction_type="expense"
                        )
                        
                        # Step 4: Update budget
                        await update_budget_spent(category=category, amount=amount)
                        
                        # Step 4.5: Check if this is a debt payment and update debt
                        # Update debt for both fixed_survival (monthly) and debt_offensive (extraordinary)
                        debt_name = detect_debt_payment(description, category, amount)
                        if debt_name:
                            try:
                                await update_debt_balance(debt_name, amount)
                                logger.info(f"Updated {debt_name} debt balance by {amount} (category: {category})")
                            except Exception as e:
                                logger.warning(f"Could not update debt balance: {str(e)}")
                        # Also check if debt_offensive mentions a specific debt
                        elif category == "debt_offensive":
                            desc_lower = description.lower()
                            if "lumni" in desc_lower:
                                try:
                                    await update_debt_balance("Lumni", amount)
                                    logger.info(f"Updated Lumni debt balance by {amount} (extraordinary payment)")
                                except Exception as e:
                                    logger.warning(f"Could not update Lumni debt balance: {str(e)}")
                            elif "icetex" in desc_lower:
                                try:
                                    await update_debt_balance("ICETEX", amount)
                                    logger.info(f"Updated ICETEX debt balance by {amount} (extraordinary payment)")
                                except Exception as e:
                                    logger.warning(f"Could not update ICETEX debt balance: {str(e)}")
                        
                        # Step 5: Get budget status
                        budget_status = await get_budget_status(category)
                        
                        # Step 6: Generate response
                        response_text = generate_cfo_response(
                            action=action,
                            amount=amount,
                            category=category,
                            description=description,
                            budget_status=budget_status,
                            conversation_history=conversation_history
                        )
                        
                    except Exception as e:
                        logger.error(f"Error processing expense: {str(e)}")
                        response_text = f"Error procesando el gasto: {str(e)}"
            
            elif action == "check_debt":
                # User wants to check debt status
                try:
                    debts = await get_all_debts()
                    if not debts:
                        response_text = "No se encontraron deudas registradas."
                    else:
                        debt_info = []
                        total_debt = 0
                        for debt in debts:
                            name = debt.get("name", "Unknown")
                            current = float(debt.get("current_balance", 0) or 0)
                            initial = float(debt.get("initial_balance", 0) or 0)
                            paid = initial - current
                            total_debt += current
                            debt_info.append(f"{name}: ${current:,.0f} COP (Pagado: ${paid:,.0f})")
                        
                        response_text = "💳 ESTADO DE DEUDAS:\n\n"
                        response_text += "\n".join(debt_info)
                        response_text += f"\n\nTotal adeudado: ${total_debt:,.0f} COP"
                except Exception as e:
                    logger.error(f"Error getting debt status: {str(e)}")
                    response_text = f"Error consultando deudas: {str(e)}"
            
            elif action == "check_patrimony":
                # User wants to check patrimony
                try:
                    monthly_status = await calculate_monthly_patrimony()
                    patrimony = await get_patrimony()
                    
                    current_patrimony = float(patrimony.get("current_balance", 0) or 0) if patrimony else 0
                    monthly_income = monthly_status.get("monthly_income", 0)
                    monthly_expenses = monthly_status.get("monthly_expenses", 0)
                    remaining = monthly_status.get("remaining_this_month", 0)
                    projected = monthly_status.get("projected_patrimony", current_patrimony)
                    
                    response_text = "💰 PATRIMONIO:\n\n"
                    response_text += f"Patrimonio acumulado: ${current_patrimony:,.0f} COP\n"
                    response_text += f"\nEste mes:\n"
                    response_text += f"  Ingresos: ${monthly_income:,.0f} COP\n"
                    response_text += f"  Gastos: ${monthly_expenses:,.0f} COP\n"
                    response_text += f"  Queda: ${remaining:,.0f} COP\n"
                    response_text += f"\nProyección al final del mes: ${projected:,.0f} COP"
                except Exception as e:
                    logger.error(f"Error getting patrimony: {str(e)}")
                    response_text = f"Error consultando patrimonio: {str(e)}"
            
            elif action == "financial_summary":
                # User wants complete financial summary
                try:
                    from datetime import datetime
                    
                    # Get debts
                    debts = await get_all_debts()
                    total_debt = sum(float(d.get("current_balance", 0) or 0) for d in debts)
                    initial_debt_total = sum(float(d.get("initial_balance", 0) or 0) for d in debts)
                    debt_paid = initial_debt_total - total_debt
                    
                    # Get patrimony
                    monthly_status = await calculate_monthly_patrimony()
                    patrimony = await get_patrimony()
                    current_patrimony = float(patrimony.get("current_balance", 0) or 0) if patrimony else 0
                    initial_patrimony = float(patrimony.get("initial_balance", 0) or 0) if patrimony else 0
                    patrimony_growth = current_patrimony - initial_patrimony
                    
                    # Get monthly data
                    monthly_income = monthly_status.get("monthly_income", 0)
                    monthly_expenses = monthly_status.get("monthly_expenses", 0)
                    remaining_this_month = monthly_status.get("remaining_this_month", 0)
                    projected_patrimony = monthly_status.get("projected_patrimony", current_patrimony)
                    
                    # Get all budgets with details
                    budget_categories = ["fixed_survival", "debt_offensive", "kepler_growth", "networking_life", "stupid_expenses"]
                    category_names = {
                        "fixed_survival": "Gastos Fijos/Sobrevivencia",
                        "debt_offensive": "Pagos Extra Deuda",
                        "kepler_growth": "Inversión Negocio",
                        "networking_life": "Vida Social/Networking",
                        "stupid_expenses": "Gastos Innecesarios"
                    }
                    
                    budgets_detail = []
                    total_spent = 0
                    total_limit = 0
                    for cat in budget_categories:
                        try:
                            budget = await get_budget_status(cat)
                            spent = float(budget.get('current_spent', 0) or 0)
                            limit = float(budget.get('monthly_limit', 0) or 0)
                            remaining = budget.get('remaining', 0)
                            percentage = (spent / limit * 100) if limit > 0 else 0
                            total_spent += spent
                            total_limit += limit
                            budgets_detail.append({
                                "name": category_names.get(cat, cat),
                                "category": cat,
                                "spent": spent,
                                "limit": limit,
                                "remaining": remaining,
                                "percentage": percentage
                            })
                        except:
                            pass
                    
                    # Get current date info
                    today = datetime.now()
                    day_of_month = today.day
                    days_in_month = (datetime(today.year, today.month + 1, 1) - datetime(today.year, today.month, 1)).days if today.month < 12 else (datetime(today.year + 1, 1, 1) - datetime(today.year, today.month, 1)).days
                    month_progress = (day_of_month / days_in_month) * 100
                    
                    # Build comprehensive report
                    response_text = "📊 REPORTE FINANCIERO GENERAL\n"
                    response_text += f"📅 Fecha: {today.strftime('%d/%m/%Y')} (Día {day_of_month} de {days_in_month} - {month_progress:.0f}% del mes)\n"
                    response_text += "═" * 40 + "\n\n"
                    
                    # 1. PATRIMONIO
                    response_text += "💰 PATRIMONIO\n"
                    response_text += "─" * 40 + "\n"
                    response_text += f"Patrimonio Inicial:  ${initial_patrimony:,.0f} COP\n"
                    response_text += f"Patrimonio Actual:   ${current_patrimony:,.0f} COP\n"
                    response_text += f"Crecimiento Total:   ${patrimony_growth:+,.0f} COP\n"
                    if patrimony_growth != 0:
                        growth_pct = (patrimony_growth / initial_patrimony * 100) if initial_patrimony > 0 else 0
                        response_text += f"                     ({growth_pct:+.1f}% desde el inicio)\n"
                    response_text += "\n"
                    
                    # 2. ESTE MES (DETALLADO)
                    response_text += "📆 ESTE MES (Hasta hoy)\n"
                    response_text += "─" * 40 + "\n"
                    response_text += f"Ingresos del mes:    ${monthly_income:,.0f} COP\n"
                    response_text += f"Gastos del mes:      ${monthly_expenses:,.0f} COP\n"
                    response_text += f"Resta este mes:      ${remaining_this_month:+,.0f} COP\n"
                    
                    if monthly_income > 0:
                        expense_ratio = (monthly_expenses / monthly_income * 100)
                        response_text += f"Gasto/Ingreso:       {expense_ratio:.1f}%\n"
                    
                    if remaining_this_month > 0:
                        response_text += f"Proyección fin mes:  ${projected_patrimony:,.0f} COP\n"
                    else:
                        response_text += f"⚠️  Gastaste más de lo que ingresaste\n"
                    response_text += "\n"
                    
                    # 3. DEUDAS
                    response_text += "💳 DEUDAS\n"
                    response_text += "─" * 40 + "\n"
                    for debt in debts:
                        name = debt.get("name", "Unknown")
                        current = float(debt.get("current_balance", 0) or 0)
                        initial = float(debt.get("initial_balance", 0) or 0)
                        paid = initial - current
                        paid_pct = (paid / initial * 100) if initial > 0 else 0
                        response_text += f"{name}:\n"
                        response_text += f"  Saldo inicial:    ${initial:,.0f} COP\n"
                        response_text += f"  Saldo actual:     ${current:,.0f} COP\n"
                        response_text += f"  Pagado:           ${paid:,.0f} COP ({paid_pct:.1f}%)\n"
                        response_text += f"  Resta:            ${current:,.0f} COP\n"
                    response_text += f"\nTotal Deudas:        ${total_debt:,.0f} COP\n"
                    response_text += f"Total Pagado:        ${debt_paid:,.0f} COP\n"
                    response_text += "\n"
                    
                    # 4. PRESUPUESTOS DESGLOSADOS
                    response_text += "📈 PRESUPUESTOS MENSUALES\n"
                    response_text += "─" * 40 + "\n"
                    for budget in budgets_detail:
                        spent = budget["spent"]
                        limit = budget["limit"]
                        remaining = budget["remaining"]
                        pct = budget["percentage"]
                        
                        # Barra visual simple
                        bar_length = 20
                        filled = int((pct / 100) * bar_length) if limit > 0 else 0
                        bar = "█" * filled + "░" * (bar_length - filled)
                        
                        response_text += f"\n{budget['name']}:\n"
                        response_text += f"  [{bar}] {pct:.0f}%\n"
                        response_text += f"  Gastado:   ${spent:,.0f} / ${limit:,.0f} COP\n"
                        response_text += f"  Restante:  ${remaining:+,.0f} COP\n"
                    
                    response_text += f"\nTOTAL PRESUPUESTOS:\n"
                    response_text += f"  Límite total:  ${total_limit:,.0f} COP\n"
                    response_text += f"  Gastado total: ${total_spent:,.0f} COP\n"
                    response_text += f"  Restante:      ${total_limit - total_spent:+,.0f} COP\n"
                    response_text += "\n"
                    
                    # 5. ANÁLISIS Y NET WORTH
                    net_worth = current_patrimony - total_debt
                    response_text += "📊 ANÁLISIS GENERAL\n"
                    response_text += "─" * 40 + "\n"
                    response_text += f"Net Worth:          ${net_worth:+,.0f} COP\n"
                    response_text += f"(Patrimonio - Deudas)\n"
                    
                    if net_worth < 0:
                        response_text += f"\n⚠️  Tienes deuda neta: ${abs(net_worth):,.0f} COP\n"
                    else:
                        response_text += f"\n✅ Patrimonio positivo\n"
                    
                    response_text += "\n" + "═" * 40
                    
                except Exception as e:
                    logger.error(f"Error getting financial summary: {str(e)}")
                    response_text = f"Error generando resumen: {str(e)}"
            
            elif action == "close_month":
                # User wants to close the month and update patrimony
                try:
                    monthly_status = await calculate_monthly_patrimony()
                    remaining = monthly_status.get("remaining_this_month", 0)
                    
                    # Get patrimony before update
                    patrimony_before = await get_patrimony()
                    patrimony_before_balance = float(patrimony_before.get("current_balance", 0) or 0) if patrimony_before else 0
                    
                    # Update patrimony (will add if positive, subtract if negative)
                    updated_patrimony = await update_patrimony_end_of_month(remaining=remaining)
                    patrimony_after_balance = float(updated_patrimony.get("current_balance", 0) or 0)
                    
                    # Reset all budgets for the new month
                    try:
                        await reset_all_budgets()
                        budgets_reset = True
                    except Exception as e:
                        logger.error(f"Could not reset budgets: {str(e)}")
                        budgets_reset = False
                    
                    # Build response message
                    if remaining <= 0:
                        response_text = f"⚠️ MES CERRADO (GASTO EXCESIVO)\n\n"
                        response_text += f"Este mes gastaste más de lo que ingresaste.\n"
                        response_text += f"Diferencia negativa: ${abs(remaining):,.0f} COP\n\n"
                        response_text += f"Patrimonio antes: ${patrimony_before_balance:,.0f} COP\n"
                        response_text += f"Se restó del patrimonio: ${abs(remaining):,.0f} COP\n"
                        response_text += f"Patrimonio ahora: ${patrimony_after_balance:,.0f} COP\n\n"
                    else:
                        response_text = f"✅ MES CERRADO\n\n"
                        response_text += f"Patrimonio antes: ${patrimony_before_balance:,.0f} COP\n"
                        response_text += f"Lo que quedó este mes: ${remaining:,.0f} COP\n"
                        response_text += f"Patrimonio ahora: ${patrimony_after_balance:,.0f} COP\n\n"
                    
                    if budgets_reset:
                        response_text += f"✅ Presupuestos reseteados a cero para el nuevo mes."
                    else:
                        response_text += f"⚠️ No se pudieron resetear los presupuestos. Intenta de nuevo."
                        
                except Exception as e:
                    logger.error(f"Error closing month: {str(e)}")
                    response_text = f"Error cerrando el mes: {str(e)}"
            
            elif action == "consult_spending":
                # User wants advice on spending something
                try:
                    # Get complete financial state
                    financial_state = await get_complete_financial_state()
                    
                    # Generate spending advice using the guardian/coach logic
                    response_text = generate_spending_advice(
                        user_query=user_text,
                        amount=amount if amount > 0 else 0,
                        financial_state=financial_state,
                        conversation_history=conversation_history
                    )
                except Exception as e:
                    logger.error(f"Error generating spending advice: {str(e)}")
                    response_text = f"Error analizando tu consulta: {str(e)}"
            
            elif action == "query_transaction":
                # User wants to query past transactions
                try:
                    # Extract search parameters from description
                    query_desc = description.lower() if description else ""
                    
                    # Try to extract category, type, and days from the query
                    search_category = None
                    search_type = None
                    search_days = None
                    search_desc = None
                    
                    # Check for time references
                    if "hoy" in query_desc or "today" in query_desc:
                        search_days = 1
                    elif "semana" in query_desc or "week" in query_desc:
                        search_days = 7
                    elif "mes" in query_desc or "month" in query_desc:
                        search_days = 30
                    
                    # Check for transaction type
                    if "ingreso" in query_desc or "income" in query_desc or "gané" in query_desc:
                        search_type = "income"
                    elif "gasto" in query_desc or "expense" in query_desc or "gasté" in query_desc:
                        search_type = "expense"
                    
                    # Check for category keywords
                    category_keywords = {
                        "fixed_survival": ["survival", "fijo", "arriendo", "servicio", "servicios"],
                        "debt_offensive": ["deuda", "debt", "lumni", "icetex"],
                        "kepler_growth": ["kepler", "negocio", "curso", "aws", "api"],
                        "networking_life": ["networking", "social", "amigo", "novia"],
                        "stupid_expenses": ["stupid", "tonto", "lujo"]
                    }
                    
                    for cat, keywords in category_keywords.items():
                        if any(kw in query_desc for kw in keywords):
                            search_category = cat
                            break
                    
                    # Use description as search term if no specific filters
                    if not search_category and not search_type and description:
                        search_desc = description
                    
                    # Get transactions
                    transactions = await get_transactions(
                        description=search_desc,
                        category=search_category,
                        transaction_type=search_type,
                        limit=50,
                        days=search_days
                    )
                    
                    # Generate response
                    response_text = generate_transaction_query_response(
                        user_query=user_text,
                        transactions=transactions,
                        conversation_history=conversation_history
                    )
                except Exception as e:
                    logger.error(f"Error querying transactions: {str(e)}")
                    response_text = f"Error consultando transacciones: {str(e)}"
            
            elif action == "query_thoughts":
                # User wants to query thoughts/reminders
                try:
                    # Extract filters from description
                    desc_lower = description.lower() if description else user_text.lower()
                    
                    # Detect date filter
                    date_filter = None
                    if "hoy" in desc_lower or "today" in desc_lower:
                        date_filter = "today"
                    elif "ayer" in desc_lower or "yesterday" in desc_lower:
                        date_filter = "yesterday"
                    
                    # Detect type filter
                    thought_type = None
                    if "recordatorio" in desc_lower or "reminder" in desc_lower:
                        thought_type = "reminder"
                    elif "idea" in desc_lower:
                        thought_type = "idea"
                    elif "nota" in desc_lower or "note" in desc_lower:
                        thought_type = "note"
                    elif "pensamiento" in desc_lower or "thought" in desc_lower:
                        thought_type = "thought"
                    
                    # Get thoughts/reminders
                    thoughts = await get_thoughts_reminders(
                        chat_id=int(chat_id) if chat_id else 0,
                        date=date_filter,
                        thought_type=thought_type,
                        limit=30
                    )
                    
                    if not thoughts:
                        response_text = "No encontré pensamientos/recordatorios que coincidan con tu búsqueda."
                    else:
                        type_names = {
                            "reminder": "Recordatorio",
                            "idea": "Idea",
                            "note": "Nota",
                            "thought": "Pensamiento"
                        }
                        
                        response_text = f"📝 {len(thoughts)} {'pensamientos' if thought_type is None else type_names.get(thought_type, 'items')} encontrados:\n\n"
                        
                        for i, thought in enumerate(thoughts[:20], 1):  # Limit to 20
                            content = thought.get("content", "")
                            t_type = thought.get("type", "thought")
                            created_at = thought.get("created_at", "")
                            reminder_date = thought.get("reminder_date")
                            is_completed = thought.get("is_completed", False)
                            
                            # Format date
                            date_str = ""
                            if created_at:
                                try:
                                    from datetime import datetime
                                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                                    date_str = dt.strftime("%d/%m/%Y %H:%M")
                                except:
                                    date_str = created_at.split("T")[0] if "T" in created_at else created_at
                            
                            status = "✅" if is_completed else ""
                            type_emoji = {"reminder": "🔔", "idea": "💡", "note": "📄", "thought": "💭"}.get(t_type, "📝")
                            
                            response_text += f"{i}. {type_emoji} {type_names.get(t_type, t_type)} {status}\n"
                            response_text += f"   {content}\n"
                            if reminder_date:
                                response_text += f"   📅 {reminder_date}\n"
                            response_text += f"   📆 {date_str}\n\n"
                        
                        if len(thoughts) > 20:
                            response_text += f"... y {len(thoughts) - 20} más"
                    
                except Exception as e:
                    logger.error(f"Error querying thoughts: {str(e)}")
                    response_text = f"Error consultando pensamientos: {str(e)}"
            
            else:
                response_text = "Acción no reconocida. Por favor, intenta de nuevo."
        
        # Step 7: Save conversation messages to history
        try:
            await save_conversation_message(chat_id=chat_id, role="user", message=user_text, intent=intent)
            await save_conversation_message(chat_id=chat_id, role="assistant", message=response_text, intent=intent)
        except Exception as e:
            logger.warning(f"Could not save conversation history: {str(e)}")
        
        # Step 8: Send response to Telegram
        if chat_id:
            try:
                await send_message(chat_id=chat_id, text=response_text)
                logger.info(f"Message sent to chat {chat_id}")
            except Exception as e:
                logger.error(f"Error sending message to Telegram: {str(e)}")
        
        # Return response for logging/debugging
        logger.info(f"Response: {response_text}")
        
        return JSONResponse({
            "status": "ok",
            "chat_id": chat_id,
            "response": response_text
        })
        
    except Exception as e:
        logger.error(f"Error in webhook: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Error procesando la solicitud: {str(e)}"
            }
        )


# Vercel serverless - la app FastAPI se expone directamente
# No se necesita handler personalizado, Vercel detecta 'app' automáticamente

