#!/usr/bin/env python3
"""Analyse complète de l'utilisation de la base de données après le workflow complet.

Ce script :
1. Compte les lignes dans chaque table
2. Vérifie l'utilisation dans le code
3. Identifie pourquoi certaines tables sont vides
4. Liste les tables non utilisées ou obsolètes
"""

import asyncio
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text, inspect
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.models import (
    AuditLog,
    ClientArticle,
    CompetitorArticle,
    ContentRoadmap,
    CrawlCache,
    ClientCoverageAnalysis,
    ClientStrength,
    DiscoveryLog,
    EditorialGap,
    ErrorLog,
    ArticleRecommendation,
    PerformanceMetric,
    ScrapingPermission,
    SiteAnalysisResult,
    SiteDiscoveryProfile,
    SiteProfile,
    TopicCluster,
    TopicOutlier,
    TopicTemporalMetrics,
    TrendAnalysis,
    TrendPipelineExecution,
    UrlDiscoveryScore,
    WeakSignalAnalysis,
    WorkflowExecution,
    GeneratedArticle,
    GeneratedArticleImage,
    GeneratedArticleVersion,
    GeneratedImage,
)


# Mapping table_name -> Model class
TABLE_MODEL_MAP = {
    "site_profiles": SiteProfile,
    "workflow_executions": WorkflowExecution,
    "site_analysis_results": SiteAnalysisResult,
    "competitor_articles": CompetitorArticle,
    "client_articles": ClientArticle,
    "topic_clusters": TopicCluster,
    "topic_outliers": TopicOutlier,
    "topic_temporal_metrics": TopicTemporalMetrics,
    "trend_analysis": TrendAnalysis,
    "article_recommendations": ArticleRecommendation,
    "weak_signals_analysis": WeakSignalAnalysis,
    "client_coverage_analysis": ClientCoverageAnalysis,
    "editorial_gaps": EditorialGap,
    "client_strengths": ClientStrength,
    "content_roadmap": ContentRoadmap,
    "trend_pipeline_executions": TrendPipelineExecution,
    "crawl_cache": CrawlCache,
    "scraping_permissions": ScrapingPermission,
    "performance_metrics": PerformanceMetric,
    "audit_log": AuditLog,
    "site_discovery_profiles": SiteDiscoveryProfile,
    "url_discovery_scores": UrlDiscoveryScore,
    "discovery_logs": DiscoveryLog,
    "error_logs": ErrorLog,
    "generated_articles": GeneratedArticle,
    "generated_article_images": GeneratedArticleImage,
    "generated_article_versions": GeneratedArticleVersion,
    "generated_images": GeneratedImage,
}


async def count_table_rows(db: AsyncSession, table_name: str) -> int:
    """Compte les lignes dans une table."""
    try:
        result = await db.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        return result.scalar_one() or 0
    except Exception as e:
        return -1  # Erreur (table n'existe peut-être pas)


async def get_table_size(db: AsyncSession, table_name: str) -> str:
    """Récupère la taille d'une table."""
    try:
        result = await db.execute(
            text(
                f"SELECT pg_size_pretty(pg_total_relation_size('public.{table_name}'))"
            )
        )
        return result.scalar_one() or "0 kB"
    except Exception:
        return "unknown"


