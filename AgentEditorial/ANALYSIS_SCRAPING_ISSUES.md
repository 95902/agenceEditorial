# Analyse : Pourquoi aucun article n'est récupéré

## Date : 2025-12-02
## Problème : `total_articles_scraped: 0` avec 168 domaines

---

## 🔍 Analyse des problèmes identifiés

### 1. **Patterns de découverte d'articles TROP RESTRICTIFS**

**Problème actuel :**
Les patterns utilisés pour identifier les articles dans les sitemaps sont très limités :
```python
article_patterns = [
    r"/blog/",
    r"/article/",
    r"/actualites/",
    r"/news/",
    r"/posts/",
    r"/post/",
    r"/blog/.*/\d{4}/",  # Date pattern
]
```

**Problèmes identifiés :**
- ❌ **Patterns manquants pour sites français** :
  - `/actualite/` (singulier, très commun)
  - `/publications/`
  - `/ressources/`
  - `/conseils/`
  - `/guides/`
  - `/tutoriels/`
  - `/veille/`
  - `/insights/`
  - `/etudes/`
  - `/actu/`,
  - `/news/`,
  - `/post/`,
  - `/article/`,
  - `/articles/`,
  - `/communiques?/`,
  - `/presse/`,
  - `/notre-actu/`,
  - `/media/`,
  - `/publications?/`,
  - `/cas-client/` ou `/cas-clients/`
  - `/temoignage/` ou `/temoignages/`
  - `/whitepaper/` ou `/livre-blanc/`
  - `/webinaire/` ou `/webinaires/`

- ❌ **Pas de fallback** : Si aucune URL du sitemap ne correspond aux patterns, on prend **RIEN**
- ❌ **Patterns trop spécifiques** : Beaucoup de sites utilisent des structures différentes

**Impact estimé :** 🔴 **CRITIQUE** - Probablement 70-80% des articles manqués

---

### 2. **Filtrage par nombre de mots TROP STRICT**

**Problème actuel :**
```python
self.min_word_count = 250  # Minimum 250 mots
```

**Problèmes identifiés :**
- ❌ **250 mots est très élevé** pour des articles de blog d'entreprise
- ❌ Beaucoup d'articles pertinents font 150-250 mots
- ❌ Les articles techniques courts mais informatifs sont exclus

**Impact estimé :** 🟡 **MOYEN** - Probablement 20-30% des articles filtrés

---

### 3. **Filtrage par âge TROP STRICT**

**Problème actuel :**
```python
self.max_age_days = 730  # 2 ans maximum
```

**Problèmes identifiés :**
- ❌ **2 ans peut être trop restrictif** pour certains contenus evergreen
- ❌ Les articles de référence peuvent être plus anciens mais toujours pertinents
- ⚠️ **Note** : Ce critère est peut-être acceptable selon les besoins métier

**Impact estimé :** 🟢 **FAIBLE** - Probablement 5-10% des articles filtrés

---

### 4. **Heuristics de découverte LIMITÉES**

**Problème actuel :**
- Ne cherche que sur la **homepage**
- Patterns identiques à ceux du sitemap (donc mêmes limitations)
- Pas de navigation vers les pages de blog dédiées

**Problèmes identifiés :**
- ❌ Ne découvre pas les pages de blog si elles ne sont pas sur la homepage
- ❌ Ne suit pas les liens "Voir tous les articles" ou "Archives"
- ❌ Patterns identiques = mêmes limitations

**Impact estimé :** 🟡 **MOYEN** - Probablement 15-25% des articles manqués

---

### 5. **Pas de fallback si aucun pattern ne correspond**

**Problème actuel :**
Si le sitemap contient 1000 URLs mais qu'aucune ne correspond aux patterns, on retourne une liste vide.

**Solution possible :**
- Prendre les N premières URLs du sitemap si aucun pattern ne correspond
- Ou analyser le contenu de la page pour détecter si c'est un article

**Impact estimé :** 🔴 **CRITIQUE** - Probablement 50-60% des domaines affectés

---

### 6. **RSS feeds - Pas de validation du contenu**

**Problème actuel :**
Les URLs extraites des RSS feeds ne sont pas filtrées par pattern (contrairement au sitemap).

**Impact estimé :** 🟢 **FAIBLE** - Les RSS sont généralement déjà filtrés

---

## 📊 Estimation de l'impact global

