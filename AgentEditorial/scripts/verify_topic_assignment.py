#!/usr/bin/env python3
"""Vérifie si l'assignation des topic_id aux articles fonctionne correctement."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func
from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.models import (
    ClientArticle,
    CompetitorArticle,
    TopicCluster,
    TrendPipelineExecution,
)
from python_scripts.vectorstore.qdrant_client import (
    get_client_collection_name,
    get_competitor_collection_name,
    qdrant_client,
)


async def verify_topic_assignment(domain: str = "innosys.fr"):
    """Vérifie l'assignation des topic_id."""
    print(f"\n{'='*80}")
    print(f"VÉRIFICATION DE L'ASSIGNATION DES TOPIC_ID: {domain}")
    print(f"{'='*80}\n")
    
    async with AsyncSessionLocal() as db:
        # 1. Vérifier les articles client
        print("📰 1. ARTICLES CLIENT")
        print("-" * 80)
        stmt = select(func.count(ClientArticle.id))
        result = await db.execute(stmt)
        total_client = result.scalar() or 0
        
        stmt = select(func.count(ClientArticle.id)).where(
            ClientArticle.topic_id.isnot(None)
        )
        result = await db.execute(stmt)
        client_with_topic = result.scalar() or 0
        
        print(f"Total articles client: {total_client}")
        print(f"Articles avec topic_id: {client_with_topic}")
        print(f"Pourcentage: {(client_with_topic/total_client*100) if total_client > 0 else 0:.1f}%")
        
        if total_client > 0 and client_with_topic == 0:
            print("⚠️  PROBLÈME: Aucun article client n'a de topic_id")
        elif client_with_topic < total_client * 0.8:
            print(f"⚠️  ATTENTION: Seulement {client_with_topic}/{total_client} articles ont un topic_id")
        else:
            print("✅ OK: La plupart des articles client ont un topic_id")
        print()
        
        # 2. Vérifier les articles concurrents
        print("📰 2. ARTICLES CONCURRENTS")
        print("-" * 80)
        stmt = select(func.count(CompetitorArticle.id))
        result = await db.execute(stmt)
        total_competitor = result.scalar() or 0
        
        stmt = select(func.count(CompetitorArticle.id)).where(
            CompetitorArticle.topic_id.isnot(None)
        )
        result = await db.execute(stmt)
        competitor_with_topic = result.scalar() or 0
        
        print(f"Total articles concurrents: {total_competitor}")
        print(f"Articles avec topic_id: {competitor_with_topic}")
        print(f"Pourcentage: {(competitor_with_topic/total_competitor*100) if total_competitor > 0 else 0:.1f}%")
        
        if total_competitor > 0 and competitor_with_topic == 0:
            print("⚠️  PROBLÈME: Aucun article concurrent n'a de topic_id")
        elif competitor_with_topic < total_competitor * 0.8:
            print(f"⚠️  ATTENTION: Seulement {competitor_with_topic}/{total_competitor} articles ont un topic_id")
        else:
            print("✅ OK: La plupart des articles concurrents ont un topic_id")
        print()
        
        # 3. Vérifier les clusters
        print("📊 3. CLUSTERS")
        print("-" * 80)
        stmt = select(func.count(TopicCluster.id))
        result = await db.execute(stmt)
        total_clusters = result.scalar() or 0
        
        print(f"Total clusters: {total_clusters}")
        
        if total_clusters > 0:
            # Vérifier la distribution des topic_id
            stmt = select(
                TopicCluster.topic_id,
                func.count(TopicCluster.id).label("count")
            ).group_by(TopicCluster.topic_id)
            result = await db.execute(stmt)
            clusters_by_topic = {row[0]: row[1] for row in result.all()}
            
            print(f"Clusters par topic_id: {clusters_by_topic}")
        print()
        
        # 4. Vérifier Qdrant
        print("🔍 4. VÉRIFICATION QDRANT")
        print("-" * 80)
        client_collection = get_client_collection_name(domain)
        competitor_collection = get_competitor_collection_name(domain)
        
        if qdrant_client.collection_exists(client_collection):
            collection_info = qdrant_client.client.get_collection(client_collection)
            print(f"Collection client: {client_collection}")
            print(f"  - Points: {collection_info.points_count}")
            
            # Vérifier quelques points pour voir s'ils ont topic_id
            try:
                points = qdrant_client.client.scroll(
                    collection_name=client_collection,
                    limit=10,
                )[0]
                
                points_with_topic = sum(
                    1 for p in points
                    if p.payload and "topic_id" in p.payload
                )
                print(f"  - Points avec topic_id (échantillon 10): {points_with_topic}/10")
            except Exception as e:
                print(f"  - Erreur lors de la vérification: {e}")
        else:
            print(f"Collection client n'existe pas: {client_collection}")
        
        if qdrant_client.collection_exists(competitor_collection):
            collection_info = qdrant_client.client.get_collection(competitor_collection)
            print(f"Collection concurrent: {competitor_collection}")
            print(f"  - Points: {collection_info.points_count}")
            
            # Vérifier quelques points
            try:
                points = qdrant_client.client.scroll(
                    collection_name=competitor_collection,
                    limit=10,
                )[0]
                
                points_with_topic = sum(
                    1 for p in points
                    if p.payload and "topic_id" in p.payload
                )
                print(f"  - Points avec topic_id (échantillon 10): {points_with_topic}/10")
            except Exception as e:
                print(f"  - Erreur lors de la vérification: {e}")
        else:
            print(f"Collection concurrent n'existe pas: {competitor_collection}")
        print()
        
        # 5. Vérifier le dernier trend pipeline
        print("🔄 5. DERNIER TREND PIPELINE")
        print("-" * 80)
        stmt = (
            select(TrendPipelineExecution)
            .where(
                TrendPipelineExecution.client_domain == domain,
                TrendPipelineExecution.is_valid == True,
            )
            .order_by(TrendPipelineExecution.start_time.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        trend_exec = result.scalar_one_or_none()
        
        if trend_exec:
            print(f"Execution ID: {trend_exec.execution_id}")
            print(f"Status Stage 1: {trend_exec.stage_1_clustering_status}")
            print(f"Status Stage 2: {trend_exec.stage_2_temporal_status}")
            print(f"Status Stage 3: {trend_exec.stage_3_llm_status}")
            print(f"Start time: {trend_exec.start_time}")
        else:
            print("Aucun trend pipeline trouvé")
        print()
        
        # 6. Résumé
        print("📊 RÉSUMÉ")
        print("-" * 80)
        total_articles = total_client + total_competitor
        total_with_topic = client_with_topic + competitor_with_topic
        
        print(f"Total articles: {total_articles}")
        print(f"Articles avec topic_id: {total_with_topic}")
        print(f"Pourcentage global: {(total_with_topic/total_articles*100) if total_articles > 0 else 0:.1f}%")
        
        if total_articles > 0:
            if total_with_topic == 0:
                print("❌ PROBLÈME CRITIQUE: Aucun article n'a de topic_id")
                print("   → L'assignation ne fonctionne pas correctement")
            elif total_with_topic < total_articles * 0.5:
                print("⚠️  PROBLÈME: Moins de 50% des articles ont un topic_id")
                print("   → L'assignation est partielle")
            else:
                print("✅ OK: La plupart des articles ont un topic_id")
                if client_with_topic == 0:
                    print("⚠️  ATTENTION: Les articles client n'ont pas de topic_id")
                    print("   → Problème spécifique aux articles client")
        print()


async def main():
    """Point d'entrée principal."""
    domain = sys.argv[1] if len(sys.argv) > 1 else "innosys.fr"
    await verify_topic_assignment(domain)


if __name__ == "__main__":
    asyncio.run(main())



