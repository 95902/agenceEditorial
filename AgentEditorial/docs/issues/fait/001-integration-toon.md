# Issue #001 : Intégration TOON (Token-Oriented Object Notation)

**Date de création** : 2025-01-25
**Date d'implémentation Phase 1** : 2025-12-29
**Statut** : ✅ Phase 1 implémentée - En évaluation Phase 2
**Priorité** : Moyenne
**Type** : Amélioration / Optimisation
**Labels** : `optimisation`, `llm`, `format-donnees`, `implemented`

---

## Contexte

TOON (Token-Oriented Object Notation) est un format de sérialisation de données conçu comme alternative compacte et lisible à JSON, particulièrement efficace pour les interactions avec les modèles de langage de grande taille (LLM). Il permet de réduire l'utilisation de tokens de **30 à 60%** par rapport à JSON, tout en conservant une lisibilité humaine et une compatibilité totale avec le modèle de données JSON.

### Pourquoi évaluer TOON ?

Le projet AgentEditorial utilise massivement les LLM pour :
- L'analyse éditoriale de sites web
- L'enrichissement d'articles avec contexte client
- La génération de recommandations de contenu
- La synthèse de tendances thématiques

Ces interactions impliquent l'envoi de structures de données complexes aux LLM, ce qui peut représenter un coût significatif en tokens, notamment avec des API payantes.

---

## Analyse des avantages

### 1. Réduction significative des tokens (30-60%)

**Impact** : Économie de coûts importante pour les API LLM payantes (OpenAI, Anthropic, etc.)

**Cas d'usage dans le projet** :
- Prompts avec données structurées volumineuses (`OUTLINE_ENRICHMENT_PROMPT`, `COMPLETE_ENRICHMENT_PROMPT`)
- Envoi de listes de recommandations d'articles aux LLM
- Transmission de contextes clients complexes

**Exemple** :
```json
// Format JSON (exemple)
[
  {"id": 1, "title": "Article 1", "hook": "Hook 1", "effort": "medium"},
  {"id": 2, "title": "Article 2", "hook": "Hook 2", "effort": "high"},
  {"id": 3, "title": "Article 3", "hook": "Hook 3", "effort": "low"}
]
```

```toon
// Format TOON (équivalent, ~40% moins de tokens)
id title hook effort
1 "Article 1" "Hook 1" medium
2 "Article 2" "Hook 2" high
3 "Article 3" "Hook 3" low
```

### 2. Optimisation pour structures uniformes

**Impact** : TOON excelle particulièrement pour les tableaux d'objets avec clés identiques.

**Structures pertinentes dans le projet** :
- `ClustersResponse` : Listes de clusters de topics
- `ArticleRecommendationSummary` : Recommandations d'articles
- `List[SiteProfileResponse]` : Profils de sites analysés
- `TrendSynthesisSummary` : Synthèses de tendances

**Fichiers concernés** :
- `python_scripts/api/routers/trend_pipeline.py` : Endpoints retournant des listes uniformes
- `python_scripts/api/routers/sites.py` : Listes de profils de sites
- `python_scripts/agents/trend_pipeline/article_enrichment/llm_enricher.py` : Envoi de données aux LLM

### 3. Compatibilité avec le modèle de données JSON

**Impact** : Conversion bidirectionnelle sans perte de données.

- Compatible avec les champs JSONB PostgreSQL existants
- Conversion transparente JSON ↔ TOON
- Pas de migration de données nécessaire

### 4. Lisibilité humaine préservée

**Impact** : Format plus compact que JSON indenté, utile pour :
- Logs de débogage
- Visualisation de données complexes
- Documentation

---

## Analyse des inconvénients et risques

### 1. Support LLM limité ⚠️ **RISQUE CRITIQUE**

**Problème** : Les LLM (Ollama/Llama3, Mistral, Phi3) sont principalement entraînés sur JSON.

