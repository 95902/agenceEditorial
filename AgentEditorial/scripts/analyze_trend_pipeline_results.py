#!/usr/bin/env python3
"""
Analyse complète des résultats du Trend Pipeline.

Ce script analyse la qualité et la performance des résultats d'une exécution
du Trend Pipeline en récupérant les données via les endpoints API.

Usage:
    python scripts/analyze_trend_pipeline_results.py <execution_id> [--api-url URL]

Exemple:
    python scripts/analyze_trend_pipeline_results.py a22ed0ac-a4bd-4bcb-b914-71d3b36af9a2
"""

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================
# Configuration des seuils de qualité
# ============================================================

@dataclass
class QualityThresholds:
    """Seuils de qualité pour l'évaluation."""
    
    # Clusters
    cluster_ratio_min: float = 0.005  # 0.5% des articles
    cluster_ratio_max: float = 0.02   # 2% des articles
    cluster_ratio_optimal: float = 0.01  # 1%
    cluster_size_min: int = 5
    cluster_size_max: int = 500
    coherence_good: float = 0.5
    outlier_ratio_max: float = 0.30
    
    # Temporal
    velocity_growth: float = 0.0  # > 0 = croissance
    freshness_good: float = 0.3
    freshness_excellent: float = 0.5
    source_diversity_min: int = 3
    potential_score_good: float = 0.5
    
    # LLM
    synthesis_coverage_min: float = 0.95  # 95% des clusters
    recommendations_per_cluster_min: int = 1
    recommendations_per_cluster_max: int = 3
    differentiation_score_good: float = 0.6
    synthesis_length_min: int = 50
    synthesis_length_max: int = 500
    
    # Gap Analysis
    coverage_gap_threshold: float = 0.2
    coverage_weak_threshold: float = 0.5
    coverage_excellent_threshold: float = 0.8
    priority_score_high: float = 0.7
    roadmap_items_min: int = 10
    roadmap_items_max: int = 20


# ============================================================
# Classes de données
# ============================================================

@dataclass
class AnalysisResult:
    """Résultat d'analyse d'une métrique."""
    name: str
    value: Any
    threshold: str
    status: str  # "excellent", "good", "warning", "critical"
    comment: str


@dataclass
class StageAnalysis:
    """Analyse d'un stage du pipeline."""
    stage_name: str
    status: str
    metrics: List[AnalysisResult] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class PipelineAnalysis:
    """Analyse complète du pipeline."""
    execution_id: str
    timestamp: str
    stages: Dict[str, StageAnalysis] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)
    raw_data: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# Récupération des données API
# ============================================================

async def fetch_pipeline_data(
    execution_id: str,
    api_url: str = "http://localhost:8000/api/v1",
) -> Dict[str, Any]:
    """Récupère toutes les données du pipeline via l'API."""
    
    endpoints = {
        "status": f"{api_url}/trend-pipeline/{execution_id}/status",
        "clusters": f"{api_url}/trend-pipeline/{execution_id}/clusters",
        "clusters_core": f"{api_url}/trend-pipeline/{execution_id}/clusters?scope=core&min_size=20",
        "gaps": f"{api_url}/trend-pipeline/{execution_id}/gaps",
        "gaps_core": f"{api_url}/trend-pipeline/{execution_id}/gaps?scope=core&top_n=10",
        "roadmap": f"{api_url}/trend-pipeline/{execution_id}/roadmap",
        "roadmap_quick_wins": f"{api_url}/trend-pipeline/{execution_id}/roadmap?scope=core&max_effort=medium",
        "llm_results": f"{api_url}/trend-pipeline/{execution_id}/llm-results",
        "llm_results_differentiated": f"{api_url}/trend-pipeline/{execution_id}/llm-results?scope=core&min_differentiation=0.7",
        "outliers": f"{api_url}/trend-pipeline/{execution_id}/outliers?limit=20",
    }
    
    data = {}
    errors = []
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        for name, url in endpoints.items():
            try:
                print(f"  Récupération {name}...")
                response = await client.get(url)
                
                if response.status_code == 200:
                    data[name] = response.json()
                    print(f"    ✓ {name}: OK")
                elif response.status_code == 404:
                    data[name] = None
                    errors.append(f"{name}: Non trouvé (404)")
                    print(f"    ✗ {name}: Non trouvé")
                else:
                    data[name] = None
                    errors.append(f"{name}: Erreur {response.status_code}")
                    print(f"    ✗ {name}: Erreur {response.status_code}")
                    
            except httpx.RequestError as e:
                data[name] = None
                errors.append(f"{name}: {str(e)}")
                print(f"    ✗ {name}: {str(e)}")
    
    data["_errors"] = errors
    return data


