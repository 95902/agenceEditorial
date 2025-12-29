# Implémentation TOON (Token-Oriented Object Notation)

**Date d'implémentation** : 2025-12-29
**Statut** : Phase 1 - TOON pour prompts LLM uniquement
**Version** : 1.0.0

---

## Vue d'ensemble

Cette documentation décrit l'implémentation de TOON (Token-Oriented Object Notation) dans AgentEditorial pour optimiser l'utilisation de tokens lors des interactions avec les LLM.

**TOON** est un format de sérialisation de données compact qui réduit l'utilisation de tokens de **30 à 60%** par rapport à JSON, tout en conservant la lisibilité et la compatibilité avec le modèle de données JSON.

## Approche adoptée : Hybride Progressive (Phase 1)

Conformément aux recommandations de l'issue #001, nous avons implémenté l'**approche hybride progressive Phase 1** :

- ✅ **TOON pour les prompts LLM** (données envoyées aux LLM)
- ✅ **JSON pour les réponses LLM** (parsing des réponses)
- ✅ **Pas d'impact sur les API existantes**
- ✅ **Fallback automatique vers JSON** si TOON n'est pas disponible

## Fichiers créés/modifiés

### Nouveaux fichiers

#### 1. `python_scripts/utils/toon_utils.py`
Utilitaires de conversion JSON ↔ TOON.

**Fonctions principales** :
- `is_toon_available()` : Vérifie si la bibliothèque TOON est disponible
- `json_to_toon(data)` : Convertit JSON vers TOON
- `toon_to_json(toon_str)` : Convertit TOON vers JSON
- `safe_json_to_toon(data, fallback_to_json=True)` : Conversion sécurisée avec fallback
- `estimate_token_savings(data)` : Estime les économies de tokens

**Exemple d'utilisation** :
```python
from python_scripts.utils.toon_utils import json_to_toon, estimate_token_savings

# Convertir des données JSON en TOON
data = [
    {"id": 1, "title": "Article 1", "effort": "medium"},
    {"id": 2, "title": "Article 2", "effort": "high"},
]

toon_str = json_to_toon(data)
print(toon_str)
# Output (format TOON) :
# id title effort
# 1 "Article 1" medium
# 2 "Article 2" high

# Estimer les économies de tokens
savings = estimate_token_savings(data)
print(f"Économie : {savings['savings_percent']}%")
```

#### 2. `python_scripts/agents/utils/toon_formatter.py`
Formatter spécialisé pour formater les données pour les LLM.

**Classe principale** : `ToonFormatter`

**Méthodes** :
- `format_for_prompt(data, label)` : Formate des données pour inclusion dans un prompt
- `format_article_list(articles, include_fields)` : Formate une liste d'articles
- `format_cluster_list(clusters)` : Formate des clusters de topics
- `format_recommendations(recommendations)` : Formate des recommandations
- `format_site_profiles(profiles)` : Formate des profils de sites

**Exemple d'utilisation** :
```python
from python_scripts.agents.utils.toon_formatter import create_toon_formatter

formatter = create_toon_formatter(enable_toon=True, log_savings=True)

articles = [
    {"id": 1, "title": "Article 1", "hook": "Hook 1", "effort": "medium"},
    {"id": 2, "title": "Article 2", "hook": "Hook 2", "effort": "high"},
]

# Formater pour un prompt LLM
formatted = formatter.format_article_list(articles, include_fields=["id", "title", "effort"])

# Utiliser dans un prompt
prompt = f"""
Analysez les articles suivants :

{formatted}

Générez des recommandations...
"""
```

#### 3. `tests/unit/test_toon_utils.py`
Tests unitaires pour les utilitaires TOON.

**Classes de tests** :
- `TestToonAvailability` : Tests de disponibilité TOON
- `TestJsonToToon` : Tests de conversion JSON → TOON
- `TestToonToJson` : Tests de conversion TOON → JSON
- `TestSafeJsonToToon` : Tests de conversion sécurisée avec fallback
- `TestEstimateTokenSavings` : Tests d'estimation des économies
- `TestToonFormatterIntegration` : Tests d'intégration du formatter

**Exécution des tests** :
```bash
# Tous les tests TOON
pytest tests/unit/test_toon_utils.py -v

# Tests spécifiques
pytest tests/unit/test_toon_utils.py::TestJsonToToon -v
```

### Fichiers modifiés

#### 1. `pyproject.toml`
Ajout de la dépendance TOON :
```toml
dependencies = [
    ...
    # TOON - Token-Oriented Object Notation for LLM optimization
    "toons>=0.1.0",
    ...
]
```

#### 2. `python_scripts/agents/trend_pipeline/article_enrichment/llm_enricher.py`
Intégration de TOON dans les prompts LLM.

**Modifications** :
- Import du `ToonFormatter`
- Ajout du paramètre `enable_toon` dans le constructeur
- Initialisation du formatter TOON
- Utilisation de TOON pour formater les outlines dans `enrich_outline()`
- Utilisation de TOON pour formater les outlines dans `enrich_complete()`

**Avant** :
```python
outline_str = json.dumps(outline, ensure_ascii=False, indent=2)
```

