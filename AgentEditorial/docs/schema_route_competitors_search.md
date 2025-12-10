# Schéma de Base de Données et Fonctionnalités - Route POST /api/v1/competitors/search

## Vue d'ensemble

La route `POST /api/v1/competitors/search` lance une recherche de concurrents pour un domaine donné. Elle utilise un pipeline de validation en 12 étapes avec recherche multi-sources et classification LLM.

## Flux d'exécution

1. **Création de l'exécution** → `workflow_executions`
2. **Recherche du profil client** → `site_profiles` (READ)
3. **Pipeline de recherche concurrents** (12 étapes) :
   - Recherche multi-sources (Tavily, DuckDuckGo)
   - Filtrage et classification
   - Enrichissement des candidats
   - Scoring et ranking
4. **Sauvegarde des résultats** → `workflow_executions` (UPDATE)

## Tables impactées

### 1. `workflow_executions` ⭐ **CRITIQUE**
- **Opération** : CREATE, UPDATE, READ
- **Description** : Enregistre l'exécution du workflow de recherche de concurrents
- **Champs impactés** :
  - `execution_id` (UUID, unique)
  - `workflow_type` = "competitor_search"
  - `status` : "pending" → "running" → "completed" ou "failed"
  - `input_data` : `{"domain": "...", "max_competitors": ...}`
  - `output_data` : Résultats de la recherche avec :
    - `competitors` : Liste des concurrents validés
    - `all_candidates` : Tous les candidats évalués (inclus + exclus)
    - `excluded_candidates` : Candidats exclus uniquement
    - `total_found` : Nombre de concurrents trouvés
    - `total_evaluated` : Nombre total de candidats évalués
  - `start_time`, `end_time`, `duration_seconds`
  - `was_success` : true/false
  - `error_message` : si échec

### 2. `site_profiles` 📖 **LECTURE SEULE**
- **Opération** : READ
- **Description** : Profil éditorial du site client (pour enrichir la recherche)
- **Champs lus** :
  - `domain`
  - `activity_domains` (JSONB) : Domaines d'activité
  - `keywords` (JSONB) : Mots-clés
  - `target_audience` (JSONB) : Audience cible
  - `editorial_tone` : Ton éditorial
  - `language_level` : Niveau de langue

## Diagramme de relations

```
workflow_executions (1)
    │
    └──> output_data.competitors (JSONB) [résultats stockés dans JSON]
    │
site_profiles (1) [READ ONLY]
    │
    └──> Utilisé pour enrichir les requêtes de recherche
```

## Fonctionnalités utilisées

### 1. **Recherche Multi-Sources** 🔍

#### 1.1 Tavily API
- **Type** : API externe (recherche web sémantique)
- **Usage** : Recherche de concurrents via requêtes sémantiques
- **Configuration** : Nécessite `TAVILY_API_KEY` dans `.env`
- **Limite** : `max_results_tavily` = 20 résultats par requête
- **Fonction** : `_search_tavily(query: str)`

#### 1.2 DuckDuckGo
- **Type** : Bibliothèque Python (`ddgs`)
- **Usage** : Recherche web alternative/complémentaire
- **Limite** : `max_results_duckduckgo` = 20 résultats par requête
- **Fonction** : `_search_duckduckgo(query: str)`

### 2. **Génération de Requêtes** 📝

#### 2.1 QueryGenerator
- **Classe** : `QueryGenerator`
- **Fonctionnalité** : Génère des requêtes de recherche optimisées
- **Stratégies** :
  - Requêtes basées sur le domaine
  - Requêtes basées sur les domaines d'activité
  - Requêtes basées sur les mots-clés du profil client
  - Requêtes combinées
- **Limite** : `max_queries` = 50 requêtes maximum

### 3. **Pipeline de Validation en 12 Étapes** 🔄

#### Étape 1 : Recherche Multi-Sources
- **Fonction** : Recherche via Tavily et DuckDuckGo
- **Résultat** : Liste brute de candidats potentiels

#### Étape 2 : Déduplication
- **Fonction** : Suppression des doublons par domaine
- **Critère** : Normalisation du domaine (lowercase, sans www)

#### Étape 3 : Pre-Filtrage
- **Classe** : `PreFilter`
- **Fonctionnalité** : Filtrage basique
  - Exclusion des domaines dans les listes d'exclusion
  - Exclusion des TLDs non autorisés
  - Filtrage des domaines invalides

#### Étape 4 : Filtrage par Domaine
- **Classe** : `DomainFilter`
- **Fonctionnalité** : Filtrage avancé des domaines
  - Exclusion des domaines du client
  - Exclusion des domaines déjà connus comme non-pertinents

#### Étape 5 : Enrichissement
- **Classe** : `CandidateEnricher`
- **Fonctionnalité** : Enrichissement des candidats
  - Récupération des métadonnées (titre, description)
  - Validation géographique (via API si disponible)
  - Cross-validation (vérification multi-sources)
- **Limite** : `max_candidates_to_enrich` = 50 candidats

#### Étape 6 : Filtrage LLM
- **Classe** : `RelevanceClassifier`
- **Fonctionnalité** : Classification par LLM (phi3:medium)
  - Évaluation de la pertinence
  - Détection des faux positifs
  - Score de pertinence (0-1)

#### Étape 7 : Filtrage Média
- **Classe** : `MediaFilter`
- **Fonctionnalité** : Exclusion des sites médias/presse
  - Détection des sites de presse
  - Exclusion automatique

#### Étape 8 : Validation du Contenu
- **Classe** : `ContentFilter`
- **Fonctionnalité** : Validation du contenu
  - Vérification de la présence de contenu éditorial
  - Exclusion des sites vides ou non-éditoriaux

