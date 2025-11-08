from __future__ import annotations

import math
import re
import statistics
from collections import defaultdict
from datetime import date
from typing import Dict, List, Tuple, Any

from django.utils import timezone

from core.models import Income, Expense, UserProfile


MONTH_LABELS = {
    1: ("январь", "январе"),
    2: ("февраль", "феврале"),
    3: ("март", "марте"),
    4: ("апрель", "апреле"),
    5: ("май", "мае"),
    6: ("июнь", "июне"),
    7: ("июль", "июле"),
    8: ("август", "августе"),
    9: ("сентябрь", "сентябре"),
    10: ("октябрь", "октябре"),
    11: ("ноябрь", "ноябре"),
    12: ("декабрь", "декабре"),
}


def _month_key(dt: date) -> str:
    return f"{dt.year:04d}-{dt.month:02d}"


def _format_currency(value: float) -> str:
    if value is None:
        return "0"
    rounded = round(float(value), 2)
    integer_part, dot, fractional = f"{abs(rounded):,.2f}".partition(".")
    integer_part = integer_part.replace(",", " ")
    fractional = fractional.rstrip("0")
    sign = "-" if rounded < 0 else ""
    if fractional:
        return f"{sign}{integer_part}.{fractional}"
    return f"{sign}{integer_part}"


def _compute_pct_change(current: float, previous: float) -> float | None:
    if previous is None:
        return None
    if previous == 0:
        if current == 0:
            return 0.0
        return None
    return round(((current - previous) / previous) * 100, 2)


def _month_phrase(month_key: str, prepositional: bool = False) -> str:
    year, month = month_key.split("-")
    year_int = int(year)
    month_int = int(month)
    names = MONTH_LABELS.get(month_int)
    if not names:
        return f"{month}.{year}"
    idx = 1 if prepositional else 0
    return f"{names[idx].capitalize()} {year_int}"


