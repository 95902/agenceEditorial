"""Script pour vérifier la validité de l'output_data d'une exécution de workflow."""

import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.models import WorkflowExecution
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


def validate_json_serializable(obj, path="root"):
    """Valide qu'un objet est JSON-serializable et détecte les valeurs problématiques."""
    issues = []
    
    if obj is None:
        return issues
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            current_path = f"{path}.{key}" if path != "root" else key
            issues.extend(validate_json_serializable(value, current_path))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            current_path = f"{path}[{i}]"
            issues.extend(validate_json_serializable(item, current_path))
    elif isinstance(obj, (int, str, bool)):
        pass  # Types valides
    elif isinstance(obj, float):
        if not (obj == obj):  # NaN check
            issues.append(f"{path}: NaN détecté")
        elif obj == float('inf') or obj == float('-inf'):
            issues.append(f"{path}: Infinity détecté")
    else:
        try:
            json.dumps(obj)
        except (TypeError, ValueError) as e:
            issues.append(f"{path}: Type non sérialisable {type(obj).__name__}: {str(e)}")
    
    return issues


def validate_output_structure(output_data: dict, workflow_type: str) -> list:
    """Valide la structure de l'output_data selon le schéma WorkflowOutputSchema."""
    issues = []
    
    if not isinstance(output_data, dict):
        issues.append("output_data doit être un dictionnaire")
        return issues
    
    # Pour competitor_search, la structure est directe (sans result_type/result_data)
    if workflow_type == "competitor_search":
        # Structure attendue: {"competitors": [...], "total_found": ..., "domain": ...}
        if "competitors" not in output_data:
            issues.append("Pour competitor_search: 'competitors' manquant (requis)")
        elif not isinstance(output_data["competitors"], list):
            issues.append("Pour competitor_search: 'competitors' doit être une liste")
        
        if "domain" not in output_data:
            issues.append("Pour competitor_search: 'domain' manquant (recommandé)")
        elif not isinstance(output_data["domain"], str):
            issues.append("Pour competitor_search: 'domain' doit être une chaîne de caractères")
        
        # Vérifier la structure des concurrents
        if "competitors" in output_data and isinstance(output_data["competitors"], list):
            for i, competitor in enumerate(output_data["competitors"]):
                if not isinstance(competitor, dict):
                    issues.append(f"competitors[{i}] doit être un dictionnaire")
                else:
                    if "domain" not in competitor:
                        issues.append(f"competitors[{i}]: 'domain' manquant")
                    if "url" not in competitor:
                        issues.append(f"competitors[{i}]: 'url' manquant")
    
    # Pour les autres workflow_types, utiliser la structure WorkflowOutputSchema standard
    else:
        # Vérifier les champs requis selon WorkflowOutputSchema
        if "result_type" not in output_data:
            issues.append("Champ 'result_type' manquant (requis)")
        elif not isinstance(output_data["result_type"], str):
            issues.append("Champ 'result_type' doit être une chaîne de caractères")
        
        if "result_data" not in output_data:
            issues.append("Champ 'result_data' manquant (requis)")
        elif not isinstance(output_data["result_data"], dict):
            issues.append("Champ 'result_data' doit être un dictionnaire")
        
        # Vérifier les champs optionnels
        if "artifacts" in output_data:
            if not isinstance(output_data["artifacts"], list):
                issues.append("Champ 'artifacts' doit être une liste")
            elif output_data["artifacts"]:
                for i, artifact in enumerate(output_data["artifacts"]):
                    if not isinstance(artifact, str):
                        issues.append(f"artifacts[{i}] doit être une chaîne de caractères")
        
        if "metrics" in output_data:
            if not isinstance(output_data["metrics"], dict):
                issues.append("Champ 'metrics' doit être un dictionnaire")
        
        # Vérifications spécifiques selon le workflow_type
        if workflow_type == "editorial_analysis":
            if "result_data" in output_data and isinstance(output_data["result_data"], dict):
                result_data = output_data["result_data"]
                if "site_profile" not in result_data:
                    issues.append("Pour editorial_analysis: 'result_data.site_profile' manquant")
    
    return issues


