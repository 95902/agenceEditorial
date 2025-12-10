# Schéma de Base de Données et Fonctionnalités - Route POST /api/v1/trend-pipeline/analyze

## Vue d'ensemble

La route `POST /api/v1/trend-pipeline/analyze` lance un pipeline d'analyse de tendances en 4 étapes (stages) pour découvrir, analyser et recommander du contenu éditorial basé sur l'analyse des articles des concurrents.

**Pipeline 4 étapes** :
1. **Stage 1 - Clustering** : Découverte de topics via BERTopic + HDBSCAN
2. **Stage 2 - Analyse Temporelle** : Métriques de volume, vélocité, fraîcheur
3. **Stage 3 - Enrichissement LLM** : Synthèse de tendances et recommandations d'articles
4. **Stage 4 - Gap Analysis** : Identification des gaps éditoriaux et roadmap de contenu

## Flux d'exécution

### Phase initiale : Récupération des domaines

1. **Si `client_domain` fourni** (ex: `innosys.fr`) :
   - Recherche la dernière exécution `competitor_search` complétée pour ce domaine
   - Extrait les domaines des concurrents validés depuis `workflow_executions.output_data.competitors`
   - Filtre uniquement les concurrents validés (non exclus)

2. **Si `domains` fourni directement** :
   - Utilise les domaines fournis directement

3. **Création de l'exécution** → `trend_pipeline_executions` (CREATE)

### Pipeline 4 étapes

#### **Stage 1 - Clustering (BERTopic + HDBSCAN)** 🔍
- Récupération des embeddings depuis Qdrant (collection `{client_domain}_competitor_articles`)
- Filtrage par fenêtre temporelle (`time_window_days`, défaut: 365 jours)
- Clustering avec BERTopic + HDBSCAN
- Génération de labels pour chaque cluster
- Calcul des scores de cohérence
- Extraction des outliers (documents non classifiés)
- Catégorisation des outliers

#### **Stage 2 - Analyse Temporelle** 📊
- Calcul de métriques temporelles par topic :
  - **Volume** : Nombre d'articles par fenêtre temporelle
  - **Vélocité** : Taux de croissance du volume
  - **Fraîcheur** : Ratio d'articles récents
  - **Diversité des sources** : Nombre de domaines différents
  - **Score de potentiel** : Score combiné pour priorisation
- Détection de drift (évolution des topics dans le temps)
- Analyse de cohésion

#### **Stage 3 - Enrichissement LLM** 🤖
- Synthèse de tendances pour les top topics (top 10 par score de potentiel)
- Génération de recommandations d'articles :
  - Titre, hook, outline
  - Score de différenciation
  - Niveau d'effort (easy, medium, complex)
- Analyse des angles saturés et opportunités
- Analyse des signaux faibles (outliers)

#### **Stage 4 - Gap Analysis** 🎯
- Analyse de couverture client par topic
- Calcul des scores de couverture et priorité
- Identification des gaps éditoriaux
- Génération d'une roadmap de contenu priorisée
- Identification des forces compétitives du client

## Tables impactées

### 1. `workflow_executions` 📖 **LECTURE SEULE**
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

### 2. `trend_pipeline_executions` ⭐ **CRITIQUE**
- **Opération** : CREATE, UPDATE
- **Description** : Enregistre l'exécution du pipeline de tendances
- **Champs impactés** :
  - `execution_id` (UUID, unique)
  - `client_domain` : Domaine du client (optionnel)
  - `domains_analyzed` : Liste des domaines analysés (JSONB)
  - `time_window_days` : Fenêtre temporelle en jours
  - `stage_1_clustering_status` : "pending" → "in_progress" → "completed" / "failed"
  - `stage_2_temporal_status` : "pending" → "in_progress" → "completed"
  - `stage_3_llm_status` : "pending" → "in_progress" → "completed" / "skipped"
  - `stage_4_gap_status` : "pending" → "in_progress" → "completed" / "skipped"
  - `total_articles` : Nombre total d'articles analysés
  - `total_clusters` : Nombre de clusters découverts
  - `total_outliers` : Nombre d'outliers
  - `total_recommendations` : Nombre de recommandations générées
  - `total_gaps` : Nombre de gaps identifiés
  - `error_message` : Message d'erreur si échec
  - `start_time`, `end_time`, `duration_seconds`

