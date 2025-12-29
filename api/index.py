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
    generate_mentorship_advice
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
    get_complete_financial_state
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
        
        # Step 1: Analyze intent (Router Layer)
        logger.info(f"Analyzing intent for message: {user_text}")
        intent = analyze_intent(user_text)
        logger.info(f"Intent: {intent}")
        
        response_text = ""
        
        # Step 2: Route to appropriate layer
        if intent == "MENTORSHIP":
            # Route to Mentorship Layer - 100% mentoria, sin contexto financiero
            try:
                response_text = generate_mentorship_advice(user_text)
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
                        budget_status=budget_status
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
                        budget_status=None
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
                            budget_status=budget_status
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
                    # Get debts
                    debts = await get_all_debts()
                    total_debt = sum(float(d.get("current_balance", 0) or 0) for d in debts)
                    
                    # Get patrimony
                    monthly_status = await calculate_monthly_patrimony()
                    patrimony = await get_patrimony()
                    current_patrimony = float(patrimony.get("current_balance", 0) or 0) if patrimony else 0
                    
                    # Get all budgets
                    budget_categories = ["fixed_survival", "debt_offensive", "kepler_growth", "networking_life", "stupid_expenses"]
                    budgets_info = []
                    total_spent = 0
                    for cat in budget_categories:
                        try:
                            budget = await get_budget_status(cat)
                            budgets_info.append(f"  {cat}: ${budget.get('current_spent', 0):,.0f} / ${budget.get('monthly_limit', 0):,.0f} COP")
                            total_spent += float(budget.get('current_spent', 0) or 0)
                        except:
                            pass
                    
                    response_text = "📊 RESUMEN FINANCIERO:\n\n"
                    response_text += "💳 DEUDAS:\n"
                    for debt in debts:
                        name = debt.get("name", "Unknown")
                        current = float(debt.get("current_balance", 0) or 0)
                        response_text += f"  {name}: ${current:,.0f} COP\n"
                    response_text += f"  Total: ${total_debt:,.0f} COP\n\n"
                    
                    response_text += "💰 PATRIMONIO:\n"
                    response_text += f"  Acumulado: ${current_patrimony:,.0f} COP\n"
                    response_text += f"  Este mes queda: ${monthly_status.get('remaining_this_month', 0):,.0f} COP\n\n"
                    
                    response_text += "📈 PRESUPUESTOS:\n"
                    response_text += "\n".join(budgets_info)
                    response_text += f"\n  Total gastado: ${total_spent:,.0f} COP"
                    
                except Exception as e:
                    logger.error(f"Error getting financial summary: {str(e)}")
                    response_text = f"Error generando resumen: {str(e)}"
            
            elif action == "close_month":
                # User wants to close the month and update patrimony
                try:
                    monthly_status = await calculate_monthly_patrimony()
                    remaining = monthly_status.get("remaining_this_month", 0)
                    
                    if remaining <= 0:
                        response_text = f"⚠️ Este mes gastaste más de lo que ingresaste. Diferencia: ${abs(remaining):,.0f} COP. No se puede sumar al patrimonio."
                        # Reset budgets anyway even if negative balance
                        try:
                            await reset_all_budgets()
                            response_text += "\n\n✅ Presupuestos reseteados para el nuevo mes."
                        except Exception as e:
                            logger.warning(f"Could not reset budgets: {str(e)}")
                            response_text += "\n\n⚠️ No se pudieron resetear los presupuestos."
                    else:
                        patrimony_before = await get_patrimony()
                        patrimony_before_balance = float(patrimony_before.get("current_balance", 0) or 0) if patrimony_before else 0
                        
                        updated_patrimony = await update_patrimony_end_of_month()
                        patrimony_after_balance = float(updated_patrimony.get("current_balance", 0) or 0)
                        
                        # Reset all budgets for the new month
                        await reset_all_budgets()
                        
                        response_text = f"✅ MES CERRADO\n\n"
                        response_text += f"Patrimonio antes: ${patrimony_before_balance:,.0f} COP\n"
                        response_text += f"Lo que quedó este mes: ${remaining:,.0f} COP\n"
                        response_text += f"Patrimonio ahora: ${patrimony_after_balance:,.0f} COP\n\n"
                        response_text += f"✅ Presupuestos reseteados a cero para el nuevo mes."
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
                        financial_state=financial_state
                    )
                except Exception as e:
                    logger.error(f"Error generating spending advice: {str(e)}")
                    response_text = f"Error analizando tu consulta: {str(e)}"
            
            else:
                response_text = "Acción no reconocida. Por favor, intenta de nuevo."
        
        # Step 7: Send response to Telegram
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

