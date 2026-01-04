# Production Deployment Guide

Руководство по развертыванию Telegram AI Image Bot на production сервере.

## Требования

- Сервер с Docker и Docker Compose
- Публичный IP или домен
- SSL сертификат (для webhook)
- Минимум 2GB RAM, 20GB диск

## Шаг 1: Подготовка сервера

```bash
# Обновите систему
sudo apt update && sudo apt upgrade -y

# Установите Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Установите Docker Compose
sudo apt install docker-compose-plugin -y

# Добавьте пользователя в группу docker
sudo usermod -aG docker $USER
newgrp docker
```

## Шаг 2: Клонирование проекта

```bash
# Клонируйте репозиторий
git clone <repository-url>
cd NanoBananaTgBot

# Создайте .env файл
cp .env.example .env
nano .env
```

## Шаг 3: Настройка переменных окружения

Заполните `.env` файл:

```bash
# Telegram Bot Token от @BotFather
BOT_TOKEN=123456:ABC-DEF...

# PostgreSQL (можно оставить по умолчанию)
POSTGRES_USER=botuser
POSTGRES_PASSWORD=СИЛЬНЫЙ_ПАРОЛЬ_ЗДЕСЬ
POSTGRES_DB=telegram_bot

# OpenAI API Key
OPENAI_API_KEY=sk-...

# Webhook URL (ваш домен с HTTPS)
WEBHOOK_URL=https://your-domain.com

# Начальный баланс (7 токенов = 1 High или несколько Medium)
INITIAL_TOKENS=7

# Админы (ваш Telegram ID, узнать: @userinfobot)
ADMIN_IDS=123456789

# Поддержка
SUPPORT_USERNAME=@your_support

# Подписка (опционально)
SUBSCRIPTION_CHANNEL=@nkonshin_ai
SUBSCRIPTION_REQUIRED=true

# Видео-приветствие (получите file_id отправив видео-кружок боту как админ)
WELCOME_VIDEO_FILE_ID=
```

**Важно:** После изменения портов в docker-compose.yml нужно выполнить `docker-compose down` перед `up` для пересоздания сети.

## Шаг 4: Настройка SSL (nginx + certbot)

### Установка nginx

```bash
sudo apt install nginx certbot python3-certbot-nginx -y
```

### Конфигурация nginx

Создайте файл `/etc/nginx/sites-available/telegram-bot`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Активируйте конфигурацию:

```bash
sudo ln -s /etc/nginx/sites-available/telegram-bot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Получение SSL сертификата

```bash
sudo certbot --nginx -d your-domain.com
```

## Шаг 5: Запуск приложения

```bash
# Запустите все сервисы
docker-compose up -d

# Проверьте логи
docker-compose logs -f

# Проверьте статус
docker-compose ps
```

## Шаг 6: Проверка работоспособности

```bash
# Проверьте health endpoint
curl https://your-domain.com/health

# Проверьте логи приложения
docker-compose logs -f app

# Проверьте логи worker
docker-compose logs -f worker
```

## Мониторинг

### Просмотр логов

```bash
# Все логи
docker-compose logs -f

# Только приложение
docker-compose logs -f app

# Только worker
docker-compose logs -f worker

# Последние 100 строк
docker-compose logs --tail=100
```

### Проверка ресурсов

```bash
# Использование ресурсов контейнерами
docker stats

# Использование диска
docker system df
```

## Обновление

```bash
# Остановите сервисы
docker-compose down

# Получите последние изменения
git pull

# Пересоберите образы
docker-compose build --no-cache

# Примените миграции БД (если есть новые)
docker-compose run --rm app alembic upgrade head

# Запустите сервисы
docker-compose up -d

# Проверьте логи
docker-compose logs -f
```

**Важно:** Если изменились порты в docker-compose.yml, используйте `docker-compose down` перед `up` для пересоздания сети.

## Резервное копирование

### Backup базы данных

```bash
# Создайте backup
docker-compose exec postgres pg_dump -U botuser telegram_bot > backup_$(date +%Y%m%d_%H%M%S).sql

# Восстановление из backup
docker-compose exec -T postgres psql -U botuser telegram_bot < backup_20231225_120000.sql
```

### Автоматический backup (cron)

Создайте скрипт `/home/user/backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/home/user/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR
cd /home/user/NanoBananaTgBot

docker-compose exec -T postgres pg_dump -U botuser telegram_bot > $BACKUP_DIR/backup_$DATE.sql

# Удалить backups старше 7 дней
find $BACKUP_DIR -name "backup_*.sql" -mtime +7 -delete
```

Добавьте в crontab:

```bash
crontab -e

# Backup каждый день в 3:00
0 3 * * * /home/user/backup.sh
```

## Troubleshooting

### Контейнеры не запускаются

```bash
# Проверьте логи
docker-compose logs

# Проверьте конфигурацию
docker-compose config

# Пересоздайте контейнеры
docker-compose down
docker-compose up -d
```

### База данных не доступна

```bash
# Проверьте статус PostgreSQL
docker-compose ps postgres

# Проверьте логи PostgreSQL
docker-compose logs postgres

# Перезапустите PostgreSQL
docker-compose restart postgres
```

### Worker не обрабатывает задачи

```bash
# Проверьте логи worker
docker-compose logs worker

# Проверьте Redis
docker-compose exec redis redis-cli ping

# Перезапустите worker
docker-compose restart worker
```

## Безопасность

1. **Используйте сильные пароли** для PostgreSQL
2. **Ограничьте доступ** к портам (только 80, 443)
3. **Закройте порты БД** — в docker-compose.yml порты PostgreSQL и Redis привязаны к 127.0.0.1
4. **Регулярно обновляйте** систему и Docker образы
5. **Настройте firewall** (ufw или iptables)
6. **Мониторьте логи** на подозрительную активность
7. **Защитите админ API** — используйте сильный `ADMIN_API_KEY`

```bash
# Настройка firewall
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### Защита от brute-force атак

В `docker-compose.yml` порты БД закрыты от внешнего доступа:

```yaml
postgres:
  ports:
    - "127.0.0.1:5432:5432"  # Только localhost

redis:
  ports:
    - "127.0.0.1:6379:6379"  # Только localhost
```

Это предотвращает внешние атаки на PostgreSQL и Redis. Контейнеры общаются через внутреннюю сеть Docker.

## Масштабирование

### Увеличение количества workers

Отредактируйте `docker-compose.yml`:

```yaml
worker:
  # ... существующая конфигурация
  deploy:
    replicas: 3  # Запустить 3 worker'а
```

Или запустите дополнительные workers вручную:

```bash
docker-compose up -d --scale worker=3
```

## Поддержка

При возникновении проблем:
1. Проверьте логи: `docker-compose logs -f`
2. Проверьте статус: `docker-compose ps`
3. Проверьте конфигурацию: `docker-compose config`
