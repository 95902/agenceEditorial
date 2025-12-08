"""Main LLM enricher (ETAGE 3)."""

import asyncio
import json
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from python_scripts.analysis.llm_enrichment.config import LLMEnrichmentConfig
from python_scripts.analysis.llm_enrichment.prompts import (
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
            
            articles = result.get("articles", [])
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
        Parse JSON from LLM response.
        
        Args:
            response: Raw LLM response
            
        Returns:
            Parsed dictionary
        """
        try:
            # Try to find JSON in response
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            
            # Try parsing the whole response
            return json.loads(response)
            
        except json.JSONDecodeError:
            # Try to extract key-value pairs
            logger.warning("Could not parse JSON response, returning raw text")
            return {"raw_response": response}

