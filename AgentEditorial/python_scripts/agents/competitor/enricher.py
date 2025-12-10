"""Enricher for candidate domains with homepage content and semantic similarity."""

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.agents.competitor.config import CompetitorSearchConfig
from python_scripts.ingestion.crawl_pages import crawl_with_permissions
from python_scripts.ingestion.text_cleaner import clean_html_text, extract_meta_description
from python_scripts.utils.logging import get_logger
from python_scripts.vectorstore.embeddings_utils import generate_embedding, generate_embeddings_batch

logger = get_logger(__name__)


class CandidateEnricher:
    """Enrich candidate domains with homepage content and metadata."""

    def __init__(self, config: CompetitorSearchConfig, db_session: AsyncSession) -> None:
        """Initialize enricher."""
        self.config = config
        self.db_session = db_session

    async def enrich_candidates(
        self,
        candidates: List[Dict[str, Any]],
        max_candidates: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Enrich top candidates with homepage content.

        Args:
            candidates: List of candidate dictionaries
            max_candidates: Maximum number of candidates to enrich

        Returns:
            Enriched candidates list
        """
        # Limit to top candidates
        candidates_to_enrich = candidates[:max_candidates]
        enriched: List[Dict[str, Any]] = []
        logger.info(
            "Starting candidate enrichment",
            total_candidates=len(candidates),
            candidates_to_enrich=len(candidates_to_enrich),
        )

        for i, candidate in enumerate(candidates_to_enrich, 1):
            try:
                domain = candidate.get("domain", "")
                if not domain:
                    continue

                url = f"https://{domain}"

                # Crawl homepage
                crawled = await crawl_with_permissions(
                    url=url,
                    db_session=self.db_session,
                    use_cache=True,
                    respect_robots=True,
                )

                if crawled and crawled.get("text"):
                    # Extract description
                    description = extract_meta_description(crawled.get("html", ""))
                    if not description:
                        # Use first paragraph as description
                        text = crawled.get("text", "")
                        first_paragraph = text.split("\n\n")[0] if text else ""
                        description = first_paragraph[:300]  # Limit to 300 chars

                    # Extract services section
                    services = self._extract_services(crawled.get("html", ""), crawled.get("text", ""))

                    # Extract activity keywords
                    activity_keywords = self._extract_activity_keywords(crawled.get("text", ""))

                    # Update candidate
                    candidate["description"] = description
                    candidate["services"] = services[:3]  # Limit to 3 services
                    candidate["activity_keywords"] = activity_keywords[:5]  # Limit to 5 keywords
                    candidate["enriched"] = True

                enriched.append(candidate)
                if i % 10 == 0:
                    logger.debug(
                        "Enrichment progress",
                        processed=i,
                        total=len(candidates_to_enrich),
                        successfully_enriched=sum(1 for c in enriched if c.get("enriched", False)),
                    )

            except Exception as e:
                logger.warning(
                    "Failed to enrich candidate",
                    domain=candidate.get("domain", ""),
                    error=str(e),
                    error_type=type(e).__name__,
                )
                # Keep candidate without enrichment
                candidate["enriched"] = False
                enriched.append(candidate)

        successfully_enriched = sum(1 for c in enriched if c.get("enriched", False))
        logger.info(
            "Candidate enrichment completed",
            total_processed=len(enriched),
            successfully_enriched=successfully_enriched,
            failed=len(enriched) - successfully_enriched,
            success_rate=round(successfully_enriched / len(enriched) * 100, 1) if enriched else 0,
        )
        return enriched

    def _extract_services(self, html: str, text: str) -> List[str]:
        """Extract services from content."""
        services: List[str] = []
        service_patterns = [
            r"services?[:\s]+([^\.]+)",
            r"prestations?[:\s]+([^\.]+)",
            r"offres?[:\s]+([^\.]+)",
            r"solutions?[:\s]+([^\.]+)",
        ]

        combined = f"{html} {text}".lower()

        for pattern in service_patterns:
            matches = re.findall(pattern, combined, re.IGNORECASE)
            for match in matches:
                service = match.strip()
                if len(service) > 10 and len(service) < 100:  # Reasonable length
                    services.append(service)

        return list(dict.fromkeys(services))  # Remove duplicates

    def _extract_activity_keywords(self, text: str) -> List[str]:
        """Extract activity keywords from text."""
        activity_keywords = [
            "conseil",
            "développement",
            "web",
            "digital",
            "marketing",
            "communication",
            "intégration",
            "maintenance",
            "infrastructure",
            "cloud",
            "cybersécurité",
            "transformation",
        ]

        text_lower = text.lower()
        found_keywords = [kw for kw in activity_keywords if kw in text_lower]

        return found_keywords

    def detect_cross_validation(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect candidates found in multiple sources (cross-validation).

        Args:
            candidates: List of candidate dictionaries

        Returns:
            Updated candidates with cross_validation flag
        """
        # Group by domain
        domain_sources: Dict[str, List[str]] = {}
        for candidate in candidates:
            domain = candidate.get("domain", "")
            source = candidate.get("source", "")
            if domain:
                if domain not in domain_sources:
                    domain_sources[domain] = []
                if source:
                    domain_sources[domain].append(source)

        # Mark cross-validated candidates
        for candidate in candidates:
            domain = candidate.get("domain", "")
            sources = domain_sources.get(domain, [])
            unique_sources = list(set(sources))
            is_cross_validated = len(unique_sources) > 1

            candidate["cross_validated"] = is_cross_validated
            candidate["sources"] = unique_sources
            candidate["source_count"] = len(unique_sources)

        cross_validated_count = sum(1 for c in candidates if c.get("cross_validated", False))
        logger.info(
            "Cross-validation completed",
            total_candidates=len(candidates),
            cross_validated=cross_validated_count,
            cross_validation_rate=round(cross_validated_count / len(candidates) * 100, 1) if candidates else 0,
        )
        return candidates

    def calculate_semantic_similarity(
        self,
        target_text: str,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Calculate semantic similarity between target and candidates.

        Args:
            target_text: Target text (keywords or description)
            candidates: List of candidate dictionaries

        Returns:
            Updated candidates with semantic_similarity scores
        """
        try:
            # Generate target embedding
            target_embedding = np.array(generate_embedding(target_text))

            # Prepare candidate texts
            candidate_texts = []
            for candidate in candidates:
                # Combine description, services, keywords
                text_parts = []
                if candidate.get("description"):
                    text_parts.append(candidate["description"])
                if candidate.get("services"):
                    text_parts.extend(candidate["services"])
                if candidate.get("activity_keywords"):
                    text_parts.extend(candidate["activity_keywords"])
                candidate_text = " ".join(text_parts) or candidate.get("domain", "")
                candidate_texts.append(candidate_text)

            # Generate embeddings batch
            candidate_embeddings = generate_embeddings_batch(candidate_texts, batch_size=32)

            # Calculate cosine similarity
            for i, candidate in enumerate(candidates):
                if i < len(candidate_embeddings):
                    candidate_emb = np.array(candidate_embeddings[i])
                    # Cosine similarity (embeddings are already normalized)
                    similarity = float(np.dot(target_embedding, candidate_emb))
                    candidate["semantic_similarity"] = max(0.0, min(1.0, similarity))  # Clamp to [0, 1]
                else:
                    candidate["semantic_similarity"] = 0.0

            avg_similarity = sum(c.get("semantic_similarity", 0) for c in candidates) / len(candidates) if candidates else 0
            max_similarity = max((c.get("semantic_similarity", 0) for c in candidates), default=0)
            min_similarity = min((c.get("semantic_similarity", 0) for c in candidates), default=0)
            logger.info(
                "Semantic similarity calculation completed",
                candidates_processed=len(candidates),
                avg_similarity=round(avg_similarity, 3),
                max_similarity=round(max_similarity, 3),
                min_similarity=round(min_similarity, 3),
            )
            return candidates

        except Exception as e:
            logger.warning(
                "Semantic similarity calculation failed",
                error=str(e),
                error_type=type(e).__name__,
                candidates_count=len(candidates),
            )
            # Fallback: set default similarity
            for candidate in candidates:
                candidate["semantic_similarity"] = 0.5
            return candidates

