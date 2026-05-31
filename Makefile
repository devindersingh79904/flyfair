.PHONY: help install test eval lint typecheck frontend-build docker-up docker-down clean

BACKEND_DIR := backend
FRONTEND_DIR := frontend
VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

##@ Help
help: ## Show this help message
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Setup
install: ## Install backend and frontend dependencies
	@echo "→ Installing backend dependencies..."
	cd $(BACKEND_DIR) && python3 -m venv .venv && $(PIP) install -r requirements.txt
	@echo "→ Installing frontend dependencies..."
	cd $(FRONTEND_DIR) && npm install

##@ Development
dev-backend: ## Start FastAPI backend in dev mode (hot-reload)
	cd $(BACKEND_DIR) && $(PYTHON) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## Start Vite frontend dev server
	cd $(FRONTEND_DIR) && npm run dev

##@ Testing
test: ## Run backend unit tests with pytest
	cd $(BACKEND_DIR) && $(PYTHON) -m pytest tests/ -v --tb=short

eval: ## Run all 25 airport search evaluation cases
	cd $(BACKEND_DIR) && $(PYTHON) scripts/run_eval.py

##@ Quality
lint: ## Run ruff linter on backend
	cd $(BACKEND_DIR) && $(PYTHON) -m ruff check app/ tests/ || true

typecheck: ## Run mypy type checks on backend
	cd $(BACKEND_DIR) && $(PYTHON) -m mypy app/ --ignore-missing-imports || true

frontend-typecheck: ## Run TypeScript type check on frontend
	cd $(FRONTEND_DIR) && npm run build -- --noEmit 2>/dev/null || npx tsc --noEmit

##@ Build
frontend-build: ## Build frontend production bundle
	cd $(FRONTEND_DIR) && npm run build

##@ Docker
docker-up: ## Build and start all services via Docker Compose
	docker-compose up --build -d

docker-down: ## Stop and remove all Docker Compose services
	docker-compose down

docker-logs: ## Tail logs from all Docker services
	docker-compose logs -f

##@ Cleanup
clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf $(FRONTEND_DIR)/dist
	@echo "✓ Cleaned"

##@ Data
generate-data: ## Generate airport JSON from raw CSV
	cd $(BACKEND_DIR) && $(PYTHON) scripts/generate_airport_data.py

generate-multilingual-data: ## Generate multilingual aliases from GeoNames
	cd $(BACKEND_DIR) && $(PYTHON) scripts/generate_multilingual_aliases.py

##@ Deployment
zip: ## Package project for submission
	zip -r submission.zip . -x "*.bak" "*assignment*" "*backend/raw_data*" "*.git*" "*node_modules*" "*__pycache__*" "*.pytest_cache*" "*.venv*" "*venv*" "*dist*" "*build*" "*.env*" "*.DS_Store*" "*.idea*" "*.vscode*" "*backend/app/data/*.txt"
