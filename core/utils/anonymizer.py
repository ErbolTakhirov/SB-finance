"""
============================================================================
АНОНИМИЗАЦИЯ ДАННЫХ ПЕРЕД ОТПРАВКОЙ В ОБЛАЧНЫЙ LLM
============================================================================

Удаляет персональные данные: ФИО, номера счетов, адреса, телефоны и т.д.
============================================================================
"""

import re
from typing import Dict, List, Any


# Паттерны для поиска персональных данных
PATTERNS = {
    # ФИО (русские имена)
    'fio': re.compile(r'\b[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\b'),
    # Номера счетов (16-19 цифр)
    'account': re.compile(r'\b\d{16,19}\b'),
    # Банковские карты (16 цифр с возможными пробелами)
    'card': re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'),
    # Телефоны (различные форматы)
    'phone': re.compile(r'(\+7|8)?[\s-]?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}'),
    # Email
    'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    # Адреса (улица, дом)
    'address': re.compile(r'(ул\.|улица|проспект|пр\.|переулок|пер\.|дом|д\.|квартира|кв\.)\s+[А-Яа-яё0-9\s,.-]+', re.IGNORECASE),
    # ИНН (10 или 12 цифр)
    'inn': re.compile(r'\b\d{10,12}\b'),
    # СНИЛС (формат XXX-XXX-XXX XX)
    'snils': re.compile(r'\b\d{3}-\d{3}-\d{3}\s\d{2}\b'),
}


def anonymize_text(text: str) -> str:
    """
    Анонимизирует текст, удаляя персональные данные.
    
    Args:
        text: Исходный текст
        
    Returns:
        Анонимизированный текст
    """
    if not text:
        return text
    
    result = text
    
    # Заменяем ФИО на [ФИО]
    result = PATTERNS['fio'].sub('[ФИО]', result)
    
    # Заменяем номера счетов на [НОМЕР_СЧЕТА]
    result = PATTERNS['account'].sub('[НОМЕР_СЧЕТА]', result)
    
    # Заменяем номера карт на [НОМЕР_КАРТЫ]
    result = PATTERNS['card'].sub('[НОМЕР_КАРТЫ]', result)
    
    # Заменяем телефоны на [ТЕЛЕФОН]
    result = PATTERNS['phone'].sub('[ТЕЛЕФОН]', result)
    
    # Заменяем email на [EMAIL]
    result = PATTERNS['email'].sub('[EMAIL]', result)
    
    # Заменяем адреса на [АДРЕС]
    result = PATTERNS['address'].sub('[АДРЕС]', result)
    
    # Заменяем ИНН на [ИНН]
    result = PATTERNS['inn'].sub('[ИНН]', result)
    
    # Заменяем СНИЛС на [СНИЛС]
    result = PATTERNS['snils'].sub('[СНИЛС]', result)
    
    return result


def anonymize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Анонимизирует словарь, рекурсивно обрабатывая все строковые значения.
    
    Args:
        data: Словарь с данными
        
    Returns:
        Анонимизированный словарь
    """
    if not isinstance(data, dict):
        return data
    
    result = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key] = anonymize_text(value)
        elif isinstance(value, dict):
            result[key] = anonymize_dict(value)
        elif isinstance(value, list):
            result[key] = [anonymize_dict(item) if isinstance(item, dict) else 
                          (anonymize_text(item) if isinstance(item, str) else item) 
                          for item in value]
        else:
            result[key] = value
    
    return result


def anonymize_transactions(transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Анонимизирует список транзакций.
    
    Args:
        transactions: Список транзакций
        
    Returns:
        Анонимизированный список
    """
    return [anonymize_dict(t) for t in transactions]


def anonymize_csv_data(csv_text: str) -> str:
    """
    Анонимизирует CSV данные.
    
    Args:
        csv_text: CSV текст
        
    Returns:
        Анонимизированный CSV
    """
    lines = csv_text.split('\n')
    anonymized_lines = []
    
    for line in lines:
        if not line.strip():
            anonymized_lines.append(line)
            continue
        
        # Анонимизируем каждую строку
        anonymized_line = anonymize_text(line)
        anonymized_lines.append(anonymized_line)
    
    return '\n'.join(anonymized_lines)

