"""
============================================================================
СЕРВЕРНАЯ УТИЛИТА ДЛЯ РАБОТЫ С ЗАШИФРОВАННЫМИ ДАННЫМИ
============================================================================

ВАЖНО: Сервер НИКОГДА не расшифровывает данные!
Все данные хранятся в зашифрованном виде.
Расшифровка происходит только на клиенте.

Этот модуль только проверяет формат и сохраняет зашифрованные данные.
============================================================================
"""

import base64
import json
from typing import Any, Dict, Optional


def is_encrypted(data: Any) -> bool:
    """
    Проверяет, зашифрованы ли данные.
    
    Ожидаемый формат от клиента:
    {
        "encrypted": true,
        "data": "base64_encrypted_string"
    }
    """
    if isinstance(data, dict):
        return data.get('encrypted') is True and 'data' in data
    return False


def extract_encrypted_data(data: Any) -> Optional[str]:
    """
    Извлекает зашифрованные данные из запроса.
    Возвращает None, если данные не зашифрованы.
    
    ВАЖНО: Не расшифровывает! Только извлекает.
    """
    if is_encrypted(data):
        return data['data']
    return None


def wrap_encrypted_response(data: Any) -> Dict[str, Any]:
    """
    Обёртывает данные для отправки клиенту в зашифрованном виде.
    ВАЖНО: Данные уже должны быть зашифрованы на клиенте!
    Это просто обёртка для формата ответа.
    
    В реальности, если данные уже зашифрованы на сервере,
    они должны быть расшифрованы на клиенте.
    """
    return {
        "encrypted": True,
        "data": data
    }


def validate_encrypted_format(data: str) -> bool:
    """
    Проверяет, что строка выглядит как валидный Base64.
    Не проверяет содержимое, только формат.
    """
    try:
        base64.b64decode(data, validate=True)
        return True
    except Exception:
        return False


def store_encrypted_field(value: Any, encrypted: bool = False) -> Dict[str, Any]:
    """
    Подготавливает поле для сохранения в БД.
    
    Если данные уже зашифрованы (пришли от клиента),
    сохраняет их как есть.
    Если нет - сохраняет как обычный текст (для обратной совместимости).
    
    ВАЖНО: В будущем все данные должны быть зашифрованы!
    """
    if encrypted and isinstance(value, dict) and is_encrypted(value):
        return {
            "encrypted": True,
            "data": value['data']
        }
    return value


def get_encrypted_value(field_value: Any) -> str:
    """
    Извлекает зашифрованное значение из поля БД.
    
    Если поле - словарь с 'encrypted' и 'data', возвращает data.
    Иначе возвращает значение как есть (для обратной совместимости).
    """
    if isinstance(field_value, dict) and field_value.get('encrypted') and 'data' in field_value:
        return field_value['data']
    return field_value

