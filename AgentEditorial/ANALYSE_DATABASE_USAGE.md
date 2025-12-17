# Analyse complète de la base de données après workflow

**Date d'analyse** : 1765973575.1240118

## 📊 Résumé exécutif

- **Total de tables analysées** : 28
- **Tables remplies et utilisées** : 23 ✅
- **Tables remplies mais non utilisées** : 0 ⚠️
- **Tables vides mais utilisées** : 5 ⚠️
- **Tables vides et non utilisées** : 0 ❌

## ✅ 1. Tables remplies et utilisées

Ces tables contiennent des données et sont utilisées dans le code.

| Table | Lignes | Taille | Usage | But |
|-------|--------|--------|-------|-----|
| `url_discovery_scores` | 3376 | 4888 kB | 10 refs | Scores de probabilité pour les URLs découvertes... |
| `competitor_articles` | 1507 | 31 MB | 12 refs | Articles scrapés des sites concurrents... |
| `topic_outliers` | 100 | 80 kB | 9 refs | Articles non classifiés par BERTopic (outliers)... |
| `site_discovery_profiles` | 51 | 168 kB | 10 refs | Profils de découverte optimisés par domaine... |
| `discovery_logs` | 51 | 80 kB | 10 refs | Logs des opérations de découverte... |
| `crawl_cache` | 40 | 2624 kB | 10 refs | Cache des pages crawlé pour éviter les re-scraping... |
| `article_recommendations` | 39 | 136 kB | 14 refs | Recommandations d'articles générées par LLM (Stage... |
| `scraping_permissions` | 36 | 264 kB | 10 refs | Cache des permissions robots.txt par domaine... |
| `client_articles` | 16 | 328 kB | 9 refs | Articles scrapés du site client... |
| `performance_metrics` | 15 | 96 kB | 11 refs | Métriques de performance des workflows... |
| `topic_clusters` | 13 | 208 kB | 23 refs | Clusters thématiques créés par BERTopic (Stage 1 T... |
| `topic_temporal_metrics` | 13 | 56 kB | 11 refs | Métriques temporelles par cluster (Stage 2 Trend P... |
| `trend_analysis` | 13 | 96 kB | 11 refs | Synthèses LLM des tendances par cluster (Stage 3 T... |
| `client_coverage_analysis` | 13 | 88 kB | 9 refs | Analyse de couverture client par topic (Stage 4)... |
| `editorial_gaps` | 13 | 96 kB | 13 refs | Gaps éditoriaux identifiés (Stage 4)... |
| `content_roadmap` | 12 | 56 kB | 11 refs | Roadmap de contenu priorisée (Stage 4)... |
| `audit_log` | 12 | 96 kB | 11 refs | Logs d'audit des actions des agents... |
| `workflow_executions` | 5 | 480 kB | 25 refs | Suivi des exécutions de workflows (sites, competit... |
| `generated_articles` | 2 | 112 kB | 7 refs | Articles générés par le pipeline de génération... |
| `site_profiles` | 1 | 80 kB | 16 refs | Profils éditoriaux des sites clients analysés... |
| `site_analysis_results` | 1 | 96 kB | 12 refs | Résultats détaillés par phase de l'analyse éditori... |
| `trend_pipeline_executions` | 1 | 80 kB | 12 refs | Suivi des exécutions du Trend Pipeline... |
| `generated_article_images` | 1 | 96 kB | 8 refs | Images générées pour les articles... |

## ⚠️ 3. Tables vides mais utilisées dans le code

Ces tables sont référencées dans le code mais sont vides. Raisons possibles :

| Table | Usage | Raison probable |
|-------|-------|------------------|
| `client_strengths` | 9 refs | Workflow non exécuté ou étape sautée |
| `error_logs` | 11 refs | Workflow non exécuté ou étape sautée |
| `generated_article_versions` | 5 refs | Génération d'article non effectuée |
| `generated_images` | 3 refs | Génération d'article non effectuée |
| `weak_signals_analysis` | 9 refs | Workflow non exécuté ou étape sautée |

## 📋 5. Détails complets par table

### `article_recommendations`

- **But** : Recommandations d'articles générées par LLM (Stage 3)
- **Lignes** : 39
- **Taille** : 136 kB
- **Modèle** : `ArticleRecommendation`
- **Score d'utilisation** : 28
- **Références dans le code** :
  - **imports** : 7 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/clear_database.py`
    - ... et 4 autre(s)
  - **crud_usage** : 1 fichier(s)
    - `python_scripts/database/crud_llm_results.py`
  - **api_routes** : 2 fichier(s)
    - `python_scripts/api/routers/trend_pipeline.py`
    - `python_scripts/api/routers/article_enrichment.py`
  - **agents** : 1 fichier(s)
    - `python_scripts/agents/trend_pipeline/article_enrichment/article_enricher.py`
  - **direct_sql** : 3 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/analyze_unused_tables_complete.py`

### `audit_log`

- **But** : Logs d'audit des actions des agents
- **Lignes** : 12
- **Taille** : 96 kB
- **Modèle** : `AuditLog`
- **Score d'utilisation** : 19
- **Références dans le code** :
  - **imports** : 6 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/clear_database.py`
    - ... et 3 autre(s)
  - **crud_usage** : 1 fichier(s)
    - `python_scripts/database/crud_executions.py`
  - **direct_sql** : 4 fichier(s)
    - `scripts/fix_sequences.py`
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - ... et 1 autre(s)

### `client_articles`

- **But** : Articles scrapés du site client
- **Lignes** : 16
- **Taille** : 328 kB
- **Modèle** : `ClientArticle`
- **Score d'utilisation** : 16
- **Références dans le code** :
  - **imports** : 5 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/clear_database.py`
    - ... et 2 autre(s)
  - **crud_usage** : 1 fichier(s)
    - `python_scripts/database/crud_client_articles.py`
  - **direct_sql** : 3 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/analyze_unused_tables_complete.py`

### `client_coverage_analysis`

- **But** : Analyse de couverture client par topic (Stage 4)
- **Lignes** : 13
- **Taille** : 88 kB
- **Modèle** : `ClientCoverageAnalysis`
- **Score d'utilisation** : 16
- **Références dans le code** :
  - **imports** : 5 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/clear_database.py`
    - ... et 2 autre(s)
  - **crud_usage** : 1 fichier(s)
    - `python_scripts/database/crud_coverage.py`
  - **direct_sql** : 3 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/analyze_unused_tables_complete.py`

### `client_strengths`

- **But** : Forces compétitives du client (Stage 4)
- **Lignes** : 0
- **Taille** : 32 kB
- **Modèle** : `ClientStrength`
- **Score d'utilisation** : 16
- **Références dans le code** :
  - **imports** : 5 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/clear_database.py`
    - ... et 2 autre(s)
  - **crud_usage** : 1 fichier(s)
    - `python_scripts/database/crud_coverage.py`
  - **direct_sql** : 3 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/analyze_unused_tables_complete.py`

### `competitor_articles`

- **But** : Articles scrapés des sites concurrents
- **Lignes** : 1507
- **Taille** : 31 MB
- **Modèle** : `CompetitorArticle`
- **Score d'utilisation** : 21
- **Références dans le code** :
  - **imports** : 7 fichier(s)
    - `scripts/migrate_qdrant_to_1024.py`
    - `scripts/index_existing_articles.py`
    - `scripts/analyze_unused_tables.py`
    - ... et 4 autre(s)
  - **crud_usage** : 1 fichier(s)
    - `python_scripts/database/crud_articles.py`
  - **direct_sql** : 4 fichier(s)
    - `scripts/fix_sequences.py`
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - ... et 1 autre(s)

### `content_roadmap`

- **But** : Roadmap de contenu priorisée (Stage 4)
- **Lignes** : 12
- **Taille** : 56 kB
- **Modèle** : `ContentRoadmap`
- **Score d'utilisation** : 21
- **Références dans le code** :
  - **imports** : 6 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/clear_database.py`
    - ... et 3 autre(s)
  - **crud_usage** : 1 fichier(s)
    - `python_scripts/database/crud_gaps.py`
  - **api_routes** : 1 fichier(s)
    - `python_scripts/api/routers/trend_pipeline.py`
  - **direct_sql** : 3 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/analyze_unused_tables_complete.py`

### `crawl_cache`

- **But** : Cache des pages crawlé pour éviter les re-scraping
- **Lignes** : 40
- **Taille** : 2624 kB
- **Modèle** : `CrawlCache`
- **Score d'utilisation** : 17
- **Références dans le code** :
  - **imports** : 5 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/clear_database.py`
    - ... et 2 autre(s)
  - **crud_usage** : 1 fichier(s)
    - `python_scripts/database/crud_crawl_cache.py`
  - **direct_sql** : 4 fichier(s)
    - `scripts/fix_sequences.py`
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - ... et 1 autre(s)

### `discovery_logs`

- **But** : Logs des opérations de découverte
- **Lignes** : 51
- **Taille** : 80 kB
- **Modèle** : `DiscoveryLog`
- **Score d'utilisation** : 18
- **Références dans le code** :
  - **imports** : 5 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/clear_database.py`
    - ... et 2 autre(s)
  - **crud_usage** : 1 fichier(s)
    - `python_scripts/agents/scrapping/crud.py`
  - **agents** : 1 fichier(s)
    - `python_scripts/agents/scrapping/crud.py`
  - **direct_sql** : 3 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/analyze_unused_tables_complete.py`

### `editorial_gaps`

- **But** : Gaps éditoriaux identifiés (Stage 4)
- **Lignes** : 13
- **Taille** : 96 kB
- **Modèle** : `EditorialGap`
- **Score d'utilisation** : 25
- **Références dans le code** :
  - **imports** : 7 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/clear_database.py`
    - ... et 4 autre(s)
  - **crud_usage** : 1 fichier(s)
    - `python_scripts/database/crud_gaps.py`
  - **api_routes** : 1 fichier(s)
    - `python_scripts/api/routers/trend_pipeline.py`
  - **agents** : 1 fichier(s)
    - `python_scripts/agents/trend_pipeline/article_enrichment/article_enricher.py`
  - **direct_sql** : 3 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/analyze_unused_tables_complete.py`

### `error_logs`

- **But** : Logs d'erreurs pour diagnostic
- **Lignes** : 0
- **Taille** : 104 kB
- **Modèle** : `ErrorLog`
- **Score d'utilisation** : 21
- **Références dans le code** :
  - **imports** : 6 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/clear_database.py`
    - ... et 3 autre(s)
  - **crud_usage** : 1 fichier(s)
    - `python_scripts/database/crud_error_logs.py`
  - **api_routes** : 1 fichier(s)
    - `python_scripts/api/routers/errors.py`
  - **direct_sql** : 3 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/analyze_unused_tables_complete.py`

### `generated_article_images`

- **But** : Images générées pour les articles
- **Lignes** : 1
- **Taille** : 96 kB
- **Modèle** : `GeneratedArticleImage`
- **Score d'utilisation** : 17
- **Références dans le code** :
  - **imports** : 5 fichier(s)
    - `scripts/analyze_database_usage.py`
    - `scripts/clear_database.py`
    - `scripts/analyze_image_generation.py`
    - ... et 2 autre(s)
  - **crud_usage** : 2 fichier(s)
    - `python_scripts/database/crud_images.py`
    - `python_scripts/database/crud_generated_articles.py`
  - **direct_sql** : 1 fichier(s)
    - `scripts/analyze_database_usage.py`

### `generated_article_versions`

- **But** : Versions historiques des articles générés
- **Lignes** : 0
- **Taille** : 32 kB
- **Modèle** : `GeneratedArticleVersion`
- **Score d'utilisation** : 10
- **Références dans le code** :
  - **imports** : 3 fichier(s)
    - `scripts/analyze_database_usage.py`
    - `scripts/clear_database.py`
    - `python_scripts/database/crud_generated_articles.py`
  - **crud_usage** : 1 fichier(s)
    - `python_scripts/database/crud_generated_articles.py`
  - **direct_sql** : 1 fichier(s)
    - `scripts/analyze_database_usage.py`

### `generated_articles`

- **But** : Articles générés par le pipeline de génération
- **Lignes** : 2
- **Taille** : 112 kB
- **Modèle** : `GeneratedArticle`
- **Score d'utilisation** : 14
- **Références dans le code** :
  - **imports** : 4 fichier(s)
    - `scripts/analyze_database_usage.py`
    - `scripts/clear_database.py`
    - `scripts/analyze_image_generation.py`
    - ... et 1 autre(s)
  - **crud_usage** : 1 fichier(s)
    - `python_scripts/database/crud_generated_articles.py`
  - **agents** : 1 fichier(s)
    - `python_scripts/agents/article_generation/orchestrator.py`
  - **direct_sql** : 1 fichier(s)
    - `scripts/analyze_database_usage.py`

### `generated_images`

- **But** : Images générées avec Z-Image (standalone)
- **Lignes** : 0
- **Taille** : 64 kB
- **Modèle** : `GeneratedImage`
- **Score d'utilisation** : 5
- **Références dans le code** :
  - **imports** : 2 fichier(s)
    - `scripts/analyze_database_usage.py`
    - `scripts/clear_database.py`
  - **direct_sql** : 1 fichier(s)
    - `scripts/analyze_database_usage.py`

### `performance_metrics`

- **But** : Métriques de performance des workflows
- **Lignes** : 15
- **Taille** : 96 kB
- **Modèle** : `PerformanceMetric`
- **Score d'utilisation** : 19
- **Références dans le code** :
  - **imports** : 6 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/clear_database.py`
    - ... et 3 autre(s)
  - **crud_usage** : 1 fichier(s)
    - `python_scripts/database/crud_executions.py`
  - **direct_sql** : 4 fichier(s)
    - `scripts/fix_sequences.py`
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - ... et 1 autre(s)

### `scraping_permissions`

- **But** : Cache des permissions robots.txt par domaine
- **Lignes** : 36
- **Taille** : 264 kB
- **Modèle** : `ScrapingPermission`
- **Score d'utilisation** : 17
- **Références dans le code** :
  - **imports** : 5 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/clear_database.py`
    - ... et 2 autre(s)
  - **crud_usage** : 1 fichier(s)
    - `python_scripts/database/crud_permissions.py`
  - **direct_sql** : 4 fichier(s)
    - `scripts/fix_sequences.py`
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - ... et 1 autre(s)

### `site_analysis_results`

- **But** : Résultats détaillés par phase de l'analyse éditoriale
- **Lignes** : 1
- **Taille** : 96 kB
- **Modèle** : `SiteAnalysisResult`
- **Score d'utilisation** : 22
- **Références dans le code** :
  - **imports** : 6 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/clear_database.py`
    - ... et 3 autre(s)
  - **crud_usage** : 2 fichier(s)
    - `python_scripts/database/crud_profiles.py`
    - `python_scripts/database/crud_executions.py`
  - **direct_sql** : 4 fichier(s)
    - `scripts/fix_sequences.py`
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - ... et 1 autre(s)

### `site_discovery_profiles`

- **But** : Profils de découverte optimisés par domaine
- **Lignes** : 51
- **Taille** : 168 kB
- **Modèle** : `SiteDiscoveryProfile`
- **Score d'utilisation** : 18
- **Références dans le code** :
  - **imports** : 5 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/clear_database.py`
    - ... et 2 autre(s)
  - **crud_usage** : 1 fichier(s)
    - `python_scripts/agents/scrapping/crud.py`
  - **agents** : 1 fichier(s)
    - `python_scripts/agents/scrapping/crud.py`
  - **direct_sql** : 3 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/analyze_unused_tables_complete.py`

### `site_profiles`

- **But** : Profils éditoriaux des sites clients analysés
- **Lignes** : 1
- **Taille** : 80 kB
- **Modèle** : `SiteProfile`
- **Score d'utilisation** : 31
- **Références dans le code** :
  - **imports** : 9 fichier(s)
    - `scripts/prepare_article_generation_test.py`
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - ... et 6 autre(s)
  - **crud_usage** : 2 fichier(s)
    - `python_scripts/database/crud_profiles.py`
    - `tests/unit/test_crud_profiles.py`
  - **api_routes** : 1 fichier(s)
    - `python_scripts/api/routers/sites.py`
  - **direct_sql** : 4 fichier(s)
    - `scripts/fix_sequences.py`
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - ... et 1 autre(s)

### `topic_clusters`

- **But** : Clusters thématiques créés par BERTopic (Stage 1 Trend Pipeline)
- **Lignes** : 13
- **Taille** : 208 kB
- **Modèle** : `TopicCluster`
- **Score d'utilisation** : 49
- **Références dans le code** :
  - **imports** : 13 fichier(s)
    - `scripts/prepare_article_generation_test.py`
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - ... et 10 autre(s)
  - **crud_usage** : 5 fichier(s)
    - `python_scripts/database/crud_llm_results.py`
    - `python_scripts/database/crud_temporal_metrics.py`
    - `python_scripts/database/crud_coverage.py`
    - ... et 2 autre(s)
  - **api_routes** : 1 fichier(s)
    - `python_scripts/api/routers/trend_pipeline.py`
  - **agents** : 1 fichier(s)
    - `python_scripts/agents/trend_pipeline/article_enrichment/article_enricher.py`
  - **direct_sql** : 3 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/analyze_unused_tables_complete.py`

### `topic_outliers`

- **But** : Articles non classifiés par BERTopic (outliers)
- **Lignes** : 100
- **Taille** : 80 kB
- **Modèle** : `TopicOutlier`
- **Score d'utilisation** : 16
- **Références dans le code** :
  - **imports** : 5 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/clear_database.py`
    - ... et 2 autre(s)
  - **crud_usage** : 1 fichier(s)
    - `python_scripts/database/crud_clusters.py`
  - **direct_sql** : 3 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/analyze_unused_tables_complete.py`

### `topic_temporal_metrics`

- **But** : Métriques temporelles par cluster (Stage 2 Trend Pipeline)
- **Lignes** : 13
- **Taille** : 56 kB
- **Modèle** : `TopicTemporalMetrics`
- **Score d'utilisation** : 20
- **Références dans le code** :
  - **imports** : 6 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/clear_database.py`
    - ... et 3 autre(s)
  - **crud_usage** : 1 fichier(s)
    - `python_scripts/database/crud_temporal_metrics.py`
  - **agents** : 1 fichier(s)
    - `python_scripts/agents/trend_pipeline/article_enrichment/article_enricher.py`
  - **direct_sql** : 3 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/analyze_unused_tables_complete.py`

### `trend_analysis`

- **But** : Synthèses LLM des tendances par cluster (Stage 3 Trend Pipeline)
- **Lignes** : 13
- **Taille** : 96 kB
- **Modèle** : `TrendAnalysis`
- **Score d'utilisation** : 21
- **Références dans le code** :
  - **imports** : 6 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/clear_database.py`
    - ... et 3 autre(s)
  - **crud_usage** : 1 fichier(s)
    - `python_scripts/database/crud_llm_results.py`
  - **api_routes** : 1 fichier(s)
    - `python_scripts/api/routers/trend_pipeline.py`
  - **direct_sql** : 3 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/analyze_unused_tables_complete.py`

### `trend_pipeline_executions`

- **But** : Suivi des exécutions du Trend Pipeline
- **Lignes** : 1
- **Taille** : 80 kB
- **Modèle** : `TrendPipelineExecution`
- **Score d'utilisation** : 22
- **Références dans le code** :
  - **imports** : 7 fichier(s)
    - `scripts/prepare_article_generation_test.py`
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - ... et 4 autre(s)
  - **api_routes** : 1 fichier(s)
    - `python_scripts/api/routers/trend_pipeline.py`
  - **agents** : 1 fichier(s)
    - `python_scripts/agents/trend_pipeline/agent.py`
  - **direct_sql** : 3 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/analyze_unused_tables_complete.py`

### `url_discovery_scores`

- **But** : Scores de probabilité pour les URLs découvertes
- **Lignes** : 3376
- **Taille** : 4888 kB
- **Modèle** : `UrlDiscoveryScore`
- **Score d'utilisation** : 18
- **Références dans le code** :
  - **imports** : 5 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/clear_database.py`
    - ... et 2 autre(s)
  - **crud_usage** : 1 fichier(s)
    - `python_scripts/agents/scrapping/crud.py`
  - **agents** : 1 fichier(s)
    - `python_scripts/agents/scrapping/crud.py`
  - **direct_sql** : 3 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/analyze_unused_tables_complete.py`

### `weak_signals_analysis`

- **But** : Analyse des signaux faibles (outliers groupés)
- **Lignes** : 0
- **Taille** : 24 kB
- **Modèle** : `WeakSignalAnalysis`
- **Score d'utilisation** : 16
- **Références dans le code** :
  - **imports** : 5 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/clear_database.py`
    - ... et 2 autre(s)
  - **crud_usage** : 1 fichier(s)
    - `python_scripts/database/crud_weak_signals.py`
  - **direct_sql** : 3 fichier(s)
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - `scripts/analyze_unused_tables_complete.py`

### `workflow_executions`

- **But** : Suivi des exécutions de workflows (sites, competitors, discovery, etc.)
- **Lignes** : 5
- **Taille** : 480 kB
- **Modèle** : `WorkflowExecution`
- **Score d'utilisation** : 50
- **Références dans le code** :
  - **imports** : 16 fichier(s)
    - `scripts/check_scraping_logs.py`
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - ... et 13 autre(s)
  - **crud_usage** : 1 fichier(s)
    - `python_scripts/database/crud_executions.py`
  - **api_routes** : 3 fichier(s)
    - `python_scripts/api/routers/trend_pipeline.py`
    - `python_scripts/api/routers/competitors.py`
    - `python_scripts/api/routers/discovery.py`
  - **agents** : 1 fichier(s)
    - `python_scripts/agents/agent_orchestrator.py`
  - **direct_sql** : 4 fichier(s)
    - `scripts/fix_sequences.py`
    - `scripts/analyze_unused_tables.py`
    - `scripts/analyze_database_usage.py`
    - ... et 1 autre(s)

## 💡 6. Recommandations

### Tables à vérifier

Les tables suivantes sont utilisées mais vides. Vérifier si le workflow correspondant a été exécuté :

- `client_strengths` : Forces compétitives du client (Stage 4)
- `error_logs` : Logs d'erreurs pour diagnostic
- `generated_article_versions` : Versions historiques des articles générés
- `generated_images` : Images générées avec Z-Image (standalone)
- `weak_signals_analysis` : Analyse des signaux faibles (outliers groupés)

