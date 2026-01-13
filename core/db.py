"""
Database operations for Supabase integration.
Handles transactions and budget management.
"""
import os
import httpx
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Initialize Supabase client using REST API directly
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables")

# Remove trailing slash if present
supabase_url = supabase_url.rstrip('/')

# Headers para Supabase
def get_supabase_headers() -> Dict[str, str]:
    """Get headers for Supabase API requests."""
    if not supabase_key:
        raise ValueError("SUPABASE_KEY is not set")
    return {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }


async def insert_transaction(amount: float, category: str, description: str, transaction_type: str = "expense") -> Dict[str, Any]:
    """
    Insert a new transaction into the database.
    
    Args:
        amount: Transaction amount in COP
        category: One of the valid categories
        description: Transaction description
        transaction_type: Type of transaction - "expense" or "income" (default: "expense")
        
    Returns:
        Dict with transaction data
    """
    try:
        data = {
            "amount": float(amount),
            "category": category,
            "description": description if description else None,
            "type": transaction_type
        }
        
        headers = get_supabase_headers()
        url = f"{supabase_url}/rest/v1/transactions"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=data, headers=headers)
            
            # Log error details for debugging
            if response.status_code != 201:
                error_detail = response.text
                try:
                    error_json = response.json()
                    error_detail = str(error_json)
                except:
                    pass
                logger.error(f"Supabase error {response.status_code}: {error_detail}. Headers sent: {list(headers.keys())}")
                raise Exception(f"Supabase error {response.status_code}: {error_detail}. Request data: {data}")
            
            result = response.json()
            # Supabase returns array, get first element
            return result[0] if isinstance(result, list) and result else result
    except httpx.HTTPStatusError as e:
        error_detail = e.response.text if e.response else str(e)
        raise Exception(f"Error inserting transaction (HTTP {e.response.status_code if e.response else 'unknown'}): {error_detail}")
    except Exception as e:
        raise Exception(f"Error inserting transaction: {str(e)}")


async def get_transactions(
    description: Optional[str] = None,
    category: Optional[str] = None,
    transaction_type: Optional[str] = None,
    limit: int = 50,
    days: Optional[int] = None
) -> list[Dict[str, Any]]:
    """
    Get transactions from the database with optional filters.
    
    Args:
        description: Filter by description (partial match, case insensitive)
        category: Filter by category
        transaction_type: Filter by type ('expense' or 'income')
        limit: Maximum number of transactions to return (default: 50)
        days: Filter by last N days (optional)
        
    Returns:
        List of transaction dictionaries
    """
    try:
        from datetime import datetime, timedelta
        
        headers = get_supabase_headers()
        url = f"{supabase_url}/rest/v1/transactions"
        params = {
            "order": "created_at.desc",
            "limit": str(limit)
        }
        
        # Add filters
        if category:
            params["category"] = f"eq.{category}"
        if transaction_type:
            params["type"] = f"eq.{transaction_type}"
        if days:
            date_filter = (datetime.now() - timedelta(days=days)).isoformat() + "Z"
            params["created_at"] = f"gte.{date_filter}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            result = response.json()
            
            transactions = result if isinstance(result, list) else []
            
            # Filter by description if provided (Supabase text search is limited, so we filter in Python)
            if description:
                desc_lower = description.lower()
                transactions = [
                    t for t in transactions 
                    if t.get("description") and desc_lower in t.get("description", "").lower()
                ]
            
            return transactions
    except Exception as e:
        logger.error(f"Error getting transactions: {str(e)}")
        return []


async def get_budget(category: str) -> Optional[Dict[str, Any]]:
    """
    Get budget information for a specific category.
    
    Args:
        category: Budget category
        
    Returns:
        Dict with budget data or None if not found
    """
    try:
        headers = get_supabase_headers()
        url = f"{supabase_url}/rest/v1/budgets"
        params = {"category": f"eq.{category}"}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                return result[0]
            return None
    except Exception as e:
        raise Exception(f"Error getting budget: {str(e)}")


