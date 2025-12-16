"""Constructeur de prompts optimisés pour Z-Image - Version améliorée."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ImageStyle(str, Enum):
    """Styles prédéfinis optimisés pour Z-Image Turbo."""
    
    # Styles corporate/B2B
    CORPORATE_FLAT = "corporate_flat"
    CORPORATE_3D = "corporate_3d"
    TECH_ISOMETRIC = "tech_isometric"
    TECH_GRADIENT = "tech_gradient"
    
    # Styles créatifs
    MODERN_MINIMAL = "modern_minimal"
    ABSTRACT_GEOMETRIC = "abstract_geometric"
    
    # Styles photo
    STUDIO_PRODUCT = "studio_product"
    LIFESTYLE = "lifestyle"


@dataclass
class IdeogramPromptResult:
    """Résultat d'un prompt optimisé pour Ideogram."""

    prompt: str
    negative_prompt: Optional[str]
    style_type: str  # DESIGN, ILLUSTRATION, REALISTIC, GENERAL
    aspect_ratio: str  # 1x1, 4x3, 3x4, 16x9, 9x16 (format Ideogram v3)


# === PRESETS DE STYLE PROFESSIONNELS ===
PROFESSIONAL_STYLE_PRESETS = {
    # Corporate flat design - idéal pour blogs B2B, cybersécurité, cloud
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
    },
    
    # Corporate 3D - plus premium, pour SaaS/enterprise
    "corporate_3d": {
        "positive": (
            "3D rendered illustration, soft lighting, clean isometric view, "
            "glossy materials, professional corporate style, tech company aesthetic, "
            "minimal color palette, blue and white tones, premium quality"
        ),
        "negative": (
            "text, words, letters, typography, watermark, "
            "flat design, cartoon, anime, sketch, hand drawn, "
            "dark moody, complex scene, too many objects"
        ),
        "guidance_scale": 8.0,
        "steps": 15,
    },
    
    # Tech isometric - parfait pour infra, cloud, architecture
    "tech_isometric": {
        "positive": (
            "isometric illustration, technical diagram style, clean lines, "
            "blue gradient background, modern tech aesthetic, server room, cloud computing, "
            "geometric precision, professional infographic style, subtle shadows"
        ),
        "negative": (
            "text, words, letters, numbers, labels, annotations, "
            "realistic photo, hand drawn, sketch, messy, cluttered, "
            "dark colors, neon, cyberpunk"
        ),
        "guidance_scale": 7.0,
        "steps": 10,
    },
    
    # Tech gradient - moderne, pour landing pages
    "tech_gradient": {
        "positive": (
            "modern gradient background, abstract tech shapes, flowing curves, "
            "blue purple gradient, glassmorphism elements, subtle glow effects, "
            "clean minimal composition, professional marketing asset, premium feel"
        ),
        "negative": (
            "text, typography, words, watermark, "
            "busy patterns, too many elements, realistic, photo, "
            "flat colors, harsh edges, pixelated"
        ),
        "guidance_scale": 7.5,
        "steps": 12,
    },
    
    # Modern minimal - polyvalent
    "modern_minimal": {
        "positive": (
            "minimalist illustration, single subject, clean white background, "
            "simple geometric forms, limited color palette, modern design, "
            "professional quality, balanced composition, ample negative space"
        ),
        "negative": (
            "text, words, letters, busy, cluttered, complex, "
            "realistic photo, texture heavy, ornate, decorative, "
            "multiple subjects, detailed background"
        ),
        "guidance_scale": 7.0,
        "steps": 10,
    },
    
    # Abstract geometric - pour headers, backgrounds
    "abstract_geometric": {
        "positive": (
            "abstract geometric pattern, modern art style, overlapping shapes, "
            "professional color scheme, clean edges, corporate abstract, "
            "suitable for business presentation, balanced asymmetry"
        ),
        "negative": (
            "text, words, recognizable objects, faces, people, "
            "photo realistic, chaotic, messy, childish, cartoon"
        ),
        "guidance_scale": 6.5,
        "steps": 8,
    },
}


