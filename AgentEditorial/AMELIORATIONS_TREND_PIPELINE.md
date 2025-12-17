# Améliorations du Trend Pipeline - Filtrage et Classification des Topics

## Résumé des améliorations

Ce document décrit les améliorations apportées au Trend Pipeline pour permettre le filtrage, la classification et le tri des topics selon une grille Innosys.

## Date d'implémentation
15 décembre 2025

## Objectifs

1. ✅ Compter et filtrer les "vrais" topics (size / cohérence)
2. ✅ Identifier et exposer les axes hors sujet / outliers
3. ✅ Trier / filtrer les résultats par catégorie (`topic_label`)
4. ✅ Fournir une grille de classification Innosys (core/adjacent/off_scope)

## Composants créés

### 1. Module de filtrage (`topic_filters.py`)

**Fichier** : `python_scripts/analysis/article_enrichment/topic_filters.py`

**Fonctionnalités** :
- `classify_topic_label(label: str) -> TopicScope` : Classifier un topic selon la grille Innosys
- `is_major_topic(size, coherence_score, min_size, min_coherence) -> bool` : Déterminer si un topic est "majeur"
- `filter_by_scope(items, scope_filter, label_key) -> list` : Filtrer une liste d'items par scope
- `get_scope_distribution(items, label_key) -> dict` : Calculer la distribution par scope

**Grille de classification** :
- **CORE_KEYWORDS** : cloud, cybersécurité, data, dev, product, conseil IT, etc.
- **ADJACENT_KEYWORDS** : accessibilité, design, réglementation, innovation, RSE tech, etc.
- **OFF_SCOPE_KEYWORDS** : hospitalité, régions, comptabilité, marketing générique, etc.

### 2. Endpoints API enrichis

Tous les endpoints GET du trend-pipeline ont été enrichis avec des query parameters de filtrage :

#### GET `/api/v1/trend-pipeline/{execution_id}/clusters`
**Nouveaux paramètres** :
- `min_size` (int, défaut: 1) : Taille minimale du cluster
- `min_coherence` (float, défaut: 0.0) : Score de cohérence minimum
- `scope` (string, défaut: "all") : Filtre par catégorie ("all", "core", "adjacent", "off_scope")

**Exemples** :
```bash
# Clusters majeurs core (≥20 articles)
curl "http://localhost:8000/api/v1/trend-pipeline/{execution_id}/clusters?min_size=20&scope=core"

# Clusters adjacents avec bonne cohérence
curl "http://localhost:8000/api/v1/trend-pipeline/{execution_id}/clusters?scope=adjacent&min_coherence=0.5"
```

#### GET `/api/v1/trend-pipeline/{execution_id}/gaps`
**Nouveaux paramètres** :
- `scope` (string, défaut: "all") : Filtre par catégorie
- `top_n` (int, optionnel) : Limiter aux N premiers gaps par priorité

**Exemples** :
```bash
# Top 10 gaps core
curl "http://localhost:8000/api/v1/trend-pipeline/{execution_id}/gaps?scope=core&top_n=10"
```

#### GET `/api/v1/trend-pipeline/{execution_id}/roadmap`
**Nouveaux paramètres** :
- `scope` (string, défaut: "all") : Filtre par catégorie
- `max_effort` (string, optionnel: "easy" ou "medium") : Filtre les quick wins

**Exemples** :
```bash
# Quick wins core (effort easy/medium)
curl "http://localhost:8000/api/v1/trend-pipeline/{execution_id}/roadmap?scope=core&max_effort=medium"
```

#### GET `/api/v1/trend-pipeline/{execution_id}/llm-results`
**Nouveaux paramètres** :
- `scope` (string, défaut: "all") : Filtre par catégorie
- `min_differentiation` (float, défaut: 0.0) : Score de différenciation minimum pour les recommandations

**Exemples** :
```bash
# Recommandations core très différenciées (≥0.7)
curl "http://localhost:8000/api/v1/trend-pipeline/{execution_id}/llm-results?scope=core&min_differentiation=0.7"
```

#### GET `/api/v1/trend-pipeline/{execution_id}/outliers` (NOUVEAU)
**Description** : Nouvel endpoint exposant les articles qui n'ont été assignés à aucun cluster (outliers/hors-sujet).

**Paramètres** :
- `max_distance` (float, optionnel) : Distance d'embedding maximum à inclure
- `limit` (int, optionnel) : Nombre maximum d'outliers à retourner
- `domain` (string, optionnel) : Filtrer par domaine

**Réponse** :
```json
{
  "execution_id": "123e4567-...",
  "outliers": [
    {
      "document_id": "doc_123",
      "article_id": 456,
      "domain": "example.com",
      "title": "Article hors-sujet",
      "url": "https://example.com/article",
      "potential_category": "hospitality",
      "embedding_distance": 0.85
    }
  ],
  "total": 15
}
```

**Exemples** :
```bash
# Tous les outliers
curl "http://localhost:8000/api/v1/trend-pipeline/{execution_id}/outliers"

# Top 20 outliers les plus distants
curl "http://localhost:8000/api/v1/trend-pipeline/{execution_id}/outliers?limit=20"
```

### 3. Script d'analyse enrichi

**Fichier** : `scripts/analyze_trend_pipeline_results.py`

**Améliorations** :
- Récupération automatique des données avec filtres (core, quick wins, outliers, etc.)
- Calcul de la distribution par scope (core/adjacent/off_scope)
- Affichage des topics majeurs core (≥20 articles)
- Affichage du top 5 outliers (articles hors-sujet)

**Utilisation** :
```bash
python scripts/analyze_trend_pipeline_results.py <execution_id>
```

