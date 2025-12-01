# Project Specification: Agent Éditorial & Concurrentiel

**Feature ID:** 000-project-foundation  
**Feature Branch:** main  
**Status:** Ready for Planning  
**Version:** 1.2.0  
**Last Updated:** 2025-01-25  
**Owner:** Development Team  
**Priority:** Critical

---

## Overview

### Problem Statement

Les entreprises et professionnels du marketing de contenu manquent d'outils automatisés pour :

- Comprendre leur propre style éditorial de manière objective
- Identifier leurs concurrents réels sur le marché digital
- Analyser les tendances éditoriales de leur secteur
- Obtenir des recommandations data-driven pour leur stratégie de contenu

L'analyse manuelle de ces éléments prend des semaines et reste subjective. Les outils existants (SEMrush, Ahrefs) se focalisent sur le SEO technique mais négligent l'analyse éditoriale profonde.

### Solution

**Agent Éditorial & Concurrentiel** est un système multi-agents utilisant l'IA pour automatiser l'analyse éditoriale et concurrentielle complète. Le système :

1. **Crawle et analyse** le style éditorial d'un site (ton, structure, vocabulaire)
2. **Identifie automatiquement** les concurrents via recherche multi-sources
3. **Scrape et indexe** les articles de blog concurrents
4. **Détecte les tendances** thématiques avec topic modeling (BERTopic)
5. **Génère des recommandations** stratégiques basées sur les gaps détectés

### Key Benefits

**Pour les utilisateurs :**

- ⏱️ Temps d'analyse réduit de **3 semaines à 2 heures**
- 📊 **Objectivité** via analyse IA multi-modèles
- 🎯 **Recommandations actionnables** basées sur données réelles
- 🔄 **Monitoring continu** des tendances concurrentielles

**Pour le business :**

- 💰 Réduction coûts consulting (€5K-15K par analyse → €0)
- 📈 Amélioration performance éditoriale mesurable
- 🚀 Accélération time-to-market stratégie contenu

### Target Users

**Primary Users:**

- Responsables marketing de contenu (PME, ETI)
- Consultants SEO / Content Strategy
- Agences digitales

**Secondary Users:**

- Data analysts marketing
- Product managers SaaS B2B
- Équipes communication corporate

### Success Metrics

| Métrique | Baseline | Target (6 mois) |
|----------|----------|-----------------|
| Temps analyse complète | 2-3 semaines | < 3 heures |
| Précision identification concurrents | N/A | > 85% |
| Topics découverts pertinents | N/A | > 80% |
| Satisfaction utilisateur | N/A | > 4.5/5 |
| Coût par analyse | €8,000 | < €50 |

---

## User Stories

### Epic 1: Analyse Éditoriale Automatisée

#### US-001: Analyser le style éditorial d'un site (Priority: Critical)

**As a** responsable marketing de contenu  
**I want** analyser automatiquement le style éditorial de mon site web  
**So that** je comprends objectivement mon positionnement éditorial actuel

**Acceptance Scenarios:**

**Scenario 1: Analyse réussie d'un site standard**
- **Given** un domaine valide "example.com" avec 50+ pages de contenu
- **And** le site est accessible publiquement
- **When** je lance l'analyse éditoriale
- **Then** le système crawle max 50 pages en respectant robots.txt
- **And** génère un profil éditorial complet en < 10 minutes
- **And** le profil contient : niveau de langage, ton, structure, mots-clés, audience cible
- **And** les résultats sont sauvegardés dans site_profiles

**Scenario 2: Site avec contenu limité**
- **Given** un domaine avec < 10 pages de contenu
- **When** je lance l'analyse
- **Then** le système retourne un avertissement "Contenu insuffisant"
- **And** propose d'analyser avec un seuil réduit
- **And** génère un profil partiel si accepté

**Scenario 3: Domaine inaccessible**
- **Given** un domaine qui retourne 403 ou robots.txt interdit crawling
- **When** je tente l'analyse
- **Then** le système retourne une erreur explicite
- **And** propose d'analyser via URL unique fournie manuellement

**Business Rules:**

- Maximum 200 pages analysées par domaine (protection coûts)
- Respect obligatoire robots.txt et crawl-delay
- Analyse multi-LLM : 4 modèles spécialisés (llama3, mistral, phi3)
- Cache de 30 jours : réutilisation si domaine déjà analysé

**Dependencies:**

- Crawl4AI installé et configuré
- Ollama avec modèles téléchargés (llama3:8b, mistral:7b, phi3:medium)
- Qdrant collection créée pour le domaine
- PostgreSQL tables: site_profiles, workflow_executions

---

#### US-002: Consulter l'historique d'analyses (Priority: High)

**As a** utilisateur existant  
**I want** accéder à l'historique de mes analyses précédentes  
**So that** je peux comparer l'évolution de mon style éditorial

**Acceptance Scenarios:**

**Scenario 1: Liste des analyses**
- **Given** j'ai analysé 3 domaines dans le passé
- **When** j'accède à "/api/v1/sites"
- **Then** je vois la liste des 3 domaines avec date dernière analyse
- **And** statut de chaque analyse (completed, pending, failed)

**Scenario 2: Détail d'une analyse**
- **Given** une analyse complétée pour "example.com"
- **When** je requête "/api/v1/sites/example.com"
- **Then** je reçois le profil éditorial complet
- **And** métadonnées : date, nb pages analysées, durée, modèles utilisés

**Scenario 3: Comparaison temporelle**
- **Given** 2+ analyses du même domaine à dates différentes
- **When** je demande "/api/v1/sites/example.com/history"
- **Then** je vois l'évolution des métriques clés dans le temps

---

### Epic 2: Recherche Concurrentielle Automatisée

#### US-003: Identifier les concurrents automatiquement (Priority: Critical)

**As a** responsable marketing  
**I want** que le système identifie automatiquement mes concurrents  
**So that** je n'ai pas à les lister manuellement et découvre des acteurs ignorés

**Acceptance Scenarios:**

