"""Main LLM enricher (ETAGE 3)."""

import asyncio
import json
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from python_scripts.agents.trend_pipeline.llm_enrichment.config import LLMEnrichmentConfig
from python_scripts.agents.trend_pipeline.llm_enrichment.prompts import (
    TREND_SYNTHESIS_PROMPT,
    ANGLE_GENERATION_PROMPT,
    OUTLIER_ANALYSIS_PROMPT,
)
from python_scripts.agents.utils.llm_factory import create_llm
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


class LLMEnricher:
    """LLM-based trend enrichment and analysis."""
    
    def __init__(self, config: Optional[LLMEnrichmentConfig] = None):
        """
        Initialize the LLM enricher.
        
        Args:
            config: LLM enrichment configuration
        """
        self.config = config or LLMEnrichmentConfig.default()
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
    
    async def synthesize_trend(
        self,
        topic_label: str,
        keywords: List[str],
        volume: int,
        time_period: int,
        velocity: float,
        velocity_trend: str,
        source_diversity: int,
        representative_docs: List[str],
    ) -> Dict[str, Any]:
        """
        Generate trend synthesis using LLM.
        
        Args:
            topic_label: Topic label
            keywords: Top keywords
            volume: Number of articles
            time_period: Time period in days
            velocity: Velocity score
            velocity_trend: Velocity trend classification
            source_diversity: Number of unique sources
            representative_docs: Sample representative documents
            
        Returns:
            Synthesis results
        """
        # Prepare representative docs text
        docs_text = "\n".join([
            f"- {doc[:300]}..." if len(doc) > 300 else f"- {doc}"
            for doc in representative_docs[:3]
        ])
        
        # Format prompt
        prompt = TREND_SYNTHESIS_PROMPT.format(
            topic_label=topic_label,
            keywords=", ".join(keywords[:10]),
            volume=volume,
            time_period=time_period,
            velocity=f"{velocity:.2f}",
            velocity_trend=velocity_trend,
            source_diversity=source_diversity,
            representative_docs=docs_text,
        )
        
        # Get model
        model = self.config.models.get("trend_synthesis", self.config.fallback_model)
        
        try:
            response = await self._invoke_llm(
                prompt=prompt,
                model=model,
                timeout=self.config.synthesis_timeout_seconds,
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

            # CRITICAL: Validate required fields (fix for ANALYSE-PROBLEMES #2)
            # Ensure opportunities and saturated_angles exist
            if "synthesis" not in result or not result.get("synthesis"):
                logger.error(
                    "LLM response missing 'synthesis' field",
                    topic=topic_label,
                    result_keys=list(result.keys())
                )
                result["synthesis"] = f"Tendance sur {topic_label} avec {volume} articles."

            if "saturated_angles" not in result or result["saturated_angles"] is None:
                logger.warning(
                    "LLM response missing 'saturated_angles', setting to empty list",
                    topic=topic_label,
                    result_keys=list(result.keys()),
                    response_preview=response[:200]
                )
                result["saturated_angles"] = []

            if "opportunities" not in result or result["opportunities"] is None:
                logger.warning(
                    "LLM response missing 'opportunities', setting to empty list",
                    topic=topic_label,
                    result_keys=list(result.keys()),
                    response_preview=response[:200]
                )
                result["opportunities"] = []

            # Ensure they are lists, not strings
            if isinstance(result.get("saturated_angles"), str):
                result["saturated_angles"] = [result["saturated_angles"]]
            if isinstance(result.get("opportunities"), str):
                result["opportunities"] = [result["opportunities"]]

            result["llm_model_used"] = model
            return result

        except Exception as e:
            logger.error("Trend synthesis failed", error=str(e))
            return {
                "synthesis": f"Tendance sur {topic_label} avec {volume} articles.",
                "saturated_angles": [],
                "opportunities": [],
                "editorial_potential": "medium",
                "llm_model_used": model,
                "error": str(e),
            }
    
    async def generate_article_angles(
        self,
        topic_label: str,
        keywords: List[str],
        saturated_angles: List[str],
        opportunities: List[str],
        num_angles: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Generate article angle recommendations.
        
        Args:
            topic_label: Topic label
            keywords: Top keywords
            saturated_angles: Angles to avoid
            opportunities: Identified opportunities
            num_angles: Number of angles to generate
            
        Returns:
            List of article recommendations
        """
        # Format prompt
        prompt = ANGLE_GENERATION_PROMPT.format(
            topic_label=topic_label,
            keywords=", ".join(keywords[:10]),
            saturated_angles=", ".join(saturated_angles) if saturated_angles else "Aucun",
            opportunities="\n".join([f"- {o}" for o in opportunities]) if opportunities else "À définir",
            num_angles=min(num_angles, self.config.max_angles_per_topic),
        )
        
        # Get model
        model = self.config.models.get("angle_generation", self.config.fallback_model)
        
        try:
            response = await self._invoke_llm(
                prompt=prompt,
                model=model,
                timeout=self.config.angle_timeout_seconds,
            )
            
            # Parse JSON response
            result = self._parse_json_response(response)
            
            # Normalize articles to ensure it's a list of dicts
            articles = self._normalize_articles(result.get("articles", []))
            
            # Add model info to each article
            for article in articles:
                article["llm_model_used"] = model
            
            return articles
            
        except Exception as e:
            logger.error("Angle generation failed", error=str(e))
            return [{
                "title": f"Article sur {topic_label}",
                "hook": f"Découvrez les dernières tendances autour de {topic_label}.",
                "outline": ["Introduction", "Analyse", "Conclusion"],
                "effort_level": "medium",
                "differentiation_score": 0.5,
                "llm_model_used": model,
                "error": str(e),
            }]
    
    async def analyze_outliers(
        self,
        outliers: List[Dict[str, Any]],
        texts: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze outlier documents for weak signals.
        
        Args:
            outliers: List of outlier documents
            texts: Document texts
            
        Returns:
            Weak signal analysis
        """
        if not outliers:
            return {
                "common_thread": None,
                "is_weak_signal": False,
                "disruption_potential": 0,
                "recommendation": "wait",
            }
        
        # Prepare outlier summaries
        summaries = []
        for i, outlier in enumerate(outliers[:self.config.max_outlier_clusters_to_analyze]):
            metadata = outlier.get("metadata", {})
            title = metadata.get("title", f"Document {i+1}")
            
            # Get text if available
            text = ""
            if texts and outlier.get("index") is not None:
                idx = outlier["index"]
                if idx < len(texts):
                    text = texts[idx][:200] + "..." if len(texts[idx]) > 200 else texts[idx]
            
            summaries.append(f"**{title}**: {text}")
        
        # Format prompt
        prompt = OUTLIER_ANALYSIS_PROMPT.format(
            outlier_summaries="\n".join(summaries),
        )
        
        # Get model
        model = self.config.models.get("outlier_analysis", self.config.fallback_model)
        
        try:
            response = await self._invoke_llm(
                prompt=prompt,
                model=model,
                timeout=self.config.outlier_timeout_seconds,
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
            logger.error("Outlier analysis failed", error=str(e))
            return {
                "common_thread": None,
                "is_weak_signal": False,
                "disruption_potential": 0,
                "recommendation": "wait",
                "llm_model_used": model,
                "error": str(e),
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
            try:
                json_text = json_block_match.group(1).strip()
                json_text = self._fix_json_common_issues(json_text)
                return json.loads(json_text)
            except json.JSONDecodeError:
                pass
        
        # Strategy 2: Try to find JSON block between ``` and ```
        code_block_match = re.search(r"```\s*(.*?)\s*```", response, re.DOTALL)
        if code_block_match:
            try:
                json_text = code_block_match.group(1).strip()
                # Remove language identifier if present
                if json_text.startswith("json"):
                    json_text = json_text[4:].strip()
                json_text = self._fix_json_common_issues(json_text)
                return json.loads(json_text)
            except json.JSONDecodeError:
                pass
        
        # Strategy 3: Find first { and last } and extract
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            try:
                json_text = response[json_start:json_end]
                json_text = self._fix_json_common_issues(json_text)
                return json.loads(json_text)
            except json.JSONDecodeError:
                pass
        
        # Strategy 4: Try parsing the whole response
        try:
            json_text = self._fix_json_common_issues(response)
            return json.loads(json_text)
        except json.JSONDecodeError:
            pass
        
        # Strategy 5: Try to extract partial JSON (key-value pairs)
        try:
            return self._extract_partial_json(response)
        except Exception as e:
            logger.warning(
                "Could not parse JSON response, returning raw text",
                error=str(e),
                response_preview=response[:200],
            )
            return {"raw_response": response}
    
    def _fix_json_common_issues(self, json_text: str) -> str:
        """
        Fix common JSON formatting issues.
        
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
        
        # Fix single quotes to double quotes for object keys
        json_text = re.sub(r"'([^']*)':", r'"\1":', json_text)
        
        # Fix unquoted keys (word: -> "word":)
        json_text = re.sub(r'(\w+):', r'"\1":', json_text)
        
        # Note: We don't fix newlines in strings as they might be intentional
        # The JSON parser should handle them correctly if properly quoted
        
        return json_text
    
    def _extract_balanced_json(self, json_str: str, start_char: str) -> str:
        """
        Extract balanced JSON structure from a string.
        
        Args:
            json_str: JSON string (may be incomplete)
            start_char: Starting character ('[' for array, '{' for object)
            
        Returns:
            Balanced JSON string, or original if cannot balance
        """
        json_str = json_str.strip()
        
        if start_char == "[":
            # Extract array with balanced brackets
            bracket_count = 0
            in_string = False
            escape_next = False
            result = []
            
            for char in json_str:
                result.append(char)
                
                if escape_next:
                    escape_next = False
                    continue
                
                if char == "\\":
                    escape_next = True
                    continue
                
                if char == '"':
                    in_string = not in_string
                    continue
                
                if not in_string:
                    if char == "[":
                        bracket_count += 1
                    elif char == "]":
                        bracket_count -= 1
                        if bracket_count == 0:
                            return "".join(result)
        
        elif start_char == "{":
            # Extract object with balanced braces
            brace_count = 0
            in_string = False
            escape_next = False
            result = []
            
            for char in json_str:
                result.append(char)
                
                if escape_next:
                    escape_next = False
                    continue
                
                if char == "\\":
                    escape_next = True
                    continue
                
                if char == '"':
                    in_string = not in_string
                    continue
                
                if not in_string:
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            return "".join(result)
        
        # If not balanced, return as-is
        return json_str
    
    def _extract_partial_json(self, json_text: str) -> Dict[str, Any]:
        """
        Extract valid JSON parts even if full JSON is invalid.
        
        Args:
            json_text: Invalid JSON string
            
        Returns:
            Dictionary with extracted valid parts
        """
        result = {}
        
        # Strategy 1: Try to find complete JSON structures for common keys
        # Look for "articles": [...] pattern with balanced brackets
        articles_pattern = r'"articles"\s*:\s*(\[)'
        articles_match = re.search(articles_pattern, json_text, re.DOTALL)
        if articles_match:
            start_pos = articles_match.end() - 1  # Position of '['
            remaining = json_text[start_pos:]
            try:
                balanced_array = self._extract_balanced_json(remaining, "[")
                parsed = json.loads(balanced_array)
                if isinstance(parsed, list):
                    result["articles"] = parsed
                    # Remove this part from json_text to avoid double extraction
                    full_match = json_text[articles_match.start():articles_match.start() + len(balanced_array) + 1]
                    json_text = json_text.replace(full_match, "", 1)
            except (json.JSONDecodeError, ValueError) as e:
                logger.debug("Could not parse articles array", error=str(e))
        
        # Strategy 2: Try to extract key-value pairs
        # Match: "key": value (where value can be string, number, boolean, null, object, array)
        # Use a more flexible pattern that handles multi-line values
        pattern = r'"([^"]+)":\s*([^,}\]]+?)(?=\s*[,}\]])'
        matches = re.findall(pattern, json_text, re.DOTALL)
        
        for key, value in matches:
            # Skip if already extracted
            if key in result:
                continue
            
            value = value.strip()
            # Remove trailing commas
            value = value.rstrip(",").strip()
            
            # Try to parse value as JSON
            try:
                # Try as JSON first
                result[key] = json.loads(value)
            except (json.JSONDecodeError, ValueError):
                # If not valid JSON, try to parse as nested JSON string
                value_stripped = value.strip('"').strip("'")
                
                # Try to extract balanced JSON structures
                if value_stripped.startswith("["):
                    try:
                        balanced = self._extract_balanced_json(value_stripped, "[")
                        result[key] = json.loads(balanced)
                        continue
                    except (json.JSONDecodeError, ValueError):
                        pass
                elif value_stripped.startswith("{"):
                    try:
                        balanced = self._extract_balanced_json(value_stripped, "{")
                        result[key] = json.loads(balanced)
                        continue
                    except (json.JSONDecodeError, ValueError):
                        pass
                
                # If not valid JSON, try to infer type
                if value.lower() in ("true", "false"):
                    result[key] = value.lower() == "true"
                elif value.lower() == "null":
                    result[key] = None
                elif value.isdigit():
                    result[key] = int(value)
                elif re.match(r"^-?\d+\.\d+$", value):
                    result[key] = float(value)
                else:
                    # Remove quotes if present
                    value = value.strip('"').strip("'")
                    result[key] = value
        
        if not result:
            logger.warning("Could not extract any valid JSON parts")
            return {"raw_response": json_text}
        
        logger.info(
            "Extracted partial JSON",
            extracted_keys=list(result.keys()),
        )
        return result
    
    def _normalize_articles(self, articles: Any) -> List[Dict[str, Any]]:
        """
        Normalize articles to a list of dictionaries.
        
        Args:
            articles: Can be a list, a JSON string, or None
            
        Returns:
            List of article dictionaries
        """
        if articles is None:
            return []
        
        # If already a list, validate and normalize
        if isinstance(articles, list):
            normalized = []
            for article in articles:
                if isinstance(article, dict):
                    normalized.append(article)
                elif isinstance(article, str):
                    # Try to parse as JSON object
                    try:
                        article_dict = json.loads(article)
                        if isinstance(article_dict, dict):
                            normalized.append(article_dict)
                    except (json.JSONDecodeError, ValueError):
                        logger.warning(
                            "Could not parse article as JSON object",
                            article_preview=article[:100]
                        )
                else:
                    logger.warning(
                        "Article is not a dict or string",
                        article_type=type(article).__name__
                    )
            return normalized
        
        # If it's a string, try to parse as JSON array
        if isinstance(articles, str):
            articles_stripped = articles.strip()
            # Remove quotes if present
            if articles_stripped.startswith('"') and articles_stripped.endswith('"'):
                articles_stripped = articles_stripped[1:-1]
            
            # Try to parse as JSON array
            if articles_stripped.startswith("["):
                try:
                    # First try direct parsing
                    parsed = json.loads(articles_stripped)
                    if isinstance(parsed, list):
                        return self._normalize_articles(parsed)  # Recursive call
                except (json.JSONDecodeError, ValueError):
                    # If direct parsing fails, try to extract balanced JSON
                    try:
                        balanced = self._extract_balanced_json(articles_stripped, "[")
                        parsed = json.loads(balanced)
                        if isinstance(parsed, list):
                            return self._normalize_articles(parsed)  # Recursive call
                    except (json.JSONDecodeError, ValueError):
                        # Try to extract partial articles from truncated JSON
                        try:
                            # Find all complete JSON objects in the array
                            objects = []
                            i = 1  # Skip opening '['
                            while i < len(articles_stripped):
                                # Find next '{'
                                obj_start = articles_stripped.find("{", i)
                                if obj_start == -1:
                                    break
                                
                                # Extract balanced object
                                obj_str = articles_stripped[obj_start:]
                                balanced_obj = self._extract_balanced_json(obj_str, "{")
                                
                                try:
                                    obj = json.loads(balanced_obj)
                                    if isinstance(obj, dict):
                                        objects.append(obj)
                                    i = obj_start + len(balanced_obj)
                                except (json.JSONDecodeError, ValueError):
                                    i = obj_start + 1
                            
                            if objects:
                                return objects
                        except Exception:
                            pass
            
            # Try to parse as single JSON object (wrap in array)
            if articles_stripped.startswith("{"):
                try:
                    # First try direct parsing
                    parsed = json.loads(articles_stripped)
                    if isinstance(parsed, dict):
                        return [parsed]
                except (json.JSONDecodeError, ValueError):
                    # Try to extract balanced JSON
                    try:
                        balanced = self._extract_balanced_json(articles_stripped, "{")
                        parsed = json.loads(balanced)
                        if isinstance(parsed, dict):
                            return [parsed]
                    except (json.JSONDecodeError, ValueError):
                        pass
        
        logger.warning(
            "Could not normalize articles",
            articles_type=type(articles).__name__,
            articles_preview=str(articles)[:200] if not isinstance(articles, str) else articles[:200]
        )
        return []