# ============================================================
# Analyse des Clusters (Stage 1)
# ============================================================

def analyze_clusters(
    data: Dict[str, Any],
    status_data: Dict[str, Any],
    thresholds: QualityThresholds,
) -> StageAnalysis:
    """Analyse la qualité des clusters."""
    
    stage = StageAnalysis(
        stage_name="Stage 1: Clustering BERTopic",
        status=status_data.get("stage_1_clustering_status", "unknown") if status_data else "unknown",
    )
    
    if not data:
        stage.issues.append("Aucune donnée de clusters disponible")
        return stage
    
    clusters = data.get("clusters", [])
    total_clusters = data.get("total", 0)
    total_articles = status_data.get("total_articles", 0) if status_data else 0
    total_outliers = status_data.get("total_outliers", 0) if status_data else 0
    
    # Métrique 1: Nombre de clusters
    stage.metrics.append(AnalysisResult(
        name="Nombre de clusters",
        value=total_clusters,
        threshold=f"Attendu: {max(1, int(total_articles * 0.005))}-{int(total_articles * 0.02)}",
        status="good" if total_clusters > 0 else "critical",
        comment=f"{total_clusters} clusters créés pour {total_articles} articles",
    ))
    
    # Métrique 2: Ratio clusters/articles
    if total_articles > 0:
        ratio = total_clusters / total_articles
        status = "excellent" if thresholds.cluster_ratio_min <= ratio <= thresholds.cluster_ratio_max else "warning"
        stage.metrics.append(AnalysisResult(
            name="Ratio clusters/articles",
            value=f"{ratio:.2%}",
            threshold=f"{thresholds.cluster_ratio_min:.1%} - {thresholds.cluster_ratio_max:.1%}",
            status=status,
            comment="Optimal" if status == "excellent" else "Ajuster min_cluster_size dans BERTopic",
        ))
    
    # Métrique 3: Distribution des tailles
    if clusters:
        sizes = [c.get("size", 0) for c in clusters]
        avg_size = sum(sizes) / len(sizes) if sizes else 0
        min_size = min(sizes) if sizes else 0
        max_size = max(sizes) if sizes else 0
        
        small_clusters = sum(1 for s in sizes if s < thresholds.cluster_size_min)
        large_clusters = sum(1 for s in sizes if s > thresholds.cluster_size_max)
        
        status = "excellent" if small_clusters == 0 and large_clusters == 0 else "warning"
        stage.metrics.append(AnalysisResult(
            name="Distribution tailles",
            value=f"min={min_size}, avg={avg_size:.1f}, max={max_size}",
            threshold=f"{thresholds.cluster_size_min}-{thresholds.cluster_size_max}",
            status=status,
            comment=f"{small_clusters} petits (<{thresholds.cluster_size_min}), {large_clusters} grands (>{thresholds.cluster_size_max})",
        ))
        
        if small_clusters > 0:
            stage.issues.append(f"{small_clusters} clusters trop petits (< {thresholds.cluster_size_min} articles)")
            stage.suggestions.append("Augmenter min_cluster_size dans la config BERTopic")
    
    # Métrique 4: Scores de cohérence
    coherence_scores = [c.get("coherence_score") for c in clusters if c.get("coherence_score") is not None]
    if coherence_scores:
        avg_coherence = sum(coherence_scores) / len(coherence_scores)
        status = "excellent" if avg_coherence >= thresholds.coherence_good else "warning"
        stage.metrics.append(AnalysisResult(
            name="Cohérence moyenne",
            value=f"{avg_coherence:.3f}",
            threshold=f">= {thresholds.coherence_good}",
            status=status,
            comment="Bonne cohérence thématique" if status == "excellent" else "Cohérence faible",
        ))
    else:
        stage.metrics.append(AnalysisResult(
            name="Cohérence moyenne",
            value="N/A",
            threshold=f">= {thresholds.coherence_good}",
            status="warning",
            comment="Scores de cohérence non calculés",
        ))
    
    # Métrique 5: Ratio outliers
    if total_articles > 0:
        outlier_ratio = total_outliers / total_articles
        status = "excellent" if outlier_ratio <= thresholds.outlier_ratio_max else "warning"
        stage.metrics.append(AnalysisResult(
            name="Ratio outliers",
            value=f"{outlier_ratio:.1%} ({total_outliers} articles)",
            threshold=f"<= {thresholds.outlier_ratio_max:.0%}",
            status=status,
            comment="Acceptable" if status == "excellent" else "Trop d'articles non classifiés",
        ))
        
        if outlier_ratio > thresholds.outlier_ratio_max:
            stage.issues.append(f"Trop d'outliers: {outlier_ratio:.1%}")
            stage.suggestions.append("Réduire min_cluster_size ou ajuster les paramètres HDBSCAN")
    
    # Métrique 6: Qualité des labels
    if clusters:
        labels = [c.get("label", "") for c in clusters]
        avg_label_len = sum(len(l) for l in labels) / len(labels)
        empty_labels = sum(1 for l in labels if not l or l == "-1" or l.startswith("Topic"))
        
        status = "excellent" if empty_labels == 0 and avg_label_len > 10 else "warning"
        stage.metrics.append(AnalysisResult(
            name="Qualité labels",
            value=f"Longueur moy: {avg_label_len:.1f}, vides: {empty_labels}",
            threshold="Labels descriptifs, longueur > 10",
            status=status,
            comment="Labels descriptifs" if status == "excellent" else f"{empty_labels} labels non informatifs",
        ))
    
    return stage


