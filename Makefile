.PHONY: dev dev-build down logs test test-unit test-integration coverage e2e lint format typecheck migrate ci clean clear-cache clear-memories stats memory-stats cache-stats db-shell redis-shell test-file quality

# =============================================================================
# YG Starter - Development Commands
# =============================================================================

# -----------------------------------------------------------------------------
# Development
# -----------------------------------------------------------------------------

dev:
	docker compose up

dev-build:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f backend

logs-frontend:
	docker compose logs -f frontend

# -----------------------------------------------------------------------------
# Testing
# -----------------------------------------------------------------------------

test:
	cd backend && uv run pytest
	cd frontend && npm test

test-unit:
	cd backend && uv run pytest tests/unit -v

test-integration:
	docker compose -f docker-compose.test.yml up -d
	cd backend && uv run pytest tests/integration -v
	docker compose -f docker-compose.test.yml down

coverage:
	cd backend && uv run pytest --cov=app --cov-report=html
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
	cp .env.example .env
	cd backend && uv sync
	cd frontend && npm install
	@echo "Setup complete! Run 'make dev' to start."

# -----------------------------------------------------------------------------
# CI Pipeline
# -----------------------------------------------------------------------------

ci: lint format-check typecheck test coverage

# -----------------------------------------------------------------------------
# Cleanup
# -----------------------------------------------------------------------------

clean:
	docker compose down -v
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
	docker compose exec redis redis-cli KEYS "embed:*" | xargs -r docker compose exec redis redis-cli DEL
	docker compose exec redis redis-cli KEYS "artifact:*" | xargs -r docker compose exec redis redis-cli DEL
	@echo "Cache cleared!"

## Clear all memories from database
clear-memories:
	@echo "Clearing all memories..."
	docker compose exec backend uv run python -c "\
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
	docker compose exec postgres psql -U postgres -d yg_starter

## Open Redis shell
redis-shell:
	docker compose exec redis redis-cli

## Run a single test file
test-file:
	cd backend && uv run pytest $(FILE) -v

## Check all code quality
quality:
	cd backend && uv run ruff format --check app/ tests/
	cd backend && uv run ruff check app/ tests/
	cd backend && uv run pytest tests/ -q
