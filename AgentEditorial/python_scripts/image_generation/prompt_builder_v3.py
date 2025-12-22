"""Constructeur de prompts avancé pour génération d'images IT professionnelles."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import httpx
from loguru import logger


class VisualStyle(str, Enum):
    """Styles visuels disponibles."""
    PHOTOREALISTIC = "photorealistic"      # Photos réalistes, hardware réel
    FLAT_DESIGN = "flat_design"            # Illustrations vectorielles, icônes
    ISOMETRIC = "isometric"                # Vue isométrique 3D
    TECHNICAL_DIAGRAM = "technical_diagram" # Schémas techniques, architectures
    THREE_D_RENDER = "3d_render"           # Objets 3D stylisés, glossy
    ABSTRACT_GRADIENT = "abstract_gradient" # Formes abstraites, modernes


class ITDomain(str, Enum):
    """Domaines IT couverts."""
    CYBERSECURITY = "cybersecurity"
    CLOUD_INFRASTRUCTURE = "cloud_infrastructure"
    NETWORKING = "networking"
    DATA_CENTER = "data_center"
    DEVOPS = "devops"
    AI_ML = "ai_ml"
    DATA_ANALYTICS = "data_analytics"
    SOFTWARE_DEVELOPMENT = "software_development"
    IOT = "iot"
    BLOCKCHAIN = "blockchain"


class CameraAngle(str, Enum):
    """Angles de vue."""
    WIDE_ANGLE = "wide_angle"
    CLOSE_UP = "close_up"
    AERIAL = "aerial"
    EYE_LEVEL = "eye_level"
    LOW_ANGLE = "low_angle"
    ISOMETRIC_VIEW = "isometric_view"
    THREE_QUARTER = "three_quarter"


class Lighting(str, Enum):
    """Types d'éclairage."""
    STUDIO = "studio"
    NATURAL = "natural"
    DRAMATIC = "dramatic"
    LED_GLOW = "led_glow"
    SOFT_DIFFUSED = "soft_diffused"
    NEON = "neon"
    CINEMATIC = "cinematic"


class Ambiance(str, Enum):
    """Ambiances visuelles."""
    PROFESSIONAL = "professional"
    FUTURISTIC = "futuristic"
    MINIMAL = "minimal"
    CORPORATE = "corporate"
    TECH_STARTUP = "tech_startup"
    ENTERPRISE = "enterprise"
    INNOVATIVE = "innovative"


class ImageFormat(str, Enum):
    """Formats d'image."""
    BLOG_HEADER = "blog_header"       # 16:9, 1200x630
    SOCIAL_SQUARE = "social_square"   # 1:1, 1080x1080
    SOCIAL_STORY = "social_story"     # 9:16, 1080x1920
    THUMBNAIL = "thumbnail"           # 4:3, 400x300
    HERO_BANNER = "hero_banner"       # 21:9, 2560x1080
    LINKEDIN_POST = "linkedin_post"   # 1200x627


# === TEMPLATES DE DOMAINES IT ===

