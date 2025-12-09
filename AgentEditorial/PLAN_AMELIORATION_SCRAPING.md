# Plan d'amélioration du scraping d'articles

## Date : 2025-12-02
## Objectif : Améliorer le taux de récupération d'articles (actuellement 0%)

---

## 📋 Vue d'ensemble

Ce plan propose des améliorations progressives pour résoudre les problèmes identifiés dans `ANALYSIS_SCRAPING_ISSUES.md`. Les modifications sont organisées par priorité et impact estimé.

**Impact attendu :** Passage de 0% à 60-80% d'articles récupérés

---

## 🎯 Phase 1 : Corrections critiques (Priorité 1)

### Tâche 1.1 : Élargir les patterns de découverte d'articles

**Fichier :** `python_scripts/agents/agent_scraping.py`

**Modifications :**
- [ ] Créer une constante `ARTICLE_URL_PATTERNS` avec tous les patterns français
- [ ] Ajouter les patterns manquants identifiés dans l'analyse
- [ ] Ajouter des patterns génériques (dates WordPress, slugs SEO)

**Patterns à ajouter :**
```python
ARTICLE_URL_PATTERNS = [
    # Patterns existants
    r"/blog/",
    r"/article/",
    r"/actualites/",
    r"/news/",
    r"/posts/",
    r"/post/",
    
    # Nouveaux patterns français
    r"/actualite/",           # Singulier
    r"/actu/",
    r"/articles/",            # Pluriel
    r"/communiques?/",        # Communiqué(s)
    r"/presse/",
    r"/notre-actu/",
    r"/media/",
    r"/publications?/",        # Publication(s)
    r"/ressources/",
    r"/conseils/",
    r"/guides/",
    r"/tutoriels/",
    r"/veille/",
    r"/insights/",
    r"/etudes/",
    r"/cas-client/",
    r"/cas-clients/",
    r"/temoignage/",
    r"/temoignages/",
    r"/whitepaper/",
    r"/livre-blanc/",
    r"/webinaire/",
    r"/webinaires/",
    
    # Patterns génériques
    r"/\d{4}/\d{2}/",         # WordPress date pattern (YYYY/MM/)
    r"/\d{4}/\d{2}/\d{2}/",   # WordPress date pattern (YYYY/MM/DD/)
    r"/[-a-z0-9]+/",          # Slug SEO (format: /mon-article-seo/)
]
```

**Emplacement :**
- Ligne 75-83 : `discover_article_urls()` - Strategy 1 (Sitemap)
- Ligne 253-259 : `_discover_via_heuristics()` - Strategy 3

**Estimation :** 30 minutes

---

### Tâche 1.2 : Ajouter un fallback intelligent pour le sitemap

**Fichier :** `python_scripts/agents/agent_scraping.py`

**Problème :** Si aucun pattern ne correspond, on retourne une liste vide.

**Solution :**
- [ ] Si aucun article trouvé via patterns, prendre les N premières URLs du sitemap
- [ ] Filtrer les URLs exclues (extensions, catégories)
- [ ] Limiter à `max_articles` même en fallback

**Modifications :**
```python
# Après la boucle de filtrage par patterns (ligne 85-93)
if sitemap_count == 0 and len(sitemap_urls) > 0:
    # Fallback : prendre les premières URLs du sitemap
    self.logger.info(
        "No articles found via patterns, using fallback",
        domain=domain,
        sitemap_urls_available=len(sitemap_urls),
    )
    
    # Exclure les extensions et catégories
    excluded_extensions = ['.pdf', '.jpg', '.png', '.css', '.js', '.xml']
    excluded_patterns = [r'/category/', r'/tag/', r'/page/\d+']
    
    for url in sitemap_urls:
        if len(article_urls) >= max_articles:
            break
        
        # Vérifier extensions
        if any(url.lower().endswith(ext) for ext in excluded_extensions):
            continue
        
        # Vérifier catégories/pagination
        if any(re.search(pattern, url, re.IGNORECASE) for pattern in excluded_patterns):
            continue
        
        article_urls.append(url)
        sitemap_count += 1
```

