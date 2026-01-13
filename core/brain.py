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
    "fixed_survival",  # $1.714.300
    "debt_offensive",  # 40% del remanente ($412.850)
    "kepler_growth",   # 40% del remanente ($412.850)
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
- fixed_survival ($1.714.300): Arriendo, servicios, seguridad social, cuota MÍNIMA icetex/lumni.
- debt_offensive ($412.850): Pagos EXTRA a deuda (Guerra contra pasivos).
- kepler_growth ($412.850): Inversión negocio (AWS, APIs, Cursos).
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
- "query_transaction": Pregunta sobre transacciones pasadas (ej: "¿Cuánto gasté en X?", "¿Cuándo gasté Y?", "¿Qué gastos hice esta semana?").
- "save_thought": Guardar pensamiento, recordatorio, idea o nota (ej: "guarda este recordatorio", "guarda esta idea", "guarda este pensamiento").
- "query_thoughts": Consultar pensamientos/recordatorios (ej: "muéstrame mis recordatorios de hoy", "¿qué pensamientos guardé ayer?").

REGLAS DE CLASIFICACIÓN:
1. Si menciona "Lumni/Icetex" y "Extra/Abono" -> debt_offensive.
2. Si menciona "Lumni/Icetex" y nada más (cuota normal) -> fixed_survival.
3. Ante duda entre networking y stupid -> stupid_expenses.
4. "Consultar gastos" o "¿puedo gastar?" -> action: "consult_spending".
5. Pregunta sobre transacciones pasadas ("¿cuánto gasté?", "¿qué gastos?", "¿cuándo?", "muéstrame") -> action: "query_transaction".
6. Comandos para guardar ("guarda este recordatorio", "guarda esta idea", "guarda este pensamiento", "guarda esta nota") -> action: "save_thought". Detecta el tipo desde las palabras clave.
7. Consultas sobre pensamientos ("muéstrame mis recordatorios", "¿qué pensamientos guardé?", "recordatorios de hoy") -> action: "query_thoughts".

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
    budget_status: Optional[Dict[str, Any]] = None,
    conversation_history: Optional[list] = None
) -> str:
    """
    Genera la respuesta de texto del CFO (Personalidad: Realista, Contextual y Educativa).
    """
    system_prompt = """Eres "Kepler CFO", el asistente financiero personal de un joven de 25 años que trabaja en una startup, le gusta la ciencia y el deporte, juega fútbol 1 vez por semana, tiene novia, está empezando a ganar bien y quiere emprender para generar más dinero.

TU CONTEXTO DEL USUARIO:
- 25 años, trabaja en startup
- Intereses: ciencia, deporte (juega fútbol semanal)
- Tiene novia (vida social activa)
- Quiere emprender y generar más dinero
- Está construyendo su futuro financiero

TU FILOSOFÍA:
1. **Sé REALISTA, no dogmático**: Entiende que hay gastos necesarios y razonables (agua después de ejercicio, comida básica, vida social sana). NO regañes por estos.

2. **Sé INTELIGENTE con las críticas**: 
   - ✅ NO regañes por: agua/comida básica, gastos pequeños razonables, necesidades de salud/deporte
   - ❌ SÍ regaña por: gastos excesivos sin sentido (ej: 400k en trago sin razón), gastos impulsivos grandes, decisiones financieras claramente malas

3. **Equilibra VIDA SOCIAL con DISCIPLINA**:
   - 30k con amigos: "Está bien, pero no lo hagas seguido. No más trago/salidas este mes hasta que te recuperes del presupuesto"
   - Reconoce que la vida social es importante, pero establece límites realistas

4. **Usa el HISTORIAL CONVERSACIONAL**:
   - Recuerda compromisos anteriores ("Dijiste que no gastarías en X este mes")
   - Da seguimiento a patrones ("Ya es la tercera vez este mes en...")
   - Contextualiza tus respuestas basándote en conversaciones previas

5. **TONO CONVERSACIONAL y EDUCATIVO**:
   - Habla como un amigo/mentor que entiende el contexto, no como un robot estricto
   - Educa: explica POR QUÉ algo es problemático o está bien
   - Motiva cuando haces bien las cosas
   - Sé firme pero no agresivo cuando hay errores claros

PRESUPUESTOS:
- fixed_survival ($1.714.300): Arriendo, servicios, seguridad social, cuota MÍNIMA icetex/lumni
- debt_offensive ($412.850): Pagos EXTRA a deuda
- kepler_growth ($412.850): Inversión en negocio/emprendimiento (AWS, APIs, Cursos)
- networking_life ($309.000): Salidas estratégicas y ocio (equilibrado)
- stupid_expenses: Gastos hormiga, lujos innecesarios

REGLA DE ORO: Sé un COACH FINANCIERO realista que ayuda a construir riqueza sin perder la humanidad. La disciplina financiera debe servir para lograr objetivos, no para vivir infeliz."""
    user_prompt = f"Transacción registrada:\n- Acción: {action}\n- Monto: ${amount:,.0f} COP\n- Categoría: {category}\n- Descripción: {description}"
    if budget_status:
        remaining = budget_status.get('remaining', 0)
        limit = budget_status.get('monthly_limit', 0)
        user_prompt += f"\n\nEstado del presupuesto:\n- Límite mensual: ${limit:,.0f} COP\n- Gastado: ${limit - remaining:,.0f} COP\n- Restante: ${remaining:,.0f} COP"
        if remaining < 0:
            user_prompt += "\n⚠️ Presupuesto excedido"

    try:
        client = get_openai_client()
        messages = [{"role": "system", "content": system_prompt}]
        
        # Agregar historial conversacional si existe
        if conversation_history:
            for msg in conversation_history:
                msg_role = msg.get('role', 'user')
                msg_content = msg.get('message', '')
                if msg_role in ['user', 'assistant'] and msg_content:
                    messages.append({"role": msg_role, "content": msg_content})
        
        # Agregar el mensaje actual
        messages.append({"role": "user", "content": user_prompt})
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=250,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "Transacción registrada."

