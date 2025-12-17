"""Service d'apprentissage pour améliorer la génération d'articles."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.crud_article_learning import (
    get_positive_examples,
    list_learning_data,
)
from python_scripts.utils.logging import get_logger


logger = get_logger(__name__)


@dataclass
class LearnedPattern:
    """Pattern appris pour améliorer la génération."""

    pattern_type: str  # "topic_keywords", "tone_combination", "prompt_structure", etc.
    pattern_data: Dict[str, Any]
    confidence: float  # 0.0 à 1.0
    examples_count: int


@dataclass
class PromptImprovement:
    """Amélioration de prompt basée sur les patterns."""

    original_prompt: str
    improved_prompt: str
    improvements: List[str]
    confidence: float


class ArticleLearningService:
    """Service d'apprentissage pour améliorer la génération d'articles."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def analyze_articles(
        self,
        *,
        site_profile_id: Optional[int] = None,
        min_global_score: float = 80.0,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Analyse les articles générés pour identifier les patterns de succès.

        Args:
            site_profile_id: Filtrer par profil de site
            min_global_score: Score global minimum pour considérer comme positif
            limit: Nombre maximum d'articles à analyser

        Returns:
            Dictionnaire avec les patterns identifiés
        """
        logger.info(
            "Starting article analysis",
            site_profile_id=site_profile_id,
            min_global_score=min_global_score,
        )

        # Récupérer les exemples positifs
        positive_examples = await get_positive_examples(
            self.db_session,
            site_profile_id=site_profile_id,
            min_global_score=min_global_score,
            limit=limit,
        )

        if not positive_examples:
            logger.warning("No positive examples found for analysis")
            return {
                "patterns": [],
                "total_analyzed": 0,
                "patterns_found": 0,
            }

        # Analyser les patterns
        patterns = await self._extract_patterns(positive_examples)

        logger.info(
            "Article analysis completed",
            total_analyzed=len(positive_examples),
            patterns_found=len(patterns),
        )

        return {
            "patterns": [self._pattern_to_dict(p) for p in patterns],
            "total_analyzed": len(positive_examples),
            "patterns_found": len(patterns),
        }

    async def _extract_patterns(
        self,
        examples: List[Any],
    ) -> List[LearnedPattern]:
        """Extrait les patterns des exemples positifs."""
        patterns: List[LearnedPattern] = []

        # Pattern 1: Combinaisons topic/keywords efficaces
        topic_keywords_pattern = self._analyze_topic_keywords_combinations(examples)
        if topic_keywords_pattern:
            patterns.append(topic_keywords_pattern)

        # Pattern 2: Tones efficaces par type de topic
        tone_pattern = self._analyze_tone_effectiveness(examples)
        if tone_pattern:
            patterns.append(tone_pattern)

        # Pattern 3: Structures de prompts efficaces
        prompt_structure_pattern = self._analyze_prompt_structures(examples)
        if prompt_structure_pattern:
            patterns.append(prompt_structure_pattern)

        # Pattern 4: Longueurs optimales
        length_pattern = self._analyze_optimal_lengths(examples)
        if length_pattern:
            patterns.append(length_pattern)

        return patterns

    def _analyze_topic_keywords_combinations(
        self,
        examples: List[Any],
    ) -> Optional[LearnedPattern]:
        """Analyse les combinaisons topic/keywords qui fonctionnent bien."""
        topic_keyword_pairs: List[tuple] = []

        for example in examples:
            params = example.generation_params
            topic = params.get("topic", "")
            keywords = params.get("keywords", [])

            if topic and keywords:
                # Normaliser le topic (premiers mots)
                topic_words = topic.lower().split()[:3]
                topic_keyword_pairs.append((tuple(topic_words), tuple(keywords)))

        if not topic_keyword_pairs:
            return None

        # Compter les combinaisons fréquentes
        counter = Counter(topic_keyword_pairs)
        most_common = counter.most_common(5)

        if most_common:
            pattern_data = {
                "common_combinations": [
                    {
                        "topic_words": list(combo[0]),
                        "keywords": list(combo[1]),
                        "frequency": count,
                    }
                    for combo, count in most_common
                ],
            }

            return LearnedPattern(
                pattern_type="topic_keywords",
                pattern_data=pattern_data,
                confidence=min(1.0, most_common[0][1] / len(examples)),
                examples_count=len(examples),
            )

        return None

    def _analyze_tone_effectiveness(
        self,
        examples: List[Any],
    ) -> Optional[LearnedPattern]:
        """Analyse l'efficacité des tones par type de topic."""
        tone_scores: Dict[str, List[float]] = {}

        for example in examples:
            params = example.generation_params
            tone = params.get("tone", "professional")

            # Extraire le score global
            score = self._extract_global_score(example.quality_scores)
            if score:
                if tone not in tone_scores:
                    tone_scores[tone] = []
                tone_scores[tone].append(score)

        if not tone_scores:
            return None

        # Calculer les scores moyens par tone
        tone_avg_scores = {
            tone: sum(scores) / len(scores)
            for tone, scores in tone_scores.items()
        }

        pattern_data = {
            "tone_effectiveness": tone_avg_scores,
            "best_tone": max(tone_avg_scores.items(), key=lambda x: x[1])[0],
        }

        return LearnedPattern(
            pattern_type="tone_effectiveness",
            pattern_data=pattern_data,
            confidence=0.7,  # Confiance moyenne
            examples_count=len(examples),
        )

    def _analyze_prompt_structures(
        self,
        examples: List[Any],
    ) -> Optional[LearnedPattern]:
        """Analyse les structures de prompts efficaces."""
        prompt_structures: List[str] = []

        for example in examples:
            prompt = example.prompt_used
            if prompt:
                # Identifier la structure (longueur, présence de sections, etc.)
                structure = self._identify_prompt_structure(prompt)
                prompt_structures.append(structure)

        if not prompt_structures:
            return None

        counter = Counter(prompt_structures)
        most_common = counter.most_common(3)

        pattern_data = {
            "common_structures": [
                {"structure": struct, "frequency": count}
                for struct, count in most_common
            ],
        }

        return LearnedPattern(
            pattern_type="prompt_structure",
            pattern_data=pattern_data,
            confidence=min(1.0, most_common[0][1] / len(examples)),
            examples_count=len(examples),
        )

    def _analyze_optimal_lengths(
        self,
        examples: List[Any],
    ) -> Optional[LearnedPattern]:
        """Analyse les longueurs optimales d'articles."""
        lengths: List[int] = []

        for example in examples:
            params = example.generation_params
            target_words = params.get("target_words", 2000)
            lengths.append(target_words)

        if not lengths:
            return None

        avg_length = sum(lengths) / len(lengths)
        min_length = min(lengths)
        max_length = max(lengths)

        pattern_data = {
            "average_target_words": round(avg_length),
            "min_target_words": min_length,
            "max_target_words": max_length,
            "optimal_range": [min_length, max_length],
        }

        return LearnedPattern(
            pattern_type="optimal_length",
            pattern_data=pattern_data,
            confidence=0.8,
            examples_count=len(examples),
        )

    def _extract_global_score(self, quality_scores: Dict[str, Any]) -> Optional[float]:
        """Extrait le score global des quality_scores."""
        try:
            if isinstance(quality_scores, dict):
                review = quality_scores.get("review", {})
                if isinstance(review, dict):
                    raw_review = review.get("raw_review", "")
                    # Chercher "global_score": X dans le texte JSON
                    match = re.search(r'"global_score":\s*(\d+)', raw_review)
                    if match:
                        return float(match.group(1))
        except Exception:
            pass
        return None

    def _identify_prompt_structure(self, prompt: str) -> str:
        """Identifie la structure d'un prompt."""
        # Analyse simple : longueur et présence de sections
        word_count = len(prompt.split())
        has_sections = ":" in prompt or "\n" in prompt

        if word_count < 50:
            return "short"
        elif word_count < 150:
            return "medium"
        else:
            return "long"

    def _pattern_to_dict(self, pattern: LearnedPattern) -> Dict[str, Any]:
        """Convertit un LearnedPattern en dictionnaire."""
        return {
            "pattern_type": pattern.pattern_type,
            "pattern_data": pattern.pattern_data,
            "confidence": pattern.confidence,
            "examples_count": pattern.examples_count,
        }

    async def improve_prompt(
        self,
        topic: str,
        keywords: List[str],
        tone: str,
        target_words: int,
        *,
        site_profile_id: Optional[int] = None,
    ) -> Optional[PromptImprovement]:
        """
        Améliore un prompt basé sur les patterns appris.

        Args:
            topic: Sujet de l'article
            keywords: Mots-clés
            tone: Ton souhaité
            target_words: Nombre de mots cible
            site_profile_id: ID du profil de site

        Returns:
            PromptImprovement si des améliorations sont disponibles
        """
        # Récupérer les patterns
        analysis = await self.analyze_articles(
            site_profile_id=site_profile_id,
            min_global_score=80.0,
            limit=50,
        )

        patterns = analysis.get("patterns", [])
        if not patterns:
            return None

        # Construire le prompt de base
        original_prompt = self._build_base_prompt(topic, keywords, tone, target_words)

        # Appliquer les améliorations basées sur les patterns
        improvements: List[str] = []
        improved_prompt = original_prompt

        for pattern in patterns:
            if pattern["pattern_type"] == "tone_effectiveness":
                best_tone = pattern["pattern_data"].get("best_tone")
                if best_tone and best_tone != tone:
                    improvements.append(f"Tone recommandé: {best_tone} (au lieu de {tone})")

            if pattern["pattern_type"] == "optimal_length":
                optimal = pattern["pattern_data"].get("average_target_words")
                if optimal and abs(optimal - target_words) > 500:
                    improvements.append(
                        f"Longueur recommandée: {optimal} mots (actuellement {target_words})"
                    )

        # Calculer la confiance (moyenne des confidences des patterns utilisés)
        confidence = (
            sum(p["confidence"] for p in patterns) / len(patterns)
            if patterns
            else 0.0
        )

        return PromptImprovement(
            original_prompt=original_prompt,
            improved_prompt=improved_prompt,  # Pour l'instant, pas de modification automatique
            improvements=improvements,
            confidence=confidence,
        )

    def _build_base_prompt(
        self,
        topic: str,
        keywords: List[str],
        tone: str,
        target_words: int,
    ) -> str:
        """Construit un prompt de base."""
        return f"Topic: {topic}\nKeywords: {', '.join(keywords)}\nTone: {tone}\nTarget words: {target_words}"

