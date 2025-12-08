"""Script pour vérifier les logs de scraping récents."""

import asyncio
import json
import sys
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

# Ajouter le chemin du projet
sys.path.insert(0, str(__file__).replace("/scripts/check_scraping_logs.py", ""))

from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.models import WorkflowExecution


def format_duration(seconds: Optional[int]) -> str:
    """Format duration in human-readable format."""
    if not seconds:
        return "N/A"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def format_statistics(stats: dict) -> str:
    """Format statistics dictionary."""
    if not stats:
        return "Aucune statistique"
    
    lines = []
    for key, value in stats.items():
        if isinstance(value, dict):
            lines.append(f"  {key}:")
            for sub_key, sub_value in value.items():
                lines.append(f"    {sub_key}: {sub_value}")
        else:
            lines.append(f"  {key}: {value}")
    return "\n".join(lines)


async def check_recent_scraping_logs(limit: int = 5, execution_id: Optional[str] = None):
    """
    Vérifier les logs de scraping récents.
    
    Args:
        limit: Nombre d'exécutions à afficher
        execution_id: ID d'exécution spécifique (optionnel)
    """
    async with AsyncSessionLocal() as session:
        try:
            # Construire la requête
            query = select(WorkflowExecution).where(
                WorkflowExecution.workflow_type == "scraping",
                WorkflowExecution.is_valid == True,  # noqa: E712
            )
            
            if execution_id:
                query = query.where(WorkflowExecution.execution_id == execution_id)
            else:
                query = query.order_by(desc(WorkflowExecution.created_at)).limit(limit)
            
            result = await session.execute(query)
            executions = result.scalars().all()
            
            if not executions:
                print("❌ Aucune exécution de scraping trouvée.")
                return
            
            print(f"\n{'='*80}")
            print(f"📊 LOGS DE SCRAPING ({len(executions)} exécution(s))")
            print(f"{'='*80}\n")
            
            for i, execution in enumerate(executions, 1):
                print(f"{'─'*80}")
                print(f"📋 Exécution #{i}")
                print(f"{'─'*80}")
                print(f"🆔 Execution ID: {execution.execution_id}")
                print(f"📅 Créé le: {execution.created_at}")
                print(f"⏱️  Durée: {format_duration(execution.duration_seconds)}")
                print(f"📊 Statut: {execution.status}")
                print(f"✅ Succès: {'Oui' if execution.was_success else 'Non'}")
                
                if execution.start_time:
                    print(f"🕐 Début: {execution.start_time}")
                if execution.end_time:
                    print(f"🕐 Fin: {execution.end_time}")
                
                # Input data
                if execution.input_data:
                    print(f"\n📥 INPUT DATA:")
                    input_data = execution.input_data
                    domains = input_data.get("domains", [])
                    client_domain = input_data.get("client_domain")
                    max_articles = input_data.get("max_articles_per_domain", 100)
                    
                    if client_domain:
                        print(f"  Client Domain: {client_domain}")
                    if domains:
                        print(f"  Domaines: {len(domains)} domaines")
                        if len(domains) <= 10:
                            for domain in domains:
                                print(f"    - {domain}")
                        else:
                            for domain in domains[:5]:
                                print(f"    - {domain}")
                            print(f"    ... et {len(domains) - 5} autres")
                    print(f"  Max articles par domaine: {max_articles}")
                
                # Output data
                if execution.output_data:
                    print(f"\n📤 OUTPUT DATA:")
                    output_data = execution.output_data
                    
                    # Statistiques globales
                    stats = output_data.get("statistics", {})
                    if stats:
                        print(f"\n📊 STATISTIQUES GLOBALES:")
                        print(f"  Total domaines: {stats.get('total_domains', 0)}")
                        print(f"  Domaines avec articles découverts: {stats.get('domains_with_articles_discovered', 0)}")
                        print(f"  Domaines sans articles: {stats.get('domains_without_articles', 0)}")
                        print(f"  Domaines avec erreurs: {stats.get('domains_with_errors', 0)}")
                        print(f"  Total articles découverts: {stats.get('total_articles_discovered', 0)}")
                        print(f"  Total articles sauvegardés: {stats.get('total_articles_saved', 0)}")
                        print(f"  Articles déjà existants: {stats.get('total_articles_already_exists', 0)}")
                        print(f"  Articles échoués (crawl): {stats.get('total_articles_crawl_failed', 0)}")
                        print(f"  Articles filtrés: {stats.get('total_articles_filtered', 0)}")
                        print(f"  Erreurs: {stats.get('total_articles_errors', 0)}")
                    
                    # Articles par domaine
                    articles_by_domain = output_data.get("articles_by_domain", {})
                    total_scraped = output_data.get("total_articles_scraped", 0)
                    
                    print(f"\n📰 ARTICLES PAR DOMAINE:")
                    print(f"  Total articles scrapés: {total_scraped}")
                    
                    if articles_by_domain:
                        domains_with_articles = {
                            domain: len(articles)
                            for domain, articles in articles_by_domain.items()
                            if articles
                        }
                        
                        if domains_with_articles:
                            print(f"  Domaines avec articles ({len(domains_with_articles)}):")
                            # Trier par nombre d'articles décroissant
                            sorted_domains = sorted(
                                domains_with_articles.items(),
                                key=lambda x: x[1],
                                reverse=True
                            )
                            for domain, count in sorted_domains[:10]:
                                print(f"    - {domain}: {count} article(s)")
                            if len(sorted_domains) > 10:
                                print(f"    ... et {len(sorted_domains) - 10} autres domaines")
                        else:
                            print(f"  ⚠️  Aucun domaine n'a d'articles scrapés")
                    else:
                        print(f"  ⚠️  Aucun article trouvé")
                
                # Error message
                if execution.error_message:
                    print(f"\n❌ ERREUR:")
                    print(f"  {execution.error_message}")
                
                print()
            
            print(f"{'='*80}\n")
            
        except Exception as e:
            print(f"❌ Erreur lors de la récupération des logs: {e}")
            import traceback
            traceback.print_exc()


async def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Vérifier les logs de scraping")
    parser.add_argument(
        "-n",
        "--limit",
        type=int,
        default=5,
        help="Nombre d'exécutions à afficher (défaut: 5)",
    )
    parser.add_argument(
        "-e",
        "--execution-id",
        type=str,
        help="ID d'exécution spécifique à afficher",
    )
    
    args = parser.parse_args()
    
    await check_recent_scraping_logs(limit=args.limit, execution_id=args.execution_id)


if __name__ == "__main__":
    asyncio.run(main())

