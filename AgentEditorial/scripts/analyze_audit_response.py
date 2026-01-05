#!/usr/bin/env python3
"""Analyse la réponse de la route GET /api/v1/sites/{domain}/audit.

Ce script :
1. Lance la route /audit
2. Analyse la réponse pour vérifier sa validité
3. Vérifie tous les champs requis
4. Génère un rapport d'analyse
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

API_BASE_URL = "http://localhost:8000/api/v1"
DEFAULT_TIMEOUT = 60.0


def analyze_pending_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyse une réponse PendingAuditResponse."""
    analysis = {
        "type": "PendingAuditResponse",
        "valid": True,
        "issues": [],
        "fields_present": {},
        "fields_missing": [],
    }
    
    # Vérifier les champs requis
    required_fields = ["status", "execution_id", "message", "workflow_steps", "data_status"]
    
    for field in required_fields:
        if field in data:
            analysis["fields_present"][field] = True
            analysis["fields_present"][field + "_value"] = data[field]
        else:
            analysis["fields_missing"].append(field)
            analysis["valid"] = False
            analysis["issues"].append(f"Champ requis manquant: {field}")
    
    # Vérifier le statut
    if "status" in data and data["status"] != "pending":
        analysis["issues"].append(f"Statut inattendu: {data['status']} (attendu: 'pending')")
    
    # Vérifier execution_id
    if "execution_id" in data:
        exec_id = data["execution_id"]
        if not exec_id or len(exec_id) < 10:
            analysis["issues"].append(f"execution_id invalide: {exec_id}")
            analysis["valid"] = False
    
    # Vérifier workflow_steps
    if "workflow_steps" in data:
        steps = data["workflow_steps"]
        if not isinstance(steps, list):
            analysis["issues"].append("workflow_steps doit être une liste")
            analysis["valid"] = False
        else:
            for i, step in enumerate(steps):
                step_required = ["step", "name", "status"]
                for field in step_required:
                    if field not in step:
                        analysis["issues"].append(f"workflow_steps[{i}] manque le champ: {field}")
                        analysis["valid"] = False
    
    # Vérifier data_status
    if "data_status" in data:
        data_status = data["data_status"]
        required_status_fields = [
            "has_profile",
            "has_competitors",
            "has_client_articles",
            "has_competitor_articles",
            "has_trend_pipeline",
        ]
        for field in required_status_fields:
            if field not in data_status:
                analysis["issues"].append(f"data_status manque le champ: {field}")
                analysis["valid"] = False
    
    return analysis