**Risques** :
- Les LLM peuvent ne pas comprendre le format TOON
- Parsing incorrect des réponses
- Refus de générer du TOON
- Nécessité de tests approfondis avec chaque modèle

**Fichiers concernés** :
- `python_scripts/agents/prompts.py` : Tous les prompts LLM
- `python_scripts/agents/trend_pipeline/article_enrichment/prompts.py`
- `python_scripts/agents/trend_pipeline/llm_enrichment/prompts.py`

**Recommandation** : Tester TOON uniquement pour les **entrées** LLM (prompts), conserver JSON pour les **sorties** (réponses).

### 2. Écosystème limité

**Problème** : Moins de support que JSON dans l'écosystème.

**Limitations** :
- Bibliothèques et outils limités
- Support limité dans navigateurs, Postman, curl
- Moins de documentation et d'exemples
- Communauté plus petite

**Impact** : Complexité accrue pour le développement et le débogage.

### 3. Complexité d'implémentation

**Problème** : Ajout d'une couche d'abstraction supplémentaire.

**Complexités** :
- Gestion de deux formats (JSON et TOON)
- Conversion à chaque interaction
- Tests supplémentaires (JSON + TOON)
- Risque de bugs de conversion
- Maintenance de code supplémentaire

**Fichiers à modifier** :
- `python_scripts/utils/json_utils.py` : Ajout de fonctions TOON
- Nouveau fichier : `python_scripts/utils/toon_utils.py`
- Nouveau fichier : `python_scripts/api/middleware/toon_response.py`

### 4. Compatibilité API

**Problème** : Les clients HTTP attendent généralement JSON.

**Conséquences** :
- Nécessité de négociation de contenu (`Accept: application/toon`)
- Risque de confusion pour les développeurs frontend
- Support client limité (curl, Postman, etc.)
- Documentation API plus complexe

**Endpoints concernés** :
- Tous les endpoints dans `python_scripts/api/routers/`

### 5. Base de données PostgreSQL

**Problème** : JSONB stocke du JSON, pas du TOON.

**Impact** :
- Pas de gain en stockage
- Conversion nécessaire à chaque lecture/écriture
- Overhead de performance potentiel

**Tables concernées** :
- Toutes les tables avec champs JSONB dans `python_scripts/database/models.py`

### 6. Performance

**Problème** : Conversion JSON ↔ TOON ajoute une étape de traitement.

**Impact** :
- Overhead sur les réponses API volumineuses
- Latence supplémentaire (même si minime)
- Consommation CPU supplémentaire

**À mesurer** : Impact réel selon les volumes de données du projet.

---

## Cas d'usage spécifiques au projet

### ✅ Cas où TOON est avantageux

#### 1. Prompts LLM avec données structurées

**Fichiers** :
- `python_scripts/agents/trend_pipeline/article_enrichment/llm_enricher.py`
- `python_scripts/agents/trend_pipeline/article_enrichment/prompts.py`

**Exemple** : Envoi de listes de recommandations d'articles aux LLM pour enrichissement.

**Gain estimé** : 30-50% de réduction de tokens sur les prompts volumineux.

#### 2. Réponses API avec tableaux uniformes

**Endpoints** :
- `GET /api/v1/trend-pipeline/{execution_id}/clusters`
- `GET /api/v1/trend-pipeline/{execution_id}/llm-results`
- `GET /api/v1/sites` (liste de profils)

**Gain estimé** : 40-60% de réduction pour les réponses avec listes uniformes.

#### 3. Logs et débogage

**Fichiers** :
- `python_scripts/utils/logging.py`

**Gain** : Format plus compact pour les structures complexes dans les logs.

### ❌ Cas où TOON est moins pertinent

#### 1. Stockage en base de données

**Raison** : JSONB reste en JSON, pas de gain en stockage.

**Tables** : Toutes les tables avec JSONB.

#### 2. Réponses API simples

**Raison** : Objets uniques sans tableaux uniformes = gain limité.

