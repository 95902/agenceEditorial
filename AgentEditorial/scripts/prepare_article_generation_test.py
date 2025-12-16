"""Script pour préparer un payload de test pour la génération d'articles à partir d'une exécution trend_pipeline."""

import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.models import TrendPipelineExecution, TopicCluster, SiteProfile
from python_scripts.database.crud_clusters import get_topic_clusters_by_analysis


async def prepare_article_generation_payload(execution_id: str) -> dict:
    """
    Prépare un payload JSON pour tester la génération d'articles.
    
    Args:
        execution_id: ID de l'exécution trend_pipeline
        
    Returns:
        Dictionnaire avec le payload JSON prêt à utiliser
    """
    async with AsyncSessionLocal() as db:
        # 1. Récupérer l'exécution trend_pipeline
        result = await db.execute(
            select(TrendPipelineExecution).where(
                TrendPipelineExecution.execution_id == execution_id
            )
        )
        execution = result.scalar_one_or_none()
        
        if not execution:
            raise ValueError(f"Exécution {execution_id} non trouvée")
        
        print(f"✓ Exécution trouvée: {execution_id}")
        print(f"  - Total clusters: {execution.total_clusters}")
        print(f"  - Client domain: {execution.client_domain}")
        
        # 2. Récupérer les clusters (priorité: core > adjacent > off_scope)
        clusters = await get_topic_clusters_by_analysis(
            db,
            execution.id,
            scope=None,  # Tous les scopes
            only_valid=True,
        )
        
        if not clusters:
            raise ValueError(f"Aucun cluster trouvé pour l'exécution {execution_id}")
        
        # Trier par scope (core > adjacent > off_scope) puis par taille
        def scope_priority(scope: str) -> int:
            return {"core": 0, "adjacent": 1, "off_scope": 2}.get(scope, 3)
        
        clusters_sorted = sorted(
            clusters,
            key=lambda c: (scope_priority(c.scope), -c.size)
        )
        
        # Prendre le meilleur cluster
        best_cluster = clusters_sorted[0]
        
        print(f"\n✓ Cluster sélectionné:")
        print(f"  - Topic ID: {best_cluster.topic_id}")
        print(f"  - Label: {best_cluster.label}")
        print(f"  - Scope: {best_cluster.scope}")
        print(f"  - Size: {best_cluster.size}")
        print(f"  - Coherence: {best_cluster.coherence_score}")
        
        # 3. Extraire les keywords du cluster (filtrer les stopwords)
        stopwords_fr = {
            "et", "de", "la", "pour", "les", "le", "en", "un", "une", "des", "du", "dans",
            "par", "sur", "avec", "est", "sont", "être", "avoir", "faire", "plus", "tout",
            "tous", "toute", "toutes", "cette", "ce", "ces", "son", "sa", "ses", "leur",
            "leurs", "qui", "que", "quoi", "où", "quand", "comment", "pourquoi", "comme"
        }
        
        top_terms = best_cluster.top_terms
        keywords = []
        
        if isinstance(top_terms, dict):
            # Format: {"terms": [{"word": "...", "score": ...}, ...]}
            terms_list = top_terms.get("terms", [])
            for t in terms_list[:15]:
                if isinstance(t, dict):
                    word = t.get("word", "").lower().strip()
                    if word and word not in stopwords_fr and len(word) > 2:
                        keywords.append(word)
        elif isinstance(top_terms, list):
            # Format: [{"word": "...", "score": ...}, ...] ou ["word1", "word2", ...]
            for term in top_terms[:15]:
                if isinstance(term, dict):
                    word = term.get("word", "").lower().strip()
                elif isinstance(term, str):
                    word = term.lower().strip()
                else:
                    continue
                
                if word and word not in stopwords_fr and len(word) > 2:
                    keywords.append(word)
        
        # Si pas assez de keywords, utiliser le label
        if len(keywords) < 3:
            label_words = best_cluster.label.replace("_", " ").split()
            for word in label_words:
                word_lower = word.lower().strip()
                if word_lower and word_lower not in stopwords_fr and len(word_lower) > 2:
                    if word_lower not in keywords:
                        keywords.append(word_lower)
        
        # Limiter à 10 keywords maximum
        keywords = keywords[:10]
        keywords_str = ", ".join(keywords)
        
        print(f"  - Keywords: {keywords_str}")
        
        # 4. Récupérer un site_profile_id si possible
        site_profile_id = None
        if execution.client_domain:
            # Chercher un site_profile pour ce domaine
            result = await db.execute(
                select(SiteProfile).where(
                    SiteProfile.domain == execution.client_domain,
                    SiteProfile.is_valid == True  # noqa: E712
                ).order_by(SiteProfile.analysis_date.desc())
            )
            site_profile = result.scalar_one_or_none()
            if site_profile:
                site_profile_id = site_profile.id
                print(f"\n✓ Site profile trouvé:")
                print(f"  - ID: {site_profile_id}")
                print(f"  - Domain: {site_profile.domain}")
                print(f"  - Tone: {site_profile.editorial_tone}")
        
        # 5. Construire le payload
        payload = {
            "topic": best_cluster.label,
            "keywords": keywords_str,
            "tone": "professional",  # Par défaut, peut être personnalisé
            "target_words": 2000,
            "language": "fr",
            "site_profile_id": site_profile_id,
            "generate_images": True
        }
        
        # Si on a un site_profile, utiliser son tone s'il existe
        if site_profile_id and site_profile and site_profile.editorial_tone:
            # Mapper les tones possibles
            tone_mapping = {
                "professional": "professional",
                "casual": "casual",
                "educational": "educational",
                "persuasive": "persuasive",
            }
            profile_tone = site_profile.editorial_tone.lower()
            if profile_tone in tone_mapping:
                payload["tone"] = tone_mapping[profile_tone]
        
        return payload


async def main():
    """Point d'entrée principal."""
    execution_id = "03317802-daf5-443e-9815-7a594570eab0"
    
    try:
        payload = await prepare_article_generation_payload(execution_id)
        
        print("\n" + "="*60)
        print("PAYLOAD JSON POUR LA GÉNÉRATION D'ARTICLES")
        print("="*60)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print("="*60)
        
        print("\n✓ Payload prêt à être utilisé avec:")
        print(f"  POST http://localhost:8000/api/v1/articles/generate")
        print("\n  Body:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"\n✗ Erreur: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

