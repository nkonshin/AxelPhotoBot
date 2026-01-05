# Исправление конфликта миграций Alembic

## Проблема

Ошибка: `Multiple head revisions are present for given argument 'head'`

Это означает, что в базе данных есть несколько "головных" миграций, и Alembic не знает, какую применять.

## Решение

### Шаг 1: Остановить контейнеры

```bash
docker-compose down
```

### Шаг 2: Запушить исправленную миграцию

```bash
git add alembic/versions/20260106_add_payments_table.py
git commit -m "fix: Fix alembic migration conflict - set correct down_revision"
git push
```

### Шаг 3: На сервере обновить код

```bash
cd ~/NanoBananaBot
git pull
```

### Шаг 4: Исправить конфликт в базе данных

Есть два варианта:

#### Вариант А: Объединить головы (рекомендуется)

```bash
# Запустить только базу данных
docker-compose up -d db

# Подождать 5 секунд
sleep 5

# Войти в контейнер приложения
docker-compose run --rm app bash

# Внутри контейнера посмотреть текущие головы
alembic heads

# Объединить головы (создаст merge-миграцию)
alembic merge heads -m "merge payment and extend_url migrations"

# Применить миграции
alembic upgrade head

# Выйти
exit
```

#### Вариант Б: Сбросить базу данных (УДАЛИТ ВСЕ ДАННЫЕ!)

**⚠️ ВНИМАНИЕ: Этот вариант удалит все данные пользователей!**

```bash
# Остановить все контейнеры
docker-compose down

# Удалить volume с базой данных
docker volume rm nanobanabot_postgres_data

# Запустить заново
docker-compose up -d
```

### Шаг 5: Запустить бота

```bash
docker-compose up -d
```

### Шаг 6: Проверить логи

```bash
make logs
```

## Проверка успешности

Если всё прошло успешно, вы увидите:

```
telegram_bot_app     | INFO  [alembic.runtime.migration] Running upgrade ... -> f1a2b3c4d5e6, Add payments table for YooKassa integration
telegram_bot_app     | 2026-01-06 ... - __main__ - INFO - Starting application...
telegram_bot_app     | 2026-01-06 ... - __main__ - INFO - Database initialized
```

## Что было исправлено

В файле `alembic/versions/20260106_add_payments_table.py` изменили:

```python
# Было:
down_revision: Union[str, None] = None

# Стало:
down_revision: Union[str, None] = 'extend_source_url'
```

Это указывает Alembic, что миграция `payments` должна идти после миграции `extend_source_url`, а не создавать новую ветку.