### 3. `topic_clusters` ⭐ **CRITIQUE** (Stage 1)
- **Opération** : CREATE (batch)
- **Description** : Clusters thématiques découverts par BERTopic
- **Champs impactés** :
  - `analysis_id` : ID de l'exécution (FK vers `trend_pipeline_executions.id`)
  - `topic_id` : ID du topic (unique par analysis)
  - `label` : Label généré pour le topic
  - `top_terms` : Top termes du topic (JSONB)
  - `size` : Nombre de documents dans le cluster
  - `centroid_vector_id` : ID du vecteur centroïde (optionnel)
  - `document_ids` : IDs des documents du cluster (JSONB)
  - `coherence_score` : Score de cohérence du cluster
  - `created_at` : Date de création

### 4. `topic_outliers` 📝 (Stage 1)
- **Opération** : CREATE (batch)
- **Description** : Documents non classifiés (outliers, topic_id=-1)
- **Champs impactés** :
  - `analysis_id` : ID de l'exécution
  - `document_id` : ID du document
  - `article_id` : ID de l'article (optionnel)
  - `potential_category` : Catégorie potentielle suggérée
  - `embedding_distance` : Distance au cluster le plus proche
  - `created_at` : Date de création

### 5. `topic_temporal_metrics` ⭐ **CRITIQUE** (Stage 2)
- **Opération** : CREATE
- **Description** : Métriques temporelles par topic et fenêtre temporelle
- **Champs impactés** :
  - `topic_cluster_id` : ID du cluster (FK vers `topic_clusters.id`)
  - `window_start` : Début de la fenêtre temporelle
  - `window_end` : Fin de la fenêtre temporelle
  - `volume` : Nombre d'articles dans la fenêtre
  - `velocity` : Taux de croissance (vélocité)
  - `freshness_ratio` : Ratio d'articles récents
  - `source_diversity` : Nombre de domaines sources différents
  - `cohesion_score` : Score de cohésion du topic
  - `potential_score` : Score de potentiel (pour priorisation)
  - `drift_detected` : Indique si un drift a été détecté
  - `drift_distance` : Distance du drift (si détecté)
  - `created_at` : Date de création

### 6. `trend_analysis` ⭐ **CRITIQUE** (Stage 3)
- **Opération** : CREATE
- **Description** : Synthèses de tendances générées par LLM
- **Champs impactés** :
  - `topic_cluster_id` : ID du cluster (FK vers `topic_clusters.id`)
  - `synthesis` : Synthèse de la tendance (texte généré par LLM)
  - `saturated_angles` : Angles saturés identifiés (JSONB)
  - `opportunities` : Opportunités identifiées (JSONB)
  - `llm_model_used` : Modèle LLM utilisé (ex: "llama3", "mistral")
  - `processing_time_seconds` : Temps de traitement
  - `created_at` : Date de création

### 7. `article_recommendations` ⭐ **CRITIQUE** (Stage 3)
- **Opération** : CREATE
- **Description** : Recommandations d'articles générées par LLM
- **Champs impactés** :
  - `topic_cluster_id` : ID du cluster (FK vers `topic_clusters.id`)
  - `title` : Titre de l'article recommandé
  - `hook` : Accroche de l'article
  - `outline` : Plan de l'article (JSONB)
  - `differentiation_score` : Score de différenciation
  - `effort_level` : Niveau d'effort ("easy", "medium", "complex")
  - `status` : Statut ("suggested", "approved", "in_progress", "published")
  - `created_at` : Date de création

### 8. `weak_signals_analysis` 📝 (Stage 3)
- **Opération** : CREATE
- **Description** : Analyse des signaux faibles (outliers)
- **Champs impactés** :
  - `analysis_id` : ID de l'exécution
  - `outlier_ids` : IDs des outliers analysés (JSONB)
  - `common_thread` : Fil conducteur commun identifié
  - `disruption_potential` : Potentiel de disruption
  - `recommendation` : Recommandation ("early_adopter", "wait", "monitor")
  - `llm_model_used` : Modèle LLM utilisé
  - `created_at` : Date de création

