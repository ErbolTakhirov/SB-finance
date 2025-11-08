"""
Утилита для отладки LLM запросов.
Используйте для проверки правильности настройки API.
"""
import json
import requests
from django.conf import settings


def test_openrouter_connection():
    """
    Тестирует подключение к OpenRouter API.
    Возвращает детальную информацию об ошибке.
    """
    print("=" * 60)
    print("ТЕСТ ПОДКЛЮЧЕНИЯ К OPENROUTER API")
    print("=" * 60)
    
    # Проверка настроек
    print(f"\n1. Проверка настроек:")
    print(f"   API URL: {settings.LLM_API_URL}")
    print(f"   Model: {settings.LLM_MODEL}")
    print(f"   API Key: {'*' * 20 + settings.LLM_API_KEY[-10:] if settings.LLM_API_KEY else 'НЕ УСТАНОВЛЕН'}")
    
    if not settings.LLM_API_KEY:
        print("\n❌ ОШИБКА: API ключ не установлен!")
        print("   Установите LLM_API_KEY в settings.py или .env файле")
        return False
    
    # Формируем тестовый запрос
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {settings.LLM_API_KEY}",
        'Referer': getattr(settings, 'LLM_HTTP_REFERER', 'http://localhost:8000'),
        'X-Title': getattr(settings, 'LLM_APP_TITLE', 'SB Finance AI'),
    }
    
    payload = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "user", "content": "Скажи 'Привет' одним словом"}
        ],
    }
    
    print(f"\n2. Отправка тестового запроса...")
    print(f"   Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
    
    try:
        resp = requests.post(
            settings.LLM_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        print(f"\n3. Ответ сервера:")
        print(f"   Status Code: {resp.status_code}")
        print(f"   Headers: {dict(resp.headers)}")
        
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
            if 'choices' in data and data['choices']:
                reply = data['choices'][0]['message']['content']
                print(f"\n✅ УСПЕХ! API работает корректно.")
                print(f"   Ответ: {reply}")
                return True
            else:
                print(f"\n⚠️  Неожиданный формат ответа")
                return False
        else:
            print(f"\n❌ ОШИБКА HTTP {resp.status_code}")
            try:
                error_data = resp.json()
                print(f"   Error Details: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
            except:
                print(f"   Error Text: {resp.text[:500]}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"\n❌ ОШИБКА СЕТИ: {e}")
        return False
    except Exception as e:
        print(f"\n❌ НЕОЖИДАННАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    import os
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sb_finance.settings')
    django.setup()
    test_openrouter_connection()

