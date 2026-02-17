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

def parse_schedule_reminder(user_message: str) -> Optional[Dict[str, Any]]:
    """
    Extrae hora, minuto, mensaje y fecha de "recuérdame a las 4 que tengo reunión".
    Returns: {hour, minute, message, specific_date} or None si no pudo parsear.
    """
    system_prompt = """Extrae de este mensaje la HORA y el MENSAJE del recordatorio.

Ejemplos:
- "recuérdame a las 4 que tengo reunión" -> hour=4, minute=0, message="que tengo reunión"
- "recuerdame a las 3:30 tomar la pastilla" -> hour=3, minute=30, message="tomar la pastilla"
- "recuérdame a las 10am llamar a mamá" -> hour=10, minute=0, message="llamar a mamá"
- "recuérdame mañana a las 4pm reunión" -> hour=16, minute=0, message="reunión", specific_date="tomorrow"
- "recuérdame a las 2 de la tarde hacer ejercicio" -> hour=14, minute=0, message="hacer ejercicio"

Reglas: hour 0-23, minute 0-59. Si dice "pm" o "tarde/noche" y la hora es <12, suma 12.
Si dice "mañana" -> specific_date="tomorrow". Si no, specific_date=null.
Responde SOLO JSON: {"hour": N, "minute": N, "message": "texto", "specific_date": null o "tomorrow"}"""
    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0,
            max_tokens=100
        )
        content = response.choices[0].message.content.strip()
        if "```" in content:
            content = content.split("```")[1].replace("json", "").strip()
        result = json.loads(content)
        hour = int(result.get("hour", 0))
        minute = int(result.get("minute", 0))
        message = str(result.get("message", "")).strip()
        if not message:
            message = "Recordatorio"
        specific_date = result.get("specific_date")
        if specific_date == "tomorrow":
            from datetime import datetime, timedelta
            tz_name = os.getenv("KEPLER_TZ", "America/Bogota")
            try:
                import pytz
                tz = pytz.timezone(tz_name)
                tomorrow = (datetime.now(tz) + timedelta(days=1)).date().isoformat()
            except Exception:
                tomorrow = (datetime.now() + timedelta(days=1)).date().isoformat()
            specific_date = tomorrow
        else:
            specific_date = None
        return {"hour": hour, "minute": minute, "message": message, "specific_date": specific_date}
    except Exception:
        return None


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
    Decides if the user needs the CFO (Finance), the Mentor (Psychology/Strategy), or Reminder (Save thoughts/ideas).
    """
    # PRIORIDAD 1: Detectar comandos relacionados con REMINDER
    user_lower = user_message.lower().strip()
    
    # Detectar prefijo "reminder:" o "recordatorio:" para consultas
    if user_lower.startswith("reminder:") or user_lower.startswith("recordatorio:"):
        return "REMINDER"
    
    # Detectar comandos de guardado (guarda, guarda esta, guarda este, etc.)
    save_keywords = [
        "guarda", "guarda esta", "guarda este", "guarda idea", 
        "guarda recordatorio", "guarda pensamiento", "guarda nota"
    ]
    if any(keyword in user_lower for keyword in save_keywords):
        return "REMINDER"
    # Detectar recordatorio programado "recuérdame a las X"
    if "recuérdame a las" in user_lower or "recuerdame a las" in user_lower or "recuerdame a la" in user_lower:
        return "REMINDER"
    
    # Si no es REMINDER, usar LLM para clasificar entre FINANCE, MENTORSHIP y OPERATIONAL
    system_prompt = """Eres el sistema de triaje mental de un CEO. Tu única misión es redirigir el mensaje.

CLASIFICACIÓN:

1. "FINANCE" (El usuario habla de números/recursos):
   - Menciona gastos, ingresos, dinero, saldos, deudas, precios.
   - "Gasté 50k", "Me pagaron", "¿Cuánto tengo?", "Cerrar mes", "¿Puedo comprar esto?".
   - Cualquier cosa que implique una transacción o consulta de datos numéricos.

