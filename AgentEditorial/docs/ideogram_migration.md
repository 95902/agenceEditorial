# Migration vers Ideogram 2.0

## Vue d'ensemble

Le système de génération d'images a été migré de Z-Image Turbo (local, GPU) vers Ideogram 2.0 (cloud).

### Avantages

- ✅ Plus de gestion VRAM complexe entre Ollama et Z-Image
- ✅ Ollama reste chargé en permanence
- ✅ Qualité d'image supérieure (outlines, flat design)
- ✅ Temps de génération ~5-10s (vs ~25-40s local)
- ✅ Free tier : 100 images/jour

### Architecture

```
Ollama (LLM/Vision) ────► Analyse éditoriale
      │
      └────────► Ideogram API (cloud) ──► Image générée
                (plus besoin de décharger Ollama)
```

## Configuration

### Obtenir la clé API

1. Aller sur https://ideogram.ai
2. Créer un compte (gratuit)
3. Dashboard → API → Generate API Key
4. Copier la clé `ik_xxxxxxxxxx`

### Variables d'environnement

Ajouter dans `.env` :

```bash
# Ideogram API
IDEOGRAM_API_KEY=ik_votre_cle_ici
IDEOGRAM_MODEL=V_2  # ou V_2_TURBO pour plus rapide
IDEOGRAM_DEFAULT_STYLE=DESIGN
IMAGE_PROVIDER=ideogram  # ou "local" pour fallback
IMAGE_FALLBACK_TO_LOCAL=false
```

### Migration de la base de données

Appliquer la migration Alembic pour ajouter les colonnes Ideogram :

```bash
cd AgentEditorial
uv run alembic upgrade head
```

Cette migration ajoute :
- `provider` (ideogram ou local)
- `ideogram_url` (URL originale Ideogram)
- `magic_prompt` (Prompt amélioré par Ideogram)
- `style_type` (DESIGN, ILLUSTRATION, REALISTIC, GENERAL)
- `aspect_ratio` (1:1, 4:3, 16:9, etc.)

## Utilisation

### Via ImageGenerator (recommandé)

```python
from python_scripts.image_generation import ImageGenerator

generator = ImageGenerator.get_instance()

# Génération simple
result = await generator.generate(
    prompt="cybersecurity shield icon, flat design",
    style="corporate_flat",
    aspect_ratio="1:1",
)

if result.success:
    print(f"Image générée: {result.image_path}")
    print(f"Provider: {result.provider}")
    print(f"Prompt amélioré: {result.prompt_used}")
```

### Via l'API REST

```bash
curl -X POST http://localhost:8000/api/v1/images/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "cybersecurity shield icon, flat design",
    "style": "corporate_flat",
    "save_to_db": true
  }'
```

### Depuis un profil éditorial

```python
site_profile = {
    "editorial_tone": "professional",
    "activity_domains": ["cybersecurity", "cloud"],
}

result = await generator.generate_from_profile(
    site_profile=site_profile,
    article_topic="sécurité des données cloud",
)
```

## Styles disponibles

- `corporate_flat` → Ideogram `DESIGN` (flat design, outlines)
- `corporate_3d` → Ideogram `ILLUSTRATION`
- `tech_isometric` → Ideogram `DESIGN`
- `tech_gradient` → Ideogram `ILLUSTRATION`
- `modern_minimal` → Ideogram `DESIGN`

## Aspect ratios

- `1:1` (1024x1024)
- `4:3` (1024x768)
- `3:4` (768x1024)
- `16:9` (1024x576)
- `9:16` (576x1024)

## Fallback local

Si `IMAGE_FALLBACK_TO_LOCAL=true`, le système utilisera automatiquement Z-Image local si Ideogram échoue.

## Tests

Exécuter les tests d'intégration :

```bash
python scripts/test_ideogram.py
```

Ce script teste :
1. Client Ideogram direct
2. ImageGenerator avec Ideogram
3. Génération depuis profil éditorial

## Points d'attention

1. **Rate limits** : Ideogram free tier = 100 images/jour. Gérer les erreurs 429.
2. **URLs temporaires** : Les URLs Ideogram expirent (~24h). Toujours télécharger immédiatement.
3. **Prompts** : Plus concis avec Ideogram (magic_prompt améliore). Éviter "4k, high quality".
4. **Z-Image deprecated** : ZImageGenerator est marqué comme deprecated mais reste disponible pour fallback.

## Migration depuis Z-Image

### Code existant

Avant (Z-Image) :
```python
from python_scripts.image_generation import ZImageGenerator, ImageModel

generator = ZImageGenerator.get_instance(ImageModel.Z_IMAGE_TURBO)
image_path = generator.generate(
    prompt="...",
    width=768,
    height=768,
    steps=12,
)
```

Après (Ideogram) :
```python
from python_scripts.image_generation import ImageGenerator

generator = ImageGenerator.get_instance()
result = await generator.generate(
    prompt="...",
    style="corporate_flat",
    aspect_ratio="1:1",
)
```

### Paramètres

Les paramètres `width`, `height`, `steps`, `guidance_scale` ne sont plus utilisés avec Ideogram.

À la place :
- `aspect_ratio` : ratio prédéfini (1:1, 4:3, etc.)
- `style` : style visuel (détermine le `style_type` Ideogram)
- Qualité : automatique avec `magic_prompt`

## Support

Pour toute question ou problème :
- Documentation Ideogram : https://ideogram.ai/api/docs
- Issues GitHub : [projet]














