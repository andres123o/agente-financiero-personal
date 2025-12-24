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