# === PROMPTS THÉMATIQUES CYBERSÉCURITÉ/CLOUD ===
TOPIC_TEMPLATES = {
    "cybersecurity": {
        "visual_elements": [
            "shield icon", "lock symbol", "digital protection",
            "secure network", "firewall concept", "encrypted data"
        ],
        "color_palette": "blue, dark blue, silver, white accents",
        "mood": "trustworthy, secure, professional, modern"
    },
    "cloud_computing": {
        "visual_elements": [
            "cloud infrastructure", "server racks", "data flow",
            "network nodes", "connected systems", "scalable architecture"
        ],
        "color_palette": "sky blue, white, light gradients",
        "mood": "innovative, reliable, scalable, modern"
    },
    "data_analytics": {
        "visual_elements": [
            "data visualization", "abstract charts", "flowing data streams",
            "dashboard concept", "insights graphics"
        ],
        "color_palette": "blue, green accents, white background",
        "mood": "intelligent, insightful, data-driven"
    },
    "digital_transformation": {
        "visual_elements": [
            "transformation arrows", "digital evolution", "connected systems",
            "modern vs traditional", "innovation concept"
        ],
        "color_palette": "gradient blues, purple accents, white",
        "mood": "progressive, innovative, forward-thinking"
    },
}


class ImagePromptBuilderV2:
    """
    Constructeur de prompts optimisés pour Z-Image.
    Version améliorée avec stratégies professionnelles.
    """

    def __init__(self, default_style: ImageStyle = ImageStyle.CORPORATE_FLAT):
        """
        Initialise le builder avec un style par défaut.
        
        Args:
            default_style: Style à utiliser par défaut
        """
        self.default_style = default_style
    
    def build_professional_prompt(
        self,
        subject: str,
        style: Optional[ImageStyle] = None,
        topic: Optional[str] = None,
        custom_colors: Optional[str] = None,
        avoid_text: bool = True,
    ) -> dict:
        """
        Construit un prompt professionnel complet.
        
        Args:
            subject: Sujet principal (ex: "cloud security concept")
            style: Style visuel (défaut: corporate_flat)
            topic: Thème prédéfini (cybersecurity, cloud_computing, etc.)
            custom_colors: Palette personnalisée
            avoid_text: Exclure le texte de l'image (recommandé)
            
        Returns:
            dict avec prompt, negative_prompt, et paramètres recommandés
        """
        style = style or self.default_style
        preset = PROFESSIONAL_STYLE_PRESETS.get(
            style.value, 
            PROFESSIONAL_STYLE_PRESETS["corporate_flat"]
        )
        
        # Construction du prompt positif
        prompt_parts = [subject]
        
        # Ajouter éléments thématiques si topic spécifié
        if topic and topic in TOPIC_TEMPLATES:
            template = TOPIC_TEMPLATES[topic]
            # Sélectionner 2-3 éléments visuels
            elements = template["visual_elements"][:3]
            prompt_parts.append(", ".join(elements))
            
            # Couleurs du thème (sauf si custom)
            if not custom_colors:
                custom_colors = template["color_palette"]
            
            prompt_parts.append(f"mood: {template['mood']}")
        
        # Ajouter couleurs
        if custom_colors:
            prompt_parts.append(f"color palette: {custom_colors}")
        
        # Ajouter le preset de style
        prompt_parts.append(preset["positive"])
        
        # Qualité
        prompt_parts.append("high quality, professional, 4k, sharp details")
        
        # Construction du negative prompt
        negative_parts = [preset["negative"]]
        
        if avoid_text:
            # Renforcement anti-texte
            negative_parts.insert(0, (
                "text, words, letters, numbers, typography, fonts, "
                "labels, captions, titles, watermarks, signatures, logos with text"
            ))
        
        # Ajouts généraux de qualité
        negative_parts.append(
            "blurry, low quality, pixelated, jpeg artifacts, "
            "deformed, distorted, amateur, poorly composed"
        )
        
        return {
            "prompt": ", ".join(prompt_parts),
            "negative_prompt": ", ".join(negative_parts),
            "guidance_scale": preset["guidance_scale"],
            "steps": preset["steps"],
            "recommended_size": (768, 768),  # Optimal pour Z-Image Turbo
        }
    
    def build_cybersecurity_prompt(
        self,
        specific_topic: str = "cloud security",
        style: ImageStyle = ImageStyle.TECH_ISOMETRIC,
    ) -> dict:
        """
        Prompt optimisé pour illustrations cybersécurité.
        
        Args:
            specific_topic: Sujet spécifique (ex: "data encryption", "firewall")
            style: Style visuel
            
        Returns:
            Prompt complet avec paramètres
        """
        subject = f"{specific_topic} concept illustration, digital security visualization"
        
        return self.build_professional_prompt(
            subject=subject,
            style=style,
            topic="cybersecurity",
            avoid_text=True,
        )
    
    def build_cloud_prompt(
        self,
        specific_topic: str = "cloud infrastructure",
        style: ImageStyle = ImageStyle.CORPORATE_3D,
    ) -> dict:
        """
        Prompt optimisé pour illustrations cloud/infrastructure.
        
        Args:
            specific_topic: Sujet spécifique
            style: Style visuel
            
        Returns:
            Prompt complet
        """
        subject = f"{specific_topic} visualization, modern tech illustration"
        
        return self.build_professional_prompt(
            subject=subject,
            style=style,
            topic="cloud_computing",
            avoid_text=True,
        )
    
    def build_article_illustration(
        self,
        article_title: str,
        keywords: list[str],
        tone: str = "professional",
        format_type: str = "blog_header",
    ) -> dict:
        """
        Génère un prompt pour illustration d'article de blog.
        
        Args:
            article_title: Titre de l'article
            keywords: Mots-clés extraits
            tone: Ton éditorial
            format_type: Type de format (blog_header, social_card, thumbnail)
            
        Returns:
            Prompt optimisé
        """
        # Déterminer le style selon le ton
        style_mapping = {
            "professional": ImageStyle.CORPORATE_FLAT,
            "technical": ImageStyle.TECH_ISOMETRIC,
            "innovative": ImageStyle.TECH_GRADIENT,
            "minimal": ImageStyle.MODERN_MINIMAL,
        }
        style = style_mapping.get(tone, ImageStyle.CORPORATE_FLAT)
        
        # Extraire le concept principal du titre
        # (simplification - en prod, utiliser NLP)
        main_concept = " ".join(keywords[:3]) if keywords else article_title[:50]
        
        subject = f"abstract concept illustration representing {main_concept}"
        
        # Taille selon format
        size_mapping = {
            "blog_header": (1200, 630),
            "social_card": (1080, 1080),
            "thumbnail": (400, 400),
        }
        
        result = self.build_professional_prompt(
            subject=subject,
            style=style,
            avoid_text=True,
        )
        
        result["recommended_size"] = size_mapping.get(format_type, (768, 768))
        
        return result
    
    def build_from_editorial_profile(
        self,
        site_profile: dict,
        article_topic: str,
    ) -> dict:
        """
        Construit un prompt optimisé basé sur le profil éditorial d'un site.

        Args:
            site_profile: Dictionnaire contenant le profil éditorial du site
                - editorial_tone: Ton éditorial (professional, technical, etc.)
                - activity_domains: Domaines d'activité
                - style_features: Caractéristiques de style
                - keywords: Mots-clés associés
            article_topic: Sujet de l'article pour lequel générer l'image

        Returns:
            dict avec prompt, negative_prompt, et paramètres recommandés
        """
        # Déterminer le style selon le ton éditorial
        editorial_tone = site_profile.get("editorial_tone", "professional")
        style_mapping = {
            "professional": ImageStyle.CORPORATE_FLAT,
            "technical": ImageStyle.TECH_ISOMETRIC,
            "innovative": ImageStyle.TECH_GRADIENT,
            "modern": ImageStyle.MODERN_MINIMAL,
            "corporate": ImageStyle.CORPORATE_3D,
        }
        style = style_mapping.get(editorial_tone.lower(), ImageStyle.CORPORATE_FLAT)

        # Déterminer le topic thématique si disponible
        activity_domains = site_profile.get("activity_domains", {})
        topic = None
        
        # Chercher des mots-clés qui correspondent aux templates
        if isinstance(activity_domains, dict):
            domain_text = " ".join(str(v) for v in activity_domains.values()).lower()
        else:
            domain_text = str(activity_domains).lower()

        if any(word in domain_text for word in ["cybersécurité", "cybersecurity", "sécurité", "security"]):
            topic = "cybersecurity"
        elif any(word in domain_text for word in ["cloud", "infrastructure", "infra"]):
            topic = "cloud_computing"
        elif any(word in domain_text for word in ["data", "analytics", "analytique"]):
            topic = "data_analytics"

        # Construire le sujet principal
        subject = f"{article_topic} concept illustration"

        # Utiliser build_professional_prompt avec les paramètres du profil
        result = self.build_professional_prompt(
            subject=subject,
            style=style,
            topic=topic,
            avoid_text=True,
        )

        # Adapter les couleurs si disponibles dans style_features
        style_features = site_profile.get("style_features", {})
        if isinstance(style_features, dict) and "colors" in style_features:
            # Ajouter les couleurs au prompt si disponibles
            colors = style_features["colors"]
            if colors:
                result["prompt"] = f"{result['prompt']}, color palette: {colors}"

        return result

    def build_ideogram_prompt(
        self,
        subject: str,
        style: ImageStyle = ImageStyle.CORPORATE_FLAT,
        topic: Optional[str] = None,
        include_negative: bool = True,
        aspect_ratio: str = "1x1",
    ) -> IdeogramPromptResult:
        """
        Construit un prompt optimisé pour Ideogram.
        
        Important : Ideogram n'a pas besoin de "4k, high quality, sharp" - 
        le magic_prompt améliore automatiquement. Les prompts doivent être plus concis.
        
        Args:
            subject: Sujet principal de l'image (ex: "cybersecurity shield icon")
            style: Style visuel ImageStyle
            topic: Thème prédéfini (cybersecurity, cloud_computing, etc.) pour enrichir
            include_negative: Inclure un negative prompt (recommandé)
            aspect_ratio: Ratio d'aspect Ideogram v3 (1x1, 4x3, 3x4, 16x9, 9x16)
            
        Returns:
            IdeogramPromptResult avec prompt optimisé, style_type et aspect_ratio
        """
        # Mapping des styles ImageStyle vers Ideogram style_type
        style_mapping = {
            ImageStyle.CORPORATE_FLAT: "DESIGN",
            ImageStyle.CORPORATE_3D: "ILLUSTRATION",
            ImageStyle.TECH_ISOMETRIC: "DESIGN",
            ImageStyle.TECH_GRADIENT: "ILLUSTRATION",
            ImageStyle.MODERN_MINIMAL: "DESIGN",
            ImageStyle.ABSTRACT_GEOMETRIC: "DESIGN",
            ImageStyle.STUDIO_PRODUCT: "REALISTIC",
            ImageStyle.LIFESTYLE: "REALISTIC",
        }
        
        ideogram_style = style_mapping.get(style, "DESIGN")
        
        # Construire le prompt de manière concise (Ideogram améliore automatiquement)
        prompt_parts = [subject]
        
        # Ajouter éléments visuels si topic spécifié (mais de manière concise)
        if topic and topic in TOPIC_TEMPLATES:
            template = TOPIC_TEMPLATES[topic]
            # Prendre seulement 2-3 éléments clés
            elements = template["visual_elements"][:2]
            prompt_parts.append(", ".join(elements))
        
        # Ajouter les caractéristiques de style de manière concise
        # (sans "4k, high quality" - Ideogram le fait automatiquement)
        style_keywords = {
            ImageStyle.CORPORATE_FLAT: "flat vector design, clean black outlines on all elements",
            ImageStyle.CORPORATE_3D: "3D rendered illustration, soft lighting, isometric view",
            ImageStyle.TECH_ISOMETRIC: "isometric illustration, technical diagram style, clean lines",
            ImageStyle.TECH_GRADIENT: "modern gradient background, abstract tech shapes",
            ImageStyle.MODERN_MINIMAL: "minimalist illustration, clean composition, negative space",
            ImageStyle.ABSTRACT_GEOMETRIC: "abstract geometric pattern, modern art style",
        }
        
        if style in style_keywords:
            prompt_parts.append(style_keywords[style])
        
        # Ajouter palette de couleurs si disponible dans le topic
        if topic and topic in TOPIC_TEMPLATES:
            color_palette = TOPIC_TEMPLATES[topic]["color_palette"]
            prompt_parts.append(f"{color_palette} colors")
        
        # Composition (concis)
        prompt_parts.append("layered composition, professional tech illustration")
        
        # Construire le prompt final (sans "4k, high quality, sharp details")
        final_prompt = ", ".join(prompt_parts)
        
        # Negative prompt (si demandé)
        negative_prompt = None
        if include_negative:
            negative_parts = [
                "text, words, letters, typography, watermark, signature",
                "blurry, low quality, pixelated, deformed, distorted",
            ]
            negative_prompt = ", ".join(negative_parts)
        
        return IdeogramPromptResult(
            prompt=final_prompt,
            negative_prompt=negative_prompt,
            style_type=ideogram_style,
            aspect_ratio=aspect_ratio,
        )
    
    def enhance_existing_prompt(
        self,
        basic_prompt: str,
        add_quality: bool = True,
        add_composition: bool = True,
        remove_text: bool = True,
    ) -> dict:
        """
        Améliore un prompt existant avec des modificateurs pro.
        
        Args:
            basic_prompt: Prompt de base
            add_quality: Ajouter termes de qualité
            add_composition: Ajouter directives de composition
            remove_text: Exclure le texte
            
        Returns:
            Prompt amélioré avec negative
        """
        enhanced = basic_prompt
        
        if add_composition:
            enhanced += ", centered balanced composition, clean layout, ample negative space"
        
        if add_quality:
            enhanced += ", professional quality, high detail, 4k, sharp focus"
        
        negative_parts = []
        
        if remove_text:
            negative_parts.append(
                "text, words, letters, numbers, typography, watermark, signature"
            )
        
        negative_parts.append(
            "blurry, low quality, distorted, deformed, amateur, "
            "cluttered, busy background, multiple focal points"
        )
        
        return {
            "prompt": enhanced,
            "negative_prompt": ", ".join(negative_parts),
            "guidance_scale": 7.5,
            "steps": 10,
        }


