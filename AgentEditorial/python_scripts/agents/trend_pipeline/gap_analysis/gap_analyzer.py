"""Main gap analyzer (ETAGE 4)."""

from typing import Any, Dict, List, Optional

import numpy as np

from python_scripts.agents.trend_pipeline.gap_analysis.config import GapAnalysisConfig
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


class GapAnalyzer:
    """Analyze editorial gaps between client and competitors."""
    
    def __init__(self, config: Optional[GapAnalysisConfig] = None):
        """
        Initialize the gap analyzer.
        
        Args:
            config: Gap analysis configuration
        """
        self.config = config or GapAnalysisConfig.default()
    
    def analyze_coverage(
        self,
        client_domain: str,
        clusters: List[Dict[str, Any]],
        documents_by_topic: Dict[int, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """
        Analyze client coverage for each topic.
        
        Args:
            client_domain: Client domain to analyze
            clusters: List of topic clusters
            documents_by_topic: Documents grouped by topic
            
        Returns:
            Coverage analysis per topic
        """
        coverage_results = []
        
        for cluster in clusters:
            topic_id = cluster["topic_id"]
            documents = documents_by_topic.get(topic_id, [])
            
            if not documents:
                continue
            
            # Count client vs competitor articles
            client_count = 0
            competitor_count = 0
            domains = set()
            
            for doc in documents:
                domain = doc.get("domain", "")
                domains.add(domain)
                
                if domain == client_domain:
                    client_count += 1
                else:
                    competitor_count += 1
            
            total_count = len(documents)
            
            # Calculate coverage score
            if competitor_count > 0:
                # Ratio compared to average competitor
                num_competitors = len(domains) - (1 if client_domain in domains else 0)
                avg_competitor = competitor_count / num_competitors if num_competitors > 0 else competitor_count
                coverage_score = client_count / avg_competitor if avg_competitor > 0 else 0
            else:
                coverage_score = 1.0 if client_count > 0 else 0
            
            # Classify coverage level
            if coverage_score >= self.config.coverage_excellent_threshold:
                coverage_level = "excellent"
            elif coverage_score >= self.config.coverage_good_threshold:
                coverage_level = "good"
            elif coverage_score >= self.config.coverage_weak_threshold:
                coverage_level = "weak"
            else:
                coverage_level = "gap"
            
            coverage_results.append({
                "topic_id": topic_id,
                "topic_label": cluster.get("label", f"Topic_{topic_id}"),
                "client_count": client_count,
                "competitor_count": competitor_count,
                "total_count": total_count,
                "coverage_score": round(coverage_score, 4),
                "coverage_level": coverage_level,
                "num_sources": len(domains),
            })
        
        # Sort by coverage score (ascending = gaps first)
        coverage_results.sort(key=lambda x: x["coverage_score"])
        
        logger.info(
            "Analyzed coverage",
            topics=len(coverage_results),
            gaps=sum(1 for r in coverage_results if r["coverage_level"] == "gap"),
        )
        
        return coverage_results
    
    def identify_gaps(
        self,
        coverage_results: List[Dict[str, Any]],
        temporal_metrics: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Identify and prioritize editorial gaps.
        
        Args:
            coverage_results: Coverage analysis results
            temporal_metrics: Temporal metrics for prioritization
            
        Returns:
            Prioritized list of gaps
        """
        gaps = []
        
        # Build temporal lookup
        temporal_lookup = {}
        if temporal_metrics:
            for metrics in temporal_metrics:
                temporal_lookup[metrics["topic_id"]] = metrics
        
        for coverage in coverage_results:
            if coverage["coverage_level"] not in ["gap", "weak"]:
                continue
            
            topic_id = coverage["topic_id"]
            
            # Get temporal data
            temporal = temporal_lookup.get(topic_id, {})
            
            # Calculate priority score
            priority_score = self._calculate_priority_score(
                coverage=coverage,
                temporal=temporal,
            )
            
            # Generate diagnostic
            diagnostic = self._generate_diagnostic(coverage, temporal)
            
            # Generate opportunity description
            opportunity = self._generate_opportunity(coverage, temporal)
            
            # Risk assessment
            risk = self._assess_risk(coverage, temporal)
            
            gaps.append({
                "topic_id": topic_id,
                "topic_label": coverage["topic_label"],
                "coverage_score": coverage["coverage_score"],
                "priority_score": priority_score,
                "diagnostic": diagnostic,
                "opportunity_description": opportunity,
                "risk_assessment": risk,
                "temporal_metrics": temporal,
            })
        
        # Sort by priority (descending)
        gaps.sort(key=lambda x: x["priority_score"], reverse=True)
        
        logger.info(
            "Identified gaps",
            total=len(gaps),
            high_priority=sum(1 for g in gaps if g["priority_score"] > 0.7),
        )
        
        return gaps
    
    def identify_strengths(
        self,
        coverage_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Identify client strengths (topics where client outperforms).
        
        Args:
            coverage_results: Coverage analysis results
            
        Returns:
            List of client strengths
        """
        strengths = []
        
        for coverage in coverage_results:
            if coverage["coverage_score"] < self.config.strength_significant_threshold:
                continue
            
            advantage_score = coverage["coverage_score"] - 1.0  # Excess over parity
            
            strengths.append({
                "topic_id": coverage["topic_id"],
                "topic_label": coverage["topic_label"],
                "advantage_score": round(advantage_score, 4),
                "client_count": coverage["client_count"],
                "description": f"Position dominante sur {coverage['topic_label']} avec {coverage['client_count']} articles vs moyenne concurrents.",
            })
        
        # Sort by advantage score
        strengths.sort(key=lambda x: x["advantage_score"], reverse=True)
        
        return strengths
    
    def build_roadmap(
        self,
        gaps: List[Dict[str, Any]],
        recommendations: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Build prioritized content roadmap with diversified efforts.
        
        Args:
            gaps: Prioritized gaps
            recommendations: Article recommendations
            
        Returns:
            Content roadmap items with varied effort levels
        """
        roadmap = []
        distribution = self.config.priority_distribution
        
        # Get effort distribution config (default if not set)
        effort_distribution = getattr(self.config, "effort_distribution", {
            "easy": 0.30,
            "medium": 0.45,
            "complex": 0.25,
        })
        
        # Match recommendations to gaps - organize by effort level
        reco_by_topic = {}
        reco_by_effort = {"easy": [], "medium": [], "complex": []}
        
        for reco in recommendations:
            topic_id = reco.get("topic_cluster_id") or reco.get("topic_id")
            if topic_id not in reco_by_topic:
                reco_by_topic[topic_id] = []
            reco_by_topic[topic_id].append(reco)
            
            # Also track by effort level
            effort = reco.get("effort_level", "medium")
            if effort not in reco_by_effort:
                effort = "medium"
            reco_by_effort[effort].append(reco)
        
        priority_order = 1
        high_count = 0
        medium_count = 0
        low_count = 0
        
        # Track effort counts for diversification
        effort_counts = {"easy": 0, "medium": 0, "complex": 0}
        max_items = self.config.max_roadmap_items
        effort_targets = {
            "easy": int(max_items * effort_distribution.get("easy", 0.30)),
            "medium": int(max_items * effort_distribution.get("medium", 0.45)),
            "complex": int(max_items * effort_distribution.get("complex", 0.25)),
        }
        
        for gap in gaps:
            topic_id = gap["topic_id"]
            topic_recos = reco_by_topic.get(topic_id, [])
            
            if not topic_recos:
                continue
            
            # Determine priority tier
            if gap["priority_score"] >= 0.7 and high_count < distribution["high"]:
                priority_tier = "high"
                high_count += 1
            elif gap["priority_score"] >= 0.4 and medium_count < distribution["medium"]:
                priority_tier = "medium"
                medium_count += 1
            elif low_count < distribution["low"]:
                priority_tier = "low"
                low_count += 1
            else:
                continue
            
            # Select recommendation with effort diversification
            # Prioritize effort levels that are below target
            best_reco = self._select_reco_with_effort_balance(
                topic_recos,
                effort_counts,
                effort_targets,
            )
            
            effort = best_reco.get("effort_level", "medium")
            effort_counts[effort] = effort_counts.get(effort, 0) + 1
            
            roadmap.append({
                "priority_order": priority_order,
                "priority_tier": priority_tier,
                "gap_id": gap["topic_id"],
                "gap_label": gap["topic_label"],
                "recommendation_title": best_reco.get("title", ""),
                "recommendation_id": best_reco.get("id"),
                "estimated_effort": effort,
                "gap_priority_score": gap["priority_score"],
            })
            
            priority_order += 1
            
            if len(roadmap) >= self.config.max_roadmap_items:
                break
        
        logger.info(
            "Built roadmap",
            items=len(roadmap),
            high=high_count,
            medium=medium_count,
            low=low_count,
            effort_distribution=effort_counts,
        )
        
        return roadmap
    
    def _select_reco_with_effort_balance(
        self,
        recommendations: List[Dict[str, Any]],
        current_counts: Dict[str, int],
        targets: Dict[str, int],
    ) -> Dict[str, Any]:
        """
        Select a recommendation that helps balance effort distribution.
        
        Args:
            recommendations: Available recommendations for this topic
            current_counts: Current counts by effort level
            targets: Target counts by effort level
            
        Returns:
            Selected recommendation
        """
        if not recommendations:
            return {}
        
        # Group by effort level
        by_effort = {"easy": [], "medium": [], "complex": []}
        for reco in recommendations:
            effort = reco.get("effort_level", "medium")
            if effort not in by_effort:
                effort = "medium"
            by_effort[effort].append(reco)
        
        # Prioritize effort levels that are furthest below target
        effort_gaps = {}
        for effort, target in targets.items():
            current = current_counts.get(effort, 0)
            effort_gaps[effort] = target - current
        
        # Sort efforts by gap (descending - most needed first)
        sorted_efforts = sorted(effort_gaps.keys(), key=lambda e: effort_gaps[e], reverse=True)
        
        # Select from most needed effort level that has recommendations
        for effort in sorted_efforts:
            if by_effort.get(effort):
                return by_effort[effort][0]
        
        # Fallback: return first recommendation
        return recommendations[0]
    
    def _calculate_priority_score(
        self,
        coverage: Dict[str, Any],
        temporal: Dict[str, Any],
    ) -> float:
        """Calculate priority score for a gap."""
        weights = self.config.priority_weights
        
        # Coverage gap (inverse of coverage)
        coverage_gap_score = 1 - min(coverage["coverage_score"], 1.0)
        
        # Topic potential (from temporal)
        topic_potential = temporal.get("potential_score", 0.5)
        
        # Velocity (normalized)
        velocity = temporal.get("velocity", 1.0)
        velocity_score = min(velocity / 2.0, 1.0)  # Cap at 2x
        
        # Competitor presence (more competitors = more important)
        num_sources = coverage.get("num_sources", 1)
        competitor_score = min(num_sources / 10.0, 1.0)  # Cap at 10 sources
        
        # Effort estimate (we'll assume medium effort for now)
        effort_score = 0.5  # Will be refined with article recommendations
        
        # Weighted sum
        score = (
            weights["coverage_gap"] * coverage_gap_score +
            weights["topic_potential"] * topic_potential +
            weights["velocity"] * velocity_score +
            weights["competitor_presence"] * competitor_score +
            weights["effort_estimate"] * effort_score
        )
        
        return round(score, 4)
    
    def _generate_diagnostic(
        self,
        coverage: Dict[str, Any],
        temporal: Dict[str, Any],
    ) -> str:
        """Generate diagnostic text for a gap."""
        level = coverage["coverage_level"]
        label = coverage["topic_label"]
        client_count = coverage["client_count"]
        competitor_count = coverage["competitor_count"]
        
        velocity_trend = temporal.get("velocity_trend", "stable")
        
        if level == "gap":
            diagnostic = f"Gap critique sur '{label}': seulement {client_count} articles vs {competitor_count} chez les concurrents."
        else:  # weak
            diagnostic = f"Couverture faible sur '{label}': {client_count} articles vs {competitor_count} chez les concurrents."
        
        if velocity_trend == "accelerating":
            diagnostic += " Sujet en forte croissance."
        elif velocity_trend == "decelerating":
            diagnostic += " Sujet en déclin."
        
        return diagnostic
    
    def _generate_opportunity(
        self,
        coverage: Dict[str, Any],
        temporal: Dict[str, Any],
    ) -> str:
        """Generate opportunity description."""
        label = coverage["topic_label"]
        freshness = temporal.get("freshness_trend", "warm")
        
        if freshness == "hot":
            return f"Opportunité immédiate sur '{label}' - sujet très actuel, agir rapidement."
        elif freshness == "warm":
            return f"Opportunité de rattrapage sur '{label}' - construire une présence progressive."
        else:
            return f"Opportunité de fond sur '{label}' - contenu evergreen possible."
    
    def _assess_risk(
        self,
        coverage: Dict[str, Any],
        temporal: Dict[str, Any],
    ) -> str:
        """Assess risk of not addressing the gap."""
        coverage_score = coverage["coverage_score"]
        velocity = temporal.get("velocity", 1.0)
        num_sources = coverage.get("num_sources", 1)
        
        if coverage_score < 0.1 and velocity > 1.5 and num_sources >= 5:
            return "Risque élevé: gap critique sur un sujet en croissance, couvert par de nombreux concurrents."
        elif coverage_score < 0.3 and velocity > 1.0:
            return "Risque moyen: gap significatif sur un sujet dynamique."
        else:
            return "Risque faible: gap à surveiller, action non urgente."

