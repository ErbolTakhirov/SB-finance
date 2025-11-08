import io
import re
import time
from typing import List, Tuple, Optional, Dict, Set
from datetime import date

import pandas as pd
from django.db import transaction
from django.db.utils import OperationalError

from core.models import Income, Expense, Document, UploadedFile


CSV_REQUIRED_COLUMNS = {'type', 'date', 'amount'}


DB_LOCK_RETRY_ATTEMPTS = 5
DB_LOCK_RETRY_DELAY = 0.2


def _persist_transactions(income_objs: List[Income], expense_objs: List[Expense]) -> None:
    for attempt in range(DB_LOCK_RETRY_ATTEMPTS):
        try:
            with transaction.atomic():
                if income_objs:
                    Income.objects.bulk_create(income_objs, batch_size=200)
                if expense_objs:
                    Expense.objects.bulk_create(expense_objs, batch_size=200)
            return
        except OperationalError as exc:
            if "locked" in str(exc).lower() and attempt < DB_LOCK_RETRY_ATTEMPTS - 1:
                time.sleep(DB_LOCK_RETRY_DELAY * (attempt + 1))
                continue
            raise


def _check_duplicate(transaction_type: str, date_val: date, amount: float, category: str, description: str, source_file: Optional[UploadedFile], user) -> bool:
    """Проверяет, существует ли уже транзакция с такими же параметрами из того же файла."""
    if transaction_type == 'income':
        qs = Income.objects.filter(
            user=user,
            date=date_val,
            amount=amount,
            category=category,
            description=description or '',
            source_file=source_file
        )
    else:
        qs = Expense.objects.filter(
            user=user,
            date=date_val,
            amount=amount,
            category=category,
            description=description or '',
            source_file=source_file
        )
    return qs.exists()


def find_duplicates(user, source_file: Optional[UploadedFile] = None) -> Dict[str, List[Dict]]:
    """Находит все дубликаты транзакций. Возвращает {'incomes': [...], 'expenses': [...]}"""
    duplicates = {'incomes': [], 'expenses': []}
    
    # Для доходов
    incomes = Income.objects.filter(user=user)
    if source_file:
        incomes = incomes.filter(source_file=source_file)
    
    seen = {}
    for inc in incomes:
        key = (inc.date, inc.amount, inc.category, inc.description or '', inc.source_file_id)
        if key in seen:
            if key not in [d['key'] for d in duplicates['incomes']]:
                duplicates['incomes'].append({
                    'key': key,
                    'transactions': [seen[key], inc.id]
                })
            else:
                idx = next(i for i, d in enumerate(duplicates['incomes']) if d['key'] == key)
                if inc.id not in duplicates['incomes'][idx]['transactions']:
                    duplicates['incomes'][idx]['transactions'].append(inc.id)
        else:
            seen[key] = inc.id
    
    # Для расходов
    expenses = Expense.objects.filter(user=user)
    if source_file:
        expenses = expenses.filter(source_file=source_file)
    
    seen = {}
    for exp in expenses:
        key = (exp.date, exp.amount, exp.category, exp.description or '', exp.source_file_id)
        if key in seen:
            if key not in [d['key'] for d in duplicates['expenses']]:
                duplicates['expenses'].append({
                    'key': key,
                    'transactions': [seen[key], exp.id]
                })
            else:
                idx = next(i for i, d in enumerate(duplicates['expenses']) if d['key'] == key)
                if exp.id not in duplicates['expenses'][idx]['transactions']:
                    duplicates['expenses'][idx]['transactions'].append(exp.id)
        else:
            seen[key] = exp.id
    
    return duplicates


