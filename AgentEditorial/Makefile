.PHONY: help start stop restart status logs dev test clean install install-deps install-playwright check-deps docker-up docker-down docker-restart

# Variables
# Utilise 'docker compose' (V2) - fallback automatique vers 'docker-compose' si nécessaire
DOCKER_COMPOSE = docker compose -f docker/docker-compose.yml
PYTHON = python
UV = uv
UVICORN = $(UV) run uvicorn python_scripts.api.main:app
PORT = 8000
HOST = 0.0.0.0
VENV_BIN = .venv/bin

help: ## Affiche cette aide
	@echo "Commandes disponibles:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Installe les dépendances
	@echo "📦 Installation des dépendances..."
	uv pip install -e ".[dev]"
	@echo "🎭 Installation de Playwright..."
	@if command -v playwright > /dev/null 2>&1; then \
		playwright install chromium; \
	elif [ -f "$(VENV_BIN)/playwright" ]; then \
		$(VENV_BIN)/playwright install chromium; \
	else \
		$(UV) run playwright install chromium; \
	fi
	@echo "✅ Installation terminée"

install-deps: ## Installe uniquement les dépendances (sans dev)
	@echo "📦 Installation des dépendances..."
	uv pip install -e .
	@echo "🎭 Installation de Playwright..."
	@if command -v playwright > /dev/null 2>&1; then \
		playwright install chromium; \
	elif [ -f "$(VENV_BIN)/playwright" ]; then \
		$(VENV_BIN)/playwright install chromium; \
	else \
		$(UV) run playwright install chromium; \
	fi
	@echo "✅ Installation terminée"

install-playwright: ## Installe uniquement Playwright/Chromium
	@echo "🎭 Installation de Playwright/Chromium..."
	@if command -v playwright > /dev/null 2>&1; then \
		playwright install chromium; \
	elif [ -f "$(VENV_BIN)/playwright" ]; then \
		$(VENV_BIN)/playwright install chromium; \
	else \
		$(UV) run playwright install chromium; \
	fi
	@echo "✅ Playwright installé"

docker-up: ## Démarre les services Docker (PostgreSQL, Qdrant, Ollama)
	@echo "🐳 Démarrage des services Docker..."
	$(DOCKER_COMPOSE) up -d
	@echo "⏳ Attente du démarrage des services..."
	@sleep 5
	@echo "✅ Services Docker démarrés"

docker-down: ## Arrête les services Docker
	@echo "🐳 Arrêt des services Docker..."
	$(DOCKER_COMPOSE) down
	@echo "✅ Services Docker arrêtés"

docker-restart: ## Redémarre les services Docker
	@echo "🔄 Redémarrage des services Docker..."
	$(DOCKER_COMPOSE) restart
	@echo "✅ Services Docker redémarrés"

docker-logs: ## Affiche les logs des services Docker
	$(DOCKER_COMPOSE) logs -f

docker-status: ## Affiche le statut des services Docker
	$(DOCKER_COMPOSE) ps

init-db: ## Initialise la base de données (migrations)
	@echo "🗄️  Initialisation de la base de données..."
	@if [ -f "$(VENV_BIN)/alembic" ]; then \
		$(VENV_BIN)/alembic upgrade head; \
	else \
		$(UV) run alembic upgrade head; \
	fi
	@echo "✅ Base de données initialisée"

init-qdrant: ## Initialise la collection Qdrant
	@echo "🔍 Initialisation de Qdrant..."
	@if [ -f "$(VENV_BIN)/python" ]; then \
		$(VENV_BIN)/python scripts/init_qdrant.py; \
	else \
		$(UV) run python scripts/init_qdrant.py; \
	fi
	@echo "✅ Qdrant initialisé"

check-deps: ## Vérifie et installe les dépendances manquantes
	@echo "🔍 Vérification des dépendances..."
	@uv pip install -e . --quiet || echo "⚠️  Certaines dépendances peuvent être manquantes"
	@echo "🎭 Vérification de Playwright..."
	@if ! command -v playwright > /dev/null 2>&1 && [ ! -f "$(VENV_BIN)/playwright" ]; then \
		echo "⚠️  Playwright non trouvé. Exécutez: make install-playwright"; \
	fi
	@echo "✅ Vérification terminée"

start: check-deps ## Démarre l'API FastAPI
	@echo "🚀 Démarrage de l'API..."
	$(UVICORN) --reload --host $(HOST) --port $(PORT)

start-prod: ## Démarre l'API en mode production
	@echo "🚀 Démarrage de l'API (production)..."
	$(UVICORN) --host $(HOST) --port $(PORT) --workers 4

stop: ## Arrête l'API (trouve et tue le processus)
	@echo "🛑 Arrêt de l'API..."
	@pkill -f "uvicorn python_scripts.api.main:app" || echo "Aucun processus trouvé"
	@pkill -f "uv run uvicorn" || true

restart: stop start ## Redémarre l'API (arrête puis démarre)

status: ## Affiche le statut de l'application
	@echo "📊 Statut de l'application:"
	@echo ""
	@echo "Services Docker:"
	@$(DOCKER_COMPOSE) ps
	@echo ""
	@echo "Processus API:"
	@pgrep -f "uvicorn python_scripts.api.main:app\|uv run uvicorn" > /dev/null && echo "✅ API en cours d'exécution" || echo "❌ API arrêtée"
	@echo ""
	@echo "Port $(PORT):"
	@lsof -i :$(PORT) > /dev/null 2>&1 && echo "✅ Port $(PORT) utilisé" || echo "❌ Port $(PORT) libre"

logs: ## Affiche les logs de l'API (si en arrière-plan)
	@tail -f logs/app.log 2>/dev/null || echo "Aucun fichier de log trouvé"

dev: docker-up init-db start ## Mode développement complet (Docker + DB + API)

test: ## Lance les tests
	@echo "🧪 Exécution des tests..."
	@if [ -f "$(VENV_BIN)/pytest" ]; then \
		$(VENV_BIN)/pytest; \
	else \
		$(UV) run pytest; \
	fi

test-cov: ## Lance les tests avec couverture
	@echo "🧪 Exécution des tests avec couverture..."
	@if [ -f "$(VENV_BIN)/pytest" ]; then \
		$(VENV_BIN)/pytest --cov=python_scripts --cov-report=html --cov-report=term; \
	else \
		$(UV) run pytest --cov=python_scripts --cov-report=html --cov-report=term; \
	fi

clean: ## Nettoie les fichiers temporaires
	@echo "🧹 Nettoyage..."
	find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -r {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov 2>/dev/null || true
	@echo "✅ Nettoyage terminé"

setup: install docker-up init-db init-qdrant ## Configuration complète (install + Docker + DB + Qdrant)

reset: docker-down clean ## Réinitialise tout (arrête Docker + nettoie)

# Commandes Makefile disponibles
# make help — Affiche toutes les commandes
# make dev — Démarrage complet (Docker + DB + API)
# make start — Démarre l'API
# make restart — Redémarre l'API
# make stop — Arrête l'API
# make status — Affiche le statut
# make docker-up — Démarre les services Docker
# make docker-down — Arrête les services Docker
# make docker-restart — Redémarre les services Docker
# make docker-logs — Affiche les logs Docker
# make test — Lance les tests
# make clean — Nettoie les fichiers temporaires
# Option 1: Avec vérification automatique des dépendances
# make start

# # Option 2: Installer toutes les dépendances d'abord
# make install
# make start

# # Option 3: Vérifier manuellement
# make check-deps
# make start