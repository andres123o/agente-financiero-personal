"""
OpenAI integration for natural language processing.
Handles expense classification and response generation.
"""
import os
import json
from typing import Dict, Any, Optional
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Initialize OpenAI client
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY must be set in environment variables")

client = OpenAI(api_key=api_key)

# Valid categories as per requirements
VALID_CATEGORIES = [
    "fixed_survival",
    "debt_offensive",
    "kepler_growth",
    "networking_life",
    "stupid_expenses"
]


def classify_expense(user_message: str) -> Dict[str, Any]:
    """
    Analyze user message and extract structured expense data.
    
    Args:
        user_message: User's message from Telegram
        
    Returns:
        Dict with keys: action, amount, category, description
    """
    system_prompt = """Eres un asistente financiero experto que analiza mensajes de usuarios sobre gastos e ingresos.

Tu tarea es extraer información estructurada del mensaje del usuario y clasificarlo correctamente.

CATEGORÍAS VÁLIDAS (debes usar EXACTAMENTE estos nombres):
- "fixed_survival": Comida básica, servicios públicos, arriendo, transporte diario, necesidades básicas de supervivencia.
- "debt_offensive": Pagos a deudas (Lumni, Icetex) por encima del mínimo requerido, pagos extraordinarios a deudas.
- "kepler_growth": Gastos del negocio (servidores, dominios, publicidad, herramientas de trabajo, inversión en el negocio).
- "networking_life": Salidas sociales, cafés, cine, ocio, actividades sociales, networking.
- "stupid_expenses": Lujos innecesarios, gastos hormiga no estratégicos, compras impulsivas sin valor real.

ACCIONES VÁLIDAS:
- "expense": Un gasto
- "income": Un ingreso
- "check_budget": El usuario quiere revisar su presupuesto

IMPORTANTE:
- Si el mensaje no es claro o no puedes determinar la información, devuelve action: "unknown" y description con una pregunta al usuario.
- El amount debe ser un número en COP (pesos colombianos). Si no hay monto claro, usa 0.
- La categoría DEBE ser una de las 5 categorías válidas exactamente como están escritas arriba.
- Si es un ingreso, category puede ser null o "income".

Responde SOLO con un JSON válido en este formato:
{
    "action": "expense|income|check_budget|unknown",
    "amount": 0.0,
    "category": "categoria_valida_o_null",
    "description": "descripción breve del gasto/ingreso"
}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        content = response.choices[0].message.content
        result = json.loads(content)
        
        # Validate category if provided
        if result.get("category") and result["category"] not in VALID_CATEGORIES:
            # Try to map common variations
            category_lower = result["category"].lower()
            if "survival" in category_lower or "fijo" in category_lower or "básico" in category_lower:
                result["category"] = "fixed_survival"
            elif "deuda" in category_lower or "debt" in category_lower:
                result["category"] = "debt_offensive"
            elif "kepler" in category_lower or "negocio" in category_lower or "growth" in category_lower:
                result["category"] = "kepler_growth"
            elif "networking" in category_lower or "social" in category_lower or "ocio" in category_lower:
                result["category"] = "networking_life"
            elif "tonto" in category_lower or "stupid" in category_lower or "lujo" in category_lower:
                result["category"] = "stupid_expenses"
            else:
                # Default to fixed_survival if unclear
                result["category"] = "fixed_survival"
        
        return result
        
    except json.JSONDecodeError as e:
        return {
            "action": "unknown",
            "amount": 0.0,
            "category": None,
            "description": "No pude entender tu mensaje. Por favor, escribe algo como: 'Gasté 50000 en comida' o 'Ingresé 200000'"
        }
    except Exception as e:
        return {
            "action": "unknown",
            "amount": 0.0,
            "category": None,
            "description": f"Error procesando tu mensaje: {str(e)}"
        }


def generate_response(
    action: str,
    amount: float,
    category: Optional[str],
    description: str,
    budget_status: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate a contextual response for the user based on the transaction and budget status.
    
    Args:
        action: Type of action (expense, income, check_budget)
        amount: Transaction amount
        category: Transaction category
        description: Transaction description
        budget_status: Budget status dict with remaining, monthly_limit, current_spent
        
    Returns:
        Response message for Telegram
    """
    system_prompt = """Eres "Kepler CFO", un asistente financiero directo, sarcástico pero útil.

Tu personalidad:
- Eres directo y honesto sobre las finanzas
- Si alguien rompe el presupuesto, los insultas de forma creativa pero constructiva
- Si alguien hace un gasto tonto ("stupid_expenses"), eres sarcástico e insultas su falta de disciplina
- Si alguien paga deudas ("debt_offensive"), los felicitas secamente
- Si alguien gasta en el negocio ("kepler_growth"), los apoyas
- Eres breve pero efectivo

IMPORTANTE:
- Si remaining < 0: ALERTA ROJA. Insulta al usuario por romper el presupuesto de forma creativa.
- Si es "stupid_expenses": Insulta sarcásticamente su falta de disciplina financiera.
- Si es "debt_offensive": Felicita secamente por ser responsable.
- Si es "kepler_growth": Apoya la inversión en el negocio.
- Si es "fixed_survival": Sé neutral, es necesario.
- Si es "networking_life": Sé moderado, puede ser útil pero no excesivo.

Responde en español, de forma breve (máximo 3-4 líneas), directa y con personalidad."""

    user_prompt = f"""Acción: {action}
Monto: {amount:,.0f} COP
Categoría: {category or 'N/A'}
Descripción: {description}"""

    if budget_status:
        remaining = budget_status.get("remaining", 0)
        monthly_limit = budget_status.get("monthly_limit", 0)
        current_spent = budget_status.get("current_spent", 0)
        
        user_prompt += f"""

Estado del presupuesto:
- Límite mensual: {monthly_limit:,.0f} COP
- Gastado: {current_spent:,.0f} COP
- Restante: {remaining:,.0f} COP"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.8,
            max_tokens=200
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        # Fallback response
        if action == "expense" and budget_status:
            remaining = budget_status.get("remaining", 0)
            if remaining < 0:
                return f"⚠️ ALERTA: Has roto el presupuesto de {category}. Te quedan {abs(remaining):,.0f} COP en negativo. ¡Controla tus gastos!"
            elif category == "stupid_expenses":
                return f"Gasto registrado: {amount:,.0f} COP en {description}. ¿Realmente necesitabas esto? 🤦"
            elif category == "debt_offensive":
                return f"Bien hecho. {amount:,.0f} COP hacia tus deudas. Te quedan {remaining:,.0f} COP en esta categoría."
            else:
                return f"Gasto registrado: {amount:,.0f} COP. Te quedan {remaining:,.0f} COP en {category}."
        elif action == "income":
            return f"Ingreso registrado: {amount:,.0f} COP. {description}"
        elif action == "check_budget":
            return "Consulta tu presupuesto en la aplicación."
        else:
            return "Procesado."