**Exemples** :
- `GET /api/v1/sites/{domain}` (objet unique)
- `GET /api/v1/executions/{execution_id}` (objet unique)

#### 3. Compatibilité externe

**Raison** : Intégrations tierces attendent JSON.

**Impact** : Nécessité de maintenir JSON pour ces cas.

---

## Recommandations

### Option 1 : Approche hybride (⭐ **RECOMMANDÉE**)

**Principe** : Utiliser TOON uniquement pour les interactions LLM (prompts), conserver JSON partout ailleurs.

**Avantages** :
- ✅ Gain de tokens significatif là où c'est le plus utile
- ✅ Pas d'impact sur la compatibilité API
- ✅ Pas de risque pour les réponses LLM (qui restent en JSON)
- ✅ Implémentation ciblée et limitée

**Implémentation** :
1. Ajouter `toons` dans `pyproject.toml`
2. Créer `python_scripts/utils/toon_utils.py`
3. Modifier les prompts LLM pour utiliser TOON dans les données envoyées
4. Conserver JSON pour les réponses LLM

**Fichiers à modifier** :
- `pyproject.toml` : Ajouter dépendance `toons>=0.1.0`
- `python_scripts/utils/toon_utils.py` : Nouveau fichier
- `python_scripts/agents/trend_pipeline/article_enrichment/llm_enricher.py` : Utiliser TOON pour formater les données dans les prompts
- `python_scripts/agents/utils/toon_formatter.py` : Nouveau fichier utilitaire

**Complexité** : Faible à moyenne  
**Risque** : Faible (tests nécessaires sur la compréhension TOON par les LLM)

### Option 2 : TOON complet

**Principe** : TOON pour les API et les LLM, avec négociation de contenu.

**Avantages** :
- ✅ Gain maximal de tokens
- ✅ Format unifié

**Inconvénients** :
- ❌ Complexité élevée
- ❌ Risque de compatibilité
- ❌ Tests LLM nécessaires
- ❌ Support client limité

**Complexité** : Élevée  
**Risque** : Élevé

### Option 3 : Pas de TOON

**Principe** : Rester sur JSON uniquement.

**Avantages** :
- ✅ Simplicité maximale
- ✅ Compatibilité totale
- ✅ Pas de risque

**Inconvénients** :
- ❌ Pas de réduction de tokens
- ❌ Coûts LLM plus élevés

**Complexité** : Aucune  
**Risque** : Aucun

---

## Questions à se poser avant décision

### 1. Utilisation d'API LLM payantes ?

- [ ] **Oui** (OpenAI, Anthropic, etc.) → TOON peut réduire significativement les coûts
- [ ] **Non** (Ollama local uniquement) → Gain moins critique

**Impact** : Si utilisation locale uniquement, le gain en tokens est moins prioritaire.

### 2. Les LLM comprennent-ils TOON ?

- [ ] **À tester** : Valider avec Llama3, Mistral, Phi3
- [ ] **Risque** : Parsing incorrect possible

**Action requise** : Tests POC avant implémentation complète.

### 3. Volume de données envoyées aux LLM ?

- [ ] **Élevé** (listes de 50+ articles, structures complexes) → Gain significatif
- [ ] **Faible** (quelques objets simples) → Gain marginal

**Impact** : Plus le volume est élevé, plus TOON est pertinent.

### 4. Priorité : compatibilité ou optimisation ?

- [ ] **Compatibilité** → Rester sur JSON
- [ ] **Optimisation** → TOON avec tests approfondis

**Impact** : Détermine l'approche à adopter.

---

## Recommandation finale

### Approche hybride progressive en 3 phases

#### Phase 1 : TOON uniquement pour les prompts LLM (interne) ⭐

**Objectif** : Réduire les tokens dans les prompts sans impact sur les API.