**Estimation :** 45 minutes

---

### Tâche 1.3 : Améliorer la détection de pages de catégories

**Fichier :** `python_scripts/agents/agent_scraping.py`

**Problème :** Les pages de catégories sont traitées comme des articles.

**Solution :**
- [ ] Créer une méthode `is_category_page(url: str) -> bool`
- [ ] Exclure les pages de catégories/pagination des résultats
- [ ] Utiliser cette méthode dans le filtrage

**Nouvelle méthode :**
```python
def _is_category_page(self, url: str) -> bool:
    """
    Détecte les pages de catégorie, tag ou pagination.
    
    Args:
        url: URL à vérifier
        
    Returns:
        True si c'est une page de catégorie/pagination
    """
    url_lower = url.lower()
    category_patterns = [
        r'/(category|tag|news|actualites?|blog)(/|$)',
        r'/page/\d+/?$',
        r'/\?paged=\d+',
        r'/\?page=\d+',
    ]
    return any(re.search(pattern, url_lower) for pattern in category_patterns)
```

**Utilisation :**
- Dans `discover_article_urls()` : exclure les catégories du sitemap
- Dans `_discover_via_heuristics()` : exclure les catégories des liens

**Estimation :** 30 minutes

---

## 🎯 Phase 2 : Améliorations moyennes (Priorité 2)

### Tâche 2.1 : Assouplir le filtrage par nombre de mots

**Fichier :** `python_scripts/agents/agent_scraping.py`

**Modifications :**
- [ ] Réduire `min_word_count` de 250 à 150 mots
- [ ] Rendre cette valeur configurable via `__init__()`

**Changement :**
```python
def __init__(self, min_word_count: int = 150) -> None:
    """Initialize the scraping agent."""
    super().__init__("scraping")
    self.min_word_count = min_word_count  # Au lieu de 250
    self.max_age_days = 730  # 2 years
```

**Estimation :** 15 minutes

---

### Tâche 2.2 : Améliorer les heuristics avec navigation récursive

**Fichier :** `python_scripts/agents/agent_scraping.py`

**Problème :** Les heuristics ne cherchent que sur la homepage.

**Solution :**
- [ ] Implémenter une navigation récursive vers les pages de blog
- [ ] Suivre les liens "Voir tous les articles", "Archives", etc.
- [ ] Limiter la profondeur de navigation (max_depth = 2-3)

**Nouvelle méthode :**
```python
async def _discover_via_heuristics(
    self,
    domain: str,
    max_urls: int,
    max_depth: int = 2,
) -> List[str]:
    """
    Discover article URLs via heuristics with recursive navigation.
    
    Args:
        domain: Domain name
        max_urls: Maximum URLs to discover
        max_depth: Maximum navigation depth
        
    Returns:
        List of article URLs
    """
    base_url = f"https://{domain}"
    article_urls = set()
    visited = set()
    
    # Pages de blog communes à explorer
    blog_candidates = [
        f"{base_url}/blog/",
        f"{base_url}/actualites/",
        f"{base_url}/news/",
        f"{base_url}/articles/",
        f"{base_url}/ressources/",
    ]
    
    async def crawl_page(url: str, depth: int = 0):
        if depth > max_depth or url in visited or len(article_urls) >= max_urls:
            return
        
        visited.add(url)
        
        try:
            result = await crawl_page_async(url)
            if not result.get("success"):
                return
            
            html = result.get("html", "")
            soup = BeautifulSoup(html, "html.parser")
            
            # 1. Détecter les articles via balises <article>
            for article_tag in soup.find_all("article"):
                link = article_tag.find("a", href=True)
                if link:
                    href = link.get("href")
                    absolute_url = urljoin(base_url, href)
                    if self._is_article_url(absolute_url) and not self._is_category_page(absolute_url):
                        article_urls.add(absolute_url)
            
            # 2. Détecter les liens d'articles
            for link in soup.find_all("a", href=True):
                if len(article_urls) >= max_urls:
                    break
                
                href = link.get("href")
                if not href:
                    continue
                
                absolute_url = urljoin(base_url, href)
                
                # Si c'est un article, l'ajouter
                if self._is_article_url(absolute_url) and not self._is_category_page(absolute_url):
                    article_urls.add(absolute_url)
                # Si c'est une page de catégorie, l'explorer récursivement
                elif self._is_category_page(absolute_url) and absolute_url not in visited:
                    await crawl_page(absolute_url, depth + 1)
        
        except Exception as e:
            self.logger.debug("Heuristic crawl failed", url=url, error=str(e))
    
    # Explorer les pages candidates
    for candidate_url in blog_candidates:
        if len(article_urls) >= max_urls:
            break
        await crawl_page(candidate_url)
    
    return list(article_urls)[:max_urls]
```

