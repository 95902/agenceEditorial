"""Script complet pour analyser les tables non utilisées avec vérification DB."""

import os
import re
import subprocess
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


def get_table_info_from_db(table_name: str) -> Dict[str, any]:
    """Récupère les informations d'une table depuis la DB."""
    try:
        # Compter les lignes
        result = subprocess.run(
            [
                "docker", "exec", "editorial_postgres",
                "psql", "-U", "editorial_user", "-d", "editorial_db",
                "-t", "-c", f"SELECT COUNT(*) FROM {table_name};"
            ],
            capture_output=True,
            text=True,
            timeout=5
        )
        row_count = int(result.stdout.strip()) if result.stdout.strip() else 0
        
        # Taille de la table
        result = subprocess.run(
            [
                "docker", "exec", "editorial_postgres",
                "psql", "-U", "editorial_user", "-d", "editorial_db",
                "-t", "-c", f"SELECT pg_size_pretty(pg_total_relation_size('public.{table_name}'));"
            ],
            capture_output=True,
            text=True,
            timeout=5
        )
        size = result.stdout.strip() if result.stdout.strip() else "0 kB"
        
        return {
            "row_count": row_count,
            "size": size,
            "has_data": row_count > 0
        }
    except Exception as e:
        return {
            "row_count": -1,
            "size": "unknown",
            "has_data": False,
            "error": str(e)
        }


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
    table_pattern = re.compile(rf'\b{re.escape(table_name)}\b', re.IGNORECASE)
    model_pattern = re.compile(rf'\b{re.escape(model_class)}\b', re.IGNORECASE) if model_class else None
    
    # Scanner tous les fichiers Python
    for root, dirs, files in os.walk(codebase_path):
        # Ignorer certains dossiers
        if any(skip in root for skip in ['__pycache__', '.git', '.venv', 'node_modules', '.cursor']):
            continue
            
        for file in files:
            if not file.endswith('.py'):
                continue
                
            file_path = Path(root) / file
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception:
                continue
            
            relative_path = str(file_path.relative_to(codebase_path))
            
            # Chercher les imports de modèles
            if model_pattern and model_pattern.search(content):
                if 'from python_scripts.database.models import' in content or 'import.*models' in content:
                    if relative_path not in references["model_imports"]:
                        references["model_imports"].append(relative_path)
            
            # Chercher l'utilisation du modèle
            if model_pattern and model_pattern.search(content):
                if relative_path not in references["model_usage"]:
                    references["model_usage"].append(relative_path)
            
            # Chercher les requêtes SQL brutes
            if table_pattern.search(content):
                if any(keyword in content for keyword in ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'FROM', 'INTO']):
                    if relative_path not in references["sql_queries"]:
                        references["sql_queries"].append(relative_path)
            
            # Chercher dans les fonctions CRUD
            if 'crud' in relative_path.lower() and table_pattern.search(content):
                if relative_path not in references["crud_functions"]:
                    references["crud_functions"].append(relative_path)
            
            # Chercher dans les migrations
            if 'migrations' in relative_path and table_pattern.search(content):
                if relative_path not in references["migrations"]:
                    references["migrations"].append(relative_path)
    
    return references