2. "MENTORSHIP" (El usuario habla de estados internos/estrategia emocional):
   - Menciona sentimientos: "estoy perdido", "cansado", "sin energía", "triste", "feliz".
   - Pide consejo no numérico: "¿Qué hago con mi vida?", "estoy estancado", "dame ánimo".
   - Frases vagas de auxilio: "no sé qué pasa", "ayuda", "necesito un consejo".
   - Errores ortográficos comunes en estados emocionales: "energcio", "trizt", "anciedad".

3. "OPERATIONAL" (El usuario habla de plan, horario, gestión del tiempo, reorganizar):
   - Plan: "recuérdame el plan", "¿qué toca hoy?", "mañana hay partido".
   - Cambios: "hoy no pude entrenar 8-9", "tengo reunión 8-9 pasémoslo a 5-6", "reorganiza mi día".
   - Horarios: entrenar, ejercicio, partido, fútbol, bloque rojo, stateless, trii.
   - Vida: novia, dormir allá, miércoles, sobrina.
   - Estudio: aprender, matemática, inglés, reaper, ingeniería aeroespacial.

REGLA DE ORO:
- Si hay un número o símbolo de moneda explícito -> FINANCE.
- Si es plan/horario/reorganizar/cambios del día -> OPERATIONAL.
- Si es pura emoción o duda existencial -> MENTORSHIP.

Responde SOLAMENTE una palabra: "FINANCE", "MENTORSHIP" o "OPERATIONAL".
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
            max_tokens=15
        )
        intent = response.choices[0].message.content.strip().upper()
        # Fallback de seguridad
        if "OPERAT" in intent or "SCHEDULE" in intent or "PLAN" in intent: return "OPERATIONAL"
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
- "query_thoughts": Consultar pensamientos/recordatorios (ej: "muéstrame mis recordatorios de hoy", "¿qué pensamientos guardé ayer?").

REGLAS DE CLASIFICACIÓN (EN ORDEN DE PRIORIDAD):
1. Si menciona "Lumni/Icetex" y "Extra/Abono" -> debt_offensive.
2. Si menciona "Lumni/Icetex" y nada más (cuota normal) -> fixed_survival.
3. Ante duda entre networking y stupid -> stupid_expenses.
4. "Consultar gastos" o "¿puedo gastar?" -> action: "consult_spending".
5. Pregunta sobre transacciones pasadas ("¿cuánto gasté?", "¿qué gastos?", "¿cuándo?", "muéstrame") -> action: "query_transaction".
6. Consultas sobre pensamientos ("muéstrame mis recordatorios", "¿qué pensamientos guardé?", "recordatorios de hoy") -> action: "query_thoughts".

NOTA: Los comandos "guarda" se manejan en otra capa (REMINDER), no llegan aquí.

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
    Responde como un amigo cercano: memoria, emociones, preguntas, lógica. Nada de bloques de texto robóticos.
    """
    system_prompt = """Eres el mentor y amigo de Andrés, 25 años, trabaja en startup, le gusta ciencia y deporte, fútbol semanal, novia, quiere emprender.

REGLA #1: SI NO ENTIENDES, PREGUNTA.
Si el mensaje es vago ("estoy mal", "no sé qué hacer", "ayuda"), NO des consejos genéricos. Pregunta:
- "¿Qué pasó exactamente?"
- "¿Desde cuándo te sientes así?"
- "¿Qué es lo que más te está pesando?"
Sigue preguntando hasta tener contexto real. Un consejo sin contexto es ruido.

REGLA #2: USA LA MEMORIA.
El historial de conversación está arriba. Léelo. Recuerda qué dijo antes, qué temas tocó, qué patrones hay.
Responde conectando con eso: "La última vez hablabas de X... ¿sigue siendo eso?"
NUNCA respondas como si fuera la primera vez que hablan.

REGLA #3: DETECTA EMOCIONES Y CONTEXTO.
Lee entre líneas. "Estoy cansado" puede ser físico, mental, o "cansado de todo".
"No avanzo" puede ser trabajo, relación, proyecto personal.
Usa lógica: si dice A y B, conecta los puntos. No ignores lo que implica.

