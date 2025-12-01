# 📋 Commandes rapides - Agent Éditorial

Guide de référence rapide pour les commandes les plus utilisées.

## 🚀 Démarrage rapide

### Option 1: Makefile (recommandé)

```bash
# Voir toutes les commandes disponibles
make help

# Démarrage complet (tout en une commande)
make dev

# Ou étape par étape:
make docker-up      # Démarrer PostgreSQL, Qdrant, Ollama
make init-db        # Appliquer les migrations
make start          # Démarrer l'API FastAPI
```

### Option 2: Scripts shell

```bash
# Démarrer l'application (démarre Docker + DB + API)
./scripts/start.sh

# Redémarrer l'application
./scripts/restart.sh

# Arrêter l'application
./scripts/stop.sh
```

## 📦 Installation initiale

```bash
# Installation complète
make setup

# Ou manuellement:
make install        # Installer les dépendances Python
make docker-up      # Démarrer les services Docker
make init-db        # Initialiser la base de données
make init-qdrant    # Initialiser Qdrant
```

## 🔄 Gestion de l'application

```bash
# Démarrer l'API
make start

# Redémarrer l'API
make restart

# Arrêter l'API
make stop

# Voir le statut
make status
```

## 🐳 Gestion Docker

```bash
# Démarrer les services (PostgreSQL, Qdrant, Ollama)
make docker-up

# Arrêter les services
make docker-down

# Redémarrer les services
make docker-restart

# Voir les logs
make docker-logs

# Voir le statut
make docker-status
```

## 🗄️ Base de données

```bash
# Appliquer les migrations
make init-db

# Ou directement:
alembic upgrade head

# Créer une nouvelle migration
alembic revision --autogenerate -m "description"

# Voir l'état actuel
alembic current
```

## 🧪 Tests

```bash
# Lancer tous les tests
make test

# Tests avec couverture
make test-cov

# Ou directement:
pytest
pytest --cov=python_scripts --cov-report=html
```

## 🧹 Nettoyage

```bash
# Nettoyer les fichiers temporaires
make clean

# Réinitialiser tout (arrête Docker + nettoie)
make reset
```

## 📊 Commandes utiles

```bash
# Voir les logs de l'API
make logs

# Voir les logs Docker
make docker-logs

# Vérifier le statut de tout
make status
```

## 🔧 Commandes manuelles

Si vous préférez utiliser les commandes directement:

```bash
# Démarrer l'API
uvicorn python_scripts.api.main:app --reload --host 0.0.0.0 --port 8000

# Démarrer en production
uvicorn python_scripts.api.main:app --host 0.0.0.0 --port 8000 --workers 4

# Docker Compose
docker-compose -f docker/docker-compose.yml up -d
docker-compose -f docker/docker-compose.yml down
docker-compose -f docker/docker-compose.yml restart
docker-compose -f docker/docker-compose.yml logs -f
```

## 🌐 URLs importantes

Une fois l'application démarrée:

- **API**: http://localhost:8000
- **Documentation Swagger**: http://localhost:8000/docs
- **Documentation ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/api/v1/health
- **pgAdmin** (PostgreSQL): http://localhost:5050
  - Email: `admin@editorial.dev` (par défaut)
  - Password: `admin` (par défaut)
- **Qdrant Dashboard**: http://localhost:6333/dashboard
- **Ollama API**: http://localhost:11435
  - **Configuration GPU** : Voir [docs/gpu-setup.md](../docs/gpu-setup.md) pour activer l'accélération GPU

## 💡 Astuces

1. **Mode développement**: Utilisez `make dev` pour tout démarrer d'un coup
2. **Redémarrage rapide**: `make restart` redémarre uniquement l'API (plus rapide)
3. **Logs en temps réel**: `make docker-logs` pour suivre les services Docker
4. **Vérification**: `make status` pour voir l'état de tous les services

