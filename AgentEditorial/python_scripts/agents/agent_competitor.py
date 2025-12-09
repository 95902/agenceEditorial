"""Competitor search agent with optimized multi-source search and 12-step validation pipeline."""

import time
from typing import Any, Dict, List

import httpx
from ddgs import DDGS
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.agents.base_agent import BaseAgent
from python_scripts.agents.competitor.classifiers import (
    BusinessTypeClassifier,
    ESNClassifier,
    GeographicClassifier,
    RelevanceClassifier,
)
from python_scripts.agents.competitor.config import CompetitorSearchConfig, default_config
from python_scripts.agents.competitor.enricher import CandidateEnricher
from python_scripts.agents.competitor.filters import (
    ContentFilter,
    DomainFilter,
    MediaFilter,
    PreFilter,
)
from python_scripts.agents.competitor.query_generator import QueryGenerator
from python_scripts.agents.competitor.scorer import CompetitorScorer
from python_scripts.config.settings import settings
from python_scripts.database.crud_profiles import get_site_profile_by_domain
from python_scripts.utils.exceptions import WorkflowError
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


class CompetitorSearchAgent(BaseAgent):
    """Agent for identifying competitors via multi-source search with 12-step validation pipeline."""

    def __init__(self, config: CompetitorSearchConfig = None) -> None:
        """Initialize the competitor search agent."""
        super().__init__("competitor_search")
        self.config = config or default_config
        self.query_generator = QueryGenerator(self.config)
        self.pre_filter = PreFilter(self.config)
        self.domain_filter = DomainFilter(self.config)
        self.content_filter = ContentFilter(self.config)
        self.media_filter = MediaFilter(self.config)
        self.esn_classifier = ESNClassifier(self.config)
        self.business_classifier = BusinessTypeClassifier(self.config)
        self.relevance_classifier = RelevanceClassifier(self.config)
        self.geographic_classifier = GeographicClassifier(self.config)
        self.scorer = CompetitorScorer(self.config)
        self._tavily_available = False

    def _extract_domain_from_url(self, url: str) -> str:
        """Extract domain from URL."""
        from urllib.parse import urlparse
        
        try:
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path.split("/")[0]
            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]
            domain = domain.lower() if domain else ""
            # Filter: only .fr domains
            if domain and (domain.endswith(".fr") or domain.endswith(".fr/")):
                return domain.rstrip("/")
            return ""
        except Exception:
            return ""

    async def _test_tavily_connection(self) -> bool:
        """
        Test Tavily API connection.

        Returns:
            True if connection successful, False otherwise
        """
        # Check if API key exists
        if not settings.tavily_api_key:
            logger.error(
                "Tavily API key not found in configuration",
                hint="Set TAVILY_API_KEY in .env file",
                env_file_location="AgentEditorial/.env",
            )
            return False

        # Check if API key is not empty
        if not settings.tavily_api_key.strip():
            logger.error(
                "Tavily API key is empty",
                hint="TAVILY_API_KEY in .env file is empty or whitespace",
            )
            return False

        logger.info(
            "Testing Tavily API connection",
            api_key_prefix=settings.tavily_api_key[:10] + "..." if len(settings.tavily_api_key) > 10 else "***",
        )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Test with a simple query
                response = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": settings.tavily_api_key,
                        "query": "test",
                        "search_depth": "basic",
                        "max_results": 1,
                    },
                )
                
                if response.status_code == 200:
                    logger.info("Tavily API connection successful")
                    return True
                elif response.status_code == 401:
                    logger.error(
                        "Tavily API authentication failed",
                        status_code=response.status_code,
                        hint="Check if TAVILY_API_KEY is valid",
                    )
                    return False
                else:
                    logger.error(
                        "Tavily API connection failed",
                        status_code=response.status_code,
                        response_text=response.text[:200],
                    )
                    return False
        except httpx.TimeoutException:
            logger.error("Tavily API connection timeout")
            return False
        except Exception as e:
            logger.error(
                "Tavily API connection error",
                error=str(e),
                error_type=type(e).__name__,
            )
            return False

    async def _search_tavily(self, query: str) -> List[Dict[str, Any]]:
        """
        Search using Tavily API.

        Args:
            query: Search query

        Returns:
            List of search results
        """
        if not self._tavily_available:
            return []

        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": settings.tavily_api_key,
                        "query": query,
                        "search_depth": "basic",
                        "max_results": self.config.max_results_tavily,
                    },
                )
                duration = time.time() - start_time
                if response.status_code == 200:
                    data = response.json()
                    results = []
                    for item in data.get("results", []):
                        url = item.get("url", "")
                        # Only keep .fr domains
                        if url and (".fr" in url.lower() or url.lower().endswith(".fr/")):
                            # Extract domain from URL
                            domain = self._extract_domain_from_url(url)
                            if domain and domain.endswith(".fr"):
                                results.append(
                                    {
                                        "url": url,
                                        "domain": domain,
                                        "title": item.get("title", ""),
                                        "snippet": item.get("content", ""),
                                        "source": "tavily",
                                    }
                                )
                    logger.debug(
                        "Tavily search completed",
                        query=query[:100],
                        results=len(results),
                        total_found=len(data.get("results", [])),
                        duration_seconds=round(duration, 2),
                    )
                    return results
                else:
                    logger.warning(
                        "Tavily search failed",
                        query=query[:100],
                        status_code=response.status_code,
                        duration_seconds=round(duration, 2),
                    )
        except Exception as e:
            duration = time.time() - start_time
            logger.warning(
                "Tavily search error",
                query=query[:100],
                error=str(e),
                error_type=type(e).__name__,
                duration_seconds=round(duration, 2),
            )
        return []

    async def _search_duckduckgo(self, query: str) -> List[Dict[str, Any]]:
        """
        Search using DuckDuckGo.

        Args:
            query: Search query

        Returns:
            List of search results
        """
        start_time = time.time()
        try:
            with DDGS() as ddgs:
                results = []
                urls_without_domain = 0
                for result in ddgs.text(query, region="fr-fr", max_results=self.config.max_results_duckduckgo):
                    url = result.get("href", "")
                    # Only keep .fr domains
                    if url and (".fr" in url.lower() or url.lower().endswith(".fr/")):
                        # Extract domain from URL
                        domain = self._extract_domain_from_url(url)
                        if domain and domain.endswith(".fr"):
                            results.append(
                                {
                                    "url": url,
                                    "domain": domain,
                                    "title": result.get("title", ""),
                                    "snippet": result.get("body", ""),
                                    "source": "duckduckgo",
                                }
                            )
                        else:
                            urls_without_domain += 1
                            logger.debug("URL without valid .fr domain", url=url[:100], extracted_domain=domain)
                duration = time.time() - start_time
                logger.debug(
                    "DuckDuckGo search completed",
                    query=query[:100],
                    results=len(results),
                    urls_without_domain=urls_without_domain,
                    duration_seconds=round(duration, 2),
                )
                return results
        except Exception as e:
            duration = time.time() - start_time
            logger.warning(
                "DuckDuckGo search error",
                query=query[:100],
                error=str(e),
                error_type=type(e).__name__,
                duration_seconds=round(duration, 2),
            )
        return []

    async def search_competitors(
        self,
        domain: str,
        max_competitors: int = 100,
        db_session: AsyncSession = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for competitors using optimized 12-step pipeline.
        
        ⚠️ MÉTHODE INTERNE - Ne pas utiliser directement pour sauvegarder dans la DB.
        Utiliser `execute()` pour obtenir toutes les métadonnées complètes (total_found, 
        total_evaluated, all_candidates, excluded_candidates).

        Args:
            domain: Domain to find competitors for
            max_competitors: Maximum number of competitors to return
            db_session: Optional database session for enrichment

        Returns:
            List of all evaluated candidate dictionaries (included + excluded) with scores.
            Chaque candidat a un champ "included" (bool) indiquant s'il est inclus ou exclu.
        """
        pipeline_start_time = time.time()
        try:
            # Test Tavily connection - REQUIRED
            logger.info("Testing Tavily API connection before starting pipeline")
            self._tavily_available = await self._test_tavily_connection()
            
            if not self._tavily_available:
                error_msg = "Tavily API connection failed. Competitor search requires Tavily to be available."
                logger.error(
                    error_msg,
                    domain=domain,
                    tavily_api_key_configured=bool(settings.tavily_api_key),
                    tavily_api_key_length=len(settings.tavily_api_key) if settings.tavily_api_key else 0,
                )
                self.log_step("pipeline_start", "failed", error_msg)
                raise WorkflowError(error_msg)
            
            logger.info(
                "Starting competitor search pipeline",
                domain=domain,
                max_competitors=max_competitors,
                config_max_queries=self.config.max_queries,
                config_max_results_tavily=self.config.max_results_tavily,
                config_max_results_duckduckgo=self.config.max_results_duckduckgo,
                tavily_available=True,
            )
            self.log_step("pipeline_start", "running", f"Starting 12-step pipeline for {domain}")

            # Get site profile for context
            profile_start = time.time()
            if not db_session:
                from python_scripts.database.db_session import AsyncSessionLocal

                async with AsyncSessionLocal() as session:
                    profile = await get_site_profile_by_domain(session, domain)
            else:
                profile = await get_site_profile_by_domain(db_session, domain)

            profile_dict = {}
            if profile:
                profile_dict = {
                    "language_level": profile.language_level,
                    "editorial_tone": profile.editorial_tone,
                    "activity_domains": profile.activity_domains,
                    "keywords": profile.keywords,
                }
                logger.debug(
                    "Profile loaded",
                    domain=domain,
                    has_activity_domains=bool(profile.activity_domains),
                    has_keywords=bool(profile.keywords),
                    duration_seconds=round(time.time() - profile_start, 2),
                )
            else:
                logger.warning("No profile found for domain", domain=domain)

            # Step 1: Generate and execute multi-strategy queries
            step1_start = time.time()
            self.log_step("step_1", "running", "Generating and executing queries")
            keywords = self.query_generator.extract_keywords_from_profile(profile_dict)
            queries = self.query_generator.generate_queries(domain, keywords)

            logger.info(
                "Step 1: Query generation",
                domain=domain,
                keywords_count=len(keywords),
                queries_generated=len(queries),
                strategies=list(set(q["strategy"] for q in queries)),
            )

            all_results: List[Dict[str, Any]] = []
            strategy_results: Dict[str, Dict[str, int]] = {}

            for i, query_info in enumerate(queries, 1):
                query = query_info["query"]
                strategy = query_info["strategy"]

                # Search Tavily
                tavily_results = await self._search_tavily(query)
                for result in tavily_results:
                    result["strategy"] = strategy
                all_results.extend(tavily_results)

                # Search DuckDuckGo
                ddg_results = await self._search_duckduckgo(query)
                for result in ddg_results:
                    result["strategy"] = strategy
                all_results.extend(ddg_results)

                # Track strategy performance
                if strategy not in strategy_results:
                    strategy_results[strategy] = {"tavily": 0, "duckduckgo": 0, "total": 0}
                strategy_results[strategy]["tavily"] += len(tavily_results)
                strategy_results[strategy]["duckduckgo"] += len(ddg_results)
                strategy_results[strategy]["total"] += len(tavily_results) + len(ddg_results)

                # Log progress every 10 queries
                if i % 10 == 0:
                    logger.debug(
                        "Query execution progress",
                        domain=domain,
                        queries_executed=i,
                        total_queries=len(queries),
                        results_so_far=len(all_results),
                    )

            step1_duration = time.time() - step1_start
            logger.info(
                "Step 1: Query execution completed",
                domain=domain,
                queries_executed=len(queries),
                total_results=len(all_results),
                strategy_breakdown=strategy_results,
                duration_seconds=round(step1_duration, 2),
            )
            self.log_step("step_1", "completed", f"Found {len(all_results)} results from {len(queries)} queries")

            # Step 2: Deduplication by domain
            step2_start = time.time()
            self.log_step("step_2", "running", "Deduplicating by domain")
            deduplicated = self.domain_filter.filter(all_results, exclude_domain=domain)
            step2_duration = time.time() - step2_start
            logger.info(
                "Step 2: Deduplication completed",
                domain=domain,
                input_count=len(all_results),
                output_count=len(deduplicated),
                duplicates_removed=len(all_results) - len(deduplicated),
                duration_seconds=round(step2_duration, 2),
            )
            self.log_step("step_2", "completed", f"Deduplicated to {len(deduplicated)} domains")

            # Step 3: Pre-filtering (PDFs, excluded domains, tools, media)
            step3_start = time.time()
            self.log_step("step_3", "running", "Pre-filtering results")
            pre_filtered = self.pre_filter.filter(deduplicated)
            pre_filter_count = len(pre_filtered)
            pre_filtered = self.media_filter.filter(pre_filtered)
            step3_duration = time.time() - step3_start
            logger.info(
                "Step 3: Pre-filtering completed",
                domain=domain,
                input_count=len(deduplicated),
                after_prefilter=pre_filter_count,
                after_media_filter=len(pre_filtered),
                excluded_total=len(deduplicated) - len(pre_filtered),
                duration_seconds=round(step3_duration, 2),
            )
            self.log_step("step_3", "completed", f"Pre-filtered to {len(pre_filtered)} candidates")

            # Step 4: Enrichment homepage (top candidates)
            step4_start = time.time()
            self.log_step("step_4", "running", "Enriching top candidates")
            candidates_to_enrich = pre_filtered[:self.config.max_candidates_to_enrich]
            enriched_count = 0
            if db_session:
                enricher = CandidateEnricher(self.config, db_session)
                enriched = await enricher.enrich_candidates(candidates_to_enrich, max_candidates=len(candidates_to_enrich))
                enriched_count = sum(1 for c in enriched if c.get("enriched", False))
                # Merge enriched back with others
                enriched_domains = {c.get("domain") for c in enriched}
                for candidate in pre_filtered:
                    if candidate.get("domain") not in enriched_domains:
                        enriched.append(candidate)
                pre_filtered = enriched
            step4_duration = time.time() - step4_start
            logger.info(
                "Step 4: Enrichment completed",
                domain=domain,
                candidates_attempted=len(candidates_to_enrich),
                successfully_enriched=enriched_count,
                duration_seconds=round(step4_duration, 2),
            )
            self.log_step("step_4", "completed", f"Enriched {enriched_count}/{len(candidates_to_enrich)} candidates")

            # Step 5: Cross-source validation
            step5_start = time.time()
            self.log_step("step_5", "running", "Cross-source validation")
            cross_validated_count = 0
            if db_session:
                enricher = CandidateEnricher(self.config, db_session)
                pre_filtered = enricher.detect_cross_validation(pre_filtered)
                cross_validated_count = sum(1 for c in pre_filtered if c.get("cross_validated", False))
            step5_duration = time.time() - step5_start
            logger.info(
                "Step 5: Cross-validation completed",
                domain=domain,
                total_candidates=len(pre_filtered),
                cross_validated=cross_validated_count,
                duration_seconds=round(step5_duration, 2),
            )
            self.log_step("step_5", "completed", f"Cross-validated: {cross_validated_count} candidates")

            # Step 6: LLM filtering with enriched context
            step6_start = time.time()
            self.log_step("step_6", "running", "LLM filtering with enriched context")
            candidate_list = [{"domain": c.get("domain", ""), **c} for c in pre_filtered if c.get("domain")]
            
            if not candidate_list:
                logger.warning(
                    "No candidates available for LLM filtering",
                    domain=domain,
                    pre_filtered_count=len(pre_filtered),
                )
                filtered = []
            else:
                filtered = await self.relevance_classifier.classify_batch(domain, candidate_list, profile_dict)
            
            step6_duration = time.time() - step6_start
            logger.info(
                "Step 6: LLM filtering completed",
                domain=domain,
                input_candidates=len(candidate_list),
                output_competitors=len(filtered),
                filtered_out=len(candidate_list) - len(filtered) if candidate_list else 0,
                duration_seconds=round(step6_duration, 2),
            )
            self.log_step("step_6", "completed", f"LLM filtered to {len(filtered)} competitors")
            
            # If no candidates after LLM filtering, return early with diagnostic
            if not filtered:
                logger.error(
                    "No candidates after LLM filtering - pipeline stopping early",
                    domain=domain,
                    pipeline_diagnostic={
                        "step1_results": len(all_results),
                        "step2_deduplicated": len(deduplicated),
                        "step3_prefiltered": len(pre_filtered),
                        "step5_cross_validated": len(pre_filtered),
                        "step6_llm_input": len(candidate_list),
                    },
                )
                return []

            # Step 7: Semantic similarity calculation
            step7_start = time.time()
            self.log_step("step_7", "running", "Calculating semantic similarity")
            avg_similarity = 0.0
            if db_session:
                enricher = CandidateEnricher(self.config, db_session)
                # Prepare target text from profile
                target_text = " ".join(
                    [
                        str(profile_dict.get("activity_domains", {})),
                        str(profile_dict.get("keywords", {})),
                    ]
                )
                filtered = enricher.calculate_semantic_similarity(target_text, filtered)
                avg_similarity = sum(c.get("semantic_similarity", 0) for c in filtered) / len(filtered) if filtered else 0
            step7_duration = time.time() - step7_start
            logger.info(
                "Step 7: Semantic similarity completed",
                domain=domain,
                candidates_processed=len(filtered),
                avg_similarity=round(avg_similarity, 3),
                duration_seconds=round(step7_duration, 2),
            )
            self.log_step("step_7", "completed", "Semantic similarity calculated")

            # Step 8: Content validation
            step8_start = time.time()
            self.log_step("step_8", "running", "Content validation")
            content_validated = self.content_filter.filter(filtered)
            step8_duration = time.time() - step8_start
            logger.info(
                "Step 8: Content validation completed",
                domain=domain,
                input_count=len(filtered),
                output_count=len(content_validated),
                excluded=len(filtered) - len(content_validated),
                duration_seconds=round(step8_duration, 2),
            )
            self.log_step("step_8", "completed", f"Content validated: {len(content_validated)} candidates")

            # Step 9: Multi-criteria ranking
            step9_start = time.time()
            self.log_step("step_9", "running", "Multi-criteria ranking")
            esn_count = 0
            geo_matches = 0
            # Classify ESN and geographic
            for candidate in content_validated:
                # ESN classification
                esn_result = self.esn_classifier.classify(candidate)
                candidate["is_esn"] = esn_result.get("is_esn", False)
                candidate["esn_confidence"] = esn_result.get("esn_confidence", 0.0)
                candidate["esn_classification"] = esn_result
                if candidate["is_esn"]:
                    esn_count += 1

                # Geographic classification
                geo_result = self.geographic_classifier.classify(candidate)
                candidate.update(geo_result)
                if geo_result.get("geographic_match", False):
                    geo_matches += 1

            # Rank by combined score
            ranked = self.scorer.rank_candidates(content_validated)
            avg_combined_score = sum(c.get("combined_score", 0) for c in ranked) / len(ranked) if ranked else 0
            step9_duration = time.time() - step9_start
            logger.info(
                "Step 9: Multi-criteria ranking completed",
                domain=domain,
                candidates_ranked=len(ranked),
                esn_detected=esn_count,
                geographic_matches=geo_matches,
                avg_combined_score=round(avg_combined_score, 3),
                duration_seconds=round(step9_duration, 2),
            )
            self.log_step("step_9", "completed", f"Ranked {len(ranked)} candidates")

            # Step 10: Diversity assurance
            step10_start = time.time()
            self.log_step("step_10", "running", "Ensuring diversity")
            diverse = self.scorer.ensure_diversity(ranked, max_competitors)
            # Count by category
            category_counts = {}
            for c in diverse:
                cat = c.get("business_type", "autre")
                category_counts[cat] = category_counts.get(cat, 0) + 1
            step10_duration = time.time() - step10_start
            logger.info(
                "Step 10: Diversity assurance completed",
                domain=domain,
                input_count=len(ranked),
                output_count=len(diverse),
                category_distribution=category_counts,
                duration_seconds=round(step10_duration, 2),
            )
            self.log_step("step_10", "completed", f"Diverse selection: {len(diverse)} candidates")

            # Step 11: Confidence score calculation
            step11_start = time.time()
            self.log_step("step_11", "running", "Calculating confidence scores")
            # Already calculated in rank_candidates
            avg_confidence = sum(c.get("final_confidence", 0) for c in diverse) / len(diverse) if diverse else 0
            step11_duration = time.time() - step11_start
            logger.info(
                "Step 11: Confidence scores calculated",
                domain=domain,
                candidates_processed=len(diverse),
                avg_confidence=round(avg_confidence, 3),
                duration_seconds=round(step11_duration, 2),
            )
            self.log_step("step_11", "completed", "Confidence scores calculated")

            # Step 12: Final filtering with adjusted thresholds
            step12_start = time.time()
            self.log_step("step_12", "running", "Final filtering")
            
            # Log candidates before final filtering for debugging
            if diverse:
                logger.debug(
                    "Candidates before final filtering",
                    domain=domain,
                    count=len(diverse),
                    sample_scores=[
                        {
                            "domain": c.get("domain", ""),
                            "combined_score": c.get("combined_score", 0),
                            "final_confidence": c.get("final_confidence", 0),
                            "relevance_score": c.get("relevance_score", 0),
                        }
                        for c in diverse[:5]
                    ],
                )
            
            final_competitors = self.scorer.apply_final_filters(diverse, min_competitors=10)
            final_competitors = final_competitors[:max_competitors]
            step12_duration = time.time() - step12_start
            logger.info(
                "Step 12: Final filtering completed",
                domain=domain,
                input_count=len(diverse),
                output_count=len(final_competitors),
                excluded=len(diverse) - len(final_competitors),
                duration_seconds=round(step12_duration, 2),
            )
            self.log_step("step_12", "completed", f"Final: {len(final_competitors)} competitors")
            
            # Mark all candidates with inclusion status
            # Keep track of all candidates that were evaluated (from step 6 onwards - they have scores)
            final_domains = {c.get("domain", "").lower() for c in final_competitors}
            diverse_domains = {c.get("domain", "").lower() for c in diverse}
            all_evaluated_candidates = []
            
            # Get all candidates that were evaluated (from filtered onwards - they have LLM scores)
            # These are candidates from step 6 (LLM filtering) onwards
            all_scored_candidates = ranked  # ranked contains all candidates with scores
            
            # Add final competitors (included)
            for candidate in final_competitors:
                candidate["included"] = True
                candidate["exclusion_reason"] = None
                candidate["status"] = "included"
                all_evaluated_candidates.append(candidate)
            
            # Add excluded candidates from all_scored_candidates
            for candidate in all_scored_candidates:
                candidate_domain = candidate.get("domain", "").lower()
                if candidate_domain not in final_domains:
                    candidate["included"] = False
                    candidate["status"] = "excluded"
                    # Determine exclusion reason based on where they were filtered out
                    if candidate_domain not in diverse_domains:
                        candidate["exclusion_reason"] = "Excluded during diversity assurance step (category limit or ranking)"
                    elif candidate.get("final_confidence", 0) < self.config.min_confidence_score:
                        candidate["exclusion_reason"] = f"Confidence too low ({candidate.get('final_confidence', 0):.2f} < {self.config.min_confidence_score})"
                    elif candidate.get("combined_score", 0) < self.config.min_combined_score:
                        candidate["exclusion_reason"] = f"Combined score too low ({candidate.get('combined_score', 0):.2f} < {self.config.min_combined_score})"
                    else:
                        candidate["exclusion_reason"] = "Below final ranking threshold"
                    all_evaluated_candidates.append(candidate)
            
            # If no competitors found, log detailed diagnostic
            if not final_competitors:
                logger.error(
                    "No competitors found after pipeline",
                    domain=domain,
                    max_competitors=max_competitors,
                    pipeline_steps={
                        "step1_results": len(all_results),
                        "step2_deduplicated": len(deduplicated),
                        "step3_prefiltered": len(pre_filtered),
                        "step6_llm_filtered": len(filtered),
                        "step8_content_validated": len(content_validated),
                        "step9_ranked": len(ranked),
                        "step10_diverse": len(diverse),
                    },
                )

            # Log performance summary
            pipeline_duration = time.time() - pipeline_start_time
            perf_summary = self.query_generator.get_performance_summary()
            logger.info(
                "Pipeline completed successfully",
                domain=domain,
                competitors_found=len(final_competitors),
                max_competitors_requested=max_competitors,
                total_duration_seconds=round(pipeline_duration, 2),
                strategy_performance=perf_summary,
                pipeline_efficiency=round(len(final_competitors) / len(queries) if queries else 0, 2),
            )

            return all_evaluated_candidates

        except Exception as e:
            pipeline_duration = time.time() - pipeline_start_time
            logger.error(
                "Pipeline failed",
                domain=domain,
                error=str(e),
                error_type=type(e).__name__,
                duration_seconds=round(pipeline_duration, 2),
                exc_info=True,
            )
            self.log_step("pipeline_failed", "failed", f"Pipeline failed: {e}")
            raise WorkflowError(f"Competitor search failed: {e}") from e

    async def execute(
        self,
        execution_id: Any,
        input_data: Dict[str, Any],
        db_session: AsyncSession = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Execute competitor search workflow.
        
        ✅ MÉTHODE PUBLIQUE - Utiliser cette méthode pour obtenir toutes les métadonnées complètes.
        Cette méthode appelle `search_competitors()` en interne et enrichit les résultats avec
        toutes les métadonnées nécessaires pour la sauvegarde en base de données.

        Args:
            execution_id: Execution ID (UUID)
            input_data: Input data containing 'domain' and 'max_competitors'
            db_session: Optional database session
            **kwargs: Additional arguments

        Returns:
            Dict complet contenant :
            - competitors: Liste des concurrents inclus (included=True)
            - all_candidates: Tous les candidats évalués (inclus + exclus)
            - excluded_candidates: Liste des candidats exclus uniquement
            - total_found: Nombre de concurrents inclus
            - total_evaluated: Nombre total de candidats évalués
            - domain: Domaine analysé
        """
        domain = input_data.get("domain", "")
        max_competitors = input_data.get("max_competitors", 10)

        if not domain:
            raise ValueError("Domain is required for competitor search")

        all_candidates = await self.search_competitors(
            domain=domain,
            max_competitors=max_competitors,
            db_session=db_session,
        )

        # Separate included and excluded candidates
        included_competitors = [c for c in all_candidates if c.get("included", False)]
        excluded_candidates = [c for c in all_candidates if not c.get("included", False)]

        return {
            "competitors": included_competitors,
            "all_candidates": all_candidates,  # All evaluated candidates with stats
            "excluded_candidates": excluded_candidates,  # Only excluded ones
            "total_found": len(included_competitors),
            "total_evaluated": len(all_candidates),
            "domain": domain,
        }