async def check_execution_output(execution_id_str: str = None, workflow_id: int = None):
    """Vérifie la validité de l'output_data pour une exécution donnée."""
    async with AsyncSessionLocal() as session:
        # Construire la requête
        query = select(WorkflowExecution).where(
            WorkflowExecution.is_valid == True  # noqa: E712
        )
        
        # Recherche par id uniquement
        if workflow_id is not None and execution_id_str is None:
            query = query.where(WorkflowExecution.id == workflow_id)
        # Recherche par execution_id
        elif execution_id_str is not None:
            try:
                execution_id = UUID(execution_id_str)
                query = query.where(WorkflowExecution.execution_id == execution_id)
                if workflow_id is not None:
                    query = query.where(WorkflowExecution.id == workflow_id)
            except ValueError:
                print(f"❌ ERREUR: execution_id invalide: {execution_id_str}")
                return False
        else:
            print("❌ ERREUR: Vous devez fournir soit execution_id soit workflow_id")
            return False
        
        result = await session.execute(query)
        execution = result.scalar_one_or_none()
        
        if not execution:
            print(f"❌ ERREUR: Exécution non trouvée")
            if execution_id_str:
                print(f"   execution_id: {execution_id_str}")
            if workflow_id:
                print(f"   id: {workflow_id}")
            return False
        
        print("=" * 80)
        print(f"📋 VÉRIFICATION DE L'EXÉCUTION")
        print("=" * 80)
        print(f"ID: {execution.id}")
        print(f"Execution ID: {execution.execution_id}")
        print(f"Workflow Type: {execution.workflow_type}")
        print(f"Status: {execution.status}")
        print(f"Was Success: {execution.was_success}")
        print(f"Start Time: {execution.start_time}")
        print(f"End Time: {execution.end_time}")
        print(f"Duration: {execution.duration_seconds}s" if execution.duration_seconds else "Duration: N/A")
        if execution.error_message:
            print(f"Error Message: {execution.error_message}")
        print()
        
        # Vérifier si output_data existe
        if execution.output_data is None:
            print("⚠️  ATTENTION: output_data est NULL")
            if execution.status == "completed" and execution.was_success:
                print("   ⚠️  Problème: Status 'completed' avec was_success=True mais output_data est NULL")
            return False
        
        print("=" * 80)
        print("🔍 VALIDATION DE L'OUTPUT_DATA")
        print("=" * 80)
        
        # 1. Vérifier la sérialisation JSON
        print("\n1️⃣  Vérification de la sérialisation JSON...")
        json_issues = validate_json_serializable(execution.output_data)
        if json_issues:
            print("   ❌ Problèmes de sérialisation JSON détectés:")
            for issue in json_issues:
                print(f"      - {issue}")
        else:
            print("   ✅ Sérialisation JSON valide")
        
        # 2. Vérifier la structure
        print("\n2️⃣  Vérification de la structure...")
        structure_issues = validate_output_structure(execution.output_data, execution.workflow_type)
        if structure_issues:
            print("   ❌ Problèmes de structure détectés:")
            for issue in structure_issues:
                print(f"      - {issue}")
        else:
            print("   ✅ Structure valide")
        
        # 3. Tester la sérialisation complète
        print("\n3️⃣  Test de sérialisation complète...")
        try:
            json_str = json.dumps(execution.output_data, default=str, allow_nan=False)
            print(f"   ✅ Sérialisation réussie ({len(json_str)} caractères)")
        except (TypeError, ValueError) as e:
            print(f"   ❌ Échec de la sérialisation: {str(e)}")
            json_issues.append(f"Erreur de sérialisation: {str(e)}")
        
        # 4. Vérifier la complétude des données
        print("\n4️⃣  Vérification de la complétude...")
        completeness_issues = []
        
        if execution.workflow_type == "competitor_search":
            competitors = execution.output_data.get("competitors", [])
            total_found = execution.output_data.get("total_found")
            total_evaluated = execution.output_data.get("total_evaluated")
            all_candidates = execution.output_data.get("all_candidates", [])
            excluded_candidates = execution.output_data.get("excluded_candidates", [])
            
            # Vérifier les champs attendus selon la documentation
            expected_fields = ["competitors", "domain"]
            optional_fields = ["total_found", "total_evaluated", "all_candidates", "excluded_candidates"]
            
            for field in expected_fields:
                if field not in execution.output_data:
                    completeness_issues.append(f"Champ requis manquant: '{field}'")
            
            # Vérifier total_found
            if total_found is None:
                completeness_issues.append(f"Champ 'total_found' manquant (devrait être {len(competitors)})")
            elif total_found != len(competitors):
                completeness_issues.append(f"Incohérence: total_found={total_found} mais {len(competitors)} concurrents dans la liste")
            
            # Vérifier total_evaluated
            if total_evaluated is None:
                completeness_issues.append("Champ 'total_evaluated' manquant (recommandé)")
            
            # Vérifier all_candidates
            if "all_candidates" not in execution.output_data:
                completeness_issues.append("Champ 'all_candidates' manquant (recommandé pour traçabilité)")
            elif not all_candidates:
                completeness_issues.append("Champ 'all_candidates' présent mais vide")
            
            # Vérifier excluded_candidates
            if excluded_candidates is None:
                completeness_issues.append("Champ 'excluded_candidates' manquant (recommandé)")
            
            if len(competitors) == 0 and execution.status == "completed" and execution.was_success:
                completeness_issues.append("Aucun concurrent trouvé malgré un statut 'completed'")
            
            # Vérifier que chaque concurrent a les champs essentiels
            missing_essential = 0
            for i, competitor in enumerate(competitors[:10]):  # Limiter à 10 pour éviter trop de messages
                if not isinstance(competitor, dict):
                    continue
                missing_fields = []
                if not competitor.get("domain"):
                    missing_fields.append("domain")
                if not competitor.get("url"):
                    missing_fields.append("url")
                if missing_fields:
                    missing_essential += 1
                    if missing_essential <= 5:  # Limiter l'affichage
                        completeness_issues.append(f"competitors[{i}] manque: {', '.join(missing_fields)}")
            
            if missing_essential > 5:
                completeness_issues.append(f"... et {missing_essential - 5} autres concurrents avec champs manquants")
        
        elif execution.workflow_type == "editorial_analysis":
            if "result_data" in execution.output_data:
                result_data = execution.output_data["result_data"]
                if not result_data.get("site_profile") and execution.status == "completed":
                    completeness_issues.append("site_profile manquant dans result_data")
        
        if completeness_issues:
            print("   ⚠️  Problèmes de complétude détectés:")
            for issue in completeness_issues:
                print(f"      - {issue}")
        else:
            print("   ✅ Données complètes")
        
        # 5. Afficher un aperçu de l'output_data
        print("\n5️⃣  Aperçu de l'output_data:")
        print("-" * 80)
        try:
            preview = json.dumps(execution.output_data, indent=2, default=str, ensure_ascii=False)
            # Limiter l'affichage à 2000 caractères pour voir plus de détails
            if len(preview) > 2000:
                print(preview[:2000] + "\n... (tronqué)")
                print(f"\n   Taille totale: {len(preview)} caractères")
            else:
                print(preview)
        except Exception as e:
            print(f"   ❌ Impossible d'afficher l'aperçu: {str(e)}")
        
        # Résumé
        print("\n" + "=" * 80)
        print("📊 RÉSUMÉ")
        print("=" * 80)
        
        all_issues = json_issues + structure_issues + completeness_issues
        if all_issues:
            print(f"❌ VALIDATION ÉCHOUÉE: {len(all_issues)} problème(s) détecté(s)")
            print(f"   - Sérialisation JSON: {len(json_issues)}")
            print(f"   - Structure: {len(structure_issues)}")
            print(f"   - Complétude: {len(completeness_issues)}")
            return False
        else:
            print("✅ VALIDATION RÉUSSIE: output_data est valide et complet")
            return True


async def main():
    """Point d'entrée principal."""
    if len(sys.argv) < 2:
        print("Usage: python check_execution_output.py <execution_id> [workflow_id]")
        print("   ou: python check_execution_output.py --id <workflow_id>")
        print("Exemple: python check_execution_output.py 7997bd9a-2758-40fa-b867-f1cf334a618a 103")
        print("Exemple: python check_execution_output.py --id 106")
        sys.exit(1)
    
    execution_id = None
    workflow_id = None
    
    # Gérer l'option --id
    if sys.argv[1] == "--id" and len(sys.argv) >= 3:
        workflow_id = int(sys.argv[2])
    else:
        execution_id = sys.argv[1]
        if len(sys.argv) > 2:
            workflow_id = int(sys.argv[2])
    
    success = await check_execution_output(execution_id, workflow_id)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())