| Problème | Impact | % Articles manqués estimé |
|----------|--------|---------------------------|
| Patterns trop restrictifs | 🔴 CRITIQUE | 70-80% |
| Pas de fallback sitemap | 🔴 CRITIQUE | 50-60% |
| Filtrage word count | 🟡 MOYEN | 20-30% |
| Heuristics limitées | 🟡 MOYEN | 15-25% |
| Filtrage age | 🟢 FAIBLE | 5-10% |

**Impact combiné estimé :** 85-95% des articles potentiels sont manqués

---

## 🎯 Recommandations de correction (par priorité)

### Priorité 1 : Élargir les patterns de découverte
- Ajouter tous les patterns français communs
- Ajouter des patterns génériques (dates, slugs, etc.)

### Priorité 2 : Ajouter un fallback intelligent
- Si aucun pattern ne correspond, prendre les N premières URLs du sitemap
- Analyser le contenu pour détecter si c'est un article

### Priorité 3 : Assouplir le filtrage
- Réduire `min_word_count` à 150 mots
- Rendre le filtrage par âge optionnel ou configurable

### Priorité 4 : Améliorer les heuristics
- Naviguer vers les pages de blog dédiées
- Suivre les liens "Archives", "Tous les articles", etc.

---

## 🔬 Hypothèses à vérifier avec les nouveaux logs

Avec les améliorations de logging ajoutées, on devrait voir :
1. **`sitemap_urls_count`** : Nombre d'URLs trouvées dans les sitemaps
2. **`from_sitemap`** : Combien correspondent aux patterns
3. **`from_rss`** : Combien viennent des RSS
4. **`from_heuristics`** : Combien viennent des heuristics
5. **`filtered_reasons`** : Pourquoi les articles sont filtrés

Ces statistiques permettront de confirmer les hypothèses ci-dessus.


exmple de code : import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import re
import asyncio
from typing import List, Dict, Set, Optional
from urllib.parse import urljoin
import xml.etree.ElementTree as ET
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from python_scripts.ingestion.article_detector import ArticleDetector, quick_detect
from python_scripts.database.db_session import get_session
from python_scripts.database.models import CrawlCache, SiteAnalysisResult
from python_scripts.ingestion.detect_sitemaps import detect_sitemaps_and_urls
from python_scripts.logger import log_info, log_warning, log_error
from sqlalchemy import desc

