.PHONY: help dev dev-build down logs test test-unit test-integration coverage e2e lint format typecheck migrate ci clean clear-cache clear-memories stats memory-stats cache-stats db-shell redis-shell test-file quality

# =============================================================================
# YG Starter - Development Commands
# =============================================================================

# -----------------------------------------------------------------------------
# Help
# -----------------------------------------------------------------------------

help:
	@echo ""
	@echo "  YG Starter - Available Commands"
	@echo "  ================================"
	@echo ""
	@echo "  Development:"
	@echo "    make dev          Start all services with hot reload"
	@echo "    make dev-build    Rebuild and start all services"
	@echo "    make down         Stop all services"
	@echo "    make logs         Follow all service logs"
	@echo ""
	@echo "  Testing:"
	@echo "    make test         Run all tests (backend + frontend)"
	@echo "    make test-unit    Run backend unit tests only"
	@echo "    make coverage     Generate test coverage report"
	@echo ""
	@echo "  Code Quality:"
	@echo "    make lint         Check code style (ruff + biome)"
	@echo "    make format       Auto-format code"
	@echo "    make typecheck    Run type checking (ty + tsc)"
	@echo "    make quality      Run all quality checks"
	@echo ""
	@echo "  Database:"
	@echo "    make migrate      Run database migrations"
	@echo "    make db-shell     Open PostgreSQL shell"
	@echo "    make redis-shell  Open Redis shell"
	@echo ""
	@echo "  Admin:"
	@echo "    make stats        View usage statistics"
	@echo "    make clear-cache  Clear Redis cache"
	@echo "    make clean        Remove all containers and artifacts"
	@echo ""
	@echo "  Setup:"
	@echo "    make setup        Initial project setup"
	@echo ""
	@echo "  See README.md for detailed documentation."
	@echo ""

# -----------------------------------------------------------------------------
# Development
# -----------------------------------------------------------------------------

dev:
	docker compose --env-file backend/.env up

dev-build:
	docker compose --env-file backend/.env up --build

down:
	docker compose --env-file backend/.env down

logs:
	docker compose --env-file backend/.env logs -f

logs-backend:
	docker compose --env-file backend/.env logs -f backend

logs-frontend:
	docker compose --env-file backend/.env logs -f frontend

# -----------------------------------------------------------------------------
# Testing
# -----------------------------------------------------------------------------

test:
	cd backend && uv run pytest
	cd frontend && npm test

test-unit:
	cd backend && uv run pytest tests/unit -m unit -v

test-unit-fast:
	cd backend && uv run pytest tests/unit -m "unit and not slow" -q

test-integration:
	docker compose --env-file backend/.env -f docker-compose.test.yml up -d
	cd backend && uv run pytest tests/integration -m integration -v
	docker compose --env-file backend/.env -f docker-compose.test.yml down

test-all:
	cd backend && uv run pytest tests/ -v
	cd frontend && npm test

coverage:
	cd backend && uv run pytest tests/unit -m unit --cov=app --cov-report=html --cov-report=term-missing
	@echo "Coverage report: backend/htmlcov/index.html"

coverage-all:
	cd backend && uv run pytest tests/ --cov=app --cov-report=html --cov-report=json
	@echo "Coverage report: backend/htmlcov/index.html"

e2e:
	cd frontend && npx playwright test

# -----------------------------------------------------------------------------
# Code Quality
# -----------------------------------------------------------------------------

lint:
	cd backend && uv run ruff check .
	cd frontend && npm run lint

lint-fix:
	cd backend && uv run ruff check --fix .
	cd frontend && npm run lint:fix

format:
	cd backend && uv run ruff format .
	cd frontend && npm run format

format-check:
	cd backend && uv run ruff format --check .
	cd frontend && npm run format:check

typecheck:
	cd backend && uv run ty check
	cd frontend && npm run typecheck

# -----------------------------------------------------------------------------
# Database
# -----------------------------------------------------------------------------

migrate:
	cd backend && uv run alembic upgrade head

migrate-create:
	cd backend && uv run alembic revision --autogenerate -m "$(name)"

migrate-down:
	cd backend && uv run alembic downgrade -1

# -----------------------------------------------------------------------------
# Setup
# -----------------------------------------------------------------------------

setup:
	cp backend/.env.example backend/.env
	cd backend && uv sync
	cd frontend && npm install
	@echo "Setup complete! Edit backend/.env with your API keys, then run 'make dev' to start."

# -----------------------------------------------------------------------------
# CI Pipeline
# -----------------------------------------------------------------------------

ci: lint format-check typecheck test coverage

# -----------------------------------------------------------------------------
# Cleanup
# -----------------------------------------------------------------------------

clean:
	docker compose --env-file backend/.env down -v
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name node_modules -exec rm -rf {} +
	find . -type d -name dist -exec rm -rf {} +

# =============================================================================
# Admin & Maintenance Commands
# =============================================================================

## Clear Redis cache (embeddings, artifacts)
clear-cache:
	@echo "Clearing Redis cache..."
	docker compose --env-file backend/.env exec redis redis-cli KEYS "embed:*" | xargs -r docker compose --env-file backend/.env exec redis redis-cli DEL
	docker compose --env-file backend/.env exec redis redis-cli KEYS "artifact:*" | xargs -r docker compose --env-file backend/.env exec redis redis-cli DEL
	@echo "Cache cleared!"

## Clear all memories from database
clear-memories:
	@echo "Clearing all memories..."
	docker compose --env-file backend/.env exec backend uv run python -c "\
from app.db.session import engine;\
from sqlalchemy import text;\
import asyncio;\
async def clear():\
    async with engine.begin() as conn:\
        await conn.execute(text('TRUNCATE agent_memories CASCADE'));\
        print('Memories cleared!');\
asyncio.run(clear())\
"

## Show usage statistics
stats:
	@curl -s http://localhost:8600/api/v1/admin/stats -H "X-Admin-Key: dev-admin-key" | python -m json.tool

## Show memory statistics
memory-stats:
	@curl -s http://localhost:8600/api/v1/admin/memories/stats -H "X-Admin-Key: dev-admin-key" | python -m json.tool

## Show cache statistics
cache-stats:
	@curl -s http://localhost:8600/api/v1/admin/cache/stats -H "X-Admin-Key: dev-admin-key" | python -m json.tool

## Open PostgreSQL shell
db-shell:
	docker compose --env-file backend/.env exec postgres psql -U postgres -d yg_starter

## Open Redis shell
redis-shell:
	docker compose --env-file backend/.env exec redis redis-cli

## Run a single test file
test-file:
	cd backend && uv run pytest $(FILE) -v

## Check all code quality
quality:
	cd backend && uv run ruff format --check app/ tests/
	cd backend && uv run ruff check app/ tests/
	cd backend && uv run pytest tests/ -q
