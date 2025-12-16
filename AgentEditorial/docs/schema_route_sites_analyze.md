# Schéma de Base de Données Impactée - Route POST /api/v1/sites/analyze

## Vue d'ensemble

La route `POST /api/v1/sites/analyze` lance une analyse éditoriale complète d'un domaine. Elle impacte plusieurs tables de la base de données lors de son exécution.

## Flux d'exécution

1. **Création de l'exécution** → `workflow_executions`
2. **Découverte des URLs** (sitemap)
3. **Crawl des pages** → (pas de cache utilisé)
4. **Analyse LLM** → `site_analysis_results`
5. **Création/Mise à jour du profil** → `site_profiles`
6. **Scraping automatique du site client** → `client_articles`, `site_discovery_profiles`, `url_discovery_scores`, `discovery_logs`

## Tables impactées

> ⚠️ **Note importante** : Les tables `scraping_permissions` et `crawl_cache` existent dans le schéma mais **ne sont pas utilisées** dans ce workflow. Elles sont listées ci-dessous pour information mais ne sont pas impactées.

### 1. `workflow_executions` ⭐ **CRITIQUE**
- **Opération** : CREATE, UPDATE
- **Description** : Enregistre l'exécution du workflow d'analyse éditoriale
- **Champs impactés** :
  - `execution_id` (UUID, unique)
  - `workflow_type` = "editorial_analysis"
  - `status` : "pending" → "running" → "completed" ou "failed"
  - `input_data` : `{"domain": "...", "max_pages": ...}`
  - `output_data` : Résultats de l'analyse
  - `start_time`, `end_time`, `duration_seconds`
  - `was_success` : true/false
  - `error_message` : si échec

### 2. `site_profiles` ⭐ **CRITIQUE**
- **Opération** : CREATE ou UPDATE
- **Description** : Profil éditorial du site analysé
- **Champs impactés** :
  - `domain` (unique)
  - `analysis_date`
  - `language_level`
  - `editorial_tone`
  - `target_audience` (JSONB)
  - `activity_domains` (JSONB)
  - `content_structure` (JSONB)
  - `keywords` (JSONB)
  - `style_features` (JSONB)
  - `pages_analyzed`
  - `llm_models_used` (JSONB)

### 3. `site_analysis_results` ⭐ **CRITIQUE**
- **Opération** : CREATE
- **Description** : Résultats détaillés de l'analyse par phase
- **Champs impactés** :
  - `site_profile_id` (FK → `site_profiles.id`)
  - `execution_id` (FK → `workflow_executions.execution_id`)
  - `analysis_phase` = "synthesis"
  - `phase_results` (JSONB) : Résultats complets de l'analyse LLM
  - `llm_model_used`
  - `processing_time_seconds`

### 4. `scraping_permissions` ❌ **NON UTILISÉE**
- **Opération** : Aucune
- **Description** : Cache des permissions robots.txt (table créée mais non utilisée dans ce workflow)
- **Note** : 
  - La table existe et les fonctions CRUD existent dans `crud_permissions.py`
  - La fonction `parse_robots_txt()` utilise bien le cache, mais elle n'est **pas appelée** dans le workflow d'analyse
  - Le workflow utilise `check_robots_txt()` qui ne prend pas de `db_session` et n'utilise pas le cache
  - **Cette table n'est donc pas impactée par cette route**

### 5. `crawl_cache` ❌ **NON UTILISÉE**
- **Opération** : Aucune
- **Description** : Cache des pages crawléees (table créée mais non implémentée)
- **Note** :
  - La table existe dans le modèle mais **aucune fonction CRUD n'existe**
  - Le paramètre `check_cache` dans `crawl_page_async()` est marqué comme "not used, kept for API compatibility"
  - **Cette table n'est donc pas impactée par cette route**

### 6. `client_articles` 📝 **SCRAPING AUTOMATIQUE**
- **Opération** : CREATE
- **Description** : Articles du site client scrapés automatiquement après l'analyse
- **Champs impactés** :
  - `site_profile_id` (FK → `site_profiles.id`)
  - `url` (unique)
  - `url_hash`
  - `title`
  - `author`
  - `published_date`
  - `content_text`
  - `content_html`
  - `word_count`
  - `keywords` (JSONB)
  - `article_metadata` (JSONB)
  - `qdrant_point_id` (si indexation Qdrant activée)
  - `topic_id` (si topic modeling effectué)



## Diagramme de relations

```
workflow_executions (1)
    │
    ├──> site_analysis_results (N)
    │
site_profiles (1)
    │
    ├──> site_analysis_results (N)
    │
    ├──> client_articles (N) [via scraping automatique]
    │


❌ scraping_permissions (non utilisée dans ce workflow)
❌ crawl_cache (non utilisée dans ce workflow)
```

## Ordre d'impact

1. **Phase initiale** :
   - `workflow_executions` (CREATE)

2. **Phase crawl** :
   - (Aucune table de cache utilisée - les fonctions de cache ne sont pas appelées)

3. **Phase analyse** :
   - `site_profiles` (READ ou CREATE)
   - `site_analysis_results` (CREATE)
   - `workflow_executions` (UPDATE)

4. **Phase scraping automatique** (optionnel, en arrière-plan) :
   - `site_discovery_profiles` (CREATE ou UPDATE)
   - `url_discovery_scores` (CREATE ou UPDATE)
   - `client_articles` (CREATE)
   - `discovery_logs` (CREATE)

## Notes importantes

- ⭐ **CRITIQUE** : Tables essentielles pour le fonctionnement de la route
- ❌ **NON UTILISÉES** : Tables créées mais non utilisées dans ce workflow
- 📝 **SCRAPING AUTOMATIQUE** : Tables créées lors du scraping automatique du site client (étape 9 du workflow)

- Le scraping automatique est lancé en arrière-plan et ne bloque pas la réponse de l'API
- Les erreurs de scraping n'interrompent pas le workflow principal
- ⚠️ **Les tables `scraping_permissions` et `crawl_cache` ne sont pas utilisées** : 
  - `scraping_permissions` : Les fonctions CRUD existent mais `parse_robots_txt()` n'est pas appelée dans le workflow
  - `crawl_cache` : Aucune fonction CRUD n'existe, le paramètre `check_cache` est ignoré

## Contraintes de clés étrangères

- `site_analysis_results.site_profile_id` → `site_profiles.id` (CASCADE)
- `site_analysis_results.execution_id` → `workflow_executions.execution_id` (CASCADE)
- `client_articles.site_profile_id` → `site_profiles.id`
- `url_discovery_scores.domain` → `site_discovery_profiles.domain` (logique, pas FK)









