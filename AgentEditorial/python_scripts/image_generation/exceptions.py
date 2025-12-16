"""Exceptions personnalisées pour la génération d'images."""


class ImageGenerationError(Exception):
    """Erreur générale de génération d'image."""

    pass


class VRAMError(ImageGenerationError):
    """Erreur de mémoire GPU insuffisante."""

    pass


class ModelLoadError(ImageGenerationError):
    """Erreur de chargement du modèle."""

    pass


class PromptError(ImageGenerationError):
    """Erreur liée au prompt."""

    pass


class CacheError(ImageGenerationError):
    """Erreur de cache."""

    pass


class IdeogramAPIError(ImageGenerationError):
    """Erreur lors de l'appel à l'API Ideogram."""

    pass



