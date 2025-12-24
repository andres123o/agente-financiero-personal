"""
Database operations for Supabase integration.
Handles transactions and budget management.
"""
import os
import httpx
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

# Initialize Supabase client using REST API directly
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables")

# Remove trailing slash if present
supabase_url = supabase_url.rstrip('/')

# Create HTTP client for Supabase REST API
def get_supabase_client() -> httpx.Client:
    """Create and return an HTTP client configured for Supabase."""
    return httpx.Client(
        base_url=f"{supabase_url}/rest/v1",
        headers={
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        },
        timeout=30.0
    )


def insert_transaction(amount: float, category: str, description: str) -> Dict[str, Any]:
    """
    Insert a new transaction into the database.
    
    Args:
        amount: Transaction amount in COP
        category: One of the valid categories
        description: Transaction description
        
    Returns:
        Dict with transaction data
    """
    try:
        data = {
            "amount": float(amount),
            "category": category,
            "description": description
        }
        with get_supabase_client() as client:
            response = client.post("/transactions", json=data)
            response.raise_for_status()
            result = response.json()
            # Supabase returns array, get first element
            return result[0] if isinstance(result, list) and result else result
    except Exception as e:
        raise Exception(f"Error inserting transaction: {str(e)}")


def get_budget(category: str) -> Optional[Dict[str, Any]]:
    """
    Get budget information for a specific category.
    
    Args:
        category: Budget category
        
    Returns:
        Dict with budget data or None if not found
    """
    try:
        with get_supabase_client() as client:
            response = client.get(
                "/budgets",
                params={"category": f"eq.{category}"}
            )
            response.raise_for_status()
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                return result[0]
            return None
    except Exception as e:
        raise Exception(f"Error getting budget: {str(e)}")


def update_budget_spent(category: str, amount: float) -> Dict[str, Any]:
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
        budget = get_budget(category)
        if not budget:
            raise Exception(f"Budget not found for category: {category}")
        
        current_spent = budget.get("current_spent", 0) or 0
        new_spent = float(current_spent) + float(amount)
        
        # Update the budget using PATCH
        with get_supabase_client() as client:
            response = client.patch(
                f"/budgets?category=eq.{category}",
                json={"current_spent": new_spent}
            )
            response.raise_for_status()
            result = response.json()
            # Supabase returns array, get first element
            return result[0] if isinstance(result, list) and result else result
    except Exception as e:
        raise Exception(f"Error updating budget: {str(e)}")


def get_budget_status(category: str) -> Dict[str, Any]:
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
        budget = get_budget(category)
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

