"""Agent de création de contenu avec génération d'images."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

from loguru import logger

from python_scripts.agents.utils.llm_factory import create_llm
from python_scripts.config.settings import settings
from python_scripts.database.crud_images import save_generated_image
from python_scripts.database.crud_profiles import get_site_profile
from python_scripts.database.db_session import get_db
from python_scripts.image_generation import (
    ImagePromptBuilder,
    ZImageGenerator,
    ImageModel,
)


class ContentCreatorAgent:
    """
    Agent intelligent pour créer du contenu avec images.
    Utilise Ollama pour le texte et Z-Image pour les visuels.
    """

    def __init__(
        self,
        llm_model: str = "llama3:8b",
        image_model: ImageModel = ImageModel.Z_IMAGE_TURBO,
    ) -> None:
        """
        Initialise l'agent.

        Args:
            llm_model: Modèle LLM à utiliser (Ollama)
            image_model: Modèle d'image à utiliser (Z-Image)
        """
        self.llm_model = llm_model
        self.image_generator = ZImageGenerator.get_instance(image_model)
        self.prompt_builder = ImagePromptBuilder()

    async def create_article_with_image(
        self,
        domain: str,
        topic: str,
        image_type: str = "article",
    ) -> dict:
        """
        Crée un article complet avec image illustrative.

        Args:
            domain: Domaine du site cible
            topic: Sujet de l'article
            image_type: Type d'image à générer

        Returns:
            {
                "title": str,
                "content": str,
                "image_path": str,
                "image_prompt": str,
                "metadata": dict
            }
        """
        # Récupérer le profil éditorial
        async for db in get_db():
            site_profile = await get_site_profile(db, domain=domain)
            break

        if not site_profile:
            logger.warning("Site profile not found", domain=domain)
            site_profile_dict = {}
        else:
            site_profile_dict = {
                "editorial_tone": site_profile.editorial_tone,
                "activity_domains": site_profile.activity_domains,
                "target_audience": site_profile.target_audience,
            }

        # Générer le prompt d'image avec LLM
        image_prompt = await self._generate_image_prompt_from_llm(
            context={"topic": topic, "site_profile": site_profile_dict},
            image_type=image_type,
        )

        # Générer l'image
        try:
            image_path = self.image_generator.generate(
                prompt=image_prompt,
                width=1024,
                height=1024,
            )
        except Exception as e:
            logger.error("Image generation failed", error=str(e), topic=topic)
            image_path = None

        # Générer le contenu de l'article avec LLM
        llm = create_llm(self.llm_model)
        article_prompt = (
            f"Rédige un article de blog en français sur le sujet: {topic}\n"
            f"Ton éditorial: {site_profile_dict.get('editorial_tone', 'professional')}\n"
            f"Longueur: environ 1500 mots\n"
            f"Structure: Introduction, 3-4 sections principales, Conclusion"
        )

        content = await llm.ainvoke(article_prompt)
        content_str = str(content)

        # Extraire le titre (première ligne ou généré séparément)
        title_prompt = f"Génère un titre accrocheur pour un article sur: {topic}"
        title_response = await llm.ainvoke(title_prompt)
        title = str(title_response).strip().replace('"', "").replace("'", "")

        # Sauvegarder l'image en BDD si générée
        image_id = None
        if image_path:
            prompt_hash = hashlib.md5(
                f"{image_prompt}_1024_1024_8_4.5".encode()
            ).hexdigest()[:32]

            async for db in get_db():
                image_record = await save_generated_image(
                    db=db,
                    prompt=image_prompt,
                    prompt_hash=prompt_hash,
                    file_path=str(image_path),
                    file_name=image_path.name,
                    width=1024,
                    height=1024,
                    steps=8,
                    model_used="z-image-turbo",
                    domain=domain,
                    image_type=image_type,
                    site_profile_id=site_profile.id if site_profile else None,
                )
                image_id = image_record.id
                break

        return {
            "title": title,
            "content": content_str,
            "image_path": str(image_path) if image_path else None,
            "image_prompt": image_prompt,
            "image_id": image_id,
            "metadata": {
                "domain": domain,
                "topic": topic,
                "image_type": image_type,
            },
        }

    async def generate_social_media_pack(
        self,
        domain: str,
        content: str,
        platforms: list[str] = ["instagram", "linkedin", "twitter"],
    ) -> dict:
        """
        Génère un pack de visuels pour réseaux sociaux.

        Args:
            domain: Domaine du site
            content: Résumé du contenu
            platforms: Plateformes cibles

        Returns:
            {
                "instagram": {"image_path": str, "caption": str},
                "linkedin": {"image_path": str, "caption": str},
                ...
            }
        """
        async for db in get_db():
            site_profile = await get_site_profile(db, domain=domain)
            break

        brand_colors = None
        if site_profile and site_profile.style_features:
            brand_colors = site_profile.style_features.get("colors")

        results = {}

        for platform in platforms:
            # Générer le prompt pour cette plateforme
            prompt = self.prompt_builder.build_social_media_prompt(
                platform=platform,
                content_summary=content,
                brand_colors=brand_colors,
            )

            # Générer l'image
            try:
                image_path = self.image_generator.generate(
                    prompt=prompt,
                    width=1200 if platform != "instagram" else 1080,
                    height=675 if platform != "instagram" else 1080,
                )
            except Exception as e:
                logger.error(
                    "Social media image generation failed",
                    platform=platform,
                    error=str(e),
                )
                image_path = None

            # Générer la légende avec LLM
            llm = create_llm(self.llm_model)
            caption_prompt = (
                f"Génère une légende courte et engageante pour {platform} "
                f"sur le sujet: {content}\n"
                f"Longueur: 1-2 phrases maximum"
            )
            caption_response = await llm.ainvoke(caption_prompt)
            caption = str(caption_response).strip()

            results[platform] = {
                "image_path": str(image_path) if image_path else None,
                "caption": caption,
                "prompt": prompt,
            }

        return results

    async def create_hero_image(
        self,
        domain: str,
        page_context: Optional[str] = None,
    ) -> dict:
        """
        Génère une image hero pour landing page.

        Args:
            domain: Domaine du site
            page_context: Contexte de la page (optionnel)

        Returns:
            {
                "image_path": str,
                "prompt": str,
                "metadata": dict
            }
        """
        async for db in get_db():
            site_profile = await get_site_profile(db, domain=domain)
            break

        if not site_profile:
            raise ValueError(f"Site profile not found for domain: {domain}")

        site_profile_dict = {
            "editorial_tone": site_profile.editorial_tone,
            "activity_domains": site_profile.activity_domains,
            "target_audience": site_profile.target_audience,
        }

        # Construire le prompt hero
        prompt = self.prompt_builder.build_hero_image_prompt(
            site_profile=site_profile_dict, style="corporate"
        )

        if page_context:
            prompt += f", context: {page_context}"

        # Générer l'image
        image_path = self.image_generator.generate(
            prompt=prompt,
            width=1920,
            height=1080,
        )

        return {
            "image_path": str(image_path),
            "prompt": prompt,
            "metadata": {
                "domain": domain,
                "image_type": "hero",
            },
        }

    async def create_infographic(
        self,
        data: dict,
        title: str,
        style: str = "modern",
    ) -> dict:
        """
        Génère une infographie basée sur des données.

        Args:
            data: Données à visualiser
            data_description: Description textuelle des données
            title: Titre de l'infographie
            style: Style visuel

        Returns:
            {
                "image_path": str,
                "prompt": str,
                "metadata": dict
            }
        """
        # Convertir les données en description textuelle
        data_description = f"Data visualization: {title}. "
        if isinstance(data, dict):
            data_description += ", ".join(
                [f"{k}: {v}" for k, v in list(data.items())[:5]]
            )

        # Construire le prompt
        prompt = self.prompt_builder.build_infographic_prompt(
            data_description=data_description,
            chart_type=None,
        )

        # Générer l'image
        image_path = self.image_generator.generate(
            prompt=prompt,
            width=1200,
            height=1600,  # Format vertical pour infographie
        )

        return {
            "image_path": str(image_path),
            "prompt": prompt,
            "metadata": {
                "title": title,
                "style": style,
                "image_type": "infographic",
            },
        }

    async def _generate_image_prompt_from_llm(
        self,
        context: dict,
        image_type: str,
    ) -> str:
        """
        Utilise le LLM pour générer un prompt d'image optimisé.

        Le LLM analyse le contexte éditorial et produit un prompt
        adapté au style et au ton du site.

        Args:
            context: Contexte éditorial (topic, site_profile, etc.)
            image_type: Type d'image souhaité

        Returns:
            Prompt optimisé pour Z-Image
        """
        llm = create_llm(self.llm_model)

        prompt_template = (
            f"Tu es un expert en génération d'images avec IA.\n"
            f"Génère un prompt détaillé et optimisé pour créer une image de type '{image_type}'.\n"
            f"Contexte:\n"
            f"- Sujet: {context.get('topic', 'N/A')}\n"
        )

        site_profile = context.get("site_profile", {})
        if site_profile:
            prompt_template += (
                f"- Ton éditorial: {site_profile.get('editorial_tone', 'professional')}\n"
                f"- Domaines: {site_profile.get('activity_domains', [])}\n"
            )

        prompt_template += (
            f"\nLe prompt doit être en anglais, détaillé, et inclure:\n"
            f"- Description visuelle précise\n"
            f"- Style et ambiance\n"
            f"- Qualité et détails\n"
            f"\nRéponds uniquement avec le prompt, sans explication."
        )

        response = await llm.ainvoke(prompt_template)
        prompt = str(response).strip()

        # Nettoyer le prompt (enlever guillemets, etc.)
        prompt = prompt.replace('"', "").replace("'", "").strip()

        return prompt

    async def _analyze_editorial_context(self, domain: str) -> dict:
        """
        Récupère et analyse le contexte éditorial du domaine.

        Args:
            domain: Domaine à analyser

        Returns:
            Dictionnaire avec contexte éditorial
        """
        async for db in get_db():
            site_profile = await get_site_profile(db, domain=domain)
            break

        if not site_profile:
            return {}

        return {
            "editorial_tone": site_profile.editorial_tone,
            "activity_domains": site_profile.activity_domains,
            "target_audience": site_profile.target_audience,
            "style_features": site_profile.style_features,
        }
















