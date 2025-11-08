import os
from pathlib import Path

import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib


BASE_DIR = Path(__file__).resolve().parents[2]
MEDIA_DIR = BASE_DIR / 'media' / 'ml'
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PATH = MEDIA_DIR / 'expense_classifier.joblib'


def load_demo_data() -> pd.DataFrame:
    data = [
        ('Оплата аренды офиса за март', 'rent'),
        ('Налоговый платёж НДС', 'tax'),
        ('Зарплата сотрудникам за февраль', 'salary'),
        ('Запуск рекламной кампании в соцсетях', 'marketing'),
        ('Закупка сырья и материалов', 'purchase'),
        ('Аренда склада', 'rent'),
        ('Контекстная реклама', 'marketing'),
        ('Единый социальный налог', 'tax'),
        ('Приобретение товара для перепродажи', 'purchase'),
        ('Премии и оклады', 'salary'),
        ('Оплата офисного помещения', 'rent'),
        ('Баннерная реклама', 'marketing'),
    ]
    return pd.DataFrame(data, columns=['text', 'category'])


def train():
    df = load_demo_data()
    X_train, X_test, y_train, y_test = train_test_split(df['text'], df['category'], test_size=0.2, random_state=42)

    pipe = Pipeline([
        ('tfidf', TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
        ('clf', LogisticRegression(max_iter=1000))
    ])

    pipe.fit(X_train, y_train)
    y_pred = pipe.predict(X_test)
    print(classification_report(y_test, y_pred))

    joblib.dump(pipe, MODEL_PATH)
    print(f'Model saved to {MODEL_PATH}')


if __name__ == '__main__':
    train()

