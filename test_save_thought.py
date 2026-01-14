"""
Script de prueba para verificar el guardado y lectura de thoughts/ideas en la base de datos.
"""
import asyncio
import os
from dotenv import load_dotenv
from core.db import save_thought_reminder, get_thoughts_reminders

load_dotenv()

async def test_save_and_read():
    """Prueba guardar y leer un thought/idea"""
    
    # Usar un chat_id de prueba (el mismo del log: 1730011781)
    test_chat_id = 1730011781
    test_content = "crear canciones parecida a Sanka"
    test_type = "idea"
    
    print(f"🧪 Probando guardado de idea...")
    print(f"   Chat ID: {test_chat_id}")
    print(f"   Contenido: {test_content}")
    print(f"   Tipo: {test_type}")
    print()
    
    try:
        # 1. Guardar
        print("1️⃣ Guardando en la base de datos...")
        saved = await save_thought_reminder(
            chat_id=test_chat_id,
            content=test_content,
            thought_type=test_type,
            reminder_date=None
        )
        
        print(f"✅ Guardado exitoso!")
        print(f"   Respuesta de DB: {saved}")
        print(f"   ID: {saved.get('id') if isinstance(saved, dict) else 'N/A'}")
        print()
        
        # 2. Leer
        print("2️⃣ Leyendo desde la base de datos...")
        thoughts = await get_thoughts_reminders(
            chat_id=test_chat_id,
            date=None,
            thought_type="idea",
            limit=10
        )
        
        print(f"✅ Lectura exitosa!")
        print(f"   Total de ideas encontradas: {len(thoughts)}")
        print()
        
        # 3. Mostrar resultados
        if thoughts:
            print("📋 Ideas encontradas:")
            for i, thought in enumerate(thoughts[:5], 1):  # Mostrar solo las primeras 5
                print(f"   {i}. [{thought.get('type', 'N/A')}] {thought.get('content', 'N/A')[:50]}...")
                print(f"      ID: {thought.get('id')}, Fecha: {thought.get('created_at')}")
        else:
            print("⚠️ No se encontraron ideas")
        
        print()
        print("✅ Prueba completada exitosamente!")
        
    except Exception as e:
        print(f"❌ Error en la prueba: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_save_and_read())