DOMAIN_TEMPLATES = {
    ITDomain.CYBERSECURITY: {
        "subjects": [
            "security operations center with multiple monitors",
            "digital shield protecting network infrastructure", 
            "firewall system blocking cyber threats",
            "encrypted data transmission visualization",
            "security analyst monitoring threat dashboard",
            "padlock integrated with circuit board",
            "biometric authentication system",
        ],
        "visual_elements": [
            "security monitors", "threat maps", "encryption symbols",
            "shield icons", "lock mechanisms", "firewall barriers",
            "binary code streams", "alert notifications",
        ],
        "color_schemes": {
            "default": "deep blue, electric blue, silver, dark grey",
            "alert": "red accents, dark background, warning orange",
            "secure": "green accents, blue tones, white highlights",
        },
        "atmosphere": "high-tech, secure, vigilant, protected",
    },
    
    ITDomain.DATA_CENTER: {
        "subjects": [
            "modern data center server room with network racks",
            "rows of server cabinets with LED indicators",
            "hot aisle containment system in data center",
            "structured cabling infrastructure",
            "cooling system in server facility",
            "network operations center",
        ],
        "visual_elements": [
            "server racks", "network cables", "LED status lights",
            "cooling vents", "raised floor tiles", "cable management",
            "UPS systems", "monitoring screens",
        ],
        "color_schemes": {
            "default": "cool blue, grey, silver, green LED accents",
            "warm": "amber indicators, warm grey, subtle orange",
        },
        "atmosphere": "organized, efficient, high-performance, reliable",
    },
    
    ITDomain.CLOUD_INFRASTRUCTURE: {
        "subjects": [
            "cloud architecture with connected services",
            "hybrid cloud infrastructure diagram",
            "serverless computing visualization",
            "multi-cloud deployment concept",
            "cloud migration process",
            "containerized application architecture",
        ],
        "visual_elements": [
            "cloud symbols", "connection lines", "data flow arrows",
            "container icons", "kubernetes pods", "API gateways",
            "load balancers", "database clusters",
        ],
        "color_schemes": {
            "default": "sky blue, white, light grey, subtle gradients",
            "enterprise": "navy blue, corporate grey, gold accents",
        },
        "atmosphere": "scalable, flexible, modern, interconnected",
    },
    
    ITDomain.NETWORKING: {
        "subjects": [
            "enterprise network topology",
            "fiber optic connections with data transmission",
            "network switch with active connections",
            "wireless network coverage visualization",
            "SD-WAN architecture diagram",
            "network security perimeter",
        ],
        "visual_elements": [
            "network nodes", "connection paths", "routers", "switches",
            "fiber cables", "wireless signals", "bandwidth indicators",
            "latency metrics",
        ],
        "color_schemes": {
            "default": "electric blue, cyan, dark background, white nodes",
            "corporate": "navy, grey, subtle blue accents",
        },
        "atmosphere": "connected, fast, reliable, seamless",
    },
    
    ITDomain.DEVOPS: {
        "subjects": [
            "CI/CD pipeline visualization",
            "DevOps infinity loop concept",
            "automated deployment workflow",
            "infrastructure as code representation",
            "monitoring and observability dashboard",
            "GitOps workflow diagram",
        ],
        "visual_elements": [
            "pipeline stages", "code repositories", "deployment arrows",
            "container orchestration", "monitoring graphs", "automation gears",
            "integration connectors", "testing checkmarks",
        ],
        "color_schemes": {
            "default": "purple, blue, orange accents, dark background",
            "modern": "gradient purple to blue, white icons",
        },
        "atmosphere": "automated, efficient, continuous, collaborative",
    },
    
    ITDomain.AI_ML: {
        "subjects": [
            "neural network architecture visualization",
            "machine learning model training process",
            "AI brain with data connections",
            "deep learning layers representation",
            "computer vision processing",
            "natural language processing concept",
        ],
        "visual_elements": [
            "neural nodes", "connection weights", "data layers",
            "processing units", "learning curves", "prediction outputs",
            "training datasets", "model parameters",
        ],
        "color_schemes": {
            "default": "purple, magenta, blue, glowing nodes",
            "technical": "blue, green, matrix-style data",
        },
        "atmosphere": "intelligent, advanced, learning, innovative",
    },
    
    ITDomain.DATA_ANALYTICS: {
        "subjects": [
            "business intelligence dashboard",
            "data visualization with charts and graphs",
            "real-time analytics processing",
            "big data pipeline architecture",
            "data warehouse concept",
            "ETL process visualization",
        ],
        "visual_elements": [
            "bar charts", "line graphs", "pie charts", "data tables",
            "KPI indicators", "trend lines", "heat maps", "scatter plots",
        ],
        "color_schemes": {
            "default": "blue, green, orange highlights, white background",
            "dark": "dark theme, neon data highlights, purple accents",
        },
        "atmosphere": "insightful, data-driven, clear, actionable",
    },
    
    ITDomain.SOFTWARE_DEVELOPMENT: {
        "subjects": [
            "code editor with syntax highlighting",
            "software architecture diagram",
            "agile development workflow",
            "API integration concept",
            "microservices architecture",
            "code review collaboration",
        ],
        "visual_elements": [
            "code snippets", "IDE interface", "git branches",
            "API endpoints", "function blocks", "class diagrams",
            "database schemas", "version control",
        ],
        "color_schemes": {
            "default": "dark editor theme, syntax colors, subtle blue",
            "light": "light IDE, colorful syntax, clean white",
        },
        "atmosphere": "creative, logical, structured, collaborative",
    },
    
    ITDomain.IOT: {
        "subjects": [
            "IoT ecosystem with connected devices",
            "smart home automation system",
            "industrial IoT sensors network",
            "edge computing architecture",
            "IoT data collection visualization",
            "connected vehicle technology",
        ],
        "visual_elements": [
            "sensors", "smart devices", "connectivity waves",
            "edge nodes", "data streams", "control panels",
            "automation triggers", "device icons",
        ],
        "color_schemes": {
            "default": "green, blue, white, tech silver",
            "industrial": "orange, grey, safety yellow accents",
        },
        "atmosphere": "connected, smart, automated, efficient",
    },
    
    ITDomain.BLOCKCHAIN: {
        "subjects": [
            "blockchain network with distributed nodes",
            "cryptocurrency transaction visualization",
            "smart contract execution flow",
            "decentralized ledger concept",
            "consensus mechanism diagram",
            "NFT marketplace interface",
        ],
        "visual_elements": [
            "chain links", "block structures", "hash symbols",
            "distributed nodes", "transaction arrows", "wallet icons",
            "mining rigs", "token symbols",
        ],
        "color_schemes": {
            "default": "gold, black, electric blue, purple",
            "crypto": "neon green, dark background, matrix style",
        },
        "atmosphere": "decentralized, secure, transparent, innovative",
    },
}