**Scenario 1: Recherche multi-sources avec stratégies optimisées**
- **Given** un site analysé "mon-site.com" avec profil éditorial
- **When** je lance la recherche concurrentielle
- **Then** le système génère 60 requêtes organisées en 6 stratégies (direct, services, combo, geo, competitive, alternatives)
- **And** exécute maximum 30 requêtes sur les 60 générées (sélection optimisée)
- **And** interroge 3 sources : Tavily, DuckDuckGo, Crawl4AI pour chaque requête
- **And** fusionne les résultats en liste unique dédupliquée
- **And** filtre par domaines .fr (TLD par défaut, configurable via paramètre si besoin)
- **And** track la performance de chaque stratégie (queries, results, valid_results, efficiency)
- **And** retourne top 10 concurrents classés par pertinence

**Scenario 2: Pipeline de validation avancé**
- **Given** une liste brute de 50+ domaines trouvés via recherche multi-sources (après génération et exécution requêtes)
- **When** le système applique le pipeline de validation complet
- **Then** étape 2 : déduplication par domaine (fusion résultats multi-sources, exclusion domaine analysé)
- **And** étape 3 : pré-filtrage automatique (exclusion PDFs, domaines interdits, listing platforms, outils SEO)
- **And** étape 4 : enrichissement homepage des top 50 candidats (description, services, keywords via crawl)
- **And** étape 5 : validation cross-source (boost si candidat trouvé dans plusieurs sources)
- **And** étape 6 : filtrage LLM avec phi3:medium évalue la pertinence avec contexte enrichi (seuil >= 0.6)
- **And** élimine les faux positifs (annuaires, marketplaces, médias généralistes)
- **And** étape 7 : calcul similarité sémantique avec embeddings (all-MiniLM-L6-v2)
- **And** étape 8 : validation analyse de contenu (mots-clés business, sections services actives)
- **And** étape 9 : ranking multi-critères (LLM score + cross-validation + géographie + sémantique)
- **And** étape 10 : assurance diversité (limites par catégorie, géographie, taille)
- **And** étape 11 : calcul score de confiance final pour chaque concurrent
- **And** étape 12 : filtrage final avec seuils ajustés (confidence >= 0.35, relevance >= 0.45)
- **And** garantit minimum 10 résultats si disponibles
- **And** conserve uniquement les vrais concurrents éditoriaux (directs 0.8-1.0 et indirects 0.6-0.79)

**Scenario 3: Aucun concurrent trouvé**
- **Given** un site de niche très spécifique
- **When** la recherche ne trouve aucun concurrent pertinent après filtrage
- **Then** le système retourne une liste vide avec explication
- **And** propose d'élargir les critères de recherche (baisser seuils, élargir stratégies)
- **And** log les métriques de performance des stratégies pour diagnostic

**Scenario 4: Garantie minimum de résultats**
- **Given** une recherche qui trouve au moins 10 candidats pertinents après validation
- **When** le filtrage final par score de confiance élimine trop de résultats
- **Then** le système garantit minimum 10 résultats si disponibles (relâchement intelligent des seuils)
- **And** priorise les meilleurs résultats même si score légèrement sous les seuils stricts

**Business Rules:**

- Minimum 3 concurrents, maximum 20 (minimum 10 garantis si disponibles)
- Exclusion automatique du domaine analysé
- Score de pertinence >= 0.6 pour être retenu (concurrents directs 0.8-1.0, indirects 0.6-0.79)
- Score de confiance >= 0.35 et pertinence >= 0.45 pour filtrage final (seuils ajustables)
- Cache des résultats : 7 jours
- TLD par défaut : .fr (configurable via paramètre si besoin)
- Tracking performance des stratégies de requêtes (queries, results, valid_results, efficiency) pour optimisation future
- Support concurrents directs (même produits/services, même marché) et indirects (même industrie, services complémentaires)

**Dependencies:**

- API Tavily configurée (optionnel)
- DuckDuckGo via package ddgs (recherche directe)
- LLM phi3:medium pour classification et filtrage
- Module query_generator pour génération requêtes multi-stratégies (6 types de stratégies)
- Embeddings utils pour calcul similarité sémantique (all-MiniLM-L6-v2)
- Crawl4AI pour enrichissement homepage des candidats (top 50)

---

#### US-004: Valider/ajuster la liste des concurrents (Priority: Medium)

**As a** utilisateur  
**I want** pouvoir valider ou ajuster la liste de concurrents proposée  
**So that** l'analyse porte sur les bons acteurs

**Acceptance Scenarios:**

**Scenario 1: Validation simple**
- **Given** une liste de 10 concurrents proposés
- **When** je valide la liste sans modification
- **Then** le système marque les 10 comme "validated"
- **And** lance automatiquement l'analyse de ces concurrents

**Scenario 2: Ajout manuel de concurrents**
- **Given** je connais 2 concurrents non détectés
- **When** j'ajoute manuellement "concurrent-1.fr" et "concurrent-2.fr"
- **Then** le système vérifie que les domaines existent
- **And** les ajoute à la liste avec flag "manual" (stockage dans workflow_executions.output_data avec metadata validation)
- **And** les inclut dans les analyses suivantes

**Scenario 3: Suppression de faux positifs**
- **Given** la liste contient "media-generaliste.fr" (faux positif)
- **When** je supprime ce domaine
- **Then** il est marqué "excluded" (stockage dans workflow_executions.output_data avec flags validation)
- **And** n'apparaît plus dans les analyses futures

**Business Rules:**

- Liste de concurrents stockée dans workflow_executions.output_data (JSONB) pour chaque recherche
- Flags de validation: "validated", "manual", "excluded" stockés dans metadata
- Liste validée utilisée comme source de vérité pour analyses suivantes

---

#### Détails Techniques: Stratégies de Génération de Requêtes

Le système génère 60 requêtes optimisées organisées en 6 stratégies distinctes pour maximiser la couverture et la pertinence :

**1. Stratégie Direct (20 requêtes)**
- Requêtes simples avec keywords primaires : `{keyword} site:.fr`
- Variations avec terme "services" : `{keyword} services site:.fr`
- Basée sur les 10 premiers keywords extraits du profil client
- Objectif : Trouver directement les acteurs mentionnant les mots-clés principaux

