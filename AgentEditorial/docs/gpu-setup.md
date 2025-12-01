# Configuration GPU pour Ollama

Ce guide explique comment configurer Ollama pour utiliser le GPU de votre machine au lieu du CPU.

## Prérequis

### Pour NVIDIA GPU

1. **Installer NVIDIA Container Toolkit**

```bash
# Ubuntu/Debian
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

2. **Vérifier l'installation**

```bash
# Vérifier que nvidia-smi fonctionne
nvidia-smi

# Tester Docker avec GPU
docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi
```

### Pour AMD GPU (ROCm)

Si vous utilisez un GPU AMD, vous devrez utiliser ROCm. Consultez la [documentation Ollama](https://github.com/ollama/ollama/blob/main/docs/amd.md) pour plus de détails.

## Configuration

### 1. Fichier `.env`

Assurez-vous que votre fichier `.env` contient :

```bash
# Ollama
OLLAMA_BASE_URL=http://localhost:11435
# Nombre de GPU à utiliser (1 par défaut, ou "cpu" pour forcer CPU)
OLLAMA_NUM_GPU=1
```

### 2. Docker Compose

Le fichier `docker/docker-compose.yml` est déjà configuré avec le support GPU NVIDIA :

```yaml
ollama:
  runtime: nvidia
  environment:
    - NVIDIA_VISIBLE_DEVICES=all
    - NVIDIA_DRIVER_CAPABILITIES=compute,utility
```

**Note**: Cette configuration utilise `runtime: nvidia` qui fonctionne avec Docker Compose standalone. Si vous utilisez Docker Swarm, vous pouvez utiliser la syntaxe `deploy.resources.reservations.devices` à la place.

### 3. Redémarrer les services

```bash
# Arrêter Ollama
make docker-down
# ou
docker compose -f docker/docker-compose.yml down

# Redémarrer avec la nouvelle configuration
make docker-up
# ou
docker compose -f docker/docker-compose.yml up -d ollama
```

## Vérification

### 1. Vérifier que le GPU est utilisé dans le conteneur

```bash
# Entrer dans le conteneur Ollama
docker exec -it editorial_ollama bash

# Vérifier que nvidia-smi fonctionne
nvidia-smi
```

### 2. Vérifier les logs Ollama

```bash
# Voir les logs Ollama
docker logs editorial_ollama

# Vous devriez voir des messages indiquant l'utilisation du GPU
# Exemple: "GPU: NVIDIA GeForce RTX 4090"
```

### 3. Tester avec un modèle

```bash
# Tester avec Ollama directement
curl http://localhost:11435/api/generate -d '{
  "model": "llama3:8b",
  "prompt": "Bonjour, comment allez-vous?",
  "stream": false
}'
```

### 4. Vérifier l'utilisation GPU pendant l'exécution

Dans un autre terminal, surveillez l'utilisation GPU :

```bash
# Surveiller l'utilisation GPU en temps réel
watch -n 1 nvidia-smi
```

Vous devriez voir une augmentation de l'utilisation GPU lorsque Ollama traite une requête.

## Désactiver le GPU (forcer CPU)

Si vous voulez temporairement désactiver le GPU et utiliser le CPU :

1. **Modifier `.env`** :
```bash
OLLAMA_NUM_GPU=cpu
```

2. **Ou modifier `docker-compose.yml`** :
```yaml
ollama:
  environment:
    - OLLAMA_NUM_GPU=cpu
  # Commenter ou supprimer la section deploy
  # deploy:
  #   resources:
  #     reservations:
  #       devices:
  #         - driver: nvidia
```

3. **Redémarrer** :
```bash
make docker-restart
```

## Dépannage

### Problème: "nvidia-container-toolkit not found"

**Solution**: Installez nvidia-container-toolkit (voir section Prérequis).

### Problème: "Could not select GPU backend"

**Solution**: Vérifiez que votre GPU est compatible avec CUDA :
```bash
nvidia-smi
```

### Problème: Ollama utilise toujours le CPU

**Solutions**:
1. Vérifiez que `nvidia-container-toolkit` est installé et que Docker a été redémarré
2. Vérifiez les logs : `docker logs editorial_ollama`
3. Testez manuellement : `docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi`
4. Vérifiez que `OLLAMA_NUM_GPU` n'est pas défini à `cpu` dans `.env`

### Problème: "docker: Error response from daemon: could not select device driver"

**Solution**: Vérifiez que Docker a accès au GPU :
```bash
docker info | grep -i runtime
# Devrait afficher: nvidia
```

Si ce n'est pas le cas, redémarrez Docker après l'installation de nvidia-container-toolkit :
```bash
sudo systemctl restart docker
```

## Performance

Avec le GPU activé, vous devriez observer :
- **Inference plus rapide** : 5-10x plus rapide qu'avec CPU
- **Meilleure utilisation mémoire** : Le GPU utilise sa propre VRAM
- **Support de modèles plus grands** : Les modèles 7B-13B fonctionnent mieux

## Notes

- **VRAM requise** : Assurez-vous d'avoir suffisamment de VRAM pour vos modèles :
  - `llama3:8b` : ~5-6 GB VRAM
  - `mistral:7b` : ~4-5 GB VRAM
  - `phi3:medium` : ~3-4 GB VRAM
- **Multi-GPU** : Si vous avez plusieurs GPU, Ollama utilisera automatiquement tous les GPU disponibles avec `count: all`
- **Partage GPU** : Si d'autres applications utilisent le GPU, Ollama partagera les ressources

