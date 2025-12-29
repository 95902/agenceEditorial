# Analyse : Système de collections Qdrant

**Date** : 2025-12-29
**Problème rapporté** : Création d'une collection avec le nom du client au lieu du concurrent

---

## 🔍 Problème identifié

### Ce que vous voyez

Vous avez probablement observé la création de collections comme :
- `innosys_fr_competitor_articles` ✅ (nouvelle)
- `innosys_fr_client_articles` ✅ (nouvelle)
- `competitor_articles` ❓ (ancienne - peut exister déjà)

Et vous vous attendiez à voir :
- `operam_fr_articles` (domaine du concurrent)
- `nexir_fr_articles` (domaine du concurrent)
- etc.

---

## 📊 Ancien vs Nouveau système

### ❌ ANCIEN SYSTÈME (Global)

**Collections** :
- `competitor_articles` - TOUS les articles de TOUS les concurrents de TOUS les clients
- `client_articles` - TOUS les articles de TOUS les clients

**Problèmes** :
1. ❌ **Pas d'isolation** : Les données de tous les clients sont mélangées
2. ❌ **Sécurité** : Un client peut voir les concurrents d'un autre client
3. ❌ **Performance** : Collection énorme, recherches lentes
4. ❌ **Maintenance** : Impossible de supprimer les données d'un seul client
5. ❌ **Confusion** : Pour le trend pipeline, difficile de savoir quels articles appartiennent à quel client

### ✅ NOUVEAU SYSTÈME (Par client)

**Collections pour le client `innosys.fr`** :
- `innosys_fr_competitor_articles` - Articles des concurrents **POUR** innosys.fr
- `innosys_fr_client_articles` - Articles **DE** innosys.fr

**Collections pour le client `example.com`** :
- `example_com_competitor_articles` - Articles des concurrents **POUR** example.com
- `example_com_client_articles` - Articles **DE** example.com

**Avantages** :
1. ✅ **Isolation totale** : Chaque client a ses propres collections
2. ✅ **Sécurité** : Les données d'un client ne se mélangent jamais avec un autre
3. ✅ **Performance** : Collections plus petites, recherches plus rapides
4. ✅ **Maintenance** : Facile de supprimer toutes les données d'un client
5. ✅ **Clarté** : Le trend pipeline sait exactement quelle collection utiliser

---

## 🎯 Comment ça fonctionne

### Code : `qdrant_client.py`

```python
# Ligne 21 - ANCIEN système (legacy)
COLLECTION_NAME = "competitor_articles"  # ← Collection globale

# Ligne 47-63 - NOUVEAU système
def get_competitor_collection_name(client_domain: str) -> str:
    """
    Generate Qdrant collection name for competitor articles based on CLIENT domain.

    Format: {client_domain}_competitor_articles

    Args:
        client_domain: CLIENT domain name (e.g., "innosys.fr")

    Returns:
        Collection name (e.g., "innosys_fr_competitor_articles")
    """
    normalized_domain = client_domain.lower().replace(".", "_").replace("-", "_")
    return f"{normalized_domain}_competitor_articles"
```

### Code : `scrapping/agent.py` (ligne 430-440)

```python
# Index in Qdrant
if is_client_site:
    # Articles DU client innosys.fr
    collection_name = get_client_collection_name(domain)
    # → "innosys_fr_client_articles"
else:
    # Articles des concurrents POUR le client innosys.fr
    if client_domain:
        collection_name = get_competitor_collection_name(client_domain)
        # → "innosys_fr_competitor_articles"
    else:
        # Fallback vers ancien système (legacy)
        collection_name = COLLECTION_NAME
        # → "competitor_articles"
```

---

## 📦 Structure des collections

### Pour le client `innosys.fr`

**Collection : `innosys_fr_competitor_articles`**

Contient les articles scrapés de :
- operam.fr
- nexir.fr
- 5cloud.fr
- ... (tous les 50 concurrents validés)

**Métadonnées de chaque article** :
```json
{
  "article_id": 501,
  "domain": "operam.fr",  ← Domaine du CONCURRENT
  "title": "Article du concurrent",
  "url": "https://operam.fr/article",
  "collection": "innosys_fr_competitor_articles"  ← Collection du CLIENT
}
```

**Collection : `innosys_fr_client_articles`**

Contient les articles scrapés de :
- innosys.fr uniquement

---

## 🔧 Logique du nommage

### Pourquoi nommer avec le CLIENT et pas le CONCURRENT ?

**Cas d'usage réel** :

```
Client A (innosys.fr) a 50 concurrents : operam.fr, nexir.fr, ...
Client B (example.com) a 30 concurrents : operam.fr, other.com, ...
```

**Remarque** : `operam.fr` est concurrent de DEUX clients différents !

**Si on nommait par concurrent** :
- Collection `operam_fr_articles` contiendrait :
  - Articles pour le client A
  - Articles pour le client B
  - ❌ Mélange de données !

**Avec le nommage actuel** :
- Collection `innosys_fr_competitor_articles` contient :
  - Articles de operam.fr (pour innosys.fr)
  - Articles de nexir.fr (pour innosys.fr)
  - ✅ Isolation complète

