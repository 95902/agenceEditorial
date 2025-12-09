<!-- 76e16a97-3e88-491e-8223-f9730f40d1ee 4a1eb44c-0126-49ef-9a5f-9e93c2bb5845 -->
# Plan de correction des bonnes pratiques Python

## Objectif

Corriger les problèmes de bonnes pratiques Python identifiés dans le codebase pour améliorer la qualité du code, la maintenabilité et la conformité avec PEP 8 et les standards du projet.

## Problèmes identifiés

### 1. Type hints incorrects (CRITIQUE)

**Fichiers concernés :**

- `python_scripts/database/crud_topics.py` (lignes 65-70, 210)
- `python_scripts/ingestion/article_detector.py` (ligne 41)

**Problème :** Utilisation de `any` (minuscule) au lieu de `Any` (majuscule) dans les type hints.

**Impact :** Erreurs mypy, le type `any` n'existe pas en Python standard.

### 2. Gestion d'erreurs trop générique (MOYEN)

**Fichiers concernés :**

- `python_scripts/agents/agent_topic_modeling.py` (5 occurrences)
- `python_scripts/api/routers/trends.py` (3 occurrences)
- `python_scripts/api/routers/trend_pipeline.py` (1 occurrence)

**Problème :** Utilisation excessive de `except Exception` qui masque les erreurs spécifiques.

**Impact :** Difficulté à déboguer et à gérer les erreurs de manière appropriée.

### 3. Type hints pour kwargs (MOYEN)

**Fichiers concernés :**

- `python_scripts/database/crud_profiles.py` (lignes 19, 89)
- `python_scripts/database/crud_articles.py` (ligne 23)

**Problème :** `**kwargs: dict` devrait être `**kwargs: Any` pour plus de précision.

### 4. Comparaisons booléennes explicites (MINEUR)

**Fichiers concernés :**

- `python_scripts/database/crud_executions.py` (lignes 75, 202, 225)
- `python_scripts/database/crud_profiles.py` (lignes 57, 80, 146, 174)

**Problème :** Utilisation de `== True` avec commentaire `# noqa: E712` indiquant un problème de style.

## Modifications à effectuer

### Étape 1 : Corriger les type hints `any` → `Any`

**Fichier :** `python_scripts/database/crud_topics.py`

- Ligne 65 : `domains_included: Dict[str, any]` → `domains_included: Dict[str, Any]`
- Ligne 66 : `topics: Dict[str, any]` → `topics: Dict[str, Any]`
- Ligne 67 : `topic_hierarchy: Optional[Dict[str, any]]` → `topic_hierarchy: Optional[Dict[str, Any]]`
- Ligne 68 : `topics_over_time: Optional[Dict[str, any]]` → `topics_over_time: Optional[Dict[str, Any]]`
- Ligne 69 : `visualizations: Optional[Dict[str, any]]` → `visualizations: Optional[Dict[str, Any]]`
- Ligne 70 : `model_parameters: Optional[Dict[str, any]]` → `model_parameters: Optional[Dict[str, Any]]`
- Ligne 210 : `**kwargs: Dict[str, any]` → `**kwargs: Dict[str, Any]`

**Fichier :** `python_scripts/ingestion/article_detector.py`

- Ligne 41 : Vérifier le type hint et corriger si nécessaire

**Vérification :** S'assurer que `Any` est importé depuis `typing` dans ces fichiers.

### Étape 2 : Améliorer la gestion d'erreurs

**Fichier :** `python_scripts/agents/agent_topic_modeling.py`

- Remplacer les `except Exception` par des exceptions spécifiques quand c'est possible
- Ajouter des exceptions personnalisées appropriées (ex: `TopicModelingError`, `WorkflowError`)
- Conserver `except Exception` uniquement comme dernier recours avec logging approprié

**Fichier :** `python_scripts/api/routers/trends.py`

- Ligne 86 : Spécifier le type d'exception attendu
- Ligne 248-250 : Séparer `HTTPException` et `Exception` (déjà fait, vérifier)
- Ligne 429 : Spécifier le type d'exception pour le parsing JSON
- Ligne 450 : Déjà spécifique `(ValueError, TypeError)` - OK
- Ligne 484-486 : Séparer `HTTPException` et `Exception` (déjà fait, vérifier)

**Fichier :** `python_scripts/api/routers/trend_pipeline.py`

- Ligne 154 : Spécifier le type d'exception ou utiliser une exception personnalisée