def find_code_references(table_name: str, model_class_name: str, codebase_path: Path) -> Dict[str, List[str]]:
    """Trouve les références à une table dans le code."""
    references = {
        "imports": [],
        "crud_usage": [],
        "api_routes": [],
        "agents": [],
        "direct_sql": [],
    }
    
    model_pattern = re.compile(rf'\b{re.escape(model_class_name)}\b')
    table_pattern = re.compile(rf'\b{re.escape(table_name)}\b', re.IGNORECASE)
    
    for file_path in codebase_path.rglob("*.py"):
        # Ignorer certains dossiers
        if any(skip in str(file_path) for skip in ['__pycache__', '.git', '.venv', 'node_modules', '.cursor', 'migrations']):
            continue
        
        try:
            content = file_path.read_text(encoding='utf-8')
            rel_path = str(file_path.relative_to(codebase_path))
        except Exception:
            continue
        
        # Imports
        if model_pattern.search(content) and 'from python_scripts.database.models import' in content:
            if rel_path not in references["imports"]:
                references["imports"].append(rel_path)
        
        # CRUD usage
        if 'crud' in rel_path.lower() and model_pattern.search(content):
            if rel_path not in references["crud_usage"]:
                references["crud_usage"].append(rel_path)
        
        # API routes
        if 'api/routers' in rel_path and model_pattern.search(content):
            if rel_path not in references["api_routes"]:
                references["api_routes"].append(rel_path)
        
        # Agents
        if 'agents' in rel_path and model_pattern.search(content):
            if rel_path not in references["agents"]:
                references["agents"].append(rel_path)
        
        # SQL direct
        if table_pattern.search(content) and any(kw in content for kw in ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'FROM']):
            if rel_path not in references["direct_sql"]:
                references["direct_sql"].append(rel_path)
    
    return references


def get_table_purpose(table_name: str) -> str:
    """Retourne le but/usage attendu d'une table."""
    purposes = {
        "site_profiles": "Profils éditoriaux des sites clients analysés",
        "workflow_executions": "Suivi des exécutions de workflows (sites, competitors, discovery, etc.)",
        "site_analysis_results": "Résultats détaillés par phase de l'analyse éditoriale",
        "competitor_articles": "Articles scrapés des sites concurrents",
        "client_articles": "Articles scrapés du site client",
        "topic_clusters": "Clusters thématiques créés par BERTopic (Stage 1 Trend Pipeline)",
        "topic_outliers": "Articles non classifiés par BERTopic (outliers)",
        "topic_temporal_metrics": "Métriques temporelles par cluster (Stage 2 Trend Pipeline)",
        "trend_analysis": "Synthèses LLM des tendances par cluster (Stage 3 Trend Pipeline)",
        "article_recommendations": "Recommandations d'articles générées par LLM (Stage 3)",
        "weak_signals_analysis": "Analyse des signaux faibles (outliers groupés)",
        "client_coverage_analysis": "Analyse de couverture client par topic (Stage 4)",
        "editorial_gaps": "Gaps éditoriaux identifiés (Stage 4)",
        "client_strengths": "Forces compétitives du client (Stage 4)",
        "content_roadmap": "Roadmap de contenu priorisée (Stage 4)",
        "trend_pipeline_executions": "Suivi des exécutions du Trend Pipeline",
        "crawl_cache": "Cache des pages crawlé pour éviter les re-scraping",
        "scraping_permissions": "Cache des permissions robots.txt par domaine",
        "performance_metrics": "Métriques de performance des workflows",
        "audit_log": "Logs d'audit des actions des agents",
        "site_discovery_profiles": "Profils de découverte optimisés par domaine",
        "url_discovery_scores": "Scores de probabilité pour les URLs découvertes",
        "discovery_logs": "Logs des opérations de découverte",
        "error_logs": "Logs d'erreurs pour diagnostic",
        "generated_articles": "Articles générés par le pipeline de génération",
        "generated_article_images": "Images générées pour les articles",
        "generated_article_versions": "Versions historiques des articles générés",
        "generated_images": "Images générées avec Z-Image (standalone)",
    }
    return purposes.get(table_name, "Usage non documenté")


async def analyze_all_tables() -> Dict[str, Dict]:
    """Analyse toutes les tables."""
    results = {}
    codebase_path = Path(__file__).parent.parent
    
    async with AsyncSessionLocal() as db:
        print("📊 Analyse de la base de données...\n")
        
        for table_name, model_class in TABLE_MODEL_MAP.items():
            print(f"  Analysant {table_name}...")
            
            # Compter les lignes
            row_count = await count_table_rows(db, table_name)
            size = await get_table_size(db, table_name)
            
            # Trouver les références dans le code
            model_class_name = model_class.__name__
            references = find_code_references(table_name, model_class_name, codebase_path)
            
            # Calculer le score d'utilisation
            usage_score = (
                len(references["imports"]) * 2 +
                len(references["crud_usage"]) * 3 +
                len(references["api_routes"]) * 3 +
                len(references["agents"]) * 2 +
                len(references["direct_sql"]) * 1
            )
            
            # Déterminer le statut
            is_used = usage_score > 0
            has_data = row_count > 0
            is_empty = row_count == 0
            
            results[table_name] = {
                "row_count": row_count,
                "size": size,
                "has_data": has_data,
                "is_empty": is_empty,
                "references": references,
                "usage_score": usage_score,
                "is_used": is_used,
                "model_class": model_class_name,
                "purpose": get_table_purpose(table_name),
            }
    
    return results