# === TEMPLATES DE STYLE ===

STYLE_TEMPLATES = {
    VisualStyle.PHOTOREALISTIC: {
        "prefix": "Photorealistic high-resolution image of",
        "quality_terms": [
            "ultra detailed", "realistic", "professional photography",
            "8k resolution", "sharp focus", "hyperrealistic",
            "photographic quality", "lifelike details",
        ],
        "composition_terms": [
            "depth of field", "natural perspective", "realistic proportions",
        ],
        "ideogram_style": "REALISTIC",
    },
    
    VisualStyle.FLAT_DESIGN: {
        "prefix": "Flat design illustration of",
        "quality_terms": [
            "vector art style", "clean geometric shapes", "solid colors",
            "minimal shadows", "crisp edges", "modern graphic design",
        ],
        "composition_terms": [
            "balanced composition", "negative space", "clean layout",
            "layered elements", "black outlines on elements",
        ],
        "ideogram_style": "DESIGN",
    },
    
    VisualStyle.ISOMETRIC: {
        "prefix": "Isometric illustration of",
        "quality_terms": [
            "isometric perspective", "3D vector style", "clean lines",
            "geometric precision", "technical illustration",
        ],
        "composition_terms": [
            "isometric grid", "consistent angle", "layered depth",
            "organized layout", "modular components",
        ],
        "ideogram_style": "DESIGN",
    },
    
    VisualStyle.TECHNICAL_DIAGRAM: {
        "prefix": "Technical diagram showing",
        "quality_terms": [
            "schematic style", "clean technical drawing", "precise lines",
            "professional diagram", "architectural precision",
        ],
        "composition_terms": [
            "logical flow", "clear connections", "labeled components",
            "organized structure", "systematic layout",
        ],
        "ideogram_style": "DESIGN",
    },
    
    VisualStyle.THREE_D_RENDER: {
        "prefix": "3D rendered illustration of",
        "quality_terms": [
            "3D render", "glossy materials", "soft shadows",
            "realistic lighting", "high quality 3D", "octane render style",
        ],
        "composition_terms": [
            "dynamic angle", "depth", "volumetric lighting",
            "ambient occlusion", "reflective surfaces",
        ],
        "ideogram_style": "ILLUSTRATION",
    },
    
    VisualStyle.ABSTRACT_GRADIENT: {
        "prefix": "Abstract visualization of",
        "quality_terms": [
            "smooth gradients", "flowing shapes", "modern abstract",
            "glassmorphism", "soft glow effects", "ethereal quality",
        ],
        "composition_terms": [
            "fluid composition", "overlapping forms", "depth layers",
            "subtle transparency", "harmonious flow",
        ],
        "ideogram_style": "ILLUSTRATION",
    },
}


# === TEMPLATES D'ANGLE DE VUE ===

ANGLE_TEMPLATES = {
    CameraAngle.WIDE_ANGLE: "wide angle view, expansive perspective, full scene visible",
    CameraAngle.CLOSE_UP: "close-up shot, detailed view, macro perspective",
    CameraAngle.AERIAL: "aerial view, bird's eye perspective, top-down angle",
    CameraAngle.EYE_LEVEL: "eye level perspective, natural viewing angle",
    CameraAngle.LOW_ANGLE: "low angle shot, looking upward, dramatic perspective",
    CameraAngle.ISOMETRIC_VIEW: "isometric view, 30-degree angle, technical perspective",
    CameraAngle.THREE_QUARTER: "three-quarter view, dynamic angle, dimensional perspective",
}