### Étape 3 : Améliorer les type hints pour kwargs

**Fichier :** `python_scripts/database/crud_profiles.py`

- Ligne 19 : `**kwargs: dict` → `**kwargs: Any`
- Ligne 89 : `**kwargs: dict` → `**kwargs: Any`

**Fichier :** `python_scripts/database/crud_articles.py`

- Ligne 23 : `**kwargs: dict` → `**kwargs: Any`

**Vérification :** S'assurer que `Any` est importé depuis `typing` dans ces fichiers.

### Étape 4 : Nettoyer les comparaisons booléennes (optionnel)

**Note :** Avec SQLAlchemy, `== True` est acceptable pour les comparaisons de colonnes. Le `# noqa: E712` peut être conservé ou remplacé par `.is_(True)` si souhaité.

**Fichiers :** `python_scripts/database/crud_executions.py`, `python_scripts/database/crud_profiles.py`

- Option A : Conserver `== True` avec `# noqa: E712` (acceptable avec SQLAlchemy)
- Option B : Remplacer par `.is_(True)` pour plus de clarté

## Vérifications post-modification

1. Exécuter `mypy` pour vérifier qu'il n'y a plus d'erreurs de type
2. Exécuter `ruff check` pour vérifier le style
3. Exécuter les tests pour s'assurer qu'aucune régression n'a été introduite
4. Vérifier que tous les imports `Any` sont présents dans les fichiers modifiés

## Fichiers à modifier

1. `python_scripts/database/crud_topics.py` - Correction type hints
2. `python_scripts/ingestion/article_detector.py` - Correction type hints
3. `python_scripts/database/crud_profiles.py` - Correction type hints kwargs
4. `python_scripts/database/crud_articles.py` - Correction type hints kwargs
5. `python_scripts/agents/agent_topic_modeling.py` - Amélioration gestion erreurs
6. `python_scripts/api/routers/trends.py` - Amélioration gestion erreurs
7. `python_scripts/api/routers/trend_pipeline.py` - Amélioration gestion erreurs

## Ordre d'exécution recommandé

1. **Priorité 1** : Corriger les type hints `any` → `Any` (problème critique)
2. **Priorité 2** : Corriger les type hints `kwargs: dict` → `kwargs: Any`
3. **Priorité 3** : Améliorer la gestion d'erreurs (peut être fait progressivement)
4. **Priorité 4** : Nettoyer les comparaisons booléennes (optionnel)

## Tests à effectuer

- Vérifier que mypy passe sans erreurs : `mypy python_scripts/`
- Vérifier que ruff passe : `ruff check python_scripts/`
- Exécuter les tests unitaires : `pytest tests/unit/`
- Exécuter les tests d'intégration : `pytest tests/integration/`

### To-dos

