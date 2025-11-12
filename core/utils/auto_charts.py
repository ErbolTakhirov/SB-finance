from __future__ import annotations

import io
import json
import math
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


MAX_ROWS_DEFAULT = 200_000
PREVIEW_ROWS = 150
LARGE_DATA_THRESHOLD = 1_000


INCOME_LABELS = {
    'income', 'доход', 'поступление', 'приход', 'revenue', 'profit', 'выручка',
    'credit', 'incoming', 'inflow', 'deposit', 'пополнение', 'salary', 'зарплата',
    'дебет', 'поступления', 'переводвход', 'приходы'
}
EXPENSE_LABELS = {
    'expense', 'расход', 'withdrawal', 'outgoing', 'outflow', 'payment',
    'оплата', 'платеж', 'списание', 'debit', 'расходы', 'переводисход',
    'снятие', 'кредиты', 'затраты', 'затрата', 'purchase', 'покупка'
}


COLUMN_SYNONYMS: Dict[str, Sequence[str]] = {
    'date': (
        'date', 'дата', 'датаоперации', 'operationdate', 'transactiondate',
        'posteddate', 'датаоперациипо', 'дата_операции', 'дататранзакции',
        'timestamp', 'время', 'processedat', 'bookeddate', 'period', 'month',
        'годмесяц', 'periodstart', 'periodend'
    ),
    'amount': (
        'amount', 'сумма', 'итого', 'total', 'value', 'transactionamount',
        'суммаоперации', 'sum', 'итоговаясумма', 'итогпосле', 'netamount',
        'grossamount', 'amountlocal', 'ammount', 'к оплате', 'debitcredit'
    ),
    'income': (
        'income', 'доход', 'поступление', 'приход', 'credit', 'inflow', 'incoming',
        'revenue', 'зарплата', 'salary', 'пополнение', 'дебет', 'creditamount',
        'приходы'
    ),
    'expense': (
        'expense', 'расход', 'withdrawal', 'payment', 'outflow', 'списание',
        'платеж', 'debit', 'исход', 'outgoing', 'затраты', 'покупка', 'расходы',
        'debitamount', 'расходыитого'
    ),
    'category': (
        'category', 'категория', 'категориярасхода', 'категориядохода', 'article',
        'статья', 'статьярасходов', 'articleexpense', 'типрасхода', 'типдохода',
        'наименованиестатьи', 'группа', 'направление', 'segment', 'costcenter',
        'budgetitem'
    ),
    'tag': (
        'tag', 'tags', 'тег', 'теги', 'label', 'метка', 'ярлык', 'labels', 'группа',
        'group', 'segment', 'classification'
    ),
    'type': (
        'type', 'тип', 'direction', 'operationtype', 'transactiontype', 'вид',
        'приходрасход', 'доходрасход', 'drcr', 'creditdebit', 'categorytype'
    ),
    'account': (
        'account', 'счет', 'счёт', 'accountname', 'accountnumber', 'iban',
        'card', 'cardnumber', 'кошелек', 'wallet', 'расчетныйсчет', 'bankaccount',
        'accountid', 'accounttitle'
    ),
    'balance': (
        'balance', 'баланс', 'остаток', 'остатокпосле', 'saldo', 'остатокпоследействия',
        'balanceafter', 'остатокпо', 'balance_final'
    ),
    'person': (
        'person', 'payee', 'partner', 'контрагент', 'client', 'customer', 'vendor',
        'поставщик', 'supplier', 'beneficiary', 'получатель', 'плательщик',
        'counterparty', 'payer', 'receiver'
    ),
    'description': (
        'description', 'описание', 'note', 'details', 'memo', 'comment', 'назначение',
        'commentary', 'назначениеплатежа', 'note1', 'comment1', 'примечание'
    ),
    'currency': (
        'currency', 'валюта', 'ccy', 'curr', 'currcode', 'кодвалюты', 'валютасделки'
    ),
    'project': (
        'project', 'проект', 'costcenter', 'profitcenter', 'unit', 'подразделение',
        'department', 'департамент'
    ),
}


def _simplify(text: Any) -> str:
    raw = str(text or '').strip().lower()
    raw = raw.replace('ё', 'е')
    return ''.join(ch for ch in raw if ch.isalnum())