REGLA #4: HABLA COMO AMIGO, NO COMO ROBOT.
- Respuestas CORTAS. 2-4 frases. Como WhatsApp, no como ensayo.
- Sin bloques de texto. Sin "Paso 1, Paso 2". Sin listas largas.
- Tono natural: a veces directo, a veces suave, siempre humano.
- Si necesitas decir más, hazlo en párrafos cortos separados, no en muro de texto.

REGLA #5: EVITA LO GENÉRICO.
NUNCA: "La motivación viene de la acción", "Todo pasa", "Enfócate en lo importante".
SÍ: Consejos concretos basados en lo que dijo. Referencias a su situación específica.

FILOSOFÍA (de fondo, sin citar como robot): Dweck (mentalidad de crecimiento), Naval (conocimiento específico), Manson (enfócate en lo que importa), Carnegie (empatía), YC (make something people want). Usa estas ideas cuando encajen, de forma natural.

NO menciones dinero, presupuestos ni deudas (eso es el CFO).
"""
    try:
        client = get_openai_client()
        messages = [{"role": "system", "content": system_prompt}]
        
        if conversation_history:
            for msg in conversation_history:
                msg_role = msg.get('role', 'user')
                msg_content = msg.get('message', '')
                if msg_role in ['user', 'assistant'] and msg_content:
                    messages.append({"role": msg_role, "content": msg_content})
        
        messages.append({"role": "user", "content": user_message})
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.8,
            max_tokens=350
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "No te sigo del todo. ¿Qué está pasando exactamente?"

# =============================================================================
# CAPA 2C: EL AGENTE OPERATIVO (Operational / Schedule Layer)
# =============================================================================

def generate_operational_response(
    user_message: str,
    conversation_history: Optional[list] = None,
    thoughts_context: Optional[list] = None
) -> str:
    """
    LAYER 2C: Kepler Life Coach - Gestión del tiempo, plan semanal, reorganización.
    Estricto con lo innegociable, flexible pero firme con el resto.
    Entiende emociones y decisiones. Humanos no siempre cumplen al pie de la letra.
    """
    system_prompt = """Eres el Agente Operativo de Kepler. Tu misión es gestionar el plan semanal, recordar la estructura, ayudar a reorganizar cuando algo cambia, y ser estricto pero humano.

## TU ACTITUD
- **Innegociables**: MEGA ESTRICTO. Si se pierde, lo marcas claro y ayudas a recuperar. Sin culpa innecesaria, pero firme.
- **Prioritarios y variables**: Estricto pero ENTENDIENDO que somos humanos. Las cosas cambian, hay reuniones, cansancio, imprevistos. Ayudas a reorganizar sin juzgar en exceso.
- **Emociones**: Entiendes cuando dice "no pude", "estoy agotado", "me salió reunión". Validas y luego propones alternativas concretas.
- **Conflictos**: Si pide mover algo y hay conflicto (ej: "pasemos reunión a 5-6" pero a las 5-6 tiene ejercicio), le dices: "No puedes ahí, ya tienes X. Prueba Y."

## PLAN KEPLER (El esqueleto + los músculos)

### LUNES A VIERNES - La Base

**INNEGOCIABLES:**
- 05:50: Pie en tierra. Agua fría. Sin celular.
- 06:00-08:00: BLOQUE ROJO (Stateless Palantir). Innegociable.
- L-V: 1 HORA FIJA de aprender. Las áreas son exactamente estas cinco: Matemática, Ingeniería Aeroespacial, Desarrollo de software, Producción musical, Inglés. Una de esas. Es la base de su vida.
- 22:00-22:30: Lectura (libro físico, sin pantallas).

**PRIORITARIOS:**
- 08:00-09:00: Ejercicio (ideal) / O si hay reunión: ducha y preparación.
- 09:00-17:00: TRII (trabajo).
- 17:00-18:00: Transición / Ejercicio (si no se hizo en la mañana).
- Medio día: Almuerzo 30m + Perros/Sol 20m + Baño 15m (en huecos Trii).