# ============================================================
# Analyse des Gaps (Stage 4)
# ============================================================

def analyze_gaps(
    data: Dict[str, Any],
    status_data: Dict[str, Any],
    thresholds: QualityThresholds,
) -> StageAnalysis:
    """Analyse la qualité de l'analyse de gaps."""
    
    stage = StageAnalysis(
        stage_name="Stage 4: Gap Analysis",
        status=status_data.get("stage_4_gap_status", "unknown") if status_data else "unknown",
    )
    
    if not data:
        stage.issues.append("Aucune donnée de gaps disponible")
        return stage
    
    gaps = data.get("gaps", [])
    total_gaps = data.get("total", 0)
    
    # Métrique 1: Nombre de gaps
    status = "good" if total_gaps > 0 else "warning"
    stage.metrics.append(AnalysisResult(
        name="Gaps identifiés",
        value=total_gaps,
        threshold="> 0 (si client_domain fourni)",
        status=status,
        comment=f"{total_gaps} opportunités de contenu identifiées" if total_gaps > 0 else "Aucun gap détecté",
    ))
    
    if not gaps:
        stage.issues.append("Aucun gap éditorial identifié")
        stage.suggestions.append("Vérifier que client_domain est correctement configuré")
        return stage
    
    # Métrique 2: Distribution des coverage scores
    coverage_scores = [g.get("coverage_score", 0) for g in gaps]
    avg_coverage = sum(coverage_scores) / len(coverage_scores) if coverage_scores else 0
    
    gap_count = sum(1 for s in coverage_scores if s < thresholds.coverage_gap_threshold)
    weak_count = sum(1 for s in coverage_scores if thresholds.coverage_gap_threshold <= s < thresholds.coverage_weak_threshold)
    
    stage.metrics.append(AnalysisResult(
        name="Coverage moyen",
        value=f"{avg_coverage:.2f}",
        threshold=f"Gap: <{thresholds.coverage_gap_threshold}, Weak: <{thresholds.coverage_weak_threshold}",
        status="good",
        comment=f"{gap_count} gaps critiques, {weak_count} couverture faible",
    ))
    
    # Métrique 3: Distribution des priority scores
    priority_scores = [g.get("priority_score", 0) for g in gaps]
    avg_priority = sum(priority_scores) / len(priority_scores) if priority_scores else 0
    high_priority = sum(1 for s in priority_scores if s >= thresholds.priority_score_high)
    
    status = "excellent" if high_priority > 0 else "good"
    stage.metrics.append(AnalysisResult(
        name="Priority score moyen",
        value=f"{avg_priority:.2f}",
        threshold=f"High: >= {thresholds.priority_score_high}",
        status=status,
        comment=f"{high_priority} gaps haute priorité",
    ))
    
    # Métrique 4: Qualité des diagnostics
    diagnostics = [g.get("diagnostic", "") for g in gaps]
    avg_diag_len = sum(len(d) for d in diagnostics) / len(diagnostics) if diagnostics else 0
    empty_diag = sum(1 for d in diagnostics if not d)
    
    status = "excellent" if empty_diag == 0 and avg_diag_len > 50 else "warning"
    stage.metrics.append(AnalysisResult(
        name="Qualité diagnostics",
        value=f"Longueur moy: {avg_diag_len:.0f} chars",
        threshold="Diagnostics détaillés et actionnables",
        status=status,
        comment="Diagnostics détaillés" if status == "excellent" else f"{empty_diag} diagnostics vides",
    ))
    
    # Top 5 gaps par priorité
    top_gaps = sorted(gaps, key=lambda x: x.get("priority_score", 0), reverse=True)[:5]
    stage.metrics.append(AnalysisResult(
        name="Top 5 gaps",
        value="\n".join([f"  - {g.get('topic_label', 'N/A')}: {g.get('priority_score', 0):.2f}" for g in top_gaps]),
        threshold="N/A",
        status="info",
        comment="Gaps prioritaires à adresser",
    ))
    
    return stage


