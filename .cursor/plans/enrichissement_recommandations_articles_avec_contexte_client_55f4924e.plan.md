---
name: Enrichissement recommandations articles avec contexte client
overview: Créer un système d'enrichissement des recommandations d'articles générées par le LLM en utilisant le contexte client (site_analysis_results) et les données de tendances pour produire des outlines détaillés, des angles personnalisés et des statistiques chiffrées.
todos:
  - id: create-enrichment-module
    content: Créer le module article_enrichment avec la structure de base (__init__.py, config.py)
    status: completed
  - id: create-client-context-crud
    content: Ajouter get_client_context_for_enrichment() dans crud_profiles.py pour récupérer le contexte client complet
    status: completed
  - id: create-enrichment-prompts
    content: Créer prompts.py avec les prompts LLM pour enrichissement d'outline, personnalisation et intégration statistiques
    status: completed
    dependencies:
      - create-enrichment-module
  - id: create-llm-enricher
    content: Créer llm_enricher.py pour l'enrichissement via LLM avec intégration contexte client et statistiques
    status: completed
    dependencies:
      - create-enrichment-prompts
      - create-client-context-crud
  - id: create-article-enricher
    content: Créer article_enricher.py comme service principal orchestrant l'enrichissement complet
    status: completed
    dependencies:
      - create-llm-enricher
  - id: create-api-router
    content: Créer article_enrichment.py router avec endpoints pour enrichir les articles
    status: completed
    dependencies:
      - create-article-enricher
  - id: register-router
    content: Enregistrer le nouveau router dans main.py
    status: completed
    dependencies:
      - create-api-router
  - id: optional-enhance-model
    content: "Optionnel : Ajouter champs enrichis au modèle ArticleRecommendation si nécessaire"
    status: pending
---

# Enrichissement des recommandations d'articles avec contexte client

## Objectif

Enrichir les 30 recommandations d'articles générées par le trend pipeline en :

1. Enrichissant les outlines (trop génériques actuellement)
2. Adaptant au contexte client Innosys (depuis `site_analysis_results`)
3. Ajoutant des données chiffrées (statistiques concurrents, métriques temporelles)
4. Personnalisant les angles selon la stratégie éditoriale du client

## Architecture

### 1. Module d'enrichissement d'articles

**Fichier :** `python_scripts/analysis/article_enrichment/article_enricher.py`

Créer un nouveau module qui :

- Récupère le contexte client depuis `site_analysis_results` (phase "synthesis")
- Récupère les métriques temporelles et statistiques de couverture
- Génère des outlines enrichis via LLM
- Personnalise les angles selon le ton éditorial et le public cible
- Intègre des statistiques chiffrées

### 2. CRUD pour récupérer le contexte client

**Fichier :** `python_scripts/database/crud_profiles.py` (extension)

Ajouter des fonctions pour :

- `get_client_context_for_enrichment(domain: str)` : Récupère le contexte complet du client
  - `SiteProfile` : ton éditorial, public cible, domaines d'activité, mots-clés
  - `SiteAnalysisResult` (phase "synthesis") : synthèse complète du site
  - Retourne un dictionnaire structuré avec toutes les informations

### 3. Service d'enrichissement LLM

**Fichier :** `python_scripts/analysis/article_enrichment/llm_enricher.py`

Créer un service qui utilise un LLM pour :

- Générer des outlines détaillés (3-5 sections avec sous-sections)
- Adapter le ton et le style selon le profil client
- Intégrer des statistiques et exemples concrets
- Personnaliser les angles selon les domaines d'activité

### 4. Prompts d'enrichissement

**Fichier :** `python_scripts/analysis/article_enrichment/prompts.py`

Créer des prompts spécialisés pour :

- Enrichissement d'outline : transformer un outline générique en structure détaillée
- Personnalisation d'angle : adapter l'angle selon le contexte client
- Intégration de statistiques : ajouter des données chiffrées pertinentes

### 5. API endpoint pour enrichir les articles