def import_csv_transactions(file_obj, import_to_db: bool = True, user=None, source_file: Optional[UploadedFile] = None) -> Tuple[int, int, List[str], Dict]:
    """Import CSV with columns: type(income|expense), date(YYYY-MM-DD), amount, category(optional), description(optional).
    Returns (num_incomes, num_expenses, errors, stats_dict).
    stats_dict содержит: {'duplicates_skipped': int, 'duplicates_found': int, 'should_warn': bool}
    """
    errors: List[str] = []
    stats = {'duplicates_skipped': 0, 'duplicates_found': 0, 'should_warn': False}
    
    # Получаем настройки пользователя
    auto_clear = False
    auto_remove_dups = False
    if user and hasattr(user, 'profile'):
        auto_clear = user.profile.auto_clear_file_on_import
        auto_remove_dups = user.profile.auto_remove_duplicates
    
    # Если включена автоматическая очистка, удаляем все транзакции из этого файла
    if import_to_db and source_file and auto_clear:
        Income.objects.filter(user=user, source_file=source_file).delete()
        Expense.objects.filter(user=user, source_file=source_file).delete()
    
    try:
        df = pd.read_csv(file_obj)
    except Exception as e:
        return 0, 0, [f'Ошибка чтения CSV: {e}'], stats

    cols = set(c.lower() for c in df.columns)
    if not CSV_REQUIRED_COLUMNS.issubset(cols):
        return 0, 0, [f'CSV должен содержать столбцы: {", ".join(sorted(CSV_REQUIRED_COLUMNS))}'], stats

    # normalize columns
    df.columns = [c.lower() for c in df.columns]
    df['category'] = df.get('category', '').fillna('')
    df['description'] = df.get('description', '').fillna('')

    num_i = 0
    num_e = 0
    income_objs: List[Income] = []
    expense_objs: List[Expense] = []
    total_rows = len(df)
    duplicate_rows = 0

    for _, row in df.iterrows():
        try:
            typ = str(row['type']).strip().lower()
            dt = pd.to_datetime(row['date']).date()
            amt = float(row['amount'])
            cat = str(row.get('category', '') or 'other')
            desc = str(row.get('description', '') or '')
        except Exception as e:
            errors.append(f'Строка с ошибкой: {e}')
            continue

        # Проверка на дубликаты
        is_duplicate = False
        if import_to_db and source_file:
            is_duplicate = _check_duplicate(typ, dt, amt, cat, desc, source_file, user)
            if is_duplicate:
                duplicate_rows += 1
                stats['duplicates_found'] += 1
                if not auto_remove_dups:
                    continue  # Пропускаем дубликат

        if typ == 'income':
            num_i += 1
            if import_to_db and not is_duplicate:
                income_objs.append(Income(amount=amt, date=dt, category=cat if cat else 'other', description=desc, user=user, source_file=source_file))
        elif typ == 'expense':
            num_e += 1
            if import_to_db and not is_duplicate:
                expense_objs.append(Expense(amount=amt, date=dt, category=cat if cat else 'other', description=desc, user=user, source_file=source_file))
        else:
            errors.append(f'Неизвестный type: {typ}')

    # Проверка на предупреждение (>50% дублей)
    if total_rows > 0 and duplicate_rows / total_rows > 0.5:
        stats['should_warn'] = True

    stats['duplicates_skipped'] = duplicate_rows

    if import_to_db and (income_objs or expense_objs):
        _persist_transactions(income_objs, expense_objs)

    return num_i, num_e, errors, stats


