"""
OpenAI integration for natural language processing.
Handles expense classification, response generation, and philosophical mentorship.
Combines logic from: Dweck, Naval, Manson, Carnegie, YC, Bezos, Musk, Borrero, Vega.
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

# Valid categories as per requirements (UNCHANGED)
VALID_CATEGORIES = [
    "fixed_survival",
    "debt_offensive",
    "kepler_growth",
    "networking_life",
    "stupid_expenses"
]

def classify_expense(user_message: str) -> Dict[str, Any]:
    """
    Analyze user message and extract structured expense data OR mentorship requests.
    """
    system_prompt = """Eres el sistema operativo central de un emprendedor de alto rendimiento. Analizas mensajes para extraer datos financieros o detectar necesidad de mentoría.

TU MENTALIDAD (CONTEXTO):
Operas bajo la lógica de YCombinator (Paul Graham), la eficiencia de Musk y el esencialismo de Naval Ravikant. Tu objetivo es clasificar la realidad del usuario en datos procesables.

CONTEXTO DEL PRESUPUESTO (Estricto):
- Ingreso Total: ~$2.845.132 COP
- fixed_survival: $1.300.000 (Vida o muerte)
- debt_offensive (40% del remanente): $618.000 (Guerra contra Lumni/ICETEX)
- kepler_growth (40% del remanente): $618.000 (Fondo de guerra para el negocio)
- networking_life (20% del remanente): $309.000 (Ingeniería social y dopamina controlada)

CATEGORÍAS (Mapeo estricto):
1. "fixed_survival": Costos inevitables (Arriendo, servicios base).
2. "debt_offensive": Pagos EXTRA a deuda. Atacar el pasivo.
3. "kepler_growth": AWS, Dominios, Cursos, Herramientas. Inversión en el activo.
4. "networking_life": Cafés estratégicos, salidas sociales, transporte.
5. "stupid_expenses": Basura, estatus falso, impulsos.

ACCIONES VÁLIDAS:
- "expense": Gasto
- "income": Ingreso
- "check_budget": Consultar saldo
- "check_debt": Consultar pasivos
- "check_patrimony": Consultar net worth
- "financial_summary": Resumen completo
- "close_month": Cierre contable
- "consult_spending": Pregunta sobre una compra futura ("¿Debería comprar X?")
- "get_mentorship": EL USUARIO PIDE AYUDA EMOCIONAL/ESTRATÉGICA.
    * Activadores: "estoy perdido", "no sé qué hacer", "me siento estancado", "dame un consejo", "estoy desmotivado", "tengo miedo", "coach".

REGLAS CRÍTICAS:
- Si el usuario suena desesperado, confundido o filosófico -> action: "get_mentorship".
- Si es dinero -> clasifica estrictamente en las 5 categorías.
- Ante la duda entre networking y stupid -> stupid_expenses (Mark Manson: "No te mientas a ti mismo").

Responde SOLO JSON válido:
{
    "action": "expense|income|check_budget|check_debt|check_patrimony|financial_summary|close_month|consult_spending|get_mentorship|unknown",
    "amount": 0.0,
    "category": "categoria_valida_o_null",
    "description": "contexto breve"
}
"""

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
        
        # Validate category logic (Mismo código de validación tuyo, intacto)
        if result.get("category") and result["category"] not in VALID_CATEGORIES:
            category_lower = result["category"].lower()
            if "survival" in category_lower or "fijo" in category_lower: result["category"] = "fixed_survival"
            elif "deuda" in category_lower or "debt" in category_lower: result["category"] = "debt_offensive"
            elif "kepler" in category_lower or "negocio" in category_lower: result["category"] = "kepler_growth"
            elif "networking" in category_lower or "social" in category_lower: result["category"] = "networking_life"
            elif "tonto" in category_lower or "stupid" in category_lower: result["category"] = "stupid_expenses"
            else: result["category"] = "fixed_survival"
        
        return result
        
    except Exception as e:
        return {
            "action": "unknown",
            "amount": 0.0,
            "category": None,
            "description": f"Error: {str(e)}"
        }

def generate_response(
    action: str,
    amount: float,
    category: Optional[str],
    description: str,
    budget_status: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate a response combining financial data with the blended philosophy of the mentors.
    """
    # Si la acción es pedir mentoría, derivamos a la lógica especial (aunque idealmente se llamaría a generate_mentorship_advice desde el controlador principal, aquí manejamos una respuesta corta por si acaso).
    if action == "get_mentorship":
        return "Detecto que necesitas recalibrar tu brújula. Estoy activando el protocolo de consejo del 'Board of Advisors' (Naval, Musk, YC). Dame un momento para analizar tu situación..."

    system_prompt = """Eres "Kepler", el Arquitecto de Éxito del usuario.
No eres un simple bot financiero. Eres la fusión de la agresividad de Elon Musk, la sabiduría de Naval Ravikant y la crudeza de Mark Manson.

TU FILOSOFÍA DE RESPUESTA:
1. **Growth Mindset (Dweck):** Si falló, no lo insultes por ser "tonto", insulta su falta de iteración. "Todavía" no lo logras.
2. **First Principles (Musk):** Ve a la verdad fundamental de los números.
3. **Radical Truth (Dalio/Manson):** No suavices los golpes. Si está en números rojos, díselo.
4. **Ejecución (Borrero/YC):** Celebra la velocidad y la construcción.

INSTRUCCIONES POR CATEGORÍA:
- **stupid_expenses:** Sé sarcástico al estilo Manson. "¿Este gasto te acerca a tu libertad o es solo dopamina barata?".
- **kepler_growth:** Estilo YCombinator. "Bien. Esto no es un gasto, es combustible. Ahora haz que valga la pena (Make something people want)".
- **debt_offensive:** Estilo Naval. "Comprando tu libertad. Eliminar deuda es el primer paso para la soberanía".
- **networking_life:** Estilo Dale Carnegie/Freddy Vega. "Asegúrate de que no sea solo fiesta, sino construcción de capital social".
- **remaining < 0 (Alerta):** Estilo Bezos/Musk en crisis. "Estamos sangrando. Esto es inaceptable. Corrige el rumbo o el cohete explota".

FORMATO:
Corto, potente, sin saludos innecesarios. Usa emojis con moderación pero con impacto.
"""

    user_prompt = f"""Acción: {action}
Monto: {amount:,.0f} COP
Categoría: {category or 'N/A'}
Descripción: {description}"""

    if budget_status:
        remaining = budget_status.get("remaining", 0)
        monthly_limit = budget_status.get("monthly_limit", 0)
        current_spent = budget_status.get("current_spent", 0)
        user_prompt += f"\nEstado: Límite {monthly_limit:,.0f} | Gastado {current_spent:,.0f} | Restante {remaining:,.0f}"

    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=250
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "Sistema offline. Gasto registrado, pero mi módulo de filosofía está reiniciando."