**Rapport généré** :
- `outputs/analysis/trend_pipeline_{execution_id}_report.md` : Rapport détaillé en markdown
- `outputs/analysis/trend_pipeline_{execution_id}_data.json` : Données brutes JSON

### 4. Tests

#### Tests unitaires
**Fichier** : `tests/unit/test_topic_filters.py`

**Couverture** :
- Classification des topics (core/adjacent/off_scope)
- Détection des topics majeurs (taille, cohérence)
- Filtrage par scope
- Calcul de distribution

**Lancement** :
```bash
pytest tests/unit/test_topic_filters.py -v
```

#### Tests d'intégration
**Fichier** : `tests/integration/test_trend_pipeline_filters.py`

**Couverture** :
- Endpoints `/clusters` avec filtres
- Endpoints `/gaps` avec filtres
- Endpoints `/roadmap` avec filtres
- Endpoints `/llm-results` avec filtres
- Nouvel endpoint `/outliers`

**Lancement** :
```bash
pytest tests/integration/test_trend_pipeline_filters.py -v
```

### 5. Documentation

#### Documentation technique
**Fichier** : `docs/schema_route_trend_pipeline_analyze.md`

**Ajouts** :
- Section "Nouveaux filtres et classification des topics"
- Documentation complète des query parameters
- Exemples d'utilisation pour chaque endpoint

#### Grille de classification
**Fichier** : `docs/GRILLE_CLASSIFICATION_TOPICS.md`

**Contenu** :
- Description détaillée de la grille Innosys (core/adjacent/off_scope)
- Liste complète des mots-clés par catégorie
- Règles de priorité de classification
- Exemples d'utilisation dans l'API
- Guides d'analyse par scénario (focus core, identifier hors-sujet, explorer adjacents)

## Impact sur les routes existantes

### Routes modifiées
✅ `GET /api/v1/trend-pipeline/{execution_id}/clusters`
✅ `GET /api/v1/trend-pipeline/{execution_id}/gaps`
✅ `GET /api/v1/trend-pipeline/{execution_id}/roadmap`
✅ `GET /api/v1/trend-pipeline/{execution_id}/llm-results`

### Routes créées
✅ `GET /api/v1/trend-pipeline/{execution_id}/outliers`

### Compatibilité ascendante
✅ **Préservée** : Sans query params, les routes se comportent exactement comme avant
✅ Tous les nouveaux paramètres sont optionnels avec des valeurs par défaut

## Cas d'usage

### Cas 1 : Analyse rapide des topics core majeurs
```bash
# 1. Récupérer les clusters majeurs core
curl "http://localhost:8000/api/v1/trend-pipeline/{execution_id}/clusters?scope=core&min_size=20"

# 2. Récupérer les 10 principaux gaps core
curl "http://localhost:8000/api/v1/trend-pipeline/{execution_id}/gaps?scope=core&top_n=10"

# 3. Récupérer les quick wins core
curl "http://localhost:8000/api/v1/trend-pipeline/{execution_id}/roadmap?scope=core&max_effort=medium"
```

**Résultat** : Vue focalisée sur les opportunités à forte valeur ajoutée pour Innosys.

### Cas 2 : Identifier les articles hors-sujet
```bash
# 1. Récupérer tous les clusters off-scope
curl "http://localhost:8000/api/v1/trend-pipeline/{execution_id}/clusters?scope=off_scope"

# 2. Récupérer les outliers
curl "http://localhost:8000/api/v1/trend-pipeline/{execution_id}/outliers?limit=50"
```

**Résultat** : Liste complète des articles non pertinents pour la stratégie éditoriale.

### Cas 3 : Explorer les topics adjacents
```bash
# 1. Récupérer les clusters adjacents
curl "http://localhost:8000/api/v1/trend-pipeline/{execution_id}/clusters?scope=adjacent&min_size=10"

# 2. Récupérer les gaps adjacents
curl "http://localhost:8000/api/v1/trend-pipeline/{execution_id}/gaps?scope=adjacent"
```

**Résultat** : Identification des opportunités "longue traîne" à potentiel.

## Métriques et KPIs

Pour l'analyse `03317802-daf5-443e-9815-7a594570eab0` :

- **Total clusters** : 34
- **Clusters majeurs (≥20 articles)** : ~20
- **Distribution par scope** :
  - Core : Cybersécurité, cloud, data, dev, product, etc.
  - Adjacent : Accessibilité, design, réglementation, innovation, etc.
  - Off-scope : Accueil, régions, comptabilité, RSE autres groupes, etc.

## Fichiers créés/modifiés

### Créés
- `python_scripts/analysis/article_enrichment/topic_filters.py`
- `tests/unit/test_topic_filters.py`
- `tests/integration/test_trend_pipeline_filters.py`
- `docs/GRILLE_CLASSIFICATION_TOPICS.md`
- `AMELIORATIONS_TREND_PIPELINE.md` (ce fichier)

### Modifiés
- `python_scripts/api/routers/trend_pipeline.py` (ajout des query params + endpoint outliers)
- `docs/schema_route_trend_pipeline_analyze.md` (documentation des nouveaux filtres)
- `scripts/analyze_trend_pipeline_results.py` (utilisation des nouveaux filtres)

## Prochaines étapes suggérées

1. **Personnalisation de la grille** : Ajuster les mots-clés dans `topic_filters.py` selon les retours métier
2. **Seuils adaptatifs** : Rendre les seuils de "major topic" configurables par client
3. **Export Excel** : Ajouter un endpoint pour exporter les résultats filtrés en Excel
4. **Dashboard** : Créer une interface web pour visualiser la distribution par scope
5. **Alertes** : Notifier automatiquement si trop d'articles off-scope sont détectés

## Contact

Pour toute question ou suggestion d'amélioration, contacter l'équipe technique.




