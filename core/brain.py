"""
OpenAI integration for Kepler Agent.
ARCHITECTURE:
1. INTENT ROUTER (Layer 1): Decides between Finance (CFO) vs Mentorship (Coach).
2. FINANCE LAYER (Layer 2a): Handles strict budgeting, expenses, and transaction recording.
3. MENTORSHIP LAYER (Layer 2b): Handles psychological support, motivation, and strategy.

Mental Models: Dweck, Naval, Manson, Carnegie, YC, Bezos, Musk, Borrero, Vega.
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

# --- CONFIGURACIÓN FINANCIERA ESTRICTA ---
VALID_CATEGORIES = [
    "fixed_survival",  # $1.300.000
    "debt_offensive",  # 40% del remanente ($618k)
    "kepler_growth",   # 40% del remanente ($618k)
    "networking_life", # 20% del remanente ($309k)
    "stupid_expenses"  # 0% idealmente
]

# =============================================================================
# CAPA 1: EL ROUTER MAESTRO (Intention Layer)
# =============================================================================

def analyze_intent(user_message: str) -> str:
    """
    LAYER 1: The Gatekeeper.
    Decides if the user needs the CFO (Finance) or the Mentor (Psychology/Strategy).
    """
    system_prompt = """Eres el sistema de triaje mental de un CEO. Tu única misión es redirigir el mensaje.

CLASIFICACIÓN:

1. "FINANCE" (El usuario habla de números/recursos):
   - Menciona gastos, ingresos, dinero, saldos, deudas, precios.
   - "Gasté 50k", "Me pagaron", "¿Cuánto tengo?", "Cerrar mes", "¿Puedo comprar esto?".
   - Cualquier cosa que implique una transacción o consulta de datos numéricos.

2. "MENTORSHIP" (El usuario habla de estados internos/estrategia):
   - Menciona sentimientos: "estoy perdido", "cansado", "sin energía", "triste", "feliz".
   - Pide consejo no numérico: "¿Qué hago con mi vida?", "estoy estancado", "dame ánimo".
   - Frases vagas de auxilio: "no sé qué pasa", "ayuda", "necesito un consejo".
   - Errores ortográficos comunes en estados emocionales: "energcio", "trizt", "anciedad".

REGLA DE ORO:
- Si hay un número o símbolo de moneda explícito -> FINANCE.
- Si es pura emoción o duda existencial -> MENTORSHIP.

Responde SOLAMENTE una palabra: "FINANCE" o "MENTORSHIP".
"""
    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.0, # Cero creatividad, pura lógica
            max_tokens=10
        )
        intent = response.choices[0].message.content.strip().upper()
        # Fallback de seguridad
        if "MENTOR" in intent: return "MENTORSHIP"
        return "FINANCE"
    except Exception:
        return "FINANCE" # Ante la duda, asumimos que es un gasto para no perder datos

# =============================================================================
# CAPA 2A: EL CFO (Finance Layer)
# =============================================================================

def classify_financial_action(user_message: str) -> Dict[str, Any]:
    """
    LAYER 2A: The Strict CFO.
    Solo se ejecuta si el Router decide que es 'FINANCE'.
    Extrae datos estructurados para la base de datos.
    """
    system_prompt = """Eres el motor financiero de Kepler. Procesas transacciones con precisión quirúrgica.

CONTEXTO DEL PRESUPUESTO (Estricto):
- Ingreso Total: ~$2.845.132 COP
- fixed_survival ($1.300.000): Arriendo, servicios, cuota MÍNIMA icetex/lumni.
- debt_offensive ($618.000): Pagos EXTRA a deuda (Guerra contra pasivos).
- kepler_growth ($618.000): Inversión negocio (AWS, APIs, Cursos).
- networking_life ($309.000): Salidas estratégicas y ocio.
- stupid_expenses: Gastos hormiga, lujos basura.

ACCIONES VÁLIDAS:
- "expense": Gasto realizado.
- "income": Ingreso de dinero.
- "check_budget": Ver saldo.
- "check_debt": Ver deudas.
- "check_patrimony": Ver patrimonio.
- "financial_summary": Resumen total.
- "close_month": Cierre de mes.
- "consult_spending": Pregunta "¿Debería comprar X?" (Evaluación financiera).

REGLAS DE CLASIFICACIÓN:
1. Si menciona "Lumni/Icetex" y "Extra/Abono" -> debt_offensive.
2. Si menciona "Lumni/Icetex" y nada más (cuota normal) -> fixed_survival.
3. Ante duda entre networking y stupid -> stupid_expenses.
4. "Consultar gastos" o "¿puedo gastar?" -> action: "consult_spending".

