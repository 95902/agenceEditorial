"""LLM enricher for article recommendations."""

import asyncio
import json
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from python_scripts.agents.trend_pipeline.article_enrichment.config import ArticleEnrichmentConfig
from python_scripts.agents.trend_pipeline.article_enrichment.prompts import (
    COMPLETE_ENRICHMENT_PROMPT,
    HOOK_PERSONALIZATION_PROMPT,
    OUTLINE_ENRICHMENT_PROMPT,
    STATISTICS_INTEGRATION_PROMPT,
)
from python_scripts.agents.utils.llm_factory import create_llm
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


class ArticleLLMEnricher:
    """LLM-based article enrichment service."""
    
    def __init__(self, config: Optional[ArticleEnrichmentConfig] = None):
        """
        Initialize the article LLM enricher.
        
        Args:
            config: Article enrichment configuration
        """
        self.config = config or ArticleEnrichmentConfig.default()
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._llm_cache: Dict[str, Any] = {}
    
    def _get_llm(self, model_name: str, timeout: int = 300):
        """Get or create LLM instance for a model."""
        cache_key = f"{model_name}_{timeout}"
        if cache_key not in self._llm_cache:
            self._llm_cache[cache_key] = create_llm(
                model_name=model_name,
                temperature=0.7,
                timeout=timeout,
            )
        return self._llm_cache[cache_key]
    
    async def _invoke_llm(self, prompt: str, model: str, timeout: int) -> str:
        """Invoke LLM asynchronously using thread pool."""
        llm = self._get_llm(model, timeout)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            llm.invoke,
            prompt,
        )
    
    async def enrich_outline(
        self,
        title: str,
        hook: str,
        outline: Any,
        client_context: Dict[str, Any],
        statistics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Enrich article outline with detailed structure.
        
        Args:
            title: Article title
            hook: Article hook
            outline: Original outline (can be list or dict)
            client_context: Client context from site_analysis_results
            statistics: Trend statistics (volume, velocity, priority, etc.)
            
        Returns:
            Enriched outline structure
        """
        # Normalize outline to string representation
        if isinstance(outline, list):
            outline_str = json.dumps(outline, ensure_ascii=False, indent=2)
        elif isinstance(outline, dict):
            outline_str = json.dumps(outline, ensure_ascii=False, indent=2)
        else:
            outline_str = str(outline)
        
        # Extract client context
        editorial_tone = client_context.get("editorial_tone", "professional")
        language_level = client_context.get("language_level", "intermediate")
        target_audience = client_context.get("target_audience", {})
        activity_domains = client_context.get("activity_domains", {})
        keywords = client_context.get("keywords", {})
        
        # Format target audience
        if isinstance(target_audience, dict):
            target_audience_str = target_audience.get("primary", "general audience")
        else:
            target_audience_str = str(target_audience)
        
        # Format activity domains
        if isinstance(activity_domains, dict):
            primary_domains = activity_domains.get("primary_domains", [])
            activity_domains_str = ", ".join(primary_domains) if primary_domains else "general"
        else:
            activity_domains_str = str(activity_domains)
        
        # Format keywords
        if isinstance(keywords, dict):
            primary_keywords = keywords.get("primary_keywords", [])
            primary_keywords_str = ", ".join(primary_keywords) if primary_keywords else ""
        else:
            primary_keywords_str = str(keywords)
        
        # Format statistics
        competitor_volume = statistics.get("competitor_volume", 0)
        velocity = statistics.get("velocity", 0.0)
        priority_score = statistics.get("priority_score", 0.0)
        coverage_gap = statistics.get("coverage_gap", 0.0)
        
        # Format prompt
        prompt = OUTLINE_ENRICHMENT_PROMPT.format(
            title=title,
            hook=hook,
            outline=outline_str,
            editorial_tone=editorial_tone,
            language_level=language_level,
            target_audience=target_audience_str,
            activity_domains=activity_domains_str,
            primary_keywords=primary_keywords_str,
            competitor_volume=competitor_volume,
            velocity=velocity,
            priority_score=priority_score,
            coverage_gap=coverage_gap,
        )
        
        # Get model
        model = self.config.models.get("outline_enrichment", self.config.fallback_model)
        
        try:
            response = await self._invoke_llm(
                prompt=prompt,
                model=model,
                timeout=self.config.outline_enrichment_timeout_seconds,
            )
            
            # Parse JSON response
            result = self._parse_json_response(response)
            
            # Ensure result is a dictionary
            if not isinstance(result, dict):
                logger.warning(
                    "Parsed result is not a dictionary",
                    result_type=type(result).__name__,
                    result_preview=str(result)[:200]
                )
                result = {"raw_response": str(result)}
            
            result["llm_model_used"] = model
            return result
            
        except Exception as e:
            logger.error("Outline enrichment failed", error=str(e), title=title)
            return {
                "error": str(e),
                "llm_model_used": model,
                "original_outline": outline,
            }
    
    async def personalize_hook(
        self,
        hook: str,
        client_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Personalize article hook according to client context.
        
        Args:
            hook: Original hook
            client_context: Client context from site_analysis_results
            
        Returns:
            Personalized hook and adaptation notes
        """
        # Extract client context
        editorial_tone = client_context.get("editorial_tone", "professional")
        target_audience = client_context.get("target_audience", {})
        activity_domains = client_context.get("activity_domains", {})
        keywords = client_context.get("keywords", {})
        style_features = client_context.get("style_features", {})
        
        # Format target audience
        if isinstance(target_audience, dict):
            target_audience_str = target_audience.get("primary", "general audience")
        else:
            target_audience_str = str(target_audience)
        
        # Format activity domains
        if isinstance(activity_domains, dict):
            primary_domains = activity_domains.get("primary_domains", [])
            activity_domains_str = ", ".join(primary_domains) if primary_domains else "general"
        else:
            activity_domains_str = str(activity_domains)
        
        # Format keywords
        if isinstance(keywords, dict):
            primary_keywords = keywords.get("primary_keywords", [])
            primary_keywords_str = ", ".join(primary_keywords) if primary_keywords else ""
        else:
            primary_keywords_str = str(keywords)
        
        # Format style features
        if isinstance(style_features, dict):
            sentence_length = style_features.get("sentence_length_avg", "15-20 words")
            target_length = 50  # Default
            if "15-20" in str(sentence_length):
                target_length = 50
            elif "20-25" in str(sentence_length):
                target_length = 60
            else:
                target_length = 50
        else:
            target_length = 50
        
        # Format prompt
        prompt = HOOK_PERSONALIZATION_PROMPT.format(
            hook=hook,
            editorial_tone=editorial_tone,
            target_audience=target_audience_str,
            activity_domains=activity_domains_str,
            primary_keywords=primary_keywords_str,
            style_features=str(style_features),
            target_length=target_length,
        )
        
        # Get model
        model = self.config.models.get("angle_personalization", self.config.fallback_model)
        
        try:
            response = await self._invoke_llm(
                prompt=prompt,
                model=model,
                timeout=self.config.angle_personalization_timeout_seconds,
            )
            
            # Parse JSON response
            result = self._parse_json_response(response)
            
            # Ensure result is a dictionary
            if not isinstance(result, dict):
                logger.warning(
                    "Parsed result is not a dictionary",
                    result_type=type(result).__name__,
                    result_preview=str(result)[:200]
                )
                result = {"raw_response": str(result)}
            
            result["llm_model_used"] = model
            return result
            
        except Exception as e:
            logger.error("Hook personalization failed", error=str(e))
            return {
                "personalized_hook": hook,  # Return original on error
                "error": str(e),
                "llm_model_used": model,
            }
    
    async def enrich_complete(
        self,
        title: str,
        hook: str,
        outline: Any,
        effort_level: str,
        differentiation_score: Optional[float],
        client_context: Dict[str, Any],
        statistics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Complete article enrichment (all-in-one).
        
        Args:
            title: Article title
            hook: Article hook
            outline: Original outline
            effort_level: Effort level (easy/medium/complex)
            differentiation_score: Differentiation score (0-1)
            client_context: Client context from site_analysis_results
            statistics: Trend statistics
            
        Returns:
            Complete enriched article structure
        """
        # Normalize outline
        if isinstance(outline, list):
            outline_str = json.dumps(outline, ensure_ascii=False, indent=2)
        elif isinstance(outline, dict):
            outline_str = json.dumps(outline, ensure_ascii=False, indent=2)
        else:
            outline_str = str(outline)
        
        # Extract client context
        editorial_tone = client_context.get("editorial_tone", "professional")
        language_level = client_context.get("language_level", "intermediate")
        target_audience = client_context.get("target_audience", {})
        activity_domains = client_context.get("activity_domains", {})
        keywords = client_context.get("keywords", {})
        style_features = client_context.get("style_features", {})
        
        # Format context
        if isinstance(target_audience, dict):
            target_audience_str = target_audience.get("primary", "general audience")
        else:
            target_audience_str = str(target_audience)
        
        if isinstance(activity_domains, dict):
            primary_domains = activity_domains.get("primary_domains", [])
            activity_domains_str = ", ".join(primary_domains) if primary_domains else "general"
        else:
            activity_domains_str = str(activity_domains)
        
        if isinstance(keywords, dict):
            primary_keywords = keywords.get("primary_keywords", [])
            primary_keywords_str = ", ".join(primary_keywords) if primary_keywords else ""
        else:
            primary_keywords_str = str(keywords)
        
        # Format statistics
        competitor_volume = statistics.get("competitor_volume", 0)
        velocity = statistics.get("velocity", 0.0)
        velocity_trend = statistics.get("velocity_trend", "stable")
        priority_score = statistics.get("priority_score", 0.0)
        coverage_gap = statistics.get("coverage_gap", 0.0)
        source_diversity = statistics.get("source_diversity", 0)
        
        # Format prompt
        prompt = COMPLETE_ENRICHMENT_PROMPT.format(
            title=title,
            hook=hook,
            outline=outline_str,
            effort_level=effort_level,
            differentiation_score=differentiation_score or 0.0,
            editorial_tone=editorial_tone,
            language_level=language_level,
            target_audience=target_audience_str,
            activity_domains=activity_domains_str,
            primary_keywords=primary_keywords_str,
            style_features=str(style_features),
            competitor_volume=competitor_volume,
            velocity=velocity,
            velocity_trend=velocity_trend,
            priority_score=priority_score,
            coverage_gap=coverage_gap,
            source_diversity=source_diversity,
        )
        
        # Get model (use outline_enrichment model for complete enrichment)
        model = self.config.models.get("outline_enrichment", self.config.fallback_model)
        
        try:
            response = await self._invoke_llm(
                prompt=prompt,
                model=model,
                timeout=self.config.outline_enrichment_timeout_seconds,
            )
            
            # Parse JSON response
            result = self._parse_json_response(response)
            
            # Ensure result is a dictionary
            if not isinstance(result, dict):
                logger.warning(
                    "Parsed result is not a dictionary",
                    result_type=type(result).__name__,
                    result_preview=str(result)[:200]
                )
                result = {"raw_response": str(result)}
            
            result["llm_model_used"] = model
            return result
            
        except Exception as e:
            logger.error("Complete enrichment failed", error=str(e), title=title)
            return {
                "error": str(e),
                "llm_model_used": model,
                "original_outline": outline,
            }
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        Parse JSON from LLM response with multiple fallback strategies.
        
        Args:
            response: Raw LLM response
            
        Returns:
            Parsed dictionary
        """
        # Strategy 1: Try to find JSON block between ```json and ```
        json_block_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
        if json_block_match:
            json_text = json_block_match.group(1).strip()
            # Try parsing directly first (most JSON responses are already valid)
            try:
                return json.loads(json_text)
            except json.JSONDecodeError:
                # If direct parsing fails, try fixing common issues
                try:
                    json_text = self._fix_json_common_issues(json_text)
                    return json.loads(json_text)
                except json.JSONDecodeError as e:
                    logger.debug("Strategy 1 failed to parse JSON", error=str(e), json_preview=json_text[:200])
        
        # Strategy 2: Try to find JSON block between ``` and ```
        code_block_match = re.search(r"```\s*(.*?)\s*```", response, re.DOTALL)
        if code_block_match:
            json_text = code_block_match.group(1).strip()
            if json_text.startswith("json"):
                json_text = json_text[4:].strip()
            # Try parsing directly first
            try:
                return json.loads(json_text)
            except json.JSONDecodeError:
                # If direct parsing fails, try fixing common issues
                try:
                    json_text = self._fix_json_common_issues(json_text)
                    return json.loads(json_text)
                except json.JSONDecodeError as e:
                    logger.debug("Strategy 2 failed to parse JSON", error=str(e), json_preview=json_text[:200])
        
        # Strategy 3: Find first { and last } and extract
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            json_text = response[json_start:json_end]
            # Try parsing directly first
            try:
                return json.loads(json_text)
            except json.JSONDecodeError:
                # If direct parsing fails, try fixing common issues
                try:
                    json_text = self._fix_json_common_issues(json_text)
                    return json.loads(json_text)
                except json.JSONDecodeError as e:
                    logger.debug("Strategy 3 failed to parse JSON", error=str(e), json_preview=json_text[:200])
        
        # Strategy 4: Try parsing the whole response
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            try:
                json_text = self._fix_json_common_issues(response)
                return json.loads(json_text)
            except json.JSONDecodeError as e:
                logger.debug("Strategy 4 failed to parse JSON", error=str(e))
        
        # Strategy 5: Return raw response as fallback
        logger.warning(
            "Could not parse JSON response, returning raw text",
            response_preview=response[:200],
        )
        return {"raw_response": response}
    
    def _fix_json_common_issues(self, json_text: str) -> str:
        """
        Fix common JSON formatting issues (conservative approach).
        
        Args:
            json_text: JSON string with potential issues
            
        Returns:
            Fixed JSON string
        """
        # Remove leading/trailing whitespace
        json_text = json_text.strip()
        
        # Fix trailing commas before } or ]
        json_text = re.sub(r',\s*}', '}', json_text)
        json_text = re.sub(r',\s*]', ']', json_text)
        
        # Fix single quotes to double quotes for object keys only
        # More precise regex: only match 'key': not values
        json_text = re.sub(r"'([^']*)':\s*", r'"\1": ', json_text)
        
        # DON'T fix unquoted keys automatically - it breaks valid JSON
        # The regex r'(\w+):' is too aggressive and breaks values like "word: something"
        # Only fix if absolutely necessary with a more conservative approach
        # that only matches keys at the start of a line or after { or ,
        # For now, we skip this to avoid breaking valid JSON
        
        return json_text



