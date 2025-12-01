# Data Model: Agent Éditorial & Concurrentiel

**Date**: 2025-01-25  
**Plan**: [plan.md](./plan.md)  
**Constitution Reference**: Article I Section 1.3, Article VI

This document defines all database entities, their relationships, validation rules, and Pydantic schemas for JSONB fields.

---

## Entity Relationship Overview

```
site_profiles (1) ────< (many) site_analysis_results
site_profiles (1) ────< (many) competitor_articles (via domain analysis)
workflow_executions (1) ────< (many) site_analysis_results
workflow_executions (1) ────< (many) performance_metrics
workflow_executions (1) ────< (many) audit_log
competitor_articles (many) ────< (many) editorial_trends
competitor_articles (many) ────< (many) bertopic_analysis (via topic_id)
scraping_permissions (1) ────< (many) competitor_articles (via domain)
crawl_cache (independent, hash-based lookup)
```

---

## 1. site_profiles

**Purpose**: Stocke les profils éditoriaux analysés pour chaque domaine/site web.

### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY, AUTO_INCREMENT | Identifiant unique |
| `domain` | VARCHAR(255) | UNIQUE, NOT NULL, INDEXED | Nom de domaine (ex: "example.com") |
| `analysis_date` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Date de la dernière analyse |
| `language_level` | VARCHAR(50) | NULLABLE | Niveau de langage: `simple`, `intermediate`, `advanced`, `expert` |
| `editorial_tone` | VARCHAR(50) | NULLABLE | Ton éditorial: `professional`, `conversational`, `technical`, `marketing` |
| `target_audience` | JSONB | NULLABLE | Audience cible (Pydantic: `TargetAudienceSchema`) |
| `activity_domains` | JSONB | NULLABLE | Domaines d'activité identifiés (Pydantic: `ActivityDomainsSchema`) |
| `content_structure` | JSONB | NULLABLE | Structure de contenu analysée (Pydantic: `ContentStructureSchema`) |
| `keywords` | JSONB | NULLABLE | Mots-clés principaux (Pydantic: `KeywordsSchema`) |
| `style_features` | JSONB | NULLABLE | Caractéristiques de style (Pydantic: `StyleFeaturesSchema`) |
| `pages_analyzed` | INTEGER | DEFAULT 0 | Nombre de pages analysées |
| `llm_models_used` | JSONB | NULLABLE | Liste des modèles LLM utilisés (Pydantic: `LLMModelsSchema`) |
| `is_valid` | BOOLEAN | DEFAULT TRUE | Soft delete flag |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW(), INDEXED | Date de création |
| `updated_at` | TIMESTAMP | NOT NULL, DEFAULT NOW(), ON UPDATE NOW() | Date de mise à jour |

### Indexes

- Primary Key: `id`
- Unique: `domain`
- Index: `created_at`
- Index: `analysis_date`

### Pydantic Schemas

```python
from pydantic import BaseModel
from typing import List

class TargetAudienceSchema(BaseModel):
    """Audience cible identifiée."""
    primary: str  # Ex: "B2B entreprises", "Consommateurs tech"
    secondary: List[str] | None = None
    demographics: dict[str, any] | None = None  # Age range, interests, etc.

class ActivityDomainsSchema(BaseModel):
    """Domaines d'activité identifiés."""
    primary_domains: List[str]  # Ex: ["Intelligence Artificielle", "Technologie"]
    secondary_domains: List[str] | None = None

class ContentStructureSchema(BaseModel):
    """Structure de contenu analysée."""
    average_word_count: int | None = None
    average_paragraph_count: int | None = None
    heading_patterns: List[str] | None = None  # Ex: ["H1", "H2", "H3"]
    media_usage: dict[str, int] | None = None  # {"images": 5, "videos": 2}
    internal_linking: float | None = None  # Average internal links per page

class KeywordsSchema(BaseModel):
    """Mots-clés principaux."""
    primary_keywords: List[str]  # Top 10 keywords
    keyword_density: dict[str, float] | None = None  # keyword -> density %
    semantic_keywords: List[str] | None = None  # Keywords sémantiquement liés

class StyleFeaturesSchema(BaseModel):
    """Caractéristiques de style."""
    sentence_length_avg: float | None = None
    reading_level: str | None = None  # Ex: "College", "High School"
    formality_score: float | None = None  # 0.0 to 1.0
    punctuation_patterns: dict[str, any] | None = None

class LLMModelsSchema(BaseModel):
    """Modèles LLM utilisés pour l'analyse."""
    models: List[str]  # Ex: ["llama3:8b", "mistral:7b", "phi3:medium"]
    analysis_steps: dict[str, str] | None = None  # step -> model mapping
```