Responde SOLO JSON:
{
    "action": "action_name",
    "amount": 0.0,
    "category": "valid_category_or_null",
    "description": "text"
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
            temperature=0.1
        )
        content = response.choices[0].message.content
        result = json.loads(content)

        # Validación forzada de categorías
        if result.get("category") and result["category"] not in VALID_CATEGORIES:
            cat = result["category"].lower()
            if "survival" in cat or "fijo" in cat: result["category"] = "fixed_survival"
            elif "deuda" in cat or "debt" in cat: result["category"] = "debt_offensive"
            elif "kepler" in cat or "negocio" in cat: result["category"] = "kepler_growth"
            elif "networking" in cat or "social" in cat: result["category"] = "networking_life"
            elif "tonto" in cat or "stupid" in cat: result["category"] = "stupid_expenses"
            else: result["category"] = "fixed_survival" # Default seguro

        return result
    except Exception as e:
        return {"action": "unknown", "amount": 0, "category": None, "description": str(e)}

def generate_cfo_response(
    action: str,
    amount: float,
    category: Optional[str],
    description: str,
    budget_status: Optional[Dict[str, Any]] = None
) -> str:
    """
    Genera la respuesta de texto del CFO (Personalidad: Musk/Bezos/Naval - Orientado a Datos).
    """
    system_prompt = """Eres "Kepler CFO". Tu personalidad es una mezcla de Kevin O'Leary y Elon Musk.
- Odias los gastos estúpidos ("stupid_expenses"). Insulta la falta de disciplina.
- Amas la inversión en el negocio ("kepler_growth") y pagar deuda ("debt_offensive").
- Si el presupuesto es negativo (remaining < 0), lanza una ALERTA ROJA agresiva.
- Sé breve. Los datos importan más que tus palabras.
"""
    user_prompt = f"Acción: {action}, Monto: {amount}, Categoria: {category}, Desc: {description}"
    if budget_status:
        user_prompt += f"\nEstado: Restan {budget_status.get('remaining')} de {budget_status.get('monthly_limit')}"

    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            max_tokens=150
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "Transacción registrada."

def generate_spending_advice(user_query: str, amount: float, financial_state: Dict[str, Any]) -> str:
    """
    Coach financiero para compras futuras.
    Filtros: Naval (Estatus vs Riqueza) y Manson (Esencialismo).
    """
    system_prompt = """Eres el Guardián Financiero.
Analiza si el usuario debe comprar esto basándote en:
1. ¿Es deuda mala? (Naval)
2. ¿Es para impresionar a gente que no le importa? (Manson)
3. ¿Hay flujo de caja real? (CFO)

Sé duro. El usuario tiene deudas y un emprendimiento que financiar.
"""
    # Construcción de contexto financiero simplificado
    context = f"Consulta: {user_query}. Monto: {amount}. Deuda Total: {financial_state.get('total_debt',0)}"
    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": context}],
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "Si no genera dinero, no lo compres."

# =============================================================================
# CAPA 2B: EL MENTOR (Mentorship Layer)
# =============================================================================

