# Grille de Classification des Topics Innosys

## Vue d'ensemble

Cette grille permet de classifier automatiquement les topics découverts par le Trend Pipeline en trois catégories :
- **Core** : Topics cœur de cible Innosys
- **Adjacent** : Topics adjacents intéressants
- **Off-scope** : Topics hors-scope ou faible priorité

## Classification des topics

### Core (Cœur de cible Innosys)

Topics directement liés au cœur de métier d'Innosys : conseil IT, cloud, cybersécurité, data, développement, product management.

**Mots-clés identifiants** :
- **Cloud & Infrastructure** : cloud, aws, azure, gcp, saas, infrastructure
- **Cybersécurité** : cybersécurité, cyber, sécurité, vulnerab
- **Data & IA** : data, donnée, intelligence, ai, ia, machine learning, ml
- **Développement** : développeur, développement, dev, javascript, python, java, framework
- **Product & Agile** : product, management, agile, scrum
- **Conseil IT** : consulting, conseil, ingénieur, consultant
- **Web & Mobile** : webtech, web, application, mobile, api
- **DevOps & Test** : test, automatisation, devops, docker, kubernetes
- **Microsoft Ecosystem** : microsoft, 365, copilot
- **Architecture** : architecture, microservice, blockchain, crypto

**Exemples de topics core** :
- "cloud_cybersécurité_azure"
- "développement_python_frameworks"
- "data_intelligence_artificielle"
- "devops_kubernetes_docker"
- "product_management_agile"

### Adjacent (Topics adjacents intéressants)

Topics pertinents mais en périphérie du cœur de métier : accessibilité, design, réglementation, RSE tech, innovation.

**Mots-clés identifiants** :
- **UX/UI** : accessibilité, design, ux, ui, ergonomie
- **Transformation digitale** : digital, numérique, transformation
- **Réglementation** : regulation, réglementation, rgpd, compliance
- **Innovation** : innovation, startup, scale, croissance
- **RSE Tech** : rse, responsabilité, environnement, décarbonisation, climat
- **Diversité** : diversité, inclusion, fémin, égalité
- **RH Tech** : emploi, talent, recrutement, formation

**Exemples de topics adjacents** :
- "accessibilité_web_design"
- "réglementation_rgpd_compliance"
- "innovation_startup_écosystème"
- "diversité_inclusion_tech"

### Off-scope (Hors-scope / Faible priorité)

Topics non pertinents pour Innosys : hospitalité, régions, comptabilité pure, marketing générique, actualités de groupes tiers.

**Mots-clés identifiants** :
- **Hospitalité** : accueil, hospitalité, hôtel, hôtellerie
- **Géographie** : région, alpes, loire, bretagne, normandie, géographique
- **Comptabilité** : comptable, compta, expert-comptable, fiscal, fiduci
- **Commerce physique** : garage, petit commerce, vitrine, boutique
- **Marketing/Pub** : publicité, pub, marketing, communication
- **Groupes tiers** : tgs france, excilio, kikas, pickers, smile groupe, harington, kit harington, world clean up

**Exemples de topics off-scope** :
- "accueil_hôtellerie_services"
- "région_bretagne_actualités"
- "comptabilité_fiscale_experts"
- "tgs_france_groupe_actualités"

## Règles de priorité

Lorsqu'un topic contient des mots-clés de plusieurs catégories, la priorité est :

**Off-scope > Core > Adjacent > (Unknown → Off-scope par défaut)**

**Exemples** :
- "cloud_accueil" → **Off-scope** (car "accueil" est off-scope)
- "cloud_cybersécurité" → **Core** (car tous les mots sont core)
- "design_accessibilité" → **Adjacent** (car tous les mots sont adjacent)
- "sujet_inconnu_xyz" → **Off-scope** (par défaut)

## Utilisation dans l'API

Tous les endpoints GET du trend-pipeline acceptent le paramètre `scope` :