**2. Stratégie Combo (12 requêtes)**
- Combinaisons de paires de keywords : `{keyword1} {keyword2} site:.fr`
- Limite aux 4-5 premiers keywords pour éviter explosion combinatoire
- Objectif : Cibler les entreprises positionnées sur plusieurs domaines d'activité

**3. Stratégie Géographique (10 requêtes)**
- Keywords combinés avec régions : `{keyword} {region} site:.fr`
- Régions ciblées : Paris, Ile-de-France, région parisienne, Lyon, Nantes, France
- Basée sur les 2 premiers keywords
- Objectif : Découvrir les concurrents locaux/régionaux souvent ignorés

**4. Stratégie Competitive (12 requêtes)**
- Termes concurrentiels combinés avec keywords : `{term} {keyword} site:.fr`
- Termes utilisés : prestataire, partenaire, intégrateur, expert, spécialiste, société
- Basée sur les 2 premiers keywords
- Objectif : Identifier les entreprises positionnées comme experts/prestataires

**5. Stratégie Type ESN (6 requêtes)**
- Termes sectoriels combinés avec keywords : `{term} {keyword} site:.fr`
- Termes utilisés : ESN, SSII, société services numériques, agence digitale
- Objectif : Cibler spécifiquement les acteurs du secteur IT/services numériques

**6. Stratégie Alternatives (10 requêtes)**
- Requêtes basées sur le domaine analysé :
  - `alternatives {domain} site:.fr`
  - `concurrent {domain} site:.fr`
  - `similaire {domain} site:.fr`
  - `{domain} concurrents site:.fr`
- Combinaisons domain + keywords pour contextualiser
- Objectif : Découvrir les alternatives mentionnées dans les recherches comparatives

**Optimisation d'exécution :**

- Seulement 30 requêtes sur les 60 générées sont exécutées (sélection optimisée)
- Tracking de performance par stratégie pour identifier les plus efficaces
- Logging structuré pour optimisation future basée sur données réelles

---

#### Détails Techniques: Pipeline de Validation en 12 Étapes

Le pipeline de validation assure la qualité et la pertinence des concurrents identifiés :

**Étape 1 : Génération et Exécution Multi-Stratégies**
- Génération des 60 requêtes selon 6 stratégies
- Exécution de 30 requêtes maximum (optimisation performance)
- Recherche simultanée sur Tavily (si disponible) et DuckDuckGo pour chaque requête
- Tracking initial : nombre de requêtes par stratégie, results obtenus

**Étape 2 : Déduplication par Domaine**
- Fusion des résultats de toutes les sources par domaine unique
- Exclusion automatique du domaine analysé
- Conservation de toutes les métadonnées (sources multiples, scores, URLs)

**Étape 3 : Pré-filtrage Automatique**
- Exclusion des PDFs (URLs se terminant par .pdf)
- Exclusion des domaines interdits : .gouv.fr, .gov.fr, .edu.fr, .ac.fr, hal.*, archives-ouvertes
- Exclusion des outils d'analyse SEO : SimilarWeb, SitePrice, NicheProwler, SEMrush, Ahrefs, Moz
- Exclusion des plateformes de listing/agrégation : SortList, Digitiz, Clutch, GoodFirms, DesignRush
- Exclusion des sites médias/généralistes : latribune.fr, lemonde.fr, lesechos.fr, franceinfo.fr
- Détection de patterns "listing" dans titres/contenus (liste, classement, meilleur, top)

**Étape 4 : Enrichissement Homepage (Top 50 Candidats)**
- Crawl de la homepage des 50 meilleurs candidats après pré-filtre
- Extraction meta description ou premier paragraphe comme description
- Extraction section Services via patterns regex
- Extraction keywords d'activité (conseil, développement, web, digital, marketing, etc.)
- Skip automatique des PDFs et sites non-business (gouvernement, académique)
- Limitation : 3 services max, 5 keywords max pour éviter surcharge

**Étape 5 : Validation Cross-Source**
- Identification des candidats trouvés dans plusieurs sources (Tavily + DuckDuckGo)
- Boost de score pour ces candidats (+0.15 au score de base)
- Flag `cross_validated: true` pour traçabilité
- Objectif : Prioriser les concurrents confirmés par plusieurs sources

**Étape 6 : Filtrage LLM avec Contexte Enrichi**
- Utilisation de phi3:medium pour évaluation de pertinence
- Contexte fourni : domaine, description enrichie, services, keywords d'activité
- Seuil de pertinence >= 0.6 pour être retenu :
  - **Concurrents directs** (0.8-1.0) : Même produits/services, même marché
  - **Concurrents indirects** (0.6-0.79) : Même industrie, services complémentaires
- Raison obligatoire pour chaque concurrent retenu (explication de la pertinence)
- Fallback si LLM filtre tout : retour des top candidats avec score par défaut

**Étape 7 : Calcul Similarité Sémantique**
- Génération embedding du profil cible (keywords ou domaine)
- Génération embeddings batch des candidats (descriptions enrichies, limité à 30 pour performance)
- Calcul cosine similarity entre embedding cible et embeddings candidats
- Ajout du score `semantic_similarity` (0.0-1.0) à chaque candidat
- Utilisation all-MiniLM-L6-v2 (384 dimensions, modèle local)

**Étape 8 : Validation Analyse de Contenu**
- Vérification présence de mots-clés business dans titre/description/contenu
- Détection de sections Services actives (présence termes : services, prestations, offres, solutions)
- Vérification d'indicateurs de site actif (contact, devis, portfolio, actualités récentes)
- Exclusion des sites médias/news (détection via keywords médias dans domaine/contenu)
- Exclusion si aucun indicateur business (ni mots-clés, ni section services)

**Étape 9 : Ranking Multi-Critères**
- Calcul score de pertinence combiné :
  - LLM score : 50% du poids
  - Cross-validation bonus : +15% si trouvé dans plusieurs sources
  - Bonus géographique : +10% si même région/city détectée
  - Similarité sémantique : 25% du poids
- Tri par score calculé décroissant
- Priorité supplémentaire par source (Tavily > DuckDuckGo > Crawl4AI)

