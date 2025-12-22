# Issue #002 : Personnalisation des summaries de domaines d'activité

**Date de création** : 2025-01-25  
**Statut** : À implémenter  
**Priorité** : Moyenne  
**Type** : Amélioration / Feature  
**Labels** : `audit-endpoint`, `domains`, `data-enrichment`, `storage`

---

## Contexte

L'endpoint `/api/v1/sites/{domain}/audit` retourne actuellement des summaries génériques identiques pour tous les domaines d'activité. Par exemple, tous les domaines reçoivent le même summary : `"Innosys SSII, ESN PARIS, Business Solutions, Systèmes & Réseaux, Conseils"`.

### Problème actuel

La fonction `_generate_domain_summary()` dans `python_scripts/api/routers/sites.py` :
- Utilise les mêmes mots-clés généraux du site pour tous les domaines
- Ne filtre pas assez précisément les articles par domaine
- Ne stocke pas les summaries en base de données
- Recalcule les summaries à chaque requête (inefficace)

**Résultat** : Tous les domaines ont le même summary, ce qui n'apporte pas de valeur différenciée.

---

## Objectif

Générer et stocker des summaries personnalisés pour chaque domaine d'activité, basés sur :
1. Les articles client correspondant spécifiquement à ce domaine
2. Les mots-clés extraits de ces articles
3. Les termes pertinents depuis les titres et contenus

Les summaries doivent être :
- **Personnalisés** : Uniques pour chaque domaine
- **Stockés en base** : Persistés dans `site_profiles.activity_domains`
- **Mis à jour** : Régénérés lors de nouveaux articles scrapés

---

## Solutions proposées

### Option 1 : Enrichir `activity_domains` avec `domain_details` ⭐ **RECOMMANDÉE**

**Principe** : Ajouter une structure `domain_details` dans le JSONB `activity_domains` pour stocker les summaries et métadonnées.

**Structure proposée** :
```json
{
  "primary_domains": ["Cloud Computing", "Cybersécurité", "Intelligence Artificielle"],
  "secondary_domains": [...],
  "domain_details": {
    "cloud-computing": {
      "label": "Cloud Computing",
      "summary": "Infrastructure AWS/Azure, architectures distribuées, migration cloud, services IaaS/PaaS",
      "topics_count": 45,
      "confidence": 92,
      "last_updated": "2025-01-25T10:30:00Z"
    },
    "cybersecurite": {
      "label": "Cybersécurité",
      "summary": "Protection des données, conformité RGPD, audits de sécurité, gestion des risques",
      "topics_count": 38,
      "confidence": 88,
      "last_updated": "2025-01-25T10:30:00Z"
    }
  }
}
```

**Avantages** :
- ✅ Pas de nouvelle table (utilise JSONB existant)
- ✅ Données liées au profil (cohérent)
- ✅ Facile à mettre à jour
- ✅ Pas de migration complexe

**Inconvénients** :
- ⚠️ Requêtes JSONB (mais PostgreSQL gère bien)
- ⚠️ Pas d'historique (mais peut être ajouté)

### Option 2 : Nouvelle table `domain_summaries`

**Principe** : Créer une table dédiée pour les summaries de domaines.

**Structure proposée** :
- `id` (PK)
- `site_profile_id` (FK vers `site_profiles`)
- `domain_label` (VARCHAR)
- `domain_slug` (VARCHAR, indexé)
- `summary` (TEXT)
- `topics_count` (INTEGER)
- `confidence` (INTEGER)
- `created_at`, `updated_at` (TIMESTAMP)

**Avantages** :
- ✅ Structure normalisée
- ✅ Requêtes SQL simples
- ✅ Historique possible (via `updated_at`)

**Inconvénients** :
- ❌ Migration nécessaire
- ❌ Plus de complexité
- ❌ Jointure supplémentaire

### Option 3 : Réutiliser les données du trend pipeline

**Principe** : Utiliser les synthèses déjà générées par le trend pipeline (LLM) et mapper les domaines aux topics.

**Avantages** :
- ✅ Réutilise des données existantes
- ✅ Synthèses déjà générées par LLM (qualité)

**Inconvénients** :
- ❌ Dépend du trend pipeline (doit être exécuté)
- ❌ Mapping domaine ↔ topic à faire
- ❌ Pas toujours disponible

---

## Recommandation : Option 1

### Implémentation proposée

#### 1. Fonction de génération de summary personnalisé

Créer/modifier `_generate_domain_summary_persistent()` qui :
- Filtre les articles client correspondant au domaine spécifique
- Extrait des termes depuis les titres et mots-clés de ces articles
- Génère un summary unique basé sur les termes les plus fréquents
- Retourne un summary personnalisé

**Critères de correspondance article ↔ domaine** :
- Titre contient des mots-clés du domaine
- Mots-clés de l'article contiennent des termes du domaine
- Contenu (premiers 500 caractères) mentionne le domaine