def import_excel_transactions(file_obj, import_to_db: bool = True, sheet_name: Optional[str] = None, user=None, source_file: Optional[UploadedFile] = None) -> Tuple[int, int, List[str], Dict]:
    """
    Import Excel (.xlsx, .xls) with columns: type(income|expense), date(YYYY-MM-DD), amount, category(optional), description(optional).
    Returns (num_incomes, num_expenses, errors, stats_dict).
    stats_dict содержит: {'duplicates_skipped': int, 'duplicates_found': int, 'should_warn': bool}
    
    Args:
        file_obj: Excel file object
        import_to_db: Whether to import to database
        sheet_name: Specific sheet name to read (None = first sheet)
        user: User object
        source_file: UploadedFile object (источник транзакций)
    """
    errors: List[str] = []
    stats = {'duplicates_skipped': 0, 'duplicates_found': 0, 'should_warn': False}
    
    # Получаем настройки пользователя
    auto_clear = False
    auto_remove_dups = False
    if user and hasattr(user, 'profile'):
        auto_clear = user.profile.auto_clear_file_on_import
        auto_remove_dups = user.profile.auto_remove_duplicates
    
    # Если включена автоматическая очистка, удаляем все транзакции из этого файла
    if import_to_db and source_file and auto_clear:
        Income.objects.filter(user=user, source_file=source_file).delete()
        Expense.objects.filter(user=user, source_file=source_file).delete()
    
    try:
        # Read Excel file
        df = pd.read_excel(file_obj, sheet_name=sheet_name, engine='openpyxl')
    except Exception as e:
        # Try with xlrd for .xls files
        try:
            file_obj.seek(0)
            df = pd.read_excel(file_obj, sheet_name=sheet_name, engine='xlrd')
        except Exception as e2:
            return 0, 0, [f'Ошибка чтения Excel: {e}. Также попытка с xlrd: {e2}'], stats

    cols = set(c.lower() for c in df.columns)
    if not CSV_REQUIRED_COLUMNS.issubset(cols):
        return 0, 0, [f'Excel должен содержать столбцы: {", ".join(sorted(CSV_REQUIRED_COLUMNS))}'], stats

    # normalize columns
    df.columns = [c.lower() for c in df.columns]
    df['category'] = df.get('category', '').fillna('')
    df['description'] = df.get('description', '').fillna('')

    num_i = 0
    num_e = 0
    income_objs: List[Income] = []
    expense_objs: List[Expense] = []
    total_rows = len(df)
    duplicate_rows = 0

    for _, row in df.iterrows():
        try:
            typ = str(row['type']).strip().lower()
            dt = pd.to_datetime(row['date']).date()
            amt = float(row['amount'])
            cat = str(row.get('category', '') or 'other')
            desc = str(row.get('description', '') or '')
        except Exception as e:
            errors.append(f'Строка с ошибкой: {e}')
            continue

        # Проверка на дубликаты
        is_duplicate = False
        if import_to_db and source_file:
            is_duplicate = _check_duplicate(typ, dt, amt, cat, desc, source_file, user)
            if is_duplicate:
                duplicate_rows += 1
                stats['duplicates_found'] += 1
                if not auto_remove_dups:
                    continue  # Пропускаем дубликат

        if typ == 'income':
            num_i += 1
            if import_to_db and not is_duplicate:
                income_objs.append(Income(amount=amt, date=dt, category=cat if cat else 'other', description=desc, user=user, source_file=source_file))
        elif typ == 'expense':
            num_e += 1
            if import_to_db and not is_duplicate:
                expense_objs.append(Expense(amount=amt, date=dt, category=cat if cat else 'other', description=desc, user=user, source_file=source_file))
        else:
            errors.append(f'Неизвестный type: {typ}')

    # Проверка на предупреждение (>50% дублей)
    if total_rows > 0 and duplicate_rows / total_rows > 0.5:
        stats['should_warn'] = True

    stats['duplicates_skipped'] = duplicate_rows

    if import_to_db and (income_objs or expense_objs):
        _persist_transactions(income_objs, expense_objs)

    return num_i, num_e, errors, stats


def extract_text_from_docx(file_obj) -> str:
    try:
        from docx import Document as Docx
        doc = Docx(file_obj)
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:
        return f"[Ошибка чтения DOCX: {e}]"


def extract_text_from_pdf(file_obj) -> str:
    try:
        from pdfminer.high_level import extract_text
        # pdfminer принимает путь или file-like; читаем bytes и отдаём BytesIO
        data = file_obj.read()
        return extract_text(io.BytesIO(data))
    except Exception as e:
        return f"[Ошибка чтения PDF: {e}]"


def create_document_from_text(doc_type: str, text: str, user=None) -> Document:
    return Document.objects.create(doc_type=doc_type, params={}, generated_text=text, user=user)


def quick_text_amounts_summary(text: str) -> dict:
    """Very simple heuristic to find amounts and hint a quick summary."""
    nums = [float(x.replace(',', '.')) for x in re.findall(r"\b\d+[\.,]?\d*\b", text or '')]
    total = round(sum(nums), 2) if nums else 0.0
    return {
        'numbers_found': len(nums),
        'sum_of_numbers': total,
    }

