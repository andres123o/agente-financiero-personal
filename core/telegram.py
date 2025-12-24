"""
Telegram bot integration for sending messages.
"""
import os
import httpx
import logging
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}" if TELEGRAM_BOT_TOKEN else None


async def send_message(chat_id: int, text: str) -> bool:
    """
    Send a message to a Telegram chat.
    
    Args:
        chat_id: Telegram chat ID
        text: Message text to send
        
    Returns:
        True if successful, False otherwise
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set, cannot send message")
        return False
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TELEGRAM_API_URL}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML"
                }
            )
            response.raise_for_status()
            return True
    except Exception as e:
        logger.error(f"Error sending Telegram message: {str(e)}")
        return False