### 9. `client_coverage_analysis` ⭐ **CRITIQUE** (Stage 4)
- **Opération** : CREATE
- **Description** : Analyse de couverture client par topic
- **Champs impactés** :
  - `domain` : Domaine du client
  - `topic_cluster_id` : ID du cluster (FK vers `topic_clusters.id`)
  - `client_article_count` : Nombre d'articles du client sur ce topic
  - `coverage_score` : Score de couverture (0.0 à 1.0)
  - `avg_distance_to_centroid` : Distance moyenne au centroïde
  - `analysis_date` : Date de l'analyse

### 10. `editorial_gaps` ⭐ **CRITIQUE** (Stage 4)
- **Opération** : CREATE
- **Description** : Gaps éditoriaux identifiés
- **Champs impactés** :
  - `client_domain` : Domaine du client
  - `topic_cluster_id` : ID du cluster (FK vers `topic_clusters.id`)
  - `coverage_score` : Score de couverture (faible = gap)
  - `priority_score` : Score de priorité (pour tri)
  - `diagnostic` : Diagnostic du gap
  - `opportunity_description` : Description de l'opportunité
  - `risk_assessment` : Évaluation des risques
  - `created_at` : Date de création

### 11. `client_strengths` 📝 (Stage 4)
- **Opération** : CREATE
- **Description** : Forces compétitives du client (topics où le client surperforme)
- **Champs impactés** :
  - `domain` : Domaine du client
  - `topic_cluster_id` : ID du cluster (FK vers `topic_clusters.id`)
  - `advantage_score` : Score d'avantage compétitif
  - `description` : Description de la force
  - `created_at` : Date de création

### 12. `content_roadmap` ⭐ **CRITIQUE** (Stage 4)
- **Opération** : CREATE
- **Description** : Roadmap de contenu priorisée
- **Champs impactés** :
  - `client_domain` : Domaine du client
  - `gap_id` : ID du gap (FK vers `editorial_gaps.id`)
  - `recommendation_id` : ID de la recommandation (FK vers `article_recommendations.id`)
  - `priority_order` : Ordre de priorité (1, 2, 3, ...)
  - `estimated_effort` : Effort estimé ("easy", "medium", "complex")
  - `status` : Statut ("pending", "in_progress", "completed")
  - `created_at` : Date de création

### 13. Qdrant Vector Store 🔍 **LECTURE SEULE**
- **Opération** : READ uniquement
- **Description** : Base de données vectorielle pour récupération des embeddings
- **Collections utilisées** :
  - `{client_domain}_competitor_articles` : Collection des articles concurrents (ex: `innosys_fr_competitor_articles` si `client_domain=innosys.fr`)
  - **Note** : Le nom de collection est généré automatiquement depuis `client_domain` via `get_competitor_collection_name()`
  - **Filtres** :
    - Par domaines (domains list)
    - Par fenêtre temporelle (`max_age_days`)
- **Données lues** :
  - Embeddings (vecteurs 1024 dimensions)
  - Métadonnées : `domain`, `title`, `content_text`, `published_date`, `url`, etc.

### 14. `competitor_articles` 📖 **LECTURE SEULE** (via Qdrant)
- **Opération** : READ indirect (via Qdrant)
- **Description** : Articles des concurrents utilisés pour l'analyse
- **Note** : Les articles sont récupérés via Qdrant, pas directement depuis PostgreSQL

## Ordre d'impact par étape

### Phase initiale
1. `workflow_executions` (READ) - Récupération des concurrents si `client_domain` fourni
2. `trend_pipeline_executions` (CREATE) - Création de l'exécution

### Stage 1 - Clustering
3. Qdrant (READ) - Récupération des embeddings et métadonnées
4. `topic_clusters` (CREATE batch) - Sauvegarde des clusters
5. `topic_outliers` (CREATE batch) - Sauvegarde des outliers
6. `trend_pipeline_executions` (UPDATE) - Mise à jour du statut et statistiques

### Stage 2 - Analyse Temporelle
7. `topic_temporal_metrics` (CREATE) - Sauvegarde des métriques temporelles
8. `trend_pipeline_executions` (UPDATE) - Mise à jour du statut

### Stage 3 - Enrichissement LLM
9. `trend_analysis` (CREATE) - Sauvegarde des synthèses de tendances
10. `article_recommendations` (CREATE) - Sauvegarde des recommandations
11. `weak_signals_analysis` (CREATE) - Sauvegarde de l'analyse des signaux faibles (optionnel)
12. `trend_pipeline_executions` (UPDATE) - Mise à jour du statut et `total_recommendations`

