# Plan d'amélioration de la découverte d'articles

> **Projet** : Agent Éditorial & Concurrentiel  
> **Module** : `ScrapingAgent` - Découverte d'articles  
> **Date** : Décembre 2024  
> **Version** : 2.0

---

## Table des matières

1. [Diagnostic du code actuel](#diagnostic-du-code-actuel)
2. [Architecture améliorée proposée](#architecture-améliorée-proposée)
3. [PHASE 0 — Profilage du site](#phase-0--profilage-du-site)
4. [PHASE 1 — Découverte multi-sources améliorée](#phase-1--découverte-multi-sources-améliorée)
5. [PHASE 2 — Scoring de probabilité](#phase-2--scoring-de-probabilité)
6. [PHASE 3 — Extraction adaptative](#phase-3--extraction-adaptative)
7. [Nouvelles tables de données](#nouvelles-tables-de-données)
8. [Workflow d'exécution amélioré](#workflow-dexécution-amélioré)
9. [Métriques de suivi](#métriques-de-suivi)
10. [Annexes](#annexes)

---

## Diagnostic du code actuel

### Forces actuelles

| Fonctionnalité | Statut |
|----------------|--------|
| 3 stratégies de découverte (sitemap, RSS, heuristics) | ✅ |
| Filtrage des extensions indésirables | ✅ |
| Filtrage des pages de catégories | ✅ |
| Détection des offres d'emploi | ✅ |
| Gestion des redirections de domaines | ✅ |
| Normalisation des URLs (www) | ✅ |

### Faiblesses identifiées

| Problème | Impact | Priorité |
|----------|--------|----------|
| Patterns d'URL statiques | Rate les sites avec structures atypiques | 🔴 Haute |
| Pas d'apprentissage par site | Chaque crawl repart de zéro | 🔴 Haute |
| Heuristiques HTML limitées | Manque schema.org, Open Graph, JSON-LD | 🔴 Haute |
| Pas de scoring de confiance | Traitement binaire (article ou non) | 🟠 Moyenne |
| Pagination basique | Rate les articles anciens | 🟠 Moyenne |
| Pas de détection de CMS | Ne profite pas des APIs natives | 🟠 Moyenne |
| Pas de détection de structure | Ne s'adapte pas au site | 🟡 Basse |

### Statistiques actuelles (estimation)

- **Taux de découverte** : ~60-70% des articles disponibles
- **Taux de faux positifs** : ~15-20% (URLs non-articles scrapées)
- **Sites problématiques** : Sites custom sans patterns standards

---

## Architecture améliorée proposée

### Vue d'ensemble du pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PHASE 0 : Profilage du site                      │
│  Analyser la structure AVANT de chercher les articles               │
│  → Détection CMS, APIs, patterns d'URL, sélecteurs optimaux         │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PHASE 1 : Découverte multi-sources               │
│  Sitemap → RSS → API headless → Crawl intelligent                   │
│  → Utilise le profil pour prioriser les sources                     │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PHASE 2 : Scoring & Validation                   │
│  Chaque URL reçoit un score de probabilité "article"                │
│  → Tri par score, sélection des meilleurs candidats                 │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PHASE 3 : Extraction adaptative                  │
│  Utiliser le profil du site pour extraction optimale                │
│  → Sélecteurs personnalisés, validation post-extraction             │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FEEDBACK : Amélioration continue                 │
│  Mettre à jour le profil avec les résultats                         │
│  → Success rate, sélecteurs efficaces, patterns validés             │
└─────────────────────────────────────────────────────────────────────┘
```

### Gains attendus

| Métrique | Avant | Après (cible) |
|----------|-------|---------------|
| Taux de découverte | ~65% | > 85% |
| Taux de validité | ~80% | > 90% |
| Sites WordPress optimisés | Non | Oui (API REST) |
| Temps de re-crawl | 100% | -40% (profil réutilisé) |

---

## PHASE 0 — Profilage du site

### Objectif

Analyser la structure du site **une seule fois** et sauvegarder le "profil de découverte" pour les crawls suivants. Ce profil permet d'adapter la stratégie de découverte à chaque site.

### Éléments à détecter

#### A. Structure des URLs

| Élément | Exemple | Méthode de détection |
|---------|---------|----------------------|
| Pattern de date | `/2024/06/15/mon-article` | Regex sur sitemap/RSS |
| Pattern de slug | `/blog/mon-article-seo` | Analyse des URLs connues |
| Pattern de catégorie | `/categorie/sous-cat/article` | Profondeur d'URL |
| Pattern d'ID | `/article/12345` | Regex numérique |
| Préfixe de blog | `/actualites/`, `/insights/` | Fréquence dans sitemap |

**Regex de détection** :

```python
URL_PATTERN_DETECTORS = {
    "wordpress_date": r"/\d{4}/\d{2}/\d{2}/[\w-]+/?$",
    "wordpress_month": r"/\d{4}/\d{2}/[\w-]+/?$",
    "slug_only": r"/blog/[\w-]+/?$",
    "category_slug": r"/[\w-]+/[\w-]+/[\w-]+/?$",
    "numeric_id": r"/(?:article|post|p)/\d+/?$",
}
```

#### B. Technologie du site (CMS)

| CMS/Framework | Indices de détection | Impact sur découverte |
|---------------|---------------------|----------------------|
| **WordPress** | `/wp-content/`, `/wp-json/`, `<meta name="generator" content="WordPress">` | ✅ Utiliser REST API |
| **Drupal** | `/node/`, `/sites/default/`, `Drupal.settings` | Structure spécifique |
| **Hubspot** | `hs-sites.com`, `<meta name="generator" content="HubSpot">` | API disponible |
| **Ghost** | `/ghost/`, `<meta name="generator" content="Ghost">` | API Content |
| **Webflow** | `webflow.com`, `data-wf-site` | Structure spécifique |
| **Wix** | `wix.com`, `_wix_browser_sess` | Limité |
| **Shopify** | `cdn.shopify.com`, `/blogs/` | Structure blog spécifique |
| **Custom** | Aucun pattern connu | Heuristiques renforcées |

**Code de détection CMS** :

```python
CMS_DETECTION_RULES = {
    "wordpress": {
        "html_patterns": [
            r'<meta name="generator" content="WordPress',
            r'/wp-content/',
            r'/wp-includes/',
        ],
        "url_patterns": [
            r'/wp-json/',
            r'/xmlrpc\.php',
        ],
        "headers": {
            "X-Powered-By": "WordPress",
        }
    },
    "drupal": {
        "html_patterns": [
            r'Drupal\.settings',
            r'/sites/default/files/',
            r'<meta name="generator" content="Drupal',
        ],
    },
    "ghost": {
        "html_patterns": [
            r'<meta name="generator" content="Ghost',
            r'ghost-(?:card|content)',
        ],
    },
    "hubspot": {
        "html_patterns": [
            r'<meta name="generator" content="HubSpot',
            r'hs-scripts\.com',
            r'hsforms\.net',
        ],
    },
}
```

#### C. Points d'entrée des articles

| Source | Fiabilité | Méthode de détection |
|--------|-----------|---------------------|
| API REST (WordPress) | ⭐⭐⭐⭐⭐ | Test `/wp-json/wp/v2/posts` |
| Sitemap dédié blog | ⭐⭐⭐⭐⭐ | `sitemap-blog.xml`, `sitemap-posts.xml` |
| RSS principal | ⭐⭐⭐⭐ | `<link rel="alternate" type="application/rss+xml">` |
| Ghost Content API | ⭐⭐⭐⭐ | Test `/ghost/api/content/posts/` |
| Page listing blog | ⭐⭐⭐ | `/blog/`, `/actualites/` avec pagination |
| Schema.org CollectionPage | ⭐⭐⭐⭐ | JSON-LD dans la page listing |

### Algorithme de profilage

```
FONCTION profiler_site(domain):
    profil = {}
    
    # 1. Détecter le CMS
    html_homepage = fetch(domain)
    profil.cms = detecter_cms(html_homepage)
    
    # 2. Tester les APIs natives
    SI profil.cms == "wordpress":
        api_test = fetch(domain + "/wp-json/wp/v2/posts?per_page=1")
        SI api_test.status == 200:
            profil.api_endpoints = {
                "posts": "/wp-json/wp/v2/posts",
                "categories": "/wp-json/wp/v2/categories"
            }
            profil.has_rest_api = True
    
    # 3. Découvrir les sitemaps
    profil.sitemap_urls = []
    POUR chaque sitemap_path DANS SITEMAP_LOCATIONS:
        test = fetch(domain + sitemap_path)
        SI test.status == 200 ET est_xml_valide(test):
            profil.sitemap_urls.append(sitemap_path)
            # Chercher sitemaps imbriqués
            SI contient_sitemap_index(test):
                profil.sitemap_urls += extraire_sous_sitemaps(test)
    
    # 4. Découvrir les flux RSS
    profil.rss_feeds = extraire_rss_links(html_homepage)
    profil.rss_feeds += tester_rss_communs(domain)
    
    # 5. Analyser les patterns d'URL
    urls_echantillon = collecter_urls_echantillon(profil)
    profil.url_patterns = analyser_patterns(urls_echantillon)
    
    # 6. Détecter la pagination
    page_blog = fetch(domain + "/blog/")
    profil.pagination_pattern = detecter_pagination(page_blog)
    
    # 7. Tester les sélecteurs de contenu
    article_test = fetch(urls_echantillon[0])
    profil.content_selector = trouver_meilleur_selecteur(article_test)
    profil.title_selector = trouver_selecteur_titre(article_test)
    profil.date_selector = trouver_selecteur_date(article_test)
    
    RETOURNER profil
```

### Stockage du profil

**Nouvelle table `site_discovery_profiles`** :

```sql
CREATE TABLE site_discovery_profiles (
    id SERIAL PRIMARY KEY,
    domain TEXT UNIQUE NOT NULL,
    
    -- Détection technique
    cms_detected TEXT,                    -- 'wordpress', 'drupal', 'hubspot', 'ghost', 'custom'
    cms_version TEXT,
    has_rest_api BOOLEAN DEFAULT FALSE,
    api_endpoints JSONB,                  -- {"posts": "/wp-json/wp/v2/posts", ...}
    
    -- Sources de découverte
    sitemap_urls JSONB,                   -- ["/sitemap.xml", "/post-sitemap.xml"]
    rss_feeds JSONB,                      -- ["/feed/", "/blog/feed/"]
    blog_listing_pages JSONB,             -- ["/blog/", "/actualites/"]
    
    -- Patterns détectés
    url_patterns JSONB,                   -- {"article": "/blog/{slug}", "date": "/YYYY/MM/{slug}"}
    pagination_pattern TEXT,              -- "?page={n}" ou "/page/{n}/"
    
    -- Sélecteurs optimaux (testés et validés)
    content_selector TEXT,                -- ".entry-content"
    title_selector TEXT,                  -- "h1.entry-title"
    date_selector TEXT,                   -- "time.published"
    author_selector TEXT,
    
    -- Statistiques d'efficacité
    total_urls_discovered INT DEFAULT 0,
    total_articles_valid INT DEFAULT 0,
    success_rate FLOAT,                   -- valid / discovered
    avg_article_word_count FLOAT,
    
    -- Métadonnées
    last_profiled_at TIMESTAMP,
    last_crawled_at TIMESTAMP,
    profile_version INT DEFAULT 1,
    notes TEXT,                           -- Notes manuelles si ajustements
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index pour recherche rapide
CREATE INDEX idx_site_discovery_profiles_domain ON site_discovery_profiles(domain);
CREATE INDEX idx_site_discovery_profiles_cms ON site_discovery_profiles(cms_detected);
```

### Durée de vie du profil

| Élément | Durée de validité | Raison |
|---------|-------------------|--------|
| CMS détecté | 30 jours | Rarement changé |
| API endpoints | 30 jours | Stable |
| Sitemaps | 7 jours | Peuvent être mis à jour |
| RSS feeds | 7 jours | Peuvent changer |
| Sélecteurs CSS | 14 jours | Thème peut changer |
| Patterns URL | 30 jours | Structure stable |

---

## PHASE 1 — Découverte multi-sources améliorée

### Ordre de priorité des sources

```
1. API REST (si disponible)     → Fiabilité maximale, données structurées
2. RSS avec pagination          → Bonne fiabilité, articles récents
3. Sitemaps dédiés blog         → Exhaustif, mais peut inclure du bruit
4. Sitemap général (filtré)     → Fallback, filtrage nécessaire
5. Crawl heuristique            → Dernier recours, coûteux
```

### Stratégie 1 : APIs natives

#### WordPress REST API

```python
WORDPRESS_API_CONFIG = {
    "posts_endpoint": "/wp-json/wp/v2/posts",
    "params": {
        "per_page": 100,      # Maximum autorisé
        "orderby": "date",
        "order": "desc",
        "_fields": "id,date,modified,slug,title,excerpt,link,author,categories,tags"
    },
    "pagination": {
        "header": "X-WP-TotalPages",
        "param": "page"
    }
}
```

**Avantages** :
- Données structurées (titre, contenu, date, auteur, catégories)
- Pagination native fiable
- Pas de parsing HTML nécessaire
- Filtrage par catégorie possible

**Exemple de réponse** :
```json
{
    "id": 12345,
    "date": "2024-06-15T10:30:00",
    "modified": "2024-06-16T08:00:00",
    "slug": "mon-article-seo",
    "title": {"rendered": "Mon Article SEO"},
    "excerpt": {"rendered": "<p>Extrait de l'article...</p>"},
    "link": "https://example.com/blog/mon-article-seo/",
    "author": 1,
    "categories": [5, 12],
    "tags": [8, 15, 23]
}
```

#### Ghost Content API

```python
GHOST_API_CONFIG = {
    "posts_endpoint": "/ghost/api/content/posts/",
    "params": {
        "key": "{content_api_key}",  # Clé publique
        "limit": 100,
        "fields": "id,title,slug,html,excerpt,published_at,updated_at,url,authors,tags"
    }
}
```

#### Détection automatique d'API

```python
async def detect_api_endpoints(domain: str) -> Dict[str, Any]:
    """Détecter les APIs disponibles sur un domaine."""
    apis = {}
    
    # Test WordPress
    wp_test = await fetch(f"https://{domain}/wp-json/wp/v2/posts?per_page=1")
    if wp_test.status_code == 200:
        apis["wordpress"] = {
            "posts": "/wp-json/wp/v2/posts",
            "categories": "/wp-json/wp/v2/categories",
            "tags": "/wp-json/wp/v2/tags",
            "max_per_page": 100,
        }
    
    # Test Ghost (nécessite clé API publique)
    ghost_test = await fetch(f"https://{domain}/ghost/api/content/posts/")
    if ghost_test.status_code in [200, 401]:  # 401 = API existe mais clé requise
        apis["ghost"] = {
            "posts": "/ghost/api/content/posts/",
            "requires_key": ghost_test.status_code == 401,
        }
    
    return apis
```

### Stratégie 2 : Sitemaps intelligents

#### Emplacements de sitemap à tester

```python
SITEMAP_LOCATIONS = [
    # Standards
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
    
    # WordPress
    "/wp-sitemap.xml",
    "/wp-sitemap-posts-post-1.xml",
    "/post-sitemap.xml",
    "/sitemap-posts.xml",
    
    # Dédiés blog/news
    "/blog-sitemap.xml",
    "/news-sitemap.xml",
    "/article-sitemap.xml",
    "/sitemap-blog.xml",
    "/sitemap-news.xml",
    "/sitemap-articles.xml",
    
    # Sous-dossiers
    "/sitemaps/sitemap.xml",
    "/sitemap/sitemap.xml",
    "/sitemap/blog.xml",
    
    # Yoast SEO (WordPress)
    "/page-sitemap.xml",
    "/post-sitemap.xml",
    "/category-sitemap.xml",
]
```

#### Parsing de sitemap index

```python
async def parse_sitemap_index(sitemap_url: str) -> List[str]:
    """Parser un sitemap index pour extraire les sous-sitemaps."""
    response = await fetch(sitemap_url)
    soup = BeautifulSoup(response.text, "xml")
    
    sub_sitemaps = []
    for sitemap in soup.find_all("sitemap"):
        loc = sitemap.find("loc")
        if loc:
            sub_sitemaps.append(loc.text.strip())
    
    return sub_sitemaps
```

#### Filtrage intelligent des URLs de sitemap

```python
async def filter_sitemap_urls(urls: List[str], domain: str) -> List[Dict]:
    """Filtrer et scorer les URLs d'un sitemap."""
    filtered = []
    
    for url in urls:
        score = 0
        metadata = {"url": url, "source": "sitemap"}
        
        # Patterns positifs
        if re.search(r"/blog/|/actualites?/|/news/|/article/", url, re.I):
            score += 15
        if re.search(r"/\d{4}/\d{2}/", url):  # Pattern date
            score += 10
        if len(url.split("/")) >= 4:  # Profondeur suffisante
            score += 5
            
        # Patterns négatifs
        if re.search(r"/category/|/tag/|/author/|/page/", url, re.I):
            score -= 20
        if re.search(r"/contact|/about|/mentions-legales|/cgv", url, re.I):
            score -= 25
        if any(url.lower().endswith(ext) for ext in ['.pdf', '.jpg', '.png']):
            score -= 30
            
        metadata["initial_score"] = score
        if score >= 0:
            filtered.append(metadata)
    
    return sorted(filtered, key=lambda x: x["initial_score"], reverse=True)
```

### Stratégie 3 : RSS amélioré

#### Emplacements RSS à tester

```python
RSS_LOCATIONS = [
    # Standards
    "/feed/",
    "/rss/",
    "/feed.xml",
    "/rss.xml",
    "/atom.xml",
    "/index.xml",
    
    # Par section
    "/blog/feed/",
    "/actualites/feed/",
    "/news/feed/",
    "/articles/feed/",
    
    # Formats alternatifs
    "/feed/atom/",
    "/feed/rss/",
    "/feed/rss2/",
    
    # Wordpress
    "/comments/feed/",  # À ignorer (commentaires)
]
```

#### Pagination RSS

```python
async def parse_rss_with_pagination(feed_url: str, max_pages: int = 5) -> List[str]:
    """Parser un flux RSS avec support de pagination."""
    all_urls = set()
    
    for page in range(1, max_pages + 1):
        # Construire l'URL paginée
        if page == 1:
            current_url = feed_url
        else:
            # Essayer différents formats de pagination
            pagination_formats = [
                f"{feed_url}?paged={page}",
                f"{feed_url}?page={page}",
                f"{feed_url}page/{page}/",
            ]
            current_url = pagination_formats[0]  # Tester le premier
        
        response = await fetch(current_url)
        if response.status_code != 200:
            break
            
        soup = BeautifulSoup(response.text, "xml")
        
        # Extraire les URLs
        page_urls = []
        for item in soup.find_all("item"):
            link = item.find("link")
            if link and link.text:
                page_urls.append(link.text.strip())
        
        # Atom format
        for entry in soup.find_all("entry"):
            link = entry.find("link")
            if link:
                href = link.get("href") or link.text
                if href:
                    page_urls.append(href.strip())
        
        if not page_urls:
            break  # Plus de contenu
            
        all_urls.update(page_urls)
        
        # Vérifier s'il y a une page suivante (Atom)
        next_link = soup.find("link", rel="next")
        if not next_link and page > 1:
            break
    
    return list(all_urls)
```

### Stratégie 4 : Crawl heuristique amélioré

#### Nouveaux sélecteurs CSS

```python
ARTICLE_CONTAINER_SELECTORS = [
    # Sémantiques HTML5
    "article",
    "main article",
    "[role='article']",
    
    # Schema.org
    "[itemtype*='Article']",
    "[itemtype*='BlogPosting']",
    "[itemtype*='NewsArticle']",
    
    # Classes communes
    ".post",
    ".blog-post",
    ".article",
    ".news-item",
    ".entry",
    ".hentry",
    
    # Classes génériques
    ".card",
    ".item",
    "[class*='post']",
    "[class*='article']",
    "[class*='news']",
    "[class*='actu']",
    "[class*='blog']",
]

ARTICLE_LINK_SELECTORS = [
    # Dans containers d'articles
    "article a[href]",
    ".post a[href]",
    ".article a[href]",
    ".entry a[href]",
    
    # Titres
    "h2 a[href]",
    "h3 a[href]",
    ".post-title a",
    ".entry-title a",
    ".article-title a",
    
    # Relations
    "a[rel='bookmark']",
    
    # Patterns de lecture
    "a:contains('Lire la suite')",
    "a:contains('En savoir plus')",
    "a:contains('Read more')",
]
```

#### Détection Schema.org / JSON-LD

```python
def extract_jsonld_info(html: str) -> Dict[str, Any]:
    """Extraire les informations JSON-LD d'une page."""
    soup = BeautifulSoup(html, "html.parser")
    info = {
        "is_article": False,
        "is_listing": False,
        "article_urls": [],
        "metadata": {}
    }
    
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            
            # Gérer les tableaux
            if isinstance(data, list):
                for item in data:
                    process_jsonld_item(item, info)
            else:
                process_jsonld_item(data, info)
                
        except json.JSONDecodeError:
            continue
    
    return info

def process_jsonld_item(item: Dict, info: Dict) -> None:
    """Traiter un élément JSON-LD."""
    item_type = item.get("@type", "")
    
    # Types d'articles
    if item_type in ["Article", "BlogPosting", "NewsArticle", "TechArticle"]:
        info["is_article"] = True
        info["metadata"] = {
            "headline": item.get("headline"),
            "datePublished": item.get("datePublished"),
            "dateModified": item.get("dateModified"),
            "author": item.get("author", {}).get("name"),
            "description": item.get("description"),
        }
    
    # Pages de listing
    elif item_type in ["CollectionPage", "Blog", "WebPage"]:
        if item_type in ["CollectionPage", "Blog"]:
            info["is_listing"] = True
        
        # Extraire les articles liés
        main_entity = item.get("mainEntity", [])
        if isinstance(main_entity, list):
            for entity in main_entity:
                if entity.get("@type") in ["Article", "BlogPosting"]:
                    url = entity.get("url")
                    if url:
                        info["article_urls"].append(url)
    
    # Types à ignorer
    elif item_type in ["Product", "JobPosting", "Event", "Organization"]:
        info["is_article"] = False
```

#### Détection Open Graph

```python
def extract_opengraph_info(html: str) -> Dict[str, Any]:
    """Extraire les informations Open Graph."""
    soup = BeautifulSoup(html, "html.parser")
    
    og_data = {}
    for meta in soup.find_all("meta", property=True):
        prop = meta.get("property", "")
        content = meta.get("content", "")
        
        if prop.startswith("og:"):
            og_data[prop] = content
        elif prop.startswith("article:"):
            og_data[prop] = content
    
    return {
        "is_article": og_data.get("og:type") == "article",
        "title": og_data.get("og:title"),
        "description": og_data.get("og:description"),
        "image": og_data.get("og:image"),
        "published_time": og_data.get("article:published_time"),
        "modified_time": og_data.get("article:modified_time"),
        "author": og_data.get("article:author"),
        "section": og_data.get("article:section"),
        "tags": og_data.get("article:tag"),
    }
```

---

## PHASE 2 — Scoring de probabilité

### Principe

Au lieu d'un filtrage binaire (article / non-article), assigner un **score de confiance** à chaque URL découverte. Cela permet de :
- Prioriser les URLs les plus probables
- Ajuster dynamiquement les seuils selon le volume disponible
- Améliorer le profil avec le feedback

### Grille de scoring complète

#### Points positifs

| Critère | Points | Condition |
|---------|--------|-----------|
| **Source de découverte** | | |
| API REST (WordPress/Ghost) | +30 | Données structurées |
| Flux RSS | +25 | Source fiable |
| Sitemap dédié blog | +20 | `post-sitemap.xml`, `blog-sitemap.xml` |
| Sitemap général | +10 | `sitemap.xml` standard |
| Crawl heuristique | +5 | Découverte HTML |
| **Pattern d'URL** | | |
| Match pattern date `/YYYY/MM/` | +15 | WordPress classique |
| Match pattern date `/YYYY/MM/DD/` | +18 | Date complète |
| Match `/blog/`, `/actualites/`, `/news/` | +12 | Préfixe blog |
| Match `/article/`, `/post/` | +10 | Préfixe article |
| Slug SEO (> 3 mots avec tirets) | +8 | `mon-super-article-seo` |
| URL longue (> 60 caractères) | +5 | Probable article |
| **Métadonnées Schema.org** | | |
| JSON-LD type Article/BlogPosting | +30 | Confirmation forte |
| JSON-LD type NewsArticle | +28 | Article d'actualité |
| JSON-LD avec datePublished | +10 | Date confirmée |
| **Métadonnées Open Graph** | | |
| `og:type="article"` | +25 | Confirmation OG |
| `article:published_time` présent | +12 | Date OG |
| `article:author` présent | +8 | Auteur confirmé |
| **Structure HTML** | | |
| Balise `<article>` principale | +15 | HTML5 sémantique |
| Balise `<time datetime>` | +10 | Date structurée |
| Classe `.entry-content` ou similaire | +8 | Structure blog |
| Meta `author` présent | +5 | Auteur détecté |
| **Contenu (post-crawl)** | | |
| Word count > 500 | +15 | Article substantiel |
| Word count 300-500 | +10 | Article moyen |
| Word count 150-300 | +5 | Article court |
| Images dans le contenu | +3 | Contenu enrichi |
| Présence de sous-titres (h2, h3) | +5 | Structure éditoriale |

#### Points négatifs

| Critère | Points | Condition |
|---------|--------|-----------|
| **URL suspecte** | | |
| Contient `/category/`, `/categorie/` | -25 | Page catégorie |
| Contient `/tag/`, `/tags/` | -25 | Page tag |
| Contient `/author/`, `/auteur/` | -20 | Page auteur |
| Contient `/page/`, `?paged=` | -30 | Pagination |
| Contient `/search`, `/recherche` | -30 | Page recherche |
| Contient `/contact`, `/about`, `/a-propos` | -25 | Page statique |
| Contient `/mentions-legales`, `/cgv`, `/cgu` | -30 | Page légale |
| Contient `/inscription`, `/login`, `/register` | -30 | Page auth |
| **Extension fichier** | | |
| `.pdf`, `.doc`, `.xls` | -40 | Document téléchargeable |
| `.jpg`, `.png`, `.gif`, `.svg` | -40 | Image |
| `.zip`, `.rar` | -40 | Archive |
| **Contenu suspect** | | |
| JSON-LD type Product | -30 | Page produit |
| JSON-LD type JobPosting | -35 | Offre d'emploi |
| JSON-LD type Event | -25 | Événement |
| Patterns offre d'emploi (texte) | -30 | Détection textuelle |
| Word count < 100 | -20 | Trop court |
| Word count < 50 | -30 | Très court |
| **Structure suspecte** | | |
| Formulaire de contact dominant | -20 | Page contact |
| Galerie d'images sans texte | -15 | Portfolio |
| Liste de produits | -25 | Catalogue |

### Calcul du score

```python
def calculate_article_score(url_data: Dict) -> int:
    """Calculer le score de probabilité article."""
    score = 0
    details = {}
    
    # Source de découverte
    source_scores = {
        "api": 30,
        "rss": 25,
        "sitemap_blog": 20,
        "sitemap": 10,
        "heuristic": 5,
    }
    source = url_data.get("discovery_source", "heuristic")
    source_score = source_scores.get(source, 0)
    score += source_score
    details["source"] = source_score
    
    # Pattern d'URL
    url = url_data.get("url", "")
    url_score = calculate_url_pattern_score(url)
    score += url_score
    details["url_pattern"] = url_score
    
    # Schema.org (si disponible)
    if url_data.get("jsonld_type") in ["Article", "BlogPosting", "NewsArticle"]:
        score += 30
        details["schema"] = 30
    
    # Open Graph (si disponible)
    if url_data.get("og_type") == "article":
        score += 25
        details["opengraph"] = 25
    
    # Contenu (post-crawl)
    word_count = url_data.get("word_count", 0)
    if word_count > 500:
        score += 15
    elif word_count > 300:
        score += 10
    elif word_count > 150:
        score += 5
    elif word_count < 100:
        score -= 20
    details["word_count"] = score - sum(details.values())
    
    # Signaux négatifs
    negative_score = calculate_negative_signals(url, url_data)
    score += negative_score
    details["negative"] = negative_score
    
    return score, details
```

### Seuils de décision

| Score | Catégorie | Action |
|-------|-----------|--------|
| ≥ 60 | ✅ **Très probable** | Scraper en priorité |
| 40-59 | ✅ **Probable** | Scraper avec confiance |
| 20-39 | ⚠️ **Incertain** | Scraper si quota non atteint |
| 0-19 | ⚠️ **Peu probable** | Scraper seulement si désespéré |
| < 0 | ❌ **Improbable** | Ignorer |

### Stratégie de sélection

```python
def select_urls_to_scrape(scored_urls: List[Dict], max_articles: int) -> List[str]:
    """Sélectionner les URLs à scraper selon le score."""
    
    # Trier par score décroissant
    sorted_urls = sorted(scored_urls, key=lambda x: x["score"], reverse=True)
    
    selected = []
    
    # Prendre tous les "très probables" (score >= 60)
    for url_data in sorted_urls:
        if url_data["score"] >= 60:
            selected.append(url_data["url"])
        if len(selected) >= max_articles:
            break
    
    # Si pas assez, prendre les "probables" (score >= 40)
    if len(selected) < max_articles:
        for url_data in sorted_urls:
            if 40 <= url_data["score"] < 60:
                selected.append(url_data["url"])
            if len(selected) >= max_articles:
                break
    
    # Si toujours pas assez, prendre les "incertains" (score >= 20)
    if len(selected) < max_articles:
        for url_data in sorted_urls:
            if 20 <= url_data["score"] < 40:
                selected.append(url_data["url"])
            if len(selected) >= max_articles:
                break
    
    return selected
```

### Table de stockage des scores

```sql
CREATE TABLE url_discovery_scores (
    id SERIAL PRIMARY KEY,
    domain TEXT NOT NULL,
    url TEXT NOT NULL,
    url_hash TEXT UNIQUE NOT NULL,
    
    -- Source et scoring
    discovery_source TEXT,                -- 'api', 'rss', 'sitemap', 'sitemap_blog', 'heuristic'
    initial_score INT,                    -- Score avant crawl
    final_score INT,                      -- Score après crawl
    score_breakdown JSONB,                -- {"source": 25, "pattern": 15, "schema": 30, ...}
    
    -- Validation post-crawl
    was_scraped BOOLEAN DEFAULT FALSE,
    is_valid_article BOOLEAN,             -- Confirmé comme article
    validation_reason TEXT,               -- Raison si invalide
    
    -- Métadonnées
    discovered_at TIMESTAMP DEFAULT NOW(),
    scraped_at TIMESTAMP,
    
    -- Index
    CONSTRAINT unique_url_per_domain UNIQUE (domain, url_hash)
);

CREATE INDEX idx_url_scores_domain ON url_discovery_scores(domain);
CREATE INDEX idx_url_scores_score ON url_discovery_scores(initial_score DESC);
CREATE INDEX idx_url_scores_valid ON url_discovery_scores(is_valid_article);
```

---

## PHASE 3 — Extraction adaptative

### Principe

Utiliser le profil du site (Phase 0) pour optimiser l'extraction de contenu. Chaque site peut avoir des sélecteurs différents pour le titre, le contenu, la date, l'auteur.

### Sélecteurs de contenu par ordre de priorité

```python
CONTENT_SELECTORS_PRIORITY = [
    # Schema.org (plus fiable)
    "[itemprop='articleBody']",
    "[itemprop='text']",
    
    # WordPress themes
    "article .entry-content",
    "article .post-content",
    ".single-post .entry-content",
    ".post-template .post-content",
    
    # Classes génériques
    ".article-content",
    ".article-body",
    ".post-body",
    ".content-body",
    ".blog-content",
    ".news-content",
    
    # Structure HTML5
    "main article",
    "article main",
    "#content article",
    ".content article",
    
    # Fallback
    "article",
    ".post",
    ".article",
    "main",
    "#main-content",
    ".main-content",
]
```

### Sélecteurs de titre

```python
TITLE_SELECTORS_PRIORITY = [
    # Schema.org
    "[itemprop='headline']",
    "[itemprop='name']",
    
    # Classes spécifiques
    "h1.entry-title",
    "h1.post-title",
    "h1.article-title",
    ".entry-header h1",
    ".post-header h1",
    ".article-header h1",
    
    # Générique
    "article h1",
    "main h1",
    "#content h1",
    "h1",
]
```

### Sélecteurs de date

```python
DATE_SELECTORS_PRIORITY = [
    # Schema.org
    "[itemprop='datePublished']",
    "time[datetime]",
    
    # Classes spécifiques
    ".entry-date",
    ".post-date",
    ".article-date",
    ".published",
    ".date-published",
    ".meta-date",
    
    # WordPress
    ".posted-on time",
    ".entry-meta time",
    
    # Patterns texte (regex)
    # Seront analysés en dernier recours
]
```

### Sélecteurs d'auteur

```python
AUTHOR_SELECTORS_PRIORITY = [
    # Schema.org
    "[itemprop='author']",
    "[rel='author']",
    
    # Classes spécifiques
    ".author-name",
    ".entry-author",
    ".post-author",
    ".article-author",
    ".byline",
    ".by-author",
    
    # Liens auteur
    "a[href*='/author/']",
    "a[href*='/auteur/']",
]
```

### Algorithme d'extraction adaptative

```python
async def extract_article_adaptive(html: str, url: str, profile: Dict) -> Dict:
    """Extraire un article en utilisant le profil du site."""
    soup = BeautifulSoup(html, "html.parser")
    article = {}
    
    # 1. Essayer d'abord les données structurées
    jsonld = extract_jsonld_info(html)
    if jsonld.get("is_article"):
        article.update(jsonld.get("metadata", {}))
    
    opengraph = extract_opengraph_info(html)
    if opengraph.get("is_article"):
        # Compléter avec OG si pas dans JSON-LD
        for key in ["title", "description", "published_time", "author"]:
            if not article.get(key) and opengraph.get(key):
                article[key] = opengraph[key]
    
    # 2. Utiliser les sélecteurs du profil (s'ils existent)
    if profile.get("content_selector"):
        content = soup.select_one(profile["content_selector"])
        if content:
            article["content"] = clean_text(content.get_text())
            article["content_html"] = str(content)
    
    if profile.get("title_selector"):
        title = soup.select_one(profile["title_selector"])
        if title and not article.get("title"):
            article["title"] = clean_text(title.get_text())
    
    if profile.get("date_selector"):
        date = soup.select_one(profile["date_selector"])
        if date and not article.get("published_time"):
            article["published_time"] = extract_date(date)
    
    # 3. Fallback sur les sélecteurs génériques
    if not article.get("content"):
        for selector in CONTENT_SELECTORS_PRIORITY:
            content = soup.select_one(selector)
            if content and len(content.get_text(strip=True)) > 200:
                article["content"] = clean_text(content.get_text())
                article["content_html"] = str(content)
                article["_content_selector_used"] = selector
                break
    
    if not article.get("title"):
        for selector in TITLE_SELECTORS_PRIORITY:
            title = soup.select_one(selector)
            if title:
                article["title"] = clean_text(title.get_text())
                article["_title_selector_used"] = selector
                break
    
    if not article.get("published_time"):
        for selector in DATE_SELECTORS_PRIORITY:
            date = soup.select_one(selector)
            if date:
                parsed_date = extract_date(date)
                if parsed_date:
                    article["published_time"] = parsed_date
                    article["_date_selector_used"] = selector
                    break
    
    # 4. Calculer les métriques
    article["word_count"] = len(article.get("content", "").split())
    article["url"] = url
    
    return article
```

### Mise à jour du profil avec feedback

```python
async def update_profile_with_feedback(
    domain: str,
    extraction_results: List[Dict],
    db_session: AsyncSession
) -> None:
    """Mettre à jour le profil avec les résultats d'extraction."""
    
    # Analyser les sélecteurs les plus efficaces
    content_selectors = Counter()
    title_selectors = Counter()
    date_selectors = Counter()
    
    valid_articles = 0
    total_word_count = 0
    
    for result in extraction_results:
        if result.get("word_count", 0) >= 150:
            valid_articles += 1
            total_word_count += result["word_count"]
            
            if result.get("_content_selector_used"):
                content_selectors[result["_content_selector_used"]] += 1
            if result.get("_title_selector_used"):
                title_selectors[result["_title_selector_used"]] += 1
            if result.get("_date_selector_used"):
                date_selectors[result["_date_selector_used"]] += 1
    
    # Mettre à jour le profil
    profile_update = {
        "total_articles_valid": valid_articles,
        "success_rate": valid_articles / len(extraction_results) if extraction_results else 0,
        "avg_article_word_count": total_word_count / valid_articles if valid_articles else 0,
        "last_crawled_at": datetime.utcnow(),
    }
    
    # Sélecteurs les plus efficaces
    if content_selectors:
        profile_update["content_selector"] = content_selectors.most_common(1)[0][0]
    if title_selectors:
        profile_update["title_selector"] = title_selectors.most_common(1)[0][0]
    if date_selectors:
        profile_update["date_selector"] = date_selectors.most_common(1)[0][0]
    
    # Sauvegarder
    await update_site_discovery_profile(db_session, domain, profile_update)
```

---

## Nouvelles tables de données

### Migration SQL complète

```sql
-- =====================================================
-- TABLE: site_discovery_profiles
-- Stocke le profil de découverte pour chaque domaine
-- =====================================================
CREATE TABLE site_discovery_profiles (
    id SERIAL PRIMARY KEY,
    domain TEXT UNIQUE NOT NULL,
    
    -- Détection technique
    cms_detected TEXT,                    -- 'wordpress', 'drupal', 'hubspot', 'ghost', 'custom'
    cms_version TEXT,
    has_rest_api BOOLEAN DEFAULT FALSE,
    api_endpoints JSONB DEFAULT '{}',     -- {"posts": "/wp-json/wp/v2/posts", ...}
    
    -- Sources de découverte (ordonnées par efficacité)
    sitemap_urls JSONB DEFAULT '[]',      -- ["/sitemap.xml", "/post-sitemap.xml"]
    rss_feeds JSONB DEFAULT '[]',         -- ["/feed/", "/blog/feed/"]
    blog_listing_pages JSONB DEFAULT '[]',-- ["/blog/", "/actualites/"]
    
    -- Patterns détectés
    url_patterns JSONB DEFAULT '{}',      -- {"date": "/YYYY/MM/{slug}", "category": "/cat/{slug}"}
    article_url_regex TEXT,               -- Regex compilé pour matcher les articles
    pagination_pattern TEXT,              -- "?page={n}" ou "/page/{n}/"
    
    -- Sélecteurs CSS optimaux (testés et validés)
    content_selector TEXT,                -- ".entry-content"
    title_selector TEXT,                  -- "h1.entry-title"
    date_selector TEXT,                   -- "time.published"
    author_selector TEXT,
    image_selector TEXT,
    
    -- Statistiques d'efficacité
    total_urls_discovered INT DEFAULT 0,
    total_articles_valid INT DEFAULT 0,
    success_rate FLOAT DEFAULT 0,         -- valid / discovered
    avg_article_word_count FLOAT,
    
    -- Métadonnées
    last_profiled_at TIMESTAMP,
    last_crawled_at TIMESTAMP,
    profile_version INT DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    notes TEXT,                           -- Notes manuelles
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index
CREATE INDEX idx_sdp_domain ON site_discovery_profiles(domain);
CREATE INDEX idx_sdp_cms ON site_discovery_profiles(cms_detected);
CREATE INDEX idx_sdp_active ON site_discovery_profiles(is_active);

-- =====================================================
-- TABLE: url_discovery_scores
-- Stocke le score de chaque URL découverte
-- =====================================================
CREATE TABLE url_discovery_scores (
    id SERIAL PRIMARY KEY,
    domain TEXT NOT NULL,
    url TEXT NOT NULL,
    url_hash TEXT NOT NULL,
    
    -- Source de découverte
    discovery_source TEXT NOT NULL,       -- 'api', 'rss', 'sitemap_blog', 'sitemap', 'heuristic'
    discovered_in TEXT,                   -- URL/path où découvert (ex: "/post-sitemap.xml")
    
    -- Scoring
    initial_score INT DEFAULT 0,          -- Score avant crawl
    final_score INT,                      -- Score après validation
    score_breakdown JSONB DEFAULT '{}',   -- {"source": 25, "url_pattern": 15, ...}
    
    -- Validation
    was_scraped BOOLEAN DEFAULT FALSE,
    scrape_status TEXT,                   -- 'success', 'failed', 'timeout', 'blocked'
    is_valid_article BOOLEAN,             -- NULL = pas encore validé
    validation_reason TEXT,               -- Raison si invalide
    
    -- Métadonnées extraites (pré-crawl si dispo)
    title_hint TEXT,                      -- Titre depuis RSS/API
    date_hint TIMESTAMP,                  -- Date depuis RSS/API
    
    -- Timestamps
    discovered_at TIMESTAMP DEFAULT NOW(),
    scraped_at TIMESTAMP,
    
    -- Contraintes
    CONSTRAINT unique_url_discovery UNIQUE (domain, url_hash)
);

-- Index
CREATE INDEX idx_uds_domain ON url_discovery_scores(domain);
CREATE INDEX idx_uds_score ON url_discovery_scores(initial_score DESC);
CREATE INDEX idx_uds_source ON url_discovery_scores(discovery_source);
CREATE INDEX idx_uds_valid ON url_discovery_scores(is_valid_article);
CREATE INDEX idx_uds_scraped ON url_discovery_scores(was_scraped);

-- =====================================================
-- TABLE: discovery_logs
-- Logs détaillés des opérations de découverte
-- =====================================================
CREATE TABLE discovery_logs (
    id SERIAL PRIMARY KEY,
    domain TEXT NOT NULL,
    execution_id UUID,
    
    -- Type d'opération
    operation TEXT NOT NULL,              -- 'profile', 'discover', 'scrape', 'validate'
    phase TEXT,                           -- 'phase0', 'phase1', 'phase2', 'phase3'
    
    -- Résultats
    status TEXT NOT NULL,                 -- 'success', 'partial', 'failed'
    urls_found INT DEFAULT 0,
    urls_scraped INT DEFAULT 0,
    urls_valid INT DEFAULT 0,
    
    -- Détails
    sources_used JSONB DEFAULT '[]',      -- ["api", "rss", "sitemap"]
    errors JSONB DEFAULT '[]',            -- Erreurs rencontrées
    duration_seconds FLOAT,
    
    -- Métadonnées
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index
CREATE INDEX idx_dl_domain ON discovery_logs(domain);
CREATE INDEX idx_dl_execution ON discovery_logs(execution_id);
CREATE INDEX idx_dl_created ON discovery_logs(created_at DESC);
```

### Modèles SQLAlchemy

```python
# python_scripts/database/models_discovery.py

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float,
    DateTime, ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from datetime import datetime

from python_scripts.database.db_session import Base


class SiteDiscoveryProfile(Base):
    """Profil de découverte pour un domaine."""
    
    __tablename__ = "site_discovery_profiles"
    
    id = Column(Integer, primary_key=True)
    domain = Column(Text, unique=True, nullable=False, index=True)
    
    # Détection technique
    cms_detected = Column(Text)
    cms_version = Column(Text)
    has_rest_api = Column(Boolean, default=False)
    api_endpoints = Column(JSONB, default={})
    
    # Sources de découverte
    sitemap_urls = Column(JSONB, default=[])
    rss_feeds = Column(JSONB, default=[])
    blog_listing_pages = Column(JSONB, default=[])
    
    # Patterns
    url_patterns = Column(JSONB, default={})
    article_url_regex = Column(Text)
    pagination_pattern = Column(Text)
    
    # Sélecteurs CSS
    content_selector = Column(Text)
    title_selector = Column(Text)
    date_selector = Column(Text)
    author_selector = Column(Text)
    image_selector = Column(Text)
    
    # Statistiques
    total_urls_discovered = Column(Integer, default=0)
    total_articles_valid = Column(Integer, default=0)
    success_rate = Column(Float, default=0)
    avg_article_word_count = Column(Float)
    
    # Métadonnées
    last_profiled_at = Column(DateTime)
    last_crawled_at = Column(DateTime)
    profile_version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UrlDiscoveryScore(Base):
    """Score de découverte pour une URL."""
    
    __tablename__ = "url_discovery_scores"
    
    id = Column(Integer, primary_key=True)
    domain = Column(Text, nullable=False, index=True)
    url = Column(Text, nullable=False)
    url_hash = Column(Text, nullable=False)
    
    # Source
    discovery_source = Column(Text, nullable=False)
    discovered_in = Column(Text)
    
    # Scoring
    initial_score = Column(Integer, default=0)
    final_score = Column(Integer)
    score_breakdown = Column(JSONB, default={})
    
    # Validation
    was_scraped = Column(Boolean, default=False)
    scrape_status = Column(Text)
    is_valid_article = Column(Boolean)
    validation_reason = Column(Text)
    
    # Hints
    title_hint = Column(Text)
    date_hint = Column(DateTime)
    
    # Timestamps
    discovered_at = Column(DateTime, default=datetime.utcnow)
    scraped_at = Column(DateTime)
    
    __table_args__ = (
        UniqueConstraint('domain', 'url_hash', name='unique_url_discovery'),
        Index('idx_uds_score', 'initial_score'),
    )


class DiscoveryLog(Base):
    """Log des opérations de découverte."""
    
    __tablename__ = "discovery_logs"
    
    id = Column(Integer, primary_key=True)
    domain = Column(Text, nullable=False, index=True)
    execution_id = Column(UUID(as_uuid=True))
    
    # Type
    operation = Column(Text, nullable=False)
    phase = Column(Text)
    
    # Résultats
    status = Column(Text, nullable=False)
    urls_found = Column(Integer, default=0)
    urls_scraped = Column(Integer, default=0)
    urls_valid = Column(Integer, default=0)
    
    # Détails
    sources_used = Column(JSONB, default=[])
    errors = Column(JSONB, default=[])
    duration_seconds = Column(Float)
    
    created_at = Column(DateTime, default=datetime.utcnow)
```

---

## Workflow d'exécution amélioré

### Diagramme de flux complet

```
┌──────────────────────────────────────────────────────────────────┐
│                        ENTRÉE                                     │
│              domain à crawler + max_articles                      │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                 CHARGER PROFIL EXISTANT                          │
│         SELECT * FROM site_discovery_profiles                     │
│                  WHERE domain = {domain}                          │
└──────────────────────────────────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
            Profil existe            Profil absent
            ET < 7 jours             OU > 7 jours
                    │                       │
                    │                       ▼
                    │       ┌───────────────────────────────────┐
                    │       │         PHASE 0 : PROFILAGE       │
                    │       │  1. Détecter CMS                  │
                    │       │  2. Tester APIs (WP, Ghost...)    │
                    │       │  3. Trouver sitemaps              │
                    │       │  4. Trouver RSS feeds             │
                    │       │  5. Analyser patterns URL         │
                    │       │  6. Tester sélecteurs             │
                    │       │  7. Sauvegarder profil            │
                    │       └───────────────────────────────────┘
                    │                       │
                    └───────────┬───────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                 PHASE 1 : DÉCOUVERTE                              │
│                                                                   │
│  SI profil.has_rest_api:                                         │
│      urls += découvrir_via_api(profil.api_endpoints)             │
│                                                                   │
│  SI len(urls) < max_articles:                                     │
│      urls += découvrir_via_rss(profil.rss_feeds)                 │
│                                                                   │
│  SI len(urls) < max_articles:                                     │
│      urls += découvrir_via_sitemap(profil.sitemap_urls)          │
│                                                                   │
│  SI len(urls) < max_articles:                                     │
│      urls += découvrir_via_heuristic(profil.blog_listing_pages)  │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                 PHASE 2 : SCORING                                 │
│                                                                   │
│  POUR chaque url DANS urls:                                       │
│      score = calculer_score(url, source, profil)                 │
│      sauvegarder_dans_url_discovery_scores(url, score)           │
│                                                                   │
│  urls_triées = trier_par_score(urls)                             │
│  urls_sélectionnées = urls_triées[:max_articles]                 │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                 PHASE 3 : EXTRACTION                              │
│                                                                   │
│  POUR chaque url DANS urls_sélectionnées:                        │
│      html = crawl(url)                                           │
│      article = extraire_article(html, profil.selectors)          │
│      is_valid, reason = valider_article(article)                 │
│                                                                   │
│      SI is_valid:                                                │
│          sauvegarder_article(article)                            │
│          indexer_qdrant(article)                                 │
│      SINON:                                                      │
│          log_article_invalide(url, reason)                       │
│                                                                   │
│      mettre_à_jour_score_final(url, is_valid)                    │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                 FEEDBACK : AMÉLIORATION                           │
│                                                                   │
│  success_rate = articles_valides / articles_scrapés              │
│  sélecteurs_efficaces = analyser_sélecteurs_utilisés()           │
│                                                                   │
│  mettre_à_jour_profil(domain, {                                  │
│      success_rate,                                               │
│      sélecteurs_efficaces,                                       │
│      total_urls_discovered,                                      │
│      total_articles_valid,                                       │
│      last_crawled_at                                             │
│  })                                                              │
│                                                                   │
│  sauvegarder_discovery_log(domain, stats)                        │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                        SORTIE                                     │
│  {                                                               │
│      "articles_scraped": [...],                                  │
│      "statistics": {                                             │
│          "discovered": N,                                        │
│          "scraped": M,                                           │
│          "valid": K,                                             │
│          "success_rate": K/M                                     │
│      }                                                           │
│  }                                                               │
└──────────────────────────────────────────────────────────────────┘
```

### Gestion des erreurs

| Phase | Erreur possible | Action |
|-------|-----------------|--------|
| Phase 0 | Timeout sur homepage | Utiliser profil par défaut |
| Phase 0 | API 403/404 | Marquer `has_rest_api = false` |
| Phase 1 | Sitemap invalide | Passer à la source suivante |
| Phase 1 | RSS vide | Passer à la source suivante |
| Phase 2 | Erreur de calcul | Score par défaut = 10 |
| Phase 3 | Timeout crawl | Retry 2x puis skip |
| Phase 3 | HTML invalide | Skip et logger |
| Phase 3 | Extraction échoue | Skip et logger |

### Pseudo-code principal

```python
async def discover_and_scrape_articles(
    domain: str,
    max_articles: int = 100,
    db_session: AsyncSession,
    force_reprofile: bool = False,
) -> Dict[str, Any]:
    """Pipeline complet de découverte et scraping."""
    
    start_time = datetime.utcnow()
    stats = {
        "discovered": 0,
        "scraped": 0,
        "valid": 0,
        "sources_used": [],
    }
    
    # PHASE 0: Charger ou créer le profil
    profile = await get_site_discovery_profile(db_session, domain)
    
    should_reprofile = (
        force_reprofile
        or profile is None
        or (datetime.utcnow() - profile.last_profiled_at).days > 7
    )
    
    if should_reprofile:
        logger.info(f"Profilage du site {domain}...")
        profile = await profile_site(domain)
        await save_site_discovery_profile(db_session, profile)
    
    # PHASE 1: Découverte multi-sources
    discovered_urls = []
    
    # 1a. API REST (si disponible)
    if profile.has_rest_api:
        api_urls = await discover_via_api(domain, profile.api_endpoints, max_articles)
        for url in api_urls:
            discovered_urls.append({
                "url": url["url"],
                "source": "api",
                "title_hint": url.get("title"),
                "date_hint": url.get("date"),
            })
        stats["sources_used"].append("api")
        logger.info(f"API: {len(api_urls)} URLs découvertes")
    
    # 1b. RSS (compléter si besoin)
    if len(discovered_urls) < max_articles and profile.rss_feeds:
        remaining = max_articles - len(discovered_urls)
        rss_urls = await discover_via_rss(profile.rss_feeds, remaining)
        for url in rss_urls:
            if url not in [u["url"] for u in discovered_urls]:
                discovered_urls.append({"url": url, "source": "rss"})
        stats["sources_used"].append("rss")
        logger.info(f"RSS: {len(rss_urls)} URLs découvertes")
    
    # 1c. Sitemap (compléter si besoin)
    if len(discovered_urls) < max_articles and profile.sitemap_urls:
        remaining = max_articles - len(discovered_urls)
        sitemap_urls = await discover_via_sitemap(profile.sitemap_urls, remaining)
        for url in sitemap_urls:
            if url not in [u["url"] for u in discovered_urls]:
                discovered_urls.append({"url": url, "source": "sitemap"})
        stats["sources_used"].append("sitemap")
        logger.info(f"Sitemap: {len(sitemap_urls)} URLs découvertes")
    
    # 1d. Heuristiques (dernier recours)
    if len(discovered_urls) < max_articles:
        remaining = max_articles - len(discovered_urls)
        heuristic_urls = await discover_via_heuristics(domain, profile, remaining)
        for url in heuristic_urls:
            if url not in [u["url"] for u in discovered_urls]:
                discovered_urls.append({"url": url, "source": "heuristic"})
        stats["sources_used"].append("heuristic")
        logger.info(f"Heuristiques: {len(heuristic_urls)} URLs découvertes")
    
    stats["discovered"] = len(discovered_urls)
    
    # PHASE 2: Scoring
    scored_urls = []
    for url_data in discovered_urls:
        score, breakdown = calculate_article_score(url_data)
        scored_urls.append({
            **url_data,
            "initial_score": score,
            "score_breakdown": breakdown,
        })
        
        # Sauvegarder le score
        await save_url_discovery_score(db_session, domain, url_data["url"], score, breakdown)
    
    # Trier et sélectionner
    scored_urls.sort(key=lambda x: x["initial_score"], reverse=True)
    urls_to_scrape = scored_urls[:max_articles]
    
    logger.info(f"Scores: min={scored_urls[-1]['initial_score']}, max={scored_urls[0]['initial_score']}")
    
    # PHASE 3: Extraction
    scraped_articles = []
    
    for url_data in urls_to_scrape:
        try:
            # Crawl
            html = await crawl_page_async(url_data["url"])
            if not html.get("success"):
                await update_url_scrape_status(db_session, url_data["url"], "failed")
                continue
            
            stats["scraped"] += 1
            
            # Extraction adaptative
            article = await extract_article_adaptive(html["html"], url_data["url"], profile)
            
            # Validation
            is_valid, reason = validate_article(article)
            
            if is_valid:
                # Sauvegarder
                saved_article = await save_competitor_article(db_session, domain, article)
                
                # Indexer dans Qdrant
                await index_article_qdrant(saved_article)
                
                scraped_articles.append(saved_article)
                stats["valid"] += 1
                
                await update_url_validation(db_session, url_data["url"], True)
            else:
                await update_url_validation(db_session, url_data["url"], False, reason)
                logger.debug(f"Article invalide: {url_data['url']} - {reason}")
        
        except Exception as e:
            logger.error(f"Erreur scraping {url_data['url']}: {e}")
            await update_url_scrape_status(db_session, url_data["url"], "error", str(e))
    
    # FEEDBACK: Améliorer le profil
    stats["success_rate"] = stats["valid"] / stats["scraped"] if stats["scraped"] > 0 else 0
    
    await update_profile_with_feedback(domain, scraped_articles, db_session)
    
    # Log final
    duration = (datetime.utcnow() - start_time).total_seconds()
    await save_discovery_log(db_session, domain, stats, duration)
    
    logger.info(
        f"Scraping terminé pour {domain}: "
        f"{stats['discovered']} découverts, "
        f"{stats['scraped']} scrapés, "
        f"{stats['valid']} valides "
        f"({stats['success_rate']:.1%}) en {duration:.1f}s"
    )
    
    return {
        "domain": domain,
        "articles": scraped_articles,
        "statistics": stats,
    }
```

---

## Métriques de suivi

### KPIs principaux

| Métrique | Formule | Cible | Seuil d'alerte |
|----------|---------|-------|----------------|
| **Taux de découverte** | URLs trouvées / max_articles demandé | > 80% | < 50% |
| **Taux de validité** | Articles valides / URLs scrapées | > 75% | < 50% |
| **Précision du scoring** | Articles valides avec score ≥50 / total score ≥50 | > 85% | < 70% |
| **Couverture API** | Domaines avec API / total domaines | Tracking | N/A |
| **Temps de profilage** | Durée Phase 0 | < 30s | > 60s |
| **Temps par article** | Durée totale / articles scrapés | < 2s | > 5s |
| **Taux de réutilisation profil** | Crawls avec profil existant / total crawls | > 70% | < 50% |

### Dashboard de monitoring

#### Vue 1 : Performance globale

```
┌─────────────────────────────────────────────────────────────────┐
│                    PERFORMANCE GLOBALE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Taux de validité (7 derniers jours)                           │
│  ████████████████████████████░░░░░  78%                        │
│                                                                 │
│  Répartition des sources                                       │
│  API     ████████████████         45%                          │
│  RSS     ████████                 22%                          │
│  Sitemap ██████                   18%                          │
│  Heurist █████                    15%                          │
│                                                                 │
│  Temps moyen par domaine: 45s                                  │
│  Articles/jour: 2,340                                          │
└─────────────────────────────────────────────────────────────────┘
```

#### Vue 2 : Performance par domaine

```
┌─────────────────────────────────────────────────────────────────┐
│                    PAR DOMAINE                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Domaine             CMS        Validité   Articles   Dernière │
│  ─────────────────────────────────────────────────────────────  │
│  example.com         WordPress  92%        156        2h       │
│  concurrent.fr       Custom     67%        89         5h       │
│  blog.tech           Ghost      88%        234        1h       │
│  actualites.io       Drupal     71%        67         12h      │
│                                                                 │
│  ⚠️ Alerte: concurrent.fr - taux de validité < 70%             │
└─────────────────────────────────────────────────────────────────┘
```

#### Vue 3 : Analyse des échecs

```
┌─────────────────────────────────────────────────────────────────┐
│                    ANALYSE DES ÉCHECS                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Raisons d'invalidation (dernières 24h)                        │
│                                                                 │
│  Contenu trop court       ████████████████  42%                │
│  Page catégorie           ████████          21%                │
│  Offre d'emploi           ██████            15%                │
│  Page produit             ████              11%                │
│  Timeout/Erreur           ███               8%                 │
│  Autre                    █                 3%                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Annexes

### A. Liste complète des patterns d'URL

```python
# Patterns positifs (articles)
ARTICLE_URL_PATTERNS = [
    # Français
    r"/blog/",
    r"/actualites?/",
    r"/actu/",
    r"/news/",
    r"/articles?/",
    r"/posts?/",
    r"/communiques?/",
    r"/presse/",
    r"/publications?/",
    r"/ressources/",
    r"/conseils/",
    r"/guides?/",
    r"/tutoriels?/",
    r"/insights?/",
    r"/etudes?/",
    r"/cas-clients?/",
    r"/temoignages?/",
    r"/webinaires?/",
    
    # Dates WordPress
    r"/\d{4}/\d{2}/\d{2}/",  # /2024/06/15/
    r"/\d{4}/\d{2}/",        # /2024/06/
]

# Patterns négatifs (non-articles)
EXCLUDE_URL_PATTERNS = [
    # Navigation
    r"/category/",
    r"/categorie/",
    r"/tag/",
    r"/author/",
    r"/auteur/",
    r"/page/\d+",
    r"\?paged?=\d+",
    
    # Pages statiques
    r"/contact",
    r"/about",
    r"/a-propos",
    r"/mentions-legales",
    r"/cgv",
    r"/cgu",
    r"/politique-confidentialite",
    r"/privacy",
    
    # Auth/compte
    r"/login",
    r"/register",
    r"/inscription",
    r"/connexion",
    r"/mon-compte",
    r"/account",
    
    # E-commerce
    r"/panier",
    r"/cart",
    r"/checkout",
    r"/produit/",
    r"/product/",
    r"/shop/",
    r"/boutique/",
    
    # Recherche
    r"/search",
    r"/recherche",
    r"\?s=",
]
```

### B. Mapping CMS → Configuration

```python
CMS_CONFIGURATIONS = {
    "wordpress": {
        "api_test_url": "/wp-json/wp/v2/posts?per_page=1",
        "posts_endpoint": "/wp-json/wp/v2/posts",
        "max_per_page": 100,
        "default_selectors": {
            "content": ".entry-content",
            "title": "h1.entry-title",
            "date": "time.entry-date",
            "author": ".author-name",
        },
        "sitemap_patterns": [
            "/wp-sitemap.xml",
            "/wp-sitemap-posts-post-1.xml",
            "/post-sitemap.xml",
        ],
    },
    "ghost": {
        "api_test_url": "/ghost/api/content/posts/",
        "requires_api_key": True,
        "default_selectors": {
            "content": ".post-content",
            "title": "h1.post-title",
            "date": "time.post-date",
            "author": ".author-name",
        },
    },
    "drupal": {
        "default_selectors": {
            "content": ".node-content",
            "title": "h1.page-title",
            "date": ".submitted",
            "author": ".username",
        },
        "sitemap_patterns": ["/sitemap.xml"],
    },
    "hubspot": {
        "default_selectors": {
            "content": ".blog-post__body",
            "title": "h1.blog-post__title",
            "date": ".blog-post__timestamp",
            "author": ".blog-post__author",
        },
    },
    "custom": {
        "default_selectors": {
            "content": "article, .post, .article, main",
            "title": "h1",
            "date": "time[datetime], .date, .published",
            "author": ".author, .byline",
        },
    },
}
```

### C. Exemples de JSON-LD Article

```json
{
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "Mon super article SEO",
    "description": "Description de l'article pour les moteurs de recherche",
    "image": "https://example.com/image.jpg",
    "datePublished": "2024-06-15T10:30:00+02:00",
    "dateModified": "2024-06-16T08:00:00+02:00",
    "author": {
        "@type": "Person",
        "name": "Jean Dupont",
        "url": "https://example.com/author/jean-dupont"
    },
    "publisher": {
        "@type": "Organization",
        "name": "Example Company",
        "logo": {
            "@type": "ImageObject",
            "url": "https://example.com/logo.png"
        }
    },
    "mainEntityOfPage": {
        "@type": "WebPage",
        "@id": "https://example.com/blog/mon-super-article-seo"
    },
    "articleSection": "Technologie",
    "keywords": ["SEO", "article", "blog"]
}
```

### D. Checklist d'implémentation

- [ ] **Phase 0**
  - [ ] Créer `SiteProfiler` class
  - [ ] Implémenter détection CMS
  - [ ] Implémenter détection API
  - [ ] Implémenter analyse patterns URL
  - [ ] Créer table `site_discovery_profiles`
  - [ ] Tests unitaires

- [ ] **Phase 1**
  - [ ] Refactorer `discover_article_urls()`
  - [ ] Ajouter `discover_via_api()`
  - [ ] Améliorer `discover_via_rss()` (pagination)
  - [ ] Améliorer `discover_via_sitemap()` (filtering)
  - [ ] Améliorer `discover_via_heuristics()` (sélecteurs)
  - [ ] Tests unitaires

- [ ] **Phase 2**
  - [ ] Créer `ArticleScorer` class
  - [ ] Implémenter grille de scoring
  - [ ] Créer table `url_discovery_scores`
  - [ ] Tests unitaires

- [ ] **Phase 3**
  - [ ] Créer `AdaptiveExtractor` class
  - [ ] Implémenter extraction JSON-LD
  - [ ] Implémenter extraction Open Graph
  - [ ] Implémenter sélecteurs adaptatifs
  - [ ] Tests unitaires

- [ ] **Feedback loop**
  - [ ] Implémenter mise à jour du profil
  - [ ] Créer table `discovery_logs`
  - [ ] Dashboard de monitoring

---

## Historique des versions

| Version | Date | Changements |
|---------|------|-------------|
| 1.0 | Dec 2024 | Version initiale |
| 2.0 | Dec 2024 | Architecture 4 phases, scoring, profiling |

---

*Document généré pour le projet Agent Éditorial & Concurrentiel*
