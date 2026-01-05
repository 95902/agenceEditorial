#!/usr/bin/env python3
"""Vérifie les données en base pour comprendre pourquoi l'audit ne fonctionne pas."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.crud_profiles import get_site_profile_by_domain
from python_scripts.database.crud_client_articles import count_client_articles, list_client_articles
from python_scripts.database.crud_articles import count_competitor_articles
from python_scripts.database.models import (
    SiteProfile,
    WorkflowExecution,
    TrendPipelineExecution,
    ClientArticle,
    CompetitorArticle,
)


async def check_audit_data(domain: str = "innosys.fr"):
    """Vérifie toutes les données nécessaires pour l'audit."""
    print(f"\n{'='*80}")
    print(f"VÉRIFICATION DES DONNÉES POUR L'AUDIT: {domain}")
    print(f"{'='*80}\n")
    
    async with AsyncSessionLocal() as db:
        # 1. Site Profile
        print("📋 1. SITE PROFILE")
        print("-" * 80)
        profile = await get_site_profile_by_domain(db, domain)
        if profile:
            print(f"✅ Site profile trouvé (ID: {profile.id})")
            print(f"   - Domain: {profile.domain}")
            print(f"   - Analysis date: {profile.analysis_date}")
            print(f"   - Language level: {profile.language_level}")
            print(f"   - Editorial tone: {profile.editorial_tone}")
            print(f"   - Pages analyzed: {profile.pages_analyzed}")
            print(f"   - Activity domains: {profile.activity_domains}")
            print(f"   - Target audience: {profile.target_audience}")
            print(f"   - Keywords: {profile.keywords}")
            print(f"   - Content structure: {profile.content_structure}")
            print(f"   - Style features: {profile.style_features}")
        else:
            print(f"❌ Site profile NON trouvé")
        print()
        
        # 2. Competitor Search
        print("🔍 2. COMPETITOR SEARCH")
        print("-" * 80)
        stmt = (
            select(WorkflowExecution)
            .where(
                WorkflowExecution.workflow_type == "competitor_search",
                WorkflowExecution.status == "completed",
                WorkflowExecution.input_data["domain"].astext == domain,
                WorkflowExecution.is_valid == True,
            )
            .order_by(desc(WorkflowExecution.start_time))
            .limit(1)
        )
        result = await db.execute(stmt)
        competitor_exec = result.scalar_one_or_none()
        
        if competitor_exec:
            print(f"✅ Competitor search trouvé (Execution ID: {competitor_exec.execution_id})")
            print(f"   - Status: {competitor_exec.status}")
            print(f"   - Was success: {competitor_exec.was_success}")
            print(f"   - Start time: {competitor_exec.start_time}")
            print(f"   - End time: {competitor_exec.end_time}")
            
            if competitor_exec.output_data:
                competitors = competitor_exec.output_data.get("competitors", [])
                print(f"   - Nombre de concurrents: {len(competitors)}")
                validated = [c for c in competitors if c.get("validated", False) or c.get("manual", False)]
                print(f"   - Concurrents validés: {len(validated)}")
                if validated:
                    print(f"   - Domaines validés: {[c.get('domain') for c in validated[:5]]}")
            else:
                print(f"   ⚠️ output_data est None")
        else:
            print(f"❌ Competitor search NON trouvé")
        print()
        
        # 3. Client Articles
        print("📰 3. CLIENT ARTICLES")
        print("-" * 80)
        if profile:
            count = await count_client_articles(db, site_profile_id=profile.id)
            print(f"✅ Nombre d'articles client: {count}")
            
            # Vérifier le seuil
            import os
            min_required = int(os.getenv("MIN_CLIENT_ARTICLES_FOR_AUDIT", "5"))
            is_sufficient = count >= min_required
            print(f"   - Seuil requis: {min_required}")
            print(f"   - Suffisant: {'✅ Oui' if is_sufficient else '❌ Non'}")
            
            if count > 0:
                articles = await list_client_articles(db, site_profile_id=profile.id, limit=5)
                print(f"   - Exemples d'articles:")
                for article in articles[:3]:
                    print(f"     • {article.title[:60]}... (ID: {article.id})")
        else:
            print(f"❌ Pas de profile, impossible de vérifier les articles client")
        print()
        
        # 4. Competitor Articles
        print("📰 4. COMPETITOR ARTICLES")
        print("-" * 80)
        if competitor_exec and competitor_exec.output_data:
            competitors_data = competitor_exec.output_data.get("competitors", [])
            competitor_domains = [
                c.get("domain")
                for c in competitors_data
                if c.get("domain")
                and not c.get("excluded", False)
                and (c.get("validated", False) or c.get("manual", False))
            ]
            
            if competitor_domains:
                print(f"✅ Domaines de concurrents validés: {len(competitor_domains)}")
                total_count = 0
                for comp_domain in competitor_domains[:5]:
                    count = await count_competitor_articles(db, domain=comp_domain)
                    total_count += count
                    print(f"   - {comp_domain}: {count} articles")
                
                # Vérifier le seuil
                import os
                min_required = int(os.getenv("MIN_COMPETITOR_ARTICLES_FOR_AUDIT", "10"))
                is_sufficient = total_count >= min_required
                print(f"   - Total articles: {total_count}")
                print(f"   - Seuil requis: {min_required}")
                print(f"   - Suffisant: {'✅ Oui' if is_sufficient else '❌ Non'}")
            else:
                print(f"❌ Aucun domaine de concurrent validé")
        else:
            print(f"❌ Pas de competitor_exec ou output_data manquant")
        print()
        
        # 5. Trend Pipeline
        print("📊 5. TREND PIPELINE")
        print("-" * 80)
        stmt = (
            select(TrendPipelineExecution)
            .where(
                TrendPipelineExecution.client_domain == domain,
                TrendPipelineExecution.stage_1_clustering_status == "completed",
                TrendPipelineExecution.stage_2_temporal_status == "completed",
                TrendPipelineExecution.stage_3_llm_status == "completed",
                TrendPipelineExecution.is_valid == True,
            )
            .order_by(desc(TrendPipelineExecution.start_time))
            .limit(1)
        )
        result = await db.execute(stmt)
        trend_exec = result.scalar_one_or_none()
        
        if trend_exec:
            print(f"✅ Trend pipeline trouvé (Execution ID: {trend_exec.execution_id})")
            print(f"   - Stage 1 (clustering): {trend_exec.stage_1_clustering_status}")
            print(f"   - Stage 2 (temporal): {trend_exec.stage_2_temporal_status}")
            print(f"   - Stage 3 (LLM): {trend_exec.stage_3_llm_status}")
            print(f"   - Start time: {trend_exec.start_time}")
            print(f"   - End time: {trend_exec.end_time}")
        else:
            print(f"❌ Trend pipeline NON trouvé ou incomplet")
        print()
        
        # 6. Audit Orchestrator
        print("🎯 6. AUDIT ORCHESTRATOR")
        print("-" * 80)
        stmt = (
            select(WorkflowExecution)
            .where(
                WorkflowExecution.workflow_type == "audit_orchestrator",
                WorkflowExecution.input_data["domain"].astext == domain,
                WorkflowExecution.is_valid == True,
            )
            .order_by(desc(WorkflowExecution.created_at))
            .limit(5)
        )
        result = await db.execute(stmt)
        orchestrators = list(result.scalars().all())
        
        if orchestrators:
            print(f"✅ {len(orchestrators)} orchestrator(s) trouvé(s)")
            for i, orch in enumerate(orchestrators, 1):
                print(f"\n   Orchestrator {i}:")
                print(f"   - Execution ID: {orch.execution_id}")
                print(f"   - Status: {orch.status}")
                print(f"   - Was success: {orch.was_success}")
                print(f"   - Start time: {orch.start_time}")
                print(f"   - End time: {orch.end_time}")
                if orch.duration_seconds:
                    print(f"   - Duration: {orch.duration_seconds}s")
                if orch.error_message:
                    print(f"   - Error: {orch.error_message}")
        else:
            print(f"❌ Aucun orchestrator trouvé")
        print()
        
        # 7. Résumé et diagnostic
        print("📊 RÉSUMÉ ET DIAGNOSTIC")
        print("-" * 80)
        
        has_profile = profile is not None
        has_competitors = competitor_exec is not None
        has_client_articles = profile and await count_client_articles(db, site_profile_id=profile.id) >= 5
        has_competitor_articles = False
        if competitor_exec and competitor_exec.output_data:
            competitors_data = competitor_exec.output_data.get("competitors", [])
            competitor_domains = [
                c.get("domain")
                for c in competitors_data
                if c.get("domain")
                and not c.get("excluded", False)
                and (c.get("validated", False) or c.get("manual", False))
            ]
            if competitor_domains:
                total_count = sum(
                    await count_competitor_articles(db, domain=comp_domain)
                    for comp_domain in competitor_domains
                )
                has_competitor_articles = total_count >= 10
        has_trend_pipeline = trend_exec is not None
        
        print(f"✅ Profile: {'Oui' if has_profile else '❌ Non'}")
        print(f"✅ Competitors: {'Oui' if has_competitors else '❌ Non'}")
        print(f"✅ Client articles: {'Oui' if has_client_articles else '❌ Non'}")
        print(f"✅ Competitor articles: {'Oui' if has_competitor_articles else '❌ Non'}")
        print(f"✅ Trend pipeline: {'Oui' if has_trend_pipeline else '❌ Non'}")
        print()
        
        all_essential = has_profile and has_competitors and has_trend_pipeline
        all_complete = all_essential and has_client_articles and has_competitor_articles
        
        if all_complete:
            print("✅ TOUTES LES DONNÉES SONT DISPONIBLES")
            print("   → La route devrait retourner SiteAuditResponse")
        elif all_essential:
            print("⚠️ DONNÉES ESSENTIELLES DISPONIBLES (mais articles manquants)")
            print("   → La route devrait retourner SiteAuditResponse (avec les corrections récentes)")
        else:
            print("❌ DONNÉES MANQUANTES")
            missing = []
            if not has_profile:
                missing.append("Profile")
            if not has_competitors:
                missing.append("Competitors")
            if not has_trend_pipeline:
                missing.append("Trend pipeline")
            print(f"   → Données manquantes: {', '.join(missing)}")
            print("   → La route devrait lancer les workflows manquants")
        print()


async def main():
    """Point d'entrée principal."""
    domain = sys.argv[1] if len(sys.argv) > 1 else "innosys.fr"
    await check_audit_data(domain)


if __name__ == "__main__":
    asyncio.run(main())