class ArticleURLDiscovery:
    """Découvre automatiquement les URLs d'articles sur les sites concurrents (version finale dynamique)"""

    ARTICLE_URL_PATTERNS = [
        r'/blog/',
        r'/actualites?/',
        r'/actualite/',
        r'/actu/',
        r'/news/',
        r'/post/',
        r'/article/',
        r'/articles/',
        r'/communiques?/',
        r'/presse/',
        r'/notre-actu/',
        r'/media/',
        r'/publications?/',
        r'/\d{4}/\d{2}/',  # Wordpress
        r'/[-a-z0-9]+/'    # **nouveau : format slug SEO**
    ]

    EXCLUDED_EXTENSIONS = [
        '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.svg',
        '.css', '.js', '.xml', '.zip', '.doc', '.docx'
    ]

    def __init__(self, max_urls_per_domain: int = 100, max_depth: int = 3, verify_ssl: bool = False):
        self.max_urls_per_domain = max_urls_per_domain
        self.max_depth = max_depth
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; EditorialBot/3.1; +http://example.com/bot)'
        })
        if not verify_ssl:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # 🔍 Détecteur d’articles (ton scorer)
        self.article_detector = ArticleDetector(
            min_word_count=250,
            min_score=0.35,
        )
    # -------------------------
    # 🔎 FILTRES
    # -------------------------
    def is_article_url(self, url: str) -> bool:
        url_lower = url.lower()
        if any(url_lower.endswith(ext) for ext in self.EXCLUDED_EXTENSIONS):
            return False
        if self.is_category_page(url_lower):
            return False  # ne pas confondre catégories/pagination et articles
        return any(re.search(pattern, url_lower) for pattern in self.ARTICLE_URL_PATTERNS)

    def is_category_page(self, url: str) -> bool:
        """Détecte les pages de catégorie, de tag ou de pagination"""
        return bool(re.search(
            r'/(category|tag|news|actualites?|blog)(/|$)|/page/\d+/?$',
            url.lower()
        ))

    def filter_real_articles(self, urls: List[str]) -> List[str]:
        """Filtre les URLs pour ne garder que les vraies pages d'articles (via ArticleDetector)."""
        final = []
        for url in urls:
            try:
                r = self.session.get(url, timeout=20, verify=self.verify_ssl)
                if r.status_code != 200 or 'text/html' not in r.headers.get('content-type', ''):
                    continue

                is_article, score, meta = self.article_detector.detect(r.text, url)
                if is_article:
                    final.append(url)
                    log_info(
                        f"✓ Article validé ({score:.2f}, {meta['scores']}) : {url}"
                    )
                else:
                    log_info(
                        f"⏭️ Rejeté (score={score:.2f}, words={meta['words']}) : {url}"
                    )
            except Exception as e:
                log_warning(f"Erreur ArticleDetector pour {url}: {e}")
                continue

        return final


    # -------------------------
    # 📡 FLUX RSS (multi-pages)
    # -------------------------
    def extract_rss_feeds(self, domain: str) -> List[str]:
        rss_feeds = []
        paths = [
            '/feed/', '/rss/', '/feed.xml', '/rss.xml',
            '/blog/feed/', '/category/news/feed/'
        ]
        for path in paths:
            full_url = urljoin(domain, path)
            try:
                r = self.session.get(full_url, timeout=20, verify=self.verify_ssl)
                if r.status_code == 200 and 'xml' in r.headers.get('content-type', ''):
                    rss_feeds.append(full_url)
                    log_info(f"✓ Flux RSS trouvé: {full_url}")
            except Exception:
                continue
        return list(set(rss_feeds))

    def parse_rss_feed(self, rss_url: str) -> List[str]:
        """Parse les flux RSS et suit les pages suivantes via ?paged=2"""
        all_urls = set()
        page_count = 0

        for page in range(1, 6):  # jusqu’à 5 pages RSS
            paged_url = f"{rss_url}?paged={page}" if page > 1 else rss_url
            try:
                r = self.session.get(paged_url, timeout=20, verify=self.verify_ssl)
                if r.status_code != 200:
                    break

                root = ET.fromstring(r.content)
                for item in root.findall('.//item'):
                    link = item.find('link')
                    if link is not None and link.text:
                        all_urls.add(link.text.strip())

                log_info(f"✓ {len(all_urls)} articles trouvés (RSS page {page})")

                # Si moins de 10 éléments, on arrête (fin du flux)
                if len(root.findall('.//item')) < 10:
                    break

            except Exception as e:
                log_warning(f"Erreur RSS {paged_url}: {e}")
                break

        return list(all_urls)

    # -------------------------
    # 🌐 EXPLORATION HTML
    # -------------------------
    def detect_articles_from_html(self, base_url: str, url: str, depth: int = 0, visited: Optional[Set[str]] = None) -> Set[str]:
        if visited is None:
            visited = set()
        if url in visited or depth > self.max_depth:
            return set()

        visited.add(url)
        articles = set()

        try:
            r = self.session.get(url, timeout=20, verify=self.verify_ssl)
            if r.status_code != 200:
                return set()
            soup = BeautifulSoup(r.text, 'html.parser')

            # 1️⃣ Détection par structure HTML (balises article ou classes typiques)
            for article_tag in soup.find_all(['article', 'div'], class_=re.compile(r'(post|entry|article)', re.I)):
                link = article_tag.find('a', href=True)
                if link:
                    full_url = urljoin(base_url, link['href'])
                    if full_url.startswith(base_url) and not any(full_url.endswith(ext) for ext in self.EXCLUDED_EXTENSIONS):
                        articles.add(full_url)

            # 2️⃣ Fallback — exploration classique de tous les liens <a>
            for link in soup.find_all('a', href=True):
                full_url = urljoin(base_url, link['href'])
                if not full_url.startswith(base_url):
                    continue
                if self.is_article_url(full_url):
                    articles.add(full_url)
                elif self.is_category_page(full_url) and full_url not in visited:
                    articles.update(self.detect_articles_from_html(base_url, full_url, depth + 1, visited))

        except Exception as e:
            log_warning(f"Erreur HTML {url}: {e}")

        if depth == 0:
            log_info(f"✓ {len(articles)} articles détectés via HTML sur {url}")
        return articles


    # -------------------------
    # 🗺️ SITEMAP
    # -------------------------
    async def discover_from_sitemap(self, domain: str) -> List[str]:
        urls = []
        try:
            sitemap_data = await detect_sitemaps_and_urls(domain)
            if sitemap_data and 'urls' in sitemap_data:
                for url in sitemap_data['urls']:
                    if self.is_article_url(url):
                        urls.append(url)
                log_info(f"✓ {len(urls)} articles trouvés via sitemap {domain}")
        except Exception as e:
            log_warning(f"Erreur sitemap {domain}: {e}")
        return urls

    # -------------------------
    # 🚀 DISCOVERY PRINCIPALE
    # -------------------------
    async def discover_article_urls(self, domain: str) -> List[str]:
        base_url = domain if domain.startswith("http") else f"https://{domain}"
        all_urls: Set[str] = set()

        # 1️⃣ Cache
        cached = self._check_cache(domain)
        all_urls.update(cached)

        # 2️⃣ Sitemap
        sitemap_urls = await self.discover_from_sitemap(base_url)
        all_urls.update(sitemap_urls)

        # 3️⃣ RSS (multi-pages)
        for feed in self.extract_rss_feeds(base_url):
            rss_urls = self.parse_rss_feed(feed)
            all_urls.update(rss_urls)

        # 4️⃣ HTML dynamique (catégories/pagination)
        category_candidates = [url for url in all_urls if self.is_category_page(url)]
        if not category_candidates:
            category_candidates.extend([
                f"{base_url}/blog/",
                f"{base_url}/actualites/",
                f"{base_url}/news/",
                f"{base_url}/ssii-esn-paris/category/news/",
                f"{base_url}/blog/business/",
                f"{base_url}/resources/",
                f"{base_url}/press/",
                f"{base_url}/blog/tech/",
                f"{base_url}/articles/"


            ])

        for cat_url in category_candidates:
            log_info(f"🧭 Exploration dynamique de la page de catégorie : {cat_url}")
            html_urls = self.detect_articles_from_html(base_url, cat_url)
            all_urls.update(html_urls)

        # 5️⃣ Nettoyage  brut(on retire les categories/pagination)

        candidates = [
            u for u in all_urls
            if not self.is_category_page(u)
        ]

        # 6️⃣ Filtrage final avec ArticleDetector (HTML + scoring)
        log_info(f"🧪 Vérification des articles réels via ArticleDetector ({len(candidates)} candidats)...")
        filtered = self.filter_real_articles(candidates)

        # 7️⃣ Limitation & sauvegarde
        final = filtered[:self.max_urls_per_domain]

        self._save_to_cache(domain, final)
        log_info(f"✅ {len(final)} URLs d'articles découvertes pour {domain}")
        return final

    # -------------------------
    # 💾 CACHE
    # -------------------------
    def _check_cache(self, domain: str) -> List[str]:
        with get_session() as session:
            cached = session.query(CrawlCache).filter(
                CrawlCache.domain == domain, CrawlCache.is_valid == True
            ).all()
            return [c.url for c in cached]

    def _save_to_cache(self, domain: str, urls: List[str]):
        with get_session() as session:
            for u in urls:
                if not session.query(CrawlCache).filter(CrawlCache.url == u).first():
                    entry = CrawlCache(
                        url_hash=str(hash(u)),
                        domain=domain,
                        url=u,
                        is_valid=True,
                        last_crawled=datetime.utcnow()
                    )
                    session.add(entry)
            session.commit()
            log_info(f"✓ {len(urls)} URLs sauvegardées dans crawl_cache")