# ============================================================
# Analyse des résultats LLM (Stage 3)
# ============================================================

def analyze_llm_results(
    data: Dict[str, Any],
    status_data: Dict[str, Any],
    clusters_data: Dict[str, Any],
    thresholds: QualityThresholds,
) -> StageAnalysis:
    """Analyse la qualité des résultats LLM."""
    
    stage = StageAnalysis(
        stage_name="Stage 3: LLM Enrichment",
        status=status_data.get("stage_3_llm_status", "unknown") if status_data else "unknown",
    )
    
    if not data:
        stage.issues.append("Aucune donnée LLM disponible")
        return stage
    
    syntheses = data.get("syntheses", [])
    recommendations = data.get("recommendations", [])
    total_syntheses = data.get("total_syntheses", 0)
    total_recommendations = data.get("total_recommendations", 0)
    total_clusters = clusters_data.get("total", 0) if clusters_data else 0
    
    # Métrique 1: Couverture des synthèses
    if total_clusters > 0:
        coverage = total_syntheses / total_clusters
        status = "excellent" if coverage >= thresholds.synthesis_coverage_min else "warning"
        stage.metrics.append(AnalysisResult(
            name="Couverture synthèses",
            value=f"{coverage:.1%} ({total_syntheses}/{total_clusters})",
            threshold=f">= {thresholds.synthesis_coverage_min:.0%}",
            status=status,
            comment="Tous les clusters analysés" if coverage >= 1 else f"{total_clusters - total_syntheses} clusters sans synthèse",
        ))
        
        if coverage < thresholds.synthesis_coverage_min:
            stage.issues.append(f"Synthèses manquantes pour {total_clusters - total_syntheses} clusters")
    else:
        stage.metrics.append(AnalysisResult(
            name="Couverture synthèses",
            value=f"{total_syntheses}",
            threshold="N/A",
            status="warning",
            comment="Pas de données clusters pour comparaison",
        ))
    
    # Métrique 2: Qualité des synthèses
    if syntheses:
        synthesis_texts = [s.get("synthesis", "") for s in syntheses]
        avg_length = sum(len(t.split()) for t in synthesis_texts) / len(synthesis_texts)
        
        status = "excellent" if thresholds.synthesis_length_min <= avg_length <= thresholds.synthesis_length_max else "warning"
        stage.metrics.append(AnalysisResult(
            name="Longueur synthèses",
            value=f"{avg_length:.0f} mots (moyenne)",
            threshold=f"{thresholds.synthesis_length_min}-{thresholds.synthesis_length_max} mots",
            status=status,
            comment="Longueur optimale" if status == "excellent" else "Ajuster les prompts LLM",
        ))
        
        # Opportunités identifiées
        opportunities_counts = [len(s.get("opportunities", []) or []) for s in syntheses]
        avg_opportunities = sum(opportunities_counts) / len(opportunities_counts) if opportunities_counts else 0
        
        stage.metrics.append(AnalysisResult(
            name="Opportunités/synthèse",
            value=f"{avg_opportunities:.1f} (moyenne)",
            threshold=">= 1",
            status="excellent" if avg_opportunities >= 1 else "warning",
            comment=f"Total: {sum(opportunities_counts)} opportunités",
        ))
    
    # Métrique 3: Recommandations d'articles
    stage.metrics.append(AnalysisResult(
        name="Recommandations",
        value=total_recommendations,
        threshold=f"{thresholds.recommendations_per_cluster_min}-{thresholds.recommendations_per_cluster_max} par cluster",
        status="good" if total_recommendations > 0 else "warning",
        comment=f"{total_recommendations} articles recommandés",
    ))
    
    if total_clusters > 0:
        reco_per_cluster = total_recommendations / total_clusters
        status = "excellent" if thresholds.recommendations_per_cluster_min <= reco_per_cluster <= thresholds.recommendations_per_cluster_max else "warning"
        stage.metrics.append(AnalysisResult(
            name="Ratio recos/cluster",
            value=f"{reco_per_cluster:.1f}",
            threshold=f"{thresholds.recommendations_per_cluster_min}-{thresholds.recommendations_per_cluster_max}",
            status=status,
            comment="Ratio optimal" if status == "excellent" else "Ajuster le nombre de recommandations par topic",
        ))
    
    # Métrique 4: Distribution effort levels
    if recommendations:
        effort_counts = {}
        for r in recommendations:
            effort = r.get("effort_level", "unknown")
            effort_counts[effort] = effort_counts.get(effort, 0) + 1
        
        effort_dist = ", ".join([f"{k}: {v}" for k, v in sorted(effort_counts.items())])
        stage.metrics.append(AnalysisResult(
            name="Distribution effort",
            value=effort_dist,
            threshold="Équilibré (easy/medium/complex)",
            status="good",
            comment="Mix d'efforts variés" if len(effort_counts) > 1 else "Tous le même niveau",
        ))
        
        # Differentiation scores
        diff_scores = [r.get("differentiation_score") for r in recommendations if r.get("differentiation_score") is not None]
        if diff_scores:
            avg_diff = sum(diff_scores) / len(diff_scores)
            status = "excellent" if avg_diff >= thresholds.differentiation_score_good else "warning"
            stage.metrics.append(AnalysisResult(
                name="Score différenciation",
                value=f"{avg_diff:.2f} (moyenne)",
                threshold=f">= {thresholds.differentiation_score_good}",
                status=status,
                comment="Bonne différenciation" if status == "excellent" else "Recommandations peu différenciées",
            ))
    
    return stage


