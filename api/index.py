"""
FastAPI webhook handler for Telegram bot.
Main entry point for Kepler CFO.
"""
import os
import logging
from typing import Dict, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from core.brain import classify_expense, generate_response
from core.db import insert_transaction, update_budget_spent, get_budget_status
from core.telegram import send_message

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Kepler CFO Telegram Bot")


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
        
        # Step 1: Classify expense with OpenAI
        logger.info(f"Classifying message: {user_text}")
        classification = classify_expense(user_text)
        
        action = classification.get("action", "unknown")
        amount = float(classification.get("amount", 0))
        category = classification.get("category")
        description = classification.get("description", "")
        
        logger.info(f"Classification result: {classification}")
        
        # Step 2: Handle different actions
        budget_status = None
        response_text = ""
        
        if action == "unknown":
            # OpenAI couldn't understand the message
            response_text = description or "No pude entender tu mensaje. Por favor, sé más específico."
            
        elif action == "check_budget":
            # User wants to check budget
            if category:
                budget_status = await get_budget_status(category)
                response_text = generate_response(
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
                response_text = generate_response(
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
                    
                    # Step 5: Get budget status
                    budget_status = await get_budget_status(category)
                    
                    # Step 6: Generate response
                    response_text = generate_response(
                        action=action,
                        amount=amount,
                        category=category,
                        description=description,
                        budget_status=budget_status
                    )
                    
                except Exception as e:
                    logger.error(f"Error processing expense: {str(e)}")
                    response_text = f"Error procesando el gasto: {str(e)}"
        
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

