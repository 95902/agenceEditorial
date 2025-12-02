#!/bin/bash

# Script d'arrêt de l'application Agent Éditorial

set -e

# Couleurs pour les messages
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
DOCKER_COMPOSE_FILE="docker/docker-compose.yml"

echo -e "${YELLOW}🛑 Arrêt de l'application Agent Éditorial${NC}"
echo ""

# Arrêter l'API
echo -e "${YELLOW}🛑 Arrêt de l'API...${NC}"
if pkill -f "uvicorn python_scripts.api.main:app\|uv run uvicorn" 2>/dev/null; then
    echo -e "${GREEN}✅ API arrêtée${NC}"
else
    echo -e "${YELLOW}⚠️  Aucun processus API trouvé${NC}"
fi

# Arrêter les services Docker (optionnel - décommenter si nécessaire)
# echo -e "${YELLOW}🐳 Arrêt des services Docker...${NC}"
# docker-compose -f "$DOCKER_COMPOSE_FILE" down
# echo -e "${GREEN}✅ Services Docker arrêtés${NC}"

echo -e "${GREEN}✅ Application arrêtée${NC}"

