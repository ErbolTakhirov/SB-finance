from collections import defaultdict
from django.db.models import Sum


def build_recommendations(incomes_qs, expenses_qs):
    recs = []

    # 1) Excessive spend in any category > 40% of total expenses
    total_expense = expenses_qs.aggregate(total=Sum('amount'))['total'] or 0
    by_cat = expenses_qs.values('category').annotate(total=Sum('amount')).order_by('-total')
    for row in by_cat:
        if total_expense and row['total'] / total_expense > 0.4:
            recs.append(f"Слишком высокие расходы по категории '{row['category']}'. Рассмотрите оптимизацию затрат.")

    # 2) Income trend decrease: compare last 3 months vs previous 3
    def monthly(qs):
        agg = defaultdict(float)
        for o in qs:
            k = o.date.replace(day=1)
            agg[k] += float(o.amount)
        months = sorted(agg.keys())
        return months, [agg[m] for m in months]

    m, v = monthly(incomes_qs)
    if len(v) >= 6:
        recent = sum(v[-3:]) / 3
        prev = sum(v[-6:-3]) / 3
        if recent < prev * 0.9:  # >10% drop
            recs.append("Замечено снижение доходов. Усильте продажи/маркетинг и проработайте воронку.")

    if not recs:
        recs.append("Финансовые показатели стабильны. Продолжайте действующие практики и мониторинг.")

    return recs