**Actions** :
1. Ajouter dépendance `toons` dans `pyproject.toml`
2. Créer `python_scripts/utils/toon_utils.py` avec fonctions de conversion
3. Créer `python_scripts/agents/utils/toon_formatter.py` pour formater les données pour LLM
4. Modifier `python_scripts/agents/trend_pipeline/article_enrichment/llm_enricher.py` :
   - Utiliser TOON pour formater les données dans les prompts
   - Conserver JSON pour les réponses LLM (ils génèrent du JSON)
5. Tests POC avec les modèles utilisés (Llama3, Mistral, Phi3)

**Avantages** :
- ✅ Pas d'impact sur les API existantes
- ✅ Gain de tokens là où c'est le plus utile
- ✅ Risque limité (tests ciblés)

**Fichiers à créer/modifier** :
- `pyproject.toml`
- `python_scripts/utils/toon_utils.py` (nouveau)
- `python_scripts/agents/utils/toon_formatter.py` (nouveau)
- `python_scripts/agents/trend_pipeline/article_enrichment/llm_enricher.py`

#### Phase 2 : Évaluation des résultats

**Objectif** : Mesurer l'impact réel de TOON.

**Métriques** :
- Réduction réelle de tokens (mesurée)
- Compréhension des LLM (taux de succès)
- Performance (latence, CPU)
- Bugs éventuels

**Durée** : 2-4 semaines de tests en production

#### Phase 3 : Extension conditionnelle

**Objectif** : Étendre TOON aux API si Phase 1 est concluante.

**Actions** (si Phase 2 positive) :
1. Ajouter support TOON aux API via header `Accept: application/toon`
2. Créer `python_scripts/api/middleware/toon_response.py`
3. Modifier `python_scripts/api/main.py` pour négociation de contenu
4. Conserver JSON par défaut pour compatibilité

**Condition** : Phase 2 doit montrer des bénéfices clairs.

---

## Prochaines étapes

### Si décision d'implémenter (Option 1 - Approche hybride)

1. **Validation** : Approuver l'approche hybride progressive
2. **POC** : Créer un test minimal avec un prompt LLM utilisant TOON
3. **Tests** : Valider la compréhension TOON par les modèles utilisés
4. **Implémentation Phase 1** : Intégrer TOON dans les prompts LLM uniquement
5. **Monitoring** : Mesurer la réduction de tokens et les performances
6. **Décision Phase 3** : Étendre ou non selon les résultats

### Fichiers de référence

- `python_scripts/agents/trend_pipeline/article_enrichment/llm_enricher.py` : Point d'entrée principal
- `python_scripts/agents/prompts.py` : Prompts LLM existants
- `python_scripts/utils/json_utils.py` : Utilitaires JSON actuels
- `python_scripts/api/routers/trend_pipeline.py` : Endpoints avec structures uniformes

### Documentation externe

- [TOON Tools Documentation](https://www.toontools.app/docs)
- [TOON Kit Documentation](https://toon-kit.com/docs)
- [TOON Python Library](https://toons.readthedocs.io/)

---

## Notes

- **Date d'évaluation** : 2025-01-25
- **Décision requise** : Validation de l'approche hybride progressive
- **Prochaine revue** : Après Phase 2 (évaluation des résultats)

---

## Historique

- **2025-01-25** : Création de l'issue, analyse complète des avantages/inconvénients
- **2025-12-29** : Implémentation Phase 1 complétée
  - ✅ Ajout dépendance `toons>=0.1.0` dans `pyproject.toml`
  - ✅ Création `python_scripts/utils/toon_utils.py` avec fonctions de conversion
  - ✅ Création `python_scripts/agents/utils/toon_formatter.py` pour formater les données LLM
  - ✅ Modification `llm_enricher.py` pour utiliser TOON dans les prompts
  - ✅ Création `tests/unit/test_toon_utils.py` avec tests complets
  - ✅ Documentation complète dans `docs/TOON_IMPLEMENTATION.md`
  - 📊 Prochaine étape : Phase 2 (Évaluation sur 2-4 semaines)





