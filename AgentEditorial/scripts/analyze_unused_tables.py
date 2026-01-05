"""Script pour analyser les tables non utilisées dans la base de données."""

import os
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict

# Tables dans la base de données
DB_TABLES = [
    "article_recommendations", "audit_log", "bertopic_analysis", "client_articles",
    "client_coverage_analysis", "client_strengths", "competitor_articles", "content_roadmap",
    "crawl_cache", "discovery_logs", "editorial_gaps", "editorial_trends",
    "error_logs", "hybrid_trends_analysis", "performance_metrics", "scraping_permissions",
    "site_analysis_results", "site_discovery_profiles", "site_profiles", "topic_clusters",
    "topic_outliers", "topic_temporal_metrics", "trend_analysis", "trend_pipeline_executions",
    "url_discovery_scores", "weak_signals_analysis", "workflow_executions"
]

# Modèles dans models.py (mapping table_name -> class_name)
TABLE_TO_MODEL = {
    "site_profiles": "SiteProfile",
    "workflow_executions": "WorkflowExecution",
    "site_analysis_results": "SiteAnalysisResult",
    "competitor_articles": "CompetitorArticle",
    "client_articles": "ClientArticle",
    "topic_clusters": "TopicCluster",
    "topic_outliers": "TopicOutlier",
    "topic_temporal_metrics": "TopicTemporalMetrics",
    "trend_analysis": "TrendAnalysis",
    "article_recommendations": "ArticleRecommendation",
    "weak_signals_analysis": "WeakSignalAnalysis",
    "client_coverage_analysis": "ClientCoverageAnalysis",
    "editorial_gaps": "EditorialGap",
    "client_strengths": "ClientStrength",
    "content_roadmap": "ContentRoadmap",
    "trend_pipeline_executions": "TrendPipelineExecution",
    "crawl_cache": "CrawlCache",
    "scraping_permissions": "ScrapingPermission",
    "performance_metrics": "PerformanceMetric",
    "audit_log": "AuditLog",
    "site_discovery_profiles": "SiteDiscoveryProfile",
    "url_discovery_scores": "UrlDiscoveryScore",
    "discovery_logs": "DiscoveryLog",
    "error_logs": "ErrorLog",
}

# Dossiers à scanner
SCAN_DIRS = [
    "python_scripts/database",
    "python_scripts/agents",
    "python_scripts/api",
    "python_scripts/vectorstore",
    "python_scripts/utils",
]


def find_table_references(table_name: str, codebase_path: Path) -> Dict[str, List[str]]:
    """Trouve toutes les références à une table dans le code."""
    references = {
        "model_imports": [],
        "model_usage": [],
        "sql_queries": [],
        "crud_functions": [],
        "migrations": [],
    }
    
    # Patterns de recherche
    model_class = TABLE_TO_MODEL.get(table_name)
    table_pattern = re.compile(rf'\b{table_name}\b', re.IGNORECASE)
    model_pattern = re.compile(rf'\b{model_class}\b', re.IGNORECASE) if model_class else None
    
    # Scanner tous les fichiers Python
    for root, dirs, files in os.walk(codebase_path):
        # Ignorer certains dossiers
        if any(skip in root for skip in ['__pycache__', '.git', '.venv', 'node_modules']):
            continue
            
        for file in files:
            if not file.endswith('.py'):
                continue
                
            file_path = Path(root) / file
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
            except Exception:
                continue
            
            relative_path = str(file_path.relative_to(codebase_path))
            
            # Chercher les imports de modèles
            if model_pattern and model_pattern.search(content):
                if 'from python_scripts.database.models import' in content or 'import.*models' in content:
                    references["model_imports"].append(relative_path)
            
            # Chercher l'utilisation du modèle
            if model_pattern and model_pattern.search(content):
                references["model_usage"].append(relative_path)
            
            # Chercher les requêtes SQL brutes
            if table_pattern.search(content):
                if 'SELECT' in content or 'INSERT' in content or 'UPDATE' in content or 'DELETE' in content:
                    references["sql_queries"].append(relative_path)
            
            # Chercher dans les fonctions CRUD
            if 'crud' in relative_path.lower() and table_pattern.search(content):
                references["crud_functions"].append(relative_path)
            
            # Chercher dans les migrations
            if 'migrations' in relative_path and table_pattern.search(content):
                references["migrations"].append(relative_path)
    
    return references


