.DEFAULT_GOAL := help

BACKEND_DIR := backend
FRONTEND_DIR := frontend
# Prevent any active venv in the shell from conflicting with uv's project venv
unexport VIRTUAL_ENV

.PHONY: help install install-backend install-frontend dev backend frontend build lint lint-backend lint-frontend test clean

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "  install           Install all backend and frontend dependencies"
	@echo "  install-backend   Install Python dependencies"
	@echo "  install-frontend  Install Node dependencies"
	@echo "  dev               Start both backend and frontend (foreground, Ctrl+C to stop both)"
	@echo "  backend           Start the FastAPI backend only  (http://localhost:8000)"
	@echo "  frontend          Start the Vite dev server only  (http://localhost:5173)"
	@echo "  build             Production build of the frontend"
	@echo "  lint              Lint both backend and frontend"
	@echo "  lint-backend      Run mypy type-checking on the backend"
	@echo "  lint-frontend     Run ESLint on the frontend"
	@echo "  test              Run the backend test suite"
	@echo "  clean             Remove frontend build artefacts and Python caches"

# ── Dependencies ─────────────────────────────────────────────────────────────

install: install-backend install-frontend

install-backend:
	cd $(BACKEND_DIR) && uv sync --dev

install-frontend:
	cd $(FRONTEND_DIR) && npm install

# ── Development ───────────────────────────────────────────────────────────────

dev:
	@echo "Starting backend on http://localhost:8000 and frontend on http://localhost:5173"
	@echo "Press Ctrl+C to stop both."
	@trap 'kill 0' INT; \
		cd $(BACKEND_DIR) && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 & \
		cd $(FRONTEND_DIR) && npm run dev -- --host 0.0.0.0; \
		wait

backend:
	cd $(BACKEND_DIR) && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd $(FRONTEND_DIR) && npm run dev -- --host 0.0.0.0

# Start services via Docker Compose (build + run in foreground)
.PHONY: docker-up docker-down
docker-up:
	@echo "Starting services with docker compose (foreground)"
	docker compose up --build

docker-down:
	@echo "Stopping and removing docker compose services"
	docker compose down

# ── Linting ───────────────────────────────────────────────────────────────────

lint: lint-backend lint-frontend

lint-backend:
	cd $(BACKEND_DIR) && uv run mypy app tests

lint-frontend:
	cd $(FRONTEND_DIR) && npm run lint

# ── Testing ───────────────────────────────────────────────────────────────────

test:
	cd $(BACKEND_DIR) && uv run pytest tests/ -v

# ── Production ────────────────────────────────────────────────────────────────

build:
	cd $(FRONTEND_DIR) && npm run build

# ── Cleanup ───────────────────────────────────────────────────────────────────

clean:
	rm -rf $(FRONTEND_DIR)/dist
	rm -rf $(BACKEND_DIR)/.venv
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