def analyze_complete_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyse une réponse SiteAuditResponse."""
    analysis = {
        "type": "SiteAuditResponse",
        "valid": True,
        "issues": [],
        "fields_present": {},
        "fields_missing": [],
        "field_analysis": {},
    }
    
    # Vérifier les champs requis
    required_fields = ["url", "profile", "domains", "audience", "competitors", "took_ms"]
    
    for field in required_fields:
        if field in data:
            analysis["fields_present"][field] = True
            analysis["fields_present"][field + "_value"] = data[field]
        else:
            analysis["fields_missing"].append(field)
            analysis["valid"] = False
            analysis["issues"].append(f"Champ requis manquant: {field}")
    
    # Analyser le profile
    if "profile" in data:
        profile = data["profile"]
        if not isinstance(profile, dict):
            analysis["issues"].append("profile doit être un objet")
            analysis["valid"] = False
        else:
            profile_required = ["style", "themes"]
            for field in profile_required:
                if field not in profile:
                    analysis["issues"].append(f"profile manque le champ: {field}")
                    analysis["valid"] = False
                else:
                    analysis["field_analysis"][f"profile.{field}"] = profile[field]
    
    # Analyser style
    if "profile" in data and "style" in data["profile"]:
        style = data["profile"]["style"]
        style_required = ["tone", "vocabulary", "format"]
        for field in style_required:
            if field not in style:
                analysis["issues"].append(f"profile.style manque le champ: {field}")
                analysis["valid"] = False
    
    # Analyser domains
    if "domains" in data:
        domains = data["domains"]
        if not isinstance(domains, list):
            analysis["issues"].append("domains doit être une liste")
            analysis["valid"] = False
        else:
            analysis["field_analysis"]["domains_count"] = len(domains)
            for i, domain in enumerate(domains):
                domain_required = ["id", "label", "confidence", "topics_count", "summary"]
                for field in domain_required:
                    if field not in domain:
                        analysis["issues"].append(f"domains[{i}] manque le champ: {field}")
                        analysis["valid"] = False
    
    # Analyser audience
    if "audience" in data:
        audience = data["audience"]
        if not isinstance(audience, dict):
            analysis["issues"].append("audience doit être un objet")
            analysis["valid"] = False
        else:
            audience_required = ["type", "level", "sectors"]
            for field in audience_required:
                if field not in audience:
                    analysis["issues"].append(f"audience manque le champ: {field}")
                    analysis["valid"] = False
    
    # Analyser competitors
    if "competitors" in data:
        competitors = data["competitors"]
        if not isinstance(competitors, list):
            analysis["issues"].append("competitors doit être une liste")
            analysis["valid"] = False
        else:
            analysis["field_analysis"]["competitors_count"] = len(competitors)
            # Vérifier que max_competitors = 10 est respecté (on devrait avoir max 10)
            if len(competitors) > 10:
                analysis["issues"].append(
                    f"Trop de concurrents retournés: {len(competitors)} (max attendu: 10)"
                )
            for i, competitor in enumerate(competitors):
                if not isinstance(competitor, dict):
                    analysis["issues"].append(f"competitors[{i}] doit être un objet")
                    analysis["valid"] = False
                else:
                    comp_required = ["name", "similarity"]
                    for field in comp_required:
                        if field not in competitor:
                            analysis["issues"].append(f"competitors[{i}] manque le champ: {field}")
                            analysis["valid"] = False
    
    # Analyser took_ms
    if "took_ms" in data:
        took_ms = data["took_ms"]
        if not isinstance(took_ms, int) or took_ms < 0:
            analysis["issues"].append(f"took_ms doit être un entier positif, reçu: {took_ms}")
            analysis["valid"] = False
    
    return analysis


async def analyze_audit_route(domain: str, timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """Analyse la route GET /api/v1/sites/{domain}/audit."""
    print(f"\n{'='*80}")
    print(f"Analyse de la route GET /api/v1/sites/{{domain}}/audit")
    print(f"{'='*80}")
    print(f"Domaine: {domain}")
    print(f"API Base URL: {API_BASE_URL}\n")
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            print(f"📡 Appel de la route...")
            response = await client.get(f"{API_BASE_URL}/sites/{domain}/audit")
            
            print(f"📊 Statut HTTP: {response.status_code}")
            
            if response.status_code != 200:
                return {
                    "error": True,
                    "status_code": response.status_code,
                    "message": response.text[:500],
                }
            
            data = response.json()
            
            # Déterminer le type de réponse
            if "execution_id" in data:
                # PendingAuditResponse
                print("📋 Type de réponse: PendingAuditResponse")
                analysis = analyze_pending_response(data)
            else:
                # SiteAuditResponse
                print("📋 Type de réponse: SiteAuditResponse")
                analysis = analyze_complete_response(data)
            
            analysis["raw_response"] = data
            analysis["status_code"] = response.status_code
            
            return analysis
        
        except httpx.TimeoutException:
            return {
                "error": True,
                "message": "Timeout lors de l'appel à l'API",
            }
        except Exception as e:
            return {
                "error": True,
                "message": f"Erreur: {str(e)}",
            }


def print_analysis(analysis: Dict[str, Any]) -> None:
    """Affiche l'analyse de manière lisible."""
    if analysis.get("error"):
        print(f"\n❌ Erreur: {analysis.get('message', 'Erreur inconnue')}")
        return
    
    print(f"\n{'='*80}")
    print("RÉSULTATS DE L'ANALYSE")
    print(f"{'='*80}\n")
    
    response_type = analysis.get("type", "Unknown")
    is_valid = analysis.get("valid", False)
    
    print(f"Type de réponse: {response_type}")
    print(f"Statut HTTP: {analysis.get('status_code', 'N/A')}")
    print(f"Validité: {'✅ VALIDE' if is_valid else '❌ INVALIDE'}\n")
    
    if analysis.get("issues"):
        print("⚠️ PROBLÈMES IDENTIFIÉS:")
        print("-" * 80)
        for issue in analysis["issues"]:
            print(f"  - {issue}")
        print()
    
    if analysis.get("fields_missing"):
        print("❌ CHAMPS MANQUANTS:")
        print("-" * 80)
        for field in analysis["fields_missing"]:
            print(f"  - {field}")
        print()
    
    if analysis.get("field_analysis"):
        print("📊 ANALYSE DES CHAMPS:")
        print("-" * 80)
        for key, value in analysis["field_analysis"].items():
            print(f"  - {key}: {value}")
        print()
    
    # Afficher des détails spécifiques selon le type
    if response_type == "SiteAuditResponse":
        raw = analysis.get("raw_response", {})
        print("📋 DÉTAILS DE LA RÉPONSE:")
        print("-" * 80)
        print(f"  URL: {raw.get('url', 'N/A')}")
        print(f"  Nombre de domaines: {len(raw.get('domains', []))}")
        print(f"  Nombre de concurrents: {len(raw.get('competitors', []))}")
        print(f"  Temps d'analyse: {raw.get('took_ms', 0)} ms")
        if raw.get("competitors"):
            print(f"\n  Concurrents (max 10):")
            for i, comp in enumerate(raw["competitors"][:10], 1):
                print(f"    {i}. {comp.get('name', 'N/A')} (similarity: {comp.get('similarity', 0)})")
        print()
    
    elif response_type == "PendingAuditResponse":
        raw = analysis.get("raw_response", {})
        print("📋 DÉTAILS DE LA RÉPONSE:")
        print("-" * 80)
        print(f"  Execution ID: {raw.get('execution_id', 'N/A')}")
        print(f"  Message: {raw.get('message', 'N/A')}")
        print(f"  Nombre d'étapes: {len(raw.get('workflow_steps', []))}")
        print(f"  Étapes:")
        for step in raw.get("workflow_steps", []):
            print(f"    - Étape {step.get('step', 'N/A')}: {step.get('name', 'N/A')} ({step.get('status', 'N/A')})")
        print()


async def main():
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Analyse la réponse de la route GET /api/v1/sites/{domain}/audit"
    )
    parser.add_argument(
        "--domain",
        type=str,
        default="innosys.fr",
        help="Domaine à analyser (défaut: innosys.fr)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Timeout en secondes (défaut: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Fichier de sortie pour sauvegarder l'analyse JSON",
    )
    
    args = parser.parse_args()
    
    analysis = await analyze_audit_route(args.domain, args.timeout)
    print_analysis(analysis)
    
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False, default=str)
        print(f"💾 Analyse sauvegardée: {output_path}")
    
    # Code de sortie
    if analysis.get("error"):
        sys.exit(1)
    elif not analysis.get("valid", False):
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