def analyze_all_tables(codebase_path: Path) -> Dict[str, Dict]:
    """Analyse toutes les tables."""
    results = {}
    
    print("Analyse des tables en cours...")
    for i, table in enumerate(DB_TABLES, 1):
        print(f"[{i}/{len(DB_TABLES)}] Analyse de {table}...")
        references = find_table_references(table, codebase_path)
        results[table] = references
    
    return results


def check_model_exists(table_name: str) -> bool:
    """Vérifie si un modèle existe dans models.py."""
    return table_name in TABLE_TO_MODEL


def generate_report(results: Dict[str, Dict], output_path: Path) -> None:
    """Génère un rapport markdown."""
    
    # Catégoriser les tables
    tables_with_model = []
    tables_without_model = []
    unused_tables = []
    
    for table, refs in results.items():
        has_model = check_model_exists(table)
        has_usage = any(refs.values())
        
        if not has_model:
            tables_without_model.append((table, refs))
        elif not has_usage:
            unused_tables.append((table, refs))
        else:
            tables_with_model.append((table, refs))
    
    # Générer le rapport
    report = []
    report.append("# Rapport d'analyse des tables de la base de données\n")
    report.append(f"**Date d'analyse** : {Path(__file__).stat().st_mtime}\n")
    report.append(f"**Total de tables analysées** : {len(DB_TABLES)}\n\n")
    
    # Section 1: Tables sans modèle
    report.append("## 1. Tables sans modèle dans models.py\n")
    report.append("Ces tables existent dans la base de données mais n'ont pas de modèle SQLAlchemy défini.\n\n")
    
    for table, refs in sorted(tables_without_model):
        report.append(f"### `{table}`\n")
        report.append(f"- **Modèle SQLAlchemy** : ❌ Non défini\n")
        report.append(f"- **Références dans le code** :\n")
        
        if any(refs.values()):
            for ref_type, files in refs.items():
                if files:
                    report.append(f"  - {ref_type}: {len(files)} fichier(s)\n")
                    for file in files[:5]:  # Limiter à 5 fichiers
                        report.append(f"    - `{file}`\n")
                    if len(files) > 5:
                        report.append(f"    - ... et {len(files) - 5} autre(s)\n")
        else:
            report.append("  - Aucune référence trouvée\n")
        
        report.append("\n")
    
    # Section 2: Tables avec modèle mais non utilisées
    report.append("## 2. Tables avec modèle mais non utilisées\n")
    report.append("Ces tables ont un modèle SQLAlchemy mais ne sont pas référencées dans le code.\n\n")
    
    for table, refs in sorted(unused_tables):
        model_class = TABLE_TO_MODEL.get(table)
        report.append(f"### `{table}`\n")
        report.append(f"- **Modèle SQLAlchemy** : ✅ `{model_class}`\n")
        report.append(f"- **Références dans le code** : Aucune\n")
        report.append("\n")
    
    # Section 3: Résumé
    report.append("## 3. Résumé\n\n")
    report.append(f"- **Tables avec modèle et utilisées** : {len(tables_with_model)}\n")
    report.append(f"- **Tables sans modèle** : {len(tables_without_model)}\n")
    report.append(f"- **Tables avec modèle mais non utilisées** : {len(unused_tables)}\n\n")
    
    # Section 4: Recommandations
    report.append("## 4. Recommandations\n\n")
    
    if tables_without_model:
        report.append("### Tables à supprimer (sans modèle et non utilisées)\n\n")
        for table, refs in sorted(tables_without_model):
            if not any(refs.values()):
                report.append(f"- `{table}` : Supprimer la table (aucune référence trouvée)\n")
        report.append("\n")
    
    if unused_tables:
        report.append("### Tables à vérifier (modèle existe mais non utilisées)\n\n")
        for table, refs in sorted(unused_tables):
            model_class = TABLE_TO_MODEL.get(table)
            report.append(f"- `{table}` (`{model_class}`) : Vérifier si le modèle est nécessaire\n")
        report.append("\n")
    
    # Écrire le rapport
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(''.join(report))
    
    print(f"\nRapport généré : {output_path}")


if __name__ == "__main__":
    # Chemin du projet
    project_root = Path(__file__).parent.parent
    
    # Analyser toutes les tables
    results = analyze_all_tables(project_root)
    
    # Générer le rapport
    report_path = project_root / "ANALYSE_TABLES_NON_UTILISEES.md"
    generate_report(results, report_path)
    
    print("\n✅ Analyse terminée !")

















