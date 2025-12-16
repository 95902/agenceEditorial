# Schéma de Base de Données et Fonctionnalités - Route POST /api/v1/discovery/scrape

## Vue d'ensemble

La route `POST /api/v1/discovery/scrape` lance un scraping amélioré avec pipeline de découverte en 4 phases pour découvrir et extraire des articles de manière optimisée.

**Cas d'usage avec `client_domain=innosys.fr`** :
- Récupère automatiquement les concurrents validés depuis une recherche de concurrents précédente
- Scrape les articles de tous les concurrents trouvés
- Utilise un pipeline optimisé de découverte multi-sources

## Flux d'exécution

### Phase initiale : Récupération des domaines

1. **Si `client_domain` fourni** (ex: `innosys.fr`) :
   - Recherche la dernière exécution `competitor_search` complétée pour ce domaine
   - Extrait les domaines des concurrents validés depuis `workflow_executions.output_data.competitors`
   - Force `is_client_site=false` (on scrape les concurrents, pas le client)

2. **Si `domains` fourni directement** :
   - Utilise les domaines fournis directement

3. **Création de l'exécution** → `workflow_executions` (CREATE)

### Pipeline 4 phases (par domaine)

Pour chaque domaine à scraper :

#### **Phase 0 - Profiling** 🔍
- Analyse la structure du site
- Détecte le CMS (WordPress, Drupal, etc.)
- Détecte les APIs REST disponibles
- Découvre les sitemaps
- Découvre les flux RSS
- Identifie les patterns d'URLs
- Détermine les sélecteurs CSS optimaux

