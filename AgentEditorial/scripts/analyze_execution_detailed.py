#!/usr/bin/env python3
"""Analyse détaillée d'une exécution de workflow.

Analyse une exécution et ses workflows enfants pour comprendre ce qui s'est passé.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).parent.parent))

from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.crud_executions import get_workflow_execution
from python_scripts.database.models import WorkflowExecution
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def analyze_execution_detailed(execution_id_str: str) -> dict:
    """Analyse détaillée d'une exécution."""
    try:
        execution_id = UUID(execution_id_str)
    except ValueError:
        return {"error": f"UUID invalide: {execution_id_str}"}
    
    async with AsyncSessionLocal() as db:
        # Récupérer l'exécution principale
        execution = await get_workflow_execution(db, execution_id)
        
        if not execution:
            return {"error": f"Exécution {execution_id} non trouvée"}
        
        analysis = {
            "execution_id": str(execution.execution_id),
            "workflow_type": execution.workflow_type,
            "status": execution.status,
            "was_success": execution.was_success,
            "start_time": execution.start_time.isoformat() if execution.start_time else None,
            "end_time": execution.end_time.isoformat() if execution.end_time else None,
            "duration_seconds": execution.duration_seconds,
            "error_message": execution.error_message,
            "input_data": execution.input_data,
            "output_data": execution.output_data,
        }
        
        # Si c'est un orchestrator, récupérer les workflows enfants
        if execution.workflow_type == "audit_orchestrator":
            stmt = (
                select(WorkflowExecution)
                .where(
                    WorkflowExecution.parent_execution_id == execution_id,
                    WorkflowExecution.is_valid == True,
                )
                .order_by(WorkflowExecution.created_at)
            )
            result = await db.execute(stmt)
            child_workflows = list(result.scalars().all())
            
            analysis["child_workflows"] = []
            for child in child_workflows:
                analysis["child_workflows"].append({
                    "execution_id": str(child.execution_id),
                    "workflow_type": child.workflow_type,
                    "status": child.status,
                    "was_success": child.was_success,
                    "start_time": child.start_time.isoformat() if child.start_time else None,
                    "end_time": child.end_time.isoformat() if child.end_time else None,
                    "duration_seconds": child.duration_seconds,
                    "error_message": child.error_message,
                })
        
        return analysis


def print_analysis(analysis: dict) -> None:
    """Affiche l'analyse de manière lisible."""
    if "error" in analysis:
        print(f"❌ Erreur: {analysis['error']}")
        return
    
    print(f"\n{'='*80}")
    print(f"ANALYSE DÉTAILLÉE DE L'EXÉCUTION")
    print(f"{'='*80}\n")
    
    print(f"📋 INFORMATIONS GÉNÉRALES")
    print("-" * 80)
    print(f"  Execution ID: {analysis['execution_id']}")
    print(f"  Type: {analysis['workflow_type']}")
    print(f"  Statut: {analysis['status']}")
    print(f"  Succès: {'✅ Oui' if analysis['was_success'] else '❌ Non'}")
    print(f"  Début: {analysis['start_time']}")
    print(f"  Fin: {analysis['end_time']}")
    if analysis['duration_seconds']:
        minutes = analysis['duration_seconds'] // 60
        seconds = analysis['duration_seconds'] % 60
        print(f"  Durée: {minutes}m {seconds}s ({analysis['duration_seconds']}s)")
    print()
    
    if analysis.get('error_message'):
        print(f"❌ ERREUR")
        print("-" * 80)
        print(f"  {analysis['error_message']}")
        print()
    
    if analysis.get('input_data'):
        print(f"📥 INPUT DATA")
        print("-" * 80)
        print(json.dumps(analysis['input_data'], indent=2, ensure_ascii=False))
        print()
    
    if analysis.get('output_data'):
        print(f"📤 OUTPUT DATA")
        print("-" * 80)
        print(json.dumps(analysis['output_data'], indent=2, ensure_ascii=False))
        print()
    
    if analysis.get('child_workflows'):
        print(f"🔗 WORKFLOWS ENFANTS")
        print("-" * 80)
        for i, child in enumerate(analysis['child_workflows'], 1):
            print(f"\n  {i}. {child['workflow_type']}")
            print(f"     Execution ID: {child['execution_id']}")
            print(f"     Statut: {child['status']}")
            print(f"     Succès: {'✅ Oui' if child['was_success'] else '❌ Non'}")
            if child.get('start_time'):
                print(f"     Début: {child['start_time']}")
            if child.get('end_time'):
                print(f"     Fin: {child['end_time']}")
            if child.get('duration_seconds'):
                minutes = child['duration_seconds'] // 60
                seconds = child['duration_seconds'] % 60
                print(f"     Durée: {minutes}m {seconds}s")
            if child.get('error_message'):
                print(f"     ❌ Erreur: {child['error_message']}")
        print()
        
        # Résumé des workflows enfants
        print(f"📊 RÉSUMÉ DES WORKFLOWS ENFANTS")
        print("-" * 80)
        total = len(analysis['child_workflows'])
        completed = sum(1 for c in analysis['child_workflows'] if c['status'] == 'completed')
        failed = sum(1 for c in analysis['child_workflows'] if c['status'] == 'failed')
        running = sum(1 for c in analysis['child_workflows'] if c['status'] == 'running')
        pending = sum(1 for c in analysis['child_workflows'] if c['status'] == 'pending')
        
        print(f"  Total: {total}")
        print(f"  ✅ Complétés: {completed}")
        print(f"  ❌ Échoués: {failed}")
        print(f"  🔄 En cours: {running}")
        print(f"  ⏳ En attente: {pending}")
        print()


async def main():
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Analyse détaillée d'une exécution de workflow"
    )
    parser.add_argument(
        "execution_id",
        type=str,
        help="ID de l'exécution à analyser",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Fichier de sortie pour sauvegarder l'analyse JSON",
    )
    
    args = parser.parse_args()
    
    analysis = await analyze_execution_detailed(args.execution_id)
    print_analysis(analysis)
    
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False, default=str)
        print(f"💾 Analyse sauvegardée: {output_path}")
    
    if "error" in analysis:
        sys.exit(1)
    elif not analysis.get('was_success', False):
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