def check_migration_history(table_name: str, migrations_path: Path) -> List[str]:
    """Vérifie l'historique des migrations pour une table."""
    migrations = []
    
    for migration_file in migrations_path.glob("*.py"):
        try:
            with open(migration_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if table_name in content.lower():
                    migrations.append(migration_file.name)
        except Exception:
            continue
    
    return sorted(migrations)


def analyze_all_tables(codebase_path: Path, migrations_path: Path) -> Dict[str, Dict]:
    """Analyse toutes les tables."""
    results = {}
    
    print("Analyse des tables en cours...")
    for i, table in enumerate(DB_TABLES, 1):
        print(f"[{i}/{len(DB_TABLES)}] Analyse de {table}...")
        
        # Références dans le code
        references = find_table_references(table, codebase_path)
        
        # Informations de la DB
        db_info = get_table_info_from_db(table)
        
        # Historique des migrations
        migrations = check_migration_history(table, migrations_path)
        
        # Vérifier si le modèle existe
        has_model = table in TABLE_TO_MODEL
        
        # Vérifier si utilisé
        has_usage = any(references.values())
        
        results[table] = {
            "references": references,
            "db_info": db_info,
            "migrations": migrations,
            "has_model": has_model,
            "has_usage": has_usage,
            "model_class": TABLE_TO_MODEL.get(table),
        }
    
    return results


def generate_report(results: Dict[str, Dict], output_path: Path) -> None:
    """Génère un rapport markdown complet."""
    
    # Catégoriser les tables
    tables_with_model_and_usage = []
    tables_with_model_no_usage = []
    tables_without_model_has_usage = []
    tables_without_model_no_usage = []
    
    for table, data in results.items():
        has_model = data["has_model"]
        has_usage = data["has_usage"]
        
        if has_model and has_usage:
            tables_with_model_and_usage.append((table, data))
        elif has_model and not has_usage:
            tables_with_model_no_usage.append((table, data))
        elif not has_model and has_usage:
            tables_without_model_has_usage.append((table, data))
        else:
            tables_without_model_no_usage.append((table, data))
    
    # Générer le rapport
    report = []
    report.append("# Rapport d'analyse des tables de la base de données\n\n")
    report.append("## Résumé exécutif\n\n")
    report.append(f"- **Total de tables analysées** : {len(DB_TABLES)}\n")
    report.append(f"- **Tables avec modèle et utilisées** : {len(tables_with_model_and_usage)}\n")
    report.append(f"- **Tables avec modèle mais non utilisées** : {len(tables_with_model_no_usage)}\n")
    report.append(f"- **Tables sans modèle mais référencées** : {len(tables_without_model_has_usage)}\n")
    report.append(f"- **Tables sans modèle et non utilisées** : {len(tables_without_model_no_usage)}\n\n")
    
    # Section 1: Tables sans modèle et non utilisées (à supprimer)
    report.append("## 1. Tables à supprimer (sans modèle et non utilisées)\n\n")
    report.append("Ces tables existent dans la base de données mais n'ont pas de modèle SQLAlchemy et ne sont pas utilisées dans le code.\n\n")
    
    for table, data in sorted(tables_without_model_no_usage):
        db_info = data["db_info"]
        report.append(f"### `{table}`\n\n")
        report.append(f"- **Modèle SQLAlchemy** : ❌ Non défini\n")
        report.append(f"- **Utilisation dans le code** : ❌ Aucune référence\n")
        report.append(f"- **Données dans la DB** : {db_info['row_count']} ligne(s) ({db_info['size']})\n")
        
        if data["migrations"]:
            report.append(f"- **Migrations** : {len(data['migrations'])} migration(s) référencent cette table\n")
            for mig in data["migrations"][:3]:
                report.append(f"  - `{mig}`\n")
        
        report.append("\n")
    
    # Section 2: Tables sans modèle mais référencées (à créer le modèle)
    if tables_without_model_has_usage:
        report.append("## 2. Tables sans modèle mais référencées (à créer le modèle)\n\n")
        report.append("Ces tables sont utilisées dans le code mais n'ont pas de modèle SQLAlchemy défini.\n\n")
        
        for table, data in sorted(tables_without_model_has_usage):
            refs = data["references"]
            db_info = data["db_info"]
            report.append(f"### `{table}`\n\n")
            report.append(f"- **Modèle SQLAlchemy** : ❌ Non défini\n")
            report.append(f"- **Données dans la DB** : {db_info['row_count']} ligne(s) ({db_info['size']})\n")
            report.append(f"- **Références dans le code** :\n")
            
            for ref_type, files in refs.items():
                if files:
                    report.append(f"  - **{ref_type}** : {len(files)} fichier(s)\n")
                    for file in files[:3]:
                        report.append(f"    - `{file}`\n")
                    if len(files) > 3:
                        report.append(f"    - ... et {len(files) - 3} autre(s)\n")
            
            report.append("\n")
    
    # Section 3: Tables avec modèle mais non utilisées
    if tables_with_model_no_usage:
        report.append("## 3. Tables avec modèle mais non utilisées\n\n")
        report.append("Ces tables ont un modèle SQLAlchemy mais ne sont pas référencées dans le code.\n\n")
        
        for table, data in sorted(tables_with_model_no_usage):
            db_info = data["db_info"]
            model_class = data["model_class"]
            report.append(f"### `{table}`\n\n")
            report.append(f"- **Modèle SQLAlchemy** : ✅ `{model_class}`\n")
            report.append(f"- **Utilisation dans le code** : ❌ Aucune référence\n")
            report.append(f"- **Données dans la DB** : {db_info['row_count']} ligne(s) ({db_info['size']})\n")
            
            if data["migrations"]:
                report.append(f"- **Migrations** : {len(data['migrations'])} migration(s)\n")
            
            report.append("\n")
    
    # Section 4: Recommandations
    report.append("## 4. Recommandations\n\n")
    
    if tables_without_model_no_usage:
        report.append("### Actions immédiates : Supprimer les tables non utilisées\n\n")
        for table, data in sorted(tables_without_model_no_usage):
            db_info = data["db_info"]
            if db_info["row_count"] == 0:
                report.append(f"- **`{table}`** : Supprimer la table (0 lignes, aucune référence)\n")
                report.append(f"  ```sql\n")
                report.append(f"  DROP TABLE IF EXISTS {table} CASCADE;\n")
                report.append(f"  ```\n")
        report.append("\n")
    
    if tables_without_model_has_usage:
        report.append("### Actions à planifier : Créer les modèles manquants\n\n")
        for table, data in sorted(tables_without_model_has_usage):
            report.append(f"- **`{table}`** : Créer le modèle SQLAlchemy dans `models.py`\n")
        report.append("\n")
    
    if tables_with_model_no_usage:
        report.append("### À vérifier : Modèles non utilisés\n\n")
        for table, data in sorted(tables_with_model_no_usage):
            model_class = data["model_class"]
            db_info = data["db_info"]
            if db_info["row_count"] == 0:
                report.append(f"- **`{table}` (`{model_class}`)** : Vérifier si le modèle est nécessaire (0 lignes)\n")
            else:
                report.append(f"- **`{table}` (`{model_class}`)** : Modèle défini mais non utilisé ({db_info['row_count']} lignes)\n")
        report.append("\n")
    
    # Section 5: Détails par table (toutes)
    report.append("## 5. Détails complets par table\n\n")
    report.append("| Table | Modèle | Utilisé | Lignes | Taille | Références |\n")
    report.append("|-------|--------|--------|--------|--------|------------|\n")
    
    for table, data in sorted(results.items()):
        model_status = "✅" if data["has_model"] else "❌"
        usage_status = "✅" if data["has_usage"] else "❌"
        db_info = data["db_info"]
        ref_count = sum(len(files) for files in data["references"].values())
        
        report.append(f"| `{table}` | {model_status} | {usage_status} | {db_info['row_count']} | {db_info['size']} | {ref_count} |\n")
    
    # Écrire le rapport
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(''.join(report))
    
    print(f"\n✅ Rapport généré : {output_path}")


if __name__ == "__main__":
    # Chemins du projet
    project_root = Path(__file__).parent.parent
    migrations_path = project_root / "python_scripts" / "database" / "migrations" / "versions"
    
    # Analyser toutes les tables
    results = analyze_all_tables(project_root, migrations_path)
    
    # Générer le rapport
    report_path = project_root / "ANALYSE_TABLES_NON_UTILISEES.md"
    generate_report(results, report_path)
    
    print("\n✅ Analyse complète terminée !")








