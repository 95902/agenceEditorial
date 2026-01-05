#!/usr/bin/env python3
"""Test de vérification du comportement de GET /api/v1/sites/{domain}/audit.

Ce script vérifie que la route :
1. Vérifie si le site profile existe
2. Si il existe ET toutes les données sont disponibles : renvoie SiteAuditResponse
3. Si il existe MAIS des données manquent : lance les workflows manquants (PendingAuditResponse)
4. Si il n'existe pas : lance le workflow d'analyse (PendingAuditResponse)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

API_BASE_URL = "http://localhost:8000/api/v1"
DEFAULT_TIMEOUT = 30.0


async def check_site_profile_exists(domain: str) -> Optional[Dict[str, Any]]:
    """Vérifie si un site profile existe pour le domaine."""
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        try:
            response = await client.get(f"{API_BASE_URL}/sites/{domain}")
            if response.status_code == 200:
                return response.json()
            return None
        except Exception:
            return None


async def test_audit_route(domain: str) -> Dict[str, Any]:
    """Teste la route /audit et analyse le comportement."""
    print(f"\n{'='*80}")
    print(f"Test de la route GET /api/v1/sites/{{domain}}/audit")
    print(f"{'='*80}")
    print(f"Domaine: {domain}\n")
    
    results = {
        "domain": domain,
        "profile_exists": False,
        "audit_response_type": None,
        "audit_response": None,
        "workflow_launched": False,
        "validation": {},
    }
    
    # Étape 1: Vérifier si le profile existe
    print("📋 ÉTAPE 1: Vérification de l'existence du site profile")
    print("-" * 80)
    profile = await check_site_profile_exists(domain)
    
    if profile:
        print(f"✅ Site profile EXISTE pour {domain}")
        print(f"   - Domain: {profile.get('domain', 'N/A')}")
        print(f"   - Analysis date: {profile.get('analysis_date', 'N/A')}")
        print(f"   - Language level: {profile.get('language_level', 'N/A')}")
        results["profile_exists"] = True
    else:
        print(f"❌ Site profile N'EXISTE PAS pour {domain}")
        results["profile_exists"] = False
    print()
    
    # Étape 2: Appeler la route /audit
    print("📡 ÉTAPE 2: Appel de la route /audit")
    print("-" * 80)
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        try:
            response = await client.get(f"{API_BASE_URL}/sites/{domain}/audit")
            print(f"Statut HTTP: {response.status_code}")
            
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                results["error"] = error_msg
                print(f"❌ Erreur HTTP: {error_msg}")
                return results
            
            data = response.json()
            results["audit_response"] = data
            
            # Déterminer le type de réponse
            if "execution_id" in data:
                results["audit_response_type"] = "PendingAuditResponse"
                results["workflow_launched"] = True
                print(f"📋 Type de réponse: PendingAuditResponse")
                print(f"   - Execution ID: {data.get('execution_id', 'N/A')}")
                print(f"   - Message: {data.get('message', 'N/A')}")
                print(f"   - Nombre d'étapes: {len(data.get('workflow_steps', []))}")
                print(f"   - Data status:")
                if "data_status" in data:
                    ds = data["data_status"]
                    print(f"     • has_profile: {ds.get('has_profile', False)}")
                    print(f"     • has_competitors: {ds.get('has_competitors', False)}")
                    print(f"     • has_client_articles: {ds.get('has_client_articles', False)}")
                    print(f"     • has_competitor_articles: {ds.get('has_competitor_articles', False)}")
                    print(f"     • has_trend_pipeline: {ds.get('has_trend_pipeline', False)}")
            else:
                results["audit_response_type"] = "SiteAuditResponse"
                results["workflow_launched"] = False
                print(f"📋 Type de réponse: SiteAuditResponse")
                print(f"   - URL: {data.get('url', 'N/A')}")
                print(f"   - Nombre de domaines: {len(data.get('domains', []))}")
                print(f"   - Nombre de concurrents: {len(data.get('competitors', []))}")
                print(f"   - Temps d'analyse: {data.get('took_ms', 0)} ms")
            
            print()
            
        except httpx.ConnectError as e:
            error_msg = f"Impossible de se connecter à l'API: {e}"
            results["error"] = error_msg
            print(f"❌ Erreur de connexion: {error_msg}")
            print(f"   Vérifiez que l'API est démarrée sur {API_BASE_URL}")
            return results
        except httpx.TimeoutException as e:
            error_msg = f"Timeout lors de l'appel à l'API: {e}"
            results["error"] = error_msg
            print(f"❌ Timeout: {error_msg}")
            return results
        except Exception as e:
            error_msg = f"Erreur inattendue: {str(e)}"
            results["error"] = error_msg
            print(f"❌ Erreur: {error_msg}")
            import traceback
            traceback.print_exc()
            return results
    
    # Étape 3: Validation du comportement
    print("✅ ÉTAPE 3: Validation du comportement")
    print("-" * 80)
    
    validation = {}
    
    # Scénario 1: Profile existe et toutes les données sont disponibles
    if results["profile_exists"] and results["audit_response_type"] == "SiteAuditResponse":
        validation["scenario"] = "Profile existe + Données complètes"
        validation["expected"] = "SiteAuditResponse avec toutes les données"
        validation["actual"] = "SiteAuditResponse"
        validation["valid"] = True
        print("✅ Scénario 1: Profile existe + Données complètes")
        print("   → Route retourne SiteAuditResponse ✅")
    
    # Scénario 2: Profile existe mais des données manquent
    elif results["profile_exists"] and results["audit_response_type"] == "PendingAuditResponse":
        validation["scenario"] = "Profile existe + Données manquantes"
        validation["expected"] = "PendingAuditResponse avec workflows manquants"
        validation["actual"] = "PendingAuditResponse"
        validation["valid"] = True
        print("✅ Scénario 2: Profile existe + Données manquantes")
        print("   → Route retourne PendingAuditResponse et lance les workflows manquants ✅")
        
        # Vérifier quels workflows sont lancés
        if results["audit_response"] and "workflow_steps" in results["audit_response"]:
            steps = results["audit_response"]["workflow_steps"]
            print(f"   → Workflows lancés: {len(steps)}")
            for step in steps:
                print(f"     • {step.get('name', 'N/A')} (status: {step.get('status', 'N/A')})")
    
    # Scénario 3: Profile n'existe pas
    elif not results["profile_exists"] and results["audit_response_type"] == "PendingAuditResponse":
        validation["scenario"] = "Profile n'existe pas"
        validation["expected"] = "PendingAuditResponse avec workflow d'analyse"
        validation["actual"] = "PendingAuditResponse"
        validation["valid"] = True
        print("✅ Scénario 3: Profile n'existe pas")
        print("   → Route retourne PendingAuditResponse et lance le workflow d'analyse ✅")
        
        # Vérifier que le workflow d'analyse est lancé
        if results["audit_response"] and "workflow_steps" in results["audit_response"]:
            steps = results["audit_response"]["workflow_steps"]
            has_analysis = any(
                step.get("name") == "Editorial Analysis" 
                for step in steps
            )
            if has_analysis:
                print("   → Workflow 'Editorial Analysis' lancé ✅")
            else:
                print("   ⚠️ Workflow 'Editorial Analysis' non détecté dans les étapes")
                validation["valid"] = False
    
    else:
        validation["scenario"] = "Cas inattendu"
        validation["expected"] = "Comportement cohérent"
        validation["actual"] = f"Profile: {results['profile_exists']}, Response: {results['audit_response_type']}"
        validation["valid"] = False
        print("❌ Scénario inattendu")
        print(f"   → Profile existe: {results['profile_exists']}")
        print(f"   → Type de réponse: {results['audit_response_type']}")
    
    results["validation"] = validation
    print()
    
    return results


def print_summary(results: Dict[str, Any]) -> None:
    """Affiche un résumé des résultats."""
    print(f"{'='*80}")
    print("RÉSUMÉ")
    print(f"{'='*80}\n")
    
    print(f"Domaine testé: {results['domain']}")
    print(f"Profile existe: {'✅ Oui' if results['profile_exists'] else '❌ Non'}")
    print(f"Type de réponse: {results['audit_response_type']}")
    print(f"Workflow lancé: {'✅ Oui' if results['workflow_launched'] else '❌ Non'}")
    
    if results.get("validation"):
        val = results["validation"]
        print(f"\nValidation: {'✅ VALIDE' if val.get('valid') else '❌ INVALIDE'}")
        print(f"Scénario: {val.get('scenario', 'N/A')}")
        print(f"Attendu: {val.get('expected', 'N/A')}")
        print(f"Actuel: {val.get('actual', 'N/A')}")
    
    if results.get("error"):
        print(f"\n❌ Erreur: {results['error']}")


async def main():
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Test de vérification du comportement de GET /api/v1/sites/{domain}/audit"
    )
    parser.add_argument(
        "--domain",
        type=str,
        default="innosys.fr",
        help="Domaine à tester (défaut: innosys.fr)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Fichier de sortie pour sauvegarder les résultats JSON",
    )
    
    args = parser.parse_args()
    
    results = await test_audit_route(args.domain)
    print_summary(results)
    
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n💾 Résultats sauvegardés: {output_path}")
    
    # Code de sortie
    if results.get("error"):
        sys.exit(1)
    elif not results.get("validation", {}).get("valid", False):
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())

