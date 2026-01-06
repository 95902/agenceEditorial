#!/usr/bin/env python3
"""
Analyse détaillée de la sortie (output) de la route GET /api/v1/sites/{domain}/audit

Ce script :
1. Appelle la route audit pour obtenir la réponse complète
2. Analyse en profondeur tous les champs de la réponse
3. Génère des statistiques détaillées sur chaque section
4. Identifie les données manquantes ou incomplètes
5. Produit un rapport complet avec métriques et insights
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

API_BASE_URL = "http://localhost:8000/api/v1"
DEFAULT_TIMEOUT = 30.0  # 30 secondes pour les réponses rapides


@dataclass
class DomainAnalysis:
    """Analyse d'un domaine d'activité."""
    id: str
    label: str
    confidence: int
    topics_count: int
    summary_length: int
    has_topics: bool
    topics_count_actual: int
    has_metrics: bool
    metrics: Optional[Dict[str, Any]] = None


@dataclass
class AuditOutputAnalysis:
    """Analyse complète de la sortie de la route audit."""
    domain: str
    timestamp: str
    response_type: str  # "SiteAuditResponse" ou "PendingAuditResponse"
    status_code: int
    
    # Métriques générales
    has_profile: bool
    has_domains: bool
    has_competitors: bool
    has_trending_topics: bool
    has_trend_analyses: bool
    has_temporal_insights: bool
    has_editorial_opportunities: bool
    
    # Statistiques détaillées
    profile_stats: Dict[str, Any]
    domains_stats: Dict[str, Any]
    competitors_stats: Dict[str, Any]
    trending_topics_stats: Dict[str, Any]
    trend_analyses_stats: Dict[str, Any]
    temporal_insights_stats: Dict[str, Any]
    editorial_opportunities_stats: Dict[str, Any]
    
    # Analyses par domaine
    domains_analysis: List[DomainAnalysis]
    
    # Problèmes et recommandations
    issues: List[str]
    recommendations: List[str]
    
    # Données brutes
    raw_response: Dict[str, Any]


def analyze_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Analyse la section profile."""
    stats = {
        "has_style": "style" in profile,
        "has_themes": "themes" in profile,
        "themes_count": len(profile.get("themes", [])),
        "style_details": {}
    }
    
    if "style" in profile:
        style = profile["style"]
        stats["style_details"] = {
            "tone": style.get("tone"),
            "vocabulary": style.get("vocabulary"),
            "format": style.get("format"),
            "has_all_fields": all(k in style for k in ["tone", "vocabulary", "format"])
        }
    
    if "themes" in profile:
        stats["themes_list"] = profile["themes"]
    
    return stats


