.PHONY: help build up down restart logs shell test clean migrate deploy

help: ## Показать эту справку
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# === Быстрый деплой ===

deploy: ## 🚀 Быстрый деплой без пересборки (5-10 сек)
	@echo "🚀 Быстрый деплой..."
	@git pull
	@docker-compose restart app worker
	@echo "✅ Деплой завершён!"

deploy-migrate: ## 🚀 Быстрый деплой с миграциями
	@echo "🚀 Деплой с миграциями..."
	@git pull
	@docker-compose exec app alembic upgrade head
	@docker-compose restart app worker
	@echo "✅ Деплой завершён!"

# === Основные команды ===

build: ## Собрать Docker образы
	docker-compose build

up: ## Запустить все сервисы
	docker-compose up -d

down: ## Остановить все сервисы
	docker-compose down

restart: ## Перезапустить все сервисы
	docker-compose restart

restart-app: ## Перезапустить только app
	docker-compose restart app

restart-worker: ## Перезапустить только worker
	docker-compose restart worker

logs: ## Показать логи всех сервисов
	docker-compose logs -f

logs-app: ## Показать логи FastAPI приложения
	docker-compose logs -f app

logs-worker: ## Показать логи RQ Worker
	docker-compose logs -f worker

shell: ## Открыть shell в контейнере приложения
	docker-compose exec app bash

shell-db: ## Открыть psql в контейнере БД
	docker-compose exec postgres psql -U botuser -d telegram_bot

test: ## Запустить тесты
	pytest -v

test-local: ## Запустить тесты локально (без Docker)
	python -m pytest -v

migrate: ## Применить миграции БД
	docker-compose exec app alembic upgrade head

migrate-create: ## Создать новую миграцию (использование: make migrate-create MSG="описание")
	docker-compose exec app alembic revision --autogenerate -m "$(MSG)"

clean: ## Остановить и удалить контейнеры, сети, volumes
	docker-compose down -v

ps: ## Показать статус сервисов
	docker-compose ps

rebuild: ## Пересобрать образы без кэша (только при изменении requirements.txt)
	docker-compose down
	docker-compose build --no-cache
	docker-compose up -d

dev: ## Запустить в режиме разработки (с hot-reload)
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

prod: up ## Запустить в production режиме

stop: down ## Остановить сервисы (алиас для down)
