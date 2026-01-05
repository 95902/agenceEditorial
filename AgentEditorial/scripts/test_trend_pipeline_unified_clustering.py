#!/usr/bin/env python3
"""Test du trend pipeline avec clustering unifié (articles client + concurrents)."""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from python_scripts.database.db_session import AsyncSessionLocal
from sqlalchemy import select, func
from python_scripts.database.models import (
    ClientArticle,
    CompetitorArticle,
    TrendPipelineExecution,
)


async def check_articles_before():
    """Vérifier l'état des articles avant le clustering."""
    async with AsyncSessionLocal() as db:
        # Articles client
        stmt = select(func.count(ClientArticle.id))
        result = await db.execute(stmt)
        total_client = result.scalar() or 0
        
        stmt = select(func.count(ClientArticle.id)).where(
            ClientArticle.topic_id.isnot(None)
        )
        result = await db.execute(stmt)
        client_with_topic = result.scalar() or 0
        
        # Articles concurrents
        stmt = select(func.count(CompetitorArticle.id))
        result = await db.execute(stmt)
        total_competitor = result.scalar() or 0
        
        stmt = select(func.count(CompetitorArticle.id)).where(
            CompetitorArticle.topic_id.isnot(None)
        )
        result = await db.execute(stmt)
        competitor_with_topic = result.scalar() or 0
        
        print(f"\n📊 ÉTAT AVANT LE CLUSTERING")
        print(f"{'='*80}")
        print(f"Articles client: {client_with_topic}/{total_client} avec topic_id")
        print(f"Articles concurrents: {competitor_with_topic}/{total_competitor} avec topic_id")
        
        return {
            "client_total": total_client,
            "client_with_topic": client_with_topic,
            "competitor_total": total_competitor,
            "competitor_with_topic": competitor_with_topic,
        }


async def launch_trend_pipeline(client_domain: str = "innosys.fr") -> str:
    """Lancer le trend pipeline."""
    print(f"\n🚀 LANCEMENT DU TREND PIPELINE")
    print(f"{'='*80}")
    print(f"Client domain: {client_domain}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "http://localhost:8000/api/v1/trend-pipeline/analyze",
            json={
                "client_domain": client_domain,
                "time_window_days": 365,
                "skip_llm": False,
                "skip_gap_analysis": False,
            },
        )
        
        if response.status_code != 202:
            print(f"❌ Erreur: {response.status_code}")
            print(response.text)
            sys.exit(1)
        
        data = response.json()
        execution_id = data["execution_id"]
        print(f"✅ Trend pipeline lancé")
        print(f"Execution ID: {execution_id}")
        
        return execution_id


async def wait_for_completion(execution_id: str, max_wait_minutes: int = 30):
    """Attendre la fin du trend pipeline."""
    print(f"\n⏳ ATTENTE DE LA FIN DU PIPELINE")
    print(f"{'='*80}")
    
    start_time = time.time()
    max_wait_seconds = max_wait_minutes * 60
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            elapsed = time.time() - start_time
            
            if elapsed > max_wait_seconds:
                print(f"❌ Timeout après {max_wait_minutes} minutes")
                return False
            
            response = await client.get(
                f"http://localhost:8000/api/v1/trend-pipeline/{execution_id}/status"
            )
            
            if response.status_code != 200:
                print(f"⚠️  Erreur lors de la vérification: {response.status_code}")
                await asyncio.sleep(10)
                continue
            
            data = response.json()
            stage_1 = data.get("stage_1_clustering_status", "unknown")
            stage_2 = data.get("stage_2_temporal_status", "unknown")
            stage_3 = data.get("stage_3_llm_status", "unknown")
            stage_4 = data.get("stage_4_gap_status", "unknown")
            
            print(
                f"[{elapsed:.0f}s] Stage 1: {stage_1} | Stage 2: {stage_2} | "
                f"Stage 3: {stage_3} | Stage 4: {stage_4}"
            )
            
            if stage_1 == "completed" and stage_2 == "completed" and stage_3 == "completed" and stage_4 == "completed":
                print(f"✅ Pipeline terminé en {elapsed:.0f} secondes")
                return True
            
            if stage_1 == "failed" or stage_2 == "failed" or stage_3 == "failed" or stage_4 == "failed":
                print(f"❌ Pipeline échoué")
                return False
            
            await asyncio.sleep(10)