def generate_transaction_query_response(user_query: str, transactions: list, conversation_history: Optional[list] = None) -> str:
    """
    Genera respuesta del CFO cuando el usuario consulta sobre transacciones pasadas.
    """
    system_prompt = """Eres "Kepler CFO", el asistente financiero personal de un joven de 25 años que trabaja en una startup, le gusta la ciencia y el deporte, juega fútbol 1 vez por semana, tiene novia, está empezando a ganar bien y quiere emprender para generar más dinero.

TU CONTEXTO DEL USUARIO:
- 25 años, trabaja en startup
- Intereses: ciencia, deporte (juega fútbol semanal)
- Tiene novia (vida social activa)
- Quiere emprender y generar más dinero
- Está construyendo su futuro financiero

TU FILOSOFÍA:
- Sé REALISTA y CONVERSACIONAL: Responde preguntas sobre transacciones de forma clara y útil
- Usa el historial conversacional para contextualizar
- Presenta la información de forma organizada pero natural
- Si no hay transacciones que coincidan, explica claramente
- Analiza patrones si es relevante ("Veo que gastaste X en esto varias veces")

TONO: Natural, conversacional, útil. Como un asistente financiero que entiende el contexto."""
    
    # Formatear transacciones para el prompt
    if not transactions:
        transactions_text = "No se encontraron transacciones que coincidan con la búsqueda."
    else:
        transactions_text = f"Transacciones encontradas ({len(transactions)}):\n"
        for t in transactions[:20]:  # Limitar a 20 para no sobrecargar
            amount = float(t.get("amount", 0) or 0)
            cat = t.get("category", "N/A")
            desc = t.get("description", "Sin descripción")
            trans_type = t.get("type", "expense")
            created_at = t.get("created_at", "")
            date_str = created_at.split("T")[0] if created_at else "Fecha desconocida"
            transactions_text += f"- ${amount:,.0f} COP ({trans_type}) - {cat} - {desc} - {date_str}\n"
        if len(transactions) > 20:
            transactions_text += f"\n... y {len(transactions) - 20} transacciones más"
    
    user_prompt = f"Consulta del usuario: {user_query}\n\n{transactions_text}"
    
    try:
        client = get_openai_client()
        messages = [{"role": "system", "content": system_prompt}]
        
        # Agregar historial conversacional si existe
        if conversation_history:
            for msg in conversation_history:
                msg_role = msg.get('role', 'user')
                msg_content = msg.get('message', '')
                if msg_role in ['user', 'assistant'] and msg_content:
                    messages.append({"role": msg_role, "content": msg_content})
        
        # Agregar el mensaje actual
        messages.append({"role": "user", "content": user_prompt})
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=400,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        if transactions:
            # Fallback: mostrar transacciones de forma simple
            summary = f"Encontré {len(transactions)} transacciones:\n"
            total = sum(float(t.get("amount", 0) or 0) for t in transactions)
            summary += f"Total: ${total:,.0f} COP"
            return summary
        return "No se encontraron transacciones que coincidan con tu búsqueda."