# === TEMPLATES D'ÉCLAIRAGE ===

LIGHTING_TEMPLATES = {
    Lighting.STUDIO: "professional studio lighting, controlled illumination, soft shadows",
    Lighting.NATURAL: "natural lighting, soft daylight, ambient illumination",
    Lighting.DRAMATIC: "dramatic lighting, high contrast, strong shadows, cinematic",
    Lighting.LED_GLOW: "LED accent lighting, tech glow, illuminated indicators, blue light accents",
    Lighting.SOFT_DIFFUSED: "soft diffused lighting, even illumination, no harsh shadows",
    Lighting.NEON: "neon lighting, vibrant glow, cyberpunk aesthetic",
    Lighting.CINEMATIC: "cinematic lighting, film quality, atmospheric, moody",
}


# === TEMPLATES D'AMBIANCE ===

AMBIANCE_TEMPLATES = {
    Ambiance.PROFESSIONAL: "professional atmosphere, corporate quality, business appropriate",
    Ambiance.FUTURISTIC: "futuristic aesthetic, advanced technology, sci-fi inspired",
    Ambiance.MINIMAL: "minimal aesthetic, clean and simple, uncluttered",
    Ambiance.CORPORATE: "corporate style, enterprise quality, formal presentation",
    Ambiance.TECH_STARTUP: "modern tech startup vibe, innovative, fresh",
    Ambiance.ENTERPRISE: "enterprise grade, robust, reliable, established",
    Ambiance.INNOVATIVE: "innovative feel, cutting-edge, forward-thinking",
}


# === FORMATS ET RATIOS ===

FORMAT_SPECS = {
    ImageFormat.BLOG_HEADER: {"ratio": "16:9", "ideogram_ratio": "16x9", "size": (1200, 630)},
    ImageFormat.SOCIAL_SQUARE: {"ratio": "1:1", "ideogram_ratio": "1x1", "size": (1080, 1080)},
    ImageFormat.SOCIAL_STORY: {"ratio": "9:16", "ideogram_ratio": "9x16", "size": (1080, 1920)},
    ImageFormat.THUMBNAIL: {"ratio": "4:3", "ideogram_ratio": "4x3", "size": (400, 300)},
    ImageFormat.HERO_BANNER: {"ratio": "21:9", "ideogram_ratio": "16x9", "size": (2560, 1080)},
    ImageFormat.LINKEDIN_POST: {"ratio": "1.91:1", "ideogram_ratio": "16x9", "size": (1200, 627)},
}


# === DATACLASS RÉSULTAT ===

@dataclass
class AdvancedPromptResult:
    """Résultat d'un prompt généré."""
    prompt: str
    negative_prompt: str
    style_type: str  # Pour Ideogram
    aspect_ratio: str  # Pour Ideogram
    recommended_size: tuple[int, int]
    metadata: dict  # Infos sur les choix faits


# === CLASSE PRINCIPALE ===

