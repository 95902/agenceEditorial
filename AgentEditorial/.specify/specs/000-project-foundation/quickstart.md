# Quickstart Guide: Agent Éditorial & Concurrentiel

**Date**: 2025-01-25  
**Plan**: [plan.md](./plan.md)

Ce guide fournit les étapes pour installer, configurer et démarrer le système.

---

## Prérequis

### Système

- **OS**: Linux, macOS, ou Windows (avec WSL2 recommandé)
- **Python**: 3.12 (minimum 3.10+)
- **RAM**: Minimum 16GB (recommandé 32GB pour Ollama)
- **Disk**: Minimum 50GB libre (pour modèles Ollama + DB)
- **Docker**: Docker Desktop ou Docker Engine avec Docker Compose

### Outils Requis

- **uv**: Gestionnaire de dépendances Python moderne
- **git**: Pour cloner le repository
- **PostgreSQL client** (optionnel, pour inspection DB)

---

## Installation

### 1. Installer uv

**Linux/macOS:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Vérifier l'installation:**
```bash
uv --version
```

### 2. Installer Playwright (pour Crawl4AI)

```bash
playwright install chromium
# Ou pour tous les navigateurs:
playwright install
```

### 3. Télécharger les modèles Ollama

```bash
# Démarrer Ollama (sera fait automatiquement avec Docker Compose)
# Puis télécharger les modèles:

ollama pull llama3:8b
ollama pull mistral:7b
ollama pull phi3:medium
ollama pull mxbai-embed-large
```

**Note**: Ces modèles seront téléchargés automatiquement au premier usage si Ollama est lancé via Docker Compose.

### 4. Installer le modèle spaCy français

```bash
python -m spacy download fr_core_news_md
```

---

## Configuration

### 1. Créer le fichier `.env`

Créez un fichier `.env` à la racine du projet:

```bash
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=editorial_db
POSTGRES_USER=editorial_user
POSTGRES_PASSWORD=change_me_strong_password

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=

# Ollama
OLLAMA_BASE_URL=http://localhost:11434

# API Keys (optionnel)
TAVILY_API_KEY=
OPENAI_API_KEY=

# Scraping
USER_AGENT=EditorialBot/1.0 (+https://your-site.com/bot)
CRAWL_DELAY_DEFAULT=2
MAX_PAGES_PER_DOMAIN=100

# Rate Limiting
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_ANALYSIS_PER_MINUTE=10

# Data Retention
DATA_RETENTION_DAYS=90
```

### 2. Démarrer les services avec Docker Compose

```bash
# À la racine du projet
docker-compose up -d
```

Cela démarre:
- PostgreSQL (port 5432)
- Qdrant (port 6333)
- Ollama (port 11434)

**Vérifier que les services sont démarrés:**
```bash
docker-compose ps
```

### 3. Initialiser la base de données

```bash
# Installer les dépendances
uv pip install -e ".[dev]"

# Créer les migrations Alembic (si première fois)
alembic revision --autogenerate -m "Initial schema"

# Appliquer les migrations
alembic upgrade head
```

### 4. Créer la collection Qdrant

```bash
# Via Python (script d'initialisation)
python scripts/init_qdrant.py

# Ou via API Qdrant directement
curl -X PUT "http://localhost:6333/collections/competitor_articles" \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": {
      "size": 384,
      "distance": "Cosine"
    }
  }'
```

---

## Démarrer l'API

### Mode Développement

```bash
# Démarrer avec auto-reload
uvicorn python_scripts.api.main:app --reload --host 0.0.0.0 --port 8000
```

L'API sera disponible sur: `http://localhost:8000`

### Documentation Interactive

Accédez à la documentation Swagger UI:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

---

## Exemples d'utilisation

### 1. Analyser le style éditorial d'un site

```bash
curl -X POST "http://localhost:8000/api/v1/sites/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "example.com",
    "max_pages": 50
  }'
```

**Réponse:**
```json
{
  "execution_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "start_time": "2025-01-25T10:30:00Z",
  "estimated_duration_minutes": 5
}
```

### 2. Suivre la progression (WebSocket)

```javascript
// JavaScript example
const ws = new WebSocket('ws://localhost:8000/api/v1/executions/{execution_id}/stream');

ws.onmessage = (event) => {
  const progress = JSON.parse(event.data);
  console.log(`Progress: ${progress.current}/${progress.total} - ${progress.message}`);
};
```

**Ou via polling:**
```bash
curl "http://localhost:8000/api/v1/executions/{execution_id}"
```

### 3. Obtenir le profil éditorial

```bash
curl "http://localhost:8000/api/v1/sites/example.com"
```

