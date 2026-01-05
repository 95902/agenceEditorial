# Issue #003 : Assignation des topic_id aux articles après clustering

**Date de création** : 2025-12-22  
**Date d'implémentation** : 2025-01-25  
**Statut** : Implémenté  
**Priorité** : Haute  
**Type** : Bug / Amélioration  
**Labels** : `trend-pipeline`, `clustering`, `qdrant`, `topic-assignment`, `data-integrity`

---

## Contexte

Lors de l'exécution du trend pipeline (clustering BERTopic), les topic clusters sont correctement créés et stockés dans la base de données (`topic_clusters`), mais les `topic_id` ne sont **pas assignés aux articles** dans Qdrant ni dans PostgreSQL.

### Problème actuel

1. **Clustering fonctionne** : Le trend pipeline crée correctement les clusters (13 clusters créés pour innosys.fr)
2. **Articles indexés** : Les articles sont bien indexés dans Qdrant (16/16 articles client, 1936 articles concurrents)
3. **topic_id manquant** : Aucun article n'a de `topic_id` dans son payload Qdrant ou dans la colonne `topic_id` de PostgreSQL
4. **Impact** : Impossible d'associer les articles aux clusters créés, ce qui empêche :
   - L'analyse de couverture par topic
   - L'identification des gaps éditoriaux
   - La génération de recommandations ciblées
   - Le calcul du nombre de topics par domaine d'activité

### Diagnostic effectué

**Vérification Qdrant** :
- Collection `innosys_fr_client_articles` : 16 points, aucun avec `topic_id`
- Collection `innosys_fr_competitor_articles` : 1936 points, aucun avec `topic_id`
- Topic clusters en base : 13 clusters avec `topic_id` (0 à 12)

**Vérification PostgreSQL** :
- `client_articles.topic_id` : 0/16 articles avec `topic_id` assigné
- `competitor_articles.topic_id` : Non vérifié mais probablement 0 également

---

## Objectif

Assigner automatiquement les `topic_id` aux articles (client et concurrents) après le clustering BERTopic, à la fois dans :
1. **Qdrant** : Mettre à jour le payload des points avec le `topic_id`
2. **PostgreSQL** : Mettre à jour la colonne `topic_id` des articles

---

## Analyse technique

### Workflow actuel du trend pipeline

1. **Stage 1 - Clustering** :
   - Récupère les articles depuis Qdrant
   - Génère les embeddings
   - Exécute BERTopic + HDBSCAN
   - Crée les clusters et les sauvegarde dans `topic_clusters`
   - **❌ Ne met pas à jour les articles avec les topic_id**

2. **Stage 2 - Temporal Analysis** :
   - Analyse l'évolution temporelle des topics
   - **❌ Ne nécessite pas les topic_id sur les articles**

3. **Stage 3 - LLM Enrichment** :
   - Génère des synthèses et recommandations
   - **❌ Ne nécessite pas les topic_id sur les articles**

4. **Stage 4 - Gap Analysis** :
   - Analyse les gaps de couverture
   - **⚠️ Nécessite les topic_id sur les articles pour fonctionner correctement**

### Données disponibles

Le clustering produit :
- `topics` : Liste des topic_id assignés à chaque document (par index)
- `document_ids` : Liste des IDs des documents (stockés dans `topic_clusters.document_ids`)
- `clusters` : Métadonnées des clusters (topic_id, label, size, etc.)

**Problème** : Le mapping `document_id` → `article_id` n'est pas fait automatiquement.

---

## Solutions proposées

### Option 1 : Assignation dans le Stage 1 (clustering) ⭐ **RECOMMANDÉE**

**Principe** : Après le clustering, mettre à jour les articles avec les `topic_id` assignés.

**Implémentation** :
1. Après le clustering BERTopic, récupérer les `topics` (liste des topic_id par document)
2. Mapper les indices des documents aux `document_ids` (qui sont les `qdrant_point_id`)
3. Pour chaque article :
   - Mettre à jour le payload Qdrant avec `topic_id`
   - Mettre à jour la colonne `topic_id` en PostgreSQL

**Avantages** :
- ✅ Assignation immédiate après clustering
- ✅ Données cohérentes pour les stages suivants
- ✅ Pas de traitement supplémentaire nécessaire

