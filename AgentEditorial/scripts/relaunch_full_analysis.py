#!/usr/bin/env python3
"""
Relance l'analyse complète depuis le début avec max_competitors=35

Ce script :
1. Lance la recherche de concurrents avec max_competitors=35
2. Attend la complétion
3. Analyse les résultats
4. Compare avec l'ancienne configuration (10 concurrents)
"""

import asyncio
import httpx
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

API_BASE_URL = "http://localhost:8000/api/v1"


async def wait_for_completion(client: httpx.AsyncClient, execution_id: str, max_wait: int = 600):
    """Attend la complétion d'une exécution."""
    start_time = time.time()
    check_interval = 5
    
    print("⏳ Attente de la complétion...")
    
    while time.time() - start_time < max_wait:
        await asyncio.sleep(check_interval)
        
        try:
            status_response = await client.get(
                f"{API_BASE_URL}/executions/{execution_id}",
                timeout=10.0
            )
            
            if status_response.status_code != 200:
                continue
            
            status_data = status_response.json()
            status = status_data.get("status")
            
            if status == "completed":
                print(f"✅ Exécution terminée !\n")
                return True
            elif status == "failed":
                print(f"\n❌ Exécution échouée")
                error = status_data.get("error", "Erreur inconnue")
                print(f"   Erreur: {error}")
                return False
            else:
                progress = status_data.get("progress", 0)
                print(f"   Statut: {status} ({progress}%)", end="\r")
        except Exception as e:
            print(f"   Erreur lors de la vérification: {e}", end="\r")
            continue
    
    print(f"\n⚠️ Timeout après {max_wait} secondes")
    return False


async def launch_competitor_search(client: httpx.AsyncClient, domain: str, max_competitors: int = 35):
    """Lance une recherche de concurrents."""
    print(f"🚀 Lancement de la recherche de concurrents")
    print(f"   Domaine: {domain}")
    print(f"   max_competitors: {max_competitors}\n")
    
    try:
        response = await client.post(
            f"{API_BASE_URL}/competitors/search",
            json={"domain": domain, "max_competitors": max_competitors},
            timeout=30.0
        )
        
        if response.status_code != 202:
            print(f"❌ Erreur HTTP {response.status_code}")
            print(response.text)
            return None
        
        data = response.json()
        execution_id = data.get("execution_id")
        
        print(f"✅ Recherche lancée")
        print(f"   Execution ID: {execution_id}\n")
        
        # Attendre la complétion
        completed = await wait_for_completion(client, execution_id)
        
        if not completed:
            return None
        
        return execution_id
    
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return None