**Réponse:**
```json
{
  "domain": "example.com",
  "analysis_date": "2025-01-25T10:35:00Z",
  "language_level": "intermediate",
  "editorial_tone": "professional",
  "target_audience": {
    "primary": "B2B entreprises",
    "secondary": ["Tech startups"]
  },
  "activity_domains": {
    "primary_domains": ["Intelligence Artificielle", "Technologie"]
  },
  "pages_analyzed": 50,
  ...
}
```

### 4. Rechercher des concurrents

```bash
curl -X POST "http://localhost:8000/api/v1/competitors/search" \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "example.com",
    "max_competitors": 100
  }'
```

### 5. Scraper les articles des concurrents

```bash
curl -X POST "http://localhost:8000/api/v1/scraping/competitors" \
  -H "Content-Type: application/json" \
  -d '{
    "domains": ["competitor1.fr", "competitor2.fr"],
    "max_articles_per_domain": 100
  }'
```

### 6. Analyser les tendances avec BERTopic

```bash
curl -X POST "http://localhost:8000/api/v1/trends/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "domains": ["competitor1.fr", "competitor2.fr"],
    "time_window_days": 30
  }'
```

### 7. Obtenir les topics découverts

```bash
curl "http://localhost:8000/api/v1/trends/topics?time_window_days=30"
```

### 8. Identifier les gaps de contenu

```bash
curl "http://localhost:8000/api/v1/trends/gaps?client_domain=example.com"
```

### 9. Health Check

```bash
curl "http://localhost:8000/api/v1/health"
```

---

## Tests

### Lancer tous les tests

```bash
# Tests unitaires
pytest tests/unit -v

# Tests d'intégration (nécessite services Docker)
pytest tests/integration -v

# Tests E2E (nécessite API démarrée)
pytest tests/e2e -v

# Tous les tests avec couverture
pytest --cov=python_scripts --cov-report=html --cov-report=term
```

### Tests avec testcontainers

Les tests d'intégration utilisent testcontainers pour créer des instances PostgreSQL et Qdrant éphémères. Assurez-vous que Docker est démarré.

---

## Dépannage

### PostgreSQL: Connection refused

**Problème**: `psycopg2.OperationalError: could not connect to server`

**Solutions:**
1. Vérifier que PostgreSQL est démarré: `docker-compose ps`
2. Vérifier les credentials dans `.env`
3. Vérifier que le port 5432 n'est pas utilisé par un autre service

### Ollama: Model not found

**Problème**: `Error: model 'llama3:8b' not found`

**Solutions:**
1. Vérifier qu'Ollama est démarré: `docker-compose ps`
2. Télécharger le modèle: `ollama pull llama3:8b`
3. Vérifier les modèles disponibles: `ollama list`

### Qdrant: Collection not found

**Problème**: `Qdrant collection 'competitor_articles' not found`

**Solutions:**
1. Créer la collection via script d'initialisation
2. Ou via API: `curl -X PUT "http://localhost:6333/collections/competitor_articles" ...`

### Rate Limiting: 429 Too Many Requests

**Problème**: Trop de requêtes trop rapidement

**Solutions:**
1. Attendre le temps indiqué dans header `Retry-After`
2. Ajuster `RATE_LIMIT_PER_MINUTE` dans `.env` pour le développement
3. Implémenter retry logic avec backoff exponentiel dans votre client

### Crawl4AI: Playwright browser not found

**Problème**: `Error: Executable doesn't exist`

**Solutions:**
```bash
playwright install chromium
# Ou installer tous les navigateurs:
playwright install
```

### spaCy: French model not found

**Problème**: `spacy.errors.OldModelError: [E961]`

**Solutions:**
```bash
python -m spacy download fr_core_news_md
```

---

## Structure des Logs

Les logs sont structurés en JSON et incluent:

```json
{
  "timestamp": "2025-01-25T10:30:00Z",
  "level": "INFO",
  "execution_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_name": "agent_analysis",
  "message": "workflow_started",
  "workflow_type": "editorial_analysis",
  "domain": "example.com"
}
```

**Voir les logs:**
```bash
# Si logs dans fichier
tail -f logs/app.log | jq

# Si logs dans stdout (développement)
uvicorn ... | jq
```

---

## Prochaines Étapes

1. **Personnaliser la configuration**: Ajuster les paramètres dans `.env`
2. **Exécuter une analyse complète**: Suivre le workflow end-to-end
3. **Consulter la documentation**: Voir `docs/architecture.md` et `docs/agents.md`
4. **Contribuer**: Lire les guidelines de contribution (si applicable)

---

## Support

- **Documentation**: Voir `docs/`
- **API Documentation**: `http://localhost:8000/docs`
- **Issues**: GitHub Issues (si applicable)
- **Constitution**: Voir `.specify/memory/constitution.md` pour les principes architecturaux

---

**Status**: ✅ **QUICKSTART COMPLETE**  
**Last Updated**: 2025-01-25