def analyze_domains(domains: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyse la section domains."""
    if not domains:
        return {
            "count": 0,
            "has_domains": False,
            "avg_confidence": 0,
            "avg_topics_count": 0,
            "total_topics": 0,
            "domains_with_topics": 0,
            "domains_with_metrics": 0
        }
    
    confidences = [d.get("confidence", 0) for d in domains]
    topics_counts = [d.get("topics_count", 0) for d in domains]
    summaries_lengths = [len(d.get("summary", "")) for d in domains]
    
    domains_with_topics = sum(1 for d in domains if d.get("topics") and len(d.get("topics", [])) > 0)
    domains_with_metrics = sum(1 for d in domains if d.get("metrics"))
    
    return {
        "count": len(domains),
        "has_domains": True,
        "avg_confidence": round(sum(confidences) / len(confidences), 1) if confidences else 0,
        "min_confidence": min(confidences) if confidences else 0,
        "max_confidence": max(confidences) if confidences else 0,
        "avg_topics_count": round(sum(topics_counts) / len(topics_counts), 1) if topics_counts else 0,
        "total_topics": sum(topics_counts),
        "domains_with_topics": domains_with_topics,
        "domains_with_metrics": domains_with_metrics,
        "avg_summary_length": round(sum(summaries_lengths) / len(summaries_lengths), 0) if summaries_lengths else 0,
        "min_summary_length": min(summaries_lengths) if summaries_lengths else 0,
        "max_summary_length": max(summaries_lengths) if summaries_lengths else 0,
        "domains_list": [d.get("label", "N/A") for d in domains]
    }


def analyze_domain_detail(domain: Dict[str, Any]) -> DomainAnalysis:
    """Analyse un domaine d'activité en détail."""
    topics = domain.get("topics", [])
    metrics = domain.get("metrics")
    
    return DomainAnalysis(
        id=domain.get("id", "unknown"),
        label=domain.get("label", "Unknown"),
        confidence=domain.get("confidence", 0),
        topics_count=domain.get("topics_count", 0),
        summary_length=len(domain.get("summary", "")),
        has_topics=bool(topics and len(topics) > 0),
        topics_count_actual=len(topics) if topics else 0,
        has_metrics=metrics is not None,
        metrics=metrics
    )


def analyze_competitors(competitors: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyse la section competitors."""
    if not competitors:
        return {
            "count": 0,
            "has_competitors": False,
            "avg_similarity": 0
        }
    
    similarities = [c.get("similarity", 0) for c in competitors]
    
    return {
        "count": len(competitors),
        "has_competitors": True,
        "avg_similarity": round(sum(similarities) / len(similarities), 1) if similarities else 0,
        "min_similarity": min(similarities) if similarities else 0,
        "max_similarity": max(similarities) if similarities else 0,
        "competitors_list": [{"name": c.get("name"), "similarity": c.get("similarity")} for c in competitors]
    }


def analyze_trending_topics(trending_section: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyse la section trending_topics."""
    if not trending_section:
        return {
            "has_section": False,
            "topics_count": 0
        }
    
    topics = trending_section.get("topics", [])
    summary = trending_section.get("summary", {})
    
    if not topics:
        return {
            "has_section": True,
            "topics_count": 0,
            "has_summary": bool(summary)
        }
    
    growth_rates = [t.get("growth_rate", 0) for t in topics if t.get("growth_rate")]
    potential_scores = [t.get("potential_score", 0) for t in topics if t.get("potential_score")]
    
    return {
        "has_section": True,
        "topics_count": len(topics),
        "has_summary": bool(summary),
        "summary": summary,
        "avg_growth_rate": round(sum(growth_rates) / len(growth_rates), 2) if growth_rates else 0,
        "max_growth_rate": max(growth_rates) if growth_rates else 0,
        "avg_potential_score": round(sum(potential_scores) / len(potential_scores), 1) if potential_scores else 0,
        "high_potential_count": sum(1 for s in potential_scores if s >= 80) if potential_scores else 0,
        "topics_preview": [
            {
                "title": t.get("title", "N/A"),
                "growth_rate": t.get("growth_rate"),
                "potential_score": t.get("potential_score")
            }
            for t in topics[:5]
        ]
    }


def analyze_trend_analyses(analyses_section: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyse la section trend_analyses."""
    if not analyses_section:
        return {
            "has_section": False,
            "analyses_count": 0
        }
    
    analyses = analyses_section.get("analyses", [])
    summary = analyses_section.get("summary", {})
    
    if not analyses:
        return {
            "has_section": True,
            "analyses_count": 0,
            "has_summary": bool(summary)
        }
    
    analyses_with_opportunities = sum(1 for a in analyses if a.get("opportunities") and len(a.get("opportunities", [])) > 0)
    analyses_with_saturated = sum(1 for a in analyses if a.get("saturated_angles") and len(a.get("saturated_angles", [])) > 0)
    
    return {
        "has_section": True,
        "analyses_count": len(analyses),
        "has_summary": bool(summary),
        "summary": summary,
        "analyses_with_opportunities": analyses_with_opportunities,
        "analyses_with_saturated": analyses_with_saturated,
        "analyses_preview": [
            {
                "topic": a.get("topic_title", a.get("topic", "N/A")),
                "topic_id": a.get("topic_id", "N/A"),
                "has_opportunities": bool(a.get("opportunities") and len(a.get("opportunities", [])) > 0),
                "has_saturated_angles": bool(a.get("saturated_angles") and len(a.get("saturated_angles", [])) > 0),
                "synthesis": a.get("synthesis", "")[:100] if a.get("synthesis") else None
            }
            for a in analyses[:5]
        ]
    }


def analyze_temporal_insights(insights_section: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyse la section temporal_insights."""
    if not insights_section:
        return {
            "has_section": False,
            "insights_count": 0
        }
    
    insights = insights_section.get("insights", [])
    summary = insights_section.get("summary", {})
    
    if not insights:
        return {
            "has_section": True,
            "insights_count": 0,
            "has_summary": bool(summary)
        }
    
    potential_scores = [i.get("potential_score", 0) for i in insights if i.get("potential_score")]
    
    return {
        "has_section": True,
        "insights_count": len(insights),
        "has_summary": bool(summary),
        "summary": summary,
        "avg_potential_score": round(sum(potential_scores) / len(potential_scores), 1) if potential_scores else 0,
        "high_potential_count": sum(1 for s in potential_scores if s >= 80) if potential_scores else 0,
        "insights_preview": [
            {
                "topic": i.get("topic", "N/A"),
                "potential_score": i.get("potential_score"),
                "has_time_windows": bool(i.get("time_windows"))
            }
            for i in insights[:5]
        ]
    }


def analyze_editorial_opportunities(opportunities_section: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyse la section editorial_opportunities."""
    if not opportunities_section:
        return {
            "has_section": False,
            "recommendations_count": 0
        }
    
    recommendations = opportunities_section.get("recommendations", [])
    summary = opportunities_section.get("summary", {})
    
    if not recommendations:
        return {
            "has_section": True,
            "recommendations_count": 0,
            "has_summary": bool(summary)
        }
    
    effort_levels = Counter(r.get("effort_level") for r in recommendations if r.get("effort_level"))
    statuses = Counter(r.get("status") for r in recommendations if r.get("status"))
    differentiation_scores = [r.get("differentiation_score", 0) for r in recommendations if r.get("differentiation_score")]
    
    return {
        "has_section": True,
        "recommendations_count": len(recommendations),
        "has_summary": bool(summary),
        "summary": summary,
        "by_effort_level": dict(effort_levels),
        "by_status": dict(statuses),
        "avg_differentiation_score": round(sum(differentiation_scores) / len(differentiation_scores), 1) if differentiation_scores else 0,
        "high_differentiation_count": sum(1 for s in differentiation_scores if s >= 80) if differentiation_scores else 0,
        "recommendations_preview": [
            {
                "title": r.get("title", "N/A"),
                "effort_level": r.get("effort_level"),
                "status": r.get("status"),
                "differentiation_score": r.get("differentiation_score")
            }
            for r in recommendations[:5]
        ]
    }


def analyze_complete_response(data: Dict[str, Any]) -> AuditOutputAnalysis:
    """Analyse complète d'une réponse SiteAuditResponse."""
    issues = []
    recommendations = []
    
    # Analyser chaque section
    profile = data.get("profile", {})
    domains = data.get("domains", [])
    competitors = data.get("competitors", [])
    trending_topics = data.get("trending_topics")
    trend_analyses = data.get("trend_analyses")
    temporal_insights = data.get("temporal_insights")
    editorial_opportunities = data.get("editorial_opportunities")
    
    # Vérifications de base
    if not profile:
        issues.append("⚠️ Section 'profile' manquante ou vide")
    if not domains:
        issues.append("⚠️ Section 'domains' manquante ou vide")
    if not competitors:
        issues.append("⚠️ Aucun concurrent trouvé")
    
    # Analyser chaque section
    profile_stats = analyze_profile(profile)
    domains_stats = analyze_domains(domains)
    competitors_stats = analyze_competitors(competitors)
    trending_topics_stats = analyze_trending_topics(trending_topics)
    trend_analyses_stats = analyze_trend_analyses(trend_analyses)
    temporal_insights_stats = analyze_temporal_insights(temporal_insights)
    editorial_opportunities_stats = analyze_editorial_opportunities(editorial_opportunities)
    
    # Analyser chaque domaine en détail
    domains_analysis = [analyze_domain_detail(d) for d in domains]
    
    # Générer des recommandations
    if domains_stats.get("count", 0) == 0:
        recommendations.append("🔧 Aucun domaine d'activité trouvé. Vérifier l'analyse éditoriale.")
    
    if domains_stats.get("domains_with_topics", 0) == 0 and domains_stats.get("count", 0) > 0:
        recommendations.append("💡 Considérer activer 'include_topics=true' pour voir les topics détaillés par domaine.")
    
    if competitors_stats.get("count", 0) == 0:
        recommendations.append("🔧 Aucun concurrent identifié. Lancer une recherche de concurrents.")
    
    if not trending_topics_stats.get("has_section"):
        recommendations.append("💡 La section trending_topics n'est pas disponible. Vérifier le trend pipeline.")
    
    if not trend_analyses_stats.get("has_section"):
        recommendations.append("💡 La section trend_analyses n'est pas disponible. Vérifier le trend pipeline.")
    
    if domains_stats.get("avg_confidence", 0) < 50:
        recommendations.append("⚠️ La confiance moyenne des domaines est faible. Améliorer la qualité des articles scrapés.")
    
    if competitors_stats.get("avg_similarity", 0) < 50:
        recommendations.append("⚠️ La similarité moyenne des concurrents est faible. Vérifier la recherche de concurrents.")
    
    return AuditOutputAnalysis(
        domain=data.get("url", "unknown").replace("https://", "").replace("http://", ""),
        timestamp=datetime.now().isoformat(),
        response_type="SiteAuditResponse",
        status_code=200,
        has_profile=bool(profile),
        has_domains=bool(domains),
        has_competitors=bool(competitors),
        has_trending_topics=trending_topics_stats.get("has_section", False),
        has_trend_analyses=trend_analyses_stats.get("has_section", False),
        has_temporal_insights=temporal_insights_stats.get("has_section", False),
        has_editorial_opportunities=editorial_opportunities_stats.get("has_section", False),
        profile_stats=profile_stats,
        domains_stats=domains_stats,
        competitors_stats=competitors_stats,
        trending_topics_stats=trending_topics_stats,
        trend_analyses_stats=trend_analyses_stats,
        temporal_insights_stats=temporal_insights_stats,
        editorial_opportunities_stats=editorial_opportunities_stats,
        domains_analysis=domains_analysis,
        issues=issues,
        recommendations=recommendations,
        raw_response=data
    )


def analyze_pending_response(data: Dict[str, Any]) -> AuditOutputAnalysis:
    """Analyse d'une réponse PendingAuditResponse."""
    issues = []
    recommendations = []
    
    data_status = data.get("data_status", {})
    workflow_steps = data.get("workflow_steps", [])
    execution_id = data.get("execution_id", "N/A")
    message = data.get("message", "N/A")
    
    # Extraire le domaine depuis l'execution_id ou message si possible
    domain = "unknown"
    if "domain" in str(data):
        # Essayer d'extraire depuis les données brutes
        pass
    
    # Analyser le statut des données
    missing_data = []
    available_data = []
    
    if data_status.get("has_profile", False):
        available_data.append("profile")
    else:
        missing_data.append("profile")
    
    if data_status.get("has_competitors", False):
        available_data.append("competitors")
    else:
        missing_data.append("competitors")
    
    if data_status.get("has_client_articles", False):
        available_data.append("client_articles")
    else:
        missing_data.append("client_articles")
    
    if data_status.get("has_competitor_articles", False):
        available_data.append("competitor_articles")
    else:
        missing_data.append("competitor_articles")
    
    if data_status.get("has_trend_pipeline", False):
        available_data.append("trend_pipeline")
    else:
        missing_data.append("trend_pipeline")
    
    # Générer des issues et recommandations
    if missing_data:
        issues.append(f"⚠️ Données manquantes ({len(missing_data)}/5): {', '.join(missing_data)}")
        recommendations.append(f"⏳ {len(workflow_steps)} workflow(s) en cours pour générer les données manquantes")
        recommendations.append(f"📋 Execution ID: {execution_id}")
        recommendations.append("💡 Utiliser GET /api/v1/sites/{domain}/audit/status/{execution_id} pour suivre la progression")
    
    if available_data:
        recommendations.append(f"✅ Données déjà disponibles: {', '.join(available_data)}")
    
    # Analyser les étapes de workflow
    workflow_stats = {
        "total_steps": len(workflow_steps),
        "steps_details": [
            {
                "step": step.get("step"),
                "name": step.get("name"),
                "status": step.get("status"),
                "execution_id": step.get("execution_id")
            }
            for step in workflow_steps
        ]
    }
    
    return AuditOutputAnalysis(
        domain=domain,
        timestamp=datetime.now().isoformat(),
        response_type="PendingAuditResponse",
        status_code=200,
        has_profile=data_status.get("has_profile", False),
        has_domains=False,
        has_competitors=data_status.get("has_competitors", False),
        has_trending_topics=False,
        has_trend_analyses=False,
        has_temporal_insights=False,
        has_editorial_opportunities=False,
        profile_stats={"workflow_stats": workflow_stats},
        domains_stats={"count": 0},
        competitors_stats={"count": 0},
        trending_topics_stats={},
        trend_analyses_stats={},
        temporal_insights_stats={},
        editorial_opportunities_stats={},
        domains_analysis=[],
        issues=issues,
        recommendations=recommendations,
        raw_response=data
    )


def print_detailed_analysis(analysis: AuditOutputAnalysis):
    """Affiche l'analyse détaillée."""
    print("\n" + "="*80)
    print("ANALYSE DÉTAILLÉE - Sortie de la route GET /api/v1/sites/{domain}/audit")
    print("="*80)
    print(f"\nDomaine: {analysis.domain}")
    print(f"Timestamp: {analysis.timestamp}")
    print(f"Type de réponse: {analysis.response_type}")
    print(f"Statut HTTP: {analysis.status_code}")
    
    # Vue d'ensemble
    print(f"\n{'='*80}")
    print("VUE D'ENSEMBLE")
    print(f"{'='*80}")
    print(f"✅ Profile: {'Oui' if analysis.has_profile else 'Non'}")
    print(f"✅ Domaines: {'Oui' if analysis.has_domains else 'Non'}")
    print(f"✅ Concurrents: {'Oui' if analysis.has_competitors else 'Non'}")
    print(f"✅ Trending Topics: {'Oui' if analysis.has_trending_topics else 'Non'}")
    print(f"✅ Trend Analyses: {'Oui' if analysis.has_trend_analyses else 'Non'}")
    print(f"✅ Temporal Insights: {'Oui' if analysis.has_temporal_insights else 'Non'}")
    print(f"✅ Editorial Opportunities: {'Oui' if analysis.has_editorial_opportunities else 'Non'}")
    
    # Profile
    if analysis.has_profile:
        print(f"\n{'='*80}")
        print("PROFILE")
        print(f"{'='*80}")
        stats = analysis.profile_stats
        print(f"Thèmes: {stats.get('themes_count', 0)}")
        if stats.get('themes_list'):
            print(f"  Liste: {', '.join(stats['themes_list'])}")
        if stats.get('style_details'):
            style = stats['style_details']
            print(f"Style:")
            print(f"  Ton: {style.get('tone', 'N/A')}")
            print(f"  Vocabulaire: {style.get('vocabulary', 'N/A')}")
            print(f"  Format: {style.get('format', 'N/A')}")
    
    # Domaines
    if analysis.has_domains:
        print(f"\n{'='*80}")
        print("DOMAINES D'ACTIVITÉ")
        print(f"{'='*80}")
        stats = analysis.domains_stats
        print(f"Nombre de domaines: {stats.get('count', 0)}")
        print(f"Confiance moyenne: {stats.get('avg_confidence', 0)}%")
        print(f"  (min: {stats.get('min_confidence', 0)}%, max: {stats.get('max_confidence', 0)}%)")
        print(f"Topics totaux: {stats.get('total_topics', 0)}")
        print(f"Topics moyens par domaine: {stats.get('avg_topics_count', 0)}")
        print(f"Domaines avec topics détaillés: {stats.get('domains_with_topics', 0)}/{stats.get('count', 0)}")
        print(f"Domaines avec métriques: {stats.get('domains_with_metrics', 0)}/{stats.get('count', 0)}")
        print(f"Longueur moyenne des résumés: {stats.get('avg_summary_length', 0)} caractères")
        
        # Détail par domaine
        print(f"\nDétail par domaine:")
        for domain_analysis in analysis.domains_analysis:
            print(f"\n  📌 {domain_analysis.label} (id: {domain_analysis.id})")
            print(f"     Confiance: {domain_analysis.confidence}%")
            print(f"     Topics count: {domain_analysis.topics_count}")
            print(f"     Résumé: {domain_analysis.summary_length} caractères")
            print(f"     Topics détaillés: {'Oui' if domain_analysis.has_topics else 'Non'} ({domain_analysis.topics_count_actual} topics)")
            print(f"     Métriques: {'Oui' if domain_analysis.has_metrics else 'Non'}")
            if domain_analysis.metrics:
                metrics = domain_analysis.metrics
                print(f"       - Articles totaux: {metrics.get('total_articles', 0)}")
                print(f"       - Trending topics: {metrics.get('trending_topics', 0)}")
                print(f"       - Pertinence moyenne: {metrics.get('avg_relevance', 0)}")
    
    # Concurrents
    if analysis.has_competitors:
        print(f"\n{'='*80}")
        print("CONCURRENTS")
        print(f"{'='*80}")
        stats = analysis.competitors_stats
        print(f"Nombre de concurrents: {stats.get('count', 0)}")
        print(f"Similarité moyenne: {stats.get('avg_similarity', 0)}%")
        print(f"  (min: {stats.get('min_similarity', 0)}%, max: {stats.get('max_similarity', 0)}%)")
        if stats.get('competitors_list'):
            print(f"\nTop concurrents:")
            for i, comp in enumerate(stats['competitors_list'][:10], 1):
                print(f"  {i}. {comp['name']} (similarité: {comp['similarity']}%)")
    
    # Trending Topics
    if analysis.has_trending_topics:
        print(f"\n{'='*80}")
        print("TRENDING TOPICS")
        print(f"{'='*80}")
        stats = analysis.trending_topics_stats
        print(f"Nombre de topics: {stats.get('topics_count', 0)}")
        if stats.get('topics_count', 0) > 0:
            print(f"Taux de croissance moyen: {stats.get('avg_growth_rate', 0)}%")
            print(f"Score de potentiel moyen: {stats.get('avg_potential_score', 0)}")
            print(f"Topics à haut potentiel (≥80): {stats.get('high_potential_count', 0)}")
            if stats.get('topics_preview'):
                print(f"\nAperçu des topics:")
                for topic in stats['topics_preview']:
                    print(f"  - {topic['title']}")
                    print(f"    Croissance: {topic.get('growth_rate', 'N/A')}%, Potentiel: {topic.get('potential_score', 'N/A')}")
    
    # Trend Analyses
    if analysis.has_trend_analyses:
        print(f"\n{'='*80}")
        print("TREND ANALYSES")
        print(f"{'='*80}")
        stats = analysis.trend_analyses_stats
        print(f"Nombre d'analyses: {stats.get('analyses_count', 0)}")
        if stats.get('analyses_count', 0) > 0:
            print(f"Analyses avec opportunités: {stats.get('analyses_with_opportunities', 0)}")
            print(f"Analyses avec angles saturés: {stats.get('analyses_with_saturated', 0)}")
            if stats.get('analyses_preview'):
                print(f"\nAperçu des analyses:")
                for analysis_item in stats['analyses_preview']:
                    topic = analysis_item.get('topic', 'N/A')
                    if topic == 'N/A' and analysis_item.get('topic_id'):
                        topic = analysis_item.get('topic_id', 'N/A')
                    print(f"  - {topic}")
                    print(f"    Opportunités: {'Oui' if analysis_item.get('has_opportunities') else 'Non'}")
                    print(f"    Angles saturés: {'Oui' if analysis_item.get('has_saturated_angles') else 'Non'}")
    
    # Temporal Insights
    if analysis.has_temporal_insights:
        print(f"\n{'='*80}")
        print("TEMPORAL INSIGHTS")
        print(f"{'='*80}")
        stats = analysis.temporal_insights_stats
        print(f"Nombre d'insights: {stats.get('insights_count', 0)}")
        if stats.get('insights_count', 0) > 0:
            print(f"Score de potentiel moyen: {stats.get('avg_potential_score', 0)}")
            print(f"Insights à haut potentiel (≥80): {stats.get('high_potential_count', 0)}")
    
    # Editorial Opportunities
    if analysis.has_editorial_opportunities:
        print(f"\n{'='*80}")
        print("EDITORIAL OPPORTUNITIES")
        print(f"{'='*80}")
        stats = analysis.editorial_opportunities_stats
        print(f"Nombre de recommandations: {stats.get('recommendations_count', 0)}")
        if stats.get('recommendations_count', 0) > 0:
            print(f"Score de différenciation moyen: {stats.get('avg_differentiation_score', 0)}")
            print(f"Recommandations à haute différenciation (≥80): {stats.get('high_differentiation_count', 0)}")
            if stats.get('by_effort_level'):
                print(f"\nPar niveau d'effort:")
                for level, count in stats['by_effort_level'].items():
                    print(f"  - {level}: {count}")
            if stats.get('by_status'):
                print(f"\nPar statut:")
                for status, count in stats['by_status'].items():
                    print(f"  - {status}: {count}")
    
    # Pour les réponses PendingAuditResponse
    if analysis.response_type == "PendingAuditResponse":
        print(f"\n{'='*80}")
        print("WORKFLOWS EN COURS")
        print(f"{'='*80}")
        workflow_stats = analysis.profile_stats.get("workflow_stats", {})
        if workflow_stats:
            print(f"Nombre d'étapes: {workflow_stats.get('total_steps', 0)}")
            if workflow_stats.get("steps_details"):
                print(f"\nDétail des étapes:")
                for step_detail in workflow_stats["steps_details"]:
                    print(f"  {step_detail.get('step')}. {step_detail.get('name')} - {step_detail.get('status', 'N/A')}")
                    if step_detail.get('execution_id'):
                        print(f"     Execution ID: {step_detail['execution_id']}")
        
        raw = analysis.raw_response
        if raw.get("execution_id"):
            print(f"\nExecution ID principal: {raw['execution_id']}")
        if raw.get("message"):
            print(f"Message: {raw['message']}")
        
        data_status = raw.get("data_status", {})
        if data_status:
            print(f"\nStatut des données:")
            print(f"  Profile: {'✅' if data_status.get('has_profile') else '❌'}")
            print(f"  Concurrents: {'✅' if data_status.get('has_competitors') else '❌'}")
            print(f"  Articles client: {'✅' if data_status.get('has_client_articles') else '❌'}")
            print(f"  Articles concurrents: {'✅' if data_status.get('has_competitor_articles') else '❌'}")
            print(f"  Trend pipeline: {'✅' if data_status.get('has_trend_pipeline') else '❌'}")
    
    # Problèmes et recommandations
    if analysis.issues:
        print(f"\n{'='*80}")
        print("PROBLÈMES IDENTIFIÉS")
        print(f"{'='*80}")
        for issue in analysis.issues:
            print(f"  {issue}")
    
    if analysis.recommendations:
        print(f"\n{'='*80}")
        print("RECOMMANDATIONS")
        print(f"{'='*80}")
        for i, rec in enumerate(analysis.recommendations, 1):
            print(f"{i}. {rec}")
    
    print("\n" + "="*80)


async def main():
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Analyse détaillée de la sortie de la route GET /api/v1/sites/{domain}/audit"
    )
    parser.add_argument(
        "--domain",
        type=str,
        default="innosys.fr",
        help="Domaine à analyser (défaut: innosys.fr)"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Timeout en secondes (défaut: {DEFAULT_TIMEOUT})"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Fichier JSON de sortie pour sauvegarder l'analyse"
    )
    
    args = parser.parse_args()
    
    print(f"🔍 Analyse détaillée de la sortie de la route audit")
    print(f"Domaine: {args.domain}")
    print(f"API: {API_BASE_URL}/sites/{args.domain}/audit")
    print("⏳ Appel de l'API...\n")
    
    async with httpx.AsyncClient(timeout=args.timeout) as client:
        try:
            response = await client.get(f"{API_BASE_URL}/sites/{args.domain}/audit")
            
            if response.status_code != 200:
                print(f"❌ Erreur HTTP {response.status_code}")
                print(response.text[:500])
                sys.exit(1)
            
            data = response.json()
            
            # Extraire le domaine depuis l'URL de la requête
            domain_from_url = args.domain
            
            # Déterminer le type de réponse
            if "execution_id" in data:
                analysis = analyze_pending_response(data)
                analysis.domain = domain_from_url  # Corriger le domaine
            else:
                analysis = analyze_complete_response(data)
                if analysis.domain == "unknown":
                    analysis.domain = domain_from_url
            
            # Afficher l'analyse
            print_detailed_analysis(analysis)
            
            # Sauvegarder si demandé
            if args.output:
                output_path = Path(args.output)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Convertir en dict pour JSON
                analysis_dict = asdict(analysis)
                # Convertir les DomainAnalysis en dict
                analysis_dict["domains_analysis"] = [asdict(da) for da in analysis.domains_analysis]
                
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(analysis_dict, f, indent=2, ensure_ascii=False, default=str)
                print(f"\n💾 Analyse sauvegardée: {output_path}")
        
        except httpx.TimeoutException:
            print(f"❌ Timeout lors de l'appel à l'API (timeout: {args.timeout}s)")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Erreur: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

