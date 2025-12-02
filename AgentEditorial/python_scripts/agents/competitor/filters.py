"""Filters for competitor search results."""

import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from python_scripts.agents.competitor.config import CompetitorSearchConfig
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


class PreFilter:
    """Pre-filter to exclude unwanted domains and URLs."""

    def __init__(self, config: CompetitorSearchConfig) -> None:
        """Initialize pre-filter."""
        self.config = config
        self.excluded_count = 0
        
        # Patterns pour la détection de contenu
        self._init_patterns()

    def _init_patterns(self) -> None:
        """Initialiser les patterns de détection."""
        # Patterns pour sites d'emploi/recrutement
        self.job_patterns = {
            "domain": [
                "emploi", "job", "recrutement", "carriere", "career", "recruiting",
                "talent", "interim", "staffing", "freelance-", "malt.", "comet.",
            ],
            "keywords": [
                "offre d'emploi", "offres d'emploi", "postuler", "candidature",
                "recrutement", "recrute", "recruteur", "cv", "curriculum vitae",
                "cdi", "cdd", "freelance", "interim", "mission", "poste à pourvoir",
                "nous rejoindre", "rejoignez-nous", "carrière", "career",
                "job", "jobs", "vacancies", "hiring", "postulez", "candidater",
            ],
        }

        # Patterns pour e-commerce
        self.ecommerce_patterns = {
            "domain": [
                "shop", "store", "boutique", "buy", "achat", "vente", "marketplace",
                "amazon", "cdiscount", "fnac", "darty", "leboncoin", "ebay",
            ],
            "keywords": [
                "achat en ligne", "acheter", "commander", "commande", "panier",
                "livraison", "livré", "paiement", "prix", "promotion", "soldes",
                "boutique en ligne", "e-commerce", "shopping", "vente en ligne",
                "marketplace", "petites annonces", "annonces gratuites",
                "ajouter au panier", "retrait magasin", "click & collect",
            ],
        }

        # Patterns pour universités/écoles
        self.university_patterns = {
            "domain": [
                "univ-", "universite", "ecole-", "école-", "ens-", "insa-",
                ".ac-", ".edu", "polytechnique", "centrale", "mines-", "telecom-",
                "epitech", "epita", "hec.", "essec", "esilv", "esme", "sciencespo",
                "ixesn", "erasmus",
            ],
            "keywords": [
                "université", "universite", "école", "ecole", "académie", "academie",
                "étudiant", "étudiants", "etudiant", "etudiants", "student",
                "campus", "faculté", "licence", "master", "doctorat", "phd",
                "formation initiale", "alternance scolaire", "parcours scolaire",
                "inscription", "rentrée universitaire", "erasmus", "student network",
                "enseignement supérieur", "grande école", "classe préparatoire",
            ],
        }

        # Patterns pour services publics/gouvernementaux
        self.public_service_patterns = {
            "domain": [
                ".gouv.", ".gov.", ".edu.", ".ac.", ".ameli.", ".caf.", ".urssaf.",
                "service-public", "servicepublic", "francetravail", "pole-emploi",
                "parcoursup", "impots.", "banque-france", ".sante.fr", ".cnrs.",
                "metropole.", "mairie-", "ville-", ".agglo-", ".ars.",
            ],
            "keywords": [
                "service public", "administration", "gouvernement", "ministère",
                "préfecture", "mairie", "commune", "département", "région",
                "assurance maladie", "ameli", "caf", "sécurité sociale",
                "pôle emploi", "france travail", "impôts", "trésor public",
                "collectivité", "agglomération", "métropole", "communauté urbaine",
                "conseil général", "conseil régional", "état français",
            ],
        }

        # Patterns pour reprise/vente d'entreprises
        self.business_sale_patterns = {
            "domain": [
                "reprise-", "cession-", "transmission-", "fusacq", "transentreprise",
                "bpifrance", "cra.asso", "franchise",
            ],
            "keywords": [
                "reprise d'entreprise", "reprise entreprise", "entreprise à vendre",
                "cession", "rachat", "transmission", "à vendre", "à céder",
                "ssii à vendre", "esn à vendre", "valorisation d'entreprise",
                "acquisition", "fusionner", "fusion acquisition", "m&a",
                "reprise activité", "vente de fonds", "fonds de commerce",
                "évaluation d'entreprise", "due diligence", "repreneur",
            ],
        }

        # Patterns pour annuaires
        self.directory_patterns = {
            "domain": [
                "annuaire", "pagesjaunes", "118", "societe.com", "infogreffe",
                "pappers", "kompass", "europages", "verif.", "manageo",
                "trustpilot", "yelp", "tripadvisor",
            ],
            "keywords": [
                "annuaire", "annuaire des", "liste des", "répertoire",
                "trouver un", "rechercher un", "comparer les",
                "classement", "top 10", "meilleur", "ranking",
                "avis clients", "note", "évaluation", "comparaison",
                "fiche entreprise", "coordonnées", "numéro siret", "numéro siren",
            ],
        }

        # Patterns pour médias/presse
        self.media_patterns = {
            "domain": [
                "news", "actu", "journal", "presse", "media", "info",
                "lemonde", "lefigaro", "lesechos", "liberation", "leparisien",
                "bfm", "tf1", "france24", "rtl", "europe1", "rmc",
                "01net", "zdnet", "silicon", "numerama", "clubic", "frandroid",
            ],
            "keywords": [
                "actualité", "actualites", "news", "journal", "presse",
                "média", "media", "information", "reportage", "article",
                "breaking news", "flash info", "dernières nouvelles",
                "édition", "rédaction", "journaliste", "interview",
            ],
        }

        # Patterns pour plateformes de listing/classement
        self.listing_platform_patterns = {
            "domain": [
                "sortlist", "clutch", "goodfirms", "designrush", "awwwards",
                "dribbble", "behance", "capterra", "appvizer", "g2.",
                "trustradius", "getapp",
            ],
            "keywords": [
                "top agences", "meilleures agences", "classement agences",
                "sélection agences", "trouver une agence", "choisir une agence",
                "comparer agences", "avis agences", "rating",
                "portfolio agencies", "agency directory", "agency ranking",
            ],
        }

        # Patterns pour outils SEO/Analytics
        self.seo_tool_patterns = {
            "domain": [
                "semrush", "ahrefs", "moz.", "majestic", "similarweb", "alexa",
                "seobserver", "ubersuggest", "spyfu", "serpstat", "sistrix",
                "woorank", "sitechecker", "gtmetrix", "pagespeed",
                "builtwith", "wappalyzer", "siteprice", "worthofweb",
            ],
            "keywords": [
                "analyse seo", "audit seo", "backlinks", "domain authority",
                "traffic estimate", "keyword research", "competitor analysis tool",
                "website analysis", "site audit", "seo score",
            ],
        }

    def filter(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter results to exclude PDFs, excluded domains, tools, media, etc.

        Args:
            results: List of search results

        Returns:
            Filtered list
        """
        filtered: List[Dict[str, Any]] = []
        excluded_reasons: Dict[str, int] = {}

        for result in results:
            url = result.get("url", "")
            if not url:
                continue

            # Exclude PDFs
            if url.lower().endswith(".pdf"):
                excluded_reasons["pdf"] = excluded_reasons.get("pdf", 0) + 1
                continue

            # Extract domain
            domain = self._extract_domain(url)
            if not domain:
                excluded_reasons["invalid_domain"] = excluded_reasons.get("invalid_domain", 0) + 1
                continue

            # Check using config's exclusion method with reason
            exclusion = self.config.get_exclusion_reason(domain)
            if exclusion:
                category, reason = exclusion
                excluded_reasons[category] = excluded_reasons.get(category, 0) + 1
                continue

            # Get title and snippet for content analysis
            title = result.get("title", "").lower()
            snippet = result.get("snippet", "").lower()
            combined_text = f"{title} {snippet}"

            # Check for job site patterns
            if self._matches_patterns(domain, combined_text, self.job_patterns):
                excluded_reasons["job_site_content"] = excluded_reasons.get("job_site_content", 0) + 1
                continue

            # Check for e-commerce patterns
            if self._matches_patterns(domain, combined_text, self.ecommerce_patterns):
                excluded_reasons["ecommerce_content"] = excluded_reasons.get("ecommerce_content", 0) + 1
                continue

            # Check for university patterns
            if self._matches_patterns(domain, combined_text, self.university_patterns):
                excluded_reasons["university_content"] = excluded_reasons.get("university_content", 0) + 1
                continue

            # Check for public service patterns
            if self._matches_patterns(domain, combined_text, self.public_service_patterns):
                excluded_reasons["public_service_content"] = excluded_reasons.get("public_service_content", 0) + 1
                continue

            # Check for business sale patterns
            if self._matches_patterns(domain, combined_text, self.business_sale_patterns):
                excluded_reasons["business_sale_content"] = excluded_reasons.get("business_sale_content", 0) + 1
                continue

            # Check for directory patterns
            if self._matches_patterns(domain, combined_text, self.directory_patterns):
                excluded_reasons["directory_content"] = excluded_reasons.get("directory_content", 0) + 1
                continue

            # Check for media patterns
            if self._matches_patterns(domain, combined_text, self.media_patterns):
                excluded_reasons["media_content"] = excluded_reasons.get("media_content", 0) + 1
                continue

            # Check for listing platform patterns
            if self._matches_patterns(domain, combined_text, self.listing_platform_patterns):
                excluded_reasons["listing_platform_content"] = excluded_reasons.get("listing_platform_content", 0) + 1
                continue

            # Check for SEO tool patterns
            if self._matches_patterns(domain, combined_text, self.seo_tool_patterns):
                excluded_reasons["seo_tool_content"] = excluded_reasons.get("seo_tool_content", 0) + 1
                continue

            # All checks passed
            result["domain"] = domain
            filtered.append(result)

        self.excluded_count = len(results) - len(filtered)
        if excluded_reasons or self.excluded_count > 0:
            logger.info(
                "Pre-filter completed",
                input_count=len(results),
                output_count=len(filtered),
                excluded_total=self.excluded_count,
                exclusion_breakdown=excluded_reasons,
                exclusion_rate=round(self.excluded_count / len(results) * 100, 1) if results else 0,
            )

        return filtered

    def _matches_patterns(
        self, domain: str, combined_text: str, patterns: Dict[str, List[str]]
    ) -> bool:
        """
        Check if domain or content matches the given patterns.
        
        For content patterns, we require STRONG matches (multiple keywords or 
        keyword + domain pattern) to avoid false positives.

        Args:
            domain: The domain to check
            combined_text: Combined title and snippet text
            patterns: Dictionary with 'domain' and 'keywords' lists

        Returns:
            True if matches patterns
        """
        domain_lower = domain.lower()
        
        # Check domain patterns
        domain_matches = sum(1 for p in patterns.get("domain", []) if p in domain_lower)
        
        # If domain strongly matches (2+ patterns), it's likely this category
        if domain_matches >= 2:
            return True
        
        # Check content keywords
        keyword_matches = sum(1 for kw in patterns.get("keywords", []) if kw in combined_text)
        
        # If domain partially matches AND content matches, it's this category
        if domain_matches >= 1 and keyword_matches >= 1:
            return True
        
        # If content STRONGLY matches (3+ keywords), it's likely this category
        if keyword_matches >= 3:
            return True
        
        return False

    def _extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path.split("/")[0]
            if domain.startswith("www."):
                domain = domain[4:]
            return domain.lower() if domain else None
        except Exception:
            return None


class DomainFilter:
    """Filter for .fr domains and deduplication."""

    def __init__(self, config: CompetitorSearchConfig) -> None:
        """Initialize domain filter."""
        self.config = config

    def filter(self, results: List[Dict[str, Any]], exclude_domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Filter to keep only .fr domains and deduplicate.

        Args:
            results: List of search results
            exclude_domain: Domain to exclude (target domain and its subdomains)

        Returns:
            Filtered and deduplicated list
        """
        seen_domains: set[str] = set()
        filtered: List[Dict[str, Any]] = []
        excluded_subdomains = 0

        for result in results:
            domain = result.get("domain", "")
            if not domain:
                continue

            # Only keep .fr domains
            if not domain.endswith(".fr"):
                continue

            domain_lower = domain.lower()
            
            # Exclude target domain and its subdomains
            if exclude_domain:
                exclude_domain_lower = exclude_domain.lower()
                # Exact match
                if domain_lower == exclude_domain_lower:
                    continue
                # Subdomain check: if domain ends with .exclude_domain, it's a subdomain
                if domain_lower.endswith(f".{exclude_domain_lower}"):
                    excluded_subdomains += 1
                    continue

            # Deduplicate
            if domain_lower not in seen_domains:
                seen_domains.add(domain_lower)
                filtered.append(result)

        excluded_non_fr = sum(1 for r in results if r.get("domain") and not r.get("domain", "").endswith(".fr"))
        excluded_target = 1 if exclude_domain and any(r.get("domain", "").lower() == exclude_domain.lower() for r in results) else 0
        logger.info(
            "Domain filter completed",
            input_count=len(results),
            output_count=len(filtered),
            unique_domains=len(seen_domains),
            excluded_non_fr=excluded_non_fr,
            excluded_target_domain=excluded_target,
            excluded_subdomains=excluded_subdomains,
            duplicates_removed=len(results) - len(filtered) - excluded_non_fr - excluded_target - excluded_subdomains,
        )
        return filtered


class ContentFilter:
    """Filter based on content analysis."""

    def __init__(self, config: CompetitorSearchConfig) -> None:
        """Initialize content filter."""
        self.config = config
        
        # Mots-clés positifs (indiquent une ESN/agence digitale)
        self.positive_keywords = {
            "esn": ["esn", "ssii", "société de services numériques", "entreprise de services numériques"],
            "agence": ["agence digitale", "agence web", "agence de communication", "agence marketing"],
            "services_it": [
                "développement", "intégration", "maintenance", "infrastructure",
                "cloud", "cybersécurité", "transformation digitale", "conseil it",
                "hébergement", "infogérance", "devops", "data", "big data", "ia", "intelligence artificielle",
            ],
            "business": [
                "services", "prestations", "offres", "solutions", "conseil",
                "expertise", "accompagnement", "partenaire", "client",
            ],
            "activity": [
                "portfolio", "réalisations", "projets", "références", "clients",
                "équipe", "contact", "devis", "qui sommes-nous", "à propos",
            ],
        }
        
        # Mots-clés négatifs (indiquent un faux positif)
        self.negative_keywords = {
            "job_site": [
                "offre d'emploi", "offres d'emploi", "postuler", "candidature",
                "recrutement", "cv", "cdi", "cdd", "nous rejoindre", "carrière",
            ],
            "ecommerce": [
                "achat en ligne", "acheter", "commander", "panier", "livraison",
                "paiement", "promotion", "soldes", "boutique en ligne", "e-commerce",
            ],
            "public_service": [
                "service public", "administration", "gouvernement", "ministère",
                "assurance maladie", "pôle emploi", "france travail", "impôts",
            ],
            "university": [
                "université", "école", "étudiant", "campus", "faculté",
                "master", "licence", "doctorat", "formation initiale",
            ],
            "business_sale": [
                "reprise d'entreprise", "entreprise à vendre", "cession",
                "transmission", "à vendre", "à céder", "rachat",
            ],
            "directory": [
                "annuaire", "liste des", "répertoire", "trouver un",
                "comparer les", "classement", "top 10", "meilleur",
            ],
            "media": [
                "actualité", "news", "journal", "presse", "média", "reportage",
            ],
        }

    def validate_business_content(self, result: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate that result has business content indicators.

        Args:
            result: Search result dictionary

        Returns:
            Tuple (is_valid, reason)
        """
        title = result.get("title", "").lower()
        snippet = result.get("snippet", "").lower()
        description = result.get("description", "").lower()
        domain = result.get("domain", "").lower()

        # Combine all text for analysis
        combined_text = f"{title} {snippet} {description}"

        # === ÉTAPE 1: Vérifier si c'est clairement un faux positif ===
        
        # Compteur de signaux négatifs
        negative_score = 0
        negative_reasons = []
        
        for category, keywords in self.negative_keywords.items():
            matches = [kw for kw in keywords if kw in combined_text]
            if matches:
                negative_score += len(matches)
                negative_reasons.append(f"{category}:{len(matches)}")
        
        # Si trop de signaux négatifs, exclure
        if negative_score >= 3:
            return False, f"Trop de signaux négatifs: {', '.join(negative_reasons)}"

        # === ÉTAPE 2: Vérification du domaine ===
        
        # Vérifier si le domaine est exclu via config
        exclusion = self.config.get_exclusion_reason(domain)
        if exclusion:
            return False, f"Domaine exclu: {exclusion[1]}"

        # === ÉTAPE 3: Vérifier les signaux positifs ===
        
        positive_score = 0
        positive_reasons = []
        
        for category, keywords in self.positive_keywords.items():
            matches = [kw for kw in keywords if kw in combined_text or kw in domain]
            if matches:
                positive_score += len(matches)
                positive_reasons.append(f"{category}:{len(matches)}")

        # Bonus pour les indicateurs ESN forts
        esn_strong_indicators = ["esn", "ssii", "services numériques", "services informatiques"]
        if any(ind in combined_text or ind in domain for ind in esn_strong_indicators):
            positive_score += 3
            positive_reasons.append("esn_strong:3")

        # Bonus si le contenu a été enrichi (site accessible)
        is_enriched = result.get("enriched", False)
        if is_enriched:
            positive_score += 1
            positive_reasons.append("enriched:1")

        # === ÉTAPE 4: Décision finale ===
        
        # Accepter si suffisamment de signaux positifs
        if positive_score >= 2:
            return True, f"Validé avec score positif: {positive_score} ({', '.join(positive_reasons)})"
        
        # Accepter si enrichi et pas de signaux négatifs forts
        if is_enriched and negative_score < 2:
            return True, "Validé: enrichi avec peu de signaux négatifs"
        
        # Accepter si ESN/SSII détecté
        is_esn = result.get("is_esn", False)
        esn_confidence = result.get("esn_confidence", 0)
        if is_esn and esn_confidence > 0.5:
            return True, f"Validé: ESN avec confidence {esn_confidence}"
        
        return False, f"Rejeté: score positif insuffisant ({positive_score}), signaux négatifs: {negative_score}"

    def filter(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter results based on content validation.

        Args:
            results: List of search results

        Returns:
            Filtered list
        """
        filtered: List[Dict[str, Any]] = []
        excluded = 0
        exclusion_reasons: Dict[str, int] = {}

        for result in results:
            is_valid, reason = self.validate_business_content(result)
            if is_valid:
                filtered.append(result)
            else:
                excluded += 1
                # Extraire la catégorie principale de la raison
                category = reason.split(":")[0] if ":" in reason else "other"
                exclusion_reasons[category] = exclusion_reasons.get(category, 0) + 1

        if excluded > 0 or len(results) != len(filtered):
            logger.info(
                "Content filter completed",
                input_count=len(results),
                output_count=len(filtered),
                excluded=excluded,
                exclusion_reasons=exclusion_reasons,
                exclusion_rate=round(excluded / len(results) * 100, 1) if results else 0,
            )

        return filtered


class MediaFilter:
    """Filter to exclude media/news sites."""

    def __init__(self, config: CompetitorSearchConfig) -> None:
        """Initialize media filter."""
        self.config = config
        
        # Patterns de détection des médias
        self.media_domain_patterns = [
            "news", "actu", "journal", "presse", "media", "info",
            "lemonde", "lefigaro", "lesechos", "liberation", "leparisien",
            "bfm", "tf1", "france24", "rtl", "europe1", "rmc",
            "01net", "zdnet", "silicon", "numerama", "clubic", "frandroid",
            "ouest-france", "sudouest", "lavoixdunord", "leprogres",
            "korben", "blogdumoderateur", "siecledigital",
        ]
        
        self.media_content_patterns = [
            "actualité", "actualites", "news", "journal", "presse",
            "média", "media", "information", "reportage", "article",
            "breaking news", "flash info", "dernières nouvelles",
            "édition", "rédaction", "journaliste", "interview",
        ]

    def is_media_site(self, result: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Check if result is from a media/news site.

        Args:
            result: Search result dictionary

        Returns:
            Tuple (is_media, reason)
        """
        domain = result.get("domain", "").lower()
        title = result.get("title", "").lower()
        snippet = result.get("snippet", "").lower()
        combined_text = f"{title} {snippet}"

        # Check excluded media domains from config
        if self.config.excluded_media:
            for media in self.config.excluded_media:
                if media in domain:
                    return True, f"Média exclu (config): {media}"

        # Check for media patterns in domain
        domain_matches = [p for p in self.media_domain_patterns if p in domain]
        if len(domain_matches) >= 2:
            return True, f"Patterns média dans domaine: {domain_matches}"

        # Check for media patterns in content
        content_matches = [p for p in self.media_content_patterns if p in combined_text]
        
        # Domain partial match + content match = media
        if len(domain_matches) >= 1 and len(content_matches) >= 2:
            return True, f"Domaine ({domain_matches}) + contenu ({content_matches[:2]})"
        
        # Strong content match = likely media
        if len(content_matches) >= 4:
            return True, f"Patterns média forts dans contenu: {content_matches[:3]}"

        return False, "Pas un média"

    def filter(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter out media/news sites.

        Args:
            results: List of search results

        Returns:
            Filtered list
        """
        filtered: List[Dict[str, Any]] = []
        excluded = 0
        exclusion_details: Dict[str, int] = {}

        for result in results:
            is_media, reason = self.is_media_site(result)
            if not is_media:
                filtered.append(result)
            else:
                excluded += 1
                # Catégoriser la raison
                category = "config" if "config" in reason else "pattern"
                exclusion_details[category] = exclusion_details.get(category, 0) + 1

        if excluded > 0 or len(results) != len(filtered):
            logger.info(
                "Media filter completed",
                input_count=len(results),
                output_count=len(filtered),
                excluded=excluded,
                exclusion_details=exclusion_details,
                exclusion_rate=round(excluded / len(results) * 100, 1) if results else 0,
            )

        return filtered


class JobSiteFilter:
    """Filter to exclude job/recruitment sites."""

    def __init__(self, config: CompetitorSearchConfig) -> None:
        """Initialize job site filter."""
        self.config = config
        
        self.job_domain_patterns = [
            "emploi", "job", "recrutement", "carriere", "career", "recruiting",
            "talent", "interim", "staffing", "freelance-", "malt.", "comet.",
            "indeed", "glassdoor", "cadremploi", "hellowork", "meteojob",
            "monster", "regionsjob", "linkedin", "welcometothejungle",
            "michaelpage", "hays", "randstad", "manpower", "adecco",
        ]
        
        self.job_content_patterns = [
            "offre d'emploi", "offres d'emploi", "postuler", "candidature",
            "recrutement", "recrute", "recruteur", "cv", "curriculum vitae",
            "cdi", "cdd", "freelance", "interim", "mission", "poste à pourvoir",
            "nous rejoindre", "rejoignez-nous", "carrière", "career",
            "job", "jobs", "vacancies", "hiring", "postulez", "candidater",
            "salaire", "rémunération", "avantages", "package salarial",
        ]

    def is_job_site(self, result: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Check if result is from a job/recruitment site.

        Args:
            result: Search result dictionary

        Returns:
            Tuple (is_job_site, reason)
        """
        domain = result.get("domain", "").lower()
        title = result.get("title", "").lower()
        snippet = result.get("snippet", "").lower()
        combined_text = f"{title} {snippet}"

        # Check excluded job sites from config
        if self.config.excluded_job_sites:
            for job_site in self.config.excluded_job_sites:
                if job_site in domain or domain == job_site:
                    return True, f"Site d'emploi exclu (config): {job_site}"

        # Check for job patterns in domain
        domain_matches = [p for p in self.job_domain_patterns if p in domain]
        if len(domain_matches) >= 2:
            return True, f"Patterns emploi dans domaine: {domain_matches}"

        # Check for job patterns in content
        content_matches = [p for p in self.job_content_patterns if p in combined_text]
        
        # Domain partial match + content match = job site
        if len(domain_matches) >= 1 and len(content_matches) >= 2:
            return True, f"Domaine ({domain_matches}) + contenu ({content_matches[:2]})"
        
        # Strong content match = likely job posting
        if len(content_matches) >= 4:
            return True, f"Patterns emploi forts dans contenu: {content_matches[:3]}"

        return False, "Pas un site d'emploi"

    def filter(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter out job/recruitment sites.

        Args:
            results: List of search results

        Returns:
            Filtered list
        """
        filtered: List[Dict[str, Any]] = []
        excluded = 0

        for result in results:
            is_job, _ = self.is_job_site(result)
            if not is_job:
                filtered.append(result)
            else:
                excluded += 1

        if excluded > 0:
            logger.info(
                "Job site filter completed",
                input_count=len(results),
                output_count=len(filtered),
                excluded=excluded,
                exclusion_rate=round(excluded / len(results) * 100, 1) if results else 0,
            )

        return filtered


class DirectoryFilter:
    """Filter to exclude directories and listing sites."""

    def __init__(self, config: CompetitorSearchConfig) -> None:
        """Initialize directory filter."""
        self.config = config
        
        self.directory_domain_patterns = [
            "annuaire", "pagesjaunes", "118", "societe.com", "infogreffe",
            "pappers", "kompass", "europages", "verif.", "manageo",
            "trustpilot", "yelp", "tripadvisor", "avis", "rating",
            "sortlist", "clutch", "goodfirms", "designrush", "capterra",
        ]
        
        self.directory_content_patterns = [
            "annuaire", "annuaire des", "liste des", "répertoire",
            "trouver un", "rechercher un", "comparer les", "comparatif",
            "classement", "top 10", "top 20", "meilleur", "ranking",
            "avis clients", "note", "évaluation", "comparaison",
            "fiche entreprise", "coordonnées", "numéro siret", "numéro siren",
            "entreprises similaires", "concurrents de", "alternatives à",
        ]

    def is_directory(self, result: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Check if result is from a directory/listing site.

        Args:
            result: Search result dictionary

        Returns:
            Tuple (is_directory, reason)
        """
        domain = result.get("domain", "").lower()
        title = result.get("title", "").lower()
        snippet = result.get("snippet", "").lower()
        combined_text = f"{title} {snippet}"

        # Check excluded directories from config
        if self.config.excluded_directories:
            for directory in self.config.excluded_directories:
                if directory in domain or domain == directory:
                    return True, f"Annuaire exclu (config): {directory}"

        # Check for directory patterns in domain
        domain_matches = [p for p in self.directory_domain_patterns if p in domain]
        if len(domain_matches) >= 1:
            return True, f"Pattern annuaire dans domaine: {domain_matches}"

        # Check for directory patterns in content
        content_matches = [p for p in self.directory_content_patterns if p in combined_text]
        
        # Strong content match with directory indicators
        if len(content_matches) >= 3:
            return True, f"Patterns annuaire forts dans contenu: {content_matches[:3]}"

        return False, "Pas un annuaire"

    def filter(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter out directory/listing sites.

        Args:
            results: List of search results

        Returns:
            Filtered list
        """
        filtered: List[Dict[str, Any]] = []
        excluded = 0

        for result in results:
            is_dir, _ = self.is_directory(result)
            if not is_dir:
                filtered.append(result)
            else:
                excluded += 1

        if excluded > 0:
            logger.info(
                "Directory filter completed",
                input_count=len(results),
                output_count=len(filtered),
                excluded=excluded,
                exclusion_rate=round(excluded / len(results) * 100, 1) if results else 0,
            )

        return filtered


class ComprehensiveFilter:
    """Comprehensive filter that combines all individual filters."""

    def __init__(self, config: CompetitorSearchConfig) -> None:
        """Initialize comprehensive filter."""
        self.config = config
        self.pre_filter = PreFilter(config)
        self.domain_filter = DomainFilter(config)
        self.content_filter = ContentFilter(config)
        self.media_filter = MediaFilter(config)
        self.job_filter = JobSiteFilter(config)
        self.directory_filter = DirectoryFilter(config)

    def filter(
        self, 
        results: List[Dict[str, Any]], 
        exclude_domain: Optional[str] = None,
        apply_content_filter: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Apply all filters in sequence.

        Args:
            results: List of search results
            exclude_domain: Domain to exclude (target domain)
            apply_content_filter: Whether to apply content validation

        Returns:
            Fully filtered list
        """
        logger.info(f"Starting comprehensive filtering with {len(results)} candidates")
        
        # Step 1: Pre-filter (PDFs, excluded domains, basic patterns)
        filtered = self.pre_filter.filter(results)
        logger.info(f"After pre-filter: {len(filtered)} candidates")
        
        # Step 2: Domain filter (.fr only, deduplication, exclude target)
        filtered = self.domain_filter.filter(filtered, exclude_domain)
        logger.info(f"After domain filter: {len(filtered)} candidates")
        
        # Step 3: Job site filter
        filtered = self.job_filter.filter(filtered)
        logger.info(f"After job site filter: {len(filtered)} candidates")
        
        # Step 4: Directory filter
        filtered = self.directory_filter.filter(filtered)
        logger.info(f"After directory filter: {len(filtered)} candidates")
        
        # Step 5: Media filter
        filtered = self.media_filter.filter(filtered)
        logger.info(f"After media filter: {len(filtered)} candidates")
        
        # Step 6: Content filter (optional, for post-enrichment validation)
        if apply_content_filter:
            filtered = self.content_filter.filter(filtered)
            logger.info(f"After content filter: {len(filtered)} candidates")
        
        logger.info(f"Comprehensive filtering complete: {len(filtered)} candidates remaining")
        return filtered