def _match_role(column_key: str, role: str) -> bool:
    targets = COLUMN_SYNONYMS.get(role, ())
    if not targets:
        return False
    for pattern in targets:
        key = _simplify(pattern)
        if not key:
            continue
        if column_key == key or column_key.endswith(key) or key in column_key:
            return True
    return False


def load_dataframe_from_bytes(file_bytes: bytes, file_extension: str, *, max_rows: int = MAX_ROWS_DEFAULT) -> pd.DataFrame:
    """Loads CSV/Excel data into a DataFrame, applying basic heuristics for delimiters and encodings."""
    ext = (file_extension or '').split('.')[-1].lower()
    buffer = io.BytesIO(file_bytes)

    if ext in ('csv', 'txt'):
        try:
            df = pd.read_csv(buffer)
        except Exception:
            buffer.seek(0)
            try:
                df = pd.read_csv(buffer, sep=None, engine='python')
            except Exception:
                buffer.seek(0)
                df = pd.read_csv(buffer, delimiter=';')
    elif ext in ('xlsx', 'xls'):
        df = pd.read_excel(buffer)
    else:
        raise ValueError(f"Unsupported file type for chart generation: {file_extension}")

    if max_rows and len(df) > max_rows:
        df = df.head(max_rows).copy()
    return df


@dataclass
class DetectedSchema:
    original_columns: List[str]
    role_map: Dict[str, List[str]]
    numeric_columns: List[str]
    categorical_columns: List[str]
    text_columns: List[str]

    def first(self, role: str) -> Optional[str]:
        items = self.role_map.get(role) or []
        return items[0] if items else None


def detect_schema(df: pd.DataFrame) -> DetectedSchema:
    numeric_cols: List[str] = []
    categorical_cols: List[str] = []
    text_cols: List[str] = []
    role_map: Dict[str, List[str]] = {key: [] for key in COLUMN_SYNONYMS.keys()}
    role_map.update({'unknown': []})

    for col in df.columns:
        simplified = _simplify(col)
        matched_roles: List[str] = []
        for role in COLUMN_SYNONYMS.keys():
            if _match_role(simplified, role):
                role_map.setdefault(role, []).append(col)
                matched_roles.append(role)

        if not matched_roles:
            role_map.setdefault('unknown', []).append(col)

        if pd.api.types.is_numeric_dtype(df[col]):
            numeric_cols.append(col)
        else:
            # attempt to treat as numeric after cleaning
            try:
                pd.to_numeric(df[col], errors='raise')
                numeric_cols.append(col)
                continue
            except Exception:
                pass

            # treat as categorical / text
            nunique = df[col].nunique(dropna=True)
            if nunique and nunique <= max(50, len(df) * 0.2):
                categorical_cols.append(col)
            else:
                text_cols.append(col)

    # ensure canonical keys exist
    for key in COLUMN_SYNONYMS.keys():
        role_map.setdefault(key, [])

    return DetectedSchema(
        original_columns=list(df.columns),
        role_map=role_map,
        numeric_columns=numeric_cols,
        categorical_columns=categorical_cols,
        text_columns=text_cols,
    )


def _to_numeric(series: pd.Series) -> pd.Series:
    if series is None:
        return pd.Series(dtype=float)
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors='coerce')

    cleaned = (
        series.astype(str)
        .str.replace('\u00A0', '', regex=False)
        .str.replace(' ', '', regex=False)
        .str.replace(',', '.', regex=False)
    )
    cleaned = cleaned.replace({'': np.nan, 'nan': np.nan, 'None': np.nan})
    return pd.to_numeric(cleaned, errors='coerce')


def _extract_first_non_empty(series: pd.Series) -> pd.Series:
    if series is None:
        return pd.Series(dtype=object)
    return series.fillna('').astype(str).str.strip()


