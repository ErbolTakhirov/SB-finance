# 🚀 Инструкция по деплою

## Подготовка к публикации на GitHub

### 1. Проверьте файлы

Убедитесь, что следующие файлы созданы и заполнены:
- ✅ `README.md` - описание проекта
- ✅ `.gitignore` - исключения для Git
- ✅ `LICENSE` - лицензия MIT
- ✅ `CONTRIBUTING.md` - руководство для контрибьюторов
- ✅ `env.example` - пример конфигурации

### 2. Обновите информацию в README

Замените в `README.md`:
- `yourusername` на ваш GitHub username
- `your.email@example.com` на ваш email
- Добавьте ссылку на ваш репозиторий

### 3. Инициализируйте Git (если еще не сделано)

```bash
git init
git add .
git commit -m "Initial commit: SB Finance AI project"
```

### 4. Создайте репозиторий на GitHub

1. Перейдите на https://github.com/new
2. Создайте новый репозиторий
3. НЕ добавляйте README, .gitignore или LICENSE (они уже есть)

### 5. Подключите удаленный репозиторий

```bash
git remote add origin https://github.com/yourusername/sb-finance-ai.git
git branch -M main
git push -u origin main
```

### 6. Проверьте, что .env не попал в Git

```bash
# Убедитесь, что .env в .gitignore
git check-ignore .env
# Должно вернуть: .env

# Если .env уже был закоммичен, удалите его из истории:
git rm --cached .env
git commit -m "Remove .env from repository"
```

## Production деплой

### Вариант 1: Heroku

1. Установите Heroku CLI
2. Создайте `Procfile`:
```
web: gunicorn sb_finance.wsgi --log-file -
```
3. Создайте `runtime.txt`:
```
python-3.11
```
4. Деплой:
```bash
heroku create your-app-name
heroku config:set DJANGO_DEBUG=0
heroku config:set DJANGO_SECRET_KEY=your-secret-key
git push heroku main
```

### Вариант 2: DigitalOcean / VPS

1. Установите зависимости на сервере
2. Настройте Nginx + Gunicorn
3. Используйте PostgreSQL вместо SQLite
4. Настройте SSL сертификат (Let's Encrypt)

### Вариант 3: Docker

Создайте `Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "sb_finance.wsgi", "--bind", "0.0.0.0:8000"]
```

## Безопасность для production

1. **Смените SECRET_KEY:**
```python
import secrets
print(secrets.token_urlsafe(50))
```

2. **Отключите DEBUG:**
```env
DJANGO_DEBUG=0
```

3. **Настройте ALLOWED_HOSTS:**
```env
DJANGO_ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
```

4. **Используйте PostgreSQL:**
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'dbname',
        'USER': 'dbuser',
        'PASSWORD': 'dbpass',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

5. **Настройте статические файлы:**
```python
STATIC_ROOT = '/var/www/static/'
MEDIA_ROOT = '/var/www/media/'
```

6. **Включите HTTPS** (обязательно для production)

## Мониторинг

Рекомендуется настроить:
- Логирование ошибок (Sentry, Rollbar)
- Мониторинг производительности
- Резервное копирование БД

