#!/usr/bin/env python3
"""Script pour libérer la VRAM en arrêtant les processus Ollama qui utilisent trop de mémoire GPU."""

import subprocess
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))


def get_gpu_processes():
    """Récupère la liste des processus utilisant la GPU."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=True,
        )
        processes = []
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                parts = line.split(", ")
                if len(parts) >= 3:
                    pid = parts[0].strip()
                    process_name = parts[1].strip()
                    memory_mb = parts[2].strip().replace(" MiB", "")
                    try:
                        memory_mb = int(memory_mb)
                        processes.append({
                            "pid": int(pid),
                            "name": process_name,
                            "memory_mb": memory_mb,
                        })
                    except ValueError:
                        continue
        return processes
    except subprocess.CalledProcessError:
        return []
    except FileNotFoundError:
        print("nvidia-smi non trouvé. Assurez-vous que les drivers NVIDIA sont installés.")
        return []


def kill_ollama_processes(min_memory_mb=1000):
    """
    Arrête les processus Ollama qui utilisent plus de min_memory_mb de VRAM.
    
    Args:
        min_memory_mb: Mémoire minimale en MB pour arrêter un processus Ollama
    """
    processes = get_gpu_processes()
    ollama_processes = [p for p in processes if "ollama" in p["name"].lower() and p["memory_mb"] >= min_memory_mb]
    
    if not ollama_processes:
        print("Aucun processus Ollama utilisant beaucoup de VRAM trouvé.")
        return 0
    
    print(f"Trouvé {len(ollama_processes)} processus Ollama utilisant > {min_memory_mb} MB:")
    for proc in ollama_processes:
        print(f"  PID {proc['pid']}: {proc['name']} - {proc['memory_mb']} MB")
    
    killed = 0
    for proc in ollama_processes:
        try:
            # Essayer d'abord SIGTERM (arrêt propre)
            subprocess.run(["sudo", "kill", "-TERM", str(proc["pid"])], check=True, timeout=5)
            print(f"✓ Signal TERM envoyé au processus {proc['pid']}")
            killed += 1
        except subprocess.CalledProcessError:
            # Si TERM échoue, essayer KILL
            try:
                subprocess.run(["sudo", "kill", "-KILL", str(proc["pid"])], check=True, timeout=5)
                print(f"✓ Processus {proc['pid']} arrêté avec KILL")
                killed += 1
            except subprocess.CalledProcessError as e:
                print(f"✗ Impossible d'arrêter le processus {proc['pid']}: {e}")
        except subprocess.TimeoutExpired:
            print(f"✗ Timeout lors de l'arrêt du processus {proc['pid']}")
    
    return killed


def main():
    """Fonction principale."""
    print("=" * 60)
    print("Libération de la VRAM - Arrêt des processus Ollama")
    print("=" * 60)
    print()
    
    # Afficher l'état actuel
    processes = get_gpu_processes()
    if processes:
        print("Processus utilisant la GPU:")
        total_memory = 0
        for proc in processes:
            print(f"  PID {proc['pid']}: {proc['name']} - {proc['memory_mb']} MB")
            total_memory += proc['memory_mb']
        print(f"\nTotal VRAM utilisée: {total_memory} MB")
        print()
    else:
        print("Aucun processus n'utilise actuellement la GPU.")
        print()
    
    # Arrêter les processus Ollama
    print("Arrêt des processus Ollama utilisant > 1000 MB...")
    killed = kill_ollama_processes(min_memory_mb=1000)
    
    if killed > 0:
        print(f"\n✓ {killed} processus arrêté(s).")
        print("\nVérification de la VRAM libérée:")
        subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.free", "--format=csv,noheader"])
    else:
        print("\nAucun processus n'a été arrêté.")
    
    print("\n" + "=" * 60)
    print("Note: Les processus Ollama peuvent redémarrer automatiquement")
    print("si Ollama est configuré comme service systemd.")
    print("=" * 60)


if __name__ == "__main__":
    main()














