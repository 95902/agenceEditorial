#!/usr/bin/env python3
"""Test de charge concurrente pour la route GET /api/v1/sites/{domain}/audit.

Ce script lance 10 requêtes simultanées vers la route /audit pour :
1. Détecter les race conditions (multiples orchestrators créés)
2. Mesurer les performances (temps de réponse, latence)
3. Identifier les problèmes de synchronisation
4. Valider la cohérence des réponses

Usage:
    python scripts/test_audit_concurrent.py --domain innosys.fr
    python scripts/test_audit_concurrent.py --domain innosys.fr --num-requests 20
"""

from __future__ import annotations

import asyncio
import argparse
import json
import sys
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
from datetime import datetime
from collections import Counter

import httpx

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.models import WorkflowExecution
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession


API_BASE_URL = "http://localhost:8000/api/v1"
DEFAULT_NUM_REQUESTS = 10
DEFAULT_TIMEOUT = 30.0


@dataclass
class RequestResult:
    """Résultat d'une requête individuelle."""
    request_id: int
    status_code: int
    response_time_ms: float
    execution_id: Optional[str] = None
    response_type: Optional[str] = None  # "SiteAuditResponse" ou "PendingAuditResponse"
    error: Optional[str] = None
    data_status: Optional[Dict[str, bool]] = None
    timestamp: str = ""


@dataclass
class TestResults:
    """Résultats complets du test."""
    domain: str
    num_requests: int
    start_time: str
    end_time: str
    duration_seconds: float
    results: List[RequestResult]
    orchestrators_created: int
    unique_execution_ids: List[str]
    statistics: Dict[str, Any]
    issues: List[str]


async def make_audit_request(
    client: httpx.AsyncClient,
    domain: str,
    request_id: int,
    timeout: float = DEFAULT_TIMEOUT,
) -> RequestResult:
    """Effectue une requête GET /sites/{domain}/audit."""
    start_time = time.time()
    timestamp = datetime.now().isoformat()
    
    try:
        response = await client.get(
            f"{API_BASE_URL}/sites/{domain}/audit",
            timeout=timeout,
        )
        response_time_ms = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            data = response.json()
            
            # Déterminer le type de réponse
            response_type = None
            execution_id = None
            data_status = None
            
            if "execution_id" in data:
                # PendingAuditResponse
                response_type = "PendingAuditResponse"
                execution_id = data.get("execution_id")
                if "data_status" in data:
                    data_status = data["data_status"]
            else:
                # SiteAuditResponse
                response_type = "SiteAuditResponse"
            
            return RequestResult(
                request_id=request_id,
                status_code=response.status_code,
                response_time_ms=response_time_ms,
                execution_id=execution_id,
                response_type=response_type,
                data_status=data_status,
                timestamp=timestamp,
            )
        else:
            return RequestResult(
                request_id=request_id,
                status_code=response.status_code,
                response_time_ms=response_time_ms,
                error=f"HTTP {response.status_code}: {response.text[:200]}",
                timestamp=timestamp,
            )
    
    except httpx.TimeoutException:
        response_time_ms = (time.time() - start_time) * 1000
        return RequestResult(
            request_id=request_id,
            status_code=0,
            response_time_ms=response_time_ms,
            error="Timeout",
            timestamp=timestamp,
        )
    
    except Exception as e:
        response_time_ms = (time.time() - start_time) * 1000
        return RequestResult(
            request_id=request_id,
            status_code=0,
            response_time_ms=response_time_ms,
            error=str(e),
            timestamp=timestamp,
        )


async def count_orchestrators_created(
    db: AsyncSession,
    domain: str,
    start_time: datetime,
) -> int:
    """Compte le nombre d'orchestrators créés pour un domaine après une date."""
    stmt = (
        select(WorkflowExecution)
        .where(
            WorkflowExecution.workflow_type == "audit_orchestrator",
            WorkflowExecution.input_data["domain"].astext == domain,
            WorkflowExecution.created_at >= start_time,
        )
    )
    result = await db.execute(stmt)
    executions = result.scalars().all()
    return len(executions)