class AdvancedPromptBuilder:
    """
    Générateur de prompts avancé pour images IT professionnelles.
    """
    
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        """
        Initialise le builder.
        
        Args:
            ollama_url: URL de l'instance Ollama pour enrichissement optionnel
        """
        self.ollama_url = ollama_url
    
    def build(
        self,
        # Contenu
        subject: Optional[str] = None,
        domain: ITDomain = ITDomain.CYBERSECURITY,
        keywords: Optional[list[str]] = None,
        
        # Style
        style: VisualStyle = VisualStyle.PHOTOREALISTIC,
        
        # Personnalisation
        color_scheme: Optional[str] = None,  # "default", "alert", custom string
        angle: CameraAngle = CameraAngle.WIDE_ANGLE,
        lighting: Lighting = Lighting.STUDIO,
        ambiance: Ambiance = Ambiance.PROFESSIONAL,
        
        # Format
        format: ImageFormat = ImageFormat.BLOG_HEADER,
        
        # Options
        use_magic_prompt: bool = False,  # Enrichir via Ollama
    ) -> AdvancedPromptResult:
        """
        Construit un prompt professionnel complet.
        
        Args:
            subject: Sujet spécifique (optionnel, sinon choisi selon domain)
            domain: Domaine IT
            keywords: Mots-clés additionnels
            style: Style visuel
            color_scheme: Palette de couleurs
            angle: Angle de vue
            lighting: Type d'éclairage
            ambiance: Ambiance générale
            format: Format d'image
            use_magic_prompt: Utiliser Ollama pour enrichir
            
        Returns:
            AdvancedPromptResult avec prompt complet
        """
        
        # 1. Récupérer les templates
        domain_template = DOMAIN_TEMPLATES[domain]
        style_template = STYLE_TEMPLATES[style]
        format_spec = FORMAT_SPECS[format]
        
        # 2. Déterminer le sujet
        if not subject:
            # Choisir un sujet par défaut du domaine
            subject = domain_template["subjects"][0]
        
        # 3. Construire le prompt
        prompt_parts = []
        
        # Prefix du style
        prompt_parts.append(style_template["prefix"])
        
        # Sujet principal
        prompt_parts.append(subject)
        
        # Éléments visuels du domaine (2-3)
        visual_elements = domain_template["visual_elements"][:3]
        prompt_parts.append(f"with {', '.join(visual_elements)}")
        
        # Éclairage
        prompt_parts.append(LIGHTING_TEMPLATES[lighting])
        
        # Couleurs
        if color_scheme and color_scheme in domain_template.get("color_schemes", {}):
            colors = domain_template["color_schemes"][color_scheme]
        elif color_scheme:
            colors = color_scheme  # Custom string
        else:
            colors = domain_template["color_schemes"].get("default", "blue, grey, white")
        prompt_parts.append(f"{colors} tones")
        
        # Angle de vue
        prompt_parts.append(ANGLE_TEMPLATES[angle])
        
        # Qualité du style
        quality_terms = style_template["quality_terms"][:4]
        prompt_parts.append(", ".join(quality_terms))
        
        # Composition du style
        composition_terms = style_template["composition_terms"][:2]
        prompt_parts.append(", ".join(composition_terms))
        
        # Ambiance
        prompt_parts.append(AMBIANCE_TEMPLATES[ambiance])
        
        # Atmosphère du domaine
        prompt_parts.append(domain_template["atmosphere"])
        
        # Keywords additionnels
        if keywords:
            prompt_parts.append(", ".join(keywords[:3]))
        
        # Assembler le prompt
        final_prompt = ", ".join(prompt_parts)
        
        # 4. Negative prompt
        negative_parts = [
            "text, words, letters, typography, watermark, signature, labels",
            "blurry, low quality, pixelated, distorted, deformed",
            "amateur, poorly composed, cluttered, messy",
        ]
        
        # Ajouter des négatifs spécifiques au style
        if style == VisualStyle.PHOTOREALISTIC:
            negative_parts.append("cartoon, illustration, anime, drawing")
        elif style in [VisualStyle.FLAT_DESIGN, VisualStyle.ISOMETRIC]:
            negative_parts.append("photorealistic, 3d render, shadows, gradients")
        
        negative_prompt = ", ".join(negative_parts)
        
        # 5. Enrichissement via Ollama (optionnel)
        if use_magic_prompt:
            # Note: Cette méthode est async, mais build() est sync
            # On ne peut pas l'appeler directement ici
            # L'utilisateur devra utiliser build_from_article() ou appeler _enrich_with_ollama() séparément
            logger.warning(
                "use_magic_prompt=True requires async context. "
                "Use build_from_article() or call _enrich_with_ollama() separately."
            )
        
        return AdvancedPromptResult(
            prompt=final_prompt,
            negative_prompt=negative_prompt,
            style_type=style_template["ideogram_style"],
            aspect_ratio=format_spec["ideogram_ratio"],
            recommended_size=format_spec["size"],
            metadata={
                "domain": domain.value,
                "style": style.value,
                "angle": angle.value,
                "lighting": lighting.value,
                "ambiance": ambiance.value,
                "format": format.value,
            }
        )
    
    async def build_async(
        self,
        # Contenu
        subject: Optional[str] = None,
        domain: ITDomain = ITDomain.CYBERSECURITY,
        keywords: Optional[list[str]] = None,
        
        # Style
        style: VisualStyle = VisualStyle.PHOTOREALISTIC,
        
        # Personnalisation
        color_scheme: Optional[str] = None,
        angle: CameraAngle = CameraAngle.WIDE_ANGLE,
        lighting: Lighting = Lighting.STUDIO,
        ambiance: Ambiance = Ambiance.PROFESSIONAL,
        
        # Format
        format: ImageFormat = ImageFormat.BLOG_HEADER,
        
        # Options
        use_magic_prompt: bool = False,
    ) -> AdvancedPromptResult:
        """
        Version async de build() qui supporte l'enrichissement Ollama.
        
        Mêmes paramètres que build() mais peut utiliser use_magic_prompt=True.
        """
        # Construire le prompt de base
        result = self.build(
            subject=subject,
            domain=domain,
            keywords=keywords,
            style=style,
            color_scheme=color_scheme,
            angle=angle,
            lighting=lighting,
            ambiance=ambiance,
            format=format,
            use_magic_prompt=False,  # On gère ça après
        )
        
        # Enrichir si demandé
        if use_magic_prompt:
            enriched_prompt = await self._enrich_with_ollama(
                result.prompt, domain, style
            )
            result.prompt = enriched_prompt
        
        return result
    
    async def build_from_article(
        self,
        title: str,
        content_summary: str,
        keywords: list[str],
        site_profile: Optional[dict] = None,
        style: Optional[VisualStyle] = None,
        format: ImageFormat = ImageFormat.BLOG_HEADER,
    ) -> AdvancedPromptResult:
        """
        Construit un prompt à partir d'un article.
        
        Analyse le titre, résumé et mots-clés pour déterminer:
        - Le domaine IT approprié
        - Le style si non spécifié
        - Les éléments visuels pertinents
        
        Args:
            title: Titre de l'article
            content_summary: Résumé du contenu
            keywords: Mots-clés de l'article
            site_profile: Profil éditorial du site (optionnel)
            style: Style visuel (détecté automatiquement si None)
            format: Format d'image
            
        Returns:
            AdvancedPromptResult avec prompt complet
        """
        
        # 1. Détecter le domaine IT
        domain = self._detect_domain(title, content_summary, keywords)
        
        # 2. Détecter le style si non fourni
        if not style:
            style = self._detect_style(site_profile)
        
        # 3. Construire un sujet basé sur le titre/résumé
        subject = self._create_subject_from_content(title, content_summary, domain)
        
        # 4. Générer le prompt avec enrichissement Ollama
        return await self.build_async(
            subject=subject,
            domain=domain,
            keywords=keywords,
            style=style,
            format=format,
            use_magic_prompt=True,  # Enrichir pour les articles
        )
    
    def _detect_domain(self, title: str, summary: str, keywords: list[str]) -> ITDomain:
        """Détecte le domaine IT basé sur le contenu."""
        text = f"{title} {summary} {' '.join(keywords)}".lower()
        
        # Mapping mots-clés -> domaine
        domain_keywords = {
            ITDomain.CYBERSECURITY: ["security", "sécurité", "cyber", "firewall", "encryption", "threat", "protection"],
            ITDomain.CLOUD_INFRASTRUCTURE: ["cloud", "aws", "azure", "gcp", "kubernetes", "docker", "container"],
            ITDomain.DATA_CENTER: ["data center", "datacenter", "server room", "rack", "hosting"],
            ITDomain.NETWORKING: ["network", "réseau", "routing", "switch", "firewall", "vpn", "sd-wan"],
            ITDomain.DEVOPS: ["devops", "ci/cd", "pipeline", "deployment", "automation", "jenkins", "gitlab"],
            ITDomain.AI_ML: ["ai", "machine learning", "deep learning", "neural", "nlp", "ia", "intelligence artificielle"],
            ITDomain.DATA_ANALYTICS: ["analytics", "data", "dashboard", "bi", "visualization", "reporting"],
            ITDomain.SOFTWARE_DEVELOPMENT: ["development", "code", "programming", "api", "software", "application"],
            ITDomain.IOT: ["iot", "sensor", "connected", "smart", "edge"],
            ITDomain.BLOCKCHAIN: ["blockchain", "crypto", "nft", "smart contract", "decentralized"],
        }
        
        for domain, kws in domain_keywords.items():
            if any(kw in text for kw in kws):
                return domain
        
        return ITDomain.CLOUD_INFRASTRUCTURE  # Défaut
    
    def _detect_style(self, site_profile: Optional[dict]) -> VisualStyle:
        """Détecte le style approprié basé sur le profil éditorial."""
        if not site_profile:
            return VisualStyle.PHOTOREALISTIC
        
        tone = site_profile.get("editorial_tone", "").lower()
        
        if tone in ["technical", "technique"]:
            return VisualStyle.TECHNICAL_DIAGRAM
        elif tone in ["modern", "innovative", "innovant"]:
            return VisualStyle.ABSTRACT_GRADIENT
        elif tone in ["minimal", "minimaliste"]:
            return VisualStyle.FLAT_DESIGN
        elif tone in ["corporate", "enterprise"]:
            return VisualStyle.THREE_D_RENDER
        else:
            return VisualStyle.PHOTOREALISTIC
    
    def _create_subject_from_content(self, title: str, summary: str, domain: ITDomain) -> str:
        """Crée un sujet visuel basé sur le contenu de l'article."""
        # Récupérer des sujets par défaut du domaine
        default_subjects = DOMAIN_TEMPLATES[domain]["subjects"]
        
        # Pour l'instant, utiliser le premier sujet du domaine
        # TODO: Utiliser Ollama pour créer un sujet personnalisé
        return default_subjects[0]
    
    async def _enrich_with_ollama(self, prompt: str, domain: ITDomain, style: VisualStyle) -> str:
        """Enrichit le prompt via Ollama."""
        enrichment_prompt = f"""
Tu es un expert en prompt engineering pour la génération d'images.
Améliore ce prompt pour le rendre plus détaillé et professionnel.

Prompt actuel: {prompt}

Domaine: {domain.value}
Style: {style.value}

Règles:
- Ajoute des détails visuels spécifiques
- Garde un style {style.value}
- Maximum 150 mots
- NE JAMAIS mentionner de texte ou mots dans l'image
- Retourne UNIQUEMENT le prompt amélioré

Prompt amélioré:"""
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": "mistral:7b",
                        "prompt": enrichment_prompt,
                        "stream": False,
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                enriched = result.get("response", prompt).strip()
                
                # Nettoyer la réponse (enlever les guillemets si présents)
                if enriched.startswith('"') and enriched.endswith('"'):
                    enriched = enriched[1:-1]
                
                logger.info("Prompt enrichi via Ollama", original_length=len(prompt), enriched_length=len(enriched))
                return enriched
        except Exception as e:
            logger.warning("Échec enrichissement Ollama, utilisation du prompt original", error=str(e))
            return prompt  # Fallback au prompt original