### Stage 4 - Gap Analysis
13. `client_coverage_analysis` (CREATE) - Analyse de couverture par topic
14. `editorial_gaps` (CREATE) - Identification des gaps
15. `client_strengths` (CREATE) - Identification des forces (optionnel)
16. `content_roadmap` (CREATE) - Génération de la roadmap
17. `trend_pipeline_executions` (UPDATE) - Mise à jour du statut et `total_gaps`

### Phase finale
18. `trend_pipeline_executions` (UPDATE) - Finalisation avec `end_time` et `duration_seconds`

## Structure des données

### Request Body
```json
{
  "client_domain": "innosys.fr",
  "domains": null,
  "time_window_days": 365,
  "skip_llm": false,
  "skip_gap_analysis": false
}
```

### Response (ExecutionResponse)
```json
{
  "execution_id": "uuid",
  "status": "accepted",
  "start_time": null,
  "estimated_duration_minutes": 10
}
```

## Diagramme de flux

```
┌─────────────────────────────────────────────────────────────────┐
│ POST /api/v1/trend-pipeline/analyze                            │
│ { client_domain: "innosys.fr", time_window_days: 365 }        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Phase Initiale : Récupération des domaines                    │
│ - READ workflow_executions (competitor_search)                  │
│ - Extraire domains depuis output_data.competitors               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Création de l'exécution                                         │
│ - CREATE trend_pipeline_executions                              │
│   * execution_id, client_domain, domains_analyzed               │
│   * time_window_days, status: pending                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 1 - Clustering (BERTopic + HDBSCAN)                      │
│                                                                  │
│ 1. READ Qdrant ({client_domain}_competitor_articles)            │
│    - Filtre par domains et time_window_days                     │
│    - Récupère embeddings + métadonnées                          │
│                                                                  │
│ 2. Clustering BERTopic + HDBSCAN                               │
│    - Génération de topics                                       │
│    - Calcul de centroïdes                                       │
│                                                                  │
│ 3. Génération de labels                                         │
│    - Labels automatiques pour chaque topic                       │
│    - Calcul de cohérence                                        │
│                                                                  │
│ 4. Extraction d'outliers                                        │
│    - Documents non classifiés (topic_id=-1)                    │
│    - Catégorisation                                            │
│                                                                  │
│ 5. CREATE topic_clusters (batch)                                │
│ 6. CREATE topic_outliers (batch)                                │
│ 7. UPDATE trend_pipeline_executions                             │
│    * stage_1_clustering_status: completed                       │
│    * total_clusters, total_outliers, total_articles             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 2 - Analyse Temporelle                                   │
│                                                                  │
│ 1. Calcul de métriques par topic                                │
│    - Volume (articles par fenêtre)                              │
│    - Vélocité (taux de croissance)                              │
│    - Fraîcheur (ratio articles récents)                         │
│    - Diversité sources                                         │
│    - Score de potentiel                                        │
│                                                                  │
│ 2. Détection de drift                                           │
│    - Évolution des topics dans le temps                         │
│                                                                  │
│ 3. CREATE topic_temporal_metrics                                │
│ 4. UPDATE trend_pipeline_executions                             │
│    * stage_2_temporal_status: completed                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 3 - Enrichissement LLM                                   │
│ (si skip_llm=false)                                             │
│                                                                  │
│ Pour chaque top topic (top 10 par potential_score) :          │
│                                                                  │
│ 1. Synthèse de tendance                                         │
│    - Appel LLM (Llama3, Mistral, etc.)                         │
│    - Génération de synthèse                                     │
│    - Identification angles saturés / opportunités              │
│    - CREATE trend_analysis                                      │
│                                                                  │
│ 2. Recommandations d'articles                                  │
│    - Génération titre, hook, outline                            │
│    - Calcul score de différenciation                            │
│    - Détermination niveau d'effort                              │
│    - CREATE article_recommendations                             │
│                                                                  │
│ 3. Analyse signaux faibles (optionnel)                          │
│    - Analyse des outliers                                       │
│    - CREATE weak_signals_analysis                                │
│                                                                  │
│ 4. UPDATE trend_pipeline_executions                             │
│    * stage_3_llm_status: completed                             │
│    * total_recommendations                                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 4 - Gap Analysis                                          │
│ (si skip_gap_analysis=false et client_domain fourni)            │
│                                                                  │
│ 1. Analyse de couverture client                                 │
│    - Comparaison articles client vs concurrents                 │
│    - Calcul coverage_score par topic                            │
│    - CREATE client_coverage_analysis                            │
│                                                                  │
│ 2. Identification des gaps                                      │
│    - Topics avec faible couverture                              │
│    - Calcul priority_score                                      │
│    - Génération diagnostic et opportunités                      │
│    - CREATE editorial_gaps                                      │
│                                                                  │
│ 3. Identification des forces                                    │
│    - Topics où client surperforme                               │
│    - CREATE client_strengths                                    │
│                                                                  │
│ 4. Génération roadmap                                           │
│    - Association gaps → recommandations                          │
│    - Priorisation (priority_order)                              │
│    - CREATE content_roadmap                                     │
│                                                                  │
│ 5. UPDATE trend_pipeline_executions                             │
│    * stage_4_gap_status: completed                             │
│    * total_gaps                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Finalisation                                                    │
│ - UPDATE trend_pipeline_executions                              │
│   * end_time, duration_seconds                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Dependencies entre tables

```
workflow_executions (competitor_search)
    └─> output_data.competitors
            └─> domains list
                    └─> trend_pipeline_executions
                            ├─> topic_clusters (Stage 1)
                            │       ├─> topic_temporal_metrics (Stage 2)
                            │       ├─> trend_analysis (Stage 3)
                            │       ├─> article_recommendations (Stage 3)
                            │       ├─> client_coverage_analysis (Stage 4)
                            │       ├─> editorial_gaps (Stage 4)
                            │       └─> client_strengths (Stage 4)
                            ├─> topic_outliers (Stage 1)
                            │       └─> weak_signals_analysis (Stage 3)
                            └─> content_roadmap (Stage 4)
                                    ├─> editorial_gaps (FK)
                                    └─> article_recommendations (FK)