**Étape 10 : Assurance Diversité**
- Catégorisation des candidats : ESN, agence web, agence marketing, freelancer, autre
- Limitation par catégorie : max 5-10 par catégorie selon max_results et nombre de catégories
- Conservation de diversité géographique et de taille (PME vs ETI)
- Re-tri par score de pertinence après application des limites

**Étape 11 : Calcul Score de Confiance**
- Score combinant tous les critères : pertinence LLM, cross-validation, similarité sémantique, validation contenu
- Pondération selon fiabilité de chaque signal
- Score final 0.0-1.0 pour chaque candidat

**Étape 12 : Filtrage Final avec Seuils Ajustés**
- Filtrage par seuils minimums :
  - Score de confiance >= 0.35
  - Score de pertinence >= 0.45
- Garantie minimum 10 résultats si disponibles (relâchement intelligent si trop filtré)
- Limitation à max_results (défaut 10, max 20)
- Logging des métriques finales : total trouvé, sources utilisées, stratégies efficaces

**Tracking de Performance par Stratégie :**

- Pour chaque stratégie : nombre de requêtes exécutées, résultats obtenus, résultats valides après filtrage
- Calcul efficacité : valid_results / queries
- Logging structuré pour identification stratégies les plus performantes
- Données utilisables pour optimisation future (prioriser stratégies efficaces, ajuster distribution)

---

### Epic 3: Scraping & Analyse des Articles Concurrents

#### US-005: Scraper les articles des concurrents (Priority: Critical)

**As a** data analyst marketing  
**I want** collecter automatiquement les articles de blog des concurrents  
**So that** j'ai une base de données à jour pour l'analyse des tendances

**Acceptance Scenarios:**

**Scenario 1: Découverte et scraping réussi**
- **Given** un concurrent validé "concurrent.fr"
- **When** je lance le scraping
- **Then** le système détecte automatiquement le sitemap XML
- **And** identifie les URLs de type article/blog (pattern /blog/, /actualites/)
- **And** scrape jusqu'à 100 articles par domaine
- **And** extrait : titre, auteur, date, contenu nettoyé, mots-clés, image
- **And** sauvegarde dans competitor_articles avec toutes métadonnées

**Scenario 2: Respect des règles de scraping**
- **Given** robots.txt spécifie crawl-delay: 5
- **When** le scraping s'exécute
- **Then** le système attend 5 secondes entre chaque requête
- **And** respecte les paths disallowed
- **And** utilise le User-Agent déclaré
- **And** enregistre les permissions dans scraping_permissions

**Scenario 3: Site sans sitemap**
- **Given** un concurrent sans sitemap.xml
- **When** je lance le scraping
- **Then** le système cherche flux RSS alternatif
- **And** sinon, crawle les pages principales pour détecter liens articles
- **And** extrait max 50 articles via heuristiques HTML

**Business Rules:**

- Max 100 articles par concurrent
- Articles minimum 250 mots pour être conservés
- Date publication < 2 ans (articles récents uniquement)
- Déduplication par URL hash

**Dependencies:**

- Crawl4AI avec support async
- Playwright installé pour JS rendering
- Table competitor_articles créée
- Cache crawl_cache actif

---

#### US-006: Indexer sémantiquement les articles (Priority: High)

**As a** system  
**I want** indexer les articles dans un vectorstore  
**So that** je peux effectuer des recherches sémantiques et du clustering

**Acceptance Scenarios:**

**Scenario 1: Génération embeddings et indexation**
- **Given** 100 articles scrapés pour un concurrent
- **When** le pipeline d'indexation s'exécute
- **Then** génère embeddings pour chaque article (all-MiniLM-L6-v2)
- **And** indexe dans Qdrant collection "competitor_articles"
- **And** payload contient : article_id, domain, date, keywords, titre
- **And** stocke qdrant_point_id dans competitor_articles.qdrant_point_id

**Scenario 2: Détection de doublons**
- **Given** 2 articles avec similarité cosine > 0.92
- **When** l'indexation détecte cette similarité
- **Then** marque le 2ème article comme doublon
- **And** ne l'indexe pas dans Qdrant
- **And** log l'événement dans audit_log

**Scenario 3: Recherche sémantique**
- **Given** articles indexés dans Qdrant
- **When** je cherche "intelligence artificielle générative"
- **Then** retourne top 10 articles pertinents même sans mot-clé exact
- **And** inclut score de similarité pour chaque résultat

---

### Epic 4: Topic Modeling & Détection de Tendances

#### US-007: Analyser les tendances avec BERTopic (Priority: Critical)

**As a** stratège contenu  
**I want** identifier automatiquement les thèmes dominants chez mes concurrents  
**So that** je détecte les tendances du marché et les gaps de contenu

**Acceptance Scenarios:**

**Scenario 1: Analyse BERTopic sur 30 jours**
- **Given** 300+ articles concurrents des 30 derniers jours
- **When** je lance l'analyse des tendances
- **Then** BERTopic découvre automatiquement N topics (min 5, max 50)
- **And** chaque topic a : keywords principaux, cohérence score, nb articles
- **And** génère visualisations : carte 2D topics, barchart, évolution temporelle
- **And** sauvegarde résultats dans bertopic_analysis

**Scenario 2: Détection topics émergents**
- **Given** analyse sur 7 jours + analyse sur 30 jours
- **When** le système compare les deux périodes
- **Then** identifie les topics apparus dans les 7 derniers jours
- **And** marque comme "emerging" avec vélocité calculée
- **And** envoie alerte si topic émergent à forte croissance

**Scenario 3: Clustering hiérarchique**
- **Given** 20 topics découverts
- **When** je demande la hiérarchie
- **Then** BERTopic regroupe topics similaires en clusters parents
- **And** génère arbre hiérarchique visualisable
- **And** permet exploration drill-down topic → sous-topics

**Business Rules:**

- Minimum 50 articles pour analyse BERTopic valide
- Fenêtres temporelles : 7j, 30j, 90j
- Topics avec < 10 articles marqués comme "outliers"
- Régénération automatique tous les lundis

**Dependencies:**

- BERTopic 0.16+ installé
- UMAP + HDBSCAN pour clustering
- Embeddings pré-calculés dans Qdrant
- Table bertopic_analysis créée

---

#### US-008: Identifier les gaps de contenu (Priority: High)