# ============================================================
# Analyse de la Roadmap
# ============================================================

def analyze_roadmap(
    data: Dict[str, Any],
    thresholds: QualityThresholds,
) -> StageAnalysis:
    """Analyse la qualité de la roadmap."""
    
    stage = StageAnalysis(
        stage_name="Roadmap de contenu",
        status="completed" if data else "unknown",
    )
    
    if not data:
        stage.issues.append("Aucune donnée de roadmap disponible")
        return stage
    
    roadmap = data.get("roadmap", [])
    total = data.get("total", 0)
    
    # Métrique 1: Nombre d'items
    status = "excellent" if thresholds.roadmap_items_min <= total <= thresholds.roadmap_items_max else "warning"
    stage.metrics.append(AnalysisResult(
        name="Items roadmap",
        value=total,
        threshold=f"{thresholds.roadmap_items_min}-{thresholds.roadmap_items_max}",
        status=status,
        comment="Taille optimale" if status == "excellent" else "Ajuster max_roadmap_items",
    ))
    
    if not roadmap:
        stage.issues.append("Roadmap vide")
        return stage
    
    # Métrique 2: Distribution des priorités
    priority_counts = {}
    for item in roadmap:
        tier = item.get("priority_tier", "unknown")
        priority_counts[tier] = priority_counts.get(tier, 0) + 1
    
    priority_dist = ", ".join([f"{k}: {v}" for k, v in sorted(priority_counts.items())])
    stage.metrics.append(AnalysisResult(
        name="Distribution priorités",
        value=priority_dist,
        threshold="high: 5, medium: 10, low: 5",
        status="good",
        comment="Distribution des priorités",
    ))
    
    # Métrique 3: Distribution des efforts
    effort_counts = {}
    for item in roadmap:
        effort = item.get("estimated_effort", "unknown")
        effort_counts[effort] = effort_counts.get(effort, 0) + 1
    
    effort_dist = ", ".join([f"{k}: {v}" for k, v in sorted(effort_counts.items())])
    stage.metrics.append(AnalysisResult(
        name="Distribution efforts",
        value=effort_dist,
        threshold="Équilibré",
        status="good",
        comment="Variété des niveaux d'effort",
    ))
    
    # Top 5 items
    top_items = roadmap[:5]
    stage.metrics.append(AnalysisResult(
        name="Top 5 priorités",
        value="\n".join([f"  {i+1}. {item.get('recommendation_title', 'N/A')[:50]}..." for i, item in enumerate(top_items)]),
        threshold="N/A",
        status="info",
        comment="Actions prioritaires",
    ))
    
    return stage


# ============================================================
# Analyse de Performance
# ============================================================

