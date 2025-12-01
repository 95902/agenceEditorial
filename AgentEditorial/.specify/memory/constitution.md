# Constitution du Projet Agent editorial & Concurrentiel

Ce document établit les principes fondamentaux, l'architecture technique et les standards de développement du système **Agent Éditorial & Concurrentiel**. Tous les choix techniques, patterns de code et décisions architecturales doivent se conformer à cette Constitution.

**Mission du Projet:**

Créer un système multi-agents d'analyse éditoriale et concurrentielle utilisant l'intelligence artificielle pour analyser automatiquement le style éditorial de sites web, identifier leurs concurrents, extraire des articles, et détecter les tendances thématiques du marché.

**Principes Directeurs:**

1. **Spec-Driven Development:** Les spécifications précèdent le code
2. **AI-First Architecture:** Optimisé pour génération de code avec Cursor
3. **Type Safety:** Type hints obligatoires, validation Pydantic
4. **Async by Default:** Tout I/O est asynchrone
5. **Observability:** Traçabilité complète de tous les workflows

---

## Article I: Architecture & Stack Technique

### Section 1.1: Stack Fondamental (NON-NÉGOCIABLE)

**Langage & Runtime:**

- Python **3.10+** (minimum), Python **3.12** recommandé
- Gestion dépendances: **uv** (moderne, rapide)
- Type checking: **mypy** en mode strict
- Formatage: **black** + **isort** + **ruff**

**Framework API:**

- **FastAPI 0.115+** pour l'API REST
- **Uvicorn** comme serveur ASGI
- **Pydantic V2** pour validation de données
- Versioning API: `/api/v1/`

**Bases de Données:**

- **PostgreSQL 15+** (relationnel)
- **SQLAlchemy 2.0+** (ORM async)
- **Alembic** pour migrations
- **Qdrant** (vectorstore pour embeddings)

**Intelligence Artificielle:**

- **LangChain 0.2+** / **LangGraph** (orchestration agents)
- **Ollama** (LLMs locaux: llama3, mistral, phi3)
- **Sentence-Transformers** (embeddings)
- **BERTopic 0.16+** (topic modeling)
- **spaCy 3.7+** (NLP, entités nommées)
- **NLTK 3.9+** (analyse linguistique)

**Scraping & Ingestion:**

- **Crawl4AI 0.7+** (module Python, PAS en conteneur)
- **BeautifulSoup4** (parsing HTML)
- **Playwright** (JavaScript rendering pour Crawl4AI)

**Infrastructure:**

- **Docker Compose** (PostgreSQL, Qdrant, Ollama uniquement)
- **n8n** (orchestration workflows, optionnel)

### Section 1.2: Architecture Multi-Agents

**Pattern Global:**

- **Domain-Driven Design** avec bounded contexts par agent
- **Event-Driven Architecture** pour communication inter-agents
- **Repository Pattern** pour accès données
- **CQRS léger** (séparation read/write pour performance)

**Agents Principaux:**

| Agent | Responsabilité | Technologies |
|-------|----------------|--------------|
| **agent_analysis** | Analyse éditoriale (style, ton, structure) | LangChain + 4 LLMs spécialisés |
| **agent_competitor** | Recherche concurrents multi-sources | Tavily + DuckDuckGo + Crawl4AI |
| **agent_scraping** | Scraping articles concurrents | Crawl4AI async + respect robots.txt |
| **agent_topic_modeling** | Détection tendances avec BERTopic | BERTopic + UMAP + HDBSCAN |
| **agent_orchestrator** | Coordination workflows | LangGraph state machine |

**Communication entre Agents:**

- **Synchrone:** API FastAPI endpoints
- **Asynchrone:** Messages via PostgreSQL (table `workflow_executions`)
- **State Management:** Shared state in PostgreSQL + Qdrant

### Section 1.3: Modèle de Données (10 Tables PostgreSQL)

**Tables Principales:**

1. `site_profiles` - Profils éditoriaux analysés
2. `workflow_executions` - Traçabilité exécutions
3. `site_analysis_results` - Résultats JSON par phase
4. `competitor_articles` - Articles concurrents scrapés
5. `editorial_trends` - Tendances N-grams + entités
6. `bertopic_analysis` - Topics BERTopic découverts
7. `crawl_cache` - Cache crawling (hash URL + contenu)
8. `scraping_permissions` - Règles robots.txt
9. `performance_metrics` - Métriques détaillées
10. `audit_log` - Logs audit complets