def get_latest_competitor_domains(client_domain: str) -> List[str]:
    """
    Récupère les domaines concurrents du site client (dernière occurrence 'competitor').

    Args:
        client_domain: Domaine du site client (ex: 'innosys.fr')

    Returns:
        Liste unique des domaines concurrents.
    """
    with get_session() as session:
        # 🔍 on prend la dernière ligne (phase='competitor') pour ce client
        result = session.query(SiteAnalysisResult).filter(
            SiteAnalysisResult.domain == client_domain,
            SiteAnalysisResult.phase == 'competitor'
        ).order_by(desc(SiteAnalysisResult.created_at)).first()

        if not result:
            log_warning(f"Aucun enregistrement 'competitor' trouvé pour {client_domain}")
            return []

        payload = result.payload
        if not payload or not isinstance(payload, dict):
            log_warning(f"⚠️ Payload vide ou invalide pour {client_domain}")
            return []

        competitors_raw = payload.get("competitors", [])
        competitors = []

        for comp in competitors_raw:
            if isinstance(comp, dict) and 'domain' in comp:
                competitors.append(comp['domain'])
            elif isinstance(comp, str):
                competitors.append(comp)

        competitors = list(set(competitors))  # suppression doublons
        log_info(f"✓ {len(competitors)} concurrents trouvés pour {client_domain}")
        return competitors


