from datetime import date
from typing import Optional

from sklearn.linear_model import LinearRegression
import numpy as np


def forecast_next_month_profit(incomes_qs, expenses_qs) -> Optional[float]:
    # Aggregate by month
    by_month = {}
    for o in incomes_qs:
        key = o.date.replace(day=1)
        by_month[key] = by_month.get(key, 0.0) + float(o.amount)
    for o in expenses_qs:
        key = o.date.replace(day=1)
        by_month[key] = by_month.get(key, 0.0) - float(o.amount)

    if not by_month:
        return None

    months = sorted(by_month.keys())
    profits = [by_month[m] for m in months]
    if len(profits) == 1:
        return profits[0]

    X = np.array(range(len(months))).reshape(-1, 1)
    y = np.array(profits)
    model = LinearRegression()
    model.fit(X, y)
    next_idx = np.array([[len(months)]])
    pred = float(model.predict(next_idx)[0])
    return round(pred, 2)