**Contraintes:**

- Tous les champs JSONB doivent avoir un schema Pydantic correspondant
- Index obligatoires sur: domain, execution_id, status, created_at
- Relations Many-to-Many via tables de liaison explicites
- Soft delete (flag `is_valid`) pour données critiques

---

## Article II: Standards de Code Python

### Section 2.1: Type Hints & Validation (OBLIGATOIRE)

**Règle:** Tout code Python DOIT utiliser type hints.

```python
# ✅ CORRECT
async def analyze_domain(
    domain: str,
    max_pages: int = 50,
    session: AsyncSession | None = None
) -> SiteProfile:
    ...

# ❌ INTERDIT
async def analyze_domain(domain, max_pages=50, session=None):
    ...
```

**Validation:**

- Tous les inputs API: **Pydantic models**
- Tous les outputs API: **Pydantic models**
- Configuration: **Pydantic Settings**
- Données DB → modèles métier: **Mappers explicites**

### Section 2.2: Async/Await (OBLIGATOIRE)

**Règle:** Tout I/O (DB, HTTP, LLM, Crawl) DOIT être asynchrone.

```python
# ✅ CORRECT
async def crawl_and_analyze(url: str) -> ArticleData:
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url)
    embedding = await generate_embedding(result.text)
    await save_to_qdrant(embedding)
    return ArticleData(...)

# ❌ INTERDIT - Bloquant
def crawl_and_analyze(url: str) -> ArticleData:
    result = requests.get(url)  # Blocking!
    ...
```

### Section 2.3: Structure des Modules

**Organisation des fichiers:**

```
python_scripts/
├── agents/              # Agents IA
│   ├── agent_analysis.py
│   ├── agent_competitor.py
│   ├── agent_scraping_analysis_concurence.py
│   ├── prompts.py       # Tous les prompts LLM centralisés
│   └── utils/
├── analysis/            # Topic modeling & NLP
│   ├── topic_modeling.py    # BERTopic
│   ├── ngram_extraction.py
│   ├── entity_extraction.py # spaCy
│   └── trend_synthesizer.py
├── api/                 # FastAPI
│   ├── main.py
│   ├── dependencies.py  # DB sessions, auth, etc.
│   ├── routers/
│   │   ├── sites.py
│   │   ├── competitors.py
│   │   ├── trends.py
│   │   └── health.py
│   └── schemas/         # Pydantic models API
│       ├── requests.py
│       └── responses.py
├── database/
│   ├── models.py        # SQLAlchemy models
│   ├── db_session.py
│   ├── crud_*.py        # CRUD operations
│   └── migrations/      # Alembic
├── ingestion/
│   ├── crawl_pages.py   # Crawl4AI
│   ├── detect_sitemaps.py
│   └── text_cleaner.py
├── vectorstore/
│   ├── qdrant_client.py
│   └── embeddings_utils.py
├── config/
│   └── settings.py      # Pydantic Settings
└── tests/
    ├── unit/
    ├── integration/
    └── e2e/
```

### Section 2.4: Docstrings & Documentation

**Format:** Google-style docstrings obligatoires.

```python
async def analyze_competitor_trends(
    domain_list: list[str],
    window_days: int = 30
) -> BertopicAnalysis:
    """Analyze editorial trends on competitor articles using BERTopic.

    This function retrieves articles from the specified competitor domains,
    applies BERTopic clustering, and analyzes topic evolution over time.

    Args:
        domain_list: List of competitor domain names (e.g., ["site1.fr", "site2.fr"])
        window_days: Temporal window in days for trend analysis (default: 30)

    Returns:
        BertopicAnalysis containing discovered topics, evolution data, and visualizations

    Raises:
        ValueError: If domain_list is empty or window_days < 7
        DatabaseError: If article retrieval fails

    Example:
        >>> topics = await analyze_competitor_trends(
        ...     ["competitor1.fr", "competitor2.fr"],
        ...     window_days=30
        ... )
        >>> print(f"Found {len(topics.topics)} topics")
    """
    ...
```

