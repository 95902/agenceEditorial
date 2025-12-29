#!/bin/bash

# Script de démarrage de l'application Agent Éditorial

set -e

# Couleurs pour les messages
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
PORT=8000
HOST=0.0.0.0
DOCKER_COMPOSE_FILE="docker/docker-compose.yml"

echo -e "${BLUE}🚀 Démarrage de l'application Agent Éditorial${NC}"
echo ""

# Vérifier si Docker est en cours d'exécution
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker n'est pas en cours d'exécution${NC}"
    exit 1
fi

# Démarrer les services Docker
echo -e "${YELLOW}🐳 Démarrage des services Docker...${NC}"
docker-compose -f "$DOCKER_COMPOSE_FILE" up -d

# Attendre que les services soient prêts
echo -e "${YELLOW}⏳ Attente du démarrage des services...${NC}"
sleep 5

# Vérifier la base de données
echo -e "${YELLOW}🗄️  Vérification de la base de données...${NC}"
if ! alembic current > /dev/null 2>&1; then
    echo -e "${YELLOW}📦 Initialisation de la base de données...${NC}"
    if command -v alembic > /dev/null 2>&1; then
        alembic upgrade head
    elif [ -f ".venv/bin/alembic" ]; then
        .venv/bin/alembic upgrade head
    elif command -v uv > /dev/null 2>&1; then
        uv run alembic upgrade head
    fi
fi

# Vérifier Playwright
echo -e "${YELLOW}🎭 Vérification de Playwright...${NC}"
if [ ! -d "$HOME/.cache/ms-playwright/chromium-1194" ] && [ ! -d "$HOME/.cache/ms-playwright" ]; then
    echo -e "${YELLOW}⚠️  Playwright/Chromium non installé. Installation en cours...${NC}"
    if command -v playwright > /dev/null 2>&1; then
        playwright install chromium
    elif [ -f ".venv/bin/playwright" ]; then
        .venv/bin/playwright install chromium
    elif command -v uv > /dev/null 2>&1; then
        uv run playwright install chromium
    else
        echo -e "${RED}❌ Impossible d'installer Playwright. Exécutez: make install-playwright${NC}"
    fi
fi

# Démarrer l'API
echo -e "${GREEN}🚀 Démarrage de l'API FastAPI...${NC}"
echo -e "${BLUE}📍 API disponible sur: http://${HOST}:${PORT}${NC}"
echo -e "${BLUE}📚 Documentation: http://${HOST}:${PORT}/docs${NC}"
echo ""

# Utiliser uv run si disponible, sinon utiliser le venv
if command -v uv > /dev/null 2>&1; then
    uv run uvicorn python_scripts.api.main:app --reload --host "$HOST" --port "$PORT"
elif [ -f ".venv/bin/uvicorn" ]; then
    .venv/bin/uvicorn python_scripts.api.main:app --reload --host "$HOST" --port "$PORT"
else
    echo -e "${RED}❌ uvicorn non trouvé. Installez les dépendances avec: make install${NC}"
    exit 1
fi