async def discover_all_competitor_articles(client_domain: str, limit_domains: Optional[int] = None) -> Dict[str, List[str]]:
    """
    Découvre les articles de tous les concurrents du site client donné.
    """
    discovery = ArticleURLDiscovery(max_urls_per_domain=100)
    competitor_domains = get_latest_competitor_domains(client_domain)

    if not competitor_domains:
        log_warning(f"Aucun concurrent trouvé pour {client_domain}")
        return {}

    if limit_domains:
        competitor_domains = competitor_domains[:limit_domains]

    log_info(f"🚀 Découverte d'articles pour {len(competitor_domains)} concurrents de {client_domain}")

    results = {}

    # ✅ important : attendre chaque appel async
    for domain in tqdm(competitor_domains, desc=f"Analyse concurrents de {client_domain}"):
        try:
            urls = await safe_discover(discovery, domain)
            results[domain] = urls
            log_info(f"✅ {len(urls)} articles trouvés pour {domain}")
        except Exception as e:
            log_error(f"❌ Erreur pour {domain}: {e}")
            results[domain] = []

    total_articles = sum(len(urls) for urls in results.values())
    log_info(f"🎯 TOTAL: {total_articles} articles découverts pour {client_domain}")
    return results


async def safe_discover(discovery, domain):
    try:
        return await discovery.discover_article_urls(domain)
    except Exception as e:
        log_error(f"❌ Crash isolé pour {domain}: {e}")
        return []  


exemple d'extraction : """
harvest_article_content.py — Téléchargement et nettoyage des articles concurrents
Phase 2 du pipeline de scraping concurrentiel
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import re, time, html
from datetime import datetime
from python_scripts.database.crud_results import save_analysis_result
from python_scripts.database.crud_competitor_articles import save_competitor_article

REQUEST_TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (competitor-bot/1.0)"
ARTICLE_MIN_WORDS = 250


def fetch_html(url: str) -> str | None:
    """Télécharge le HTML d'une page (avec User-Agent propre)."""
    try:
        r = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT})
        if r.ok and "text/html" in r.headers.get("Content-Type", ""):
            return r.text
    except requests.RequestException:
        return None
    return None


def text_cleaner(html_text: str) -> str:
    """Nettoie le HTML et renvoie du texte lisible."""
    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    text = re.sub(r"\s+", " ", html.unescape(text))
    return text.strip()


def extract_article_metadata(url: str, html_text: str) -> dict:
    """Heuristiques pour identifier les métadonnées d’un article."""
    soup = BeautifulSoup(html_text, "html.parser")
    meta = {}

    def mget(prop):
        tag = soup.find("meta", {"property": prop}) or soup.find("meta", {"name": prop})
        return tag["content"].strip() if tag and tag.get("content") else None

    meta["url"] = url
    meta["domain"] = urlparse(url).netloc.replace("www.", "")
    meta["title"] = soup.title.string.strip() if soup.title else mget("og:title") or "Sans titre"
    meta["description"] = mget("description") or mget("og:description")
    meta["author"] = mget("article:author") or mget("author")
    meta["published_at"] = mget("article:published_time") or mget("date") or None
    meta["lead_image"] = mget("og:image")
    meta["schema_type"] = mget("og:type")
    meta["keywords"] = (mget("keywords") or "").split(",") if mget("keywords") else []
    meta["fetched_at"] = datetime.utcnow().isoformat()
    meta["content"] = text_cleaner(html_text)
    meta["word_count"] = len(meta["content"].split())
    meta["reading_time_min"] = round(meta["word_count"] / 200)  # 200 wpm

    # Vérifie si c’est bien un article
    article_tags = soup.find_all("article")
    if len(article_tags) == 0 and meta["word_count"] < ARTICLE_MIN_WORDS:
        meta["is_article"] = False
    else:
        meta["is_article"] = True

    return meta


def harvest_article(url: str) -> dict | None:
    """Télécharge et extrait les données d’un article concurrent."""
    html_text = fetch_html(url)
    if not html_text:
        print(f"⚠️ Impossible de récupérer {url}")
        return None

    meta = extract_article_metadata(url, html_text)
    if not meta["is_article"]:
        print(f"⏩ Ignoré (non article ou trop court): {url}")
        return None

    print(f"✅ Article extrait : {meta['title']} ({meta['word_count']} mots)")
    # ✅ Sauvegarde via ORM
    save_competitor_article(meta)
    return meta
