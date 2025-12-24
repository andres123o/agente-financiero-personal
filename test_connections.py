"""
Script de verificación para Kepler CFO.
Prueba todas las conexiones y configuraciones.
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

def test_env_variables():
    """Verifica que todas las variables de entorno estén configuradas."""
    print("=" * 50)
    print("1. VERIFICANDO VARIABLES DE ENTORNO")
    print("=" * 50)
    
    required_vars = {
        "SUPABASE_URL": os.getenv("SUPABASE_URL"),
        "SUPABASE_KEY": os.getenv("SUPABASE_KEY"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN")
    }
    
    all_ok = True
    for var_name, var_value in required_vars.items():
        if var_value and var_value.startswith("tu_") or not var_value:
            print(f"❌ {var_name}: NO CONFIGURADA (placeholder encontrado)")
            all_ok = False
        else:
            # Mostrar solo los primeros y últimos caracteres por seguridad
            masked = var_value[:8] + "..." + var_value[-4:] if len(var_value) > 12 else "***"
            print(f"✅ {var_name}: {masked}")
    
    return all_ok


def test_supabase():
    """Prueba la conexión con Supabase."""
    print("\n" + "=" * 50)
    print("2. VERIFICANDO CONEXIÓN CON SUPABASE")
    print("=" * 50)
    
    try:
        from supabase import create_client
        
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            print("❌ Variables de Supabase no configuradas")
            return False
        
        client = create_client(supabase_url, supabase_key)
        
        # Intentar leer de la tabla budgets
        result = client.table("budgets").select("*").limit(1).execute()
        print("✅ Conexión con Supabase: EXITOSA")
        print(f"   Tabla 'budgets' accesible: ✅")
        
        # Verificar tabla transactions
        try:
            result = client.table("transactions").select("*").limit(1).execute()
            print(f"   Tabla 'transactions' accesible: ✅")
        except Exception as e:
            print(f"   ⚠️  Tabla 'transactions': {str(e)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error conectando con Supabase: {str(e)}")
        return False


def test_openai():
    """Prueba la conexión con OpenAI."""
    print("\n" + "=" * 50)
    print("3. VERIFICANDO CONEXIÓN CON OPENAI")
    print("=" * 50)
    
    try:
        from openai import OpenAI
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key.startswith("tu_"):
            print("❌ OPENAI_API_KEY no configurada correctamente")
            return False
        
        client = OpenAI(api_key=api_key)
        
        # Hacer una llamada simple de prueba
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": "Responde solo 'OK'"}
            ],
            max_tokens=5
        )
        
        print("✅ Conexión con OpenAI: EXITOSA")
        print(f"   Modelo 'gpt-4o-mini' disponible: ✅")
        return True
        
    except Exception as e:
        print(f"❌ Error conectando con OpenAI: {str(e)}")
        if "Invalid API key" in str(e):
            print("   💡 Verifica que tu API key sea correcta")
        return False


def test_telegram():
    """Prueba la conexión con Telegram."""
    print("\n" + "=" * 50)
    print("4. VERIFICANDO CONEXIÓN CON TELEGRAM")
    print("=" * 50)
    
    try:
        import httpx
        
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token or bot_token.startswith("tu_"):
            print("❌ TELEGRAM_BOT_TOKEN no configurada correctamente")
            return False
        
        # Probar getMe endpoint
        url = f"https://api.telegram.org/bot{bot_token}/getMe"
        
        response = httpx.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        if data.get("ok"):
            bot_info = data.get("result", {})
            print("✅ Conexión con Telegram: EXITOSA")
            print(f"   Bot: @{bot_info.get('username', 'N/A')}")
            print(f"   Nombre: {bot_info.get('first_name', 'N/A')}")
            return True
        else:
            print(f"❌ Error en respuesta de Telegram: {data.get('description', 'Unknown')}")
            return False
            
    except Exception as e:
        print(f"❌ Error conectando con Telegram: {str(e)}")
        if "Unauthorized" in str(e):
            print("   💡 Verifica que tu bot token sea correcto")
        return False


def test_imports():
    """Verifica que todos los módulos se pueden importar."""
    print("\n" + "=" * 50)
    print("5. VERIFICANDO IMPORTS Y MÓDULOS")
    print("=" * 50)
    
    modules = [
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("openai", "OpenAI"),
        ("supabase", "Supabase"),
        ("httpx", "HTTPX"),
        ("pydantic", "Pydantic"),
    ]
    
    all_ok = True
    for module_name, display_name in modules:
        try:
            __import__(module_name)
            print(f"✅ {display_name}: Instalado")
        except ImportError:
            print(f"❌ {display_name}: NO INSTALADO")
            all_ok = False
    
    # Probar imports locales
    try:
        from core.brain import classify_expense, generate_response
        print("✅ core.brain: Importado correctamente")
    except Exception as e:
        print(f"❌ core.brain: Error - {str(e)}")
        all_ok = False
    
    try:
        from core.db import insert_transaction, get_budget_status
        print("✅ core.db: Importado correctamente")
    except Exception as e:
        print(f"❌ core.db: Error - {str(e)}")
        all_ok = False
    
    try:
        from core.telegram import send_message
        print("✅ core.telegram: Importado correctamente")
    except Exception as e:
        print(f"❌ core.telegram: Error - {str(e)}")
        all_ok = False
    
    return all_ok


def main():
    """Ejecuta todas las pruebas."""
    print("\n" + "🔍 VERIFICACIÓN DE KEPLER CFO" + "\n")
    
    results = {
        "Variables de entorno": test_env_variables(),
        "Imports": test_imports(),
        "Supabase": test_supabase(),
        "OpenAI": test_openai(),
        "Telegram": test_telegram(),
    }
    
    print("\n" + "=" * 50)
    print("RESUMEN")
    print("=" * 50)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASÓ" if passed else "❌ FALLÓ"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 ¡TODO ESTÁ CONFIGURADO CORRECTAMENTE!")
        print("\nPróximos pasos:")
        print("1. Ejecuta: uvicorn api.index:app --reload")
        print("2. O despliega en Vercel: vercel")
    else:
        print("⚠️  HAY PROBLEMAS QUE RESOLVER")
        print("\nRevisa los errores arriba y corrige la configuración.")
    print("=" * 50 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())