**As a** responsable marketing  
**I want** comparer mes topics aux topics concurrents  
**So that** j'identifie les sujets que je ne couvre pas (gaps)

**Acceptance Scenarios:**

**Scenario 1: Comparaison client vs concurrents**
- **Given** analyse BERTopic de mon site + 5 concurrents
- **When** je demande l'analyse des gaps
- **Then** le système compare les ensembles de topics
- **And** identifie topics présents chez ≥3 concurrents mais absents chez moi
- **And** calcule "gap score" basé sur fréquence + importance topic

**Scenario 2: Recommandations de contenu**
- **Given** 5 gaps identifiés
- **When** je demande des recommandations
- **Then** pour chaque gap, suggère : titre article, mots-clés cibles, angle éditorial
- **And** priorise par impact estimé (fréquence × engagement concurrent)
- **And** génère calendrier éditorial suggéré

**Scenario 3: Suivi des gaps comblés**
- **Given** j'ai publié du contenu sur 2 gaps identifiés
- **When** je relance l'analyse après 30 jours
- **Then** le système détecte la couverture de ces topics
- **And** met à jour le gap score
- **And** marque comme "addressed" avec date

---

### Epic 5: API FastAPI & Orchestration

#### US-009: Exposer tous les workflows via API REST (Priority: Critical)

**As a** développeur  
**I want** accéder à toutes les fonctionnalités via API REST  
**So that** je peux intégrer le système dans d'autres applications

**Acceptance Scenarios:**

**Scenario 1: Lancement analyse éditoriale async**
- **Given** je fais une requête API vers le système
- **When** je POST /api/v1/sites/analyze avec {"domain": "example.com", "max_pages": 50}
- **Then** retourne 202 Accepted avec execution_id
- **And** lance l'analyse en background task
- **And** je peux suivre la progression via WebSocket

**Scenario 2: Suivi d'exécution en temps réel**
- **Given** une analyse en cours avec execution_id "abc-123"
- **When** je me connecte au WebSocket /api/v1/executions/abc-123/stream
- **Then** reçois messages JSON de progression
- **And** {"type": "progress", "current": 10, "total": 50, "message": "Crawling page 10"}
- **And** {"type": "completed", "result": {...}} à la fin

**Scenario 3: Documentation OpenAPI automatique**
- **Given** l'API FastAPI déployée
- **When** j'accède à /docs
- **Then** vois documentation Swagger UI interactive
- **And** tous les endpoints documentés avec schémas Pydantic
- **And** possibilité de tester directement dans l'interface

**API Endpoints Required:**

```
POST   /api/v1/sites/analyze                    # Launch editorial analysis
GET    /api/v1/sites/{domain}                   # Get site profile
GET    /api/v1/sites                            # List analyzed sites

POST   /api/v1/competitors/search               # Find competitors
GET    /api/v1/competitors/{domain}             # Get competitor list

POST   /api/v1/scraping/competitors             # Scrape competitor articles
GET    /api/v1/scraping/articles                # List scraped articles

POST   /api/v1/trends/analyze                   # Run BERTopic analysis
GET    /api/v1/trends/topics                    # Get discovered topics
GET    /api/v1/trends/gaps                      # Compare client vs competitors

GET    /api/v1/executions/{execution_id}        # Get workflow status
WS     /api/v1/executions/{execution_id}/stream # Real-time progress

GET    /api/v1/health                           # Health check
```

**Dependencies:**

- FastAPI 0.115+ avec Uvicorn
- Pydantic V2 pour tous les schemas
- Background tasks pour workflows longs
- WebSocket support pour streaming

---

#### US-010: Gérer les workflows avec traçabilité complète (Priority: High)

**As a** system administrator  
**I want** tracer toutes les exécutions de workflows  
**So that** je peux débugger, auditer et optimiser le système

**Acceptance Scenarios:**

**Scenario 1: Création et tracking workflow**
- **Given** un workflow "editorial_analysis" lancé
- **When** le système démarre l'exécution
- **Then** crée entrée dans workflow_executions avec status "pending"
- **And** génère execution_id unique (UUID)
- **And** enregistre : start_time, input_data, workflow_type

**Scenario 2: Mise à jour statuts intermédiaires**
- **Given** un workflow en cours
- **When** chaque étape se complète
- **Then** log dans audit_log : step_name, status, input/output, timestamp
- **And** enregistre dans performance_metrics : durée étape, tokens LLM, pages crawlées

**Scenario 3: Finalisation avec résultats**
- **Given** un workflow qui se termine avec succès
- **When** le système finalise
- **Then** met à jour workflow_executions : status="completed", end_time, output_data, was_success=true
- **And** calcule duration totale
- **And** enregistre agrégations dans performance_metrics (avg_duration, success_rate calculées via requêtes SQL si besoin)

**Scenario 4: Gestion des erreurs**
- **Given** une erreur survient pendant l'exécution
- **When** l'exception est catchée
- **Then** met à jour workflow_executions : status="failed", error_message, was_success=false
- **And** log complet dans audit_log avec stack trace
- **And** notifie l'utilisateur via API/WebSocket

---

## Functional Requirements

### FR-001: Crawling & Ingestion (MUST)

Le système DOIT pouvoir crawler et extraire le contenu de sites web en respectant :

- robots.txt et crawl-delay spécifié
- Limitation configurable du nombre de pages (default: 50, max: 200)
- Extraction de contenu nettoyé (sans HTML/CSS/JS)
- Détection automatique de sitemaps et flux RSS

### FR-002: Analyse Éditoriale Multi-LLM (MUST)

Le système DOIT analyser le style éditorial via 4 LLMs spécialisés :

- **llama3:8b** : Extraction domaines d'activité + analyse ton/style
- **mistral:7b** : Analyse structure de contenu
- **phi3:medium** : Extraction mots-clés stratégiques
- Synthèse finale fusionnant les 4 analyses

### FR-003: Recherche Concurrentielle Multi-Sources (MUST)

Le système DOIT identifier concurrents via un pipeline avancé multi-étapes :

**Génération de requêtes optimisées :**

