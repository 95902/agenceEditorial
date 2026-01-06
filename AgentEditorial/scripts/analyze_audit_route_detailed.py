#!/usr/bin/env python3
"""
Script d'analyse détaillée de la route GET /api/v1/sites/{domain}/audit

Ce script :
1. Instrumente chaque étape de la route pour mesurer les performances
2. Compte les requêtes DB
3. Identifie les goulots d'étranglement
4. Génère un rapport avec métriques et recommandations
"""

import asyncio
import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import sys

# Ajouter le chemin du projet
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import event, select, desc
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.api.routers.sites import (
    _check_site_profile,
    _check_competitors,
    _check_trend_pipeline,
    _check_client_articles,
    _check_competitor_articles,
    build_complete_audit_from_database,
)
from python_scripts.database.models import WorkflowExecution


@dataclass
class StepMetrics:
    """Métriques pour une étape de la route."""
    step_name: str
    duration_ms: float
    db_queries_count: int
    db_queries_duration_ms: float
    error: Optional[str] = None
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


@dataclass
class AuditAnalysis:
    """Analyse complète de la route audit."""
    domain: str
    timestamp: str
    total_duration_ms: float
    steps: List[StepMetrics]
    db_total_queries: int
    db_total_duration_ms: float
    bottlenecks: List[Dict[str, Any]]
    recommendations: List[str]
    response_type: str  # "SiteAuditResponse" ou "PendingAuditResponse"


class QueryCounter:
    """Compteur de requêtes SQL."""
    
    def __init__(self):
        self.count = 0
        self.total_duration = 0.0
        self.queries = []
        self._start_time = None
    
    def start_query(self):
        self._start_time = time.perf_counter()
    
    def end_query(self, query_text: str = ""):
        if self._start_time:
            duration = (time.perf_counter() - self._start_time) * 1000
            self.count += 1
            self.total_duration += duration
            self.queries.append({
                "query": query_text[:200] if query_text else "N/A",  # Limiter la taille
                "duration_ms": round(duration, 2)
            })
            self._start_time = None
    
    def reset(self):
        self.count = 0
        self.total_duration = 0.0
        self.queries = []
    
    def get_stats(self):
        return {
            "count": self.count,
            "total_duration_ms": round(self.total_duration, 2),
            "avg_duration_ms": round(self.total_duration / self.count, 2) if self.count > 0 else 0,
            "queries": self.queries[:10]  # Limiter à 10 pour le rapport
        }


# Instance globale du compteur
query_counter = QueryCounter()


def setup_query_counter():
    """Configure le compteur de requêtes SQL."""
    @event.listens_for(Engine, "before_cursor_execute")
    def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        query_counter.start_query()
    
    @event.listens_for(Engine, "after_cursor_execute")
    def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        query_counter.end_query(str(statement))


async def analyze_step(
    step_name: str,
    coro,
    *args,
    **kwargs
) -> StepMetrics:
    """Analyse une étape de la route."""
    query_counter.reset()
    start_time = time.perf_counter()
    error = None
    details = {}
    
    try:
        result = await coro(*args, **kwargs)
        if result is None:
            details["result"] = "None"
        elif isinstance(result, tuple):
            details["result_type"] = type(result[0]).__name__ if result else "None"
            details["result_size"] = len(result) if isinstance(result, (list, tuple)) else 1
        elif hasattr(result, '__len__'):
            details["result_size"] = len(result)
        else:
            details["result_type"] = type(result).__name__
    except Exception as e:
        error = str(e)
        result = None
    
    duration_ms = (time.perf_counter() - start_time) * 1000
    stats = query_counter.get_stats()
    
    return StepMetrics(
        step_name=step_name,
        duration_ms=round(duration_ms, 2),
        db_queries_count=stats["count"],
        db_queries_duration_ms=stats["total_duration_ms"],
        error=error,
        details=details
    )