**Après** :
```python
if isinstance(outline, (list, dict)):
    outline_str = self._toon_formatter.format_for_prompt(outline, label="Outline")
else:
    outline_str = str(outline)
```

## Installation

### 1. Installer la dépendance TOON

```bash
cd AgentEditorial
pip install toons>=0.1.0
```

Ou avec le fichier de configuration du projet :

```bash
pip install -e .
```

### 2. Vérifier l'installation

```python
from python_scripts.utils.toon_utils import is_toon_available

if is_toon_available():
    print("✅ TOON est disponible")
else:
    print("❌ TOON n'est pas disponible, le système utilisera JSON")
```

## Utilisation

### Dans les prompts LLM

L'intégration TOON est **automatiquement activée** dans `ArticleLLMEnricher`.

```python
from python_scripts.agents.trend_pipeline.article_enrichment.llm_enricher import ArticleLLMEnricher

# Par défaut, TOON est activé
enricher = ArticleLLMEnricher(enable_toon=True)

# Pour désactiver TOON (utiliser JSON)
enricher = ArticleLLMEnricher(enable_toon=False)
```

### Formater manuellement des données

```python
from python_scripts.agents.utils.toon_formatter import format_data_for_llm

data = [
    {"id": 1, "name": "Item 1", "value": 100},
    {"id": 2, "name": "Item 2", "value": 200},
]

# Formater avec TOON
formatted = format_data_for_llm(data, label="Items", use_toon=True)

# Formater avec JSON
formatted_json = format_data_for_llm(data, label="Items", use_toon=False)
```

## Avantages observés

### Réduction de tokens

**Exemple réel** :

**JSON** (116 caractères) :
```json
[
  {"id": 1, "title": "Article 1", "effort": "medium"},
  {"id": 2, "title": "Article 2", "effort": "high"},
  {"id": 3, "title": "Article 3", "effort": "low"}
]
```

**TOON** (~60 caractères, **~48% de réduction**) :
```
id title effort
1 "Article 1" medium
2 "Article 2" high
3 "Article 3" low
```

### Logging automatique

Le `ToonFormatter` log automatiquement les statistiques d'économie :

```
INFO: TOON formatting statistics
  label: Outline
  json_length: 450
  toon_length: 220
  savings_chars: 230
  savings_percent: 51.11
```

## Comportement de fallback

Si la bibliothèque `toons` n'est pas installée :

1. ✅ Le système **fonctionne normalement** avec JSON
2. ✅ Un avertissement est logué au démarrage
3. ✅ Aucune erreur bloquante
4. ✅ Les tests sont skippés automatiquement

```python
# Safe conversion with fallback
from python_scripts.utils.toon_utils import safe_json_to_toon

# Si TOON n'est pas disponible, retourne du JSON
result = safe_json_to_toon(data, fallback_to_json=True)
```

## Limitations actuelles (Phase 1)

### ✅ Implémenté
- TOON pour les prompts LLM (données envoyées)
- Fallback automatique vers JSON
- Tests unitaires complets
- Logging des économies de tokens

### ❌ Non implémenté (futures phases)
- Support TOON pour les réponses API (Phase 3)
- Négociation de contenu `Accept: application/toon` (Phase 3)
- TOON pour les réponses LLM (risque de parsing)

## Prochaines étapes (Phases 2 et 3)

### Phase 2 : Évaluation (2-4 semaines)

**Métriques à mesurer** :
- Réduction réelle de tokens en production
- Compréhension TOON par les LLM (Llama3, Mistral, Phi3)
- Impact sur la performance (latence, CPU)
- Taux de succès des prompts

**Outils de monitoring** :
```python
# À implémenter
from python_scripts.utils.toon_utils import estimate_token_savings

stats = estimate_token_savings(data)
# Log ces stats pour analyse
```

### Phase 3 : Extension conditionnelle

**Si Phase 2 est concluante** :
1. Ajouter support TOON aux API REST
2. Négociation de contenu via header `Accept: application/toon`
3. Middleware TOON pour les réponses API
4. Conserver JSON par défaut pour compatibilité

**Fichiers à créer** :
- `python_scripts/api/middleware/toon_response.py`
- Modifications dans `python_scripts/api/main.py`

## Ressources

### Documentation officielle TOON
- [TOON Format - Site officiel](https://toonformat.dev/)
- [GitHub - python-toon](https://github.com/xaviviro/python-toon)
- [GitHub - toons (Rust-based)](https://github.com/alesanfra/toons)
- [PyPI - toons](https://pypi.org/project/toons/)
- [TOON Tools Documentation](https://www.toontools.app/docs)

### Références internes
- Issue #001 : `docs/issues/001-integration-toon.md`
- Tests unitaires : `tests/unit/test_toon_utils.py`

## Support

Pour toute question ou problème lié à l'implémentation TOON :

1. Vérifier que `toons` est installé : `pip list | grep toons`
2. Consulter les logs pour les statistiques d'économie
3. Exécuter les tests : `pytest tests/unit/test_toon_utils.py -v`
4. Désactiver TOON temporairement : `ArticleLLMEnricher(enable_toon=False)`

---

**Dernière mise à jour** : 2025-12-29
**Auteur** : AgentEditorial Development Team
**Version** : 1.0.0 (Phase 1)