def _infer_income_expense(
    df: pd.DataFrame,
    schema: DetectedSchema,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Returns (amount_series, income_series, expense_series) with expenses as positive values."""
    amount_cols = schema.role_map.get('amount') or []
    income_cols = schema.role_map.get('income') or []
    expense_cols = schema.role_map.get('expense') or []
    type_cols = schema.role_map.get('type') or []

    amount = None
    if amount_cols:
        amount = _to_numeric(df[amount_cols[0]])
    elif income_cols or expense_cols:
        amount = pd.Series(0.0, index=df.index)
    else:
        # fallback to numeric columns
        for col in schema.numeric_columns:
            if df[col].dtype != object:
                amount = _to_numeric(df[col])
                break

    income = pd.Series(0.0, index=df.index)
    expense = pd.Series(0.0, index=df.index)

    if income_cols:
        for col in income_cols:
            income = income.add(_to_numeric(df[col]).fillna(0), fill_value=0)
    if expense_cols:
        for col in expense_cols:
            expense = expense.add(_to_numeric(df[col]).abs().fillna(0), fill_value=0)

    if amount is None:
        amount = income.sub(expense, fill_value=0)

    # Determine sign via type labels if necessary
    if not income_cols or not expense_cols:
        type_series = None
        if type_cols:
            type_series = df[type_cols[0]].astype(str).str.lower()

        inferred_income = pd.Series(0.0, index=df.index)
        inferred_expense = pd.Series(0.0, index=df.index)

        if type_series is not None and amount is not None:
            income_mask = type_series.apply(lambda x: any(lbl in x for lbl in INCOME_LABELS))
            expense_mask = type_series.apply(lambda x: any(lbl in x for lbl in EXPENSE_LABELS))

            if income_mask.any():
                inferred_income.loc[income_mask] = amount.loc[income_mask].abs()
            if expense_mask.any():
                inferred_expense.loc[expense_mask] = amount.loc[expense_mask].abs()

        if not inferred_income.any() and not inferred_expense.any() and amount is not None:
            # fallback: positive -> income, negative -> expense
            inferred_income = amount.clip(lower=0).abs()
            inferred_expense = amount.clip(upper=0).abs()

        if not income_cols:
            income = inferred_income
        if not expense_cols:
            expense = inferred_expense

    # ensure amount derived from income/expense if it was missing
    if amount is None or (amount.abs().sum(skipna=True) == 0 and (income.any() or expense.any())):
        amount = income - expense

    return amount.fillna(0), income.fillna(0), expense.fillna(0)


def _prepare_normalized_dataframe(df: pd.DataFrame, schema: DetectedSchema) -> pd.DataFrame:
    result = df.copy()

    date_col = schema.first('date')
    if date_col:
        result['__date__'] = pd.to_datetime(df[date_col], errors='coerce')
    else:
        result['__date__'] = pd.NaT

    category_col = (schema.role_map.get('category') or [None])[0]
    if category_col:
        result['__category__'] = _extract_first_non_empty(df[category_col])
    else:
        result['__category__'] = ''

    tag_col = (schema.role_map.get('tag') or [None])[0]
    if tag_col:
        result['__tag__'] = _extract_first_non_empty(df[tag_col])
    else:
        result['__tag__'] = ''

    account_col = (schema.role_map.get('account') or [None])[0]
    if account_col:
        result['__account__'] = _extract_first_non_empty(df[account_col])
    else:
        result['__account__'] = ''

    person_col = (schema.role_map.get('person') or [None])[0]
    if person_col:
        result['__person__'] = _extract_first_non_empty(df[person_col])
    else:
        result['__person__'] = ''

    balance_col = (schema.role_map.get('balance') or [None])[0]
    if balance_col:
        result['__balance__'] = _to_numeric(df[balance_col])
    else:
        result['__balance__'] = np.nan

    amount, income, expense = _infer_income_expense(df, schema)
    result['__amount__'] = amount
    result['__income__'] = income
    result['__expense__'] = expense
    result['__abs_amount__'] = amount.abs()
    result['__net__'] = income - expense

    type_col = (schema.role_map.get('type') or [None])[0]
    if type_col:
        result['__type__'] = df[type_col].astype(str).str.strip()
    else:
        result['__type__'] = ''

    description_col = (schema.role_map.get('description') or [None])[0]
    if description_col:
        result['__description__'] = df[description_col].astype(str).str.strip()
    else:
        result['__description__'] = ''

    return result


def _format_currency(value: float) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "0"
    try:
        return f"{value:,.2f}".replace(",", " ").replace(".00", "")
    except Exception:
        return str(value)


def _group_by_period(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    grouped = df.copy()
    grouped = grouped.dropna(subset=['__date__'])
    if grouped.empty:
        return grouped
    grouped['__period__'] = grouped['__date__'].dt.to_period(freq).dt.to_timestamp()
    return grouped.groupby('__period__')[['__amount__', '__income__', '__expense__']].sum().reset_index()


def _choose_frequency(date_series: pd.Series) -> str:
    date_series = date_series.dropna()
    if date_series.empty:
        return 'M'
    min_date = date_series.min()
    max_date = date_series.max()
    span_days = (max_date - min_date).days if isinstance(max_date, pd.Timestamp) else 0
    if span_days > 720:
        return 'Q'
    if span_days > 120:
        return 'M'
    if span_days > 30:
        return 'W'
    return 'D'


def _build_time_series_charts(df_norm: pd.DataFrame) -> List[Dict[str, Any]]:
    charts: List[Dict[str, Any]] = []
    if '__date__' not in df_norm.columns or df_norm['__date__'].dropna().empty:
        return charts

    freq = _choose_frequency(df_norm['__date__'])
    aggregated = _group_by_period(df_norm, freq)
    if aggregated.empty:
        return charts

    labels = aggregated['__period__'].dt.strftime('%Y-%m')
    income_values = aggregated['__income__'].round(2).tolist()
    expense_values = aggregated['__expense__'].round(2).tolist()
    balance_values = aggregated['__amount__'].round(2).tolist()

    has_income = any(abs(v) > 1e-9 for v in income_values)
    has_expense = any(abs(v) > 1e-9 for v in expense_values)

    # Line chart (income vs expense)
    line_datasets = []
    insight_parts: List[str] = []
    if has_income:
        line_datasets.append({
            'label': 'Доходы',
            'data': income_values,
            'borderColor': '#16a34a',
            'backgroundColor': 'rgba(22, 163, 74, 0.2)',
            'tension': 0.35,
            'fill': False,
        })
        insight_parts.append(f"максимальные доходы {_format_currency(max(income_values))}")
    if has_expense:
        line_datasets.append({
            'label': 'Расходы',
            'data': expense_values,
            'borderColor': '#ef4444',
            'backgroundColor': 'rgba(239, 68, 68, 0.2)',
            'tension': 0.35,
            'fill': False,
        })
        insight_parts.append(f"максимальные расходы {_format_currency(max(expense_values))}")
    if not line_datasets:
        line_datasets.append({
            'label': 'Оборот',
            'data': balance_values,
            'borderColor': '#3b82f6',
            'backgroundColor': 'rgba(59, 130, 246, 0.2)',
            'tension': 0.35,
            'fill': False,
        })

    charts.append({
        'id': 'trend_income_expense',
        'type': 'line',
        'priority': 1,
        'title': 'Динамика по датам',
        'subtitle': 'Агрегация по периодам',
        'insight': '; '.join(insight_parts) if insight_parts else '',
        'chartjs': {
            'data': {
                'labels': labels.tolist(),
                'datasets': line_datasets,
            },
            'options': {
                'responsive': True,
                'interaction': {'mode': 'index', 'intersect': False},
                'maintainAspectRatio': False,
                'scales': {
                    'y': {
                        'ticks': {'callback': "value => value.toLocaleString('ru-RU')"},
                        'title': {'display': True, 'text': 'Сумма'},
                    },
                },
            },
        },
        'meta': {'frequency': freq, 'records': len(aggregated)},
    })

    if has_income and has_expense:
        charts.append({
            'id': 'bar_income_vs_expense',
            'type': 'bar',
            'variant': 'grouped',
            'priority': 2,
            'title': 'Доходы vs расходы по периодам',
            'insight': '',
            'chartjs': {
                'data': {
                    'labels': labels.tolist(),
                    'datasets': [
                        {
                            'label': 'Доходы',
                            'data': income_values,
                            'backgroundColor': 'rgba(22, 163, 74, 0.7)',
                            'borderRadius': 6,
                        },
                        {
                            'label': 'Расходы',
                            'data': expense_values,
                            'backgroundColor': 'rgba(239, 68, 68, 0.75)',
                            'borderRadius': 6,
                        },
                    ],
                },
                'options': {
                    'responsive': True,
                    'maintainAspectRatio': False,
                    'interaction': {'mode': 'index', 'intersect': False},
                    'scales': {
                        'x': {'stacked': False},
                        'y': {'stacked': False, 'beginAtZero': True},
                    },
                },
            },
            'meta': {'frequency': freq, 'records': len(aggregated)},
        })

    return charts


def _build_category_charts(df_norm: pd.DataFrame) -> List[Dict[str, Any]]:
    charts: List[Dict[str, Any]] = []
    if '__category__' not in df_norm or df_norm['__category__'].replace('', np.nan).dropna().empty:
        return charts

    cat_group = (
        df_norm.groupby('__category__')[['__expense__', '__income__', '__amount__']]
        .sum()
        .sort_values('__expense__', ascending=False)
    )
    if cat_group.empty:
        return charts

    top = cat_group.head(8)
    labels = top.index.tolist()
    expenses = top['__expense__'].round(2).tolist()
    incomes = top['__income__'].round(2).tolist()

    total_expenses = cat_group['__expense__'].sum()
    if total_expenses <= 0:
        total_expenses = cat_group['__amount__'].clip(lower=0).sum()
    pie_values = expenses if sum(expenses) > 0 else [abs(v) for v in top['__amount__'].tolist()]

    charts.append({
        'id': 'pie_expense_categories',
        'type': 'pie',
        'priority': 1,
        'title': 'Структура расходов по категориям',
        'insight': f"Топ категория: {labels[0]} ({_format_currency(expenses[0])})" if labels else '',
        'chartjs': {
            'data': {
                'labels': labels,
                'datasets': [{
                    'label': 'Расходы',
                    'data': pie_values,
                    'backgroundColor': [
                        '#ef4444', '#f97316', '#f59e0b', '#10b981', '#3b82f6', '#a855f7', '#ec4899', '#0ea5e9'
                    ],
                }],
            },
            'options': {
                'responsive': True,
                'maintainAspectRatio': False,
            },
        },
        'meta': {'records': len(cat_group)},
    })

    charts.append({
        'id': 'bar_top_categories',
        'type': 'bar',
        'priority': 2,
        'title': 'ТОП категорий по тратам',
        'variant': 'vertical',
        'chartjs': {
            'data': {
                'labels': labels,
                'datasets': [{
                    'label': 'Расходы',
                    'data': expenses,
                    'backgroundColor': 'rgba(239, 68, 68, 0.75)',
                    'borderRadius': 8,
                }],
            },
            'options': {
                'responsive': True,
                'maintainAspectRatio': False,
                'scales': {
                    'y': {'beginAtZero': True},
                },
            },
        },
        'meta': {'records': len(cat_group)},
    })

    if incomes and any(v > 0 for v in incomes):
        charts.append({
            'id': 'bar_top_income_categories',
            'type': 'bar',
            'priority': 3,
            'title': 'ТОП категорий по доходам',
            'variant': 'vertical',
            'chartjs': {
                'data': {
                    'labels': labels,
                    'datasets': [{
                        'label': 'Доходы',
                        'data': incomes,
                        'backgroundColor': 'rgba(16, 185, 129, 0.8)',
                        'borderRadius': 8,
                    }],
                },
                'options': {
                    'responsive': True,
                    'maintainAspectRatio': False,
                    'scales': {
                        'y': {'beginAtZero': True},
                    },
                },
            },
            'meta': {'records': len(cat_group)},
        })

    return charts


def _build_partner_chart(df_norm: pd.DataFrame) -> Optional[Dict[str, Any]]:
    if '__person__' not in df_norm:
        return None
    person_series = df_norm['__person__'].replace('', np.nan).dropna()
    if person_series.empty:
        return None
    partner_group = (
        df_norm.groupby('__person__')[['__expense__', '__income__']]
        .sum()
        .sort_values('__expense__', ascending=False)
    )
    if partner_group.empty:
        return None

    top = partner_group.head(7)
    labels = top.index.tolist()
    expenses = top['__expense__'].round(2).tolist()

    datasets = [{
        'label': 'Расходы',
        'data': expenses,
        'backgroundColor': 'rgba(59, 130, 246, 0.8)',
        'borderRadius': 6,
    }]

    if top['__income__'].sum() > 0:
        datasets.append({
            'label': 'Доходы',
            'data': top['__income__'].round(2).tolist(),
            'backgroundColor': 'rgba(16, 185, 129, 0.8)',
            'borderRadius': 6,
        })

    return {
        'id': 'bar_top_partners',
        'type': 'bar',
        'variant': 'horizontal',
        'priority': 1,
        'title': 'ТОП партнёров',
        'chartjs': {
            'data': {
                'labels': labels,
                'datasets': datasets,
            },
            'options': {
                'indexAxis': 'y',
                'responsive': True,
                'maintainAspectRatio': False,
                'scales': {
                    'x': {'beginAtZero': True},
                },
            },
        },
        'meta': {'records': len(partner_group)},
    }


def _build_account_chart(df_norm: pd.DataFrame) -> Optional[Dict[str, Any]]:
    if '__account__' not in df_norm:
        return None
    df_account = df_norm[['__date__', '__account__', '__balance__']].dropna(subset=['__date__'])
    if df_account.empty:
        return None
    has_balance = df_account['__balance__'].notna().any()
    if not has_balance and '__amount__' in df_norm:
        # rebuild balance cumulatively per account if possible
        df_account = df_norm[['__date__', '__account__', '__amount__']].dropna(subset=['__date__'])
        if df_account.empty:
            return None
        df_account = df_account.sort_values('__date__')
        df_account['__balance__'] = df_account.groupby('__account__')['__amount__'].cumsum()

    if df_account['__account__'].replace('', np.nan).dropna().nunique() <= 1:
        return None

    freq = _choose_frequency(df_account['__date__'])
    df_account['__period__'] = df_account['__date__'].dt.to_period(freq).dt.to_timestamp()
    pivot = (
        df_account.groupby(['__period__', '__account__'])['__balance__']
        .last()
        .unstack('__account__')
        .fillna(method='ffill')
        .fillna(0)
    )
    if pivot.empty:
        return None

    labels = pivot.index.strftime('%Y-%m').tolist()
    datasets = []
    colors = [
        '#3b82f6', '#10b981', '#6366f1', '#f97316', '#ef4444', '#8b5cf6', '#0ea5e9',
        '#14b8a6', '#f59e0b'
    ]
    for idx, account in enumerate(pivot.columns):
        datasets.append({
            'label': str(account),
            'data': pivot[account].round(2).tolist(),
            'borderColor': colors[idx % len(colors)],
            'backgroundColor': colors[idx % len(colors)],
            'fill': False,
            'tension': 0.25,
        })

    return {
        'id': 'line_account_balances',
        'type': 'line',
        'priority': 3,
        'title': 'Баланс по счетам',
        'chartjs': {
            'data': {'labels': labels, 'datasets': datasets},
            'options': {
                'responsive': True,
                'maintainAspectRatio': False,
                'interaction': {'mode': 'index', 'intersect': False},
            },
        },
        'meta': {'records': int(df_account['__account__'].nunique())},
    }


def _build_anomaly_scatter(df_norm: pd.DataFrame) -> Optional[Dict[str, Any]]:
    if '__date__' not in df_norm or df_norm['__date__'].dropna().empty:
        return None
    if '__abs_amount__' not in df_norm:
        return None

    df_amounts = df_norm[['__date__', '__amount__', '__category__', '__person__']].dropna(subset=['__date__'])
    if df_amounts.empty:
        return None

    values = df_amounts['__amount__']
    if values.abs().sum() == 0:
        return None

    mean_val = values.mean()
    std_val = values.std(ddof=0) if len(values) > 1 else 0
    threshold = mean_val + 2.5 * std_val if std_val else values.abs().max()
    anomalies = df_amounts[values.abs() >= abs(threshold)].copy()

    scatter_points = [{
        'x': row['__date__'].isoformat(),
        'y': round(row['__amount__'], 2),
        'category': row['__category__'],
        'person': row['__person__'],
    } for _, row in df_amounts.iterrows()]

    return {
        'id': 'scatter_anomalies',
        'type': 'scatter',
        'priority': 4,
        'title': 'Выбросы и крупные транзакции',
        'insight': f"Обнаружено {len(anomalies)} аномалий" if len(anomalies) else 'Явных выбросов не найдено',
        'chartjs': {
            'data': {
                'datasets': [{
                    'label': 'Транзакции',
                    'data': scatter_points,
                    'backgroundColor': 'rgba(99, 102, 241, 0.65)',
                    'pointRadius': 4,
                }],
            },
            'options': {
                'responsive': True,
                'maintainAspectRatio': False,
                'scales': {
                    'x': {'type': 'time', 'time': {'unit': 'day'}},
                },
            },
        },
        'meta': {'anomalies': len(anomalies)},
    }


def _collect_insights(df_norm: pd.DataFrame) -> Dict[str, Any]:
    total_income = df_norm['__income__'].sum()
    total_expense = df_norm['__expense__'].sum()
    balance = total_income - total_expense
    tx_count = len(df_norm)

    insights = {
        'headline': '',
        'highlights': [],
        'alerts': [],
    }

    insights['headline'] = (
        f"Доходы: {_format_currency(total_income)}, расходы: {_format_currency(total_expense)}, "
        f"баланс: {_format_currency(balance)}"
    )

    # highlight top category
    if '__category__' in df_norm and df_norm['__category__'].replace('', np.nan).dropna().any():
        category_totals = df_norm.groupby('__category__')['__expense__'].sum()
        if not category_totals.empty:
            top_cat = category_totals.idxmax()
            top_value = category_totals.loc[top_cat]
            insights['highlights'].append(
                f"Топ расходная категория: {top_cat} ({_format_currency(top_value)})"
            )

    if balance < 0:
        insights['alerts'].append({
            'type': 'negative_balance',
            'severity': 'critical',
            'message': f"🚩 Отрицательный баланс {_format_currency(balance)}. Расходы превышают доходы.",
        })
    if total_expense > 0 and total_income > 0:
        ratio = total_expense / total_income
        if ratio > 1.2:
            insights['alerts'].append({
                'type': 'expense_ratio',
                'severity': 'warning',
                'message': f"Расходы составляют {ratio:.1f}× от доходов. Проверьте ключевые категории.",
            })

    return insights


def build_auto_charts(
    file_bytes: bytes,
    file_extension: str,
    *,
    max_rows: int = MAX_ROWS_DEFAULT,
) -> Dict[str, Any]:
    df = load_dataframe_from_bytes(file_bytes, file_extension, max_rows=max_rows)
    row_count = len(df)
    if row_count == 0:
        return {
            'ok': False,
            'error': 'Файл пуст — нечего визуализировать.',
            'row_count': 0,
            'warnings': ['Загрузите файл с транзакциями.'],
        }

    schema = detect_schema(df)
    normalized = _prepare_normalized_dataframe(df, schema)

    warnings: List[str] = []
    if not schema.role_map.get('date'):
        warnings.append("Не найдена колонка с датой — временные графики могут быть ограничены.")
    if not schema.role_map.get('amount') and not schema.role_map.get('income') and not schema.role_map.get('expense'):
        warnings.append("Не удалось определить колонку с суммой. Добавьте столбец «amount/сумма».")

    charts: List[Dict[str, Any]] = []
    primary_ids: List[str] = []

    time_charts = _build_time_series_charts(normalized)
    if time_charts:
        charts.extend(time_charts)
        primary_ids.append(time_charts[0]['id'])

    cat_charts = _build_category_charts(normalized)
    if cat_charts:
        charts.extend(cat_charts)
        if len(primary_ids) < 2:
            primary_ids.append(cat_charts[0]['id'])

    partner_chart = _build_partner_chart(normalized)
    if partner_chart:
        charts.append(partner_chart)
        if len(primary_ids) < 3:
            primary_ids.append(partner_chart['id'])

    account_chart = _build_account_chart(normalized)
    if account_chart:
        charts.append(account_chart)

    anomaly_chart = _build_anomaly_scatter(normalized)
    if anomaly_chart:
        charts.append(anomaly_chart)

    if row_count < 5:
        warnings.append("Недостаточно данных для глубокой аналитики. Добавьте больше транзакций.")

    if row_count > LARGE_DATA_THRESHOLD:
        warnings.append("Данные автоматически агрегированы по периодам (1000+ строк). Используйте фильтры для детализации.")

    insights = _collect_insights(normalized)

    schema_payload = {
        'columns': schema.original_columns,
        'detected_roles': schema.role_map,
        'numeric_columns': schema.numeric_columns,
        'categorical_columns': schema.categorical_columns,
        'text_columns': schema.text_columns,
        'normalized_columns': list(normalized.columns),
    }

    preview_json = normalized.head(PREVIEW_ROWS).to_json(orient='records', date_format='iso')
    try:
        preview = json.loads(preview_json)
    except json.JSONDecodeError:
        preview = []

    return {
        'ok': True,
        'row_count': row_count,
        'warnings': warnings,
        'primary_chart_ids': primary_ids[:3],
        'charts': charts,
        'insights': insights,
        'schema': schema_payload,
        'preview': preview,
    }


def build_custom_chart(
    file_bytes: bytes,
    file_extension: str,
    *,
    dimension: str,
    metric: str,
    chart_type: str,
    aggregation: str = 'sum',
) -> Dict[str, Any]:
    df = load_dataframe_from_bytes(file_bytes, file_extension)
    schema = detect_schema(df)
    normalized = _prepare_normalized_dataframe(df, schema)

    dimension_key = dimension
    metric_key = metric

    if dimension_key not in normalized.columns:
        raise ValueError(f"Поле {dimension} отсутствует в данных.")
    if metric_key not in normalized.columns:
        raise ValueError(f"Метрика {metric} отсутствует в данных.")

    series_dim = normalized[dimension_key]
    series_metric = normalized[metric_key]

    if aggregation == 'sum':
        aggregated = normalized.groupby(dimension_key)[metric_key].sum().sort_values(ascending=False)
    elif aggregation == 'avg':
        aggregated = normalized.groupby(dimension_key)[metric_key].mean().sort_values(ascending=False)
    elif aggregation == 'count':
        aggregated = normalized.groupby(dimension_key)[metric_key].count().sort_values(ascending=False)
    else:
        raise ValueError(f"Неподдерживаемая агрегация {aggregation}")

    aggregated = aggregated.head(20)
    labels = [str(k) for k in aggregated.index.tolist()]
    values = [float(v) if pd.notna(v) else 0.0 for v in aggregated.tolist()]

    chart_id = f"custom_{chart_type}_{uuid.uuid4().hex[:8]}"
    dataset_label = f"{aggregation}({metric})"
    if chart_type == 'pie':
        chart_payload = {
            'id': chart_id,
            'type': 'pie',
            'title': f"{dataset_label} по {dimension}",
            'chartjs': {
                'data': {
                    'labels': labels,
                    'datasets': [{
                        'label': dataset_label,
                        'data': values,
                        'backgroundColor': [
                            '#3b82f6', '#ef4444', '#22c55e', '#f97316', '#a855f7', '#0ea5e9', '#14b8a6', '#facc15'
                        ],
                    }],
                },
                'options': {'responsive': True, 'maintainAspectRatio': False},
            },
            'meta': {'source': 'custom', 'dimension': dimension, 'metric': metric, 'aggregation': aggregation},
        }
    else:
        dataset = {
            'label': dataset_label,
            'data': values,
        }
        options = {
            'responsive': True,
            'maintainAspectRatio': False,
        }
        if chart_type == 'horizontalBar':
            options['indexAxis'] = 'y'
            chart_type_real = 'bar'
        else:
            chart_type_real = chart_type if chart_type in {'line', 'bar'} else 'bar'

        if chart_type_real == 'line':
            dataset['borderColor'] = '#3b82f6'
            dataset['backgroundColor'] = 'rgba(59, 130, 246, 0.2)'
            dataset['tension'] = 0.35
            dataset['fill'] = False
        else:
            dataset['backgroundColor'] = 'rgba(59, 130, 246, 0.8)'
            dataset['borderRadius'] = 8

        chart_payload = {
            'id': chart_id,
            'type': chart_type_real,
            'title': f"{dataset_label} по {dimension}",
            'chartjs': {
                'data': {
                    'labels': labels,
                    'datasets': [dataset],
                },
                'options': options,
            },
            'meta': {'source': 'custom', 'dimension': dimension, 'metric': metric, 'aggregation': aggregation},
        }

    return chart_payload


