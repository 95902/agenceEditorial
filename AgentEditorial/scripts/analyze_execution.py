#!/usr/bin/env python3
"""Script pour analyser une exécution de workflow depuis la base de données."""

import asyncio
import json
from collections import Counter
from uuid import UUID
from datetime import datetime

from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.crud_executions import get_workflow_execution
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


def format_duration(seconds: int) -> str:
    """Formate une durée en secondes en format lisible."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours}h {minutes}m {secs}s"


def analyze_competitor_results(output_data: dict) -> dict:
    """Analyse les résultats d'une recherche de concurrents."""
    analysis = {
        "statistics": {},
        "sources": {},
        "exclusion_reasons": {},
        "score_distribution": {},
        "esn_distribution": {},
        "business_types": {},
        "strategies": {},
        "top_competitors": [],
        "top_excluded": [],
        "issues": [],
    }

    competitors = output_data.get("competitors", [])
    all_candidates = output_data.get("all_candidates", [])
    excluded_candidates = output_data.get("excluded_candidates", [])
    total_found = output_data.get("total_found", 0)
    total_evaluated = output_data.get("total_evaluated", 0)

    # Statistiques générales
    analysis["statistics"] = {
        "total_found": total_found,
        "total_evaluated": total_evaluated,
        "included": len(competitors),
        "excluded": len(excluded_candidates),
        "inclusion_rate": f"{(len(competitors) / total_evaluated * 100):.1f}%" if total_evaluated > 0 else "0%",
    }

    # Analyse des sources
    all_items = (all_candidates if all_candidates else competitors) + excluded_candidates
    sources = [item.get("source", "unknown") for item in all_items]
    analysis["sources"] = dict(Counter(sources))

    # Analyse des raisons d'exclusion
    exclusion_reasons = [
        item.get("exclusion_reason", "Unknown")
        for item in excluded_candidates
        if item.get("exclusion_reason")
    ]
    analysis["exclusion_reasons"] = dict(Counter(exclusion_reasons))

    # Distribution des scores
    scores = [
        item.get("combined_score", 0)
        for item in all_items
        if item.get("combined_score") is not None
    ]
    if scores:
        analysis["score_distribution"] = {
            "min": min(scores),
            "max": max(scores),
            "mean": sum(scores) / len(scores),
            "median": sorted(scores)[len(scores) // 2],
            "count": len(scores),
        }

    # Distribution ESN
    esn_counts = Counter(
        item.get("is_esn", False) for item in all_items if "is_esn" in item
    )
    analysis["esn_distribution"] = {
        "esn": esn_counts.get(True, 0),
        "non_esn": esn_counts.get(False, 0),
    }

    # Types de business
    business_types = [
        item.get("business_type", "unknown")
        for item in all_items
        if item.get("business_type")
    ]
    analysis["business_types"] = dict(Counter(business_types))

    # Stratégies
    strategies = [
        item.get("strategy", "unknown")
        for item in all_items
        if item.get("strategy")
    ]
    analysis["strategies"] = dict(Counter(strategies))

    # Top concurrents inclus
    sorted_competitors = sorted(
        competitors,
        key=lambda x: x.get("combined_score", 0),
        reverse=True,
    )[:10]
    analysis["top_competitors"] = [
        {
            "domain": c.get("domain", "N/A"),
            "score": c.get("combined_score", 0),
            "esn": c.get("is_esn", False),
            "relevance": c.get("relevance_score", 0),
            "source": c.get("source", "unknown"),
        }
        for c in sorted_competitors
    ]

    # Top exclus (avec scores élevés)
    sorted_excluded = sorted(
        excluded_candidates,
        key=lambda x: x.get("combined_score", 0),
        reverse=True,
    )[:10]
    analysis["top_excluded"] = [
        {
            "domain": e.get("domain", "N/A"),
            "score": e.get("combined_score", 0),
            "reason": e.get("exclusion_reason", "Unknown"),
            "esn": e.get("is_esn", False),
        }
        for e in sorted_excluded
    ]

    # Détection de problèmes
    if len(competitors) == 0 and total_evaluated > 0:
        analysis["issues"].append(
            "⚠️ Aucun concurrent inclus malgré des candidats évalués"
        )

    if len(excluded_candidates) > len(competitors) * 10:
        analysis["issues"].append(
            f"⚠️ Taux d'exclusion très élevé: {len(excluded_candidates)} exclus pour {len(competitors)} inclus"
        )

    # Vérifier les candidats non évalués par LLM
    not_evaluated = [
        item
        for item in all_items
        if "Not evaluated by LLM" in str(item.get("reason", ""))
    ]
    if not_evaluated:
        analysis["issues"].append(
            f"⚠️ {len(not_evaluated)} candidats non évalués par le LLM (scores par défaut)"
        )

    # Vérifier les domaines problématiques
    problematic_domains = [
        item.get("domain", "")
        for item in all_items
        if any(
            pattern in item.get("domain", "").lower()
            for pattern in [
                "bpifrance",
                "billetweb",
                "pagesjaunes",
                "univ-",
                "universit",
                "sciencespo",
                "esilv",
                "devinci",
            ]
        )
    ]
    if problematic_domains:
        analysis["issues"].append(
            f"⚠️ {len(problematic_domains)} domaines problématiques détectés (universités, annuaires, etc.)"
        )

    return analysis


async def analyze_execution(execution_id_str: str):
    """Analyse une exécution de workflow."""
    try:
        execution_id = UUID(execution_id_str)
    except ValueError:
        print(f"❌ UUID invalide: {execution_id_str}")
        return

    async with AsyncSessionLocal() as db:
        execution = await get_workflow_execution(db, execution_id)

        if not execution:
            print(f"❌ Exécution {execution_id} non trouvée en base de données")
            return

        print("=" * 80)
        print(f"📊 ANALYSE DE L'EXÉCUTION: {execution_id}")
        print("=" * 80)

        # Informations générales
        print(f"\n🔹 Type de workflow: {execution.workflow_type}")
        print(f"🔹 Statut: {execution.status}")
        print(f"🔹 Succès: {'✅ Oui' if execution.was_success else '❌ Non'}")
        print(f"🔹 Début: {execution.start_time}")
        print(f"🔹 Fin: {execution.end_time}")
        if execution.duration_seconds:
            print(
                f"🔹 Durée: {format_duration(execution.duration_seconds)} ({execution.duration_seconds}s)"
            )

        if execution.error_message:
            print(f"\n❌ ERREUR:")
            print(f"   {execution.error_message}")

        # Données d'entrée
        print(f"\n📥 INPUT DATA:")
        if execution.input_data:
            print(json.dumps(execution.input_data, indent=2, ensure_ascii=False))
        else:
            print("   (vide)")

        # Données de sortie
        if execution.output_data:
            print(f"\n📤 OUTPUT DATA:")
            output = execution.output_data

            if execution.workflow_type == "competitor_search":
                analysis = analyze_competitor_results(output)
                
                print(f"\n📊 STATISTIQUES:")
                stats = analysis["statistics"]
                print(f"  • Total trouvé: {stats['total_found']}")
                print(f"  • Total évalué: {stats['total_evaluated']}")
                print(f"  • Inclus: {stats['included']}")
                print(f"  • Exclus: {stats['excluded']}")
                print(f"  • Taux d'inclusion: {stats['inclusion_rate']}")

                if analysis["sources"]:
                    print(f"\n🔍 SOURCES:")
                    for source, count in sorted(
                        analysis["sources"].items(), key=lambda x: x[1], reverse=True
                    ):
                        print(f"  • {source}: {count}")

                if analysis["exclusion_reasons"]:
                    print(f"\n🚫 RAISONS D'EXCLUSION:")
                    for reason, count in sorted(
                        analysis["exclusion_reasons"].items(),
                        key=lambda x: x[1],
                        reverse=True,
                    ):
                        print(f"  • {reason}: {count}")

                if analysis["score_distribution"]:
                    dist = analysis["score_distribution"]
                    print(f"\n📈 DISTRIBUTION DES SCORES:")
                    print(f"  • Min: {dist['min']:.3f}")
                    print(f"  • Max: {dist['max']:.3f}")
                    print(f"  • Moyenne: {dist['mean']:.3f}")
                    print(f"  • Médiane: {dist['median']:.3f}")
                    print(f"  • Nombre de scores: {dist['count']}")

                if analysis["esn_distribution"]:
                    esn_dist = analysis["esn_distribution"]
                    print(f"\n🏢 DISTRIBUTION ESN:")
                    print(f"  • ESN: {esn_dist['esn']}")
                    print(f"  • Non-ESN: {esn_dist['non_esn']}")

                if analysis["business_types"]:
                    print(f"\n💼 TYPES DE BUSINESS:")
                    for btype, count in sorted(
                        analysis["business_types"].items(),
                        key=lambda x: x[1],
                        reverse=True,
                    ):
                        print(f"  • {btype}: {count}")

                if analysis["strategies"]:
                    print(f"\n🎯 STRATÉGIES:")
                    for strategy, count in sorted(
                        analysis["strategies"].items(),
                        key=lambda x: x[1],
                        reverse=True,
                    ):
                        print(f"  • {strategy}: {count}")

                if analysis["top_competitors"]:
                    print(f"\n✅ TOP 10 CONCURRENTS INCLUS:")
                    for i, comp in enumerate(analysis["top_competitors"], 1):
                        esn_mark = "🏢" if comp["esn"] else "  "
                        print(
                            f"  {i:2d}. {esn_mark} {comp['domain']:40s} | Score: {comp['score']:.3f} | Relevance: {comp['relevance']:.2f} | Source: {comp['source']}"
                        )

                if analysis["top_excluded"]:
                    print(f"\n🚫 TOP 10 EXCLUS (scores élevés):")
                    for i, excl in enumerate(analysis["top_excluded"], 1):
                        esn_mark = "🏢" if excl["esn"] else "  "
                        print(
                            f"  {i:2d}. {esn_mark} {excl['domain']:40s} | Score: {excl['score']:.3f} | Raison: {excl['reason'][:50]}"
                        )

                if analysis["issues"]:
                    print(f"\n⚠️ PROBLÈMES DÉTECTÉS:")
                    for issue in analysis["issues"]:
                        print(f"  {issue}")

            else:
                # Autres types de workflows
                print(json.dumps(output, indent=2, ensure_ascii=False))

        print("\n" + "=" * 80)


if __name__ == "__main__":
    import sys

    execution_id = sys.argv[1] if len(sys.argv) > 1 else "633d086b-52d1-47c5-ae6b-6203d66b462e"
    asyncio.run(analyze_execution(execution_id))


