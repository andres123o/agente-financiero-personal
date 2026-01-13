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
    classify_financial_action,
    generate_cfo_response,
    generate_spending_advice,
    generate_mentorship_advice,
    generate_transaction_query_response
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
    update_thought_completed
)
from core.telegram import send_message

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Kepler CFO Telegram Bot")


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
        
        # Step 1: Get conversation history (6-9 recent messages)
        conversation_history = []
        try:
            conversation_history = await get_conversation_history(chat_id, limit=8)
            logger.info(f"Retrieved {len(conversation_history)} messages from history")
        except Exception as e:
            logger.warning(f"Could not retrieve conversation history: {str(e)}")
        
        # Step 2: Analyze intent (Router Layer)
        logger.info(f"Analyzing intent for message: {user_text}")
        intent = analyze_intent(user_text)
        logger.info(f"Intent: {intent}")
        
        response_text = ""
        
        # Step 3: Route to appropriate layer
        if intent == "MENTORSHIP":
            # Route to Mentorship Layer - 100% mentoria, sin contexto financiero
            try:
                response_text = generate_mentorship_advice(user_text, conversation_history=conversation_history)
            except Exception as e:
                logger.error(f"Error generating mentorship advice: {str(e)}")
                response_text = f"Error procesando tu mensaje: {str(e)}"
        
        else:
            # Route to Finance Layer (CFO)
            logger.info(f"Routing to Finance Layer")
            classification = classify_financial_action(user_text)
            
            action = classification.get("action", "unknown")
            amount = float(classification.get("amount", 0))
            category = classification.get("category")
            description = classification.get("description", "")
            
            logger.info(f"Classification result: {classification}")
            
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
            
            elif action == "save_thought":
                # User wants to save a thought, reminder, idea or note
                try:
                    # Extract type from description
                    desc_lower = description.lower() if description else user_text.lower()
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
                    
                    # Extract content (remove command words)
                    content = user_text
                    command_words = ["guarda", "save", "recordatorio", "reminder", "idea", "pensamiento", "thought", "nota", "note", "este", "esta"]
                    words = content.split()
                    content_words = [w for w in words if w.lower() not in command_words]
                    content = " ".join(content_words).strip()
                    
                    if not content:
                        content = description if description else user_text
                    
                    # Save thought/reminder
                    saved = await save_thought_reminder(
                        chat_id=chat_id,
                        content=content,
                        thought_type=thought_type,
                        reminder_date=reminder_date
                    )
                    
                    type_names = {
                        "reminder": "recordatorio",
                        "idea": "idea",
                        "note": "nota",
                        "thought": "pensamiento"
                    }
                    type_name = type_names.get(thought_type, "pensamiento")
                    
                    response_text = f"✅ {type_name.capitalize()} guardado:\n\n{content}"
                    if reminder_date:
                        response_text += f"\n\n📅 Recordatorio para: {reminder_date}"
                    
                except Exception as e:
                    logger.error(f"Error saving thought: {str(e)}")
                    response_text = f"Error guardando el pensamiento: {str(e)}"
            
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
                        chat_id=chat_id,
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