- [ ] Réduire le seuil min_score de KeyBERT de 0.3 à 0.1
- [ ] Corriger la sérialisation des scores N-grams (vérifier make_json_serializable)
- [ ] Ajouter des logs de completion pour TextRank
- [ ] Intégrer Qdrant dans l'analyse hybride pour recherche sémantique et enrichissement
- [ ] Créer un module d'enrichissement sémantique utilisant Qdrant
- [ ] [US7] Implement agent_topic_modeling.py with BERTopic pipeline
- [ ] [US7] Configure BERTopic with optimal hyperparameters in topic_modeling.py
- [ ] [US7] Implement temporal topic evolution analysis
- [ ] [US7] Implement emerging topics detection
- [ ] [US7] Implement topic hierarchy generation
- [ ] [US7] Generate BERTopic visualizations
- [ ] [US7] Save visualizations to configurable path
- [ ] [US7] Implement CRUD operations for BertopicAnalysis
- [ ] [US7] Store BERTopic results in bertopic_analysis table
- [ ] [US7] Link topics to articles via topic_id
- [ ] [US7] Implement POST /api/v1/trends/analyze endpoint
- [ ] [US7] Implement GET /api/v1/trends/topics endpoint
- [ ] [US7] Add request/response schemas for trends
- [ ] [US7] Register trends router in main.py
- [ ] [US7] Integrate BERTopic analysis workflow in orchestrator
- [ ] [US7] Add trends analysis background task runner
- [ ] Améliorer la détection d'articles sur les pages de catégorie comme /actualites/
- [ ] Extraire tous les liens depuis les pages de catégorie et vérifier s'ils sont des articles
- [ ] Utiliser le détecteur d'articles pour identifier les vraies pages d'articles même sans pattern
- [ ] [US5] Create unit test for sitemap detection in tests/unit/test_detect_sitemaps.py
- [ ] Implement agent_competitor.py with multi-source search (Tavily, DuckDuckGo, Crawl4AI)
- [ ] Add competitor search prompts (LLM filtering) in prompts.py
- [ ] Implement LLM filtering logic (phi3:medium) to remove false positives
- [ ] Implement result deduplication and ranking by relevance score
- [ ] Implement POST /api/v1/competitors/search endpoint
- [ ] Implement GET /api/v1/competitors/{domain} endpoint
- [ ] Add request/response schemas for competitor search
- [ ] Register competitors router in main.py
- [ ] Integrate competitor search workflow in agent_orchestrator.py
- [ ] Add competitor search background task runner
- [ ] Créer le dossier python_scripts/agents/competitor/ avec __init__.py
- [ ] Créer config.py avec configuration optimisée (seuils, poids, limites, domaines exclus)
- [ ] Créer query_generator.py avec 6 stratégies et génération de 50+ requêtes
- [ ] Créer filters.py avec PreFilter, DomainFilter, ContentFilter, MediaFilter
- [ ] Créer classifiers.py avec ESNClassifier, BusinessTypeClassifier, RelevanceClassifier, GeographicClassifier
- [ ] Créer enricher.py pour enrichissement homepage, cross-validation, similarité sémantique
- [ ] Créer scorer.py avec scoring multi-critères normalisé et assurance diversité
- [ ] Refactoriser agent_competitor.py pour utiliser les nouveaux modules et implémenter le pipeline 12 étapes
- [ ] Mettre à jour les imports dans competitors.py et autres fichiers utilisant agent_competitor
- [ ] Optimiser la configuration pour permettre 500+ articles par concurrent
- [ ] Implement agent_competitor.py with multi-source search (Tavily, DuckDuckGo, Crawl4AI)
- [ ] Add competitor search prompts (LLM filtering) in prompts.py
- [ ] Implement LLM filtering logic (phi3:medium) to remove false positives
- [ ] Implement result deduplication and ranking by relevance score
- [ ] Implement POST /api/v1/competitors/search endpoint
- [ ] Implement GET /api/v1/competitors/{domain} endpoint
- [ ] Add request/response schemas for competitor search
- [ ] Register competitors router in main.py
- [ ] Integrate competitor search workflow in agent_orchestrator.py
- [ ] Add competitor search background task runner
- [ ] Améliorer la détection d'articles sur les pages de catégorie comme /actualites/
- [ ] Extraire tous les liens depuis les pages de catégorie et vérifier s'ils sont des articles
- [ ] Utiliser le détecteur d'articles pour identifier les vraies pages d'articles même sans pattern
- [ ] [US5] Create unit test for sitemap detection in tests/unit/test_detect_sitemaps.py
- [ ] Implement agent_competitor.py with multi-source search (Tavily, DuckDuckGo, Crawl4AI)
- [ ] Add competitor search prompts (LLM filtering) in prompts.py
- [ ] Implement LLM filtering logic (phi3:medium) to remove false positives
- [ ] Implement result deduplication and ranking by relevance score
- [ ] Implement POST /api/v1/competitors/search endpoint
- [ ] Implement GET /api/v1/competitors/{domain} endpoint
- [ ] Add request/response schemas for competitor search
- [ ] Register competitors router in main.py
- [ ] Integrate competitor search workflow in agent_orchestrator.py
- [ ] Add competitor search background task runner
- [ ] Créer le dossier python_scripts/agents/competitor/ avec __init__.py
- [ ] Créer config.py avec configuration optimisée (seuils, poids, limites, domaines exclus)
- [ ] Créer query_generator.py avec 6 stratégies et génération de 50+ requêtes
- [ ] Créer filters.py avec PreFilter, DomainFilter, ContentFilter, MediaFilter
- [ ] Créer classifiers.py avec ESNClassifier, BusinessTypeClassifier, RelevanceClassifier, GeographicClassifier
- [ ] Créer enricher.py pour enrichissement homepage, cross-validation, similarité sémantique
- [ ] Créer scorer.py avec scoring multi-critères normalisé et assurance diversité
- [ ] Refactoriser agent_competitor.py pour utiliser les nouveaux modules et implémenter le pipeline 12 étapes
- [ ] Mettre à jour les imports dans competitors.py et autres fichiers utilisant agent_competitor
- [ ] Optimiser la configuration pour permettre 500+ articles par concurrent
- [ ] Implement agent_competitor.py with multi-source search (Tavily, DuckDuckGo, Crawl4AI)
- [ ] Add competitor search prompts (LLM filtering) in prompts.py
- [ ] Implement LLM filtering logic (phi3:medium) to remove false positives
- [ ] Implement result deduplication and ranking by relevance score
- [ ] Implement POST /api/v1/competitors/search endpoint
- [ ] Implement GET /api/v1/competitors/{domain} endpoint
- [ ] Add request/response schemas for competitor search
- [ ] Register competitors router in main.py
- [ ] Integrate competitor search workflow in agent_orchestrator.py
- [ ] Add competitor search background task runner
- [ ] [US7] Implement agent_topic_modeling.py with BERTopic pipeline
- [ ] [US7] Configure BERTopic with optimal hyperparameters in topic_modeling.py
- [ ] [US7] Implement temporal topic evolution analysis
- [ ] [US7] Implement emerging topics detection
- [ ] [US7] Implement topic hierarchy generation
- [ ] [US7] Generate BERTopic visualizations
- [ ] [US7] Save visualizations to configurable path
- [ ] [US7] Implement CRUD operations for BertopicAnalysis
- [ ] [US7] Store BERTopic results in bertopic_analysis table
- [ ] [US7] Link topics to articles via topic_id
- [ ] [US7] Implement POST /api/v1/trends/analyze endpoint
- [ ] [US7] Implement GET /api/v1/trends/topics endpoint
- [ ] [US7] Add request/response schemas for trends
- [ ] [US7] Register trends router in main.py
- [ ] [US7] Integrate BERTopic analysis workflow in orchestrator
- [ ] [US7] Add trends analysis background task runner
- [ ] Améliorer la détection d'articles sur les pages de catégorie comme /actualites/
- [ ] Extraire tous les liens depuis les pages de catégorie et vérifier s'ils sont des articles
- [ ] Utiliser le détecteur d'articles pour identifier les vraies pages d'articles même sans pattern
- [ ] [US5] Create unit test for sitemap detection in tests/unit/test_detect_sitemaps.py
- [ ] Implement agent_competitor.py with multi-source search (Tavily, DuckDuckGo, Crawl4AI)
- [ ] Add competitor search prompts (LLM filtering) in prompts.py
- [ ] Implement LLM filtering logic (phi3:medium) to remove false positives
- [ ] Implement result deduplication and ranking by relevance score
- [ ] Implement POST /api/v1/competitors/search endpoint
- [ ] Implement GET /api/v1/competitors/{domain} endpoint
- [ ] Add request/response schemas for competitor search
- [ ] Register competitors router in main.py
- [ ] Integrate competitor search workflow in agent_orchestrator.py
- [ ] Add competitor search background task runner
- [ ] Créer le dossier python_scripts/agents/competitor/ avec __init__.py
- [ ] Créer config.py avec configuration optimisée (seuils, poids, limites, domaines exclus)
- [ ] Créer query_generator.py avec 6 stratégies et génération de 50+ requêtes
- [ ] Créer filters.py avec PreFilter, DomainFilter, ContentFilter, MediaFilter
- [ ] Créer classifiers.py avec ESNClassifier, BusinessTypeClassifier, RelevanceClassifier, GeographicClassifier
- [ ] Créer enricher.py pour enrichissement homepage, cross-validation, similarité sémantique
- [ ] Créer scorer.py avec scoring multi-critères normalisé et assurance diversité
- [ ] Refactoriser agent_competitor.py pour utiliser les nouveaux modules et implémenter le pipeline 12 étapes
- [ ] Mettre à jour les imports dans competitors.py et autres fichiers utilisant agent_competitor
- [ ] Optimiser la configuration pour permettre 500+ articles par concurrent
- [ ] Implement agent_competitor.py with multi-source search (Tavily, DuckDuckGo, Crawl4AI)
- [ ] Add competitor search prompts (LLM filtering) in prompts.py
- [ ] Implement LLM filtering logic (phi3:medium) to remove false positives
- [ ] Implement result deduplication and ranking by relevance score
- [ ] Implement POST /api/v1/competitors/search endpoint
- [ ] Implement GET /api/v1/competitors/{domain} endpoint
- [ ] Add request/response schemas for competitor search
- [ ] Register competitors router in main.py
- [ ] Integrate competitor search workflow in agent_orchestrator.py
- [ ] Add competitor search background task runner
- [ ] Améliorer la détection d'articles sur les pages de catégorie comme /actualites/
- [ ] Extraire tous les liens depuis les pages de catégorie et vérifier s'ils sont des articles
- [ ] Utiliser le détecteur d'articles pour identifier les vraies pages d'articles même sans pattern
- [ ] [US5] Create unit test for sitemap detection in tests/unit/test_detect_sitemaps.py
- [ ] Implement agent_competitor.py with multi-source search (Tavily, DuckDuckGo, Crawl4AI)
- [ ] Add competitor search prompts (LLM filtering) in prompts.py
- [ ] Implement LLM filtering logic (phi3:medium) to remove false positives
- [ ] Implement result deduplication and ranking by relevance score
- [ ] Implement POST /api/v1/competitors/search endpoint
- [ ] Implement GET /api/v1/competitors/{domain} endpoint
- [ ] Add request/response schemas for competitor search
- [ ] Register competitors router in main.py
- [ ] Integrate competitor search workflow in agent_orchestrator.py
- [ ] Add competitor search background task runner
- [ ] Créer le dossier python_scripts/agents/competitor/ avec __init__.py
- [ ] Créer config.py avec configuration optimisée (seuils, poids, limites, domaines exclus)
- [ ] Créer query_generator.py avec 6 stratégies et génération de 50+ requêtes
- [ ] Créer filters.py avec PreFilter, DomainFilter, ContentFilter, MediaFilter
- [ ] Créer classifiers.py avec ESNClassifier, BusinessTypeClassifier, RelevanceClassifier, GeographicClassifier
- [ ] Créer enricher.py pour enrichissement homepage, cross-validation, similarité sémantique
- [ ] Créer scorer.py avec scoring multi-critères normalisé et assurance diversité
- [ ] Refactoriser agent_competitor.py pour utiliser les nouveaux modules et implémenter le pipeline 12 étapes
- [ ] Mettre à jour les imports dans competitors.py et autres fichiers utilisant agent_competitor
- [ ] Optimiser la configuration pour permettre 500+ articles par concurrent
- [ ] Implement agent_competitor.py with multi-source search (Tavily, DuckDuckGo, Crawl4AI)
- [ ] Add competitor search prompts (LLM filtering) in prompts.py
- [ ] Implement LLM filtering logic (phi3:medium) to remove false positives
- [ ] Implement result deduplication and ranking by relevance score
- [ ] Implement POST /api/v1/competitors/search endpoint
- [ ] Implement GET /api/v1/competitors/{domain} endpoint
- [ ] Add request/response schemas for competitor search
- [ ] Register competitors router in main.py
- [ ] Integrate competitor search workflow in agent_orchestrator.py
- [ ] Add competitor search background task runner
- [ ] Supprimer module analysis/hybrid/ (10 fichiers)
- [ ] Supprimer agent_hybrid_trends.py et hybrid_trends router
- [ ] Supprimer crud_hybrid_trends.py et migration
- [ ] Retirer HybridTrendsAnalysis de models.py et schemas
- [ ] Ajouter tables topic_clusters et topic_outliers
- [ ] Creer module analysis/clustering/ (5 fichiers)
- [ ] Creer crud_clusters.py
- [ ] Ajouter table topic_temporal_metrics
- [ ] Creer module analysis/temporal/ (9 fichiers)
- [ ] Creer crud_temporal_metrics.py
- [ ] Ajouter tables trend_analysis, article_recommendations, weak_signals
- [ ] Creer module analysis/llm_enrichment/ (7 fichiers)
- [ ] Creer CRUDs pour trend_analysis et recommendations
- [ ] Ajouter tables coverage, gaps, strengths, roadmap
- [ ] Creer module analysis/gap_analysis/ (8 fichiers)
- [ ] Creer CRUDs pour coverage et gaps
- [ ] Creer agent_trend_pipeline.py orchestrateur
- [ ] Creer router trend_pipeline.py et schemas
- [ ] Creer migration Alembic pour 9 nouvelles tables
- [ ] Creer tests unitaires et integration
- [ ] Réduire le seuil min_score de KeyBERT de 0.3 à 0.1
- [ ] Corriger la sérialisation des scores N-grams (vérifier make_json_serializable)
- [ ] Ajouter des logs de completion pour TextRank
- [ ] Intégrer Qdrant dans l'analyse hybride pour recherche sémantique et enrichissement
- [ ] Créer un module d'enrichissement sémantique utilisant Qdrant
- [ ] [US7] Implement agent_topic_modeling.py with BERTopic pipeline
- [ ] [US7] Configure BERTopic with optimal hyperparameters in topic_modeling.py
- [ ] [US7] Implement temporal topic evolution analysis
- [ ] [US7] Implement emerging topics detection
- [ ] [US7] Implement topic hierarchy generation
- [ ] [US7] Generate BERTopic visualizations
- [ ] [US7] Save visualizations to configurable path
- [ ] [US7] Implement CRUD operations for BertopicAnalysis
- [ ] [US7] Store BERTopic results in bertopic_analysis table
- [ ] [US7] Link topics to articles via topic_id
- [ ] [US7] Implement POST /api/v1/trends/analyze endpoint
- [ ] [US7] Implement GET /api/v1/trends/topics endpoint
- [ ] [US7] Add request/response schemas for trends
- [ ] [US7] Register trends router in main.py
- [ ] [US7] Integrate BERTopic analysis workflow in orchestrator
- [ ] [US7] Add trends analysis background task runner
- [ ] Améliorer la détection d'articles sur les pages de catégorie comme /actualites/
- [ ] Extraire tous les liens depuis les pages de catégorie et vérifier s'ils sont des articles
- [ ] Utiliser le détecteur d'articles pour identifier les vraies pages d'articles même sans pattern
- [ ] [US5] Create unit test for sitemap detection in tests/unit/test_detect_sitemaps.py
- [ ] Implement agent_competitor.py with multi-source search (Tavily, DuckDuckGo, Crawl4AI)
- [ ] Add competitor search prompts (LLM filtering) in prompts.py
- [ ] Implement LLM filtering logic (phi3:medium) to remove false positives
- [ ] Implement result deduplication and ranking by relevance score
- [ ] Implement POST /api/v1/competitors/search endpoint
- [ ] Implement GET /api/v1/competitors/{domain} endpoint
- [ ] Add request/response schemas for competitor search
- [ ] Register competitors router in main.py
- [ ] Integrate competitor search workflow in agent_orchestrator.py
- [ ] Add competitor search background task runner
- [ ] Créer le dossier python_scripts/agents/competitor/ avec __init__.py
- [ ] Créer config.py avec configuration optimisée (seuils, poids, limites, domaines exclus)
- [ ] Créer query_generator.py avec 6 stratégies et génération de 50+ requêtes
- [ ] Créer filters.py avec PreFilter, DomainFilter, ContentFilter, MediaFilter
- [ ] Créer classifiers.py avec ESNClassifier, BusinessTypeClassifier, RelevanceClassifier, GeographicClassifier
- [ ] Créer enricher.py pour enrichissement homepage, cross-validation, similarité sémantique
- [ ] Créer scorer.py avec scoring multi-critères normalisé et assurance diversité
- [ ] Refactoriser agent_competitor.py pour utiliser les nouveaux modules et implémenter le pipeline 12 étapes
- [ ] Mettre à jour les imports dans competitors.py et autres fichiers utilisant agent_competitor
- [ ] Optimiser la configuration pour permettre 500+ articles par concurrent
- [ ] Implement agent_competitor.py with multi-source search (Tavily, DuckDuckGo, Crawl4AI)
- [ ] Add competitor search prompts (LLM filtering) in prompts.py
- [ ] Implement LLM filtering logic (phi3:medium) to remove false positives
- [ ] Implement result deduplication and ranking by relevance score
- [ ] Implement POST /api/v1/competitors/search endpoint
- [ ] Implement GET /api/v1/competitors/{domain} endpoint
- [ ] Add request/response schemas for competitor search
- [ ] Register competitors router in main.py
- [ ] Integrate competitor search workflow in agent_orchestrator.py
- [ ] Add competitor search background task runner
- [ ] Améliorer la détection d'articles sur les pages de catégorie comme /actualites/
- [ ] Extraire tous les liens depuis les pages de catégorie et vérifier s'ils sont des articles
- [ ] Utiliser le détecteur d'articles pour identifier les vraies pages d'articles même sans pattern
- [ ] [US5] Create unit test for sitemap detection in tests/unit/test_detect_sitemaps.py
- [ ] Implement agent_competitor.py with multi-source search (Tavily, DuckDuckGo, Crawl4AI)
- [ ] Add competitor search prompts (LLM filtering) in prompts.py
- [ ] Implement LLM filtering logic (phi3:medium) to remove false positives
- [ ] Implement result deduplication and ranking by relevance score
- [ ] Implement POST /api/v1/competitors/search endpoint
- [ ] Implement GET /api/v1/competitors/{domain} endpoint
- [ ] Add request/response schemas for competitor search
- [ ] Register competitors router in main.py
- [ ] Integrate competitor search workflow in agent_orchestrator.py
- [ ] Add competitor search background task runner
- [ ] Créer le dossier python_scripts/agents/competitor/ avec __init__.py
- [ ] Créer config.py avec configuration optimisée (seuils, poids, limites, domaines exclus)
- [ ] Créer query_generator.py avec 6 stratégies et génération de 50+ requêtes
- [ ] Créer filters.py avec PreFilter, DomainFilter, ContentFilter, MediaFilter
- [ ] Créer classifiers.py avec ESNClassifier, BusinessTypeClassifier, RelevanceClassifier, GeographicClassifier
- [ ] Créer enricher.py pour enrichissement homepage, cross-validation, similarité sémantique
- [ ] Créer scorer.py avec scoring multi-critères normalisé et assurance diversité
- [ ] Refactoriser agent_competitor.py pour utiliser les nouveaux modules et implémenter le pipeline 12 étapes
- [ ] Mettre à jour les imports dans competitors.py et autres fichiers utilisant agent_competitor
- [ ] Optimiser la configuration pour permettre 500+ articles par concurrent
- [ ] Implement agent_competitor.py with multi-source search (Tavily, DuckDuckGo, Crawl4AI)
- [ ] Add competitor search prompts (LLM filtering) in prompts.py
- [ ] Implement LLM filtering logic (phi3:medium) to remove false positives
- [ ] Implement result deduplication and ranking by relevance score
- [ ] Implement POST /api/v1/competitors/search endpoint
- [ ] Implement GET /api/v1/competitors/{domain} endpoint
- [ ] Add request/response schemas for competitor search
- [ ] Register competitors router in main.py
- [ ] Integrate competitor search workflow in agent_orchestrator.py
- [ ] Add competitor search background task runner
- [ ] [US7] Implement agent_topic_modeling.py with BERTopic pipeline
- [ ] [US7] Configure BERTopic with optimal hyperparameters in topic_modeling.py
- [ ] [US7] Implement temporal topic evolution analysis
- [ ] [US7] Implement emerging topics detection
- [ ] [US7] Implement topic hierarchy generation
- [ ] [US7] Generate BERTopic visualizations
- [ ] [US7] Save visualizations to configurable path
- [ ] [US7] Implement CRUD operations for BertopicAnalysis
- [ ] [US7] Store BERTopic results in bertopic_analysis table
- [ ] [US7] Link topics to articles via topic_id
- [ ] [US7] Implement POST /api/v1/trends/analyze endpoint
- [ ] [US7] Implement GET /api/v1/trends/topics endpoint
- [ ] [US7] Add request/response schemas for trends
- [ ] [US7] Register trends router in main.py
- [ ] [US7] Integrate BERTopic analysis workflow in orchestrator
- [ ] [US7] Add trends analysis background task runner
- [ ] Améliorer la détection d'articles sur les pages de catégorie comme /actualites/
- [ ] Extraire tous les liens depuis les pages de catégorie et vérifier s'ils sont des articles
- [ ] Utiliser le détecteur d'articles pour identifier les vraies pages d'articles même sans pattern
- [ ] [US5] Create unit test for sitemap detection in tests/unit/test_detect_sitemaps.py
- [ ] Implement agent_competitor.py with multi-source search (Tavily, DuckDuckGo, Crawl4AI)
- [ ] Add competitor search prompts (LLM filtering) in prompts.py
- [ ] Implement LLM filtering logic (phi3:medium) to remove false positives
- [ ] Implement result deduplication and ranking by relevance score
- [ ] Implement POST /api/v1/competitors/search endpoint
- [ ] Implement GET /api/v1/competitors/{domain} endpoint
- [ ] Add request/response schemas for competitor search
- [ ] Register competitors router in main.py
- [ ] Integrate competitor search workflow in agent_orchestrator.py
- [ ] Add competitor search background task runner
- [ ] Créer le dossier python_scripts/agents/competitor/ avec __init__.py
- [ ] Créer config.py avec configuration optimisée (seuils, poids, limites, domaines exclus)
- [ ] Créer query_generator.py avec 6 stratégies et génération de 50+ requêtes
- [ ] Créer filters.py avec PreFilter, DomainFilter, ContentFilter, MediaFilter
- [ ] Créer classifiers.py avec ESNClassifier, BusinessTypeClassifier, RelevanceClassifier, GeographicClassifier
- [ ] Créer enricher.py pour enrichissement homepage, cross-validation, similarité sémantique
- [ ] Créer scorer.py avec scoring multi-critères normalisé et assurance diversité
- [ ] Refactoriser agent_competitor.py pour utiliser les nouveaux modules et implémenter le pipeline 12 étapes
- [ ] Mettre à jour les imports dans competitors.py et autres fichiers utilisant agent_competitor
- [ ] Optimiser la configuration pour permettre 500+ articles par concurrent
- [ ] Implement agent_competitor.py with multi-source search (Tavily, DuckDuckGo, Crawl4AI)
- [ ] Add competitor search prompts (LLM filtering) in prompts.py
- [ ] Implement LLM filtering logic (phi3:medium) to remove false positives
- [ ] Implement result deduplication and ranking by relevance score
- [ ] Implement POST /api/v1/competitors/search endpoint
- [ ] Implement GET /api/v1/competitors/{domain} endpoint
- [ ] Add request/response schemas for competitor search
- [ ] Register competitors router in main.py
- [ ] Integrate competitor search workflow in agent_orchestrator.py
- [ ] Add competitor search background task runner
- [ ] Améliorer la détection d'articles sur les pages de catégorie comme /actualites/
- [ ] Extraire tous les liens depuis les pages de catégorie et vérifier s'ils sont des articles
- [ ] Utiliser le détecteur d'articles pour identifier les vraies pages d'articles même sans pattern
- [ ] [US5] Create unit test for sitemap detection in tests/unit/test_detect_sitemaps.py
- [ ] Implement agent_competitor.py with multi-source search (Tavily, DuckDuckGo, Crawl4AI)
- [ ] Add competitor search prompts (LLM filtering) in prompts.py
- [ ] Implement LLM filtering logic (phi3:medium) to remove false positives
- [ ] Implement result deduplication and ranking by relevance score
- [ ] Implement POST /api/v1/competitors/search endpoint
- [ ] Implement GET /api/v1/competitors/{domain} endpoint
- [ ] Add request/response schemas for competitor search
- [ ] Register competitors router in main.py
- [ ] Integrate competitor search workflow in agent_orchestrator.py
- [ ] Add competitor search background task runner
- [ ] Créer le dossier python_scripts/agents/competitor/ avec __init__.py
- [ ] Créer config.py avec configuration optimisée (seuils, poids, limites, domaines exclus)
- [ ] Créer query_generator.py avec 6 stratégies et génération de 50+ requêtes
- [ ] Créer filters.py avec PreFilter, DomainFilter, ContentFilter, MediaFilter
- [ ] Créer classifiers.py avec ESNClassifier, BusinessTypeClassifier, RelevanceClassifier, GeographicClassifier
- [ ] Créer enricher.py pour enrichissement homepage, cross-validation, similarité sémantique
- [ ] Créer scorer.py avec scoring multi-critères normalisé et assurance diversité
- [ ] Refactoriser agent_competitor.py pour utiliser les nouveaux modules et implémenter le pipeline 12 étapes
- [ ] Mettre à jour les imports dans competitors.py et autres fichiers utilisant agent_competitor
- [ ] Optimiser la configuration pour permettre 500+ articles par concurrent
- [ ] Implement agent_competitor.py with multi-source search (Tavily, DuckDuckGo, Crawl4AI)
- [ ] Add competitor search prompts (LLM filtering) in prompts.py
- [ ] Implement LLM filtering logic (phi3:medium) to remove false positives
- [ ] Implement result deduplication and ranking by relevance score
- [ ] Implement POST /api/v1/competitors/search endpoint
- [ ] Implement GET /api/v1/competitors/{domain} endpoint
- [ ] Add request/response schemas for competitor search
- [ ] Register competitors router in main.py
- [ ] Integrate competitor search workflow in agent_orchestrator.py
- [ ] Add competitor search background task runner