**Inconvénients** :
- ⚠️ Nécessite de mapper `document_id` → `article_id` (qdrant_point_id → article DB)

### Option 2 : Assignation dans un stage dédié

**Principe** : Créer un nouveau stage (1.5) entre clustering et temporal analysis.

**Avantages** :
- ✅ Séparation des responsabilités
- ✅ Plus facile à déboguer

**Inconvénients** :
- ❌ Ajoute une étape supplémentaire
- ❌ Complexité inutile

### Option 3 : Script de correction post-clustering

**Principe** : Créer un script séparé qui peut être exécuté après le clustering.

**Avantages** :
- ✅ Flexibilité (peut être exécuté à tout moment)
- ✅ Ne modifie pas le pipeline principal

**Inconvénients** :
- ❌ Nécessite une exécution manuelle
- ❌ Risque d'oubli
- ❌ Données incohérentes entre les stages

---

## Recommandation : Option 1

### Implémentation détaillée

#### 1. Modifier `_execute_stage_1_clustering`

**Fichier** : `python_scripts/agents/trend_pipeline/agent.py`

**Ajout après la création des clusters** :
```python
# Après avoir sauvegardé les clusters en base
# Assigner les topic_id aux articles

# Récupérer les document_ids depuis les clusters
document_topic_mapping = {}
for i, topic_id in enumerate(topics):
    if i < len(document_ids):
        doc_id = document_ids[i]
        if topic_id != -1:  # Ignorer les outliers
            document_topic_mapping[doc_id] = topic_id

# Mettre à jour Qdrant et PostgreSQL
await assign_topics_to_documents(
    db_session=self.db_session,
    document_topic_mapping=document_topic_mapping,
    domains=domains,
    client_domain=client_domain
)
```

#### 2. Créer la fonction `assign_topics_to_documents`

**Fichier** : `python_scripts/agents/trend_pipeline/topic_assignment.py` (nouveau fichier)

**Fonctionnalités** :
- Prendre le mapping `document_id` → `topic_id`
- Pour chaque document :
  - Identifier s'il s'agit d'un article client ou concurrent
  - Mettre à jour le payload Qdrant
  - Mettre à jour la colonne `topic_id` en PostgreSQL

**Logique de mapping** :
- `document_id` = `qdrant_point_id` (UUID)
- Chercher l'article correspondant dans `client_articles` ou `competitor_articles`
- Mettre à jour les deux sources

#### 3. Mise à jour Qdrant

**Utiliser** : `qdrant_client.client.set_payload()` pour mettre à jour le payload

**Exemple** :
```python
qdrant_client.client.set_payload(
    collection_name=collection_name,
    payload={"topic_id": topic_id},
    points=[qdrant_point_id]
)
```

#### 4. Mise à jour PostgreSQL

**Utiliser** : CRUD functions existantes ou requêtes directes

**Exemple** :
```python
# Pour client_articles
stmt = update(ClientArticle).where(
    ClientArticle.qdrant_point_id == qdrant_point_id
).values(topic_id=topic_id)

# Pour competitor_articles
stmt = update(CompetitorArticle).where(
    CompetitorArticle.qdrant_point_id == qdrant_point_id
).values(topic_id=topic_id)
```

---

## Structure de données

### Mapping document_id → topic_id

Le clustering produit :
```python
topics = [0, 0, 1, -1, 2, 0, ...]  # topic_id par document (index)
document_ids = [
    "uuid-1", "uuid-2", "uuid-3", ...
]  # qdrant_point_id par document
```

**Mapping à créer** :
```python
{
    "uuid-1": 0,  # Document 1 → Topic 0
    "uuid-2": 0,  # Document 2 → Topic 0
    "uuid-3": 1,  # Document 3 → Topic 1
    "uuid-4": -1, # Document 4 → Outlier (ignorer)
    "uuid-5": 2,  # Document 5 → Topic 2
    ...
}
```

### Identification article client vs concurrent

**Méthode 1** : Vérifier dans quelle collection se trouve le point
- Si dans `{domain}_client_articles` → article client
- Si dans `{domain}_competitor_articles` → article concurrent

**Méthode 2** : Chercher dans PostgreSQL
- Chercher dans `client_articles` par `qdrant_point_id`
- Si trouvé → article client
- Sinon → chercher dans `competitor_articles`

---

## Points d'intégration