def analyze_performance(
    status_data: Dict[str, Any],
) -> StageAnalysis:
    """Analyse les performances du pipeline."""
    
    stage = StageAnalysis(
        stage_name="Performance globale",
        status="completed",
    )
    
    if not status_data:
        stage.issues.append("Aucune donnée de status disponible")
        return stage
    
    # Durée totale
    duration = status_data.get("duration_seconds")
    if duration:
        minutes = duration // 60
        seconds = duration % 60
        stage.metrics.append(AnalysisResult(
            name="Durée totale",
            value=f"{minutes}m {seconds}s ({duration}s)",
            threshold="< 10 minutes pour < 1000 articles",
            status="good" if duration < 600 else "warning",
            comment="Temps d'exécution",
        ))
    
    # Articles analysés
    total_articles = status_data.get("total_articles", 0)
    stage.metrics.append(AnalysisResult(
        name="Articles analysés",
        value=total_articles,
        threshold="Volume traité",
        status="good" if total_articles > 0 else "warning",
        comment=f"{total_articles} articles traités",
    ))
    
    # Throughput
    if duration and total_articles:
        throughput = total_articles / (duration / 60)  # articles/minute
        stage.metrics.append(AnalysisResult(
            name="Throughput",
            value=f"{throughput:.1f} articles/min",
            threshold="> 100 articles/min",
            status="excellent" if throughput > 100 else "good",
            comment="Vitesse de traitement",
        ))
    
    # Status des stages
    stages_status = {
        "Clustering": status_data.get("stage_1_clustering_status", "unknown"),
        "Temporal": status_data.get("stage_2_temporal_status", "unknown"),
        "LLM": status_data.get("stage_3_llm_status", "unknown"),
        "Gap Analysis": status_data.get("stage_4_gap_status", "unknown"),
    }
    
    completed = sum(1 for s in stages_status.values() if s == "completed")
    status_summary = ", ".join([f"{k}: {v}" for k, v in stages_status.items()])
    
    stage.metrics.append(AnalysisResult(
        name="Status des stages",
        value=f"{completed}/4 complétés",
        threshold="4/4 completed",
        status="excellent" if completed == 4 else "warning",
        comment=status_summary,
    ))
    
    # Totaux
    stage.metrics.append(AnalysisResult(
        name="Clusters créés",
        value=status_data.get("total_clusters", 0),
        threshold="N/A",
        status="info",
        comment="Résultat Stage 1",
    ))
    
    stage.metrics.append(AnalysisResult(
        name="Outliers",
        value=status_data.get("total_outliers", 0),
        threshold="< 30% des articles",
        status="info",
        comment="Articles non classifiés",
    ))
    
    stage.metrics.append(AnalysisResult(
        name="Gaps identifiés",
        value=status_data.get("total_gaps", 0),
        threshold="> 0",
        status="info",
        comment="Résultat Stage 4",
    ))
    
    return stage


# ============================================================
# Génération du rapport
# ============================================================

def generate_comparison_table(analysis: PipelineAnalysis) -> str:
    """Génère le tableau comparatif en markdown."""
    
    lines = [
        "## Tableau comparatif des métriques",
        "",
        "| Métrique | Valeur | Seuil optimal | Status | Commentaire |",
        "|----------|--------|---------------|--------|-------------|",
    ]
    
    status_emoji = {
        "excellent": "🟢",
        "good": "🟢",
        "warning": "🟡",
        "critical": "🔴",
        "info": "ℹ️",
    }
    
    for stage_name, stage in analysis.stages.items():
        lines.append(f"| **{stage.stage_name}** | | | | |")
        for metric in stage.metrics:
            # Truncate long values
            value = str(metric.value)
            if "\n" in value:
                value = value.split("\n")[0] + "..."
            if len(value) > 50:
                value = value[:47] + "..."
            
            emoji = status_emoji.get(metric.status, "")
            lines.append(
                f"| {metric.name} | {value} | {metric.threshold} | {emoji} {metric.status} | {metric.comment[:40]}{'...' if len(metric.comment) > 40 else ''} |"
            )
    
    return "\n".join(lines)