---

## 2. workflow_executions

**Purpose**: Traçabilité complète de toutes les exécutions de workflows.

### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY, AUTO_INCREMENT | Identifiant unique |
| `execution_id` | UUID | UNIQUE, NOT NULL, INDEXED | UUID v4 pour identification externe |
| `workflow_type` | VARCHAR(100) | NOT NULL | Type: `editorial_analysis`, `competitor_search`, `scraping`, `topic_modeling`, etc. |
| `status` | VARCHAR(50) | NOT NULL, INDEXED | Status: `pending`, `running`, `completed`, `failed`, `cancelled` |
| `input_data` | JSONB | NULLABLE | Données d'entrée du workflow (Pydantic: `WorkflowInputSchema`) |
| `output_data` | JSONB | NULLABLE | Données de sortie (résultats) (Pydantic: `WorkflowOutputSchema`) |
| `error_message` | TEXT | NULLABLE | Message d'erreur si status = `failed` |
| `start_time` | TIMESTAMP | NULLABLE | Heure de début d'exécution |
| `end_time` | TIMESTAMP | NULLABLE | Heure de fin d'exécution |
| `duration_seconds` | INTEGER | NULLABLE | Durée calculée (end_time - start_time) |
| `was_success` | BOOLEAN | NULLABLE | `true` si completed, `false` si failed |
| `parent_execution_id` | UUID | NULLABLE, FOREIGN KEY | Lien vers workflow parent (si sous-workflow) |
| `is_valid` | BOOLEAN | DEFAULT TRUE | Soft delete flag |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW(), INDEXED | Date de création |
| `updated_at` | TIMESTAMP | NOT NULL, DEFAULT NOW(), ON UPDATE NOW() | Date de mise à jour |

### Indexes

- Primary Key: `id`
- Unique: `execution_id`
- Index: `status`
- Index: `created_at`
- Index: `workflow_type`
- Foreign Key: `parent_execution_id` → `workflow_executions(execution_id)`

### Pydantic Schemas

```python
class WorkflowInputSchema(BaseModel):
    """Données d'entrée d'un workflow."""
    domain: str | None = None
    max_pages: int | None = None
    competitor_list: List[str] | None = None
    date_range: dict[str, str] | None = None  # {"start": "2025-01-01", "end": "2025-01-31"}
    options: dict[str, any] | None = None  # Options spécifiques au workflow

class WorkflowOutputSchema(BaseModel):
    """Données de sortie d'un workflow."""
    result_type: str  # "site_profile", "competitor_list", "topics", etc.
    result_data: dict[str, any]  # Données spécifiques au type de résultat
    artifacts: List[str] | None = None  # Chemins vers fichiers générés (visualisations, etc.)
    metrics: dict[str, any] | None = None  # Métriques de performance
```

---

## 3. site_analysis_results

**Purpose**: Résultats détaillés par phase d'analyse pour un site.

### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY, AUTO_INCREMENT | Identifiant unique |
| `site_profile_id` | INTEGER | NOT NULL, FOREIGN KEY, INDEXED | Lien vers `site_profiles(id)` |
| `execution_id` | UUID | NOT NULL, FOREIGN KEY, INDEXED | Lien vers `workflow_executions(execution_id)` |
| `analysis_phase` | VARCHAR(100) | NOT NULL | Phase: `crawling`, `llm_analysis`, `synthesis`, etc. |
| `phase_results` | JSONB | NOT NULL | Résultats de la phase (Pydantic: `PhaseResultsSchema`) |
| `llm_model_used` | VARCHAR(100) | NULLABLE | Modèle LLM utilisé pour cette phase |
| `processing_time_seconds` | INTEGER | NULLABLE | Temps de traitement de la phase |
| `is_valid` | BOOLEAN | DEFAULT TRUE | Soft delete flag |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Date de création |