### Section 2.5: Error Handling

**Hiérarchie d'exceptions personnalisées:**

```python
# Toutes les exceptions métier héritent de BaseException custom
class EditorialAgentException(Exception):
    """Base exception for all business logic errors."""
    pass

class CrawlingError(EditorialAgentException):
    """Raised when crawling fails."""
    pass

class LLMError(EditorialAgentException):
    """Raised when LLM inference fails."""
    pass

class DatabaseError(EditorialAgentException):
    """Raised when database operations fail."""
    pass
```

**Gestion:**

- API FastAPI: Exception handlers globaux retournant JSON structuré
- Agents: Retry logic avec tenacity (max 3 tentatives, backoff exponentiel)
- Logs: Structured logging avec contexte (execution_id, agent_name, etc.)

---

## Article III: Tests (NON-NÉGOCIABLE)

### Section 3.1: Stratégie de Tests

**Couverture minimale:** 80% (mesuré par pytest-cov)

**Types de tests:**

| Type | Framework | Responsabilité |
|------|-----------|----------------|
| **Unit** | pytest | Fonctions pures, CRUD, helpers |
| **Integration** | pytest + testcontainers | DB, Qdrant, agents |
| **E2E** | pytest + httpx | API endpoints complets |
| **Contract** | pactman (optionnel) | Contrats inter-agents |

### Section 3.2: Organisation des Tests

```
tests/
├── unit/
│   ├── test_crud_profiles.py
│   ├── test_text_cleaner.py
│   └── test_ngram_extraction.py
├── integration/
│   ├── test_agent_analysis.py
│   ├── test_bertopic_pipeline.py
│   └── conftest.py          # Fixtures DB test
└── e2e/
    ├── test_api_sites.py
    └── test_full_workflow.py
```

### Section 3.3: Fixtures & Mocks

**Règles:**

