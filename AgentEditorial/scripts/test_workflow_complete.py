#!/usr/bin/env python3
"""Test e2e guidé du workflow complet Agent Editorial pour innosys.fr.

Étapes couvertes :
1) Analyse du site client (sites/analyze)
2) Recherche de concurrents (competitors/search)
3) Scraping discovery :
   - client-scrape (site client)
   - scrape (concurrents via client_domain)
4) Trend pipeline (trend-pipeline/analyze)
5) Génération d'article (articles/generate)

Le script :
- utilise l'API locale (http://localhost:8000/api/v1 par défaut)
- fait du polling sur les exécutions longues
- s'arrête entre les étapes pour validation manuelle
"""

from __future__ import annotations

import asyncio
import argparse
import json
import sys
from pathlib import Path
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.crud_profiles import get_site_profile_by_domain


API_BASE_URL = "http://localhost:8000/api/v1"
CLIENT_DOMAIN = "innosys.fr"
MAX_PAGES = 500
MAX_COMPETITORS = 50
MAX_ARTICLES_PER_DOMAIN = 200


@dataclass
class ExecutionResult:
    execution_id: str
    status: str
    start_time: Optional[str]
    estimated_duration_minutes: Optional[int]


def _print_header(title: str) -> None:
    bar = "=" * 80
    print(f"\n{bar}\n{title}\n{bar}")


def _pause(step_name: str) -> None:
    """Pause interactive entre les étapes."""
    print(f"\n➡ Étape terminée: {step_name}")
    input("Appuyez sur Entrée pour continuer vers l'étape suivante...")


def _pretty_print(label: str, data: Any, limit: int = 1200) -> None:
    print(f"\n📄 {label}:")
    try:
        text = json.dumps(data, indent=2, ensure_ascii=False, default=str)
    except Exception:
        text = str(data)
    if len(text) > limit:
        print(text[:limit] + "\n... (tronqué)")
    else:
        print(text)


async def check_execution_status(
    client: httpx.AsyncClient,
    execution_id: str,
) -> Optional[Dict[str, Any]]:
    """Vérifie le statut d'une exécution sans attendre."""
    try:
        resp = await client.get(f"{API_BASE_URL}/executions/{execution_id}")
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception:
        return None