#### **Phase 1 - Discovery** 📡
Découverte multi-sources (dans l'ordre de priorité) :
1. **API REST** : Si le site expose une API, récupère les articles via l'API
2. **RSS** : Parse les flux RSS découverts
3. **Sitemap** : Parse les sitemaps XML
4. **Heuristiques** : Découverte par patterns et exploration de pages

#### **Phase 2 - Scoring** 📊
- Calcule un score de probabilité pour chaque URL découverte
- Score basé sur : patterns d'URL, titre, source, etc.
- Trie les URLs par score décroissant
- Sélectionne les meilleures URLs à scraper

#### **Phase 3 - Extraction** ✂️
- Crawl des URLs sélectionnées
- Extraction adaptative selon le profil du site
- Validation du contenu (nombre de mots, qualité, etc.)
- Sauvegarde des articles valides

## Tables impactées

### 1. `workflow_executions` ⭐ **CRITIQUE**
- **Opération** : CREATE, UPDATE, READ
- **Description** : Enregistre l'exécution du workflow de scraping amélioré
- **Champs impactés** :
  - `execution_id` (UUID, unique)
  - `workflow_type` = "enhanced_scraping"
  - `status` : "pending" → "running" → "completed" ou "failed"
  - `input_data` : 
    ```json
    {
      "domains": ["competitor1.fr", "competitor2.fr", ...],
      "max_articles": 100,
      "is_client_site": false,
      "site_profile_id": null,
      "force_reprofile": false,
      "client_domain": "innosys.fr"
    }
    ```
  - `output_data` : 
    ```json
    {
      "domains": ["competitor1.fr", ...],
      "results_by_domain": {
        "competitor1.fr": {
          "articles": [...],
          "statistics": {
            "discovered": 150,
            "scraped": 100,
            "valid": 85
          }
        }
      },
      "total_articles_scraped": 85,
      "statistics": {
        "total_domains": 10,
        "domains_with_articles": 8,
        "domains_without_articles": 2,
        "domains_with_errors": 0,
        "total_articles_discovered": 1200,
        "total_articles_scraped": 850,
        "total_articles_valid": 680
      }
    }
    ```
  - `start_time`, `end_time`, `duration_seconds`
  - `was_success` : true/false
  - `error_message` : si échec

### 2. `workflow_executions` (READ) 📖
- **Opération** : READ uniquement
- **Description** : Lecture de la dernière exécution `competitor_search` pour récupérer les concurrents
- **Requête** :
  ```sql
  SELECT * FROM workflow_executions
  WHERE workflow_type = 'competitor_search'
    AND status = 'completed'
    AND input_data->>'domain' = 'innosys.fr'
  ORDER BY start_time DESC
  LIMIT 1
  ```
- **Données lues** : `output_data.competitors` (liste des concurrents validés)

### 3. `site_discovery_profiles` ⭐ **CRITIQUE**
- **Opération** : CREATE, UPDATE, READ
- **Description** : Profil de découverte optimisé pour chaque domaine
- **Champs impactés** :
  - `domain` (unique)
  - `cms_detected` : CMS détecté (WordPress, Drupal, etc.)
  - `cms_version` : Version du CMS
  - `has_rest_api` : Présence d'API REST
  - `api_endpoints` : Endpoints API découverts (JSONB)
  - `sitemap_urls` : URLs des sitemaps (JSONB array)
  - `rss_feeds` : URLs des flux RSS (JSONB array)
  - `blog_listing_pages` : Pages de listing de blog (JSONB array)
  - `url_patterns` : Patterns d'URLs détectés (JSONB)
  - `article_url_regex` : Regex pour identifier les URLs d'articles
  - `pagination_pattern` : Pattern de pagination
  - `content_selector` : Sélecteur CSS optimal pour le contenu
  - `title_selector` : Sélecteur CSS optimal pour le titre
  - `date_selector` : Sélecteur CSS optimal pour la date
  - `author_selector` : Sélecteur CSS optimal pour l'auteur
  - `image_selector` : Sélecteur CSS optimal pour les images
  - `total_urls_discovered` : Nombre total d'URLs découvertes
  - `total_articles_valid` : Nombre d'articles valides trouvés
  - `success_rate` : Taux de succès (0.0 à 1.0)
  - `avg_article_word_count` : Nombre moyen de mots par article
  - `last_profiled_at` : Date du dernier profilage
  - `last_crawled_at` : Date du dernier crawl
  - `profile_version` : Version du profil
  - `is_active` : Profil actif ou non

### 4. `url_discovery_scores` ⭐ **CRITIQUE**
- **Opération** : CREATE, UPDATE
- **Description** : Scores de probabilité pour chaque URL découverte
- **Champs impactés** :
  - `domain` : Domaine analysé
  - `url` : URL découverte
  - `url_hash` : Hash de l'URL (pour déduplication)
  - `discovery_source` : Source de découverte ("api", "rss", "sitemap", "heuristic")
  - `discovered_in` : Contexte de découverte (ex: "sitemap_index.xml")
  - `initial_score` : Score initial de probabilité (0-100)
  - `final_score` : Score final après validation (peut être mis à jour)
  - `score_breakdown` : Détail du calcul du score (JSONB)
  - `was_scraped` : Indique si l'URL a été scrapée
  - `scrape_status` : Statut du scraping ("success", "failed")
  - `is_valid_article` : Indique si c'est un article valide
  - `validation_reason` : Raison de validation/rejet
  - `title_hint` : Titre suggéré (si disponible depuis la source)
  - `date_hint` : Date suggérée (si disponible depuis la source)
  - `discovered_at` : Date de découverte
  - `scraped_at` : Date de scraping (si scrapée)

### 5. `discovery_logs` 📝
- **Opération** : CREATE
- **Description** : Logs de traçabilité pour chaque opération de découverte
- **Champs impactés** :
  - `domain` : Domaine analysé
  - `execution_id` : ID de l'exécution (FK vers workflow_executions)
  - `operation` : Type d'opération ("discovery", "scraping", "profiling")
  - `phase` : Phase du pipeline ("phase_0", "phase_1", "phase_2", "phase_3")
  - `status` : Statut ("success", "failed", "partial")
  - `urls_found` : Nombre d'URLs trouvées
  - `urls_scraped` : Nombre d'URLs scrapées
  - `urls_valid` : Nombre d'URLs valides
  - `sources_used` : Sources utilisées (JSONB array: ["api", "rss", "sitemap"])
  - `errors` : Liste des erreurs rencontrées (JSONB array)
  - `duration_seconds` : Durée de l'opération
  - `created_at` : Date de création

### 6. `competitor_articles` ⭐ **CRITIQUE**
- **Opération** : CREATE, READ
- **Description** : Articles des concurrents scrapés et validés
- **Champs impactés** :
  - `domain` : Domaine du concurrent
  - `url` : URL de l'article (unique)
  - `url_hash` : Hash de l'URL (indexé)
  - `title` : Titre de l'article
  - `author` : Auteur (optionnel)
  - `published_date` : Date de publication
  - `content_text` : Contenu texte de l'article
  - `content_html` : Contenu HTML brut (optionnel)
  - `word_count` : Nombre de mots
  - `keywords` : Mots-clés extraits (JSONB)
  - `article_metadata` : Métadonnées additionnelles (JSONB)
  - `qdrant_point_id` : ID du point dans Qdrant (après indexation)
  - `topic_id` : ID du topic (peut être null, rempli plus tard)
  - `is_duplicate` : Indique si c'est un doublon
  - `duplicate_of` : ID de l'article original (si doublon)
  - `scraping_permission_id` : Lien vers scraping_permissions

### 7. `client_articles` (si `is_client_site=true`) ⭐ **CONDITIONNEL**
- **Opération** : CREATE, READ
- **Description** : Articles du site client (non utilisé dans le cas `client_domain=innosys.fr`)
- **Note** : Dans le cas `client_domain=innosys.fr`, `is_client_site` est forcé à `false`, donc cette table n'est **PAS** utilisée

### 8. `site_profiles` 📖 **LECTURE SEULE** (si client site)
- **Opération** : READ uniquement
- **Description** : Profil éditorial du site (uniquement si `is_client_site=true`)
- **Note** : Non utilisé dans le cas `client_domain=innosys.fr`

### 9. `scraping_permissions` 📖 **LECTURE SEULE**
- **Opération** : READ uniquement (via cache)
- **Description** : Permissions de scraping (robots.txt)
- **Note** : Utilisé en interne par `crawl_page_async()` pour vérifier les permissions

### 10. `error_logs` 📝
- **Opération** : CREATE
- **Description** : Logs d'erreurs pour diagnostic
- **Champs impactés** (si erreur) :
  - `execution_id` : ID de l'exécution
  - `domain` : Domaine concerné
  - `agent_name` : "enhanced_scraping"
  - `component` : "qdrant", "scraping", "discovery", etc.
  - `error_type` : Type d'erreur
  - `error_message` : Message d'erreur
  - `error_traceback` : Stack trace
  - `context` : Contexte additionnel (JSONB)
  - `severity` : "error", "warning", "critical"

### 11. Qdrant Vector Store 🔍
- **Opération** : CREATE (indexation)
- **Description** : Base de données vectorielle pour recherche sémantique
- **Collections impactées** :
  - `{client_domain}_competitor_articles` : Collection pour les articles de concurrents, nommée selon le domaine du client (ex: `innosys_fr_competitor_articles` si `client_domain=innosys.fr`)
  - `{domain}_client_articles` : Collections par domaine pour les articles clients (non utilisé ici)
  - **Note** : Si `client_domain` n'est pas fourni, utilise la collection par défaut `competitor_articles`
- **Données indexées** :
  - Vector embedding (1024 dimensions, mxbai-embed-large-v1)
  - Payload : `article_id`, `domain`, `title`, `url`, `url_hash`, `published_date`, `author`, `keywords`, `topic_id`
- **Fonctionnalités** :
  - Détection de doublons par similarité (threshold 0.92)
  - Recherche sémantique
  - Filtrage par métadonnées

## Ordre d'impact (par domaine)

### Phase 0 - Profiling
1. `site_discovery_profiles` (READ) - Vérifier si profil existe
2. Si absent ou expiré (>7 jours) :
   - `site_discovery_profiles` (CREATE ou UPDATE) - Créer/mettre à jour le profil

### Phase 1 - Discovery
3. `url_discovery_scores` (CREATE) - Sauvegarder chaque URL découverte avec score initial
4. `discovery_logs` (CREATE) - Logger les résultats de découverte

### Phase 2 - Scoring
5. `url_discovery_scores` (UPDATE) - Mettre à jour les scores et breakdowns

### Phase 3 - Extraction
6. `url_discovery_scores` (UPDATE) - Marquer `was_scraped=true`, `scrape_status`
7. `competitor_articles` (READ) - Vérifier les doublons par `url_hash`
8. `competitor_articles` (CREATE) - Sauvegarder les articles valides
9. Qdrant (CREATE) - Indexer les articles avec embeddings
10. `competitor_articles` (UPDATE) - Mettre à jour `qdrant_point_id`
11. `url_discovery_scores` (UPDATE) - Marquer `is_valid_article`, `final_score`
12. `discovery_logs` (CREATE) - Logger les résultats finaux
13. `error_logs` (CREATE) - Logger les erreurs si nécessaire

### Phase finale
14. `workflow_executions` (UPDATE) - Mettre à jour avec `output_data` complet et `status=completed`

## Structure des données dans output_data

```json
{
  "domains": ["competitor1.fr", "competitor2.fr", "competitor3.fr"],
  "results_by_domain": {
    "competitor1.fr": {
      "articles": [
        {
          "id": 12345,
          "url": "https://competitor1.fr/article-1",
          "title": "Titre de l'article",
          "word_count": 850
        }
      ],
      "statistics": {
        "discovered": 150,
        "scraped": 100,
        "valid": 85,
        "sources_used": ["api", "rss", "sitemap"]
      },
      "error": null
    },
    "competitor2.fr": {
      "articles": [...],
      "statistics": {...},
      "error": null
    }
  },
  "total_articles_scraped": 250,
  "statistics": {
    "total_domains": 3,
    "domains_with_articles": 3,
    "domains_without_articles": 0,
    "domains_with_errors": 0,
    "total_articles_discovered": 450,
    "total_articles_scraped": 300,
    "total_articles_valid": 250
  }
}
```

## Diagramme de flux

```
┌─────────────────────────────────────────────────────────────────┐
│ POST /api/v1/discovery/scrape?client_domain=innosys.fr         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. Récupération des concurrents                                 │
│    - READ workflow_executions (competitor_search)                │
│    - Extraire domains depuis output_data.competitors             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. Création de l'exécution                                      │
│    - CREATE workflow_executions (enhanced_scraping)              │
│    - status: pending                                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Pour chaque domaine (concurrent) :                              │
│                                                                  │
│ ┌────────────────────────────────────────────────────────────┐  │
│ │ PHASE 0 - Profiling                                        │  │
│ │ - READ site_discovery_profiles                            │  │
│ │ - Si absent/expiré: CREATE/UPDATE site_discovery_profiles │  │
│ └────────────────────────────────────────────────────────────┘  │
│                              │                                    │
│                              ▼                                    │
│ ┌────────────────────────────────────────────────────────────┐  │
│ │ PHASE 1 - Discovery                                        │  │
│ │ - API REST → discovered_urls                              │  │
│ │ - RSS → discovered_urls                                    │  │
│ │ - Sitemap → discovered_urls                                │  │
│ │ - Heuristics → discovered_urls                            │  │
│ │ - CREATE url_discovery_scores (pour chaque URL)           │  │
│ │ - CREATE discovery_logs                                    │  │
│ └────────────────────────────────────────────────────────────┘  │
│                              │                                    │
│                              ▼                                    │
│ ┌────────────────────────────────────────────────────────────┐  │
│ │ PHASE 2 - Scoring                                          │  │
│ │ - Calculer score pour chaque URL                           │  │
│ │ - UPDATE url_discovery_scores (score, breakdown)           │  │
│ │ - Trier et sélectionner les meilleures URLs                │  │
│ └────────────────────────────────────────────────────────────┘  │
│                              │                                    │
│                              ▼                                    │
│ ┌────────────────────────────────────────────────────────────┐  │
│ │ PHASE 3 - Extraction                                        │  │
│ │ - Crawl chaque URL sélectionnée                            │  │
│ │ - UPDATE url_discovery_scores (was_scraped, status)       │  │
│ │ - Extraction adaptative                                    │  │
│ │ - Validation du contenu                                    │  │
│ │ - READ competitor_articles (vérifier doublons)             │  │
│ │ - CREATE competitor_articles (si valide et non doublon)    │  │
│ │ - CREATE Qdrant point (indexation vectorielle)             │  │
│ │ - UPDATE competitor_articles (qdrant_point_id)            │  │
│ │ - UPDATE url_discovery_scores (is_valid_article)           │  │
│ └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Finalisation                                                 │
│    - CREATE discovery_logs (résumé final)                       │
│    - UPDATE workflow_executions                                 │
│      * status: completed                                        │
│      * output_data: résultats complets                          │
│      * was_success: true                                        │
└─────────────────────────────────────────────────────────────────┘
```

## Dependencies entre tables

```
workflow_executions (competitor_search)
    └─> output_data.competitors
            └─> domains list
                    └─> workflow_executions (enhanced_scraping)
                            ├─> site_discovery_profiles (per domain)
                            ├─> url_discovery_scores (per URL)
                            ├─> discovery_logs (per operation)
                            ├─> competitor_articles (per article)
                            │       └─> qdrant_point_id → Qdrant
                            └─> error_logs (if errors)
```

## Notes importantes

- ⭐ **CRITIQUE** : Table essentielle pour le fonctionnement de la route
- 📖 **LECTURE SEULE** : Table lue mais non modifiée
- 🔍 **EXTERNE** : Service externe (API, base vectorielle)
- 🔄 **PIPELINE** : Traitement en mémoire, pas d'écriture directe en base
- 📝 **LOGGING** : Table de traçabilité et diagnostic

### Points clés

1. **Mode auto-fetch** : Avec `client_domain=innosys.fr`, la route récupère automatiquement les concurrents depuis une recherche précédente
2. **Pipeline optimisé** : Les 4 phases permettent une découverte et extraction plus efficace que le scraping standard
3. **Profils réutilisables** : Les profils de découverte sont mis en cache et réutilisés (reprofilage après 7 jours)
4. **Scoring intelligent** : Chaque URL reçoit un score de probabilité pour prioriser le scraping
5. **Extraction adaptative** : Les sélecteurs CSS sont adaptés selon le profil du site
6. **Indexation vectorielle** : Tous les articles sont indexés dans Qdrant pour recherche sémantique
7. **Traçabilité complète** : Toutes les opérations sont loggées dans `discovery_logs` et `url_discovery_scores`

### Performance

- Durée typique : ~8 minutes pour 10-50 domaines avec max_articles=100
- Découverte multi-sources : API > RSS > Sitemap > Heuristics (ordre de priorité)
- Cache de profils : Réduit le temps de profilage pour les domaines déjà analysés






