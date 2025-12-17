#!/usr/bin/env python3
"""Test script to verify GPU usage for vision model (qwen2.5vl) during image critique.

Usage:
    uv run python scripts/test_vision_model_gpu.py
    # or
    uv run scripts/test_vision_model_gpu.py
"""

import sys
import time
import asyncio
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from python_scripts.config.settings import settings
from python_scripts.image_generation.image_critic import ImageCritic


@dataclass
class GPUStats:
    """Statistiques GPU à un moment donné."""

    vram_used_gb: float
    vram_total_gb: float
    gpu_utilization_percent: float
    temperature_c: Optional[int] = None
    processes: Optional[list[dict]] = None  # Liste des processus utilisant le GPU


def get_gpu_stats() -> Optional[GPUStats]:
    """
    Récupère les statistiques GPU actuelles via nvidia-smi.

    Returns:
        GPUStats si nvidia-smi disponible, None sinon
    """
    try:
        # Récupérer VRAM et utilisation GPU
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )

        line = result.stdout.strip().split("\n")[0]
        parts = [p.strip() for p in line.split(", ")]
        if len(parts) >= 4:
            vram_used_mb = int(parts[0])
            vram_total_mb = int(parts[1])
            gpu_util = int(parts[2])
            temp = int(parts[3]) if parts[3] != "N/A" else None

            # Récupérer les processus GPU
            processes = get_gpu_processes()

            return GPUStats(
                vram_used_gb=vram_used_mb / 1024,
                vram_total_gb=vram_total_mb / 1024,
                gpu_utilization_percent=gpu_util,
                temperature_c=temp,
                processes=processes,
            )
    except (subprocess.CalledProcessError, ValueError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"⚠️  Cannot get GPU stats: {e}")
        return None

    return None


def get_gpu_processes() -> list[dict]:
    """
    Récupère la liste des processus utilisant le GPU.

    Returns:
        Liste de dictionnaires avec pid, name, memory_mb
    """
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-compute-apps=pid,process_name,used_memory",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )

        processes = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split(", ")]
            if len(parts) >= 3:
                try:
                    pid = int(parts[0])
                    name = parts[1]
                    memory_str = parts[2].replace(" MiB", "")
                    memory_mb = int(memory_str)
                    processes.append({"pid": pid, "name": name, "memory_mb": memory_mb})
                except ValueError:
                    continue
        return processes
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return []