# === EXEMPLES D'UTILISATION ===
def demo_prompts():
    """Démontre les différents types de prompts."""
    
    builder = ImagePromptBuilderV2()
    
    print("=" * 60)
    print("EXEMPLE 1: Cybersécurité Cloud (comme ton image)")
    print("=" * 60)
    
    result = builder.build_cybersecurity_prompt(
        specific_topic="cloud security protection",
        style=ImageStyle.CORPORATE_FLAT,
    )
    
    print(f"\nPrompt:\n{result['prompt']}")
    print(f"\nNegative:\n{result['negative_prompt']}")
    print(f"\nParamètres: guidance={result['guidance_scale']}, steps={result['steps']}")
    
    print("\n" + "=" * 60)
    print("EXEMPLE 2: Infrastructure Cloud (style 3D)")
    print("=" * 60)
    
    result2 = builder.build_cloud_prompt(
        specific_topic="hybrid cloud architecture",
        style=ImageStyle.CORPORATE_3D,
    )
    
    print(f"\nPrompt:\n{result2['prompt']}")
    print(f"\nNegative:\n{result2['negative_prompt']}")
    
    print("\n" + "=" * 60)
    print("EXEMPLE 3: Article de blog")
    print("=" * 60)
    
    result3 = builder.build_article_illustration(
        article_title="Les tendances de la cybersécurité en 2025",
        keywords=["cybersécurité", "tendances", "protection", "cloud"],
        tone="professional",
        format_type="blog_header",
    )
    
    print(f"\nPrompt:\n{result3['prompt']}")
    print(f"\nTaille recommandée: {result3['recommended_size']}")


if __name__ == "__main__":
    demo_prompts()