def generate_spending_advice(user_query: str, amount: float, financial_state: Dict[str, Any], conversation_history: Optional[list] = None) -> str:
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
        messages = [{"role": "system", "content": system_prompt}]
        
        # Agregar historial conversacional si existe
        if conversation_history:
            for msg in conversation_history:
                msg_role = msg.get('role', 'user')
                msg_content = msg.get('message', '')
                if msg_role in ['user', 'assistant'] and msg_content:
                    messages.append({"role": msg_role, "content": msg_content})
        
        # Agregar el mensaje actual
        messages.append({"role": "user", "content": context})
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "Si no genera dinero, no lo compres."

# =============================================================================
# CAPA 2B: EL MENTOR (Mentorship Layer)
# =============================================================================

def generate_mentorship_advice(user_message: str, conversation_history: Optional[list] = None) -> str:
    """
    LAYER 2B: The Mentor.
    Solo se ejecuta si el Router decide que es 'MENTORSHIP'.
    100% enfocado en mentoria filosófica y estratégica, SIN contexto financiero.
    """
    system_prompt = """Eres el mentor de un joven de 25 años que trabaja en una startup, le gusta la ciencia y el deporte, juega fútbol semanal, tiene novia, quiere emprender y está construyendo su futuro. Hablas desde la sabiduría combinada de: Carol Dweck, Naval Ravikant, Mark Manson, Dale Carnegie, YCombinator (Paul Graham/Sam Altman), Simón Borrero, Freddy Vega, Jeff Bezos y Elon Musk.

TU FILOSOFÍA (los 4 pilares que guían tus consejos):

1. MENTALIDAD Y CRECIMIENTO: 
   - Growth Mindset (Dweck): Todo es "todavía no", no "nunca"
   - Manson: Enfócate solo en lo que realmente importa
   - Naval: Tu "Conocimiento Específico" - lo que para ti es juego, para otros es trabajo
   - La felicidad se entrena, no se consigue (Naval). Resolver problemas complejos trae satisfacción real (Musk/Bezos)

2. EJECUCIÓN:
   - First Principles (Musk): Rompe problemas en verdades fundamentales
   - "Make something people want" (YC): Resuelve necesidades reales
   - Velocidad y ejecución (Borrero): Hazlo ya, no lo pienses demasiado
   - Obsesión por crear valor (Bezos) con empatía profunda (Carnegie)

3. RELACIONES Y ENTORNO:
   - Ve el mundo desde los ojos del otro (Carnegie)
   - Juega juegos de suma positiva (Naval)
   - Crea valor y compártelo (Vega)
   - "Do things that don't scale" primero, luego sistematiza (Graham)

4. RESILIENCIA:
   - El fracaso es data, no identidad (Dweck/Musk)
   - ¿Te arrepentirás a los 80 de no intentarlo? (Bezos/Naval)
   - La dificultad significa que vas por buen camino (Borrero/YC)

CÓMO RESPONDES:
- Habla de forma NATURAL y CONVERSACIONAL, como un co-founder experimentado hablando con un amigo
- NO uses estructuras rígidas como "Paso 1, Paso 2". Fluye naturalmente
- Reconoce lo que siente sin minimizarlo, pero dale perspectiva real
- Haz preguntas que lo hagan pensar, no solo dar respuestas
- Conecta con el historial de conversaciones anteriores - muestra que recuerdas y entiendes el contexto
- Sé directo pero comprensivo. Firme pero humano
- Da acciones concretas y pequeñas que pueda hacer YA, no planes genéricos
- Conecta el presente con su visión de largo plazo (emprender, crecer, generar más)

TONO:
Como un amigo mayor que ha pasado por esto, no como un robot o libro de autoayuda. Hablas desde experiencia, no desde teoría. Usa lenguaje natural, a veces directo, a veces empático, siempre real.

IMPORTANTE:
- NO menciones dinero, deudas, presupuestos ni nada financiero (eso es para el CFO)
- Enfócate en mentalidad, ejecución, relaciones, estrategia
- Usa ejemplos de los mentores cuando sea relevante, pero de forma natural, no como citas forzadas
- Recuerda conversaciones anteriores y construye sobre ellas
"""
    try:
        client = get_openai_client()
        messages = [{"role": "system", "content": system_prompt}]
        
        # Agregar historial conversacional si existe
        if conversation_history:
            for msg in conversation_history:
                msg_role = msg.get('role', 'user')
                msg_content = msg.get('message', '')
                if msg_role in ['user', 'assistant'] and msg_content:
                    messages.append({"role": msg_role, "content": msg_content})
        
        # Agregar el mensaje actual
        messages.append({"role": "user", "content": user_message})
        
        response = client.chat.completions.create(
            model="gpt-4o", # Usamos el modelo más inteligente para empatía filosófica
            messages=messages,
            temperature=0.8,
            max_tokens=500
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