def generate_report(results: Dict[str, Dict], output_path: Path) -> None:
    """Génère un rapport markdown complet."""
    
    # Catégoriser les tables
    filled_and_used = []
    filled_but_unused = []
    empty_but_used = []
    empty_and_unused = []
    
    for table_name, data in results.items():
        has_data = data["has_data"]
        is_used = data["is_used"]
        
        if has_data and is_used:
            filled_and_used.append((table_name, data))
        elif has_data and not is_used:
            filled_but_unused.append((table_name, data))
        elif not has_data and is_used:
            empty_but_used.append((table_name, data))
        else:
            empty_and_unused.append((table_name, data))
    
    report = []
    report.append("# Analyse complète de la base de données après workflow\n\n")
    report.append(f"**Date d'analyse** : {Path(__file__).stat().st_mtime}\n\n")
    
    # Résumé
    report.append("## 📊 Résumé exécutif\n\n")
    report.append(f"- **Total de tables analysées** : {len(results)}\n")
    report.append(f"- **Tables remplies et utilisées** : {len(filled_and_used)} ✅\n")
    report.append(f"- **Tables remplies mais non utilisées** : {len(filled_but_unused)} ⚠️\n")
    report.append(f"- **Tables vides mais utilisées** : {len(empty_but_used)} ⚠️\n")
    report.append(f"- **Tables vides et non utilisées** : {len(empty_and_unused)} ❌\n\n")
    
    # Section 1: Tables remplies et utilisées
    report.append("## ✅ 1. Tables remplies et utilisées\n\n")
    report.append("Ces tables contiennent des données et sont utilisées dans le code.\n\n")
    report.append("| Table | Lignes | Taille | Usage | But |\n")
    report.append("|-------|--------|--------|-------|-----|\n")
    
    for table_name, data in sorted(filled_and_used, key=lambda x: x[1]["row_count"], reverse=True):
        usage_count = sum(len(files) for files in data["references"].values())
        report.append(
            f"| `{table_name}` | {data['row_count']} | {data['size']} | {usage_count} refs | {data['purpose'][:50]}... |\n"
        )
    report.append("\n")
    
    # Section 2: Tables remplies mais non utilisées
    if filled_but_unused:
        report.append("## ⚠️ 2. Tables remplies mais non utilisées\n\n")
        report.append("Ces tables contiennent des données mais ne sont pas référencées dans le code.\n\n")
        report.append("| Table | Lignes | Taille | Raison probable |\n")
        report.append("|-------|--------|--------|------------------|\n")
        
        for table_name, data in sorted(filled_but_unused, key=lambda x: x[1]["row_count"], reverse=True):
            reason = "Table obsolète ou données historiques"
            report.append(f"| `{table_name}` | {data['row_count']} | {data['size']} | {reason} |\n")
        report.append("\n")
    
    # Section 3: Tables vides mais utilisées
    if empty_but_used:
        report.append("## ⚠️ 3. Tables vides mais utilisées dans le code\n\n")
        report.append("Ces tables sont référencées dans le code mais sont vides. Raisons possibles :\n\n")
        report.append("| Table | Usage | Raison probable |\n")
        report.append("|-------|-------|------------------|\n")
        
        for table_name, data in sorted(empty_but_used):
            usage_count = sum(len(files) for files in data["references"].values())
            reason = "Workflow non exécuté ou étape sautée"
            if "trend" in table_name.lower():
                reason = "Trend Pipeline non exécuté ou étape spécifique sautée"
            elif "generated" in table_name.lower():
                reason = "Génération d'article non effectuée"
            elif "discovery" in table_name.lower():
                reason = "Discovery/Scraping non effectué"
            
            report.append(f"| `{table_name}` | {usage_count} refs | {reason} |\n")
        report.append("\n")
    
    # Section 4: Tables vides et non utilisées
    if empty_and_unused:
        report.append("## ❌ 4. Tables vides et non utilisées\n\n")
        report.append("Ces tables sont vides et ne sont pas référencées dans le code.\n\n")
        report.append("| Table | But | Action recommandée |\n")
        report.append("|-------|-----|-------------------|\n")
        
        for table_name, data in sorted(empty_and_unused):
            action = "Vérifier si nécessaire, sinon supprimer"
            report.append(f"| `{table_name}` | {data['purpose']} | {action} |\n")
        report.append("\n")
    
    # Section 5: Détails par table
    report.append("## 📋 5. Détails complets par table\n\n")
    
    for table_name, data in sorted(results.items()):
        report.append(f"### `{table_name}`\n\n")
        report.append(f"- **But** : {data['purpose']}\n")
        report.append(f"- **Lignes** : {data['row_count']}\n")
        report.append(f"- **Taille** : {data['size']}\n")
        report.append(f"- **Modèle** : `{data['model_class']}`\n")
        report.append(f"- **Score d'utilisation** : {data['usage_score']}\n")
        
        if data['references']:
            report.append(f"- **Références dans le code** :\n")
            for ref_type, files in data['references'].items():
                if files:
                    report.append(f"  - **{ref_type}** : {len(files)} fichier(s)\n")
                    for file in files[:3]:
                        report.append(f"    - `{file}`\n")
                    if len(files) > 3:
                        report.append(f"    - ... et {len(files) - 3} autre(s)\n")
        else:
            report.append(f"- **Références** : Aucune\n")
        
        report.append("\n")
    
    # Section 6: Recommandations
    report.append("## 💡 6. Recommandations\n\n")
    
    if empty_and_unused:
        report.append("### Tables à supprimer\n\n")
        report.append("Les tables suivantes sont vides et non utilisées. Elles peuvent être supprimées :\n\n")
        for table_name, data in sorted(empty_and_unused):
            report.append(f"- `{table_name}` : {data['purpose']}\n")
        report.append("\n")
    
    if empty_but_used:
        report.append("### Tables à vérifier\n\n")
        report.append("Les tables suivantes sont utilisées mais vides. Vérifier si le workflow correspondant a été exécuté :\n\n")
        for table_name, data in sorted(empty_but_used):
            report.append(f"- `{table_name}` : {data['purpose']}\n")
        report.append("\n")
    
    if filled_but_unused:
        report.append("### Tables à nettoyer\n\n")
        report.append("Les tables suivantes contiennent des données mais ne sont pas utilisées. Vérifier si elles sont obsolètes :\n\n")
        for table_name, data in sorted(filled_but_unused, key=lambda x: x[1]["row_count"], reverse=True):
            report.append(f"- `{table_name}` : {data['row_count']} lignes - {data['purpose']}\n")
        report.append("\n")
    
    # Écrire le rapport
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(''.join(report))
    
    print(f"\n✅ Rapport généré : {output_path}")


async def main():
    """Point d'entrée principal."""
    results = await analyze_all_tables()
    
    # Générer le rapport
    output_path = Path(__file__).parent.parent / "ANALYSE_DATABASE_USAGE.md"
    generate_report(results, output_path)
    
    # Afficher un résumé dans la console
    print("\n" + "=" * 80)
    print("RÉSUMÉ DE L'ANALYSE")
    print("=" * 80)
    
    filled_count = sum(1 for r in results.values() if r["has_data"])
    used_count = sum(1 for r in results.values() if r["is_used"])
    empty_unused = sum(1 for r in results.values() if not r["has_data"] and not r["is_used"])
    
    print(f"\n📊 Statistiques :")
    print(f"   - Tables avec données : {filled_count}/{len(results)}")
    print(f"   - Tables utilisées : {used_count}/{len(results)}")
    print(f"   - Tables vides et non utilisées : {empty_unused}/{len(results)}")
    
    print(f"\n📄 Rapport complet : {output_path}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