async def analyze_audit_route(domain: str) -> AuditAnalysis:
    """Analyse complète de la route audit."""
    setup_query_counter()
    
    steps = []
    total_start = time.perf_counter()
    
    async with AsyncSessionLocal() as db:
        try:
            # ÉTAPE 1: Validation du domaine (synchrone, on simule)
            validation_step = StepMetrics(
                step_name="1. Validation du domaine",
                duration_ms=0.1,
                db_queries_count=0,
                db_queries_duration_ms=0.0,
                details={"validation": "regex check"}
            )
            steps.append(validation_step)
            
            # ÉTAPE 2: Vérification site_profile
            profile = None
            profile_step = await analyze_step(
                "2. Vérification site_profile",
                _check_site_profile,
                db, domain
            )
            steps.append(profile_step)
            if not profile_step.error:
                profile = await _check_site_profile(db, domain)
                if profile:
                    profile_step.details["profile_id"] = profile.id
                    profile_step.details["has_profile"] = True
                else:
                    profile_step.details["has_profile"] = False
            
            # ÉTAPE 3: Vérifications en parallèle
            parallel_start = time.perf_counter()
            
            competitors_step = await analyze_step(
                "3a. Vérification competitors",
                _check_competitors,
                db, domain
            )
            steps.append(competitors_step)
            
            trend_step = await analyze_step(
                "3b. Vérification trend_pipeline",
                _check_trend_pipeline,
                db, domain
            )
            steps.append(trend_step)
            
            client_articles_step = None
            if profile:
                client_articles_step = await analyze_step(
                    "3c. Vérification client_articles",
                    _check_client_articles,
                    db, profile.id
                )
                steps.append(client_articles_step)
            
            parallel_duration = (time.perf_counter() - parallel_start) * 1000
            parallel_queries = competitors_step.db_queries_count + trend_step.db_queries_count
            parallel_db_time = competitors_step.db_queries_duration_ms + trend_step.db_queries_duration_ms
            if client_articles_step:
                parallel_queries += client_articles_step.db_queries_count
                parallel_db_time += client_articles_step.db_queries_duration_ms
            
            steps.append(StepMetrics(
                step_name="3. Vérifications parallèles (total)",
                duration_ms=round(parallel_duration, 2),
                db_queries_count=parallel_queries,
                db_queries_duration_ms=round(parallel_db_time, 2),
                details={"parallel_steps": 3 if profile else 2}
            ))
            
            # Récupérer les résultats pour les étapes suivantes
            competitors_execution = await _check_competitors(db, domain)
            trend_execution = await _check_trend_pipeline(db, domain)
            
            # ÉTAPE 4: Vérification articles concurrents (si nécessaire)
            if competitors_execution and competitors_execution.output_data:
                competitors_data = competitors_execution.output_data.get("competitors", [])
                competitor_domains = [
                    c.get("domain")
                    for c in competitors_data
                    if c.get("domain") and not c.get("excluded", False)
                    and (c.get("validated", False) or c.get("manual", False))
                ]
                
                if competitor_domains:
                    competitor_articles_step = await analyze_step(
                        "4. Vérification competitor_articles",
                        _check_competitor_articles,
                        db, competitor_domains, domain
                    )
                    competitor_articles_step.details["competitor_domains_count"] = len(competitor_domains)
                    steps.append(competitor_articles_step)
            
            # ÉTAPE 5: Vérification orchestrator complet
            async def check_orchestrator():
                stmt = (
                    select(WorkflowExecution)
                    .where(
                        WorkflowExecution.workflow_type == "audit_orchestrator",
                        WorkflowExecution.status == "completed",
                        WorkflowExecution.input_data["domain"].astext == domain,
                        WorkflowExecution.is_valid == True,
                        WorkflowExecution.was_success == True,
                    )
                    .order_by(desc(WorkflowExecution.end_time))
                    .limit(1)
                )
                result = await db.execute(stmt)
                return result.scalar_one_or_none()
            
            orchestrator_step = await analyze_step(
                "5. Vérification orchestrator complet",
                check_orchestrator
            )
            orchestrator_result = await check_orchestrator()
            orchestrator_step.details["has_orchestrator"] = orchestrator_result is not None
            steps.append(orchestrator_step)
            
            # ÉTAPE 6: Construction de la réponse (si données disponibles)
            if profile:
                build_step = await analyze_step(
                    "6. Construction réponse complète",
                    build_complete_audit_from_database,
                    db, domain, profile, competitors_execution, trend_execution,
                    include_topics=False,  # Pour accélérer l'analyse
                    include_trending=True,
                    include_analyses=True,
                    include_temporal=True,
                    include_opportunities=True,
                    topics_limit=10,
                    trending_limit=15
                )
                steps.append(build_step)
            
            total_duration = (time.perf_counter() - total_start) * 1000
            
            # Calculer les statistiques globales
            db_total_queries = sum(s.db_queries_count for s in steps)
            db_total_duration = sum(s.db_queries_duration_ms for s in steps)
            
            # Identifier les goulots d'étranglement
            bottlenecks = []
            for step in steps:
                if step.duration_ms > 1000:  # Plus de 1 seconde
                    bottlenecks.append({
                        "step": step.step_name,
                        "duration_ms": step.duration_ms,
                        "db_queries": step.db_queries_count,
                        "db_duration_ms": step.db_queries_duration_ms
                    })
            
            # Générer des recommandations
            recommendations = generate_recommendations(steps, bottlenecks, db_total_duration, total_duration)
            
            return AuditAnalysis(
                domain=domain,
                timestamp=datetime.now().isoformat(),
                total_duration_ms=round(total_duration, 2),
                steps=steps,
                db_total_queries=db_total_queries,
                db_total_duration_ms=round(db_total_duration, 2),
                bottlenecks=bottlenecks,
                recommendations=recommendations,
                response_type="SiteAuditResponse" if profile else "PendingAuditResponse"
            )
            
        except Exception as e:
            # En cas d'erreur, retourner une analyse partielle
            total_duration = (time.perf_counter() - total_start) * 1000
            return AuditAnalysis(
                domain=domain,
                timestamp=datetime.now().isoformat(),
                total_duration_ms=round(total_duration, 2),
                steps=steps,
                db_total_queries=sum(s.db_queries_count for s in steps),
                db_total_duration_ms=sum(s.db_queries_duration_ms for s in steps),
                bottlenecks=[],
                recommendations=[f"❌ Erreur lors de l'analyse: {str(e)}"],
                response_type="Error"
            )