- PostgreSQL de test: **testcontainers** ou DB séparée
- Qdrant de test: Instance éphémère in-memory
- LLMs: **Mocker** (pas d'appels réels en tests)
- Crawl4AI: Fixtures HTML pré-enregistrées

```python
# Exemple fixture
@pytest.fixture
async def db_session():
    """Provide async DB session for tests."""
    async with async_session_maker() as session:
        yield session
        await session.rollback()

@pytest.fixture
def mock_llm_response():
    """Mock LLM response for agent tests."""
    return {
        "tone": "professional",
        "complexity": 0.75,
        "domains": ["technology", "AI"]
    }
```

---

## Article IV: Agents IA - Standards

### Section 4.1: Structure d'un Agent

**Chaque agent DOIT implémenter:**

```python
from abc import ABC, abstractmethod
from typing import Any

class BaseAgent(ABC):
    """Base class for all agents."""
    
    def __init__(
        self,
        name: str,
        llm: BaseChatModel | None = None,
        tools: list[BaseTool] | None = None,
        memory: BaseMemory | None = None
    ):
        self.name = name
        self.llm = llm
        self.tools = tools or []
        self.memory = memory
        
    @abstractmethod
    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent's main task."""
        pass
        
    async def log_execution(self, execution_id: str, status: str):
        """Log execution to audit_log table."""
        pass
```

### Section 4.2: Prompts LLM

**Règle:** Tous les prompts sont centralisés dans `agents/prompts.py`.

**Format:** Utiliser LangChain `PromptTemplate` avec variables explicites.

```python
# agents/prompts.py
EDITORIAL_STYLE_PROMPT = PromptTemplate(
    input_variables=["content", "domain"],
    template="""Analyze the editorial style of {domain} based on this content:

Content:

{content}

Identify:

1. Language level (simple, intermediate, advanced, expert)
2. Editorial tone (professional, conversational, technical, marketing)
3. Target audience
4. Writing style features

Return valid JSON with keys: language_level, editorial_tone, target_audience, style_features.

"""
)
```

### Section 4.3: LLMs Spécialisés par Tâche

**Mapping obligatoire:**

| Tâche | Modèle Ollama | Raison |
|-------|---------------|--------|
| **Extraction domaines d'activité** | llama3:8b | Compréhension contexte large |
| **Analyse style & ton** | llama3:8b | Nuances linguistiques |
| **Structure de contenu** | mistral:7b | Classification structurée |
| **Extraction mots-clés** | phi3:medium | Rapidité + précision |
| **Synthèse multi-agents** | llama3:8b | Fusion cohérente |

### Section 4.4: Memory & State Management

**Règles:**

- Agent stateless autant que possible
- State persisté dans PostgreSQL (`workflow_executions`, `site_analysis_results`)
- LangChain memory uniquement pour conversations (si applicable)
- Pas de state en RAM sauf cache temporaire

---

## Article V: API FastAPI - Standards

### Section 5.1: Structure des Endpoints

**Convention de nommage:**

- Ressources au pluriel: `/api/v1/sites/`, `/api/v1/competitors/`
- Actions avec verbes HTTP: `GET /sites/{domain}`, `POST /sites/analyze`
- Sous-ressources: `/api/v1/sites/{domain}/competitors`

**Status codes standardisés:**

- `200 OK` - Succès (GET)
- `201 Created` - Ressource créée (POST)
- `202 Accepted` - Traitement asynchrone lancé
- `400 Bad Request` - Validation Pydantic échouée
- `404 Not Found` - Ressource inexistante
- `422 Unprocessable Entity` - Erreur métier
- `500 Internal Server Error` - Erreur serveur

### Section 5.2: Request/Response Models

**Tous les modèles héritent de `BaseModel` Pydantic:**

```python
# api/schemas/requests.py
from pydantic import BaseModel, Field, validator

class SiteAnalysisRequest(BaseModel):
    domain: str = Field(
        ...,
        regex=r'^[a-z0-9.-]+\.[a-z]{2,}$',
        example="example.com"
    )
    max_pages: int = Field(
        default=50,
        ge=10,
        le=200,
        description="Maximum number of pages to analyze"
    )
    
    @validator('domain')
    def validate_domain(cls, v):
        if v.startswith('http'):
            raise ValueError('Domain should not include protocol')
        return v.lower()

# api/schemas/responses.py
class ExecutionResponse(BaseModel):
    execution_id: str
    status: str
    start_time: datetime
    estimated_duration_minutes: int
```

### Section 5.3: Background Tasks

**Pour workflows longs (>30s):**

```python
from fastapi import BackgroundTasks

@router.post("/sites/analyze", response_model=ExecutionResponse, status_code=202)
async def analyze_site(
    request: SiteAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Launch editorial analysis in background."""
    execution = await create_workflow_execution(db, "editorial_analysis")
    
    background_tasks.add_task(
        run_analysis_workflow,
        execution.id,
        request.domain,
        request.max_pages
    )
    
    return ExecutionResponse(
        execution_id=execution.execution_id,
        status="pending",
        start_time=execution.start_time,
        estimated_duration_minutes=5
    )
```

### Section 5.4: WebSockets pour Progression

**Endpoint:** `/api/v1/executions/{execution_id}/stream`

**Messages JSON:**

```json
{
  "type": "progress",
  "execution_id": "uuid",
  "current": 25,
  "total": 50,
  "message": "Analyzing page 25/50",
  "timestamp": "2025-01-25T10:30:00Z"
}
```

---

## Article VI: Base de Données - Standards

### Section 6.1: SQLAlchemy Models

**Conventions:**

- Nom de table: snake_case pluriel (`site_profiles`, pas `SiteProfile`)
- Clé primaire: `id: int = Column(Integer, primary_key=True)`
- Timestamps: `created_at`, `updated_at` (auto-managed)
- Soft delete: `is_valid: bool = Column(Boolean, default=True)`
- JSONB: Type hint Python `dict[str, Any]` + Pydantic schema

```python
from sqlalchemy import Column, Integer, String, TIMESTAMP, JSONB, Boolean
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class SiteProfile(Base):
    __tablename__ = "site_profiles"
    
    id = Column(Integer, primary_key=True)
    domain = Column(String, unique=True, nullable=False, index=True)
    analysis_date = Column(TIMESTAMP, default=datetime.utcnow)
    language_level = Column(String)  # enum: simple, intermediate, advanced, expert
    editorial_tone = Column(String)  # enum: professional, conversational, technical
    activity_domains = Column(JSONB)  # list[str]
    content_structure = Column(JSONB)  # dict with Pydantic schema
    pages_analyzed = Column(Integer, default=0)
    is_valid = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow, index=True)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### Section 6.2: Migrations Alembic

**Règles:**

- Toujours générer avec `alembic revision --autogenerate -m "description"`
- Jamais éditer manuellement les tables en prod
- Versionner toutes les migrations dans Git
- Tester migrations up + down en dev avant prod

### Section 6.3: CRUD Operations

**Pattern Repository:**

```python
# database/crud_profiles.py
async def get_site_profile(
    db: AsyncSession,
    domain: str
) -> SiteProfile | None:
    """Get site profile by domain."""
    result = await db.execute(
        select(SiteProfile).where(SiteProfile.domain == domain)
    )
    return result.scalars().first()

async def create_site_profile(
    db: AsyncSession,
    profile_data: SiteProfileCreate
) -> SiteProfile:
    """Create new site profile."""
    profile = SiteProfile(**profile_data.model_dump())
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile
```

---

## Article VII: Scraping & Éthique

### Section 7.1: Respect robots.txt (OBLIGATOIRE)

**Règle:** Toujours lire et respecter `robots.txt` avant crawl.

```python
# ingestion/crawl_pages.py
async def crawl_with_permissions(domain: str, urls: list[str]) -> list[str]:
    """Crawl URLs respecting robots.txt rules."""
    permissions = await get_scraping_permissions(domain)
    
    if not permissions.scraping_allowed:
        raise CrawlingError(f"Scraping disallowed for {domain}")
    
    # Apply crawl-delay
    delay = permissions.crawl_delay or 2
    
    results = []
    async with AsyncWebCrawler() as crawler:
        for url in urls:
            if is_url_disallowed(url, permissions.disallowed_paths):
                continue
            result = await crawler.arun(url)
            results.append(result)
            await asyncio.sleep(delay)
    
    return results
```

### Section 7.2: Rate Limiting

**Limites:**

- Max **1 requête / 2 secondes** par domaine (par défaut)
- Max **100 pages** par domaine par exécution
- Max **5 domaines** en parallèle

### Section 7.3: User-Agent

**Obligatoire:**

```
User-Agent: EditorialBot/1.0 (+https://votre-site.com/bot-info)
```

---

## Article VIII: Topic Modeling avec BERTopic

### Section 8.1: Configuration BERTopic

**Hyperparamètres standards:**

```python
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
topic_model = BERTopic(
    embedding_model=embedding_model,
    min_topic_size=10,           # Minimum 10 articles par topic
    nr_topics="auto",            # Détection automatique
    calculate_probabilities=True,
    verbose=True
)
```

### Section 8.2: Stockage des Résultats

**Table `bertopic_analysis`:**

- `topics` (JSONB): Liste des topics avec keywords, scores
- `topic_hierarchy` (JSONB): Arbre hiérarchique
- `topics_over_time` (JSONB): Évolution temporelle
- `visualizations` (JSONB): Chemins vers fichiers HTML générés

### Section 8.3: Visualisations

**Générer automatiquement:**

1. Carte 2D des topics (`visualize_topics()`)
2. Barchart par topic (`visualize_barchart()`)
3. Évolution temporelle (`visualize_topics_over_time()`)
4. Heatmap similarité (`visualize_heatmap()`)

Stocker dans `/mnt/user-data/outputs/visualizations/`

---

## Article IX: Observabilité & Monitoring

### Section 9.1: Logging Structuré

**Format:** JSON structuré avec contexte.

```python
import structlog

logger = structlog.get_logger()

logger.info(
    "workflow_started",
    execution_id=execution.id,
    workflow_type="editorial_analysis",
    domain=domain,
    timestamp=datetime.utcnow().isoformat()
)
```

### Section 9.2: Métriques à Collecter

**Dans `performance_metrics`:**

- Durée exécution (par agent, par workflow)
- Tokens LLM consommés (par modèle)
- Pages crawlées (par domaine)
- Topics découverts (par analyse BERTopic)
- Erreurs (par type, par agent)

### Section 9.3: Health Checks

**Endpoint:** `GET /api/v1/health`

**Vérifier:**

- PostgreSQL: Connexion + latence
- Qdrant: Connexion + nombre collections
- Ollama: Disponibilité modèles (llama3, mistral, phi3)
- Disk space: `/mnt/user-data/outputs/`

---

## Article X: Sécurité & Variables d'Environnement

### Section 10.1: Variables d'Environnement

**Fichier `.env` (jamais versionné):**

```bash
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=editorial_db
POSTGRES_USER=editorial_user
POSTGRES_PASSWORD=strong_password_here

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=optional_key

# Ollama
OLLAMA_BASE_URL=http://localhost:11434

# API Keys (optionnel)
TAVILY_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here

# Scraping
USER_AGENT=EditorialBot/1.0 (+https://your-site.com/bot)
CRAWL_DELAY_DEFAULT=2
MAX_PAGES_PER_DOMAIN=100
```

**Chargement:**

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    postgres_host: str
    postgres_port: int
    postgres_db: str
    # ... autres variables
    
    class Config:
        env_file = ".env"
        
settings = Settings()
```

### Section 10.2: Secrets

**Règles:**

- Jamais de secrets hardcodés dans le code
- Utiliser `.env` en dev
- Utiliser secrets manager (HashiCorp Vault, AWS Secrets Manager) en prod
- Rotation clés API tous les 90 jours

---

## Article XI: Intégration Continue (CI/CD)

### Section 11.1: GitHub Actions

**Pipeline obligatoire:**

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh
      - name: Install dependencies
        run: uv pip install -e ".[dev]"
      - name: Run linting
        run: |
          ruff check python_scripts/
          black --check python_scripts/
          mypy python_scripts/
      - name: Run tests
        run: pytest --cov=python_scripts --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### Section 11.2: Pre-commit Hooks

**Installer:**

```bash
pre-commit install
```

**`.pre-commit-config.yaml`:**

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.10.0
    hooks:
      - id: black
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.8
    hooks:
      - id: ruff
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.11.0
    hooks:
      - id: mypy
        additional_dependencies: [types-requests]
```

---

## Article XII: Documentation

### Section 12.1: Documentation Technique

**Obligatoire:**

- `README.md` : Installation, quickstart
- `docs/architecture.md` : Diagrammes architecture
- `docs/api.md` : Documentation endpoints (générée par FastAPI)
- `docs/agents.md` : Description agents et workflows
- `docs/database.md` : Schéma DB + explications tables

### Section 12.2: ADRs (Architecture Decision Records)

**Format:**

```markdown
# ADR-001: Choix de BERTopic pour Topic Modeling

**Date:** 2025-01-20  
**Status:** Accepted

## Context

Besoin d'identifier automatiquement les thèmes dans les articles concurrents.

## Decision

Utiliser BERTopic plutôt que LDA ou NMF.

## Rationale

- Embeddings denses (meilleurs que bag-of-words)
- Clustering automatique (pas besoin de fixer nb topics)
- Évolution temporelle native
- Visualisations interactives

## Consequences

- Dépendance UMAP + HDBSCAN (heavy)
- Nécessite GPU recommandé (mais fonctionne sur CPU)
```

---

## Governance & Enforcement

### Section G.1: Révision de la Constitution

**Processus:**

1. Proposition de modification via Pull Request
2. Discussion avec mainteneurs
3. Vote (majorité 2/3)
4. Mise à jour version + date

**Versioning:** Semantic versioning (MAJOR.MINOR.PATCH)

### Section G.2: Exceptions

**Dérogations possibles:**

- Prototypes / PoCs (documenter clairement)
- Dépendances externes non conformes (isoler dans adapters)
- Urgences production (créer issue de refactoring)

**Processus:** Toute exception doit être documentée dans un ADR.

### Section G.3: Enforcement avec Cursor

**Configuration `.cursor/rules`:**

```markdown
# Cursor Rules for Agent Éditorial

- Always read CONSTITUTION.md before generating code
- All Python code must have type hints
- All async I/O operations (DB, HTTP, LLM)
- Use Pydantic for validation
- Follow SQLAlchemy 2.0 async patterns
- Centralize prompts in agents/prompts.py
- Test coverage target: 80%
```

---

**Version**: 1.0.0 | **Ratified**: 2025-01-25 | **Last Amended**: 2025-01-25
