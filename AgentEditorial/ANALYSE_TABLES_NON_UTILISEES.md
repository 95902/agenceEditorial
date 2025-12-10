# Rapport d'analyse des tables de la base de données

## Résumé exécutif

- **Total de tables analysées** : 27
- **Tables avec modèle et utilisées** : 24
- **Tables avec modèle mais non utilisées** : 0
- **Tables sans modèle mais référencées** : 3
- **Tables sans modèle et non utilisées** : 0

## 1. Tables à supprimer (sans modèle et non utilisées)

Ces tables existent dans la base de données mais n'ont pas de modèle SQLAlchemy et ne sont pas utilisées dans le code.

**Aucune table dans cette catégorie** - Toutes les tables sans modèle sont référencées dans les migrations.

## 2. Tables sans modèle mais référencées (à supprimer)

Ces tables sont référencées uniquement dans les migrations (pour suppression) mais n'ont pas de modèle SQLAlchemy. Elles devraient être supprimées.

### `bertopic_analysis`

- **Modèle SQLAlchemy** : ❌ Non défini
- **Données dans la DB** : 0 ligne(s) (32 kB)
- **Raison** : Migration `e40ad65afb31_remove_unused_tables.py` a été créée pour supprimer cette table car elle n'était utilisée que par un router de trends qui a été supprimé
- **Statut migration** : ⚠️ Migration non appliquée (version actuelle: `d30ad65afb30`)
- **Références dans le code** :
  - **migrations** : 2 fichier(s)
    - `python_scripts/database/migrations/versions/e40ad65afb31_remove_unused_tables.py` (suppression prévue)
    - `python_scripts/database/migrations/versions/74e1785c0a4b_initial_schema.py` (création initiale)
  - **sql_queries** : Références uniquement dans les scripts d'analyse (non fonctionnelles)

**Action recommandée** : Appliquer la migration `e40ad65afb31` ou supprimer manuellement la table.

### `editorial_trends`

- **Modèle SQLAlchemy** : ❌ Non défini
- **Données dans la DB** : 0 ligne(s) (40 kB)
- **Raison** : Migration `e40ad65afb31_remove_unused_tables.py` indique qu'elle n'est utilisée nulle part
- **Statut migration** : ⚠️ Migration non appliquée (version actuelle: `d30ad65afb30`)
- **Références dans le code** :
  - **migrations** : 2 fichier(s)
    - `python_scripts/database/migrations/versions/e40ad65afb31_remove_unused_tables.py` (suppression prévue)
    - `python_scripts/database/migrations/versions/74e1785c0a4b_initial_schema.py` (création initiale)
  - **sql_queries** : Références uniquement dans les scripts d'analyse (non fonctionnelles)

**Action recommandée** : Appliquer la migration `e40ad65afb31` ou supprimer manuellement la table.

### `hybrid_trends_analysis`

- **Modèle SQLAlchemy** : ❌ Non défini
- **Données dans la DB** : 0 ligne(s) (48 kB)
- **Raison** : Aucune référence trouvée dans le code, probablement une table obsolète créée pour une fonctionnalité jamais implémentée
- **Références dans le code** :
  - **sql_queries** : Références uniquement dans les scripts d'analyse (non fonctionnelles)
  - **migrations** : Aucune migration trouvée (table créée manuellement ou migration supprimée)

**Action recommandée** : Créer une migration pour supprimer cette table ou la supprimer manuellement.

## 3. Tables avec modèle mais non utilisées

Ces tables ont un modèle SQLAlchemy mais ne sont pas référencées dans le code.

**Aucune table dans cette catégorie** - Tous les modèles sont utilisés dans le code.

## 4. Tables avec 0 lignes (vides mais potentiellement utilisées)

Ces tables ont un modèle et sont utilisées dans le code, mais ne contiennent actuellement aucune donnée :

- `client_coverage_analysis` : 0 lignes (40 kB) - Modèle: `ClientCoverageAnalysis`
- `client_strengths` : 0 lignes (32 kB) - Modèle: `ClientStrength`
- `crawl_cache` : 0 lignes (56 kB) - Modèle: `CrawlCache`
- `error_logs` : 0 lignes (104 kB) - Modèle: `ErrorLog`
- `scraping_permissions` : 0 lignes (32 kB) - Modèle: `ScrapingPermission`
- `topic_temporal_metrics` : 0 lignes (24 kB) - Modèle: `TopicTemporalMetrics`
- `weak_signals_analysis` : 0 lignes (24 kB) - Modèle: `WeakSignalAnalysis`

**Note** : Ces tables sont vides mais sont utilisées dans le code. Elles peuvent être remplies lors d'exécutions futures.

## 5. Recommandations

### Actions immédiates : Supprimer les tables obsolètes

#### 1. Appliquer la migration existante

La migration `e40ad65afb31_remove_unused_tables.py` a été créée pour supprimer `bertopic_analysis` et `editorial_trends` mais n'a pas été appliquée.

```bash
# Appliquer la migration
cd AgentEditorial
alembic upgrade head
```

#### 2. Supprimer `hybrid_trends_analysis`

Cette table n'a pas de migration de suppression. Options :

**Option A : Créer une migration**
```bash
alembic revision -m "remove_hybrid_trends_analysis_table"
# Puis ajouter dans upgrade():
op.drop_table('hybrid_trends_analysis')
```