async def update_budget_spent(category: str, amount: float) -> Dict[str, Any]:
    """
    Update the current_spent amount for a budget category.
    This adds the amount to the existing current_spent.
    
    Args:
        category: Budget category
        amount: Amount to add to current_spent
        
    Returns:
        Updated budget data
    """
    try:
        # First, get current budget
        budget = await get_budget(category)
        if not budget:
            raise Exception(f"Budget not found for category: {category}")
        
        current_spent = budget.get("current_spent", 0) or 0
        new_spent = float(current_spent) + float(amount)
        
        # Update the budget using PATCH
        headers = get_supabase_headers()
        url = f"{supabase_url}/rest/v1/budgets"
        params = {"category": f"eq.{category}"}
        data = {"current_spent": new_spent}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.patch(url, params=params, json=data, headers=headers)
            response.raise_for_status()
            result = response.json()
            # Supabase returns array, get first element
            return result[0] if isinstance(result, list) and result else result
    except Exception as e:
        raise Exception(f"Error updating budget: {str(e)}")


async def get_budget_status(category: str) -> Dict[str, Any]:
    """
    Get complete budget status including remaining amount.
    
    Args:
        category: Budget category
        
    Returns:
        Dict with budget status including:
        - monthly_limit
        - current_spent
        - remaining
    """
    try:
        budget = await get_budget(category)
        if not budget:
            raise Exception(f"Budget not found for category: {category}")
        
        monthly_limit = budget.get("monthly_limit", 0) or 0
        current_spent = budget.get("current_spent", 0) or 0
        remaining = monthly_limit - current_spent
        
        return {
            "category": category,
            "monthly_limit": monthly_limit,
            "current_spent": current_spent,
            "remaining": remaining
        }
    except Exception as e:
        raise Exception(f"Error getting budget status: {str(e)}")


# ============================================
# DEBT MANAGEMENT FUNCTIONS
# ============================================

async def get_all_debts() -> list[Dict[str, Any]]:
    """
    Get all debts (Lumni and ICETEX).
    
    Returns:
        List of debt dictionaries
    """
    try:
        headers = get_supabase_headers()
        url = f"{supabase_url}/rest/v1/debts"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            result = response.json()
            return result if isinstance(result, list) else []
    except Exception as e:
        raise Exception(f"Error getting debts: {str(e)}")


async def get_debt(debt_name: str) -> Optional[Dict[str, Any]]:
    """
    Get a specific debt by name.
    
    Args:
        debt_name: Name of the debt ('Lumni' or 'ICETEX')
        
    Returns:
        Debt dictionary or None if not found
    """
    try:
        headers = get_supabase_headers()
        url = f"{supabase_url}/rest/v1/debts"
        params = {"name": f"eq.{debt_name}"}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                return result[0]
            return None
    except Exception as e:
        raise Exception(f"Error getting debt: {str(e)}")


async def update_debt_balance(debt_name: str, payment_amount: float) -> Dict[str, Any]:
    """
    Update debt balance by reducing it with a payment.
    This is called when there's a payment (monthly or extraordinary).
    
    Args:
        debt_name: Name of the debt ('Lumni' or 'ICETEX')
        payment_amount: Amount to reduce from current_balance
        
    Returns:
        Updated debt dictionary
    """
    try:
        # Get current debt
        debt = await get_debt(debt_name)
        if not debt:
            raise Exception(f"Debt '{debt_name}' not found")
        
        current_balance = float(debt.get("current_balance", 0) or 0)
        new_balance = max(0, current_balance - float(payment_amount))  # Don't go below 0
        
        # Update the debt
        headers = get_supabase_headers()
        url = f"{supabase_url}/rest/v1/debts"
        params = {"name": f"eq.{debt_name}"}
        data = {"current_balance": new_balance}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.patch(url, params=params, json=data, headers=headers)
            response.raise_for_status()
            result = response.json()
            return result[0] if isinstance(result, list) and result else result
    except Exception as e:
        raise Exception(f"Error updating debt balance: {str(e)}")


# ============================================
# PATRIMONY MANAGEMENT FUNCTIONS
# ============================================

async def get_patrimony() -> Optional[Dict[str, Any]]:
    """
    Get current patrimony information.
    
    Returns:
        Patrimony dictionary or None if not found
    """
    try:
        headers = get_supabase_headers()
        url = f"{supabase_url}/rest/v1/patrimony"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                return result[0]
            return None
    except Exception as e:
        raise Exception(f"Error getting patrimony: {str(e)}")