### 1. Dans le trend pipeline

**Fichier** : `python_scripts/agents/trend_pipeline/agent.py`

**Moment** : Après `_execute_stage_1_clustering`, avant `_execute_stage_2_temporal`

**Code** :
```python
# Dans execute() après stage_1
if results["stages"]["stage_1"]["success"]:
    # Assigner les topics aux articles
    assignment_result = await assign_topics_after_clustering(
        db_session=self.db_session,
        clusters=results["stages"]["stage_1"]["clusters"],
        topics=results["stages"]["stage_1"]["topics"],
        document_ids=results["stages"]["stage_1"]["document_ids"],
        domains=domains,
        client_domain=client_domain
    )
    results["stages"]["topic_assignment"] = assignment_result
```

### 2. Nouveau module

**Fichier** : `python_scripts/agents/trend_pipeline/topic_assignment.py` (nouveau)

**Fonctions** :
- `assign_topics_after_clustering()` : Fonction principale
- `update_qdrant_payload()` : Mise à jour Qdrant
- `update_postgresql_topic_id()` : Mise à jour PostgreSQL
- `identify_article_type()` : Identifier client vs concurrent

---

## Tests à effectuer

### Tests unitaires

1. **Mapping document_id → topic_id** :
   - Vérifier que le mapping est correct
   - Vérifier que les outliers (-1) sont ignorés

2. **Mise à jour Qdrant** :
   - Vérifier que le payload est mis à jour
   - Vérifier que les points existent

3. **Mise à jour PostgreSQL** :
   - Vérifier que les `topic_id` sont assignés
   - Vérifier que les articles sont trouvés

### Tests d'intégration

1. **Workflow complet** :
   - Exécuter le trend pipeline
   - Vérifier que les articles ont des `topic_id` après le clustering
   - Vérifier la cohérence entre Qdrant et PostgreSQL

2. **Performance** :
   - Vérifier que l'assignation ne ralentit pas trop le pipeline
   - Optimiser les batch updates si nécessaire

---

## Métriques de validation

Pour valider la correction :

1. **Cohérence Qdrant** :
   - 100% des articles indexés ont un `topic_id` dans leur payload (ou `null` si outlier)
   - Les `topic_id` correspondent aux clusters créés

2. **Cohérence PostgreSQL** :
   - 100% des articles ont un `topic_id` (ou `null` si outlier)
   - Les `topic_id` correspondent à ceux dans Qdrant

3. **Cohérence clusters** :
   - Le nombre d'articles par topic correspond à `topic_clusters.size`
   - Les articles peuvent être retrouvés via `topic_clusters.document_ids`

---

## Prochaines étapes

1. **Validation** : Approuver l'Option 1 (assignation dans Stage 1)
2. **Implémentation** :
   - Créer le module `topic_assignment.py`
   - Modifier `agent.py` pour appeler l'assignation
   - Tester avec un dataset réduit
3. **Tests** : Valider avec des données réelles
4. **Documentation** : Documenter le nouveau comportement

---

## Notes

- **Outliers** : Les documents avec `topic_id = -1` (outliers) ne doivent pas avoir de `topic_id` assigné (garder `null`)
- **Performance** : Pour de grandes collections, utiliser des batch updates (100-1000 articles à la fois)
- **Rollback** : En cas d'erreur, ne pas rollback les clusters créés, seulement l'assignation
- **Idempotence** : L'assignation doit être idempotente (peut être relancée sans problème)

---

## Historique

- **2025-12-22** : Création de l'issue, identification du problème d'assignation des topic_id
- **2025-12-22** : Diagnostic effectué, vérification Qdrant et PostgreSQL
- **2025-01-25** : Implémentation complète
  - Création du module `topic_assignment.py`
  - Intégration dans `agent.py` après le Stage 1 (clustering)
  - Mise à jour automatique des payloads Qdrant et colonnes PostgreSQL
  - Gestion des erreurs et logging détaillé

---

## Références

- Issue #002 : Personnalisation des summaries de domaines (utilise les topic_id)
- Trend Pipeline : `python_scripts/agents/trend_pipeline/agent.py`
- Qdrant Client : `python_scripts/vectorstore/qdrant_client.py`
- Models : `python_scripts/database/models.py` (ClientArticle, CompetitorArticle, TopicCluster)