async def wait_for_execution(
    client: httpx.AsyncClient,
    execution_id: str,
    timeout_seconds: int = 3600,
    poll_interval: int = 5,
    show_progress: bool = True,
    skip_if_completed: bool = True,
) -> Dict[str, Any]:
    """Poll l'endpoint /executions/{id} jusqu'à completion ou timeout."""
    # Vérifier si l'exécution est déjà complétée
    if skip_if_completed:
        status_check = await check_execution_status(client, execution_id)
        if status_check and status_check.get("status") in {"completed", "failed"}:
            status = status_check.get("status")
            print(f"✅ Exécution {execution_id} déjà terminée avec status='{status}'")
            return status_check
    
    _print_header(f"Suivi exécution {execution_id}")
    start = time.time()

    last_status: Optional[str] = None
    last_print_time = start
    progress_interval = 60  # Afficher la progression toutes les 60 secondes

    while True:
        elapsed = time.time() - start
        if elapsed > timeout_seconds:
            hours = timeout_seconds // 3600
            minutes = (timeout_seconds % 3600) // 60
            raise TimeoutError(
                f"Timeout après {hours}h {minutes}min pour l'exécution {execution_id}. "
                f"L'exécution peut continuer en arrière-plan. "
                f"Vérifiez le statut via: GET /api/v1/executions/{execution_id}"
            )

        resp = await client.get(f"{API_BASE_URL}/executions/{execution_id}")
        if resp.status_code == 404:
            print("❌ Exécution introuvable (404)")
            raise RuntimeError(f"Execution {execution_id} non trouvée")
        resp.raise_for_status()

        data = resp.json()
        status = data.get("status")
        
        # Afficher le statut si changé ou toutes les 60 secondes
        should_print = (
            status != last_status or 
            (show_progress and time.time() - last_print_time >= progress_interval)
        )
        
        if should_print:
            last_status = status
            last_print_time = time.time()
            est = data.get("estimated_duration_minutes")
            elapsed_min = int(elapsed // 60)
            elapsed_sec = int(elapsed % 60)
            print(
                f"📊 Status: {status} | "
                f"Temps écoulé: {elapsed_min}m {elapsed_sec}s | "
                f"ETA: {est} min"
            )

        if status in {"completed", "failed"}:
            elapsed_min = int(elapsed // 60)
            elapsed_sec = int(elapsed % 60)
            print(f"\n✅ Exécution terminée avec status='{status}' (durée: {elapsed_min}m {elapsed_sec}s)")
            return data

        await asyncio.sleep(poll_interval)


async def test_sites_analysis(
    client: httpx.AsyncClient,
    domain: str,
    max_pages: int,
) -> Tuple[str, int]:
    """Étape 1 : analyse éditoriale du site client."""
    _print_header("1) Analyse du site client (sites/analyze)")

    payload = {"domain": domain, "max_pages": max_pages}
    _pretty_print("Requête", payload)

    resp = await client.post(f"{API_BASE_URL}/sites/analyze", json=payload)
    if resp.status_code != 202:
        print(f"❌ Erreur analyse site: {resp.status_code}")
        print(resp.text)
        raise RuntimeError("Échec de l'appel /sites/analyze")

    data = resp.json()
    execution_id = str(data["execution_id"])
    print(f"✅ Analyse démarrée, execution_id={execution_id}")

    # Suivi exécution
    await wait_for_execution(client, execution_id, skip_if_completed=True)

    # Récupérer le profil site + site_profile_id
    profile_resp = await client.get(f"{API_BASE_URL}/sites/{domain}")
    profile_resp.raise_for_status()
    profile = profile_resp.json()

    _pretty_print("Profil éditorial (extrait)", profile)

    # On a besoin du site_profile_id pour discovery.client-scrape ; il est exposé via /profiles ?
    # Ici on repart de la liste complète et on prend le bon domaine.
    list_resp = await client.get(f"{API_BASE_URL}/sites")
    list_resp.raise_for_status()
    profiles = list_resp.json() or []

    site_profile_id: Optional[int] = None
    for p in profiles:
        if p.get("domain") == domain and "id" in p:
            site_profile_id = int(p["id"])
            break

    if site_profile_id is None:
        # Fallback: récupérer depuis la base de données directement
        print("⚠️ site_profile_id non trouvé dans /sites, tentative depuis la base de données...")
        try:
            async with AsyncSessionLocal() as db:
                profile = await get_site_profile_by_domain(db, domain)
                if profile:
                    site_profile_id = profile.id
                    print(f"✅ site_profile_id trouvé: {site_profile_id}")
                else:
                    print("⚠️ Avertissement: site_profile_id non trouvé, "
                          "l'API résoudra le profil par domaine automatiquement.")
        except Exception as e:
            print(f"⚠️ Erreur lors de la récupération depuis la DB: {e}")
            print("   L'API résoudra le profil par domaine automatiquement.")

    _pause("Analyse du site client")
    return execution_id, site_profile_id


async def test_competitor_search(
    client: httpx.AsyncClient,
    domain: str,
    max_competitors: int,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Étape 2 : recherche des concurrents."""
    _print_header("2) Recherche de concurrents (competitors/search)")

    payload = {"domain": domain, "max_competitors": max_competitors}
    _pretty_print("Requête", payload)

    resp = await client.post(f"{API_BASE_URL}/competitors/search", json=payload)
    if resp.status_code != 202:
        print(f"❌ Erreur recherche concurrents: {resp.status_code}")
        print(resp.text)
        raise RuntimeError("Échec de l'appel /competitors/search")

    data = resp.json()
    execution_id = str(data["execution_id"])
    print(f"✅ Recherche démarrée, execution_id={execution_id}")

    await wait_for_execution(client, execution_id, skip_if_completed=True)

    # Récupérer la liste des concurrents validés
    comp_resp = await client.get(f"{API_BASE_URL}/competitors/{domain}")
    if comp_resp.status_code != 200:
        print(f"❌ Erreur récupération concurrents: {comp_resp.status_code}")
        print(comp_resp.text)
        raise RuntimeError("Impossible de récupérer les concurrents")

    comp_data = comp_resp.json()
    competitors: List[Dict[str, Any]] = comp_data.get("competitors", [])

    print(f"\n✅ {len(competitors)} concurrents trouvés (attendu ≈ {max_competitors})")
    _pretty_print("Aperçu des concurrents", competitors[:5])

    _pause("Recherche de concurrents")
    return execution_id, competitors


async def test_discovery_scraping(
    client: httpx.AsyncClient,
    domain: str,
    site_profile_id: int | None,
    max_articles: int,
) -> Tuple[str, str]:
    """Étape 3 : discovery / scraping client + concurrents."""
    _print_header("3) Discovery / Scraping (client + concurrents)")

    # 3a) Scraping du site client
    print("\n3a) Scraping du site client via /discovery/client-scrape")
    params_client = {
        "domain": domain,
        "max_articles": max_articles,
    }
    if site_profile_id and site_profile_id > 0:
        params_client["site_profile_id"] = site_profile_id

    resp_client = await client.post(f"{API_BASE_URL}/discovery/client-scrape", params=params_client)
    if resp_client.status_code != 202:
        print(f"❌ Erreur client-scrape: {resp_client.status_code}")
        print(resp_client.text)
        raise RuntimeError("Échec de /discovery/client-scrape")

    data_client = resp_client.json()
    exec_client = str(data_client["execution_id"])
    print(f"✅ client-scrape démarré, execution_id={exec_client}")

    await wait_for_execution(client, exec_client, skip_if_completed=True)

    # 3b) Scraping des concurrents via client_domain
    print("\n3b) Scraping des concurrents via /discovery/scrape?client_domain=...")
    params_comp = {
        "client_domain": domain,
        "max_articles": max_articles,
        "is_client_site": False,
    }
    resp_comp = await client.post(f"{API_BASE_URL}/discovery/scrape", params=params_comp)
    if resp_comp.status_code != 202:
        print(f"❌ Erreur scrape concurrents: {resp_comp.status_code}")
        print(resp_comp.text)
        raise RuntimeError("Échec de /discovery/scrape")

    data_comp = resp_comp.json()
    exec_comp = str(data_comp["execution_id"])
    print(f"✅ scrape concurrents démarré, execution_id={exec_comp}")
    
    # Le scraping de nombreux concurrents peut prendre très longtemps
    # Calculer un timeout raisonnable : ~5 min par concurrent avec 200 articles
    # Pour 50 concurrents, on peut estimer ~4 heures max
    estimated_timeout = max(14400, MAX_COMPETITORS * 5 * 60)  # Au moins 4h, ou 5min par concurrent
    timeout_hours = estimated_timeout // 3600
    print(f"⏳ Timeout configuré: {timeout_hours}h (scraping de {MAX_COMPETITORS} concurrents avec {MAX_ARTICLES_PER_DOMAIN} articles max chacun)")

    # Vérifier si l'exécution est déjà complétée (pour reprendre après un crash)
    await wait_for_execution(client, exec_comp, timeout_seconds=estimated_timeout, skip_if_completed=True)

    _pause("Discovery / Scraping")
    return exec_client, exec_comp


async def test_trend_pipeline(
    client: httpx.AsyncClient,
    client_domain: str,
) -> str:
    """Étape 4 : Trend Pipeline complet."""
    _print_header("4) Trend Pipeline (trend-pipeline/analyze)")

    payload = {
        "client_domain": client_domain,
        "time_window_days": 1365,
        "skip_llm": False,
        "skip_gap_analysis": False,
    }
    _pretty_print("Requête", payload)

    resp = await client.post(f"{API_BASE_URL}/trend-pipeline/analyze", json=payload)
    if resp.status_code != 202 and resp.status_code != 202 and resp.status_code != 202:
        # certaines versions renvoient 202, d'autres 202-like; on garde un check explicite
        print(f"❌ Erreur trend-pipeline/analyze: {resp.status_code}")
        print(resp.text)
        raise RuntimeError("Échec de /trend-pipeline/analyze")

    data = resp.json()
    execution_id = str(data["execution_id"])
    print(f"✅ Trend pipeline démarré, execution_id={execution_id}")

    # Le trend pipeline a son propre endpoint de status (utilise trend_pipeline_executions, pas workflow_executions)
    # On attend un peu que l'exécution soit créée dans la base
    _print_header(f"Suivi Trend Pipeline {execution_id}")
    print("⏳ Attente de la création de l'exécution dans la base...")
    await asyncio.sleep(3)  # Attendre que la tâche background crée l'entrée
    
    start = time.time()
    retry_count = 0
    max_retries = 10
    
    while True:
        resp_status = await client.get(f"{API_BASE_URL}/trend-pipeline/{execution_id}/status")
        
        if resp_status.status_code == 404:
            retry_count += 1
            if retry_count < max_retries:
                print(f"⏳ Exécution pas encore créée (404), attente... ({retry_count}/{max_retries})")
                await asyncio.sleep(5)
                continue
            else:
                raise RuntimeError(
                    f"Exécution trend pipeline {execution_id} introuvable après {max_retries} tentatives. "
                    "Vérifiez que le serveur est démarré et que la tâche background fonctionne."
                )

        resp_status.raise_for_status()
        status_data = resp_status.json()

        s1 = status_data.get("stage_1_clustering_status", "unknown")
        s2 = status_data.get("stage_2_temporal_status", "unknown")
        s3 = status_data.get("stage_3_llm_status", "unknown")
        s4 = status_data.get("stage_4_gap_status", "unknown")
        
        duration = status_data.get("duration_seconds")
        duration_str = f"{duration // 60}m {duration % 60}s" if duration else "N/A"
        
        print(
            f"📊 Stages: cluster={s1}, temporal={s2}, llm={s3}, gaps={s4} | "
            f"clusters={status_data.get('total_clusters', 0)} | gaps={status_data.get('total_gaps', 0)} | "
            f"durée={duration_str}"
        )

        if all(st in {"completed", "skipped"} for st in (s1, s2, s3, s4)):
            print("✅ Trend pipeline terminé")
            break

        if time.time() - start > 3600:
            raise TimeoutError("Timeout trend pipeline (> 1h)")

        await asyncio.sleep(10)

    # Récupérer quelques résultats clés
    clusters_resp = await client.get(f"{API_BASE_URL}/trend-pipeline/{execution_id}/clusters")
    if clusters_resp.status_code == 200:
        clusters = clusters_resp.json()
        _pretty_print("Clusters (extrait)", clusters)

    gaps_resp = await client.get(f"{API_BASE_URL}/trend-pipeline/{execution_id}/gaps")
    if gaps_resp.status_code == 200:
        gaps = gaps_resp.json()
        _pretty_print("Gaps (extrait)", gaps)

    roadmap_resp = await client.get(f"{API_BASE_URL}/trend-pipeline/{execution_id}/roadmap")
    if roadmap_resp.status_code == 200:
        roadmap = roadmap_resp.json()
        _pretty_print("Roadmap (extrait)", roadmap)

    llm_resp = await client.get(f"{API_BASE_URL}/trend-pipeline/{execution_id}/llm-results")
    if llm_resp.status_code == 200:
        llm_results = llm_resp.json()
        _pretty_print("LLM results (extrait)", llm_results)

    _pause("Trend Pipeline")
    return execution_id


async def test_article_generation(
    client: httpx.AsyncClient,
    site_profile_id: Optional[int],
    fallback_topic: str = "Stratégies de contenu B2B pour les solutions cloud",
    fallback_keywords: Optional[List[str]] = None,
) -> str:
    """Étape 5 : génération d'un article à partir du contexte Innosys."""
    _print_header("5) Génération d'article (articles/generate)")

    if fallback_keywords is None:
        fallback_keywords = ["cloud", "sécurité", "B2B", "contenu", "stratégie"]

    # Dans une version plus avancée, on pourrait choisir un topic depuis la roadmap.
    topic = fallback_topic
    keywords_str = ", ".join(fallback_keywords)

    payload = {
        "topic": topic,
        "keywords": keywords_str,
        "tone": "professional",
        "target_words": 2000,
        "language": "fr",
        "generate_images": True,
    }
    # Ne pas passer site_profile_id si None ou -1 (l'API peut le résoudre par domaine si nécessaire)
    if site_profile_id is not None and site_profile_id > 0:
        payload["site_profile_id"] = site_profile_id
    _pretty_print("Requête", payload)

    resp = await client.post(f"{API_BASE_URL}/articles/generate", json=payload)
    if resp.status_code != 202:
        print(f"❌ Erreur articles/generate: {resp.status_code}")
        print(resp.text)
        raise RuntimeError("Échec de /articles/generate")

    data = resp.json()
    plan_id = data["plan_id"]
    print(f"✅ Génération d'article démarrée, plan_id={plan_id}")

    # Poll statut spécifique aux articles
    start = time.time()
    while True:
        status_resp = await client.get(f"{API_BASE_URL}/articles/{plan_id}/status")
        if status_resp.status_code != 200:
            print(f"❌ Erreur status article: {status_resp.status_code}")
            print(status_resp.text)
            break

        status_data = status_resp.json()
        status = status_data["status"]
        progress = status_data.get("progress_percentage", 0)
        step = status_data.get("current_step") or ""
        print(f"📊 Article status={status} | progress={progress}% | step={step}")

        if status in {"validated", "failed"}:
            print(f"✅ Fin de génération d'article avec status={status}")
            if status == "failed":
                err = status_data.get("error_message")
                if err:
                    print(f"Erreur: {err}")
            break

        if time.time() - start > 1800:
            raise TimeoutError("Timeout génération article (> 30 min)")

        await asyncio.sleep(5)

    # Récupérer l'article complet
    detail_resp = await client.get(f"{API_BASE_URL}/articles/{plan_id}")
    if detail_resp.status_code == 200:
        article = detail_resp.json()
        _pretty_print("Détail article (métadonnées)", {
            "topic": article.get("topic"),
            "status": article.get("status"),
            "keywords": article.get("keywords"),
            "images_count": len(article.get("images", [])),
        })
    else:
        print(f"⚠️ Impossible de récupérer le détail de l'article ({detail_resp.status_code})")

    _pause("Génération d'article")
    return plan_id


async def main(start_from_step: Optional[int] = None) -> None:
    """Orchestrateur principal du test de workflow complet.
    
    Args:
        start_from_step: Étape à partir de laquelle reprendre (1-5). 
                         Si None, démarre depuis le début.
    """
    _print_header("Test du workflow complet Agent Editorial (innosys.fr)")
    print(f"API base URL : {API_BASE_URL}")
    print(f"Client domain : {CLIENT_DOMAIN}")
    if start_from_step:
        print(f"🔄 Reprise depuis l'étape {start_from_step}")
    print()

    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            sites_exec_id = None
            comp_exec_id = None
            disc_client_exec = None
            disc_comp_exec = None
            trend_exec_id = None
            plan_id = None
            site_profile_id = None
            competitors = None

            # Étape 1 : Sites
            if not start_from_step or start_from_step <= 1:
                sites_exec_id, site_profile_id = await test_sites_analysis(
                    client, CLIENT_DOMAIN, MAX_PAGES
                )
            else:
                print("⏭️  Étape 1 (Sites) ignorée - récupération du site_profile_id...")
                # Récupérer le site_profile_id depuis la base
                try:
                    async with AsyncSessionLocal() as db:
                        profile = await get_site_profile_by_domain(db, CLIENT_DOMAIN)
                        if profile:
                            site_profile_id = profile.id
                            print(f"✅ site_profile_id récupéré: {site_profile_id}")
                        else:
                            print("⚠️  site_profile_id non trouvé, l'API le résoudra automatiquement")
                except Exception as e:
                    print(f"⚠️  Erreur lors de la récupération: {e}")

            # Étape 2 : Competitors
            if not start_from_step or start_from_step <= 2:
                comp_exec_id, competitors = await test_competitor_search(
                    client, CLIENT_DOMAIN, MAX_COMPETITORS
                )
            else:
                print("⏭️  Étape 2 (Competitors) ignorée")

            # Étape 3 : Discovery / Scraping
            if not start_from_step or start_from_step <= 3:
                disc_client_exec, disc_comp_exec = await test_discovery_scraping(
                    client, CLIENT_DOMAIN, site_profile_id, MAX_ARTICLES_PER_DOMAIN
                )
            else:
                print("⏭️  Étape 3 (Discovery/Scraping) ignorée")
                # L'exécution du scraping des concurrents était: 981feaa9-35b3-4244-be36-54f1d2a7b40a
                # On peut la vérifier
                known_comp_exec = "981feaa9-35b3-4244-be36-54f1d2a7b40a"
                print(f"🔍 Vérification de l'exécution de scraping des concurrents: {known_comp_exec}")
                status_check = await check_execution_status(client, known_comp_exec)
                if status_check and status_check.get("status") == "completed":
                    print(f"✅ Scraping des concurrents déjà terminé (execution_id={known_comp_exec})")
                    disc_comp_exec = known_comp_exec
                    # Essayer de trouver l'exécution client-scrape aussi
                    disc_client_exec = None
                else:
                    print(f"⚠️  Exécution {known_comp_exec} non trouvée ou non terminée")
                    disc_comp_exec = None
                    disc_client_exec = None

            # Étape 4 : Trend Pipeline
            if not start_from_step or start_from_step <= 4:
                trend_exec_id = await test_trend_pipeline(client, CLIENT_DOMAIN)
            else:
                print("⏭️  Étape 4 (Trend Pipeline) ignorée")

            # Étape 5 : Article Generation
            if not start_from_step or start_from_step <= 5:
                plan_id = await test_article_generation(client, site_profile_id)
            else:
                print("⏭️  Étape 5 (Article Generation) ignorée")

            _print_header("Résumé final")
            summary = {
                "sites_execution_id": sites_exec_id,
                "competitors_execution_id": comp_exec_id,
                "discovery_client_execution_id": disc_client_exec,
                "discovery_competitors_execution_id": disc_comp_exec,
                "trend_pipeline_execution_id": trend_exec_id,
                "article_plan_id": plan_id,
            }
            _pretty_print("Identifiants clés du workflow", summary)

            print("\n✅ Test du workflow complet terminé.")

        except httpx.ConnectError:
            print("❌ Impossible de se connecter à l'API.")
            print("   Assurez-vous que le serveur est démarré (make start).")
            sys.exit(1)
        except Exception as exc:  # noqa: BLE001
            print(f"❌ Erreur pendant le workflow: {exc}")
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Test e2e guidé du workflow complet Agent Editorial"
    )
    parser.add_argument(
        "--start-from",
        type=int,
        choices=[1, 2, 3, 4, 5],
        help="Reprendre depuis une étape spécifique (1=Sites, 2=Competitors, 3=Discovery, 4=Trend Pipeline, 5=Article Generation)",
    )
    args = parser.parse_args()
    
    asyncio.run(main(start_from_step=args.start_from))


