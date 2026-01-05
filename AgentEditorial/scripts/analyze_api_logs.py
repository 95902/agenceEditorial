#!/usr/bin/env python3
"""Analyse les logs de l'API pour identifier les patterns, erreurs et performances.

Ce script analyse les logs de l'API pour :
1. Identifier les requêtes et leurs statuts
2. Détecter les erreurs et warnings
3. Analyser les patterns de réutilisation d'orchestrators
4. Mesurer les performances
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

@dataclass
class LogEntry:
    """Représente une entrée de log."""
    timestamp: Optional[str]
    level: str
    message: str
    raw_line: str
    is_json: bool = False
    json_data: Optional[Dict[str, Any]] = None


@dataclass
class RequestLog:
    """Représente une requête HTTP."""
    method: str
    path: str
    status_code: int
    client_ip: str
    timestamp: Optional[str] = None


@dataclass
class LogAnalysis:
    """Résultats de l'analyse des logs."""
    total_lines: int
    requests: List[RequestLog]
    orchestrator_reuses: List[Dict[str, Any]]
    errors: List[LogEntry]
    warnings: List[LogEntry]
    info_messages: List[LogEntry]
    stats: Dict[str, Any]


def parse_log_line(line: str) -> Optional[LogEntry]:
    """Parse une ligne de log."""
    line = line.strip()
    if not line:
        return None
    
    # Essayer de parser comme JSON structuré
    if line.startswith("{"):
        try:
            json_data = json.loads(line)
            return LogEntry(
                timestamp=json_data.get("timestamp"),
                level=json_data.get("level", "info"),
                message=json_data.get("event", ""),
                raw_line=line,
                is_json=True,
                json_data=json_data,
            )
        except json.JSONDecodeError:
            pass
    
    # Parser les logs Uvicorn/FastAPI
    # Format: INFO:     127.0.0.1:47426 - "GET /api/v1/sites/innosys.fr/audit HTTP/1.1" 200 OK
    uvicorn_pattern = r'^(INFO|WARNING|ERROR):\s+(\S+)\s+-\s+"(\w+)\s+(\S+)\s+HTTP/1\.1"\s+(\d+)'
    match = re.match(uvicorn_pattern, line)
    if match:
        level = match.group(1).lower()
        client_ip = match.group(2)
        method = match.group(3)
        path = match.group(4)
        status_code = int(match.group(5))
        
        return LogEntry(
            timestamp=None,
            level=level,
            message=f"{method} {path} {status_code}",
            raw_line=line,
            is_json=False,
            json_data={
                "method": method,
                "path": path,
                "status_code": status_code,
                "client_ip": client_ip,
            },
        )
    
    # Parser les messages INFO génériques
    info_pattern = r'^INFO:\s+(.+)$'
    match = re.match(info_pattern, line)
    if match:
        return LogEntry(
            timestamp=None,
            level="info",
            message=match.group(1),
            raw_line=line,
        )
    
    return LogEntry(
        timestamp=None,
        level="unknown",
        message=line,
        raw_line=line,
    )


