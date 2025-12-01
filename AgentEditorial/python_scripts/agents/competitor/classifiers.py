"""Classifiers for competitor categorization and scoring."""

import json
import re
from typing import Any, Dict, List, Optional

from python_scripts.agents.competitor.config import CompetitorSearchConfig
from python_scripts.agents.prompts import COMPETITOR_FILTERING_PROMPT
from python_scripts.agents.utils.llm_factory import get_phi3_llm
from python_scripts.utils.exceptions import LLMError
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


class ESNClassifier:
    """Classifier for detecting ESN (Entreprise de Services Numériques)."""

    def __init__(self, config: CompetitorSearchConfig) -> None:
        """Initialize ESN classifier."""
        self.config = config

    def classify(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify if a result is an ESN.

        Args:
            result: Search result dictionary

        Returns:
            Classification result with is_esn flag and confidence
        """
        domain = result.get("domain", "").lower()
        title = result.get("title", "").lower()
        snippet = result.get("snippet", "").lower()
        description = result.get("description", "").lower()
        services = result.get("services", [])

        combined_text = f"{title} {snippet} {description} {' '.join(services) if services else ''}"

        # Check ESN keywords
        esn_score = 0.0
        matches: List[str] = []

        # Check exact keywords
        for keyword in self.config.esn_keywords:
            if keyword.lower() in combined_text:
                esn_score += 0.3
                matches.append(keyword)

        # Check patterns
        for pattern in self.config.esn_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                esn_score += 0.2
                matches.append(pattern)

        # Check activity keywords
        activity_matches = sum(1 for kw in self.config.esn_activity_keywords if kw.lower() in combined_text)
        if activity_matches >= 2:
            esn_score += 0.3
        elif activity_matches == 1:
            esn_score += 0.15

        # Normalize score
        esn_score = min(esn_score, 1.0)

        is_esn = esn_score >= 0.4  # Threshold for ESN detection

        return {
            "is_esn": is_esn,
            "esn_confidence": round(esn_score, 2),
            "esn_matches": matches[:5],  # Limit matches
        }


class BusinessTypeClassifier:
    """Classifier for business type categorization."""

    def __init__(self, config: CompetitorSearchConfig) -> None:
        """Initialize business type classifier."""
        self.config = config

    def classify(self, result: Dict[str, Any], esn_classification: Optional[Dict[str, Any]] = None) -> str:
        """
        Classify business type.

        Args:
            result: Search result dictionary
            esn_classification: Optional ESN classification result

        Returns:
            Business type category
        """
        # If already classified as ESN
        if esn_classification and esn_classification.get("is_esn", False):
            return "ESN"

        domain = result.get("domain", "").lower()
        title = result.get("title", "").lower()
        snippet = result.get("snippet", "").lower()
        description = result.get("description", "").lower()

        combined_text = f"{title} {snippet} {description}"

        # Check for agence web
        web_keywords = ["agence web", "création site", "développement web", "web agency"]
        if any(kw in combined_text for kw in web_keywords):
            return "agence_web"

        # Check for agence marketing
        marketing_keywords = ["agence marketing", "marketing digital", "communication", "publicité"]
        if any(kw in combined_text for kw in marketing_keywords):
            return "agence_marketing"

        # Check for freelancer
        freelancer_keywords = ["freelance", "indépendant", "consultant indépendant", "auto-entrepreneur"]
        if any(kw in combined_text for kw in freelancer_keywords):
            return "freelancer"

        # Default
        return "autre"


class RelevanceClassifier:
    """LLM-based relevance classifier with calibrated thresholds."""

    def __init__(self, config: CompetitorSearchConfig) -> None:
        """Initialize relevance classifier."""
        self.config = config

    async def classify_batch(
        self,
        domain: str,
        candidates: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Classify relevance of candidates using LLM.

        Args:
            domain: Target domain
            candidates: List of candidate dictionaries
            context: Context about target domain

        Returns:
            List of classified candidates with scores
        """
        if not candidates:
            return []

        try:
            llm = get_phi3_llm(temperature=0.3)  # Lower temperature for consistency

            # Process candidates in batches - reduced size for better reliability
            batch_size = 15  # Further reduced to 15 for better reliability and to ensure all are evaluated
            result_map: Dict[str, Dict[str, Any]] = {}
            total_batches = (len(candidates) + batch_size - 1) // batch_size
            
            logger.info(
                "Starting LLM batch processing",
                total_candidates=len(candidates),
                batch_size=batch_size,
                total_batches=total_batches,
            )
            
            for i in range(0, len(candidates), batch_size):
                batch = candidates[i:i + batch_size]
                candidates_text = "\n".join([f"- {c.get('domain', '')}" for c in batch])

                # Format prompt
                prompt = COMPETITOR_FILTERING_PROMPT.format(
                    domain=domain,
                    context=json.dumps(context, indent=2),
                    candidates=candidates_text,
                )

                # Invoke LLM
                try:
                    if hasattr(llm, "ainvoke"):
                        response = await llm.ainvoke(prompt)
                    elif hasattr(llm, "invoke"):
                        response = llm.invoke(prompt)
                    else:
                        response = await llm(prompt)

                    # Parse JSON response
                    response_text = response if isinstance(response, str) else str(response)
                    
                    # Log raw response for debugging if empty
                    if i == 0 and len(result_map) == 0:
                        logger.debug(
                            "LLM raw response (first batch)",
                            response_preview=response_text[:500] if len(response_text) > 500 else response_text,
                        )

                    # Extract JSON (reuse logic from agent_analysis)
                    json_start = response_text.find("{")
                    json_end = response_text.rfind("}") + 1
                    if json_start >= 0 and json_end > json_start:
                        json_text = response_text[json_start:json_end]
                        try:
                            parsed = json.loads(json_text)
                        except json.JSONDecodeError:
                            # Try JSON block
                            json_block_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
                            if json_block_match:
                                parsed = json.loads(json_block_match.group(1))
                            else:
                                logger.warning(
                                    "Failed to parse LLM JSON response",
                                    batch=i // batch_size + 1,
                                    response_preview=response_text[:200],
                                )
                                continue
                    else:
                        logger.warning(
                            "No JSON found in LLM response",
                            batch=i // batch_size + 1,
                            response_preview=response_text[:200],
                        )
                        continue

                    # Extract competitors from this batch
                    competitors_data = parsed.get("competitors", [])
                    if not isinstance(competitors_data, list):
                        competitors_data = []

                    # Add to result map
                    for item in competitors_data:
                        if isinstance(item, dict):
                            domain_name = item.get("domain", "")
                            if domain_name:
                                result_map[domain_name.lower()] = {
                                    "relevance_score": float(item.get("relevance_score", 0.5)),
                                    "confidence_score": float(item.get("confidence_score", 0.5)),
                                    "reason": item.get("reason", ""),
                                }
                except Exception as batch_error:
                    logger.warning(
                        "LLM batch processing error",
                        batch=i // batch_size + 1,
                        error=str(batch_error),
                        error_type=type(batch_error).__name__,
                    )
                    continue
            
            # Log if LLM didn't evaluate all candidates
            evaluated_domains = set(result_map.keys())
            candidate_domains = {c.get("domain", "").lower() for c in candidates if c.get("domain")}
            missing_domains = candidate_domains - evaluated_domains
            if missing_domains:
                logger.warning(
                    "LLM did not evaluate all candidates",
                    total_candidates=len(candidates),
                    evaluated=len(evaluated_domains),
                    missing=len(missing_domains),
                    missing_domains=list(missing_domains)[:20],  # Log first 20
                    evaluation_rate=f"{len(evaluated_domains) / len(candidate_domains) * 100:.1f}%",
                )

            # Apply classifications to candidates
            classified: List[Dict[str, Any]] = []
            not_in_llm_response = 0
            below_threshold = 0
            
            for candidate in candidates:
                candidate_domain = candidate.get("domain", "").lower()
                if candidate_domain in result_map:
                    classification = result_map[candidate_domain]
                    # Only include if above threshold
                    if classification["relevance_score"] >= self.config.min_relevance_score:
                        candidate.update(classification)
                        classified.append(candidate)
                    else:
                        below_threshold += 1
                        logger.debug(
                            "Candidate below threshold",
                            domain=candidate_domain,
                            relevance_score=classification["relevance_score"],
                            threshold=self.config.min_relevance_score,
                        )
                else:
                    not_in_llm_response += 1
                    # Fallback: evaluate based on signals if not in LLM response
                    esn_classification = candidate.get("esn_classification", {})
                    is_esn = esn_classification.get("is_esn", False)
                    esn_confidence = esn_classification.get("esn_confidence", 0.0)
                    is_enriched = candidate.get("enriched", False)
                    
                    # Calculate fallback score based on signals
                    fallback_score = 0.3  # Default low score
                    if is_esn and esn_confidence > 0.7:
                        fallback_score = 0.6  # High confidence ESN
                    elif is_esn and esn_confidence > 0.5:
                        fallback_score = 0.5  # Medium confidence ESN
                    elif is_enriched:
                        # If enriched, give benefit of doubt (might be valid competitor)
                        fallback_score = 0.45  # Just at threshold
                    
                    candidate["relevance_score"] = fallback_score
                    candidate["confidence_score"] = 0.4 if fallback_score >= 0.45 else 0.3
                    candidate["reason"] = f"Not evaluated by LLM - fallback score based on signals (ESN: {is_esn}, enriched: {is_enriched})"
                    
                    # Include if above threshold or has strong signals
                    if fallback_score >= self.config.min_relevance_score or (is_esn and esn_confidence > 0.5):
                        classified.append(candidate)
            
            if not_in_llm_response > 0 or below_threshold > 0:
                logger.info(
                    "LLM classification details",
                    not_in_response=not_in_llm_response,
                    below_threshold=below_threshold,
                    classified=len(classified),
                    excluded_not_evaluated=not_in_llm_response,
                )

            # Log classification results
            avg_relevance = sum(c.get("relevance_score", 0) for c in classified) / len(classified) if classified else 0
            above_threshold = sum(1 for c in classified if c.get("relevance_score", 0) >= self.config.min_relevance_score)
            logger.info(
                "LLM classification completed",
                domain=domain,
                input_candidates=len(candidates),
                output_competitors=len(classified),
                avg_relevance_score=round(avg_relevance, 3),
                above_threshold=above_threshold,
                threshold=self.config.min_relevance_score,
            )
            return classified

        except Exception as e:
            logger.warning(
                "LLM classification failed, using fallback",
                domain=domain,
                error=str(e),
                error_type=type(e).__name__,
                candidates_count=len(candidates),
            )
            # Fallback: return all with default scores
            return [
                {
                    **c,
                    "relevance_score": 0.5,
                    "confidence_score": 0.5,
                    "reason": "LLM classification failed",
                }
                for c in candidates
            ]


class GeographicClassifier:
    """Classifier for geographic matching."""

    def __init__(self, config: CompetitorSearchConfig) -> None:
        """Initialize geographic classifier."""
        self.config = config
        self.regions = [
            "paris",
            "ile-de-france",
            "lyon",
            "nantes",
            "marseille",
            "toulouse",
            "bordeaux",
            "lille",
            "strasbourg",
        ]

    def extract_location(self, result: Dict[str, Any]) -> Optional[str]:
        """
        Extract location from result.

        Args:
            result: Search result dictionary

        Returns:
            Location string if found, None otherwise
        """
        domain = result.get("domain", "").lower()
        title = result.get("title", "").lower()
        snippet = result.get("snippet", "").lower()
        description = result.get("description", "").lower()

        combined_text = f"{title} {snippet} {description}"

        # Check for region mentions
        for region in self.regions:
            if region in combined_text or region in domain:
                return region

        return None

    def match_geographic(self, target_location: Optional[str], candidate_location: Optional[str]) -> bool:
        """
        Check if locations match.

        Args:
            target_location: Target location
            candidate_location: Candidate location

        Returns:
            True if locations match
        """
        if not target_location or not candidate_location:
            return False

        return target_location.lower() == candidate_location.lower()

    def classify(self, result: Dict[str, Any], target_location: Optional[str] = None) -> Dict[str, Any]:
        """
        Classify geographic information.

        Args:
            result: Search result dictionary
            target_location: Optional target location for matching

        Returns:
            Geographic classification result
        """
        location = self.extract_location(result)
        is_match = False

        if target_location and location:
            is_match = self.match_geographic(target_location, location)

        return {
            "location": location,
            "geographic_match": is_match,
            "geographic_bonus": 0.1 if is_match else 0.0,
        }