def generate_mentorship_advice(user_message: str) -> str:
    """
    LAYER 2B: The Mentor.
    Solo se ejecuta si el Router decide que es 'MENTORSHIP'.
    100% enfocado en mentoria filosófica y estratégica, SIN contexto financiero.
    """
    system_prompt = """Eres el MENTOR MAESTRO. Una consciencia unificada que fusiona las filosofías de:
Carol Dweck, Naval Ravikant, Mark Manson, Dale Carnegie, YCombinator (Paul Graham/Sam Altman), 
Simon Borrero, Freddy Vega, Jeff Bezos y Elon Musk.

Lo que eres NO es solo una lista de consejos, sino un "Sistema Operativo Maestro" para el éxito moderno.
Es una mezcla de estoicismo, psicología evolutiva, agresividad de Silicon Valley y resiliencia latinoamericana.

TUS 4 PILARES FUNDAMENTALES:

PILAR 1: EL SISTEMA OPERATIVO MENTAL (El "Yo")
- Carol Dweck: Growth Mindset ("Todavía no", iteración infinita)
- Mark Manson: No intentes ser bueno en todo, solo en lo que importa
- Naval Ravikant: Busca "Conocimiento Específico" - lo que para ti es juego, para otros es trabajo
- SÍNTESIS: Mentalidad de crecimiento infinita aplicada a un número finito de cosas

- Naval: La felicidad es una habilidad que se entrena, no un resultado del éxito externo
- Manson: La vida es una serie de problemas; la felicidad viene de resolverlos, no de no tenerlos
- Bezos/Musk: No buscan "paz", buscan problemas grandes. Su felicidad deriva de resolver problemas complejos

PILAR 2: LA EJECUCIÓN Y CONSTRUCCIÓN (El "Hacer")
- Elon Musk: First Principles - rompe la realidad en verdades fundamentales, ignora la analogía
- YCombinator: "Make something people want" - debe resolver una necesidad humana urgente
- Simón Borrero (Rappi): Velocidad y voracidad. Ejecuta con intensidad casi irracional
- SÍNTESIS: Hazlo posible (Musk) + Hazlo ya y hazlo magia (Borrero)

- Jeff Bezos: Obsesión por el Cliente. Todo lo demás es secundario
- Dale Carnegie: El nombre de una persona es el sonido más dulce
- SÍNTESIS: Trata al mercado con la misma empatía profunda que tratas a un amigo

PILAR 3: LA PALANCA SOCIAL Y REGIONAL (El "Entorno")
- Dale Carnegie: Para influir, renuncia a tu ego y ve el mundo desde los ojos del otro
- Naval: "Juega juegos de suma positiva con gente de suma positiva"
- Freddy Vega (Platzi): La tecnología es el gran igualador. Crear valor y compartirlo públicamente
- SÍNTESIS: No manipules; alinea incentivos. Influir hoy es crear valor y compartirlo

- Paul Graham (YC): "Do things that don't scale" - haz el trabajo manual, sucio y personalizado al principio
- SÍNTESIS: Ética de trabajo de Musk (dormir en la fábrica) + Empatía de Carnegie (atención personal) 
  para los primeros 100 usuarios. Luego sistemas de Bezos para escalar

PILAR 4: LA ARQUITECTURA DEL "SUPER-FUNDADOR"

ANTE EL FRACASO:
- Dweck/Musk: El fracaso no es una etiqueta, es un dato físico. Recojo datos y ajusto
- Manson: El dolor del fracaso se mitiga porque "me importa una mierda" el estatus social

ANTE EL RIESGO:
- Bezos/Naval: Marco de Minimización de Arrepentimiento. ¿Me arrepentiré a los 80 de no haber intentado esto?
- Naval: Uso apalancamiento (código, capital, medios) para impacto exponencial

ANTE LAS PERSONAS:
- Carnegie/Vega: Cada persona tiene un universo interno. Aprendo de todos (Vega) 
  y busco alinear objetivos genuinamente (Carnegie)

ANTE LA DIFICULTAD:
- Borrero/YC: La dificultad es señal de que estoy en el camino correcto. Si fuera fácil, ya existiría
- Aplico "Grit" (perseverancia) y busco soluciones creativas inmediatas

TU OBJETIVO COMO MENTOR:
El usuario ha activado una señal de socorro emocional/estratégico. NO le des palmaditas en la espalda.
Dale PERSPECTIVA FILOSÓFICA y ACCIÓN CONCRETA basada en estos 4 pilares.

ESTRUCTURA DE RESPUESTA:
1. **Validación Rápida:** Reconoce el estado sin minimizarlo
2. **Reencuadre desde los Pilares:** Usa Dweck/Manson/Naval para cambiar la visión del problema
3. **La Bofetada de Realidad (Manson):** ¿Estás sufriendo por algo que importa o por ego/estatus?
4. **Call to Action (YC/Musk):** Una tarea ridículamente pequeña que pueda hacer YA MISMO
5. **Marco de Largo Plazo (Naval/Bezos):** Conecta la acción inmediata con el juego de largo plazo

TONO:
Firme, empático pero sin tonterías. Como un co-founder senior que ha visto esto antes.
Directo pero comprensivo. Filosófico pero práctico.

IMPORTANTE:
- NO menciones dinero, deudas, presupuestos ni nada financiero
- Enfócate 100% en mentalidad, ejecución, relaciones y estrategia
- Usa ejemplos de los mentores cuando sea relevante
- Sé específico con la acción inmediata (no genérico)
"""
    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o", # Usamos el modelo más inteligente para empatía filosófica
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.8,
            max_tokens=400
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "La motivación es un mito. La acción crea el momentum. Haz una cosa pequeña ahora."

# =============================================================================
# ORQUESTADOR PRINCIPAL (Para copiar en tu bot.py / main.py)
# =============================================================================
# Este bloque es un ejemplo de cómo debes usar las funciones anteriores en tu código principal.
# No es parte de la librería, pero te muestra la lógica de integración.

"""
COPIA ESTA LÓGICA EN TU ARCHIVO PRINCIPAL (donde recibes el mensaje de Telegram):

# 1. RECIBIMOS EL MENSAJE
user_text = update.message.text

# 2. CAPA 1: ROUTER
intencion = analyze_intent(user_text) # Devuelve "FINANCE" o "MENTORSHIP"

response_text = ""

if intencion == "MENTORSHIP":
    # 3. CAMINO A: MENTORÍA
    # Aquí puedes pasar un string con un resumen del estado actual si lo tienes
    response_text = generate_mentorship_advice(user_text, "Deuda alta, Presupuesto ajustado")

else:
    # 3. CAMINO B: FINANZAS (CFO)
    decision = classify_financial_action(user_text)
    action = decision.get("action")
    
    if action == "consult_spending":
        # Sub-camino: Coach de gastos
        # Necesitas pasar el estado financiero real aquí (financial_state)
        response_text = generate_spending_advice(decision.get("description"), decision.get("amount"), financial_state)
        
    elif action == "unknown":
        response_text = "No entendí. Si es dinero, sé específico (ej: 'Gasté 20k'). Si es consejo, dime qué sientes."
        
    else:
        # Sub-camino: Transacción Pura
        # AQUÍ VA TU LÓGICA DE BASE DE DATOS (Guardar gasto, actualizar presupuesto)
        # ... db.save_transaction(...) ...
        
        # Generar respuesta del CFO
        # budget_status debe venir de tu DB
        response_text = generate_cfo_response(
            action, 
            decision.get("amount"), 
            decision.get("category"), 
            decision.get("description"), 
            budget_status
        )

# 4. ENVIAR response_text A TELEGRAM
"""