def generate_suggestions(analysis: PipelineAnalysis) -> str:
    """Génère les suggestions d'amélioration."""
    
    lines = [
        "## Suggestions d'amélioration",
        "",
    ]
    
    all_issues = []
    all_suggestions = []
    
    for stage_name, stage in analysis.stages.items():
        if stage.issues:
            all_issues.extend([(stage.stage_name, issue) for issue in stage.issues])
        if stage.suggestions:
            all_suggestions.extend([(stage.stage_name, sugg) for sugg in stage.suggestions])
    
    if all_issues:
        lines.append("### Problèmes détectés")
        lines.append("")
        for stage_name, issue in all_issues:
            lines.append(f"- **{stage_name}**: {issue}")
        lines.append("")
    
    if all_suggestions:
        lines.append("### Recommandations")
        lines.append("")
        for stage_name, sugg in all_suggestions:
            lines.append(f"- **{stage_name}**: {sugg}")
        lines.append("")
    
    if not all_issues and not all_suggestions:
        lines.append("✅ Aucun problème majeur détecté. Le pipeline fonctionne correctement.")
        lines.append("")
    
    # Suggestions générales basées sur les métriques
    lines.append("### Optimisations possibles")
    lines.append("")
    lines.append("1. **Clustering** : Ajuster `min_cluster_size` et `min_samples` dans BERTopic pour optimiser le ratio clusters/articles")
    lines.append("2. **Temporal** : Réduire `time_window_days` pour des analyses plus récentes et pertinentes")
    lines.append("3. **LLM** : Utiliser un modèle plus performant (llama3:70b) pour des synthèses de meilleure qualité")
    lines.append("4. **Gap Analysis** : Ajuster les seuils de coverage dans `GapAnalysisConfig` selon votre secteur")
    
    return "\n".join(lines)


def generate_report(analysis: PipelineAnalysis) -> str:
    """Génère le rapport complet en markdown."""
    
    lines = [
        f"# Rapport d'analyse - Trend Pipeline",
        "",
        f"**Execution ID**: `{analysis.execution_id}`",
        f"**Date d'analyse**: {analysis.timestamp}",
        "",
        "---",
        "",
        "## Résumé exécutif",
        "",
    ]
    
    # Summary
    status_data = analysis.raw_data.get("status", {})
    if status_data:
        lines.extend([
            f"- **Articles analysés**: {status_data.get('total_articles', 'N/A')}",
            f"- **Clusters créés**: {status_data.get('total_clusters', 'N/A')}",
            f"- **Outliers**: {status_data.get('total_outliers', 'N/A')}",
            f"- **Gaps identifiés**: {status_data.get('total_gaps', 'N/A')}",
            f"- **Durée**: {status_data.get('duration_seconds', 'N/A')} secondes",
            "",
        ])
    
    # Topic distribution by scope
    clusters_data = analysis.raw_data.get("clusters", {})
    if clusters_data:
        from python_scripts.analysis.article_enrichment.topic_filters import get_scope_distribution
        clusters = clusters_data.get("clusters", [])
        scope_dist = get_scope_distribution([{"topic_label": c.get("label", "")} for c in clusters])
        lines.extend([
            "### Distribution par scope",
            "",
            f"- **Core** (topics cœur Innosys): {scope_dist.get('core', 0)}",
            f"- **Adjacent** (topics intéressants): {scope_dist.get('adjacent', 0)}",
            f"- **Off-scope** (hors-sujet / faible priorité): {scope_dist.get('off_scope', 0)}",
            "",
        ])
    
    # Major core topics
    clusters_core_data = analysis.raw_data.get("clusters_core", {})
    if clusters_core_data:
        lines.extend([
            "### Topics majeurs (core, ≥20 articles)",
            "",
            f"Nombre: {clusters_core_data.get('total', 0)}",
            "",
        ])
    
    # Outliers
    outliers_data = analysis.raw_data.get("outliers", {})
    if outliers_data:
        outliers = outliers_data.get("outliers", [])
        lines.extend([
            "### Articles hors-sujet (outliers)",
            "",
            f"Total: {outliers_data.get('total', 0)} articles non assignés à un cluster",
            "",
            "Top 5 outliers (les plus distants):",
            "",
        ])
        for i, outlier in enumerate(outliers[:5], 1):
            title = outlier.get("title", "N/A")[:60]
            domain = outlier.get("domain", "N/A")
            distance = outlier.get("embedding_distance", 0)
            lines.append(f"{i}. **{title}** - {domain} (distance: {distance:.3f})")
        lines.append("")
    
    # Stages summary
    lines.append("### Status des stages")
    lines.append("")
    for stage_name, stage in analysis.stages.items():
        status_emoji = "✅" if stage.status == "completed" else "⚠️" if stage.status == "pending" else "❌"
        lines.append(f"- {status_emoji} {stage.stage_name}: {stage.status}")
    lines.append("")
    
    lines.append("---")
    lines.append("")
    
    # Comparison table
    lines.append(generate_comparison_table(analysis))
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # Detailed analysis
    lines.append("## Analyse détaillée par stage")
    lines.append("")
    
    for stage_name, stage in analysis.stages.items():
        lines.append(f"### {stage.stage_name}")
        lines.append("")
        lines.append(f"**Status**: {stage.status}")
        lines.append("")
        
        if stage.metrics:
            for metric in stage.metrics:
                if "\n" in str(metric.value):
                    lines.append(f"**{metric.name}**:")
                    lines.append(f"```")
                    lines.append(str(metric.value))
                    lines.append(f"```")
                else:
                    lines.append(f"- **{metric.name}**: {metric.value}")
            lines.append("")
        
        if stage.issues:
            lines.append("**Problèmes**:")
            for issue in stage.issues:
                lines.append(f"- ⚠️ {issue}")
            lines.append("")
    
    lines.append("---")
    lines.append("")
    
    # Suggestions
    lines.append(generate_suggestions(analysis))
    
    return "\n".join(lines)