def generate_recommendations(
    steps: List[StepMetrics], 
    bottlenecks: List[Dict], 
    db_total_duration: float,
    total_duration: float
) -> List[str]:
    """Génère des recommandations basées sur l'analyse."""
    recommendations = []
    
    # Analyser les requêtes DB
    if total_duration > 0:
        db_percentage = (db_total_duration / total_duration) * 100
        if db_percentage > 70:
            recommendations.append(
                f"⚠️ Plus de {db_percentage:.1f}% du temps est passé en requêtes DB. "
                "Considérer l'ajout d'index ou la mise en cache."
            )
        elif db_percentage < 30:
            recommendations.append(
                f"✅ Seulement {db_percentage:.1f}% du temps en DB. "
                "Les performances DB sont bonnes."
            )
    
    # Identifier les étapes lentes
    slow_steps = [s for s in steps if s.duration_ms > 2000]
    if slow_steps:
        recommendations.append(
            f"⚠️ {len(slow_steps)} étape(s) prennent plus de 2 secondes: "
            f"{', '.join([s.step_name for s in slow_steps[:3]])}"
        )
    
    # Vérifier le parallélisme
    parallel_step = next((s for s in steps if "parallèles" in s.step_name), None)
    if parallel_step:
        individual_steps = [
            s for s in steps 
            if any(x in s.step_name for x in ["3a", "3b", "3c"])
        ]
        if individual_steps:
            max_individual = max(s.duration_ms for s in individual_steps)
            if parallel_step.duration_ms < max_individual * 1.2:
                recommendations.append(
                    "✅ Le parallélisme fonctionne bien. "
                    f"Les vérifications parallèles sont efficaces ({parallel_step.duration_ms:.0f}ms vs {max_individual:.0f}ms max individuel)."
                )
            else:
                recommendations.append(
                    "⚠️ Le parallélisme pourrait être amélioré. "
                    f"Les vérifications parallèles prennent {parallel_step.duration_ms:.0f}ms alors que le max individuel est {max_individual:.0f}ms."
                )
    
    # Recommandations spécifiques par étape
    build_step = next((s for s in steps if "Construction" in s.step_name), None)
    if build_step and build_step.duration_ms > 3000:
        recommendations.append(
            f"🔧 La construction de la réponse est lente ({build_step.duration_ms:.0f}ms). "
            "Considérer la pagination ou le chargement différé des sections optionnelles."
        )
    
    competitor_articles_step = next((s for s in steps if "competitor_articles" in s.step_name), None)
    if competitor_articles_step and competitor_articles_step.db_queries_count > 10:
        recommendations.append(
            f"🔧 Trop de requêtes ({competitor_articles_step.db_queries_count}) pour vérifier les articles concurrents. "
            "Considérer une requête agrégée ou un cache."
        )
    
    # Recommandations sur les requêtes DB
    if db_total_duration > 0:
        avg_query_time = db_total_duration / sum(s.db_queries_count for s in steps if s.db_queries_count > 0)
        if avg_query_time > 100:
            recommendations.append(
                f"🔧 Temps moyen par requête DB élevé ({avg_query_time:.0f}ms). "
                "Vérifier les index et optimiser les requêtes lentes."
            )
    
    if not recommendations:
        recommendations.append("✅ Aucun problème majeur détecté. Les performances sont bonnes.")
    
    return recommendations