#### Étape 9 : Classification et Scoring
- **Classes** :
  - `ESNClassifier` : Détection des ESN (Entreprises de Services du Numérique)
  - `BusinessTypeClassifier` : Classification par type d'entreprise
  - `GeographicClassifier` : Classification géographique
  - `CompetitorScorer` : Calcul des scores
- **Scores calculés** :
  - `relevance_score` : Score de pertinence (LLM)
  - `semantic_similarity` : Similarité sémantique (si Qdrant utilisé)
  - `confidence_score` : Score de confiance
  - `combined_score` : Score combiné (poids configurés)
- **Poids** :
  - `weight_llm_score` = 0.50
  - `weight_semantic_similarity` = 0.25
  - `bonus_cross_validation` = 0.15
  - `bonus_geographic` = 0.10

#### Étape 10 : Assurance de Diversité
- **Fonctionnalité** : Garantir la diversité des résultats
  - Limite par catégorie d'entreprise
  - Distribution équilibrée
  - Ranking final

#### Étape 11 : Calcul du Score de Confiance
- **Fonctionnalité** : Calcul du score de confiance final
  - Basé sur la cohérence des signaux
  - Validation multi-sources

#### Étape 12 : Filtrage Final
- **Classe** : `CompetitorScorer`
- **Fonctionnalité** : Filtrage final avec seuils ajustés
  - `min_relevance_score` = 0.45
  - `min_confidence_score` = 0.35
  - `min_combined_score` = 0.35
  - Limitation à `max_competitors`

### 4. **Services Externes** 🌐

#### 4.1 Tavily API
- **Endpoint** : `https://api.tavily.com/search`
- **Authentification** : API Key
- **Usage** : Recherche sémantique web
- **Configuration** : `TAVILY_API_KEY` dans `.env`

#### 4.2 DuckDuckGo
- **Type** : Bibliothèque Python (`ddgs`)
- **Usage** : Recherche web gratuite
- **Pas d'authentification requise**

#### 4.3 LLM (Ollama)
- **Modèle** : `phi3:medium`
- **Usage** : Classification et filtrage LLM
- **Configuration** : `OLLAMA_BASE_URL` dans `.env`
- **Fonction** : Évaluation de pertinence des candidats

#### 4.4 Qdrant (Optionnel)
- **Usage** : Recherche sémantique pour similarité
- **Collection** : `competitor_articles`
- **Fonction** : Calcul de similarité sémantique si disponible

### 5. **Listes d'Exclusion** 🚫

Le système utilise des listes d'exclusion configurées dans `CompetitorSearchConfig` :

- **Domaines exclus** : Liste de domaines à exclure
- **TLDs exclus** : Extensions de domaine exclues
- **Outils SEO/Analytics** : Exclusion automatique
- **Médias et presse** : Exclusion via `MediaFilter`
- **Plateformes de listing** : Exclusion automatique
- **Sites d'emploi** : Exclusion automatique
- **E-commerce** : Exclusion automatique
- **Universités** : Exclusion automatique
- **Services publics** : Exclusion automatique
- **Sites de reprise d'entreprises** : Exclusion automatique
- **Annuaires** : Exclusion automatique

## Ordre d'impact

1. **Phase initiale** :
   - `workflow_executions` (CREATE)
   - `site_profiles` (READ)

2. **Phase recherche** :
   - Appels API externes (Tavily, DuckDuckGo)
   - Pas d'écriture en base

3. **Phase traitement** :
   - Pipeline de validation (12 étapes)
   - Classification LLM
   - Pas d'écriture en base (traitement en mémoire)

4. **Phase sauvegarde** :
   - `workflow_executions` (UPDATE avec résultats)

## Structure des données dans output_data

```json
{
  "competitors": [
    {
      "domain": "example.com",
      "url": "https://example.com",
      "title": "Example Site",
      "reason": "Similar activity domains",
      "source": "tavily",
      "relevance_score": 0.85,
      "confidence_score": 0.78,
      "combined_score": 0.82,
      "business_type": "entreprise",
      "geographic_match": true,
      "cross_validation": true,
      "included": true,
      "status": "included"
    }
  ],
  "all_candidates": [...],  // Tous les candidats évalués
  "excluded_candidates": [...],  // Candidats exclus uniquement
  "total_found": 15,
  "total_evaluated": 127,
  "domain": "client-domain.com"
}
```

## Notes importantes

- ⭐ **CRITIQUE** : Table essentielle pour le fonctionnement de la route
- 📖 **LECTURE SEULE** : Table lue mais non modifiée
- 🔍 **EXTERNE** : Service externe (API, bibliothèque)
- 🔄 **PIPELINE** : Traitement en mémoire, pas d'écriture directe en base

- Les résultats sont stockés dans `workflow_executions.output_data` (JSONB)
- Aucune table dédiée aux concurrents n'est créée
- Le pipeline peut traiter jusqu'à 50 requêtes × 20 résultats = 1000+ candidats initiaux
- Le filtrage réduit à ~10-100 candidats évalués
- Le résultat final est limité à `max_competitors` (par défaut 10-100)

## Dépendances externes

- **Tavily API** : Requis (avec clé API)
- **DuckDuckGo** : Optionnel (bibliothèque Python)
- **Ollama (phi3:medium)** : Requis pour le filtrage LLM
- **Qdrant** : Optionnel (pour similarité sémantique)

## Performance

- **Durée typique** : 30-120 secondes selon le nombre de requêtes
- **Limites** :
  - `max_queries` = 50
  - `max_results_tavily` = 20
  - `max_results_duckduckgo` = 20
  - `max_candidates_to_enrich` = 50
  - `max_competitors` = 100 (par défaut)