### Indexes

- Primary Key: `id`
- Index: `site_profile_id`
- Index: `execution_id`
- Composite Index: `(site_profile_id, analysis_phase)`

### Foreign Keys

- `site_profile_id` → `site_profiles(id)` ON DELETE CASCADE
- `execution_id` → `workflow_executions(execution_id)` ON DELETE CASCADE

### Pydantic Schemas

```python
class PhaseResultsSchema(BaseModel):
    """Résultats d'une phase d'analyse."""
    phase: str
    status: str  # "success", "partial", "failed"
    data: dict[str, any]  # Données spécifiques à la phase
    confidence_score: float | None = None  # 0.0 to 1.0
    warnings: List[str] | None = None
```

---

## 4. competitor_articles

**Purpose**: Articles scrapés des sites concurrents.

### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY, AUTO_INCREMENT | Identifiant unique |
| `domain` | VARCHAR(255) | NOT NULL, INDEXED | Domaine source (ex: "competitor.fr") |
| `url` | TEXT | NOT NULL, UNIQUE | URL complète de l'article |
| `url_hash` | VARCHAR(64) | NOT NULL, INDEXED | SHA256 hash de l'URL (pour déduplication) |
| `title` | VARCHAR(500) | NOT NULL | Titre de l'article |
| `author` | VARCHAR(255) | NULLABLE | Auteur |
| `published_date` | DATE | NULLABLE, INDEXED | Date de publication |
| `content_text` | TEXT | NOT NULL | Contenu texte nettoyé |
| `content_html` | TEXT | NULLABLE | HTML original (optionnel) |
| `word_count` | INTEGER | DEFAULT 0 | Nombre de mots |
| `keywords` | JSONB | NULLABLE | Mots-clés extraits (Pydantic: `ArticleKeywordsSchema`) |
| `metadata` | JSONB | NULLABLE | Métadonnées (images, tags, categories) (Pydantic: `ArticleMetadataSchema`) |
| `qdrant_point_id` | UUID | NULLABLE | ID du point dans Qdrant (pour l'embedding) |
| `topic_id` | INTEGER | NULLABLE | ID du topic BERTopic assigné |
| `is_duplicate` | BOOLEAN | DEFAULT FALSE | Flag de doublon |
| `duplicate_of` | INTEGER | NULLABLE, FOREIGN KEY | Lien vers article original si doublon |
| `scraping_permission_id` | INTEGER | NULLABLE, FOREIGN KEY | Lien vers permissions utilisées |
| `is_valid` | BOOLEAN | DEFAULT TRUE | Soft delete flag |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW(), INDEXED | Date de scraping |
| `updated_at` | TIMESTAMP | NOT NULL, DEFAULT NOW(), ON UPDATE NOW() | Date de mise à jour |

### Indexes

- Primary Key: `id`
- Unique: `url`
- Index: `domain`
- Index: `url_hash`
- Index: `published_date`
- Index: `created_at`
- Index: `topic_id`
- Foreign Key: `duplicate_of` → `competitor_articles(id)`
- Foreign Key: `scraping_permission_id` → `scraping_permissions(id)`

### Pydantic Schemas

```python
class ArticleKeywordsSchema(BaseModel):
    """Mots-clés d'un article."""
    extracted_keywords: List[str]
    keyword_scores: dict[str, float] | None = None  # keyword -> relevance score

class ArticleMetadataSchema(BaseModel):
    """Métadonnées d'un article."""
    images: List[dict[str, str]] | None = None  # [{"url": "...", "alt": "..."}]
    tags: List[str] | None = None
    categories: List[str] | None = None
    reading_time_minutes: int | None = None
    featured_image: str | None = None
```

---

## 5. editorial_trends

**Purpose**: Tendances éditoriales extraites (N-grams, entités nommées).

### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY, AUTO_INCREMENT | Identifiant unique |
| `domain` | VARCHAR(255) | NOT NULL, INDEXED | Domaine analysé |
| `analysis_date` | DATE | NOT NULL, INDEXED | Date de l'analyse |
| `trend_type` | VARCHAR(50) | NOT NULL | Type: `ngram`, `entity`, `topic_keyword` |
| `trend_data` | JSONB | NOT NULL | Données de tendance (Pydantic: `TrendDataSchema`) |
| `time_window_days` | INTEGER | NOT NULL | Fenêtre temporelle (7, 30, 90 jours) |
| `is_valid` | BOOLEAN | DEFAULT TRUE | Soft delete flag |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Date de création |

### Indexes

- Primary Key: `id`
- Index: `domain`
- Index: `analysis_date`
- Composite Index: `(domain, analysis_date, trend_type)`

### Pydantic Schemas

```python
class TrendDataSchema(BaseModel):
    """Données de tendance éditoriale."""
    trend_type: str  # "ngram", "entity", "topic_keyword"
    items: List[dict[str, any]]  # [{"term": "...", "frequency": 42, "trend": "up"}]
    time_series: dict[str, List[float]] | None = None  # Evolution dans le temps
    significance_score: float | None = None  # 0.0 to 1.0
```

---

## 6. bertopic_analysis

**Purpose**: Analyses BERTopic (topics découverts, hiérarchie, évolution temporelle).

### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY, AUTO_INCREMENT | Identifiant unique |
| `analysis_date` | DATE | NOT NULL, INDEXED | Date de l'analyse |
| `time_window_days` | INTEGER | NOT NULL | Fenêtre: 7, 30, ou 90 jours |
| `domains_included` | JSONB | NOT NULL | Liste des domaines analysés (Pydantic: `DomainsListSchema`) |
| `topics` | JSONB | NOT NULL | Topics découverts (Pydantic: `TopicsSchema`) |
| `topic_hierarchy` | JSONB | NULLABLE | Arbre hiérarchique (Pydantic: `TopicHierarchySchema`) |
| `topics_over_time` | JSONB | NULLABLE | Évolution temporelle (Pydantic: `TopicsOverTimeSchema`) |
| `visualizations` | JSONB | NULLABLE | Chemins vers fichiers HTML (Pydantic: `VisualizationsSchema`) |
| `model_parameters` | JSONB | NULLABLE | Paramètres BERTopic utilisés |
| `is_valid` | BOOLEAN | DEFAULT TRUE | Soft delete flag |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW(), INDEXED | Date de création |

### Indexes

- Primary Key: `id`
- Index: `analysis_date`
- Index: `created_at`

### Pydantic Schemas

```python
class DomainsListSchema(BaseModel):
    """Liste des domaines inclus dans l'analyse."""
    domains: List[str]

class TopicsSchema(BaseModel):
    """Topics découverts par BERTopic."""
    topics: List[dict[str, any]]  # [{"id": 0, "keywords": ["...", "..."], "name": "...", "size": 42, "coherence": 0.85}]
    outliers_count: int
    total_articles: int

class TopicHierarchySchema(BaseModel):
    """Hiérarchie des topics."""
    hierarchy: dict[str, any]  # Structure d'arbre JSON
    parent_topics: dict[int, int] | None = None  # topic_id -> parent_topic_id

class TopicsOverTimeSchema(BaseModel):
    """Évolution temporelle des topics."""
    timestamps: List[str]  # Dates
    topic_evolution: dict[int, List[int]]  # topic_id -> [count per timestamp]
    emerging_topics: List[int] | None = None  # IDs des topics émergents

class VisualizationsSchema(BaseModel):
    """Chemins vers visualisations générées."""
    topics_2d: str | None = None  # Path to topics_2d.html
    barchart: str | None = None  # Path to barchart.html
    topics_over_time: str | None = None  # Path to evolution.html
    heatmap: str | None = None  # Path to heatmap.html
```

---

## 7. crawl_cache

**Purpose**: Cache des pages crawlé pour éviter re-crawl inutile.

### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY, AUTO_INCREMENT | Identifiant unique |
| `url` | TEXT | NOT NULL, UNIQUE | URL complète |
| `url_hash` | VARCHAR(64) | NOT NULL, INDEXED | SHA256 hash de l'URL |
| `content_hash` | VARCHAR(64) | NOT NULL, INDEXED | SHA256 hash du contenu (détection changements) |
| `domain` | VARCHAR(255) | NOT NULL, INDEXED | Domaine de l'URL |
| `cached_content` | TEXT | NOT NULL | Contenu textuel mis en cache |
| `cached_metadata` | JSONB | NULLABLE | Métadonnées mises en cache (Pydantic: `CacheMetadataSchema`) |
| `cache_hit_count` | INTEGER | DEFAULT 0 | Nombre de fois utilisé |
| `last_accessed` | TIMESTAMP | NULLABLE | Dernière utilisation du cache |
| `expires_at` | TIMESTAMP | NOT NULL, INDEXED | Date d'expiration (30 jours par défaut) |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Date de création du cache |

### Indexes

- Primary Key: `id`
- Unique: `url`
- Index: `url_hash`
- Index: `content_hash`
- Index: `domain`
- Index: `expires_at` (pour purge automatique)

### Pydantic Schemas

```python
class CacheMetadataSchema(BaseModel):
    """Métadonnées mises en cache."""
    title: str | None = None
    word_count: int | None = None
    last_modified: str | None = None  # HTTP Last-Modified header
    etag: str | None = None  # HTTP ETag
```

---

## 8. scraping_permissions

**Purpose**: Règles robots.txt parsées et mises en cache par domaine.

### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY, AUTO_INCREMENT | Identifiant unique |
| `domain` | VARCHAR(255) | NOT NULL, UNIQUE, INDEXED | Domaine (ex: "example.com") |
| `scraping_allowed` | BOOLEAN | NOT NULL, DEFAULT TRUE | Si scraping autorisé |
| `disallowed_paths` | JSONB | NOT NULL | Chemins interdits (Pydantic: `DisallowedPathsSchema`) |
| `crawl_delay` | INTEGER | NULLABLE | Délai en secondes (robots.txt Crawl-delay) |
| `user_agent_required` | VARCHAR(255) | NULLABLE | User-Agent spécifique requis |
| `robots_txt_content` | TEXT | NULLABLE | Contenu original robots.txt |
| `cache_expires_at` | TIMESTAMP | NOT NULL, INDEXED | Expiration du cache (24h) |
| `last_fetched` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Dernière récupération |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Date de création |
| `updated_at` | TIMESTAMP | NOT NULL, DEFAULT NOW(), ON UPDATE NOW() | Date de mise à jour |

### Indexes

- Primary Key: `id`
- Unique: `domain`
- Index: `cache_expires_at`

### Pydantic Schemas

```python
class DisallowedPathsSchema(BaseModel):
    """Chemins interdits par robots.txt."""
    paths: List[str]  # Ex: ["/admin/", "/private/"]
    patterns: List[str] | None = None  # Regex patterns si applicable
```

---

## 9. performance_metrics

**Purpose**: Métriques détaillées de performance par workflow/agent.

### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY, AUTO_INCREMENT | Identifiant unique |
| `execution_id` | UUID | NOT NULL, FOREIGN KEY, INDEXED | Lien vers `workflow_executions(execution_id)` |
| `agent_name` | VARCHAR(100) | NULLABLE | Nom de l'agent (si applicable) |
| `metric_type` | VARCHAR(100) | NOT NULL | Type: `duration`, `tokens_consumed`, `pages_crawled`, `topics_discovered`, `errors` |
| `metric_value` | NUMERIC(15, 4) | NOT NULL | Valeur de la métrique |
| `metric_unit` | VARCHAR(50) | NULLABLE | Unité: `seconds`, `tokens`, `count`, etc. |
| `additional_data` | JSONB | NULLABLE | Données supplémentaires (Pydantic: `MetricAdditionalDataSchema`) |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW(), INDEXED | Date de création |

### Indexes

- Primary Key: `id`
- Index: `execution_id`
- Index: `metric_type`
- Index: `created_at`
- Composite Index: `(execution_id, metric_type)`
- Foreign Key: `execution_id` → `workflow_executions(execution_id)` ON DELETE CASCADE

### Pydantic Schemas

```python
class MetricAdditionalDataSchema(BaseModel):
    """Données supplémentaires pour une métrique."""
    model_name: str | None = None  # Pour tokens_consumed
    step_name: str | None = None  # Pour duration
    error_type: str | None = None  # Pour errors
    details: dict[str, any] | None = None
```

---

## 10. audit_log

**Purpose**: Logs audit complets de toutes les opérations importantes.

### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY, AUTO_INCREMENT | Identifiant unique |
| `execution_id` | UUID | NULLABLE, FOREIGN KEY, INDEXED | Lien vers workflow (si applicable) |
| `action` | VARCHAR(100) | NOT NULL, INDEXED | Action: `workflow_started`, `agent_executed`, `purge_old_data`, `error_occurred`, etc. |
| `agent_name` | VARCHAR(100) | NULLABLE | Nom de l'agent (si applicable) |
| `step_name` | VARCHAR(100) | NULLABLE | Nom de l'étape |
| `status` | VARCHAR(50) | NOT NULL | Status: `success`, `warning`, `error` |
| `message` | TEXT | NOT NULL | Message de log |
| `details` | JSONB | NULLABLE | Détails supplémentaires (Pydantic: `AuditLogDetailsSchema`) |
| `error_traceback` | TEXT | NULLABLE | Stack trace si erreur |
| `timestamp` | TIMESTAMP | NOT NULL, DEFAULT NOW(), INDEXED | Horodatage |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Date de création |

### Indexes

- Primary Key: `id`
- Index: `execution_id`
- Index: `action`
- Index: `status`
- Index: `timestamp`
- Composite Index: `(execution_id, timestamp)`
- Foreign Key: `execution_id` → `workflow_executions(execution_id)` ON DELETE SET NULL

### Pydantic Schemas

```python
class AuditLogDetailsSchema(BaseModel):
    """Détails supplémentaires pour un log audit."""
    input_data: dict[str, any] | None = None
    output_data: dict[str, any] | None = None
    duration_seconds: float | None = None
    resource_usage: dict[str, any] | None = None  # CPU, memory, etc.
    context: dict[str, any] | None = None  # Contexte additionnel
```

---

## State Transitions

### workflow_executions.status

```
pending → running → completed
pending → running → failed
pending → cancelled
```

### Validation Rules

- `status` ne peut passer de `completed` ou `failed` vers `running`
- `end_time` doit être `NULL` si `status` est `pending` ou `running`
- `was_success` doit être `NULL` si `status` est `pending` ou `running`

---

## Data Retention Policy

- **competitor_articles**: Purge automatique après 90 jours (basé sur `published_date` ou `created_at`)
- **crawl_cache**: Expiration après 30 jours (basé sur `expires_at`)
- **scraping_permissions**: Refresh du cache après 24 heures (basé sur `cache_expires_at`)
- **workflow_executions**: Conservation indéfinie (traçabilité requise)
- **audit_log**: Conservation indéfinie (audit requis)
- **site_profiles**: Conservation indéfinie (référence pour comparaisons)

---

## Validation Rules

### Domain Validation
- Format: `^[a-z0-9.-]+\.[a-z]{2,}$` (regex)
- Pas de protocole (`http://`, `https://`)
- Pas de trailing slash
- Lowercase uniquement

### URL Validation
- Format URL valide
- Protocole `http://` ou `https://`

### Date Validation
- `published_date` ne peut être dans le futur
- `expires_at` doit être dans le futur
- `end_time` doit être >= `start_time` si les deux sont présents

### JSONB Schema Validation
- Tous les champs JSONB doivent être validés avec Pydantic avant insertion
- Utiliser `model_dump_json()` pour sérialisation PostgreSQL

---

**Status**: ✅ **DATA MODEL COMPLETE**  
**Next**: Generate API Contracts and Quickstart Guide