# === EXEMPLES D'UTILISATION ===

async def demo_prompts():
    """Démontre les différents types de prompts."""
    
    builder = AdvancedPromptBuilder()
    
    print("=" * 60)
    print("EXEMPLE 1: Data Center Photorealistic")
    print("=" * 60)
    
    result = builder.build(
        domain=ITDomain.DATA_CENTER,
        style=VisualStyle.PHOTOREALISTIC,
        lighting=Lighting.LED_GLOW,
        angle=CameraAngle.WIDE_ANGLE,
        ambiance=Ambiance.PROFESSIONAL,
        format=ImageFormat.BLOG_HEADER,
    )
    
    print(f"\nPrompt:\n{result.prompt}")
    print(f"\nNegative:\n{result.negative_prompt}")
    print(f"\nStyle Type: {result.style_type}")
    print(f"\nAspect Ratio: {result.aspect_ratio}")
    print(f"\nTaille recommandée: {result.recommended_size}")
    
    print("\n" + "=" * 60)
    print("EXEMPLE 2: Cybersecurity Flat Design")
    print("=" * 60)
    
    result2 = builder.build(
        domain=ITDomain.CYBERSECURITY,
        style=VisualStyle.FLAT_DESIGN,
        color_scheme="alert",
        angle=CameraAngle.EYE_LEVEL,
        format=ImageFormat.SOCIAL_SQUARE,
    )
    
    print(f"\nPrompt:\n{result2.prompt}")
    print(f"\nNegative:\n{result2.negative_prompt}")
    
    print("\n" + "=" * 60)
    print("EXEMPLE 3: Depuis un article")
    print("=" * 60)
    
    result3 = await builder.build_from_article(
        title="Comment sécuriser votre infrastructure cloud en 2025",
        content_summary="Guide complet sur les meilleures pratiques de sécurité cloud",
        keywords=["cloud", "sécurité", "infrastructure", "aws"],
        format=ImageFormat.BLOG_HEADER,
    )
    
    print(f"\nPrompt:\n{result3.prompt}")
    print(f"\nDomain détecté: {result3.metadata['domain']}")
    print(f"\nStyle détecté: {result3.metadata['style']}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo_prompts())