**Option B : Supprimer manuellement**
```sql
DROP TABLE IF EXISTS hybrid_trends_analysis CASCADE;
```

### Tables à conserver

Les tables suivantes sont vides mais doivent être conservées car elles sont utilisées dans le code :
- `client_coverage_analysis` - Utilisée dans le Trend Pipeline (Stage 4)
- `client_strengths` - Utilisée dans le Trend Pipeline (Stage 4)
- `crawl_cache` - Utilisée pour le cache de crawling
- `error_logs` - Utilisée pour le logging d'erreurs
- `scraping_permissions` - Utilisée pour les permissions de scraping
- `topic_temporal_metrics` - Utilisée dans le Trend Pipeline (Stage 2)
- `weak_signals_analysis` - Utilisée dans le Trend Pipeline (Stage 3)

## 6. Détails complets par table

| Table | Modèle | Utilisé | Lignes | Taille | Statut |
|-------|--------|---------|--------|--------|--------|
| `article_recommendations` | ✅ | ✅ | 108 | 192 kB | ✅ OK |
| `audit_log` | ✅ | ✅ | 20 | 96 kB | ✅ OK |
| `bertopic_analysis` | ❌ | ❌ | 0 | 32 kB | ⚠️ À supprimer |
| `client_articles` | ✅ | ✅ | 16 | 328 kB | ✅ OK |
| `client_coverage_analysis` | ✅ | ✅ | 0 | 40 kB | ✅ Vide mais utilisée |
| `client_strengths` | ✅ | ✅ | 0 | 32 kB | ✅ Vide mais utilisée |
| `competitor_articles` | ✅ | ✅ | 2323 | 36 MB | ✅ OK |
| `content_roadmap` | ✅ | ✅ | 34 | 56 kB | ✅ OK |
| `crawl_cache` | ✅ | ✅ | 0 | 56 kB | ✅ Vide mais utilisée |
| `discovery_logs` | ✅ | ✅ | 301 | 144 kB | ✅ OK |
| `editorial_gaps` | ✅ | ✅ | 36 | 144 kB | ✅ OK |
| `editorial_trends` | ❌ | ❌ | 0 | 40 kB | ⚠️ À supprimer |
| `error_logs` | ✅ | ✅ | 0 | 104 kB | ✅ Vide mais utilisée |
| `hybrid_trends_analysis` | ❌ | ❌ | 0 | 48 kB | ⚠️ À supprimer |
| `performance_metrics` | ✅ | ✅ | 15 | 96 kB | ✅ OK |
| `scraping_permissions` | ✅ | ✅ | 0 | 32 kB | ✅ Vide mais utilisée |
| `site_analysis_results` | ✅ | ✅ | 1 | 96 kB | ✅ OK |
| `site_discovery_profiles` | ✅ | ✅ | 101 | 248 kB | ✅ OK |
| `site_profiles` | ✅ | ✅ | 1 | 64 kB | ✅ OK |
| `topic_clusters` | ✅ | ✅ | 36 | 272 kB | ✅ OK |
| `topic_outliers` | ✅ | ✅ | 200 | 88 kB | ✅ OK |
| `topic_temporal_metrics` | ✅ | ✅ | 0 | 24 kB | ✅ Vide mais utilisée |
| `trend_analysis` | ✅ | ✅ | 36 | 112 kB | ✅ OK |
| `trend_pipeline_executions` | ✅ | ✅ | 2 | 112 kB | ✅ OK |
| `url_discovery_scores` | ✅ | ✅ | 5496 | 6040 kB | ✅ OK |
| `weak_signals_analysis` | ✅ | ✅ | 0 | 24 kB | ✅ Vide mais utilisée |
| `workflow_executions` | ✅ | ✅ | 8 | 928 kB | ✅ OK |

## 7. Explication des tables non utilisées

### Pourquoi ces tables existent encore ?

1. **`bertopic_analysis` et `editorial_trends`** :
   - Une migration de suppression (`e40ad65afb31`) a été créée mais n'a jamais été appliquée
   - La version actuelle de la base est `d30ad65afb30` (une version avant la migration de suppression)
   - Ces tables étaient utilisées par un ancien router de trends qui a été supprimé

2. **`hybrid_trends_analysis`** :
   - Aucune migration trouvée pour cette table
   - Probablement créée manuellement ou via une migration supprimée
   - Aucune référence dans le code fonctionnel

### Impact de la suppression

- **`bertopic_analysis`** : Aucun impact, table vide et non utilisée
- **`editorial_trends`** : Aucun impact, table vide et non utilisée
- **`hybrid_trends_analysis`** : Aucun impact, table vide et non utilisée

**Total d'espace à récupérer** : ~120 kB (négligeable)

## 8. Actions à effectuer

### Priorité 1 : Appliquer la migration existante

```bash
cd /home/mbragance_innosys/Documents/CursorProject/agenceEditorial/AgentEditorial
alembic upgrade head
```

Cela supprimera automatiquement `bertopic_analysis` et `editorial_trends`.

### Priorité 2 : Supprimer `hybrid_trends_analysis`

Créer une nouvelle migration ou supprimer manuellement :

```sql
DROP TABLE IF EXISTS hybrid_trends_analysis CASCADE;
```

Puis mettre à jour la version Alembic si nécessaire.

---

**Date d'analyse** : 2025-12-10
**Version de la base** : `d30ad65afb30`
**Migration à appliquer** : `e40ad65afb31` (remove_unused_tables)
