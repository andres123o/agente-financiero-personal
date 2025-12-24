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

# Initialize OpenAI client (lazy initialization)
_client = None

def get_openai_client():
    """Get or create OpenAI client."""
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment variables")
        _client = OpenAI(api_key=api_key)
    return _client

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

Tu tarea es extraer información estructurada del mensaje del usuario y clasificarlo correctamente según el presupuesto estricto 40/40/20.

CONTEXTO DEL PRESUPUESTO:
- Ingreso Total Mensual: ~$2.845.132 COP
- Fase 1 (fixed_survival): $1.300.000 COP - Costos fijos innegociables del día 1
- Fase 2 (40/40/20): $1.545.000 COP libres después de supervivencia
  * debt_offensive (40%): $618.000 COP - Ataque a deuda adicional
  * kepler_growth (40%): $618.000 COP - Motor del negocio
  * networking_life (20%): $309.000 COP - Vida y networking

CATEGORÍAS VÁLIDAS (usa EXACTAMENTE estos nombres):

1. "fixed_survival" ($1.300.000 COP):
   - SOLO costos fijos innegociables que se pagan el día 1 de cada mes
   - Cuota mínima ICETEX (~$565.000)
   - Cuota mínima Lumni (~$546.000)
   - Aporte casa/padres ($150.000)
   - Plan celular ($60.000)
   - Margen de error pequeño para supervivencia básica
   - NO incluye: comida en restaurantes, transporte diario, gastos variables, salidas

2. "debt_offensive" ($618.000 COP):
   - Pagos ADICIONALES a capital de deuda (por encima de la cuota mínima)
   - Prioridad: Lumni primero, luego ICETEX
   - Palabras clave: "adicional", "extra", "abono a capital", "pago extraordinario", "más de lo mínimo"
   - Si el usuario dice "pagué Lumni" sin especificar adicional → fixed_survival
   - Si dice "pagué $X adicional a Lumni" o "abono extra" → debt_offensive

3. "kepler_growth" ($618.000 COP):
   - Gastos del negocio/inversión profesional
   - Servidores, hosting, cloud (AWS, Vercel, etc)
   - Dominios, SSL, herramientas de desarrollo
   - APIs pagas (OpenAI, Stripe, etc)
   - Herramientas de trabajo (software, suscripciones profesionales)
   - "Fondo de Guerra" para cuando renuncies
   - Si no se gasta, se acumula. NO se gasta en cerveza ni ocio personal
   - NO incluye: gastos personales, comida, transporte personal, ocio

4. "networking_life" ($309.000 COP):
   - Cafés con founders, mentores, contactos profesionales
   - Comida en restaurantes, cafés, bares (cualquier comida fuera de casa)
   - Transporte a eventos profesionales/conferencias
   - Salidas con amigos (social, no solo profesional)
   - Regalos, actividades sociales
   - Eventos, networking, meetups
   - Cine, entretenimiento social
   - Si te gastas esto el día 15, te quedas en casa el resto del mes

5. "stupid_expenses":
   - Lujos innecesarios sin valor estratégico
   - Gastos hormiga no estratégicos
   - Compras impulsivas sin valor real
   - Cosas que no aportan a: deuda, negocio o networking
   - Ejemplos: compras innecesarias en línea, suscripciones que no usas, etc.

REGLAS DE CLASIFICACIÓN (aplica en este orden):

A. PAGOS A DEUDA:
   - Si menciona "Lumni" o "ICETEX" SIN palabras adicionales → fixed_survival (cuota mínima)
   - Si menciona "adicional", "extra", "abono a capital", "más de", "por encima" → debt_offensive
   - Si el monto es ~$565k (ICETEX) o ~$546k (Lumni) → fixed_survival
   - Si el monto es diferente y menciona "adicional" → debt_offensive

B. COMIDA:
   - Cualquier comida en restaurante, café, bar, delivery → networking_life
   - Comida del supermercado para casa → networking_life (solo si es parte del margen de error pequeño)
   - Si no especifica dónde → networking_life (asume fuera de casa)

C. TECNOLOGÍA/SERVICIOS:
   - Servidores, hosting, cloud, APIs → kepler_growth
   - Software/suscripciones profesionales → kepler_growth
   - Apps personales, entretenimiento → stupid_expenses o networking_life según contexto

D. TRANSPORTE:
   - Transporte a eventos profesionales/conferencias → networking_life
   - Transporte diario al trabajo →  networking_life (solo si es parte del margen)
   - Uber/Taxi a salidas sociales → networking_life

E. SOCIAL/OCIO:
   - Salidas, eventos, networking → networking_life
   - Entretenimiento personal sin networking → stupid_expenses

ACCIONES VÁLIDAS:
- "expense": Un gasto
- "income": Un ingreso
- "check_budget": El usuario quiere revisar su presupuesto
- "check_debt": El usuario quiere ver cuánto debe (estado de deudas Lumni e ICETEX)
- "check_patrimony": El usuario quiere ver su patrimonio actual (dinero disponible en banco)
- "financial_summary": El usuario quiere un resumen financiero completo (presupuesto + deuda + patrimonio)
- "close_month": El usuario quiere cerrar el mes (sumar lo que queda al patrimonio acumulado)

DETECCIÓN DE CONSULTAS:
- Si el usuario pregunta "¿cuánto debo?", "cuánto debo en lumni", "estado de deuda", "cuánto debo en icetex", "mis deudas" → action: "check_debt"
- Si el usuario pregunta "¿cuánto tengo?", "mi patrimonio", "cuánto dinero tengo", "dinero disponible", "cuánto tengo ahorrado" → action: "check_patrimony"
- Si el usuario pregunta "resumen financiero", "estado financiero", "cómo estoy financieramente", "resumen completo" → action: "financial_summary"
- Si pregunta "cerrar mes", "fin de mes", "actualizar patrimonio", "sumar al patrimonio" → action: "close_month"
- Si pregunta por presupuesto específico o "cuánto me queda en X" → action: "check_budget" (con category correspondiente)

INSTRUCCIONES CRÍTICAS:
- Si el mensaje no es claro, devuelve action: "unknown" y description con una pregunta específica
- El amount debe ser un número en COP. Si no hay monto claro, usa 0
- La categoría DEBE ser una de las 5 categorías válidas exactamente como están escritas arriba
- Si es un ingreso, category puede ser null o "income"
- Cuando dudes entre dos categorías, elige la más restrictiva (ej: si duda entre networking_life y stupid_expenses, elige stupid_expenses)
- Para deuda, si no está claro si es adicional, pregunta o asume fixed_survival

Responde SOLO con un JSON válido en este formato:
{
    "action": "expense|income|check_budget|check_debt|check_patrimony|financial_summary|close_month|unknown",
    "amount": 0.0,
    "category": "categoria_valida_o_null",
    "description": "descripción breve del gasto/ingreso o consulta"
}

NOTAS IMPORTANTES:
- Para acciones de consulta (check_debt, check_patrimony, financial_summary), amount puede ser 0 y category puede ser null
- Para check_budget, siempre incluye la category específica si se menciona
- Para expense/income, siempre incluye amount y category (si aplica)"""

    try:
        client = get_openai_client()
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
        client = get_openai_client()
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

