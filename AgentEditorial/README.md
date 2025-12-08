# Agent Éditorial & Concurrentiel

Système multi-agents d'analyse éditoriale et concurrentielle utilisant l'IA pour automatiser l'analyse du style éditorial de sites web, identifier automatiquement les concurrents, scraper leurs articles, et détecter les tendances thématiques avec BERTopic.

## 🎯 Vue d'ensemble

Ce système permet de :

- **Analyser automatiquement** le style éditorial d'un site (ton, structure, vocabulaire)
- **Identifier automatiquement** les concurrents via recherche multi-sources
- **Scraper et indexer** les articles de blog concurrents
- **Détecter les tendances** thématiques avec topic modeling (BERTopic)
- **Générer des recommandations** stratégiques basées sur les gaps détectés

## 🚀 Démarrage rapide

Pour un guide complet d'installation et de configuration, consultez [quickstart.md](.specify/specs/000-project-foundation/quickstart.md).

### Prérequis

- Python 3.10+ (3.12 recommandé)
- Docker & Docker Compose
- uv (gestionnaire de dépendances)
- Playwright (pour Crawl4AI)
- Ollama (pour les LLMs locaux)
- **GPU NVIDIA (optionnel mais recommandé)** : Pour accélérer les LLMs, consultez [docs/gpu-setup.md](docs/gpu-setup.md)

### Installation rapide

```bash
# 1. Installer uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Installer les dépendances
uv pip install -e ".[dev]"

# 3. Installer Playwright
playwright install chromium

# 4. Configurer l'environnement
cp .env.example .env
# Éditer .env avec vos configurations

# 5. Démarrer les services (PostgreSQL, Qdrant, Ollama)
docker-compose -f docker/docker-compose.yml up -d

# 6. Télécharger les modèles Ollama
ollama pull llama3:8b
ollama pull mistral:7b
ollama pull phi3:medium

# 7. Installer le modèle spaCy français
python -m spacy download fr_core_news_md

# 8. Initialiser la base de données
alembic upgrade head

# 9. Créer la collection Qdrant
make init-qdrant
# ou: uv run python scripts/init_qdrant.py

# 10. (Optionnel) Indexer les articles existants dans Qdrant
# Si vous avez des articles dans la base qui n'ont pas encore été indexés
uv run python scripts/index_existing_articles.py
# Ou pour un domaine spécifique:
uv run python scripts/index_existing_articles.py example.com
# ou utiliser la cible Makefile:
make index-articles DOMAIN=example.com

# 10. Démarrer l'API
uvicorn python_scripts.api.main:app --reload --host 0.0.0.0 --port 8000
```

L'API sera disponible sur `http://localhost:8000` avec la documentation Swagger sur `http://localhost:8000/docs`.

### Accès aux services

- **API FastAPI**: http://localhost:8000
- **Documentation Swagger**: http://localhost:8000/docs
- **pgAdmin** (gestion PostgreSQL): http://localhost:5050
  - Email: `admin@editorial.dev` (par défaut)
  - Password: `admin` (par défaut)
  - **Guide de configuration** : Voir [docs/pgadmin-setup.md](docs/pgadmin-setup.md)
  - **Connexion PostgreSQL** :
    - Host: `postgres` ⚠️ (nom du service Docker, **PAS** localhost)
    - Port: `5432`
    - Database: `editorial_db`
    - Username: `editorial_user`
    - Password: (valeur de `POSTGRES_PASSWORD` dans `.env`)
- **Qdrant Dashboard**: http://localhost:6333/dashboard
- **Ollama API**: http://localhost:11435

### Configuration GPU (optionnel mais recommandé)

Pour accélérer les LLMs avec votre GPU NVIDIA, consultez le guide complet : [docs/gpu-setup.md](docs/gpu-setup.md)

**Configuration rapide** :
1. Assurez-vous que `nvidia-container-toolkit` est installé
2. Ajoutez `OLLAMA_NUM_GPU=1` dans votre fichier `.env`
3. Redémarrez Ollama : `make docker-restart` ou `docker compose -f docker/docker-compose.yml restart ollama`

Le GPU sera automatiquement détecté et utilisé par Ollama.

## ⚡ Commandes rapides

### Avec Makefile (recommandé)

```bash
# Afficher toutes les commandes disponibles
make help

# Démarrage complet (Docker + DB + API)
make dev

# Ou étape par étape:
make docker-up      # Démarrer les services Docker
make init-db        # Initialiser la base de données
make start          # Démarrer l'API

# Redémarrer l'application
make restart

# Arrêter l'API
make stop

# Voir le statut
make status

# Voir les logs Docker
make docker-logs
```

### Avec les scripts shell

```bash
# Démarrer l'application
./scripts/start.sh

# Redémarrer l'application
./scripts/restart.sh

# Arrêter l'application
./scripts/stop.sh
```

### Commandes Docker directement

```bash
# Démarrer les services
docker-compose -f docker/docker-compose.yml up -d

# Arrêter les services
docker-compose -f docker/docker-compose.yml down

# Redémarrer les services
docker-compose -f docker/docker-compose.yml restart

# Voir les logs
docker-compose -f docker/docker-compose.yml logs -f
```

## 📁 Structure du projet

```
python_scripts/
├── agents/              # Agents IA
├── analysis/            # Topic modeling & NLP
├── api/                 # FastAPI
├── database/            # Modèles et migrations
├── ingestion/           # Crawling et scraping
├── vectorstore/         # Qdrant et embeddings
├── config/              # Configuration
├── utils/               # Utilitaires
└── jobs/                # Tâches planifiées

tests/
├── unit/                # Tests unitaires
├── integration/         # Tests d'intégration
└── e2e/                 # Tests end-to-end

docker/                  # Configuration Docker
docs/                    # Documentation
```

## 🧪 Tests

```bash
# Tous les tests
pytest

# Tests unitaires uniquement
pytest tests/unit

# Tests avec couverture
pytest --cov=python_scripts --cov-report=html
```

## 📚 Documentation

- **Spécification**: `.specify/specs/000-project-foundation/spec.md`
- **Plan d'implémentation**: `.specify/specs/000-project-foundation/plan.md`
- **Guide de démarrage**: `.specify/specs/000-project-foundation/quickstart.md`
- **Modèle de données**: `.specify/specs/000-project-foundation/data-model.md`
- **Contrats API**: `.specify/specs/000-project-foundation/contracts/api.yaml`

## 🏗️ Architecture

Le système utilise une architecture multi-agents avec :

- **FastAPI** pour l'API REST
- **PostgreSQL** pour les métadonnées et la traçabilité
- **Qdrant** pour les embeddings et la recherche sémantique
- **Ollama** pour les LLMs locaux (llama3, mistral, phi3)
- **BERTopic** pour le topic modeling
- **Crawl4AI** pour le scraping éthique

## 🔧 Configuration

Toutes les variables d'environnement sont définies dans `.env.example`. Copiez ce fichier vers `.env` et configurez selon vos besoins.

## 📝 Licence

Proprietary

## 👥 Équipe

Development Team