async def get_orchestrator_execution_ids(
    db: AsyncSession,
    domain: str,
    start_time: datetime,
) -> List[str]:
    """Récupère les IDs des orchestrators créés pour un domaine après une date."""
    stmt = (
        select(WorkflowExecution)
        .where(
            WorkflowExecution.workflow_type == "audit_orchestrator",
            WorkflowExecution.input_data["domain"].astext == domain,
            WorkflowExecution.created_at >= start_time,
        )
        .order_by(desc(WorkflowExecution.created_at))
    )
    result = await db.execute(stmt)
    executions = result.scalars().all()
    return [str(exec.execution_id) for exec in executions]


def calculate_statistics(results: List[RequestResult]) -> Dict[str, Any]:
    """Calcule les statistiques sur les temps de réponse."""
    response_times = [r.response_time_ms for r in results if r.error is None]
    
    if not response_times:
        return {
            "min_ms": 0,
            "max_ms": 0,
            "mean_ms": 0,
            "median_ms": 0,
            "p95_ms": 0,
            "p99_ms": 0,
        }
    
    response_times.sort()
    n = len(response_times)
    
    return {
        "min_ms": min(response_times),
        "max_ms": max(response_times),
        "mean_ms": sum(response_times) / n,
        "median_ms": response_times[n // 2],
        "p95_ms": response_times[int(n * 0.95)] if n > 0 else 0,
        "p99_ms": response_times[int(n * 0.99)] if n > 0 else 0,
    }


def identify_issues(
    results: List[RequestResult],
    orchestrators_created: int,
    unique_execution_ids: List[str],
    num_requests: int,
) -> List[str]:
    """Identifie les problèmes détectés dans les résultats."""
    issues = []
    
    # Vérifier les race conditions
    if orchestrators_created > 1:
        issues.append(
            f"🔴 RACE CONDITION DÉTECTÉE: {orchestrators_created} orchestrators créés "
            f"pour {num_requests} requêtes (attendu: 1)"
        )
    
    # Vérifier les erreurs
    errors = [r for r in results if r.error is not None]
    if errors:
        error_count = len(errors)
        error_types = Counter([r.error for r in errors])
        issues.append(
            f"⚠️ {error_count} erreur(s) détectée(s): {dict(error_types)}"
        )
    
    # Vérifier la cohérence des execution_id
    execution_ids = [r.execution_id for r in results if r.execution_id is not None]
    if len(execution_ids) > 0:
        unique_ids = set(execution_ids)
        if len(unique_ids) > 1:
            issues.append(
                f"⚠️ INCOHÉRENCE: {len(unique_ids)} execution_id différents retournés "
                f"({len(execution_ids)} requêtes avec execution_id)"
            )
    
    # Vérifier les timeouts
    timeouts = [r for r in results if r.error == "Timeout"]
    if timeouts:
        issues.append(f"⚠️ {len(timeouts)} timeout(s) détecté(s)")
    
    # Vérifier les codes de statut non-200
    non_200 = [r for r in results if r.status_code != 200 and r.status_code != 0]
    if non_200:
        status_codes = Counter([r.status_code for r in non_200])
        issues.append(
            f"⚠️ Codes de statut non-200: {dict(status_codes)}"
        )
    
    return issues


async def run_concurrent_test(
    domain: str,
    num_requests: int = DEFAULT_NUM_REQUESTS,
    timeout: float = DEFAULT_TIMEOUT,
) -> TestResults:
    """Lance le test de charge concurrente."""
    print(f"\n{'='*80}")
    print(f"Test de charge concurrente - Route /sites/{{domain}}/audit")
    print(f"{'='*80}")
    print(f"Domaine: {domain}")
    print(f"Nombre de requêtes: {num_requests}")
    print(f"Timeout par requête: {timeout}s")
    print(f"API Base URL: {API_BASE_URL}")
    print(f"\nLancement de {num_requests} requêtes simultanées...\n")
    
    start_time = datetime.now()
    start_time_iso = start_time.isoformat()
    
    # Lancer toutes les requêtes simultanément
    async with httpx.AsyncClient(timeout=timeout) as client:
        tasks = [
            make_audit_request(client, domain, i, timeout)
            for i in range(num_requests)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Convertir les exceptions en résultats d'erreur
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed_results.append(
                RequestResult(
                    request_id=i,
                    status_code=0,
                    response_time_ms=0,
                    error=str(result),
                    timestamp=datetime.now().isoformat(),
                )
            )
        else:
            processed_results.append(result)
    
    end_time = datetime.now()
    end_time_iso = end_time.isoformat()
    duration_seconds = (end_time - start_time).total_seconds()
    
    # Compter les orchestrators créés
    async with AsyncSessionLocal() as db:
        orchestrators_created = await count_orchestrators_created(
            db, domain, start_time
        )
        unique_execution_ids = await get_orchestrator_execution_ids(
            db, domain, start_time
        )
    
    # Calculer les statistiques
    statistics = calculate_statistics(processed_results)
    
    # Identifier les problèmes
    issues = identify_issues(
        processed_results,
        orchestrators_created,
        unique_execution_ids,
        num_requests,
    )
    
    return TestResults(
        domain=domain,
        num_requests=num_requests,
        start_time=start_time_iso,
        end_time=end_time_iso,
        duration_seconds=duration_seconds,
        results=processed_results,
        orchestrators_created=orchestrators_created,
        unique_execution_ids=unique_execution_ids,
        statistics=statistics,
        issues=issues,
    )


def print_results(results: TestResults) -> None:
    """Affiche les résultats du test."""
    print(f"\n{'='*80}")
    print("RÉSULTATS DU TEST")
    print(f"{'='*80}\n")
    
    print(f"Domaine testé: {results.domain}")
    print(f"Nombre de requêtes: {results.num_requests}")
    print(f"Durée totale: {results.duration_seconds:.2f}s")
    print(f"Début: {results.start_time}")
    print(f"Fin: {results.end_time}\n")
    
    # Statistiques de performance
    print("📊 STATISTIQUES DE PERFORMANCE")
    print("-" * 80)
    stats = results.statistics
    print(f"Temps de réponse minimum: {stats['min_ms']:.2f} ms")
    print(f"Temps de réponse maximum: {stats['max_ms']:.2f} ms")
    print(f"Temps de réponse moyen: {stats['mean_ms']:.2f} ms")
    print(f"Temps de réponse médian: {stats['median_ms']:.2f} ms")
    print(f"Temps de réponse p95: {stats['p95_ms']:.2f} ms")
    print(f"Temps de réponse p99: {stats['p99_ms']:.2f} ms")
    print()
    
    # Orchestrators créés
    print("🔍 ORCHESTRATORS CRÉÉS")
    print("-" * 80)
    print(f"Nombre d'orchestrators créés: {results.orchestrators_created}")
    print(f"Execution IDs uniques: {len(results.unique_execution_ids)}")
    if results.unique_execution_ids:
        print("IDs:")
        for exec_id in results.unique_execution_ids:
            print(f"  - {exec_id}")
    print()
    
    # Répartition des réponses
    print("📋 RÉPARTITION DES RÉPONSES")
    print("-" * 80)
    response_types = Counter([r.response_type for r in results.results if r.response_type])
    status_codes = Counter([r.status_code for r in results.results])
    print(f"Types de réponse: {dict(response_types)}")
    print(f"Codes de statut: {dict(status_codes)}")
    print()
    
    # Problèmes identifiés
    if results.issues:
        print("⚠️ PROBLÈMES IDENTIFIÉS")
        print("-" * 80)
        for issue in results.issues:
            print(f"  {issue}")
        print()
    else:
        print("✅ Aucun problème détecté\n")
    
    # Détails des requêtes
    print("📝 DÉTAILS DES REQUÊTES")
    print("-" * 80)
    for result in results.results:
        status_icon = "✅" if result.status_code == 200 else "❌"
        print(
            f"{status_icon} Requête #{result.request_id:2d}: "
            f"Status={result.status_code}, "
            f"Temps={result.response_time_ms:.2f}ms, "
            f"Type={result.response_type or 'N/A'}"
        )
        if result.execution_id:
            print(f"      Execution ID: {result.execution_id}")
        if result.error:
            print(f"      Erreur: {result.error}")


def save_results(results: TestResults, output_dir: Path) -> None:
    """Sauvegarde les résultats en JSON et Markdown."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Sauvegarder en JSON
    json_file = output_dir / f"audit_concurrent_test_{results.domain.replace('.', '_')}_{int(time.time())}.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(asdict(results), f, indent=2, ensure_ascii=False, default=str)
    print(f"\n💾 Résultats JSON sauvegardés: {json_file}")
    
    # Sauvegarder en Markdown
    md_file = output_dir / f"audit_concurrent_test_{results.domain.replace('.', '_')}_{int(time.time())}.md"
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(f"# Test de charge concurrente - Route /sites/{{domain}}/audit\n\n")
        f.write(f"**Date**: {results.start_time}\n")
        f.write(f"**Domaine**: {results.domain}\n")
        f.write(f"**Nombre de requêtes**: {results.num_requests}\n")
        f.write(f"**Durée totale**: {results.duration_seconds:.2f}s\n\n")
        
        f.write("## Statistiques de performance\n\n")
        stats = results.statistics
        f.write(f"- **Min**: {stats['min_ms']:.2f} ms\n")
        f.write(f"- **Max**: {stats['max_ms']:.2f} ms\n")
        f.write(f"- **Moyenne**: {stats['mean_ms']:.2f} ms\n")
        f.write(f"- **Médiane**: {stats['median_ms']:.2f} ms\n")
        f.write(f"- **p95**: {stats['p95_ms']:.2f} ms\n")
        f.write(f"- **p99**: {stats['p99_ms']:.2f} ms\n\n")
        
        f.write("## Orchestrators créés\n\n")
        f.write(f"- **Nombre**: {results.orchestrators_created}\n")
        f.write(f"- **Execution IDs uniques**: {len(results.unique_execution_ids)}\n")
        if results.unique_execution_ids:
            f.write("\n### IDs créés\n\n")
            for exec_id in results.unique_execution_ids:
                f.write(f"- `{exec_id}`\n")
        f.write("\n")
        
        if results.issues:
            f.write("## Problèmes identifiés\n\n")
            for issue in results.issues:
                f.write(f"- {issue}\n")
            f.write("\n")
        
        f.write("## Détails des requêtes\n\n")
        f.write("| ID | Status | Temps (ms) | Type | Execution ID | Erreur |\n")
        f.write("|----|--------|------------|------|--------------|--------|\n")
        for result in results.results:
            f.write(
                f"| {result.request_id} | {result.status_code} | "
                f"{result.response_time_ms:.2f} | {result.response_type or 'N/A'} | "
                f"{result.execution_id or 'N/A'} | {result.error or 'N/A'} |\n"
            )
    
    print(f"💾 Rapport Markdown sauvegardé: {md_file}")


async def main():
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Test de charge concurrente pour la route /sites/{domain}/audit"
    )
    parser.add_argument(
        "--domain",
        type=str,
        required=True,
        help="Domaine à tester (ex: innosys.fr)",
    )
    parser.add_argument(
        "--num-requests",
        type=int,
        default=DEFAULT_NUM_REQUESTS,
        help=f"Nombre de requêtes concurrentes (défaut: {DEFAULT_NUM_REQUESTS})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Timeout par requête en secondes (défaut: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="outputs/analysis",
        help="Répertoire de sortie pour les résultats (défaut: outputs/analysis)",
    )
    
    args = parser.parse_args()
    
    try:
        results = await run_concurrent_test(
            domain=args.domain,
            num_requests=args.num_requests,
            timeout=args.timeout,
        )
        
        print_results(results)
        
        output_dir = Path(args.output_dir)
        save_results(results, output_dir)
        
        # Code de sortie basé sur les problèmes détectés
        if results.issues:
            critical_issues = [i for i in results.issues if "🔴" in i]
            if critical_issues:
                print("\n❌ Test terminé avec des problèmes critiques")
                sys.exit(1)
            else:
                print("\n⚠️ Test terminé avec des avertissements")
                sys.exit(0)
        else:
            print("\n✅ Test terminé sans problème")
            sys.exit(0)
    
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrompu par l'utilisateur")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Erreur lors du test: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

