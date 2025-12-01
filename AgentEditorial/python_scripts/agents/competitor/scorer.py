"""Scorer for multi-criteria competitor ranking."""

from typing import Any, Dict, List

from python_scripts.agents.competitor.classifiers import BusinessTypeClassifier
from python_scripts.agents.competitor.config import CompetitorSearchConfig
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


class CompetitorScorer:
    """Scorer for multi-criteria competitor ranking with diversity assurance."""

    def __init__(self, config: CompetitorSearchConfig) -> None:
        """Initialize scorer."""
        self.config = config
        self.business_classifier = BusinessTypeClassifier(config)

    def calculate_combined_score(self, candidate: Dict[str, Any]) -> float:
        """
        Calculate combined relevance score.

        Args:
            candidate: Candidate dictionary with scores

        Returns:
            Combined score (0.0-1.0)
        """
        # Base LLM score
        llm_score = candidate.get("relevance_score", 0.5)
        confidence_score = candidate.get("confidence_score", 0.5)

        # Semantic similarity
        semantic_score = candidate.get("semantic_similarity", 0.5)

        # Cross-validation bonus
        cross_validation_bonus = 0.0
        if candidate.get("cross_validated", False):
            cross_validation_bonus = self.config.bonus_cross_validation

        # Geographic bonus
        geographic_bonus = candidate.get("geographic_bonus", 0.0)

        # ESN bonus (if ESN detected) - Renforcé
        esn_bonus = 0.0
        esn_confidence = candidate.get("esn_confidence", 0.0)
        if candidate.get("is_esn", False):
            if esn_confidence > 0.7:
                esn_bonus = 0.2  # Strong bonus for high-confidence ESN
            elif "SSII" in str(candidate.get("esn_classification", {}).get("esn_matches", [])):
                esn_bonus = 0.15  # Bonus for SSII
            else:
                esn_bonus = 0.1  # Standard bonus for ESN
        
        # Penalty for government/public services, business sale sites, directories
        gov_penalty = 0.0
        domain = candidate.get("domain", "").lower()
        description = candidate.get("description", "").lower()
        title = candidate.get("title", "").lower()
        snippet = candidate.get("snippet", "").lower()
        combined_text = f"{domain} {description} {title} {snippet}"
        
        # Government/public service patterns
        gov_patterns = [".ameli.fr", ".caf.fr", ".francetravail.fr", ".parcoursup.fr", 
                       ".labanquepostale.fr", ".gouv.fr", "service public", "administration", 
                       "gouvernement", "ministère", "bpifrance.fr", "reprise-entreprise.bpifrance.fr"]
        if any(pattern in combined_text for pattern in gov_patterns):
            gov_penalty = -0.3  # Strong penalty for government services
        
        # Business sale/transfer patterns
        business_sale_patterns = [
            "reprise d'entreprise", "reprise entreprise", "entreprise à vendre",
            "cession", "rachat", "transmission", "à vendre", "à céder",
            "ssii à vendre", "esn à vendre",
        ]
        if any(pattern in combined_text for pattern in business_sale_patterns):
            gov_penalty = -0.4  # Very strong penalty for business sale sites
        
        # Directory/listing patterns
        directory_patterns = [
            "pagesjaunes", "billetweb", "indeed", "adzuna", "glassdoor", "apec",
            "annuaire", "liste des", "classement", "comparer",
        ]
        if any(pattern in combined_text for pattern in directory_patterns):
            gov_penalty = -0.3  # Strong penalty for directories
        
        # University/educational patterns
        university_patterns = [
            "sciencespo", "esilv", "devinci", "esme", "univ-", "université",
            "universite", "école", "ecole", "académie", "academie", "ixesn.fr",
            "erasmus", "student network", "étudiant", "etudiant",
        ]
        if any(pattern in combined_text for pattern in university_patterns):
            gov_penalty = -0.3  # Strong penalty for universities

        # Calculate weighted score
        base_score = (
            (llm_score * self.config.weight_llm_score)
            + (semantic_score * self.config.weight_semantic_similarity)
        )

        # Add bonuses and penalties
        combined_score = base_score + cross_validation_bonus + geographic_bonus + esn_bonus + gov_penalty

        # Normalize to [0, 1]
        combined_score = max(0.0, min(1.0, combined_score))

        return round(combined_score, 4)

    def calculate_confidence_score(self, candidate: Dict[str, Any]) -> float:
        """
        Calculate final confidence score combining all signals.

        Args:
            candidate: Candidate dictionary

        Returns:
            Confidence score (0.0-1.0)
        """
        # Base confidence from LLM
        llm_confidence = candidate.get("confidence_score", 0.5)

        # Cross-validation increases confidence
        cross_validation_boost = 0.2 if candidate.get("cross_validated", False) else 0.0

        # Enrichment increases confidence
        enrichment_boost = 0.1 if candidate.get("enriched", False) else 0.0

        # Semantic similarity contributes to confidence
        semantic_confidence = candidate.get("semantic_similarity", 0.5) * 0.2

        # ESN detection increases confidence if detected
        esn_confidence = 0.1 if candidate.get("is_esn", False) else 0.0

        # Combine
        confidence = (
            llm_confidence * 0.4
            + semantic_confidence
            + cross_validation_boost
            + enrichment_boost
            + esn_confidence
        )

        # Normalize to [0, 1]
        confidence = max(0.0, min(1.0, confidence))

        return round(confidence, 4)

    def rank_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Rank candidates by combined score.

        Args:
            candidates: List of candidate dictionaries

        Returns:
            Ranked list
        """
        # Calculate scores for all candidates
        for candidate in candidates:
            candidate["combined_score"] = self.calculate_combined_score(candidate)
            candidate["final_confidence"] = self.calculate_confidence_score(candidate)

        # Sort by combined score (descending)
        ranked = sorted(candidates, key=lambda x: x.get("combined_score", 0), reverse=True)

        return ranked

    def ensure_diversity(
        self,
        candidates: List[Dict[str, Any]],
        max_competitors: int,
    ) -> List[Dict[str, Any]]:
        """
        Ensure diversity by category (ESN, agence web, etc.).

        Args:
            candidates: Ranked list of candidates
            max_competitors: Maximum number of competitors

        Returns:
            Diverse list respecting category limits
        """
        # Classify all candidates
        for candidate in candidates:
            esn_classification = candidate.get("esn_classification", {})
            business_type = self.business_classifier.classify(candidate, esn_classification)
            candidate["business_type"] = business_type

        # If we have fewer candidates than max_competitors, don't limit by category
        if len(candidates) <= max_competitors:
            logger.debug(
                "Not applying diversity limits - fewer candidates than max_competitors",
                candidates_count=len(candidates),
                max_competitors=max_competitors,
            )
            # Re-sort by combined score and return all
            return sorted(candidates, key=lambda x: x.get("combined_score", 0), reverse=True)

        # Group by category
        by_category: Dict[str, List[Dict[str, Any]]] = {}
        for candidate in candidates:
            category = candidate.get("business_type", "autre")
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(candidate)

        # Apply limits per category only if we have more candidates than max_competitors
        diverse: List[Dict[str, Any]] = []
        for category, category_candidates in by_category.items():
            max_per_cat = self.config.max_per_category.get(category, 10)
            # Only apply limit if we have more candidates than max_competitors
            if len(diverse) + len(category_candidates) > max_competitors:
                limited = category_candidates[:max_per_cat]
                diverse.extend(limited)
            else:
                # Add all candidates from this category if we're still under limit
                diverse.extend(category_candidates)

        # Re-sort by combined score
        diverse = sorted(diverse, key=lambda x: x.get("combined_score", 0), reverse=True)

        # Limit to max_competitors
        final_diverse = diverse[:max_competitors]
        
        logger.info(
            "Diversity assurance completed",
            input_count=len(candidates),
            output_count=len(final_diverse),
            categories_found=list(by_category.keys()),
            category_counts={cat: len(cands) for cat, cands in by_category.items()},
        )
        
        return final_diverse

    def apply_final_filters(
        self,
        candidates: List[Dict[str, Any]],
        min_competitors: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Apply final filters with adjusted thresholds.

        Args:
            candidates: List of candidates
            min_competitors: Minimum number to guarantee

        Returns:
            Filtered list
        """
        if not candidates:
            logger.warning("No candidates provided to final filter")
            return []

        # Ensure all candidates have scores calculated
        for candidate in candidates:
            if "combined_score" not in candidate:
                candidate["combined_score"] = self.calculate_combined_score(candidate)
            if "final_confidence" not in candidate:
                candidate["final_confidence"] = self.calculate_confidence_score(candidate)

        # Filter by thresholds
        filtered = [
            c
            for c in candidates
            if c.get("final_confidence", 0) >= self.config.min_confidence_score
            and c.get("combined_score", 0) >= self.config.min_combined_score
        ]

        logger.info(
            "Initial filtering completed",
            input_count=len(candidates),
            filtered_count=len(filtered),
            min_confidence_threshold=self.config.min_confidence_score,
            min_combined_threshold=self.config.min_combined_score,
        )

        # If too few results, relax thresholds
        if len(filtered) < min_competitors and len(candidates) > 0:
            logger.warning(
                "Too few results after filtering, relaxing thresholds",
                filtered=len(filtered),
                available=len(candidates),
                min_required=min_competitors,
                original_confidence_threshold=self.config.min_confidence_score,
                original_combined_threshold=self.config.min_combined_score,
            )
            # Relax thresholds by 10%
            relaxed_confidence = self.config.min_confidence_score * 0.9
            relaxed_combined = self.config.min_combined_score * 0.9

            filtered = [
                c
                for c in candidates
                if c.get("final_confidence", 0) >= relaxed_confidence
                and c.get("combined_score", 0) >= relaxed_combined
            ]

            logger.info(
                "After relaxed thresholds",
                filtered_count=len(filtered),
                relaxed_confidence_threshold=relaxed_confidence,
                relaxed_combined_threshold=relaxed_combined,
            )

            # If still too few, take top candidates regardless
            if len(filtered) < min_competitors:
                logger.warning(
                    "Still too few results, taking top candidates regardless of thresholds",
                    filtered=len(filtered),
                    min_required=min_competitors,
                    available_candidates=len(candidates),
                )
                # Take top candidates, but at least return what we have
                filtered = sorted(candidates, key=lambda x: x.get("combined_score", 0), reverse=True)[
                    :max(min_competitors, len(filtered))
                ]
        
        # If we still have no results but have candidates, return top candidates anyway
        if not filtered and candidates:
            logger.warning(
                "No candidates passed thresholds, returning top candidates anyway",
                candidates_available=len(candidates),
            )
            filtered = sorted(candidates, key=lambda x: x.get("combined_score", 0), reverse=True)[:min_competitors]

        # Log final filtering results
        if filtered:
            avg_confidence = sum(c.get("final_confidence", 0) for c in filtered) / len(filtered)
            avg_combined = sum(c.get("combined_score", 0) for c in filtered) / len(filtered)
            logger.info(
                "Final filtering completed",
                output_count=len(filtered),
                avg_confidence=round(avg_confidence, 3),
                avg_combined_score=round(avg_combined, 3),
            )
        else:
            logger.warning(
                "No candidates passed final filtering",
                input_count=len(candidates),
                min_confidence_threshold=self.config.min_confidence_score,
                min_combined_threshold=self.config.min_combined_score,
            )

        return filtered

