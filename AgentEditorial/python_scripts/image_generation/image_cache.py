"""Système de cache pour éviter de régénérer des images identiques."""

from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from loguru import logger

from python_scripts.config.image_config import IMAGE_CONFIG
from python_scripts.image_generation.exceptions import CacheError


class ImageCache:
    """
    Système de cache pour éviter de régénérer des images identiques.
    Basé sur le hash MD5 du prompt + paramètres.
    """

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        max_size_gb: float = 5.0,
        enabled: bool = True,
    ) -> None:
        """
        Initialise le cache.

        Args:
            cache_dir: Répertoire de cache (défaut: IMAGE_CONFIG.cache_dir)
            max_size_gb: Taille maximale du cache en GB
            enabled: Activer/désactiver le cache
        """
        self.enabled = enabled
        self.max_size_gb = max_size_gb
        self.cache_dir = Path(cache_dir or IMAGE_CONFIG.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        if self.enabled:
            logger.info(
                "Image cache initialized",
                cache_dir=str(self.cache_dir),
                max_size_gb=max_size_gb,
            )

    def get_cache_key(
        self,
        prompt: str,
        width: int,
        height: int,
        model: str,
        steps: Optional[int] = None,
        guidance_scale: Optional[float] = None,
        seed: Optional[int] = None,
    ) -> str:
        """
        Génère une clé de cache unique.

        Args:
            prompt: Prompt de l'image
            width: Largeur
            height: Hauteur
            model: Modèle utilisé
            steps: Nombre d'étapes
            guidance_scale: Échelle de guidage
            seed: Graine

        Returns:
            Clé de cache (hash MD5)
        """
        cache_string = f"{prompt}_{width}_{height}_{model}_{steps}_{guidance_scale}_{seed}"
        return hashlib.md5(cache_string.encode()).hexdigest()

    def get_cached(self, cache_key: str) -> Optional[Path]:
        """
        Récupère une image depuis le cache.

        Args:
            cache_key: Clé de cache

        Returns:
            Path si trouvé, None sinon
        """
        if not self.enabled:
            return None

        cached_file = self.cache_dir / f"{cache_key}.png"
        if cached_file.exists():
            logger.debug("Cache hit", cache_key=cache_key)
            return cached_file

        return None

    def cache_image(
        self,
        cache_key: str,
        image_path: Path,
        metadata: Optional[dict] = None,
    ) -> Path:
        """
        Ajoute une image au cache.

        Args:
            cache_key: Clé de cache
            image_path: Path de l'image source
            metadata: Métadonnées optionnelles

        Returns:
            Path vers l'image cachée
        """
        if not self.enabled:
            return image_path

        cached_file = self.cache_dir / f"{cache_key}.png"

        try:
            # Copier l'image dans le cache
            shutil.copy2(image_path, cached_file)

            # Sauvegarder les métadonnées si fournies
            if metadata:
                metadata_file = self.cache_dir / f"{cache_key}.json"
                import json

                metadata_file.write_text(json.dumps(metadata, indent=2))

            logger.debug("Image cached", cache_key=cache_key, path=str(cached_file))
            return cached_file

        except Exception as e:
            logger.error("Failed to cache image", error=str(e), cache_key=cache_key)
            raise CacheError(f"Failed to cache image: {e}") from e

    def clear_cache(self, older_than_days: Optional[int] = None) -> int:
        """
        Vide le cache.

        Args:
            older_than_days: Si spécifié, supprime uniquement les fichiers
                           plus vieux que N jours

        Returns:
            Nombre de fichiers supprimés
        """
        deleted_count = 0
        cutoff_date = None

        if older_than_days:
            cutoff_date = datetime.now() - timedelta(days=older_than_days)

        for file_path in self.cache_dir.glob("*.png"):
            if cutoff_date:
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_mtime > cutoff_date:
                    continue

            try:
                file_path.unlink()
                deleted_count += 1

                # Supprimer aussi le fichier de métadonnées si existe
                metadata_file = file_path.with_suffix(".json")
                if metadata_file.exists():
                    metadata_file.unlink()

            except Exception as e:
                logger.warning("Failed to delete cached file", path=str(file_path), error=str(e))

        logger.info("Cache cleared", deleted_count=deleted_count)
        return deleted_count

    def get_cache_stats(self) -> dict:
        """
        Retourne les statistiques du cache.

        Returns:
            {
                "total_files": int,
                "total_size_mb": float,
                "oldest_file": datetime,
                "newest_file": datetime
            }
        """
        files = list(self.cache_dir.glob("*.png"))
        total_size = sum(f.stat().st_size for f in files)

        if not files:
            return {
                "total_files": 0,
                "total_size_mb": 0.0,
                "oldest_file": None,
                "newest_file": None,
            }

        mtimes = [datetime.fromtimestamp(f.stat().st_mtime) for f in files]

        return {
            "total_files": len(files),
            "total_size_mb": total_size / (1024 * 1024),
            "oldest_file": min(mtimes),
            "newest_file": max(mtimes),
        }

    def enforce_size_limit(self) -> int:
        """
        Applique la limite de taille en supprimant les plus anciens fichiers.

        Returns:
            Nombre de fichiers supprimés
        """
        stats = self.get_cache_stats()
        max_size_bytes = self.max_size_gb * 1024 * 1024 * 1024

        if stats["total_size_mb"] * 1024 * 1024 <= max_size_bytes:
            return 0

        # Trier les fichiers par date (plus anciens en premier)
        files = [
            (f, datetime.fromtimestamp(f.stat().st_mtime))
            for f in self.cache_dir.glob("*.png")
        ]
        files.sort(key=lambda x: x[1])

        deleted_count = 0
        current_size = stats["total_size_mb"] * 1024 * 1024

        for file_path, _ in files:
            if current_size <= max_size_bytes:
                break

            try:
                file_size = file_path.stat().st_size
                file_path.unlink()
                current_size -= file_size
                deleted_count += 1

                # Supprimer aussi les métadonnées
                metadata_file = file_path.with_suffix(".json")
                if metadata_file.exists():
                    metadata_file.unlink()

            except Exception as e:
                logger.warning("Failed to delete file during size limit enforcement", path=str(file_path), error=str(e))

        logger.info(
            "Cache size limit enforced",
            deleted_count=deleted_count,
            remaining_size_mb=current_size / (1024 * 1024),
        )
        return deleted_count



