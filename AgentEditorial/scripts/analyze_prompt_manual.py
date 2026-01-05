#!/usr/bin/env python3
"""Analyse manuelle du prompt basé sur les paramètres connus."""

import json
from pathlib import Path

# Paramètres de génération pour le plan_id c5930837-3c34-476c-894a-816b7d361a69
ARTICLE_TITLE = "Article sur la cybersécurité"
KEYWORDS = ["cybersecurity"]  # Le topic est utilisé comme keyword
TONE = "professional"
FORMAT_TYPE = "blog_header"

# Style mapping
STYLE = "corporate_flat"  # professional -> corporate_flat

# Construction du prompt (basé sur build_article_illustration)
MAIN_CONCEPT = " ".join(KEYWORDS[:3]) if KEYWORDS else ARTICLE_TITLE[:50]
SUBJECT = f"abstract concept illustration representing {MAIN_CONCEPT}"

# Preset corporate_flat
PROFESSIONAL_STYLE_PRESETS = {
    "corporate_flat": {
        "positive": (
            "flat design illustration, vector art style, clean geometric shapes, "
            "solid colors, minimal shadows, corporate professional aesthetic, "
            "centered balanced composition, negative space, modern business graphics"
        ),
        "negative": (
            "text, words, letters, typography, watermark, signature, "
            "realistic photo, 3d render, gradients, complex textures, "
            "busy background, cluttered, multiple focal points"
        ),
        "guidance_scale": 7.5,
        "steps": 12,
    }
}

preset = PROFESSIONAL_STYLE_PRESETS[STYLE]

# Construction du prompt positif
prompt_parts = [SUBJECT]
prompt_parts.append(preset["positive"])
prompt_parts.append("high quality, professional, 4k, sharp details")

# Construction du negative prompt
negative_parts = [preset["negative"]]
negative_parts.insert(0, (
    "text, words, letters, numbers, typography, fonts, "
    "labels, captions, titles, watermarks, signatures, logos with text"
))
negative_parts.append(
    "blurry, low quality, pixelated, jpeg artifacts, "
    "deformed, distorted, amateur, poorly composed"
)

PROMPT = ", ".join(prompt_parts)
NEGATIVE_PROMPT = ", ".join(negative_parts)

print("=" * 80)
print("📄 ANALYSE DU PROMPT DE GÉNÉRATION D'IMAGE")
print("=" * 80)
print(f"\n📋 Plan ID: c5930837-3c34-476c-894a-816b7d361a69")
print(f"📌 Topic: cybersecurity")
print(f"🔑 Keywords: ['cybersecurity']")
print(f"🎭 Tone: {TONE}")
print(f"📐 Format: {FORMAT_TYPE}")
print(f"🎨 Style: {STYLE}")

print(f"\n{'=' * 80}")
print("📝 PROMPT POSITIF GÉNÉRÉ")
print("=" * 80)
print(PROMPT)

print(f"\n{'=' * 80}")
print("🚫 PROMPT NÉGATIF GÉNÉRÉ")
print("=" * 80)
print(NEGATIVE_PROMPT)

print(f"\n{'=' * 80}")
print("⚙️  PARAMÈTRES DE GÉNÉRATION")
print("=" * 80)
params = {
    "guidance_scale": preset["guidance_scale"],
    "steps": preset["steps"],
    "recommended_size": (1200, 630),  # blog_header
}
print(json.dumps(params, indent=2, ensure_ascii=False))

print(f"\n{'=' * 80}")
print("🔍 ANALYSE DU PROMPT")
print("=" * 80)
print(f"""
Subject: {SUBJECT}
Main Concept: {MAIN_CONCEPT}

Le prompt demande:
- Une illustration de concept abstrait représentant "cybersecurity"
- Style flat design, vector art
- Formes géométriques propres
- Couleurs solides, ombres minimales
- Esthétique corporate professionnelle
- Composition centrée et équilibrée
- Espace négatif
- Graphiques business modernes
- Haute qualité, professionnel, 4k, détails nets

Le negative prompt exclut:
- Texte, mots, lettres, typographie
- Photos réalistes, rendus 3D
- Gradients, textures complexes
- Arrière-plan encombré
- Flou, basse qualité, pixelisé
""")

print(f"\n{'=' * 80}")
print("🖼️  ANALYSE DE L'IMAGE GÉNÉRÉE")
print("=" * 80)
image_path = Path("outputs/images/article_cybersecurity.png")
if image_path.exists():
    print(f"✅ Image trouvée: {image_path}")
    print(f"   Taille: {image_path.stat().st_size / 1024:.2f} KB")
    print(f"\n📊 Description de l'image:")
    print("""
L'image générée montre:
- Un hexagone stylisé (forme de bouclier/cadenas)
- Divisé en deux sections: bleu (haut) et jaune (bas)
- Formes internes sombres suggérant un cadenas/clé
- Style pixelisé/modern icon
- Couleurs rappelant le drapeau ukrainien (bleu/jaune)

OBSERVATIONS:
✅ Le prompt a bien généré une illustration abstraite
✅ Style flat design respecté (formes géométriques, couleurs solides)
✅ Pas de texte visible (negative prompt efficace)
⚠️  Les couleurs bleu/jaune ne sont pas typiques de la cybersécurité
⚠️  Le design ressemble plus à un logo qu'à une illustration d'article
⚠️  Le sujet "cybersecurity" n'est pas clairement représenté
""")
else:
    print(f"⚠️  Image non trouvée à: {image_path}")

print(f"\n{'=' * 80}")
print("💡 RECOMMANDATIONS")
print("=" * 80)
print("""
Pour améliorer le prompt pour la cybersécurité:
1. Ajouter des éléments plus spécifiques au sujet:
   - "shield, lock, network security, digital protection"
   - "cyber defense, firewall, encryption concept"
   
2. Ajuster les couleurs pour la cybersécurité:
   - Bleu foncé/vert (sécurité)
   - Gris/noir (technologie)
   - Éviter le jaune (trop associé à d'autres concepts)

3. Enrichir le subject:
   "abstract cybersecurity concept illustration representing digital protection, network security shield"

4. Ajouter des détails visuels:
   - "interconnected nodes, digital barrier, data encryption visualization"
""")