# ============================================================
# Main
# ============================================================

async def analyze_pipeline(
    execution_id: str,
    api_url: str = "http://localhost:8000/api/v1",
) -> PipelineAnalysis:
    """Analyse complète du pipeline."""
    
    print(f"\n📊 Analyse du Trend Pipeline")
    print(f"   Execution ID: {execution_id}")
    print(f"   API URL: {api_url}")
    print("")
    
    # Fetch data
    print("1. Récupération des données...")
    data = await fetch_pipeline_data(execution_id, api_url)
    
    if data.get("_errors"):
        print(f"\n⚠️ Erreurs lors de la récupération:")
        for error in data["_errors"]:
            print(f"   - {error}")
    
    # Create analysis
    thresholds = QualityThresholds()
    analysis = PipelineAnalysis(
        execution_id=execution_id,
        timestamp=datetime.now().isoformat(),
        raw_data=data,
    )
    
    print("\n2. Analyse des résultats...")
    
    # Analyze each stage
    analysis.stages["performance"] = analyze_performance(data.get("status"))
    analysis.stages["clusters"] = analyze_clusters(
        data.get("clusters"),
        data.get("status"),
        thresholds,
    )
    analysis.stages["llm"] = analyze_llm_results(
        data.get("llm_results"),
        data.get("status"),
        data.get("clusters"),
        thresholds,
    )
    analysis.stages["gaps"] = analyze_gaps(
        data.get("gaps"),
        data.get("status"),
        thresholds,
    )
    analysis.stages["roadmap"] = analyze_roadmap(
        data.get("roadmap"),
        thresholds,
    )
    
    return analysis


async def main():
    """Point d'entrée principal."""
    
    parser = argparse.ArgumentParser(
        description="Analyse les résultats d'une exécution du Trend Pipeline"
    )
    parser.add_argument(
        "execution_id",
        help="ID de l'exécution à analyser",
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000/api/v1",
        help="URL de base de l'API (default: http://localhost:8000/api/v1)",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/analysis",
        help="Répertoire de sortie (default: outputs/analysis)",
    )
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Run analysis
    analysis = await analyze_pipeline(args.execution_id, args.api_url)
    
    # Generate report
    print("\n3. Génération du rapport...")
    report = generate_report(analysis)
    
    # Save report
    report_path = output_dir / f"trend_pipeline_{args.execution_id}_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"   ✓ Rapport sauvegardé: {report_path}")
    
    # Save raw data
    data_path = output_dir / f"trend_pipeline_{args.execution_id}_data.json"
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(analysis.raw_data, f, indent=2, ensure_ascii=False, default=str)
    print(f"   ✓ Données brutes sauvegardées: {data_path}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("RÉSUMÉ DE L'ANALYSE")
    print("=" * 60)
    
    status_data = analysis.raw_data.get("status", {})
    if status_data:
        print(f"\n📈 Volumes:")
        print(f"   - Articles: {status_data.get('total_articles', 'N/A')}")
        print(f"   - Clusters: {status_data.get('total_clusters', 'N/A')}")
        print(f"   - Gaps: {status_data.get('total_gaps', 'N/A')}")
    
    print(f"\n📋 Stages:")
    for stage_name, stage in analysis.stages.items():
        status_emoji = "✅" if stage.status == "completed" else "⚠️"
        issues_count = len(stage.issues)
        print(f"   {status_emoji} {stage.stage_name}: {stage.status} ({issues_count} problèmes)")
    
    # Count issues
    total_issues = sum(len(s.issues) for s in analysis.stages.values())
    if total_issues > 0:
        print(f"\n⚠️ {total_issues} problème(s) détecté(s). Voir le rapport pour les détails.")
    else:
        print(f"\n✅ Aucun problème majeur détecté.")
    
    print(f"\n📄 Rapport complet: {report_path}")
    print("")


if __name__ == "__main__":
    asyncio.run(main())