- Collection `example_com_competitor_articles` contient :
  - Articles de operam.fr (pour example.com)
  - Articles de other.com (pour example.com)
  - ✅ Isolation complète

---

## 🎭 Exemple concret

### Scraping des concurrents pour `innosys.fr`

```python
# Dans run_missing_workflows_chain
client_domain = "innosys.fr"
competitor_domains = ["operam.fr", "nexir.fr", "5cloud.fr"]

for comp_domain in competitor_domains:
    await scraping_agent.discover_and_scrape_articles(
        db,
        comp_domain,  # ← Scrape operam.fr
        is_client_site=False,
        client_domain="innosys.fr",  # ← MAIS pour le client innosys.fr
    )
```

**Résultat** :
- Articles de `operam.fr` indexés dans `innosys_fr_competitor_articles`
- Articles de `nexir.fr` indexés dans `innosys_fr_competitor_articles`
- Articles de `5cloud.fr` indexés dans `innosys_fr_competitor_articles`

**Métadonnées préservées** :
Chaque article garde son `domain` d'origine (operam.fr, nexir.fr, etc.) dans les métadonnées, donc on peut toujours filtrer par concurrent si besoin.

---

## 🔎 Vérification de la collection

### Pour savoir quelle collection utiliser

**Trend pipeline** :
```python
from python_scripts.vectorstore.qdrant_client import get_competitor_collection_name

client_domain = "innosys.fr"
collection_name = get_competitor_collection_name(client_domain)
# → "innosys_fr_competitor_articles"
```

**Recherche d'articles d'un concurrent spécifique** :
```python
# Chercher articles de operam.fr dans la collection du client innosys.fr
from qdrant_client.models import Filter, FieldCondition, MatchValue

query_filter = Filter(
    must=[
        FieldCondition(
            key="domain",
            match=MatchValue(value="operam.fr")
        )
    ]
)

results = qdrant_client.search(
    collection_name="innosys_fr_competitor_articles",
    query_vector=embedding,
    filter=query_filter
)
```

---

## ⚠️ Migration de l'ancien système

### Si vous avez une ancienne collection `competitor_articles`

**Situation** :
- Ancienne collection `competitor_articles` existe (créée par `init_qdrant.py`)
- Nouvelle collection `innosys_fr_competitor_articles` créée récemment
- Les deux coexistent

**Options** :

**Option 1 : Conserver les deux (temporaire)** ✅
- Garder `competitor_articles` pour référence
- Utiliser `innosys_fr_competitor_articles` pour nouveau workflow
- Supprimer `competitor_articles` quand confirmé que nouveau système fonctionne

**Option 2 : Migrer les données**
```python
# Script de migration (à créer si nécessaire)
# 1. Lire tous les articles de "competitor_articles"
# 2. Identifier le client_domain pour chaque article
# 3. Ré-indexer dans la bonne collection par client
```

**Option 3 : Repartir à zéro** ✅ (recommandé)
- Supprimer `competitor_articles` (ancienne)
- Garder uniquement les nouvelles collections par client
- Re-scraper si nécessaire

---

## 📋 Résumé

### ✅ Le système fonctionne correctement

La collection `innosys_fr_competitor_articles` est **CORRECTE** :
- Elle stocke les articles des **concurrents** (operam.fr, nexir.fr, etc.)
- Elle est nommée d'après le **client** (innosys.fr) pour l'isolation
- C'est le **nouveau design** recommandé

### ❌ Ce qui serait incorrect

- Une collection nommée `operam_fr_articles` contenant des articles pour plusieurs clients différents
- Utiliser la collection globale `competitor_articles` pour tous les clients

### 🎯 Prochaines actions

1. **Vérifier les collections existantes** :
   ```python
   collections = qdrant_client.client.get_collections().collections
   for col in collections:
       print(col.name)
   ```

2. **Supprimer l'ancienne collection si elle existe** :
   ```python
   if qdrant_client.collection_exists("competitor_articles"):
       qdrant_client.client.delete_collection("competitor_articles")
   ```

3. **Confirmer le nouveau système fonctionne** :
   - Vérifier que les articles sont bien indexés
   - Vérifier que le trend pipeline fonctionne
   - Confirmer que la collection contient les articles attendus

---

## 🔗 Fichiers concernés

- `python_scripts/vectorstore/qdrant_client.py:47-63` - Fonction de nommage
- `python_scripts/agents/scrapping/agent.py:430-440` - Logique d'indexation
- `python_scripts/agents/trend_pipeline/agent.py:92-93` - Utilisation dans trend pipeline
- `scripts/init_qdrant.py:13` - Ancien système (legacy)

---

## ✅ Conclusion

Le comportement actuel est **CORRECT et intentionnel** :
- `innosys_fr_competitor_articles` = Articles des concurrents **pour le client** innosys.fr
- Nommage par **client** (pas par concurrent) pour isolation des données
- Chaque article garde son `domain` d'origine dans les métadonnées

C'est le design moderne recommandé pour multi-tenancy et isolation des données.
