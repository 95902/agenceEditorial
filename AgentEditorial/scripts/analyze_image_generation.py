#!/usr/bin/env python3
"""Script pour analyser la génération d'image d'un article."""

import asyncio
import json
from uuid import UUID
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.models import GeneratedArticle, GeneratedArticleImage


async def analyze_image_generation(plan_id: str):
    """Analyse complète de la génération d'image pour un plan_id."""
    plan_uuid = UUID(plan_id)
    
    async with AsyncSessionLocal() as db:
        # Récupérer l'article
        stmt = select(GeneratedArticle).where(
            GeneratedArticle.plan_id == plan_uuid,
            GeneratedArticle.is_valid.is_(True),
        )
        result = await db.execute(stmt)
        article = result.scalar_one_or_none()
        
        if not article:
            print(f"❌ Article non trouvé pour plan_id: {plan_id}")
            return
        
        print("=" * 80)
        print("📄 ANALYSE DE LA GÉNÉRATION D'IMAGE")
        print("=" * 80)
        print(f"\n📋 Plan ID: {plan_id}")
        print(f"📌 Topic: {article.topic}")
        print(f"🔑 Keywords: {article.keywords}")
        print(f"🎭 Tone: {article.tone}")
        print(f"📊 Status: {article.status}")
        print(f"📈 Progress: {article.progress_percentage}%")
        print(f"⏰ Created: {article.created_at}")
        
        # Récupérer les images
        stmt_images = select(GeneratedArticleImage).where(
            GeneratedArticleImage.article_id == article.id
        )
        result_images = await db.execute(stmt_images)
        images = list(result_images.scalars().all())
        
        if not images:
            print("\n⚠️  Aucune image trouvée pour cet article")
            return
        
        print(f"\n🖼️  {len(images)} image(s) trouvée(s):\n")
        
        for idx, image in enumerate(images, 1):
            print("-" * 80)
            print(f"IMAGE #{idx}")
            print("-" * 80)
            
            print(f"\n📝 PROMPT UTILISÉ:")
            print(f"{'─' * 78}")
            if image.prompt:
                print(image.prompt)
            else:
                print("❌ Aucun prompt enregistré")
            
            print(f"\n🚫 NEGATIVE PROMPT:")
            print(f"{'─' * 78}")
            if image.negative_prompt:
                print(image.negative_prompt)
            else:
                print("ℹ️  Aucun negative prompt enregistré")
            
            print(f"\n📁 CHEMIN IMAGE:")
            print(f"{'─' * 78}")
            if image.local_path:
                path = Path(image.local_path)
                if path.exists():
                    print(f"✅ {image.local_path}")
                    print(f"   Taille: {path.stat().st_size / 1024:.2f} KB")
                else:
                    print(f"⚠️  {image.local_path} (fichier non trouvé)")
            else:
                print("❌ Aucun chemin enregistré")
            
            print(f"\n⚙️  PARAMÈTRES DE GÉNÉRATION:")
            print(f"{'─' * 78}")
            if image.generation_params:
                params = image.generation_params
                print(json.dumps(params, indent=2, ensure_ascii=False))
            else:
                print("ℹ️  Aucun paramètre enregistré")
            
            print(f"\n📊 QUALITÉ:")
            print(f"{'─' * 78}")
            if image.quality_score is not None:
                print(f"Score: {image.quality_score}/100")
            else:
                print("ℹ️  Score non évalué")
            
            if image.critique_details:
                print(f"\n📋 DÉTAILS DE LA CRITIQUE:")
                print(f"{'─' * 78}")
                critique = image.critique_details
                if isinstance(critique, dict):
                    print(json.dumps(critique, indent=2, ensure_ascii=False))
                else:
                    print(str(critique))
            
            print(f"\n🔄 RETRY:")
            print(f"{'─' * 78}")
            print(f"Nombre de tentatives: {image.retry_count}")
            print(f"Statut final: {image.final_status or 'N/A'}")
            
            print(f"\n⏱️  PERFORMANCE:")
            print(f"{'─' * 78}")
            if image.generation_time_seconds:
                print(f"Temps de génération: {image.generation_time_seconds:.2f} secondes")
            else:
                print("ℹ️  Temps non mesuré")
            
            print(f"\n📅 CRÉÉ LE:")
            print(f"{'─' * 78}")
            print(f"{image.created_at}")
        
        # Analyser le plan JSON si disponible
        if article.plan_json:
            print("\n" + "=" * 80)
            print("📋 PLAN DE L'ARTICLE")
            print("=" * 80)
            plan = article.plan_json
            if isinstance(plan, dict):
                print(json.dumps(plan, indent=2, ensure_ascii=False))
            else:
                print(str(plan))
        
        print("\n" + "=" * 80)
        print("✅ ANALYSE TERMINÉE")
        print("=" * 80)


async def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python scripts/analyze_image_generation.py <plan_id>")
        sys.exit(1)
    
    plan_id = sys.argv[1]
    await analyze_image_generation(plan_id)


if __name__ == "__main__":
    asyncio.run(main())