async def calculate_monthly_patrimony() -> Dict[str, Any]:
    """
    Calculate current month's patrimony status.
    This tracks in real-time: Ingreso mensual - Gastos totales = Lo que queda
    
    IMPORTANTE: Los gastos se calculan sumando current_spent de todos los budgets,
    no de las transacciones individuales, porque eso refleja mejor el gasto real.
    
    Returns:
        Dict with:
        - monthly_income: Total income this month
        - monthly_expenses: Total expenses this month (sum of all budgets current_spent)
        - remaining_this_month: Income - Expenses
        - current_patrimony: Patrimony accumulated balance
    """
    try:
        from datetime import datetime
        
        # Get current month start in ISO format (Supabase REST API format)
        now = datetime.now()
        month_start = datetime(now.year, now.month, 1).isoformat() + "Z"
        
        headers = get_supabase_headers()
        
        # Get total income this month from transactions
        income_url = f"{supabase_url}/rest/v1/transactions"
        income_params = {
            "type": "eq.income",
            "created_at": f"gte.{month_start}"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get income
            income_response = await client.get(income_url, params=income_params, headers=headers)
            income_response.raise_for_status()
            income_transactions = income_response.json()
            monthly_income = sum(float(t.get("amount", 0) or 0) for t in income_transactions) if isinstance(income_transactions, list) else 0
            
            # Get expenses from budgets (sum of all current_spent)
            # Esto es más preciso porque refleja el gasto real por categoría
            budget_categories = ["fixed_survival", "debt_offensive", "kepler_growth", "networking_life", "stupid_expenses"]
            monthly_expenses = 0
            for cat in budget_categories:
                try:
                    budget = await get_budget(cat)
                    if budget:
                        monthly_expenses += float(budget.get("current_spent", 0) or 0)
                except:
                    pass
            
            # Get current patrimony
            patrimony = await get_patrimony()
            current_patrimony = float(patrimony.get("current_balance", 0) or 0) if patrimony else 0
            
            remaining_this_month = monthly_income - monthly_expenses
            
            return {
                "monthly_income": monthly_income,
                "monthly_expenses": monthly_expenses,
                "remaining_this_month": remaining_this_month,
                "current_patrimony": current_patrimony,
                "projected_patrimony": current_patrimony + remaining_this_month
            }
    except Exception as e:
        raise Exception(f"Error calculating monthly patrimony: {str(e)}")


async def reset_all_budgets() -> bool:
    """
    Reset all budget categories' current_spent to 0.
    This should be called at the beginning of each month.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Update each budget category individually
        budget_categories = ["fixed_survival", "debt_offensive", "kepler_growth", "networking_life", "stupid_expenses"]
        headers = get_supabase_headers()
        url = f"{supabase_url}/rest/v1/budgets"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for category in budget_categories:
                try:
                    params = {"category": f"eq.{category}"}
                    data = {"current_spent": 0}
                    response = await client.patch(url, params=params, json=data, headers=headers)
                    response.raise_for_status()
                except Exception as e:
                    logger.warning(f"Could not reset budget for {category}: {str(e)}")
                    # Continue with other categories even if one fails
            return True
    except Exception as e:
        logger.error(f"Error resetting budgets: {str(e)}")
        raise Exception(f"Error resetting budgets: {str(e)}")


async def get_complete_financial_state() -> Dict[str, Any]:
    """
    Get complete financial state for spending advice.
    Includes budgets, debts, and patrimony.
    
    Returns:
        Dict with complete financial state
    """
    try:
        # Get all budgets
        budget_categories = ["fixed_survival", "debt_offensive", "kepler_growth", "networking_life", "stupid_expenses"]
        budgets_dict = {}
        for cat in budget_categories:
            try:
                budget_status = await get_budget_status(cat)
                budgets_dict[cat] = {
                    "monthly_limit": budget_status.get("monthly_limit", 0),
                    "current_spent": budget_status.get("current_spent", 0),
                    "remaining": budget_status.get("remaining", 0)
                }
            except:
                budgets_dict[cat] = {
                    "monthly_limit": 0,
                    "current_spent": 0,
                    "remaining": 0
                }
        
        # Get all debts
        debts = await get_all_debts()
        total_debt = sum(float(d.get("current_balance", 0) or 0) for d in debts)
        
        # Get patrimony
        monthly_status = await calculate_monthly_patrimony()
        patrimony_data = await get_patrimony()
        patrimony_dict = {
            "current_balance": float(patrimony_data.get("current_balance", 0) or 0) if patrimony_data else 0,
            "remaining_this_month": monthly_status.get("remaining_this_month", 0)
        }
        
        return {
            "budgets": budgets_dict,
            "debts": debts,
            "total_debt": total_debt,
            "patrimony": patrimony_dict
        }
    except Exception as e:
        logger.error(f"Error getting complete financial state: {str(e)}")
        raise Exception(f"Error getting complete financial state: {str(e)}")


async def update_patrimony_end_of_month(remaining: Optional[float] = None) -> Dict[str, Any]:
    """
    Update patrimony at the end of the month.
    Adds (or subtracts if negative) the remaining amount (income - expenses) to the accumulated patrimony.
    This should be called manually or via a command at month end.
    
    Args:
        remaining: Optional remaining amount. If not provided, will calculate it.
    
    Returns:
        Updated patrimony dictionary
    """
    try:
        # Calculate what's left this month if not provided
        if remaining is None:
            monthly_status = await calculate_monthly_patrimony()
            remaining = monthly_status.get("remaining_this_month", 0)
        else:
            monthly_status = await calculate_monthly_patrimony()
        
        # Get current patrimony
        patrimony = await get_patrimony()
        if not patrimony:
            raise Exception("Patrimony record not found")
        
        current_balance = float(patrimony.get("current_balance", 0) or 0)
        # Add remaining (can be negative, which will subtract)
        new_balance = current_balance + remaining
        # Don't allow negative patrimony (or allow it, depending on business logic)
        # For now, we'll allow it to go negative if expenses exceed patrimony
        
        # Update patrimony using the ID from the patrimony record
        headers = get_supabase_headers()
        patrimony_id = patrimony.get("id")
        if not patrimony_id:
            raise Exception("Patrimony record has no ID")
        
        url = f"{supabase_url}/rest/v1/patrimony"
        # Use ID filter for PATCH (Supabase requires a filter for PATCH operations)
        params = {"id": f"eq.{patrimony_id}"}
        data = {
            "current_balance": new_balance,
            "last_month_income": monthly_status.get("monthly_income", 0),
            "last_month_expenses": monthly_status.get("monthly_expenses", 0)
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.patch(url, params=params, json=data, headers=headers)
            response.raise_for_status()
            result = response.json()
            return result[0] if isinstance(result, list) and result else result
    except Exception as e:
        raise Exception(f"Error updating patrimony end of month: {str(e)}")


# ============================================
# CONVERSATION HISTORY FUNCTIONS
# ============================================

async def save_conversation_message(chat_id: int, role: str, message: str, intent: Optional[str] = None) -> Dict[str, Any]:
    """
    Save a conversation message to the history.
    
    Args:
        chat_id: Telegram chat ID
        role: 'user' or 'assistant'
        message: Message text
        intent: Optional intent ('FINANCE' or 'MENTORSHIP')
        
    Returns:
        Dict with saved message data
    """
    try:
        data = {
            "chat_id": chat_id,
            "role": role,
            "message": message,
            "intent": intent
        }
        
        headers = get_supabase_headers()
        url = f"{supabase_url}/rest/v1/conversation_history"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status()
            result = response.json()
            return result[0] if isinstance(result, list) and result else result
    except Exception as e:
        raise Exception(f"Error saving conversation message: {str(e)}")


async def get_conversation_history(chat_id: int, limit: int = 8) -> list[Dict[str, Any]]:
    """
    Get recent conversation history for a chat.
    
    Args:
        chat_id: Telegram chat ID
        limit: Number of recent messages to retrieve (default: 8, range: 6-9)
        
    Returns:
        List of conversation messages (most recent first)
    """
    try:
        # Ensure limit is between 6-9
        limit = max(6, min(9, limit))
        
        headers = get_supabase_headers()
        url = f"{supabase_url}/rest/v1/conversation_history"
        params = {
            "chat_id": f"eq.{chat_id}",
            "order": "created_at.desc",
            "limit": str(limit)
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            result = response.json()
            
            # Reverse to get chronological order (oldest first)
            if isinstance(result, list):
                return list(reversed(result))
            return []
    except Exception as e:
        logger.error(f"Error getting conversation history: {str(e)}")
        return []