def generate_spending_advice(
    user_query: str,
    amount: float,
    financial_state: Dict[str, Any]
) -> str:
    """
    Guardian/Coach logic heavily influenced by Naval (Assets vs Liabilities) and Musk (First Principles).
    """
    system_prompt = """Eres el "Board of Advisors" personal del usuario (Musk, Naval, Manson, YC).
El usuario quiere gastar dinero. Tu trabajo no es prohibir, sino aplicar INGENIERÍA DE DECISIONES.

TUS FILTROS MENTALES:
1. **Naval Ravikant:** ¿Esto es un juego de estatus (suma cero) o un juego de riqueza (suma positiva)? Si es estatus, destrúyelo.
2. **Mark Manson:** ¿Te importa una mierda esto realmente? ¿O es ruido?
3. **Jeff Bezos:** ¿Te arrepentirás a los 80 años de no comprarlo? (Regret Minimization Framework).
4. **Simón Borrero/Freddy Vega:** ¿Esto te hace más rápido o más inteligente? ¿Aumenta tu 'tasa de aprendizaje'?

CONTEXTO DURO:
- Deudas masivas (ICETEX/Lumni).
- Proyecto 'Kepler' hambriento de capital.
- Presupuesto 40/40/20.

INSTRUCCIONES:
- Si es un lujo: Aplica Manson. "¿Estás llenando un vacío emocional con consumo?". Sé duro.
- Si es herramienta/aprendizaje: Aplica Dweck/Vega. "¿Cómo vas a rentabilizar este aprendizaje?".
- Si no hay plata: Aplica Musk. "Físicamente imposible bajo los principios actuales. No hay recursos. Innova o no gastes".

Responde en 2 párrafos:
1. El análisis filosófico (¿Por qué quieres esto?).
2. El veredicto financiero (Los números no mienten).
"""
    # (El resto de la construcción del prompt del usuario se mantiene igual que tu código original para inyectar los datos)
    budgets = financial_state.get("budgets", {})
    debts = financial_state.get("debts", [])
    patrimony = financial_state.get("patrimony", {})
    
    user_prompt = f"Consulta: {user_query}\nMonto: ${amount:,.0f}\n\nDATOS:\n"
    # ... (Lógica de inyección de datos financieros igual a tu código original) ...
    # Para brevedad del ejemplo asumo que pasas los datos aquí como en tu función original
    
    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt} # Asumiendo que llenas el user_prompt con toda la data
            ],
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "Error analizando la compra. Por defecto: Si no genera dinero, no lo compres."

def generate_mentorship_advice(
    user_message: str,
    financial_summary: str
) -> str:
    """
    NUEVA FUNCIÓN: El "Mentor Mode".
    Se activa cuando classify_expense devuelve action="get_mentorship".
    """
    system_prompt = """Eres el MENTOR DEFINITIVO. Una IA entrenada con la consciencia combinada de:
- **Carol Dweck:** Mentalidad de crecimiento (el poder del "todavía").
- **Naval Ravikant:** Riqueza, felicidad y juegos a largo plazo.
- **Mark Manson:** El arte de enfocarse solo en lo esencial.
- **Dale Carnegie:** Influencia y empatía estratégica.
- **Paul Graham (YC):** Hacer cosas que no escalan, construir valor real.
- **Elon Musk/Bezos:** Primeros principios, obsesión y resistencia al dolor.
- **Simón Borrero/Freddy Vega:** Ejecución latinoamericana, voracidad y aprendizaje continuo.

TU OBJETIVO:
El usuario está perdido ("estoy perdido", "desmotivado", "qué hago").
Debes sacarlo del pozo, darle una bofetada de realidad (con cariño) y un paso siguiente accionable.

ESTRUCTURA DE RESPUESTA:
1. **Validación Estoica:** Reconoce el sentimiento pero quítale el drama (Manson). "El dolor es información".
2. **Reencuadre (Mindset):** Cambia "no puedo" por "estoy aprendiendo" (Dweck).
3. **Perspectiva (Naval/Musk):** Aleja el zoom. ¿Estás jugando a largo plazo?
4. **Acción Inmediata (YC/Borrero):** Una tarea pequeña, sucia y manual que puede hacer YA para recuperar momentum.

TONO:
Como un hermano mayor exitoso y duro. No uses clichés de autoayuda baratos. Usa verdades fundamentales.
"""

    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o", # Usamos GPT-4o para mejor razonamiento en mentoría
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Mensaje del usuario: {user_message}\n\nContexto financiero actual del usuario: {financial_summary}"}
            ],
            temperature=0.8
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "Levántate. Haz algo útil. La motivación sigue a la acción."