**Estimation :** 1h30

---

### Tâche 2.3 : Améliorer la découverte RSS avec pagination

**Fichier :** `python_scripts/agents/agent_scraping.py`

**Problème :** Les RSS feeds ne sont pas paginés.

**Solution :**
- [ ] Détecter et suivre les pages RSS suivantes (`?paged=2`, etc.)
- [ ] Limiter à 3-5 pages maximum

**Modifications dans `_parse_rss_feed()` :**
```python
async def _parse_rss_feed(self, feed_url: str) -> List[str]:
    """
    Parse RSS feed and extract article URLs (with pagination support).
    
    Args:
        feed_url: RSS feed URL
        
    Returns:
        List of article URLs
    """
    all_urls = set()
    max_pages = 3  # Limiter à 3 pages
    
    for page in range(1, max_pages + 1):
        if page > 1:
            # Essayer différentes formes de pagination
            paged_urls = [
                f"{feed_url}?paged={page}",
                f"{feed_url}?page={page}",
                f"{feed_url}/page/{page}/",
            ]
        else:
            paged_urls = [feed_url]
        
        found_urls = False
        for paged_url in paged_urls:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(paged_url)
                    if response.status_code != 200:
                        continue
                    
                    soup = BeautifulSoup(response.text, "xml")
                    page_urls = []
                    
                    # RSS format
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
                    
                    if page_urls:
                        all_urls.update(page_urls)
                        found_urls = True
                        self.logger.debug(
                            "RSS page parsed",
                            feed_url=paged_url,
                            urls_found=len(page_urls),
                        )
                        break  # Succès, passer à la page suivante
            
            except Exception as e:
                self.logger.debug("Failed to parse RSS page", feed_url=paged_url, error=str(e))
                continue
        
        # Si aucune URL trouvée sur cette page, arrêter
        if not found_urls:
            break
    
    return list(all_urls)
```

**Estimation :** 45 minutes

---

## 🎯 Phase 3 : Améliorations avancées (Priorité 3)

### Tâche 3.1 : Ajouter un détecteur d'articles basé sur le contenu HTML

**Fichier :** Nouveau fichier `python_scripts/ingestion/article_detector.py` (optionnel)

**Description :** Créer un détecteur qui analyse le contenu HTML pour déterminer si une page est un article.

**Fonctionnalités :**
- [ ] Détecter la présence de balises `<article>`
- [ ] Analyser la structure HTML (classes communes : `post`, `entry`, `article-content`)
- [ ] Calculer un score de confiance basé sur :
  - Présence de titre (h1)
  - Longueur du contenu
  - Présence de date de publication
  - Ratio texte/HTML

**Utilisation :**
- Utiliser ce détecteur en fallback si les patterns ne trouvent rien
- Filtrer les URLs candidates avant de les scraper

**Estimation :** 2h (optionnel, peut être fait plus tard)

---

### Tâche 3.2 : Améliorer la gestion des extensions exclues