async def check_articles_after():
    """Vérifier l'état des articles après le clustering."""
    async with AsyncSessionLocal() as db:
        # Articles client
        stmt = select(func.count(ClientArticle.id))
        result = await db.execute(stmt)
        total_client = result.scalar() or 0
        
        stmt = select(func.count(ClientArticle.id)).where(
            ClientArticle.topic_id.isnot(None)
        )
        result = await db.execute(stmt)
        client_with_topic = result.scalar() or 0
        
        # Articles concurrents
        stmt = select(func.count(CompetitorArticle.id))
        result = await db.execute(stmt)
        total_competitor = result.scalar() or 0
        
        stmt = select(func.count(CompetitorArticle.id)).where(
            CompetitorArticle.topic_id.isnot(None)
        )
        result = await db.execute(stmt)
        competitor_with_topic = result.scalar() or 0
        
        print(f"\n📊 ÉTAT APRÈS LE CLUSTERING")
        print(f"{'='*80}")
        print(f"Articles client: {client_with_topic}/{total_client} avec topic_id")
        print(f"Articles concurrents: {competitor_with_topic}/{total_competitor} avec topic_id")
        
        # Vérifier le dernier trend pipeline
        stmt = (
            select(TrendPipelineExecution)
            .where(
                TrendPipelineExecution.client_domain == "innosys.fr",
                TrendPipelineExecution.stage_1_clustering_status == "completed",
            )
            .order_by(TrendPipelineExecution.start_time.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        trend_exec = result.scalar_one_or_none()
        
        if trend_exec:
            print(f"\n📈 DERNIER TREND PIPELINE")
            print(f"{'='*80}")
            print(f"Execution ID: {trend_exec.execution_id}")
            print(f"Total clusters: {trend_exec.total_clusters}")
            print(f"Total articles: {trend_exec.total_articles}")
            print(f"Stage 1: {trend_exec.stage_1_clustering_status}")
            print(f"Stage 2: {trend_exec.stage_2_temporal_status}")
            print(f"Stage 3: {trend_exec.stage_3_llm_status}")
            print(f"Stage 4: {trend_exec.stage_4_gap_status}")
        
        return {
            "client_total": total_client,
            "client_with_topic": client_with_topic,
            "competitor_total": total_competitor,
            "competitor_with_topic": competitor_with_topic,
        }


async def main():
    """Point d'entrée principal."""
    client_domain = sys.argv[1] if len(sys.argv) > 1 else "innosys.fr"
    
    print(f"\n{'='*80}")
    print(f"TEST DU TREND PIPELINE AVEC CLUSTERING UNIFIÉ")
    print(f"{'='*80}")
    
    # 1. Vérifier l'état initial
    state_before = await check_articles_before()
    
    # 2. Lancer le trend pipeline
    execution_id = await launch_trend_pipeline(client_domain)
    
    # 3. Attendre la fin
    success = await wait_for_completion(execution_id, max_wait_minutes=30)
    
    if not success:
        print("\n❌ Le pipeline n'a pas terminé correctement")
        sys.exit(1)
    
    # 4. Vérifier l'état final
    state_after = await check_articles_after()
    
    # 5. Résumé
    print(f"\n📋 RÉSUMÉ")
    print(f"{'='*80}")
    
    client_improvement = state_after["client_with_topic"] - state_before["client_with_topic"]
    competitor_improvement = state_after["competitor_with_topic"] - state_before["competitor_with_topic"]
    
    print(f"Articles client avec topic_id:")
    print(f"  Avant: {state_before['client_with_topic']}/{state_before['client_total']}")
    print(f"  Après: {state_after['client_with_topic']}/{state_after['client_total']}")
    print(f"  Amélioration: +{client_improvement}")
    
    if state_after["client_total"] > 0:
        percentage = (state_after["client_with_topic"] / state_after["client_total"]) * 100
        print(f"  Pourcentage: {percentage:.1f}%")
        
        if percentage >= 80:
            print("  ✅ EXCELLENT: La plupart des articles client ont un topic_id")
        elif percentage >= 50:
            print("  ⚠️  PARTIEL: Seulement la moitié des articles client ont un topic_id")
        else:
            print("  ❌ PROBLÈME: Peu d'articles client ont un topic_id")
    
    print(f"\nArticles concurrents avec topic_id:")
    print(f"  Avant: {state_before['competitor_with_topic']}/{state_before['competitor_total']}")
    print(f"  Après: {state_after['competitor_with_topic']}/{state_after['competitor_total']}")
    print(f"  Amélioration: +{competitor_improvement}")
    
    if state_after["competitor_total"] > 0:
        percentage = (state_after["competitor_with_topic"] / state_after["competitor_total"]) * 100
        print(f"  Pourcentage: {percentage:.1f}%")
    
    print(f"\n{'='*80}")
    print("✅ Test terminé")


if __name__ == "__main__":
    asyncio.run(main())



