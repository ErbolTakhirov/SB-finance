import os
from pathlib import Path
from typing import Optional

import joblib
from django.conf import settings


MODEL_PATH = Path(getattr(settings, 'MEDIA_ROOT', Path.cwd()) / 'ml' / 'expense_classifier.joblib')


class ExpenseAutoCategorizer:
    def __init__(self) -> None:
        self.model = None
        try:
            if MODEL_PATH.exists():
                self.model = joblib.load(MODEL_PATH)
        except Exception:
            self.model = None

    def predict_category(self, text: str) -> Optional[str]:
        text = (text or '').strip()
        if not text:
            return None
        # ML path
        if self.model is not None:
            try:
                pred = self.model.predict([text])[0]
                return str(pred)
            except Exception:
                pass
        # Fallback simple rules
        low = text.lower()
        if any(w in low for w in ['аренда', 'офис', 'помещ']):
            return 'rent'
        if any(w in low for w in ['налог', 'ндс', 'фнс']):
            return 'tax'
        if any(w in low for w in ['зарплат', 'оклад']):
            return 'salary'
        if any(w in low for w in ['реклам', 'маркет']):
            return 'marketing'
        if any(w in low for w in ['закуп', 'покуп']):
            return 'purchase'
        return 'other'