async def get_competitors_results(client: httpx.AsyncClient, domain: str):
    """Récupère les résultats des concurrents."""
    try:
        response = await client.get(
            f"{API_BASE_URL}/competitors/{domain}",
            timeout=30.0
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"⚠️ Impossible de récupérer les concurrents: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return None


async def analyze_results(domain: str):
    """Analyse les résultats depuis la base de données."""
    from sqlalchemy import select, desc
    from sqlalchemy.ext.asyncio import AsyncSession
    
    from python_scripts.database.db_session import AsyncSessionLocal
    from python_scripts.database.models import WorkflowExecution
    
    async with AsyncSessionLocal() as db:
        # Récupérer la dernière exécution
        stmt = (
            select(WorkflowExecution)
            .where(
                WorkflowExecution.workflow_type == "competitor_search",
                WorkflowExecution.status == "completed",
                WorkflowExecution.input_data["domain"].astext == domain,
            )
            .order_by(desc(WorkflowExecution.start_time))
            .limit(1)
        )
        
        result = await db.execute(stmt)
        execution = result.scalar_one_or_none()
        
        if not execution or not execution.output_data:
            print("❌ Aucune exécution trouvée")
            return
        
        output_data = execution.output_data
        
        total_found = output_data.get("total_found", 0)
        total_evaluated = output_data.get("total_evaluated", 0)
        competitors = output_data.get("competitors", [])
        excluded_candidates = output_data.get("excluded_candidates", [])
        max_competitors_requested = execution.input_data.get("max_competitors", 10)
        
        print("="*80)
        print("ANALYSE DES RÉSULTATS")
        print("="*80)
        print(f"\n📊 STATISTIQUES")
        print("-"*80)
        print(f"max_competitors demandé: {max_competitors_requested}")
        print(f"Total candidats trouvés: {total_found}")
        print(f"Total candidats évalués: {total_evaluated}")
        print(f"Concurrents inclus (final): {len(competitors)}")
        print(f"Concurrents exclus: {len(excluded_candidates)}")
        
        if competitors:
            print(f"\n✅ CONCURRENTS INCLUS ({len(competitors)})")
            print("-"*80)
            validated = [c for c in competitors if c.get("validated", False) or c.get("manual", False)]
            print(f"Concurrents validés: {len(validated)}")
            
            similarities = [c.get("relevance_score", 0) * 100 if c.get("relevance_score") else 0 for c in competitors]
            if similarities:
                print(f"Similarité moyenne: {sum(similarities)/len(similarities):.1f}%")
                print(f"  Min: {min(similarities):.1f}%, Max: {max(similarities):.1f}%")
            
            print(f"\nListe des concurrents:")
            for i, comp in enumerate(competitors, 1):
                domain_name = comp.get("domain", "N/A")
                similarity = comp.get("relevance_score", 0) * 100 if comp.get("relevance_score") else 0
                validated_marker = "✓" if (comp.get("validated", False) or comp.get("manual", False)) else " "
                print(f"{i:2d}. {domain_name:<45} {similarity:5.1f}% {validated_marker}")
        
        if excluded_candidates:
            exclusion_reasons = {}
            for candidate in excluded_candidates:
                reason = candidate.get("exclusion_reason", "Unknown")
                exclusion_reasons[reason] = exclusion_reasons.get(reason, 0) + 1
            
            print(f"\n❌ CONCURRENTS EXCLUS ({len(excluded_candidates)})")
            print("-"*80)
            print("Top 5 raisons d'exclusion:")
            for reason, count in sorted(exclusion_reasons.items(), key=lambda x: x[1], reverse=True)[:5]:
                percentage = (count / len(excluded_candidates)) * 100
                print(f"  {reason}: {count} ({percentage:.1f}%)")
        
        print("\n" + "="*80)
        print("COMPARAISON AVEC L'ANCIENNE CONFIGURATION")
        print("="*80)
        print(f"Ancienne config (max_competitors=10):")
        print(f"  - Concurrents inclus: 10")
        print(f"  - Concurrents exclus: 140")
        print(f"\nNouvelle config (max_competitors={max_competitors_requested}):")
        print(f"  - Concurrents inclus: {len(competitors)}")
        print(f"  - Concurrents exclus: {len(excluded_candidates)}")
        print(f"  - Amélioration: +{len(competitors) - 10} concurrents inclus")
        print("="*80)


async def main():
    """Point d'entrée principal."""
    domain = sys.argv[1] if len(sys.argv) > 1 else "innosys.fr"
    max_competitors = int(sys.argv[2]) if len(sys.argv) > 2 else 35
    
    print("="*80)
    print("RELANCE DE L'ANALYSE COMPLÈTE")
    print("="*80)
    print(f"Domaine: {domain}")
    print(f"max_competitors: {max_competitors}")
    print("="*80 + "\n")
    
    async with httpx.AsyncClient(timeout=600.0) as client:
        # 1. Lancer la recherche de concurrents
        execution_id = await launch_competitor_search(client, domain, max_competitors)
        
        if not execution_id:
            print("❌ Échec de la recherche de concurrents")
            return
        
        # 2. Récupérer les résultats via API
        print("📊 Récupération des résultats via API...\n")
        results = await get_competitors_results(client, domain)
        
        if results:
            competitors = results.get("competitors", [])
            print(f"✅ {len(competitors)} concurrents récupérés via API\n")
        
        # 3. Analyser depuis la base de données
        print("📈 Analyse détaillée depuis la base de données...\n")
        await analyze_results(domain)
        
        print("\n✅ Analyse terminée !")


if __name__ == "__main__":
    asyncio.run(main())