def analyze_logs(log_file: Path) -> LogAnalysis:
    """Analyse un fichier de logs."""
    requests: List[RequestLog] = []
    orchestrator_reuses: List[Dict[str, Any]] = []
    errors: List[LogEntry] = []
    warnings: List[LogEntry] = []
    info_messages: List[LogEntry] = []
    
    with open(log_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    for line in lines:
        entry = parse_log_line(line)
        if not entry:
            continue
        
        # Classer par niveau
        if entry.level == "error":
            errors.append(entry)
        elif entry.level == "warning":
            warnings.append(entry)
        elif entry.level == "info":
            info_messages.append(entry)
        
        # Extraire les requêtes HTTP
        if entry.json_data and "method" in entry.json_data:
            requests.append(RequestLog(
                method=entry.json_data["method"],
                path=entry.json_data["path"],
                status_code=entry.json_data["status_code"],
                client_ip=entry.json_data.get("client_ip", "unknown"),
                timestamp=entry.timestamp,
            ))
        
        # Extraire les réutilisations d'orchestrator
        if entry.is_json and entry.json_data:
            if entry.json_data.get("event") == "Existing orchestrator found, reusing":
                orchestrator_reuses.append({
                    "execution_id": entry.json_data.get("execution_id"),
                    "domain": entry.json_data.get("domain"),
                    "timestamp": entry.json_data.get("timestamp"),
                })
    
    # Calculer les statistiques
    stats = {
        "total_requests": len(requests),
        "requests_by_status": Counter([r.status_code for r in requests]),
        "requests_by_path": Counter([r.path for r in requests]),
        "orchestrator_reuses_count": len(orchestrator_reuses),
        "unique_execution_ids": len(set([r.get("execution_id") for r in orchestrator_reuses if r.get("execution_id")])),
        "errors_count": len(errors),
        "warnings_count": len(warnings),
    }
    
    return LogAnalysis(
        total_lines=len(lines),
        requests=requests,
        orchestrator_reuses=orchestrator_reuses,
        errors=errors,
        warnings=warnings,
        info_messages=info_messages,
        stats=stats,
    )


def print_analysis(analysis: LogAnalysis) -> None:
    """Affiche l'analyse de manière lisible."""
    print(f"\n{'='*80}")
    print("ANALYSE DES LOGS DE L'API")
    print(f"{'='*80}\n")
    
    print(f"📊 STATISTIQUES GÉNÉRALES")
    print("-" * 80)
    print(f"  Total de lignes: {analysis.total_lines}")
    print(f"  Total de requêtes: {analysis.stats['total_requests']}")
    print(f"  Erreurs: {analysis.stats['errors_count']}")
    print(f"  Warnings: {analysis.stats['warnings_count']}")
    print()
    
    if analysis.stats['total_requests'] > 0:
        print(f"📡 REQUÊTES HTTP")
        print("-" * 80)
        print(f"  Répartition par statut:")
        for status, count in analysis.stats['requests_by_status'].most_common():
            print(f"    {status}: {count}")
        print()
        
        print(f"  Répartition par chemin:")
        for path, count in analysis.stats['requests_by_path'].most_common():
            print(f"    {path}: {count}")
        print()
    
    if analysis.orchestrator_reuses:
        print(f"🔄 RÉUTILISATION D'ORCHESTRATORS")
        print("-" * 80)
        print(f"  Nombre de réutilisations: {analysis.stats['orchestrator_reuses_count']}")
        print(f"  Execution IDs uniques: {analysis.stats['unique_execution_ids']}")
        
        if analysis.stats['unique_execution_ids'] == 1:
            print(f"  ✅ CORRECTION VALIDÉE: Un seul orchestrator réutilisé pour toutes les requêtes")
        else:
            print(f"  ⚠️ ATTENTION: {analysis.stats['unique_execution_ids']} orchestrators différents")
        
        print()
        print(f"  Détails des réutilisations:")
        for i, reuse in enumerate(analysis.orchestrator_reuses[:10], 1):
            print(f"    {i}. Domain: {reuse.get('domain', 'N/A')}, Execution ID: {reuse.get('execution_id', 'N/A')[:8]}...")
        print()
    
    if analysis.errors:
        print(f"❌ ERREURS")
        print("-" * 80)
        for error in analysis.errors[:10]:
            print(f"  - {error.message}")
        print()
    
    if analysis.warnings:
        print(f"⚠️ WARNINGS")
        print("-" * 80)
        for warning in analysis.warnings[:10]:
            print(f"  - {warning.message}")
        print()
    
    # Analyse de la race condition
    print(f"🔍 ANALYSE DE LA RACE CONDITION")
    print("-" * 80)
    if analysis.stats['orchestrator_reuses_count'] > 0:
        if analysis.stats['unique_execution_ids'] == 1:
            print(f"  ✅ SUCCÈS: La correction de la race condition fonctionne correctement")
            print(f"     - {analysis.stats['orchestrator_reuses_count']} requêtes ont réutilisé le même orchestrator")
            print(f"     - Aucune duplication d'orchestrator détectée")
        else:
            print(f"  ⚠️ PROBLÈME: Plusieurs orchestrators différents détectés")
            print(f"     - {analysis.stats['unique_execution_ids']} orchestrators différents")
    else:
        print(f"  ℹ️ Aucune réutilisation d'orchestrator détectée dans les logs")
    print()


async def main():
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Analyse les logs de l'API"
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default="/tmp/api.log",
        help="Chemin vers le fichier de logs (défaut: /tmp/api.log)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Fichier de sortie pour sauvegarder l'analyse JSON",
    )
    
    args = parser.parse_args()
    
    log_file = Path(args.log_file)
    if not log_file.exists():
        print(f"❌ Erreur: Le fichier de logs n'existe pas: {log_file}")
        sys.exit(1)
    
    print(f"📖 Lecture du fichier de logs: {log_file}")
    analysis = analyze_logs(log_file)
    print_analysis(analysis)
    
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "stats": analysis.stats,
                "orchestrator_reuses": analysis.orchestrator_reuses,
                "requests_count": len(analysis.requests),
                "errors_count": len(analysis.errors),
                "warnings_count": len(analysis.warnings),
            }, f, indent=2, ensure_ascii=False, default=str)
        print(f"💾 Analyse sauvegardée: {output_path}")
    
    # Code de sortie
    if analysis.stats['errors_count'] > 0:
        sys.exit(1)
    elif analysis.stats['unique_execution_ids'] > 1:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