```bash
# Filtrer les clusters core
GET /api/v1/trend-pipeline/{execution_id}/clusters?scope=core

# Filtrer les gaps core
GET /api/v1/trend-pipeline/{execution_id}/gaps?scope=core&top_n=10

# Filtrer la roadmap pour les quick wins core
GET /api/v1/trend-pipeline/{execution_id}/roadmap?scope=core&max_effort=medium

# Filtrer les résultats LLM pour les recommandations core très différenciées
GET /api/v1/trend-pipeline/{execution_id}/llm-results?scope=core&min_differentiation=0.7
```

Valeurs possibles pour `scope` :
- `all` (défaut) : Tous les topics
- `core` : Topics cœur de cible Innosys uniquement
- `adjacent` : Topics adjacents intéressants uniquement
- `off_scope` : Topics hors-scope uniquement

## Règle de "Major Topic"

Un topic est considéré comme "majeur" selon ces critères :

**Par défaut** :
- `size >= 20` (nombre d'articles dans le cluster)
- `coherence_score >= 0.3` (si disponible)

**Utilisation dans l'API** :
```bash
# Récupérer seulement les topics majeurs core
GET /api/v1/trend-pipeline/{execution_id}/clusters?min_size=20&min_coherence=0.3&scope=core
```

## Personnalisation

Pour modifier la grille de classification, éditez le fichier :
```
python_scripts/analysis/article_enrichment/topic_filters.py
```

Sections à modifier :
- `CORE_KEYWORDS` : Ajouter/retirer des mots-clés core
- `ADJACENT_KEYWORDS` : Ajouter/retirer des mots-clés adjacents
- `OFF_SCOPE_KEYWORDS` : Ajouter/retirer des mots-clés off-scope

**Attention** : Après modification, relancer l'API et re-tester les endpoints.

## Exemples d'analyses

### Analyse 1 : Focus sur les topics core majeurs uniquement

```bash
# 1. Récupérer les clusters core majeurs
curl "http://localhost:8000/api/v1/trend-pipeline/{execution_id}/clusters?scope=core&min_size=20"

# 2. Récupérer les 10 principaux gaps core
curl "http://localhost:8000/api/v1/trend-pipeline/{execution_id}/gaps?scope=core&top_n=10"

# 3. Récupérer les quick wins (core, effort easy/medium)
curl "http://localhost:8000/api/v1/trend-pipeline/{execution_id}/roadmap?scope=core&max_effort=medium"

# 4. Récupérer les recommandations core très différenciées
curl "http://localhost:8000/api/v1/trend-pipeline/{execution_id}/llm-results?scope=core&min_differentiation=0.7"
```

### Analyse 2 : Identifier les articles hors-sujet

```bash
# 1. Récupérer tous les clusters off-scope
curl "http://localhost:8000/api/v1/trend-pipeline/{execution_id}/clusters?scope=off_scope"

# 2. Récupérer les outliers (articles non assignés)
curl "http://localhost:8000/api/v1/trend-pipeline/{execution_id}/outliers?limit=50"
```

### Analyse 3 : Explorer les topics adjacents intéressants

```bash
# 1. Récupérer les clusters adjacents
curl "http://localhost:8000/api/v1/trend-pipeline/{execution_id}/clusters?scope=adjacent&min_size=10"

# 2. Récupérer les gaps adjacents
curl "http://localhost:8000/api/v1/trend-pipeline/{execution_id}/gaps?scope=adjacent"

# 3. Récupérer les recommandations adjacentes
curl "http://localhost:8000/api/v1/trend-pipeline/{execution_id}/llm-results?scope=adjacent"
```

## Script d'analyse automatique

Le script `scripts/analyze_trend_pipeline_results.py` utilise automatiquement ces filtres pour générer un rapport détaillé avec distribution par scope :

```bash
python scripts/analyze_trend_pipeline_results.py <execution_id>
```

Le rapport inclut :
- Distribution par scope (core/adjacent/off_scope)
- Topics majeurs core (≥20 articles)
- Top 5 outliers (articles hors-sujet)
- Recommandations par catégorie