def _detect_expense_anomalies(expense_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not expense_events:
        return []
    amounts = [float(item['amount']) for item in expense_events]
    if len(amounts) == 1:
        threshold = amounts[0] * 1.5
        stdev = 0.0
        mean_val = amounts[0]
    else:
        mean_val = statistics.mean(amounts)
        stdev = statistics.pstdev(amounts)
        if stdev < 1e-6:
            threshold = mean_val * 1.7
        else:
            threshold = mean_val + 2 * stdev
        median_val = statistics.median(amounts)
        threshold = max(threshold, median_val * 1.8)

    anomalies: List[Dict[str, Any]] = []
    for event in expense_events:
        amount = float(event['amount'])
        if amount >= threshold and amount > 0:
            z_score = (amount - mean_val) / stdev if stdev > 1e-6 else None
            anomalies.append({
                **event,
                'z_score': round(z_score, 2) if z_score is not None else None,
                'threshold': round(threshold, 2),
                'mean': round(mean_val, 2),
            })
    return anomalies


def _build_table_markdown(ordered_keys: List[str], months: Dict[str, Dict[str, Any]]) -> str:
    header = (
        "| Месяц | Доходы | Расходы | Баланс | Катег. доход | Катег. расход | Средний чек | Транзакций | Изм. доход | Изм. расход |"
        "\n|---|---|---|---|---|---|---|---|---|---|"
    )
    lines = [header]
    for mk in ordered_keys:
        info = months[mk]
        label = mk.split('-')
        month_repr = f"{label[1]}.{label[0]}"
        income_top = ", ".join(f"{item['category']} ({_format_currency(item['amount'])})" for item in info.get('top_income_categories', [])) or "—"
        expense_top = ", ".join(f"{item['category']} ({_format_currency(item['amount'])})" for item in info.get('top_expense_categories', [])) or "—"
        avg_check = _format_currency(info.get('average_check')) if info.get('average_check') else "0"
        income_delta = info.get('income_change_pct')
        expense_delta = info.get('expense_change_pct')
        income_delta_str = f"{income_delta:+.1f}%" if income_delta is not None else "—"
        expense_delta_str = f"{expense_delta:+.1f}%" if expense_delta is not None else "—"
        lines.append(
            f"| {month_repr} | {_format_currency(info.get('income_total', 0))} | {_format_currency(info.get('expense_total', 0))} | "
            f"{_format_currency(info.get('balance', 0))} | {income_top} | {expense_top} | {avg_check} | {info.get('transaction_count', 0)} | "
            f"{income_delta_str} | {expense_delta_str} |"
        )
    if len(lines) == 1:
        lines.append("| — | 0 | 0 | 0 | — | — | 0 | 0 | — | — |")
    return "\n".join(lines)


def _build_text_summary(ordered_keys: List[str], months: Dict[str, Dict[str, Any]], anomalies: List[Dict[str, Any]]) -> str:
    if not ordered_keys:
        return "Нет финансовых данных для анализа."

    sentences: List[str] = []

    # Рекорд доходов
    max_income_key = max(ordered_keys, key=lambda mk: months[mk]['income_total'])
    max_income_value = months[max_income_key]['income_total']
    if max_income_value > 0:
        top_income_cats = [item['category'] for item in months[max_income_key]['top_income_categories'][:2]]
        cat_part = f" за счёт {', '.join(top_income_cats)}" if top_income_cats else ""
        sentences.append(
            f"В {_month_phrase(max_income_key, prepositional=True)} рекорд по доходам — {_format_currency(max_income_value)}{cat_part}."
        )

    # Рекорд расходов
    max_expense_key = max(ordered_keys, key=lambda mk: months[mk]['expense_total'])
    max_expense_value = months[max_expense_key]['expense_total']
    if max_expense_value > 0:
        top_exp_cats = [item['category'] for item in months[max_expense_key]['top_expense_categories'][:2]]
        cat_part = f" (категории: {', '.join(top_exp_cats)})" if top_exp_cats else ""
        sentences.append(
            f"{_month_phrase(max_expense_key, prepositional=True)} — пик расходов {_format_currency(max_expense_value)}{cat_part}."
        )

    # Наибольшее падение доходов
    income_drops = [
        (mk, months[mk]['income_change_pct'])
        for mk in ordered_keys
        if months[mk].get('income_change_pct') is not None
    ]
    if income_drops:
        worst_drop_key, worst_drop_value = min(income_drops, key=lambda t: t[1])
        if worst_drop_value < 0:
            sentences.append(
                f"Доходы просели на {abs(worst_drop_value):.1f}% в {_month_phrase(worst_drop_key, prepositional=True)}."
            )

    # Наибольший рост расходов
    expense_jumps = [
        (mk, months[mk]['expense_change_pct'])
        for mk in ordered_keys
        if months[mk].get('expense_change_pct') is not None
    ]
    if expense_jumps:
        biggest_jump_key, biggest_jump_value = max(expense_jumps, key=lambda t: t[1])
        if biggest_jump_value > 0:
            sentences.append(
                f"Расходы выросли на {biggest_jump_value:.1f}% в {_month_phrase(biggest_jump_key, prepositional=True)}."
            )

    # Аномалии
    if anomalies:
        top_anomaly = anomalies[0]
        sentences.append(
            f"Аномалия: {_format_currency(top_anomaly['amount'])} на {top_anomaly['category']} ({top_anomaly['date']})."
        )

    if not sentences:
        return "Данные стабильны, явных отклонений не обнаружено."
    return " ".join(sentences)


def _ensure_profile(user) -> UserProfile:
    profile = getattr(user, 'profile', None)
    if profile:
        return profile
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def _analyze_trends(ordered_keys: List[str], months: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Анализирует тренды за последние 3+ месяцев."""
    if len(ordered_keys) < 2:
        return {'has_enough_data': False, 'message': 'Недостаточно данных для анализа трендов (требуется минимум 2 месяца)'}
    
    # Анализ по категориям расходов (требуется минимум 3 месяца)
    category_trends = {}
    if len(ordered_keys) >= 3:
        # Собираем данные по категориям за последние 3 месяца
        recent_months = ordered_keys[-3:]
        all_expense_categories = set()
        for mk in recent_months:
            for cat_info in months[mk].get('top_expense_categories', []):
                all_expense_categories.add(cat_info['category'])
        
        for cat in all_expense_categories:
            values = []
            for mk in recent_months:
                # Находим сумму по категории
                cat_amount = 0
                for cat_info in months[mk].get('top_expense_categories', []):
                    if cat_info['category'] == cat:
                        cat_amount = cat_info['amount']
                        break
                values.append(cat_amount)
            
            if len(values) >= 2:
                # Вычисляем тренд (рост/падение)
                if values[-1] > values[0]:
                    trend = 'growth'
                    change_pct = ((values[-1] - values[0]) / values[0] * 100) if values[0] > 0 else 0
                elif values[-1] < values[0]:
                    trend = 'decline'
                    change_pct = ((values[0] - values[-1]) / values[0] * 100) if values[0] > 0 else 0
                else:
                    trend = 'stable'
                    change_pct = 0
                
                category_trends[cat] = {
                    'trend': trend,
                    'change_pct': round(change_pct, 2),
                    'values': values,
                    'latest': values[-1],
                    'average': round(sum(values) / len(values), 2),
                }
    
    # Общие тренды доходов и расходов
    income_trend = 'stable'
    expense_trend = 'stable'
    if len(ordered_keys) >= 3:
        recent_incomes = [months[mk]['income_total'] for mk in ordered_keys[-3:]]
        recent_expenses = [months[mk]['expense_total'] for mk in ordered_keys[-3:]]
        
        if recent_incomes[-1] > recent_incomes[0]:
            income_trend = 'growth'
        elif recent_incomes[-1] < recent_incomes[0]:
            income_trend = 'decline'
        
        if recent_expenses[-1] > recent_expenses[0]:
            expense_trend = 'growth'
        elif recent_expenses[-1] < recent_expenses[0]:
            expense_trend = 'decline'
    
    return {
        'has_enough_data': len(ordered_keys) >= 3,
        'months_available': len(ordered_keys),
        'category_trends': category_trends,
        'income_trend': income_trend,
        'expense_trend': expense_trend,
        'recent_months': ordered_keys[-3:] if len(ordered_keys) >= 3 else ordered_keys,
    }


def compute_financial_memory(user) -> Dict[str, Any]:
    months: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        'income_total': 0.0,
        'expense_total': 0.0,
        'transaction_count': 0,
        'income_count': 0,
        'expense_count': 0,
        'income_by_cat': defaultdict(float),
        'expense_by_cat': defaultdict(float),
        'expense_events': [],
    })

    for inc in Income.objects.filter(user=user).select_related(None):
        mk = _month_key(inc.date)
        month_data = months[mk]
        amount = float(inc.amount)
        month_data['income_total'] += amount
        month_data['income_count'] += 1
        month_data['transaction_count'] += 1
        cat = inc.category or 'other'
        month_data['income_by_cat'][cat] += amount

    for exp in Expense.objects.filter(user=user).select_related(None):
        mk = _month_key(exp.date)
        month_data = months[mk]
        amount = float(exp.amount)
        month_data['expense_total'] += amount
        month_data['expense_count'] += 1
        month_data['transaction_count'] += 1
        cat = exp.category or 'other'
        month_data['expense_by_cat'][cat] += amount
        month_data['expense_events'].append({
            'id': exp.id,
            'amount': amount,
            'category': cat,
            'date': exp.date.isoformat(),
            'description': exp.description or "",
        })

    ordered_keys = sorted(months.keys())
    previous_income = None
    previous_expense = None

    global_anomalies: List[Dict[str, Any]] = []

    for mk in ordered_keys:
        data = months[mk]
        data['balance'] = data['income_total'] - data['expense_total']
        tx_count = data['transaction_count'] or 0
        gross_turnover = data['income_total'] + data['expense_total']
        data['average_check'] = gross_turnover / tx_count if tx_count else 0.0

        income_top = sorted(data['income_by_cat'].items(), key=lambda x: x[1], reverse=True)[:3]
        expense_top = sorted(data['expense_by_cat'].items(), key=lambda x: x[1], reverse=True)[:3]
        data['top_income_categories'] = [
            {'category': cat, 'amount': round(val, 2)} for cat, val in income_top
        ]
        data['top_expense_categories'] = [
            {'category': cat, 'amount': round(val, 2)} for cat, val in expense_top
        ]

        anomalies = _detect_expense_anomalies(data['expense_events'])
        data['anomalies'] = anomalies
        if anomalies:
            for item in anomalies:
                item['month'] = mk
            global_anomalies.extend(sorted(anomalies, key=lambda x: x['amount'], reverse=True))

        data['income_change_pct'] = _compute_pct_change(data['income_total'], previous_income)
        data['expense_change_pct'] = _compute_pct_change(data['expense_total'], previous_expense)
        data['balance_change_pct'] = _compute_pct_change(
            data['balance'], previous_income - previous_expense if previous_income is not None and previous_expense is not None else None
        )

        previous_income = data['income_total']
        previous_expense = data['expense_total']

        data.pop('income_by_cat', None)
        data.pop('expense_by_cat', None)
        data.pop('expense_events', None)

    # Анализ трендов (минимум 3 месяца)
    trends = _analyze_trends(ordered_keys, months)
    
    table_md = _build_table_markdown(ordered_keys, months)
    sorted_anomalies = sorted(global_anomalies, key=lambda x: x['amount'], reverse=True)
    summary_text = _build_text_summary(ordered_keys, months, sorted_anomalies)

    return {
        'generated_at': timezone.now().isoformat(),
        'ordered_keys': ordered_keys,
        'months': months,
        'table_markdown': table_md,
        'summary_text': summary_text,
        'trends': trends,  # Новое: анализ трендов
        'alerts': [
            {
                'month': anomaly['month'],
                'category': anomaly['category'],
                'amount': anomaly['amount'],
                'date': anomaly['date'],
                'description': anomaly.get('description') or '',
                'message': f"{_month_phrase(anomaly['month'], prepositional=True)}: {_format_currency(anomaly['amount'])} на {anomaly['category']} ({anomaly.get('description') or 'без описания'})",
            }
            for anomaly in sorted_anomalies[:10]
        ],
    }


def update_user_financial_memory(user, force_refresh: bool = False) -> Dict[str, Any]:
    profile = _ensure_profile(user)
    if not force_refresh and profile.financial_memory:
        return profile.financial_memory

    memory = compute_financial_memory(user)
    profile.financial_memory = memory
    profile.save(update_fields=['financial_memory', 'updated_at'])
    return memory


def get_user_financial_memory(user, force_refresh: bool = False) -> Dict[str, Any]:
    profile = _ensure_profile(user)
    if force_refresh or not profile.financial_memory:
        return update_user_financial_memory(user, force_refresh=True)
    return profile.financial_memory


PROMPT_INSTRUCTION_BLOCK = """
Ты — независимый и честный AI-финансовый ассистент с задачей давать только глубокие, краткие, explainable и action-oriented советы.

У тебя на руках агрегированная таблица и summary по всем месяцам (минимум 3 месяца, см. ниже).

КРИТИЧЕСКИ ВАЖНЫЕ ПРАВИЛА:

1. ВСЕГДА анализируй минимум 3 месяца данных — ищи тренды, паттерны, сезонность, отклонения.

2. Формируй markdown-анализ ТОЛЬКО по ключевым изменениям и причинам:
   - НЕ просто "траты возросли"
   - А: "траты возросли на 27% из-за категории 'маркетинг' (было 15k, стало 19k) — вероятная причина: запуск новой рекламной кампании. Что делать: проверить ROI кампании, оптимизировать бюджет на 10-15%. Как избежать: установить лимиты на категорию, еженедельный мониторинг."

3. Ранжируй советы по приоритетам:
   - 🚨 СРОЧНО (требует немедленных действий)
   - ⚡ QUICK WIN (быстрые результаты, минимум усилий)
   - 📅 ДОЛГОСРОЧНО (стратегические рекомендации)
   - ✅ НА ИСПОЛНЕНИЕ (конкретные шаги)

4. При острых местах (аномальный рост расходов >50%, падение доходов >30%, отрицательный баланс) автоматически создавай ALERT:
   "🚩 ALERT! [описание проблемы]"

5. Структурируй actionable советы по тегам:
   - 🔥 Что делать СЕЙЧАС (в течение недели)
   - 📆 Что можно сделать в ЭТОМ МЕСЯЦЕ
   - 🔮 Что посмотреть на БУДУЩЕЕ (следующие 3-6 месяцев)

6. Используй ВЕСЬ имеющийся контекст:
   - История предыдущих сообщений
   - Markdown-таблица со всеми месяцами
   - Summary по ключевым месяцам
   - Выявленные аномалии и тренды

ОБЯЗАТЕЛЬНЫЙ ФОРМАТ ВЫВОДА:

🚦 Краткий аналитический вывод
[1-2 предложения с ключевыми находками]

🚩 ВЫЯВЛЕННЫЕ РИСКИ
[Список рисков с конкретными цифрами и причинами. Если нет критических — "Критических рисков не обнаружено."]

🛠 Action-пункты

🔥 Что делать СЕЙЧАС:
1. [конкретный совет с цифрами и шагами]
2. ...

📆 Что можно сделать в ЭТОМ МЕСЯЦЕ:
1. [конкретный совет]
2. ...

🔮 Что посмотреть на БУДУЩЕЕ:
1. [стратегическая рекомендация]
2. ...

📈 Долгосрочный прогноз
[Прогноз на основе трендов, если данных достаточно]

📊 Сравнительная таблица
[Если уместно — таблица сравнения периодов/категорий]

🤝 Кейс/practice из жизни
[Опционально: пример из best practices, если уместно]

СТРОГО ЗАПРЕЩЕНО:
- "Лить воду" — только конкретика, цифры, действия
- Игнорировать summary и context — всегда используй всю таблицу
- Давать "советы ради советов" — только если есть реальная проблема или возможность
- Пересказывать сумму расходов/доходов без анализа — только выводы и сравнения
- Отвечать общими словами — только по теме и по цифрам

Если данных недостаточно (меньше 3 месяцев) — явно укажи это и дай рекомендации с учетом ограниченности данных.
""".strip()


def build_system_prompt(memory: Dict[str, Any], extra_context: str = "") -> str:
    table = memory.get('table_markdown', "| Месяц | Доходы | Расходы | Катег. доход | Катег. расход | Транзакций |\n|---|---|---|---|---|---|\n| — | 0 | 0 | — | — | 0 |")
    summary = memory.get('summary_text', 'Нет сводки')
    alerts = memory.get('alerts', [])
    trends = memory.get('trends', {})
    ordered_keys = memory.get('ordered_keys', [])

    # Блок с предупреждениями (ALERT)
    alerts_block = ""
    critical_alerts = [a for a in alerts if a.get('alert') and a.get('severity') in ['critical', 'high']]
    if critical_alerts:
        bullet_lines = "\n".join(f"- {alert['message']}" for alert in critical_alerts[:5])
        alerts_block = f"\n\n### 🚩 КРИТИЧЕСКИЕ ОПОВЕЩЕНИЯ (ALERT)\n{bullet_lines}"
    elif alerts:
        bullet_lines = "\n".join(f"- {alert.get('message', str(alert))}" for alert in alerts[:5])
        alerts_block = f"\n\n### Ранние оповещения\n{bullet_lines}"

    # Блок с анализом трендов
    trends_block = ""
    if trends.get('has_enough_data'):
        trends_info = []
        trends_info.append(f"Доступно месяцев данных: {trends.get('months_available', 0)}")
        if trends.get('category_trends'):
            trends_info.append("\nТренды по категориям расходов:")
            for cat, trend_data in list(trends['category_trends'].items())[:5]:
                trend_emoji = "📈" if trend_data['trend'] == 'growth' else "📉" if trend_data['trend'] == 'decline' else "➡️"
                trends_info.append(f"- {cat}: {trend_emoji} {trend_data['trend']} ({trend_data['change_pct']:+.1f}%), среднее: {_format_currency(trend_data['average'])}")
        trends_block = f"\n\n### Анализ трендов (последние 3+ месяца)\n" + "\n".join(trends_info)
    else:
        trends_block = f"\n\n### ⚠️ Внимание: недостаточно данных\n{trends.get('message', 'Для качественного анализа требуется минимум 3 месяца данных.')}"

    prompt = (
        f"{PROMPT_INSTRUCTION_BLOCK}\n\n"
        f"### Историческая таблица (все месяцы)\n{table}\n\n"
        f"### Краткое summary\n{summary}{trends_block}{alerts_block}"
    )

    if extra_context:
        prompt += f"\n\n### Дополнительный контекст\n{extra_context}"

    return prompt


def parse_actionable_items(reply: str) -> List[Dict[str, Any]]:
    """Извлекает actionable советы из ответа AI с поддержкой новых тегов."""
    items: List[Dict[str, Any]] = []
    lines = reply.splitlines()
    current_item = None
    current_section = None  # 🔥 СЕЙЧАС, 📆 ЭТОТ МЕСЯЦ, 🔮 БУДУЩЕЕ
    
    # Определяем приоритеты по эмодзи и ключевым словам
    priority_map = {
        '🚨': 'urgent',
        '⚡': 'quick_win',
        '📅': 'long_term',
        '✅': 'actionable',
        '🔥': 'now',
        '📆': 'this_month',
        '🔮': 'future',
    }
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        
        # Определяем секцию по заголовкам
        if '🔥' in stripped and any(keyword in stripped.lower() for keyword in ['сейчас', 'now', 'сегодня']):
            current_section = 'now'
            continue
        elif '📆' in stripped and any(keyword in stripped.lower() for keyword in ['месяц', 'month', 'этом']):
            current_section = 'this_month'
            continue
        elif '🔮' in stripped and any(keyword in stripped.lower() for keyword in ['будущее', 'future', 'будущем']):
            current_section = 'future'
            continue
        elif '🚨' in stripped or '⚡' in stripped or '📅' in stripped or '✅' in stripped:
            # Определяем приоритет по эмодзи
            for emoji, priority in priority_map.items():
                if emoji in stripped:
                    current_section = priority
                    break
            continue
        
        # Нумерованные списки (1., 2., 3., etc.)
        if re.match(r'^\d+\.', stripped):
            if current_item:
                items.append(current_item)
            
            priority = None
            for emoji, p in priority_map.items():
                if emoji in stripped:
                    priority = p
                    break
            
            current_item = {
                'text': stripped,
                'type': 'numbered',
                'section': current_section or 'general',
                'priority': priority or 'normal',
            }
        # Маркированные списки
        elif stripped.startswith(('-', '*', '•')):
            if current_item:
                items.append(current_item)
            
            priority = None
            for emoji, p in priority_map.items():
                if emoji in stripped:
                    priority = p
                    break
            
            current_item = {
                'text': stripped,
                'type': 'bullet',
                'section': current_section or 'general',
                'priority': priority or 'normal',
            }
        # Продолжение текущего совета
        elif current_item and not any(marker in stripped for marker in ['##', '###', '🚦', '🚩', '🛠', '📈', '📊', '🤝']):
            if len(stripped) > 10 and not stripped.startswith('|'):
                current_item['text'] += ' ' + stripped
        else:
            # Если начинается новый блок, сохраняем предыдущий
            if current_item:
                items.append(current_item)
                current_item = None
    
    if current_item:
        items.append(current_item)
    
    return items


def detect_anomalies_automatically(user) -> List[Dict[str, Any]]:
    """Автоматически обнаруживает аномалии после загрузки данных и возвращает список оповещений с форматом ALERT."""
    memory = compute_financial_memory(user)
    alerts = memory.get('alerts', [])
    
    # Дополнительная проверка на резкие изменения
    months = memory.get('months', {})
    ordered_keys = memory.get('ordered_keys', [])
    trends = memory.get('trends', {})
    
    anomaly_alerts = []
    
    # Минимум 3 месяца для качественного анализа
    if len(ordered_keys) < 3:
        anomaly_alerts.append({
            'type': 'insufficient_data',
            'severity': 'info',
            'message': f"⚠️ Внимание: данных только за {len(ordered_keys)} месяц(а/ев). Для качественного анализа рекомендуется минимум 3 месяца.",
        })
    
    if len(ordered_keys) >= 2:
        # Анализируем последний месяц
        if len(ordered_keys) >= 1:
            curr_key = ordered_keys[-1]
            curr_month = months[curr_key]
            
            # Проверка на резкий рост расходов (>50%)
            expense_change = curr_month.get('expense_change_pct')
            if expense_change and expense_change > 50:
                top_category = curr_month.get('top_expense_categories', [{}])[0] if curr_month.get('top_expense_categories') else {}
                category_info = f" (категория: {top_category.get('category', 'неизвестно')}, {_format_currency(top_category.get('amount', 0))})" if top_category else ""
                anomaly_alerts.append({
                    'type': 'expense_spike',
                    'severity': 'high',
                    'month': curr_key,
                    'alert': True,
                    'message': f"🚩 ALERT! Резкий рост расходов на {expense_change:.1f}% в {_month_phrase(curr_key, prepositional=True)}{category_info}. Текущие расходы: {_format_currency(curr_month.get('expense_total', 0))}",
                    'value': curr_month.get('expense_total', 0),
                    'recommendation': 'Срочно проверить причины роста и оптимизировать бюджет',
                })
            
            # Проверка на резкое падение доходов (>30%)
            income_change = curr_month.get('income_change_pct')
            if income_change and income_change < -30:
                top_category = curr_month.get('top_income_categories', [{}])[0] if curr_month.get('top_income_categories') else {}
                category_info = f" (категория: {top_category.get('category', 'неизвестно')}, {_format_currency(top_category.get('amount', 0))})" if top_category else ""
                anomaly_alerts.append({
                    'type': 'income_drop',
                    'severity': 'high',
                    'month': curr_key,
                    'alert': True,
                    'message': f"🚩 ALERT! Резкое падение доходов на {abs(income_change):.1f}% в {_month_phrase(curr_key, prepositional=True)}{category_info}. Текущие доходы: {_format_currency(curr_month.get('income_total', 0))}",
                    'value': curr_month.get('income_total', 0),
                    'recommendation': 'Проанализировать причины падения и найти способы восстановления',
                })
            
            # Проверка на отрицательный баланс
            balance = curr_month.get('balance', 0)
            if balance < 0:
                anomaly_alerts.append({
                    'type': 'negative_balance',
                    'severity': 'critical',
                    'month': curr_key,
                    'alert': True,
                    'message': f"🚩 ALERT! Отрицательный баланс {_format_currency(balance)} в {_month_phrase(curr_key, prepositional=True)}. Расходы превышают доходы!",
                    'value': balance,
                    'recommendation': 'КРИТИЧНО: немедленно сократить расходы или увеличить доходы',
                })
    
    # Анализ трендов по категориям (если есть данные за 3+ месяца)
    if trends.get('has_enough_data') and trends.get('category_trends'):
        for category, trend_data in trends['category_trends'].items():
            if trend_data['trend'] == 'growth' and trend_data['change_pct'] > 50:
                anomaly_alerts.append({
                    'type': 'category_growth',
                    'severity': 'medium',
                    'alert': True,
                    'message': f"🚩 ALERT! Категория '{category}' выросла на {trend_data['change_pct']:.1f}% за последние 3 месяца. Текущее значение: {_format_currency(trend_data['latest'])}",
                    'value': trend_data['latest'],
                    'category': category,
                    'recommendation': f'Проверить обоснованность роста расходов в категории "{category}"',
                })
    
    # Объединяем существующие alerts с новыми
    all_alerts = alerts + anomaly_alerts
    
    # Сортируем: сначала критические, потом по значению
    def sort_key(x):
        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'info': 3}
        return (severity_order.get(x.get('severity', 'info'), 3), -abs(x.get('amount', x.get('value', 0))))
    
    return sorted(all_alerts, key=sort_key)