def print_analysis_report(analysis: AuditAnalysis):
    """Affiche le rapport d'analyse."""
    print("\n" + "="*80)
    print("RAPPORT D'ANALYSE - Route GET /api/v1/sites/{domain}/audit")
    print("="*80)
    print(f"\nDomaine analysé: {analysis.domain}")
    print(f"Timestamp: {analysis.timestamp}")
    print(f"Type de réponse: {analysis.response_type}")
    
    print(f"\n{'='*80}")
    print("MÉTRIQUES GLOBALES")
    print(f"{'='*80}")
    print(f"Durée totale: {analysis.total_duration_ms:.2f} ms ({analysis.total_duration_ms/1000:.2f} s)")
    print(f"Requêtes DB totales: {analysis.db_total_queries}")
    print(f"Temps DB total: {analysis.db_total_duration_ms:.2f} ms")
    if analysis.total_duration_ms > 0:
        db_percentage = (analysis.db_total_duration_ms / analysis.total_duration_ms) * 100
        print(f"Temps DB / Temps total: {db_percentage:.1f}%")
    
    print(f"\n{'='*80}")
    print("DÉTAIL PAR ÉTAPE")
    print(f"{'='*80}")
    print(f"{'Étape':<45} {'Durée (ms)':<15} {'Requêtes DB':<15} {'Temps DB (ms)':<15}")
    print("-"*80)
    
    for step in analysis.steps:
        error_marker = " ❌" if step.error else ""
        print(
            f"{step.step_name:<45} "
            f"{step.duration_ms:>12.2f} "
            f"{step.db_queries_count:>13} "
            f"{step.db_queries_duration_ms:>13.2f}{error_marker}"
        )
        if step.error:
            print(f"  └─ Erreur: {step.error}")
        if step.details:
            for key, value in step.details.items():
                print(f"  └─ {key}: {value}")
    
    if analysis.bottlenecks:
        print(f"\n{'='*80}")
        print("GOULOTS D'ÉTRANGLEMENT (> 1 seconde)")
        print(f"{'='*80}")
        for i, bottleneck in enumerate(analysis.bottlenecks, 1):
            print(f"\n{i}. {bottleneck['step']}")
            print(f"   Durée: {bottleneck['duration_ms']:.2f} ms")
            print(f"   Requêtes DB: {bottleneck['db_queries']}")
            print(f"   Temps DB: {bottleneck['db_duration_ms']:.2f} ms")
    
    if analysis.recommendations:
        print(f"\n{'='*80}")
        print("RECOMMANDATIONS")
        print(f"{'='*80}")
        for i, rec in enumerate(analysis.recommendations, 1):
            print(f"{i}. {rec}")
    
    print("\n" + "="*80)


async def main():
    """Point d'entrée principal."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Analyse détaillée de la route GET /api/v1/sites/{domain}/audit"
    )
    parser.add_argument(
        "--domain",
        type=str,
        default="innosys.fr",
        help="Domaine à analyser (défaut: innosys.fr)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Fichier JSON de sortie pour sauvegarder l'analyse"
    )
    
    args = parser.parse_args()
    
    print(f"🔍 Analyse de la route audit pour le domaine: {args.domain}")
    print("⏳ Cela peut prendre du temps...\n")
    
    try:
        analysis = await analyze_audit_route(args.domain)
        print_analysis_report(analysis)
        
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convertir en dict pour JSON
            analysis_dict = asdict(analysis)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(analysis_dict, f, indent=2, ensure_ascii=False, default=str)
            print(f"\n💾 Analyse sauvegardée: {output_path}")
    
    except Exception as e:
        print(f"\n❌ Erreur lors de l'analyse: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())


