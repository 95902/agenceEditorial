"""Query generator for competitor search with multiple strategies."""

from typing import Any, Dict, List

from python_scripts.agents.competitor.config import CompetitorSearchConfig
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


class QueryGenerator:
    """Generate search queries using multiple strategies."""

    def __init__(self, config: CompetitorSearchConfig) -> None:
        """Initialize query generator."""
        self.config = config
        self.strategy_performance: Dict[str, Dict[str, int]] = {}

    def extract_keywords_from_profile(self, profile: Dict[str, Any]) -> List[str]:
        """
        Extract keywords from site profile for search queries.

        Args:
            profile: Site profile dictionary

        Returns:
            List of keywords
        """
        keywords: List[str] = []

        # Extract from activity_domains
        if profile.get("activity_domains"):
            if isinstance(profile["activity_domains"], dict):
                # Extract primary domains
                primary = profile["activity_domains"].get("primary", [])
                if isinstance(primary, list):
                    keywords.extend(primary[:8])  # Augmenté de 5 à 8
                secondary = profile["activity_domains"].get("secondary", [])
                if isinstance(secondary, list):
                    keywords.extend(secondary[:5])  # Augmenté de 3 à 5

        # Extract from keywords field
        if profile.get("keywords"):
            if isinstance(profile["keywords"], dict):
                primary_keywords = profile["keywords"].get("primary", [])
                if isinstance(primary_keywords, list):
                    keywords.extend(primary_keywords[:15])  # Augmenté de 10 à 15

        # Remove duplicates and empty strings
        keywords = list(dict.fromkeys([k.lower().strip() for k in keywords if k]))
        return keywords[:15]  # Augmenté de 10 à 15

    def generate_queries(
        self,
        domain: str,
        keywords: List[str],
    ) -> List[Dict[str, str]]:
        """
        Generate search queries using multiple strategies.

        Args:
            domain: Domain to find competitors for
            keywords: Keywords extracted from profile

        Returns:
            List of query dictionaries with strategy and query text
        """
        queries: List[Dict[str, str]] = []

        if not keywords:
            # Fallback: use ESN/SSII targeted queries
            # Extract base domain name (without .fr)
            base_domain = domain.replace(".fr", "").replace("www.", "")
            regions = ["Paris", "Ile-de-France", "Lyon", "Nantes", "Marseille", "Toulouse", "Bordeaux", "Lille"]
            
            # Strategy 1: ESN/SSII by region (16 queries) - Renforcé
            esn_terms = ["ESN", "SSII", "société services numériques", "agence digitale"]
            for term in esn_terms:
                for region in regions[:4]:  # Top 4 regions
                    queries.append({"strategy": "esn", "query": f"{term} {region} site:.fr"})
            
            # Strategy 2: ESN/SSII sectoral (12 queries) - Nouveau
            sector_terms = ["développement", "conseil IT", "intégration", "cloud", "cybersécurité", "transformation digitale"]
            for term in sector_terms:
                queries.append({"strategy": "esn", "query": f"ESN {term} site:.fr"})
                queries.append({"strategy": "esn", "query": f"SSII {term} site:.fr"})
            
            # Strategy 3: Alternatives ESN-focused (8 queries) - Amélioré
            alternatives_terms = ["ESN alternatives", "SSII concurrent", "ESN similaire", "SSII équivalent"]
            for term in alternatives_terms:
                queries.append({"strategy": "alternatives", "query": f"{term} {domain} site:.fr"})
                queries.append({"strategy": "alternatives", "query": f"{term} {base_domain} site:.fr"})
            
            # Strategy 4: Competitive terms with ESN context (8 queries)
            competitive_terms = ["prestataire ESN", "partenaire SSII", "intégrateur IT", "expert services numériques"]
            for term in competitive_terms:
                queries.append({"strategy": "competitive", "query": f"{term} {base_domain} site:.fr"})
                queries.append({"strategy": "competitive", "query": f"{term} site:.fr"})
            
            # Strategy 5: Geographic ESN (6 queries)
            for region in regions[:3]:  # Top 3 regions
                queries.append({"strategy": "geo", "query": f"ESN {region} site:.fr"})
                queries.append({"strategy": "geo", "query": f"SSII {region} site:.fr"})
            
            # Limit to max_queries
            limited_queries = queries[:self.config.max_queries]
            logger.info(
                "Queries generated (fallback mode - ESN focused)",
                total=len(queries),
                limited=len(limited_queries),
                strategies={q["strategy"] for q in limited_queries},
            )
            return limited_queries

        # Strategy 1: Direct (keywords with site:.fr) - 20 requêtes
        for keyword in keywords[:10]:
            queries.append({"strategy": "direct", "query": f"{keyword} site:.fr"})
            queries.append({"strategy": "direct", "query": f"{keyword} services site:.fr"})

        # Strategy 2: Combo (pairs of keywords) - 12 requêtes
        for i, kw1 in enumerate(keywords[:6]):  # Augmenté de 5 à 6
            for kw2 in keywords[i + 1 : i + 3]:
                queries.append({"strategy": "combo", "query": f"{kw1} {kw2} site:.fr"})

        # Strategy 3: Geographic - 10 requêtes
        regions = ["Paris", "Ile-de-France", "Lyon", "Nantes", "France", "Marseille", "Toulouse"]
        for keyword in keywords[:2]:
            for region in regions:
                queries.append({"strategy": "geo", "query": f"{keyword} {region} site:.fr"})

        # Strategy 4: Competitive terms - 12 requêtes
        competitive_terms = ["prestataire", "partenaire", "intégrateur", "expert", "spécialiste", "société"]
        for keyword in keywords[:2]:
            for term in competitive_terms:
                queries.append({"strategy": "competitive", "query": f"{term} {keyword} site:.fr"})

        # Strategy 5: ESN/Sector terms - 20 requêtes (renforcé)
        esn_terms = ["ESN", "SSII", "société services numériques", "agence digitale", "entreprise services numériques"]
        regions = ["Paris", "Ile-de-France", "Lyon", "Nantes", "Marseille", "Toulouse"]
        
        # ESN by region (12 queries)
        for term in esn_terms[:3]:  # Top 3 ESN terms
            for region in regions[:4]:  # Top 4 regions
                queries.append({"strategy": "esn", "query": f"{term} {region} site:.fr"})
        
        # ESN with keywords (8 queries)
        for keyword in keywords[:2]:
            for term in esn_terms[:4]:
                queries.append({"strategy": "esn", "query": f"{term} {keyword} site:.fr"})
        
        # Strategy 6: Sectoral ESN (12 queries) - Nouveau
        sector_terms = ["développement", "conseil IT", "intégration", "cloud", "cybersécurité", "transformation digitale"]
        for term in sector_terms:
            queries.append({"strategy": "esn", "query": f"ESN {term} site:.fr"})
            queries.append({"strategy": "esn", "query": f"SSII {term} site:.fr"})

        # Strategy 7: Alternatives ESN-focused (8 requêtes) - Amélioré
        alternatives_terms = [
            "ESN alternatives", "SSII concurrent", "ESN similaire", "SSII équivalent"
        ]
        for term in alternatives_terms:
            queries.append({"strategy": "alternatives", "query": f"{term} {domain} site:.fr"})
            queries.append({"strategy": "alternatives", "query": f"{term} {base_domain} site:.fr"})

        # Limit to max_queries
        limited_queries = queries[:self.config.max_queries]
        logger.info(
            "Queries generated",
            total=len(queries),
            limited=len(limited_queries),
            strategies={q["strategy"] for q in limited_queries},
        )
        return limited_queries

    def track_strategy_performance(
        self,
        strategy: str,
        queries_executed: int,
        results_found: int,
        valid_results: int,
    ) -> None:
        """
        Track performance metrics for a strategy.

        Args:
            strategy: Strategy name
            queries_executed: Number of queries executed
            results_found: Number of results found
            valid_results: Number of valid results after filtering
        """
        if strategy not in self.strategy_performance:
            self.strategy_performance[strategy] = {
                "queries_executed": 0,
                "results_found": 0,
                "valid_results": 0,
            }

        self.strategy_performance[strategy]["queries_executed"] += queries_executed
        self.strategy_performance[strategy]["results_found"] += results_found
        self.strategy_performance[strategy]["valid_results"] += valid_results

    def get_strategy_efficiency(self, strategy: str) -> float:
        """
        Get efficiency score for a strategy.

        Args:
            strategy: Strategy name

        Returns:
            Efficiency score (valid_results / queries_executed)
        """
        if strategy not in self.strategy_performance:
            return 0.0

        perf = self.strategy_performance[strategy]
        queries = perf.get("queries_executed", 0)
        if queries == 0:
            return 0.0

        return perf.get("valid_results", 0) / queries

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for all strategies."""
        summary = {}
        for strategy, perf in self.strategy_performance.items():
            queries = perf.get("queries_executed", 0)
            results = perf.get("results_found", 0)
            valid = perf.get("valid_results", 0)
            efficiency = self.get_strategy_efficiency(strategy)

            summary[strategy] = {
                "queries_executed": queries,
                "results_found": results,
                "valid_results": valid,
                "efficiency": round(efficiency, 3),
            }

        return summary

