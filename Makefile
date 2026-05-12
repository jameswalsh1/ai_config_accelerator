.DEFAULT_GOAL := help

BACKEND_DIR := backend
FRONTEND_DIR := frontend
# Prevent any active venv in the shell from conflicting with uv's project venv
unexport VIRTUAL_ENV

.PHONY: help install install-backend install-frontend dev backend frontend build lint lint-backend lint-frontend typecheck-frontend mypy test clean check-ts-deprecations fix-ts-deprecations db-import db-import-dry-run db-readiness verify-phase2

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
	@echo "  typecheck-frontend  Run tsc type-checking on the frontend (mypy equivalent)"
	@echo "  mypy              Run mypy type-checking on the backend (alias for lint-backend)"
	@echo "  test              Run the backend test suite"
	@echo "  clean             Remove frontend build artefacts and Python caches"
	@echo "  check-ts-deprecations  Report deprecated baseUrl usage in tsconfig files"
	@echo "  fix-ts-deprecations    Remove deprecated baseUrl (when paths is set) and verify"
	@echo "  db-upgrade        Apply all pending Alembic migrations (requires DB)"
	@echo "  db-downgrade      Roll back one Alembic migration step (requires DB)"
	@echo "  db-revision       Create a new Alembic revision (pass message= arg)"

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

mypy: lint-backend

lint-frontend:
	cd $(FRONTEND_DIR) && npm run lint

typecheck-frontend:
	cd $(FRONTEND_DIR) && npm run typecheck

# ── Testing ───────────────────────────────────────────────────────────────────

test:
	cd $(BACKEND_DIR) && uv run pytest tests/ -v

# ── Database import (Phase 2) ─────────────────────────────────────────────────
.PHONY: db-import db-import-dry-run db-readiness verify-phase2

db-import:
	@echo "Importing JSON wizard configs into the database..."
	cd $(BACKEND_DIR) && uv run python -m app.commands.import_json_to_db

db-import-dry-run:
	@echo "Dry-run: computing changes without writing to the database..."
	cd $(BACKEND_DIR) && uv run python -m app.commands.import_json_to_db --dry-run

db-readiness:
	@echo "Checking database import status..."
	@curl -s http://localhost:8000/health/config-db | python3 -m json.tool || echo "(server not running)"

verify-phase2:
	@echo "Running Phase 2 verification tests..."
	cd $(BACKEND_DIR) && uv run pytest tests/test_phase2_models.py tests/test_config_db_serialiser.py tests/test_import_services.py tests/test_db_repository.py tests/test_db_parity.py tests/test_phase2_feature_flag.py -v


.PHONY: db-upgrade db-downgrade db-revision

db-upgrade:
	@echo "Applying all pending Alembic migrations..."
	cd $(BACKEND_DIR) && uv run alembic upgrade head

db-downgrade:
	@echo "Rolling back one Alembic migration step..."
	cd $(BACKEND_DIR) && uv run alembic downgrade -1

db-revision:
	@echo "Creating new Alembic revision: $(message)"
	cd $(BACKEND_DIR) && uv run alembic revision --autogenerate -m "$(message)"

# ── TypeScript deprecation helpers ───────────────────────────────────────────

TS_CONFIGS := $(shell find $(FRONTEND_DIR) -name "tsconfig*.json" -not -path "*/node_modules/*")

# Scan tsconfig files and exit non-zero if deprecated baseUrl+paths pattern found
check-ts-deprecations:
	@echo "Scanning for deprecated TypeScript configuration..."
	@node -e "\
var fs=require('fs');\
var files=process.argv.slice(1);\
var found=false;\
files.forEach(function(f){\
  var raw=fs.readFileSync(f,'utf8').replace(/\/\/[^\n]*/g,'').replace(/\/\*[\s\S]*?\*\//g,'');\
  var cfg;try{cfg=JSON.parse(raw);}catch(e){return;}\
  if(cfg.compilerOptions&&cfg.compilerOptions.baseUrl!==undefined&&cfg.compilerOptions.paths){\
    console.log('  DEPRECATED: '+f+': baseUrl is redundant when paths is set (TS 4.1+)');\
    found=true;\
  }\
});\
if(!found)console.log('  No deprecated baseUrl usage found.');\
process.exit(found?1:0);" $(TS_CONFIGS)

# Remove deprecated baseUrl when paths is already configured, then run frontend tests
fix-ts-deprecations:
	@echo "Removing deprecated baseUrl from TypeScript configs..."
	@node -e "\
var fs=require('fs');\
var files=process.argv.slice(1);\
var fixed=0;\
files.forEach(function(f){\
  var content=fs.readFileSync(f,'utf8');\
  var raw=content.replace(/\/\/[^\n]*/g,'').replace(/\/\*[\s\S]*?\*\//g,'');\
  var cfg;try{cfg=JSON.parse(raw);}catch(e){return;}\
  if(cfg.compilerOptions&&cfg.compilerOptions.baseUrl!==undefined&&cfg.compilerOptions.paths){\
    var updated=content.replace(/^[ \t]*\"baseUrl\"\s*:\s*\"[^\"]*\",?\r?\n/m,'');\
    fs.writeFileSync(f,updated);\
    console.log('  Fixed: removed baseUrl from '+f);\
    fixed++;\
  }\
});\
console.log(fixed>0?'Done. '+fixed+' file(s) updated.':'Nothing to fix.');" $(TS_CONFIGS)
	@echo "Running frontend tests to verify..."
	cd $(FRONTEND_DIR) && npm run test

# ── Production ────────────────────────────────────────────────────────────────

build:
	cd $(FRONTEND_DIR) && npm run build

# ── Cleanup ───────────────────────────────────────────────────────────────────

clean:
	rm -rf $(FRONTEND_DIR)/dist
	rm -rf $(BACKEND_DIR)/.venv
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