**Fichier :** `python_scripts/api/routers/article_enrichment.py`

Créer un nouveau router avec :

- `POST /api/v1/articles/enrich` : Enrichir une recommandation d'article
- `POST /api/v1/articles/enrich-batch` : Enrichir plusieurs articles en batch
- `GET /api/v1/articles/{article_id}/enriched` : Récupérer une version enrichie

### 6. Mise à jour du modèle ArticleRecommendation

**Optionnel :** Ajouter des champs pour stocker les versions enrichies :

- `enriched_outline` : Outline enrichi (dict détaillé)
- `enriched_hook` : Hook personnalisé
- `statistics` : Statistiques intégrées (dict)
- `client_context_used` : Contexte client utilisé (dict)

## Flux d'enrichissement

1. **Récupération du contexte client**

   - Requête `SiteProfile` pour `innosys.fr`
   - Requête `SiteAnalysisResult` (phase "synthesis") pour le profil
   - Extraction : ton éditorial, public cible, domaines d'activité, mots-clés, style

2. **Récupération des données de tendances**

   - Métriques temporelles du topic (vélocité, croissance, fraîcheur)
   - Statistiques de couverture (gap score, priority score)
   - Volume d'articles concurrents

3. **Enrichissement via LLM**

   - Prompt avec : outline original, contexte client, statistiques
   - Génération d'un outline détaillé (sections + sous-sections)
   - Personnalisation du hook selon le ton éditorial
   - Intégration de statistiques dans le contenu

4. **Validation et stockage**

   - Validation de la structure de l'outline enrichi
   - Stockage dans la base de données (nouveau champ ou table dédiée)
   - Retour de la version enrichie

## Structure des données

### Contexte client (depuis site_analysis_results)

```python
{
    "editorial_tone": "professional",
    "language_level": "intermediate",
    "target_audience": {
        "primary": "business owners",
        "secondary": ["IT managers", "decision makers"]
    },
    "activity_domains": {
        "primary_domains": ["IT services", "cloud computing"],
        "secondary_domains": ["cybersecurity", "digital transformation"]
    },
    "keywords": {
        "primary_keywords": ["Innosys", "ESN", "SSII"],
        "semantic_keywords": ["Security solutions", "Digital infrastructure"]
    },
    "style_features": {
        "sentence_length_avg": "15-20 words",
        "average_word_count": 800
    }
}
```

### Outline enrichi (structure cible)

```python
{
    "introduction": {
        "title": "Introduction",
        "subsections": [
            "Contexte et enjeux",
            "Objectif de l'article"
        ],
        "key_points": ["Point 1", "Point 2"],
        "statistics": ["Stat 1", "Stat 2"]
    },
    "section_1": {
        "title": "Titre section 1",
        "subsections": [...],
        "key_points": [...],
        "statistics": [...]
    },
    "conclusion": {
        "title": "Conclusion",
        "subsections": [...],
        "call_to_action": "..."
    }
}
```

## Fichiers à créer/modifier

1. **Nouveaux fichiers :**

   - `python_scripts/analysis/article_enrichment/__init__.py`
   - `python_scripts/analysis/article_enrichment/article_enricher.py`
   - `python_scripts/analysis/article_enrichment/llm_enricher.py`
   - `python_scripts/analysis/article_enrichment/prompts.py`
   - `python_scripts/analysis/article_enrichment/config.py`
   - `python_scripts/api/routers/article_enrichment.py`

2. **Fichiers à modifier :**

   - `python_scripts/database/crud_profiles.py` : Ajouter `get_client_context_for_enrichment()`
   - `python_scripts/api/main.py` : Enregistrer le nouveau router
   - `python_scripts/database/models.py` : Optionnel - ajouter champs enrichis à `ArticleRecommendation`

## Tests

1. Tester l'enrichissement d'un article simple
2. Vérifier la récupération du contexte client
3. Valider l'intégration des statistiques
4. Tester l'adaptation du ton éditorial
5. Vérifier la structure des outlines enrichis