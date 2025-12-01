#!/bin/bash

# Script de redémarrage de l'application Agent Éditorial

set -e

# Couleurs pour les messages
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
PORT=8000
DOCKER_COMPOSE_FILE="docker/docker-compose.yml"

echo -e "${BLUE}🔄 Redémarrage de l'application Agent Éditorial${NC}"
echo ""

# Arrêter l'API si elle est en cours d'exécution
echo -e "${YELLOW}🛑 Arrêt de l'API...${NC}"
pkill -f "uvicorn python_scripts.api.main:app" 2>/dev/null && echo -e "${GREEN}✅ API arrêtée${NC}" || echo -e "${YELLOW}⚠️  Aucun processus API trouvé${NC}"

# Attendre un peu
sleep 2

# Redémarrer les services Docker
echo -e "${YELLOW}🔄 Redémarrage des services Docker...${NC}"
docker-compose -f "$DOCKER_COMPOSE_FILE" restart

# Attendre que les services soient prêts
echo -e "${YELLOW}⏳ Attente du redémarrage des services...${NC}"
sleep 5

# Redémarrer l'API
echo -e "${GREEN}🚀 Redémarrage de l'API FastAPI...${NC}"
echo -e "${BLUE}📍 API disponible sur: http://0.0.0.0:${PORT}${NC}"
echo -e "${BLUE}📚 Documentation: http://0.0.0.0:${PORT}/docs${NC}"
echo ""

# Utiliser uv run si disponible, sinon utiliser le venv
if command -v uv > /dev/null 2>&1; then
    uv run uvicorn python_scripts.api.main:app --reload --host 0.0.0.0 --port "$PORT"
elif [ -f ".venv/bin/uvicorn" ]; then
    .venv/bin/uvicorn python_scripts.api.main:app --reload --host 0.0.0.0 --port "$PORT"
else
    echo -e "${RED}❌ uvicorn non trouvé. Installez les dépendances avec: make install${NC}"
    exit 1
fi