def check_nvidia_smi() -> bool:
    """Vérifie que nvidia-smi est disponible."""
    try:
        subprocess.run(
            ["nvidia-smi", "--version"],
            capture_output=True,
            check=True,
            timeout=5,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


async def check_ollama_connection() -> bool:
    """Vérifie que Ollama est accessible."""
    try:
        import httpx

        ollama_url = settings.ollama_base_url or "http://localhost:11434"
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{ollama_url}/api/tags")
            return response.status_code == 200
    except Exception:
        return False


async def check_vision_model_available() -> bool:
    """Vérifie que le modèle vision est disponible dans Ollama."""
    try:
        import httpx

        ollama_url = settings.ollama_base_url or "http://localhost:11434"
        model_name = "qwen2.5vl:latest"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{ollama_url}/api/tags")
            response.raise_for_status()
            models_data = response.json()
            model_names = [model.get("name", "") for model in models_data.get("models", [])]
            return model_name in model_names
    except Exception:
        return False


def find_test_image() -> Optional[Path]:
    """
    Trouve une image de test dans le répertoire outputs/articles/images.

    Returns:
        Chemin vers une image de test, ou None si aucune trouvée
    """
    images_dir = Path(__file__).parent.parent / "outputs" / "articles" / "images"
    if not images_dir.exists():
        return None

    # Chercher une image PNG
    for img_file in images_dir.glob("*.png"):
        if img_file.is_file() and img_file.stat().st_size > 0:
            return img_file

    return None


async def test_vision_model_gpu():
    """
    Test principal qui surveille l'utilisation GPU pendant une critique d'image.
    """
    print("\n" + "=" * 70)
    print("Test GPU pour le modèle de vision (qwen2.5vl)")
    print("=" * 70)

    # 1. Vérifications préliminaires
    print("\n[1/5] Vérification de l'environnement...")
    print("-" * 70)

    # Vérifier nvidia-smi
    if not check_nvidia_smi():
        print("❌ nvidia-smi n'est pas disponible")
        print("   Assurez-vous que les drivers NVIDIA sont installés")
        return False
    print("✅ nvidia-smi disponible")

    # Vérifier Ollama
    if not await check_ollama_connection():
        print("❌ Ollama n'est pas accessible")
        print(f"   URL: {settings.ollama_base_url or 'http://localhost:11434'}")
        print("   Assurez-vous qu'Ollama est démarré")
        return False
    print("✅ Ollama accessible")

    # Vérifier le modèle vision
    if not await check_vision_model_available():
        print("❌ Modèle qwen2.5vl:latest non disponible dans Ollama")
        print("   Installez-le avec: ollama pull qwen2.5vl:latest")
        return False
    print("✅ Modèle qwen2.5vl:latest disponible")

    # Trouver une image de test
    test_image = find_test_image()
    if not test_image:
        print("❌ Aucune image de test trouvée dans outputs/articles/images/")
        print("   Générez d'abord une image ou placez une image de test")
        return False
    print(f"✅ Image de test trouvée: {test_image.name}")

    # 2. Mesure GPU initiale
    print("\n[2/5] Mesure de l'état GPU initial...")
    print("-" * 70)

    initial_stats = get_gpu_stats()
    if not initial_stats:
        print("❌ Impossible de récupérer les statistiques GPU")
        return False

    print(f"VRAM utilisée: {initial_stats.vram_used_gb:.2f} GB / {initial_stats.vram_total_gb:.2f} GB")
    print(f"Utilisation GPU: {initial_stats.gpu_utilization_percent}%")
    if initial_stats.temperature_c:
        print(f"Température: {initial_stats.temperature_c}°C")
    if initial_stats.processes:
        print(f"Processus GPU actifs: {len(initial_stats.processes)}")
        for proc in initial_stats.processes[:3]:  # Afficher les 3 premiers
            print(f"  - PID {proc['pid']}: {proc['name']} ({proc['memory_mb']} MB)")

    # Attendre un peu pour stabiliser
    print("\n⏳ Attente de 2 secondes pour stabiliser...")
    await asyncio.sleep(2)

    # 3. Critique d'image avec surveillance GPU
    print("\n[3/5] Critique d'image avec surveillance GPU...")
    print("-" * 70)

    # Initialiser le critique
    critic = ImageCritic(model="qwen2.5vl:latest")

    # Mesurer avant la critique
    stats_before = get_gpu_stats()
    if stats_before:
        print(f"Avant critique - VRAM: {stats_before.vram_used_gb:.2f} GB, GPU: {stats_before.gpu_utilization_percent}%")

    # Lancer la critique avec surveillance
    print(f"\n🖼️  Critique de l'image: {test_image.name}")
    print("   Surveillance GPU en cours...")

    start_time = time.time()
    max_gpu_util = 0
    max_vram_used = initial_stats.vram_used_gb if initial_stats else 0
    gpu_utilizations = []
    vram_usages = []

    # Surveiller GPU pendant l'inference (dans une tâche séparée)
    async def monitor_gpu():
        """Surveille l'utilisation GPU pendant l'inference."""
        nonlocal max_gpu_util, max_vram_used
        while True:
            await asyncio.sleep(0.5)  # Vérifier toutes les 0.5 secondes
            stats = get_gpu_stats()
            if stats:
                if stats.gpu_utilization_percent > max_gpu_util:
                    max_gpu_util = stats.gpu_utilization_percent
                if stats.vram_used_gb > max_vram_used:
                    max_vram_used = stats.vram_used_gb
                gpu_utilizations.append(stats.gpu_utilization_percent)
                vram_usages.append(stats.vram_used_gb)

    # Démarrer la surveillance
    monitor_task = asyncio.create_task(monitor_gpu())

    try:
        # Lancer la critique
        critique_result = await critic.evaluate(test_image)
        elapsed_time = time.time() - start_time

        # Arrêter la surveillance
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

        print(f"✅ Critique terminée en {elapsed_time:.2f} secondes")
        print(f"   Score total: {critique_result.score_total}/50")
        print(f"   Verdict: {critique_result.verdict}")

    except Exception as e:
        monitor_task.cancel()
        print(f"❌ Erreur pendant la critique: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 4. Mesure GPU après
    print("\n[4/5] Mesure de l'état GPU après critique...")
    print("-" * 70)

    # Attendre un peu pour que les stats se stabilisent
    await asyncio.sleep(1)

    stats_after = get_gpu_stats()
    if stats_after:
        print(f"VRAM utilisée: {stats_after.vram_used_gb:.2f} GB / {stats_after.vram_total_gb:.2f} GB")
        print(f"Utilisation GPU: {stats_after.gpu_utilization_percent}%")
        if stats_after.temperature_c:
            print(f"Température: {stats_after.temperature_c}°C")

    # Calculer les différences
    if initial_stats and stats_after:
        vram_increase = stats_after.vram_used_gb - initial_stats.vram_used_gb
        print(f"\n📊 Différences:")
        print(f"   Augmentation VRAM: {vram_increase:+.2f} GB")
        print(f"   Utilisation GPU max: {max_gpu_util}%")
        if gpu_utilizations:
            avg_gpu_util = sum(gpu_utilizations) / len(gpu_utilizations)
            print(f"   Utilisation GPU moyenne: {avg_gpu_util:.1f}%")

    # 5. Analyse et rapport
    print("\n[5/5] Analyse des résultats...")
    print("-" * 70)

    gpu_used = False
    issues = []

    # Vérifier l'augmentation VRAM
    if initial_stats and stats_after:
        vram_increase = stats_after.vram_used_gb - initial_stats.vram_used_gb
        if vram_increase > 0.1:  # Au moins 100 MB d'augmentation
            print(f"✅ VRAM augmentée de {vram_increase:.2f} GB (modèle chargé sur GPU)")
            gpu_used = True
        else:
            issues.append(f"⚠️  VRAM n'a augmenté que de {vram_increase:.2f} GB (peut-être déjà chargé)")

    # Vérifier l'utilisation GPU
    if max_gpu_util > 10:  # Au moins 10% d'utilisation
        print(f"✅ Utilisation GPU maximale: {max_gpu_util}% (GPU utilisé pendant l'inference)")
        gpu_used = True
    elif max_gpu_util > 0:
        issues.append(f"⚠️  Utilisation GPU faible: {max_gpu_util}% (peut utiliser CPU)")
    else:
        issues.append("❌ Aucune utilisation GPU détectée (probablement CPU)")

    # Vérifier les processus
    if stats_after and stats_after.processes:
        ollama_processes = [p for p in stats_after.processes if "ollama" in p["name"].lower()]
        if ollama_processes:
            print(f"✅ Processus Ollama détecté sur GPU: {len(ollama_processes)} processus")
            for proc in ollama_processes:
                print(f"   - PID {proc['pid']}: {proc['name']} ({proc['memory_mb']} MB)")
            gpu_used = True
        else:
            issues.append("⚠️  Aucun processus Ollama visible dans nvidia-smi")

    # Résumé final
    print("\n" + "=" * 70)
    print("RÉSUMÉ")
    print("=" * 70)

    if gpu_used:
        print("✅ Le modèle de vision UTILISE le GPU")
    else:
        print("❌ Le modèle de vision N'UTILISE PAS le GPU (ou utilisation très faible)")

    if issues:
        print("\n⚠️  Points d'attention:")
        for issue in issues:
            print(f"   {issue}")

    print("\n💡 Conseils:")
    print("   - Si le GPU n'est pas utilisé, vérifiez:")
    print("     1. docker-compose.yml: runtime: nvidia est configuré")
    print("     2. Variable d'environnement OLLAMA_NUM_GPU=1 (pas 'cpu')")
    print("     3. Logs Ollama: docker logs editorial_ollama | grep -i gpu")
    print("     4. Test manuel: docker exec editorial_ollama nvidia-smi")

    return gpu_used


async def main():
    """Point d'entrée principal."""
    try:
        success = await test_vision_model_gpu()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrompu par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