```

## Endpoints associés

### GET /api/v1/trend-pipeline/{execution_id}/status
- Récupère le statut de l'exécution
- Retourne : statuts des 4 étapes, totaux (clusters, gaps), durée

### GET /api/v1/trend-pipeline/{execution_id}/clusters
- Récupère les clusters découverts
- Retourne : liste des clusters avec labels, tailles, scores

### GET /api/v1/trend-pipeline/{execution_id}/gaps
- Récupère les gaps éditoriaux identifiés
- Retourne : liste des gaps avec scores de priorité

### GET /api/v1/trend-pipeline/{execution_id}/roadmap
- Récupère la roadmap de contenu
- Retourne : roadmap priorisée avec recommandations

### GET /api/v1/trend-pipeline/{execution_id}/llm-results
- Récupère les résultats LLM (synthèses + recommandations)
- Retourne : synthèses de tendances et recommandations d'articles

## Notes importantes

- ⭐ **CRITIQUE** : Table essentielle pour le fonctionnement de la route
- 📖 **LECTURE SEULE** : Table lue mais non modifiée
- 🔍 **EXTERNE** : Service externe (Qdrant, LLM)
- 📝 **LOGGING** : Table de traçabilité

### Points clés

1. **Mode auto-fetch** : Avec `client_domain`, récupère automatiquement les concurrents depuis une recherche précédente
2. **Pipeline séquentiel** : Les 4 étapes s'exécutent séquentiellement, chaque étape dépend de la précédente
3. **Skip options** : Possibilité de sauter l'enrichissement LLM (`skip_llm`) ou l'analyse de gaps (`skip_gap_analysis`)
4. **Fenêtre temporelle** : Filtre les articles par `time_window_days` (défaut: 365 jours)
5. **Top topics** : Seuls les top 10 topics (par `potential_score`) sont enrichis par LLM
6. **Gap analysis conditionnelle** : Nécessite `client_domain` et `skip_gap_analysis=false`
7. **Performance** : Durée estimée ~10 minutes pour une analyse complète

### Performance et limitations

- **Durée typique** : ~10 minutes pour une analyse complète
- **Minimum d'articles** : Nécessite un minimum d'articles (configurable, défaut: ~50)
- **Coût LLM** : L'enrichissement LLM peut être coûteux (appels multiples)
- **Scalabilité** : Le clustering peut être lent avec beaucoup d'articles (>10k)