**Fichier :** `python_scripts/agents/agent_scraping.py`

**Modifications :**
- [ ] Créer une constante `EXCLUDED_EXTENSIONS`
- [ ] Filtrer les URLs avec ces extensions dans toutes les stratégies

**Code :**
```python
EXCLUDED_EXTENSIONS = [
    '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.svg',
    '.css', '.js', '.xml', '.zip', '.doc', '.docx',
    '.xls', '.xlsx', '.ppt', '.pptx', '.mp4', '.mp3',
]
```

**Estimation :** 20 minutes

---

### Tâche 3.3 : Rendre le filtrage par âge configurable

**Fichier :** `python_scripts/agents/agent_scraping.py`

**Modifications :**
- [ ] Ajouter un paramètre `max_age_days` dans `__init__()`
- [ ] Permettre de désactiver le filtrage par âge (None = pas de limite)

**Code :**
```python
def __init__(self, min_word_count: int = 150, max_age_days: Optional[int] = 730) -> None:
    """Initialize the scraping agent."""
    super().__init__("scraping")
    self.min_word_count = min_word_count
    self.max_age_days = max_age_days  # None = pas de limite
```

**Estimation :** 15 minutes

---

## 📊 Résumé des tâches

| Phase | Tâche | Priorité | Impact | Temps estimé |
|-------|-------|----------|--------|--------------|
| 1.1 | Élargir les patterns | 🔴 CRITIQUE | 70-80% | 30 min |
| 1.2 | Fallback sitemap | 🔴 CRITIQUE | 50-60% | 45 min |
| 1.3 | Détection catégories | 🔴 CRITIQUE | 20-30% | 30 min |
| 2.1 | Assouplir word count | 🟡 MOYEN | 20-30% | 15 min |
| 2.2 | Heuristics récursives | 🟡 MOYEN | 15-25% | 1h30 |
| 2.3 | RSS pagination | 🟡 MOYEN | 10-15% | 45 min |
| 3.1 | Détecteur HTML | 🟢 FAIBLE | 5-10% | 2h (opt) |
| 3.2 | Extensions exclues | 🟢 FAIBLE | 5% | 20 min |
| 3.3 | Âge configurable | 🟢 FAIBLE | 5-10% | 15 min |

**Temps total Phase 1 :** ~1h45  
**Temps total Phase 2 :** ~2h30  
**Temps total Phase 3 :** ~2h35 (optionnel)

---

## 🚀 Ordre d'exécution recommandé

1. **Phase 1 complète** (Tâches 1.1, 1.2, 1.3) - Impact immédiat
2. **Tâche 2.1** - Quick win (15 min)
3. **Tâche 2.3** - Amélioration RSS (45 min)
4. **Tâche 2.2** - Heuristics récursives (1h30)
5. **Phase 3** - Si nécessaire après tests

---

## ✅ Critères de succès

Après implémentation, on devrait observer :
- ✅ `total_articles_discovered > 0` pour la majorité des domaines
- ✅ `total_articles_saved > 0` dans les logs
- ✅ Réduction significative de `domains_without_articles`
- ✅ Statistiques détaillées montrant où les articles sont trouvés (sitemap/RSS/heuristics)

---

## 📝 Notes d'implémentation

1. **Tests après chaque phase :** Tester avec un petit échantillon de domaines avant de passer à la phase suivante
2. **Logging :** Conserver les logs détaillés pour diagnostiquer les problèmes restants
3. **Performance :** Surveiller les temps d'exécution, surtout avec les heuristics récursives
4. **Compatibilité :** S'assurer que les modifications restent compatibles avec l'API existante

---

## 🔄 Itérations futures possibles

- Cache des URLs découvertes pour éviter de re-scraper
- Détection automatique de nouveaux patterns basée sur l'apprentissage
- Support de sitemaps index (sitemap_index.xml)
- Amélioration de l'extraction de contenu avec des sélecteurs CSS personnalisés