#### 2. Fonction de stockage

Créer `_save_domain_summaries_to_profile()` qui :
- Génère les summaries pour tous les domaines d'activité
- Met à jour `site_profiles.activity_domains.domain_details`
- Sauvegarde en base de données

#### 3. Points d'appel

**Génération initiale** :
- Après le scraping client (quand on a les articles)
- Dans `run_analysis_background` ou après le scraping

**Mise à jour** :
- Lors de nouveaux articles scrapés (incrémental)
- Via endpoint dédié `/sites/{domain}/regenerate-summaries` (manuel)

#### 4. Récupération dans `/audit`

Modifier `build_complete_audit_from_database()` pour :
- Lire depuis `activity_domains.domain_details` si disponible
- Si absent, générer à la volée (fallback) et proposer de sauvegarder

---

## Structure de données détaillée

### Format `domain_details` dans `activity_domains`

```json
{
  "primary_domains": ["Cloud Computing", "Cybersécurité"],
  "secondary_domains": ["DevOps", "Transformation Digitale"],
  "domain_details": {
    "cloud-computing": {
      "label": "Cloud Computing",
      "summary": "Infrastructure AWS/Azure, architectures distribuées, migration cloud",
      "topics_count": 45,
      "confidence": 92,
      "last_updated": "2025-01-25T10:30:00Z",
      "source_articles_count": 12
    },
    "cybersecurite": {
      "label": "Cybersécurité",
      "summary": "Protection des données, conformité RGPD, audits de sécurité",
      "topics_count": 38,
      "confidence": 88,
      "last_updated": "2025-01-25T10:30:00Z",
      "source_articles_count": 10
    }
  }
}
```

---

## Algorithme de génération de summary

### Étape 1 : Identification des articles correspondants

Pour chaque domaine :
1. Extraire les mots-clés du label (ex: "Cloud Computing" → ["cloud", "computing"])
2. Ajouter des synonymes/variations selon le domaine
3. Filtrer les articles client où :
   - Le titre contient au moins 2 mots-clés du domaine
   - OU les mots-clés de l'article contiennent des termes du domaine
   - OU le contenu (500 premiers caractères) mentionne le domaine

### Étape 2 : Extraction de termes

Depuis les articles correspondants :
1. **Titres** : Extraire des mots significatifs (>4 caractères, hors mots vides)
2. **Mots-clés** : Utiliser les `primary_keywords` des articles
3. **Fréquence** : Compter les occurrences de chaque terme

### Étape 3 : Génération du summary

1. Prendre les 3-5 termes les plus fréquents
2. Filtrer les termes déjà présents dans le label du domaine
3. Construire le summary : `", ".join(top_terms)`
4. Limiter à 5 termes maximum pour la concision

### Étape 4 : Stockage

1. Construire la structure `domain_details`
2. Mettre à jour `site_profiles.activity_domains`
3. Sauvegarder en base

---

## Points d'intégration

### 1. Après scraping client

**Fichier** : `python_scripts/api/routers/discovery.py` ou `python_scripts/agents/scrapping/agent.py`

**Moment** : Après que les articles client ont été scrapés et sauvegardés

**Action** : Appeler la fonction de génération et stockage des summaries

### 2. Endpoint de régénération manuelle

**Endpoint** : `POST /api/v1/sites/{domain}/regenerate-summaries`

**Usage** : Permet de régénérer les summaries manuellement si besoin

### 3. Mise à jour incrémentale

**Moment** : Lors de nouveaux articles scrapés (batch)

**Action** : Mettre à jour seulement les summaries des domaines concernés

---

## Métriques de qualité

Pour valider la personnalisation :

1. **Diversité** : Chaque domaine doit avoir un summary unique
2. **Pertinence** : Les termes doivent être liés au domaine
3. **Cohérence** : Les summaries doivent refléter le contenu réel des articles

**Tests** :
- Vérifier que 2 domaines différents ont des summaries différents
- Vérifier que les termes extraits apparaissent bien dans les articles correspondants
- Vérifier que les summaries sont mis à jour après nouveau scraping

---

## Prochaines étapes

1. **Validation** : Approuver l'Option 1 (enrichissement de `activity_domains`)
2. **Implémentation** : 
   - Créer la fonction de génération personnalisée
   - Créer la fonction de stockage
   - Intégrer après scraping client
3. **Tests** : Valider avec des données réelles
4. **Documentation** : Documenter la structure `domain_details`

---

## Notes

- **Performance** : La génération peut être coûteuse si beaucoup d'articles. Limiter à 50-100 articles max par domaine.
- **Fallback** : Si pas assez d'articles correspondants, utiliser les mots-clés généraux du site (comportement actuel).
- **Mise à jour** : Les summaries peuvent être régénérés périodiquement ou à la demande.

---

## Historique

- **2025-01-25** : Création de l'issue, identification du problème des summaries génériques