- Génération de 60 requêtes organisées en 6 stratégies distinctes :
  - **Direct** : 20 requêtes - keywords simples avec site:.fr
  - **Services** : variations avec terme "services"
  - **Combo** : 12 requêtes - paires de keywords combinés
  - **Geo** : 10 requêtes - keywords + régions géographiques (Paris, Lyon, etc.)
  - **Competitive** : 12 requêtes - termes concurrentiels (prestataire, expert, spécialiste)
  - **Alternatives** : 10 requêtes - variations (alternatives, concurrent, similaire + domain)
- Extraction intelligente de keywords depuis profil client (activity_domains, keywords primaires/secondaires)
- Limitation d'exécution à 30 requêtes maximum sur les 60 générées (optimisation performance)

**Recherche multi-sources :**

- Tavily Search API (si disponible, max 100 résultats, recherche avancée)
- DuckDuckGo via package ddgs (recherche directe, région fr-fr, filtre site:.fr)
- Crawl4AI pour exploration manuelle (optionnel, extraction depuis résultats de recherche)

**Pipeline de validation en 12 étapes :**

1. **Génération et exécution** : Requêtes multi-stratégies avec tracking performance par stratégie
2. **Déduplication** : Fusion résultats par domaine, exclusion domaine analysé
3. **Pré-filtrage** : Exclusion PDFs, domaines interdits (.gouv.fr, .edu.fr, outils SEO, listing platforms)
4. **Enrichissement** : Crawl homepage top 50 candidats (description, services, keywords d'activité)
5. **Validation cross-source** : Boost si candidat trouvé dans plusieurs sources
6. **Filtrage LLM** : phi3:medium avec contexte enrichi, seuil >= 0.6 (directs 0.8-1.0, indirects 0.6-0.79)
7. **Similarité sémantique** : Calcul embeddings (all-MiniLM-L6-v2), cosine similarity avec profil cible
8. **Validation contenu** : Analyse présence mots-clés business, sections services actives
9. **Ranking multi-critères** : Score combiné (LLM 50% + cross-validation 15% + géographie 10% + sémantique 25%)
10. **Assurance diversité** : Limites par catégorie (ESN, agence web, etc.), géographie, taille
11. **Score de confiance** : Calcul final combinant tous les critères
12. **Filtrage final** : Seuils ajustés (confidence >= 0.35, relevance >= 0.45), garantie minimum 10 résultats si disponibles

**Tracking et optimisation :**

- Métriques par stratégie : queries exécutées, résultats obtenus, résultats valides, efficacité
- Logging structuré pour identification stratégies les plus efficaces
- Données utilisables pour optimisation future des stratégies de recherche

### FR-004: Scraping Éthique (MUST)

Le système DOIT respecter les règles de scraping :

- Lecture obligatoire de robots.txt avant tout crawl
- Respect du crawl-delay spécifié (default: 2s)
- User-Agent identifiable : "EditorialBot/1.0 (+URL)"
- Cache de 24h des permissions pour éviter requêtes répétées
- Limitation à 100 articles maximum par domaine

### FR-005: Indexation Vectorielle (MUST)

Le système DOIT indexer tous les contenus dans Qdrant :

- Génération embeddings avec modèle local (all-MiniLM-L6-v2 pour MVP)
- Collection unique "competitor_articles" pour MVP (single-tenant, separation par source post-MVP si besoin)
- Payload riche : metadata + texte + embeddings
- Déduplication automatique (similarité cosine > 0.92)
- Stockage du qdrant_point_id dans competitor_articles.qdrant_point_id pour traçabilité

### FR-006: Topic Modeling BERTopic (MUST)

Le système DOIT appliquer BERTopic pour détecter tendances :

- Découverte automatique du nombre de topics (min: 5, max: 50)
- Analyse temporelle sur fenêtres : 7j, 30j, 90j
- Génération visualisations interactives (HTML)
- Détection topics émergents par comparaison périodes

### FR-007: API REST Complète (MUST)

Le système DOIT exposer API REST avec :

- Tous les workflows accessibles via endpoints
- Validation Pydantic de tous les inputs
- Responses structurées avec status codes standards
- Documentation OpenAPI auto-générée (Swagger UI)
- Rate limiting configurable par endpoint

### FR-008: Background Tasks (MUST)

Le système DOIT gérer workflows longs en asynchrone :

- FastAPI BackgroundTasks pour analyses > 30s
- Retour immédiat avec execution_id
- Suivi progression via WebSocket (optionnel) ou polling
- Notifications fin d'exécution (webhook ou email)

### FR-009: Traçabilité Complète (MUST)

Le système DOIT logger toutes les exécutions :

- Table workflow_executions : id, type, status, timestamps, input/output
- Table audit_log : logs détaillés par étape
- Table performance_metrics : durée, tokens LLM, pages crawlées, métriques par étape
- Agrégations calculées : avg_duration, success_rate via requêtes SQL sur performance_metrics et workflow_executions

### FR-010: Base de Données PostgreSQL (MUST)

Le système DOIT utiliser PostgreSQL avec :

- SQLAlchemy 2.0+ async
- 10 tables principales (voir Constitution Article VI)
- Migrations Alembic versionnées
- Index sur : domain, execution_id, status, created_at
- Types JSONB pour données flexibles avec schemas Pydantic

### FR-011: Cache Intelligent (SHOULD)

Le système DEVRAIT implémenter cache multi-niveaux :

- crawl_cache : Hash URL + contenu (éviter re-crawl)
- scraping_permissions : robots.txt cached 24h
- popular_domains : Stats domaines fréquemment analysés
- Invalidation automatique après X jours (configurable)

### FR-012: Monitoring & Health Checks (SHOULD)

Le système DEVRAIT exposer métriques de santé :

- Endpoint /api/v1/health vérifiant : PostgreSQL, Qdrant, Ollama
- Métriques Prometheus-compatible (optionnel)
- Logs structurés JSON (structlog)
- Alertes automatiques sur erreurs critiques

### FR-013: Export & Reporting (COULD)

Le système POURRAIT permettre exports :

- Rapports PDF générés depuis résultats d'analyse
- Export CSV des articles scrapés
- Export JSON des topics BERTopic
- Intégration Google Sheets/Excel (optionnel)

### FR-014: Data Retention & Purge (MUST)

Le système DOIT implémenter purge automatique des données :

- Conservation des articles scrapés : 90 jours maximum
- Job automatique de purge quotidien supprimant articles > 90 jours
- Purge également des données associées : embeddings Qdrant, métriques, cache
- Logs de purge dans audit_log pour traçabilité RGPD
- Réanalyse nécessaire pour obtenir historique au-delà de 90 jours

### FR-015: Rate Limiting API (MUST)

Le système DOIT implémenter rate limiting pour protéger l'API publique :

- Rate limiting par IP : 100 requêtes/minute par défaut
- Configuration flexible par endpoint (analyses plus restrictives)
- Retour HTTP 429 Too Many Requests avec headers Retry-After
- Pas d'authentification requise pour MVP (API publique)

### FR-016: Authentification (COULD - Post-MVP)

Le système POURRAIT implémenter authentification post-MVP :

- JWT tokens ou API keys pour sécurisation renforcée
- Multi-tenancy (isolation données par tenant) si besoin SaaS
- Rate limiting par utilisateur (remplace ou complète rate limiting par IP)
- Gestion quotas (X analyses/mois par utilisateur)

---

## Non-Functional Requirements

### NFR-001: Performance

- Analyse éditoriale complète : < 10 minutes pour 50 pages
- Recherche concurrents : < 2 minutes
- Scraping 100 articles : < 15 minutes (dépend crawl-delay)
- Analyse BERTopic 300 articles : < 5 minutes
- API response time : < 500ms (endpoints non-background)

### NFR-002: Scalabilité

- Support jusqu'à 1000 domaines analysés simultanément (single-tenant MVP)
- PostgreSQL optimisé pour 10M+ articles indexés (avec purge automatique 90j)
- Qdrant scaling horizontal si > 100M embeddings
- FastAPI workers configurables (2-8 selon load)
- Architecture single-tenant : pas de complexité multi-client initiale

### NFR-003: Fiabilité

- Uptime target : 99.5%
- Retry logic sur toutes opérations I/O (max 3 tentatives)
- Graceful degradation si service externe down (Tavily, Ollama)
- Backups PostgreSQL quotidiens + point-in-time recovery

### NFR-004: Maintenabilité

- Code coverage tests : ≥ 80%
- Documentation inline (docstrings) : 100% des fonctions publiques
- Type hints obligatoires (mypy strict mode)
- CI/CD : linting + tests automatiques sur chaque PR

### NFR-005: Sécurité

- Variables sensibles en .env (jamais hardcodées)
- SQL injection protection (SQLAlchemy ORM)
- Rate limiting API : 100 req/min par IP (MVP sans authentification)
- Validation stricte inputs (Pydantic)
- Purge automatique données après 90 jours (compliance RGPD)

### NFR-006: Observabilité

- Logs structurés JSON avec contexte (execution_id, agent_name)
- Métriques détaillées par agent (durée, tokens, erreurs)
- Tracing distribué (LangSmith pour LLM calls)
- Dashboard monitoring (Grafana recommandé)

---

## Success Criteria

### Definition of Done (Feature Complete)

Le projet est considéré complet quand :

**✅ Core Functionality:**

- Analyse éditoriale fonctionne sur 10+ sites test variés
- Recherche concurrentielle retourne ≥5 concurrents pertinents
- Scraping respecte 100% des robots.txt testés
- BERTopic découvre topics cohérents sur dataset test 300 articles
- API expose tous endpoints avec documentation Swagger

**✅ Quality Assurance:**

- Tests automatisés : coverage ≥ 80%
- Tous tests passent (unit + integration + e2e)
- Linting : 0 erreurs (ruff, black, mypy)
- Performance : tous benchmarks NFR respectés
- Documentation complète : README + Architecture + API

**✅ Operations:**

- Docker Compose démarre tous services (PostgreSQL, Qdrant, Ollama)
- Migrations Alembic appliquées automatiquement
- Health checks retournent "healthy"
- CI/CD pipeline exécute en < 10 minutes
- Logs accessibles et structurés

**✅ User Acceptance:**

- 3 utilisateurs beta testent avec succès
- Satisfaction moyenne ≥ 4/5
- 0 bug bloquant reporté
- Temps d'onboarding < 30 minutes

### Acceptance Testing

**Test 1: End-to-End Workflow Complet**

```
1. POST /api/v1/sites/analyze avec domain="test-site.fr"
   → Expected: 202 + execution_id
2. Poll GET /api/v1/executions/{id} jusqu'à status="completed"
   → Expected: completion en < 10 min
3. GET /api/v1/sites/test-site.fr
   → Expected: profil éditorial complet avec tous champs
4. POST /api/v1/competitors/search avec domain="test-site.fr"
   → Expected: ≥5 concurrents retournés
5. POST /api/v1/scraping/competitors avec competitors list
   → Expected: ≥50 articles scrapés
6. POST /api/v1/trends/analyze
   → Expected: ≥10 topics découverts + visualisations générées
```

**Test 2: Performance sous Charge**

```
- 10 analyses éditoriales lancées simultanément
- Expected: toutes complètent en < 15 min
- Expected: 0 erreur, 0 timeout
- Expected: PostgreSQL latency < 100ms
```

**Test 3: Resilience aux Erreurs**

```
- Domaine inexistant → erreur claire retournée
- robots.txt interdit crawl → erreur avec suggestion alternative
- Ollama down → retry puis fallback graceful
- PostgreSQL down → retry puis 503 Service Unavailable
```

---

## Technical Constraints

### Mandatory Technologies

- **Python:** 3.10+ (3.12 recommandé)
- **Frame
work API:** FastAPI 0.115+
- **Database:** PostgreSQL 15+
- **Vectorstore:** Qdrant
- **LLMs:** Ollama local (llama3, mistral, phi3)
- **ORM:** SQLAlchemy 2.0 async
- **Scraping:** Crawl4AI module (PAS conteneur)
- **Topic Modeling:** BERTopic 0.16+

### Prohibited

- ❌ Synchronous code for I/O operations
- ❌ Direct SQL queries (use SQLAlchemy)
- ❌ Hardcoded secrets in code
- ❌ Missing type hints on functions
- ❌ Missing tests for new features

### Preferred Patterns

- ✅ Domain-Driven Design
- ✅ Repository Pattern for data access
- ✅ Dependency Injection (FastAPI Depends)
- ✅ CQRS léger (read/write separation)
- ✅ Event-driven communication entre agents

---

## Architecture Decisions & Clarifications

### Authentication Strategy (RESOLVED)

**Decision:** Pas d'authentification pour MVP (API publique avec rate limiting par IP)  
**Rationale:** MVP plus rapide à développer, adapté pour tests internes et validation conceptuelle  
**Impact:** Architecture API simplifiée, rate limiting par IP uniquement (pas de JWT/API keys pour MVP)  
**Future:** Migration vers authentification (API keys ou JWT) possible post-MVP si nécessaire  
**Status:** ✅ Resolved 2025-01-25

### Multi-Tenancy (RESOLVED)

**Decision:** Single-tenant MVP uniquement  
**Rationale:** Architecture simplifiée pour MVP, pas de besoin multi-client initial  
**Impact:** Schéma DB sans tenant_id, une seule collection Qdrant, pas d'isolation requise  
**Future:** Architecture peut évoluer vers multi-tenant post-MVP si besoin (ajout tenant_id possible)  
**Status:** ✅ Resolved 2025-01-25

### [NEEDS CLARIFICATION: LLM Providers]

**Question:** Supporter OpenAI/Anthropic en plus d'Ollama local ?  
**Impact:** Abstraction LLM provider, gestion coûts, fallback strategy  
**Stakeholder:** Tech Lead  
**Priority:** Low (peut être ajouté post-MVP)

### Data Retention / RGPD (RESOLVED)

**Decision:** Conservation 90 jours puis purge automatique  
**Rationale:** Minimisation risques RGPD, réduction stockage, politique claire et simple  
**Impact:** Job de purge automatique à implémenter, données supprimées après 90 jours, réanalyse nécessaire pour historique  
**RGPD Compliance:** Politique claire de rétention, droit à l'oubli implémenté via purge automatique  
**Status:** ✅ Resolved 2025-01-25

### [NEEDS CLARIFICATION: Internationalization]

**Question:** Support multi-langues (analyse sites EN, ES, DE) ?  
**Impact:** Modèles spaCy par langue, prompts LLM traduits  
**Stakeholder:** Product Owner  
**Priority:** Low (focus FR d'abord)

---

## Dependencies & Prerequisites

### External Services

- **Tavily API** (optionnel) : Clé API pour recherche premium
- **OpenAI API** (optionnel) : Fallback si Ollama insufficient
- **Qdrant Cloud** (optionnel) : Alternative à instance locale

### Infrastructure Requirements

- **Docker & Docker Compose** : Orchestration services (PostgreSQL, Qdrant, Ollama)
- **Min 16GB RAM** : Ollama + BERTopic + Qdrant in-memory
- **Min 50GB disk** : Modèles Ollama + DB + embeddings
- **Python 3.10+** : Runtime application
- **uv** : Gestionnaire dépendances moderne

### Pre-Installation

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Playwright (for Crawl4AI)
playwright install

# Download Ollama models
ollama pull llama3:8b
ollama pull mistral:7b
ollama pull phi3:medium

# Note: Embeddings generated via Sentence-Transformers (all-MiniLM-L6-v2)
# Model downloaded automatically on first use, no manual pull needed

# Install spaCy language model
python -m spacy download fr_core_news_md
```

---

## Related Documents

- **Constitution:** `.specify/memory/constitution.md` - Principes architecturaux non-négociables
- **Database Schema:** `docs/db_schema.sql` - Schéma PostgreSQL complet
- **Issues GitHub:** `docs/issues_github.md` + `docs/issues_github_etape2.md` - Backlog détaillé
- **Architecture:** `docs/architecture.md` - Diagrammes architecture système
- **Prompts:** `python_scripts/agents/prompts.py` - Tous les prompts LLM

---

## Glossary

| Terme | Définition |
|-------|------------|
| **Agent** | Module autonome avec rôle spécifique (analysis, competitor, scraping, topic modeling) |
| **Workflow** | Séquence d'étapes orchestrées (ex: editorial_analysis = crawl → LLM → synthesis → save) |
| **Embedding** | Vecteur numérique représentant sémantiquement un texte (384 dimensions pour all-MiniLM-L6-v2, généré via Sentence-Transformers) |
| **Topic** | Thème découvert par BERTopic, représenté par cluster + keywords |
| **Gap** | Sujet présent chez concurrents mais absent dans contenu client |
| **Crawl-delay** | Délai imposé par robots.txt entre requêtes (secondes) |
| **Execution ID** | UUID unique identifiant une exécution de workflow |
| **Constitutional Compliance** | Respect strict des principes définis dans constitution.md |

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.2.0 | 2025-01-25 | Dev Team | Fixed inconsistencies: Removed workflow_stats table reference (use performance_metrics aggregations), fixed competitor_article_embeddings reference (use competitor_articles.qdrant_point_id), removed authentication mentions from US-009, harmonized embedding model (all-MiniLM-L6-v2), clarified FR-005 single collection MVP, added POST /competitors/{domain}/validate endpoint to contracts, clarified competitor storage structure. |
| 1.1.0 | 2025-01-25 | Dev Team | Resolved critical clarifications: Single-tenant MVP, 90-day data retention with auto-purge, no authentication for MVP (rate limiting by IP). Added FR-014 (Data Retention), FR-015 (Rate Limiting), updated NFR-005 and NFR-002. |
| 1.0.0 | 2025-01-25 | Dev Team | Initial comprehensive specification |

---

**Status:** ✅ READY FOR PLANNING  
**Next Step:** Use `/speckit.plan` to generate technical architecture plan

---

**Constitutional Compliance Declaration:**

✅ This specification adheres to all principles defined in `.specify/memory/constitution.md`  
✅ All technical choices align with Article I (Architecture & Stack)  
✅ All requirements respect Article II (Code Standards)  
✅ Testing strategy follows Article III (Tests mandatory)  
✅ Agent architecture matches Article IV (Agents IA)  
✅ API design conforms to Article V (FastAPI Standards)