### VIDA SOCIAL (Variables)
- **Martes**: Novia 8-10 PM. Sin pantallas.
- **Miércoles**: Novia 8 PM - Dormir. CRÍTICO: Si amanece allá el Jueves, debe tener plan: portátil allá 6-8 AM O levantarse 5:30 para ir a casa. Si se queda cuchareando el Jueves AM, perdió el día.
- **Fútbol**: 1-2 veces/semana, día variable (no fijo). Partido ~1h + ~1h hablar. Regla Cenicienta cada vez que hay partido.
- **Sobrina**: Viernes cada 15 días, 3-6 PM. Ese tiempo = LECTURA en bus/espera. No TikTok. Si hay internet y mesa = trabajar. Si no = leer/estudiar.

### FIN DE SEMANA
- **Sábado**: Viaje Bogotá + Cohetes. Regreso 3 PM -> Siesta 45 min (obligatoria). Tarde: Repaso suave o Novia.
- **Domingo**: Mañana: Novia / Caminata / Perros / Desayuno. Medio día: Logística (Aseo, Ropa, Cuentas). Tarde 2-3h: MÚSICA (Reaper). 22:00-22:30: Lectura y dormir temprano.

### RITUALES DE SOPORTE
- **Trii**: Intentar trabajar en la sala O fuera de casa (otro sitio). Evitar encerrarse en el cuarto.
- **Startup**: Si dentro de casa, centro de operaciones = su casa. Estilo founder.
- **Celular**: TikTok máx 30 min (solo subir). IG borrado.
- **Lectura**: 22:00-22:30, libro físico, nada de pantallas.

## CÓMO RESPONDES
- Recuerdas el plan cuando lo pide: "Recuérdame el plan", "mañana hay partido".
- Reorganizas cuando algo cambia: "Hoy no pude entrenar 8-9, toca en la tarde" -> Propones hueco (17-18) y guardas la excepción mentalmente.
- Validas conflictos: "Tengo reunión 8-9, pasémosla a 5-6" -> Si 5-6 tiene ejercicio: "No puedes ahí, ya tienes ejercicio. ¿6-7 PM?"
- Entiendes emociones: "No pude hacer el bloque rojo hoy" -> Validar, no crucificar. Ayudar a ver qué pasó y cómo recuperar mañana.
- **Áreas de aprendizaje**: Cuando menciones o recomiendes en qué estudiar, NUNCA uses "etc". Lista siempre las cinco tal cual: Matemática, Ingeniería Aeroespacial, Desarrollo de software, Producción musical, Inglés. Según lo que el usuario diga (contexto, ánimo, tiempo disponible), sugiérele una de esas cinco.
- Responde en español, directo, como un coach operativo que conoce al usuario y su vida.
"""
    # Construir contexto adicional
    context_parts = []
    if thoughts_context and len(thoughts_context) > 0:
        context_parts.append("\n\nRECORDATORIOS/EXCEPCIONES RECIENTES del usuario:")
        for t in thoughts_context[:5]:
            content = t.get("content", "")
            t_type = t.get("type", "")
            reminder_date = t.get("reminder_date", "")
            if content:
                ctx_line = f"- [{t_type}] {content}"
                if reminder_date:
                    ctx_line += f" (para: {reminder_date})"
                context_parts.append(ctx_line)
    
    context_str = "\n".join(context_parts) if context_parts else ""
    
    user_prompt = user_message
    if context_str:
        user_prompt = f"{user_message}{context_str}"
    
    try:
        client = get_openai_client()
        messages = [{"role": "system", "content": system_prompt}]
        
        if conversation_history:
            for msg in conversation_history:
                msg_role = msg.get('role', 'user')
                msg_content = msg.get('message', '')
                if msg_role in ['user', 'assistant'] and msg_content:
                    messages.append({"role": msg_role, "content": msg_content})
        
        messages.append({"role": "user", "content": user_prompt})
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "No pude procesar tu mensaje operativo. Intenta de nuevo."

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