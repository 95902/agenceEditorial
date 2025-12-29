"""Pydantic schemas for draft article generation API."""

from typing import List, Optional

from pydantic import BaseModel, Field


class DraftRequest(BaseModel):
    """Request schema for draft generation."""

    topic_id: str = Field(..., description="Topic identifier (slug)", examples=["edge-cloud-hybride"])
    site_client: Optional[str] = Field(None, description="Client site identifier", examples=["innosys.fr"])


class ImageSuggestion(BaseModel):
    """Image suggestion for article."""

    description: str = Field(..., description="Image description", examples=["Schéma d'architecture edge computing vs cloud traditionnel"])
    type: str = Field(..., description="Image type", examples=["Infographie"])
    placement: str = Field(..., description="Placement suggestion", examples=["Après l'introduction"])


class DraftSuggestions(BaseModel):
    """Suggestions for improving the draft."""

    images: Optional[List[ImageSuggestion]] = Field(None, description="Image suggestions (optional)")
    seo: Optional[List[str]] = Field(None, description="SEO improvement suggestions (optional)", examples=[["Ajouter plus de mots-clés longue traîne"]])
    readability: Optional[List[str]] = Field(None, description="Readability improvement suggestions (optional)", examples=[["Simplifier certaines phrases techniques"]])


class DraftMetadata(BaseModel):
    """Draft metadata."""

    word_count: int = Field(..., description="Word count", examples=[547])
    reading_time: str = Field(..., description="Estimated reading time", examples=["8 min"])
    seo_score: Optional[int] = Field(None, description="SEO score (0-100)", examples=[87])
    readability_score: Optional[int] = Field(None, description="Readability score (0-100)", examples=[72])


class GeneratedImage(BaseModel):
    """Generated image metadata."""

    path: str = Field(..., description="Image file path", examples=["outputs/articles/images/ideogram_image_abc123.png"])
    prompt: Optional[str] = Field(None, description="Prompt used for generation")
    quality_score: Optional[float] = Field(None, description="Quality score (0-1)", examples=[0.85])
    generation_time_seconds: Optional[float] = Field(None, description="Generation time in seconds", examples=[12.5])


class DraftResponse(BaseModel):
    """Response schema for draft generation."""

    id: str = Field(..., description="Draft identifier", examples=["draft-edge-cloud-hybride"])
    topic_id: str = Field(..., description="Topic identifier", examples=["edge-cloud-hybride"])
    title: str = Field(..., description="Article title", examples=["L'avenir de l'edge computing dans le cloud hybride : Guide complet 2024"])
    subtitle: Optional[str] = Field(None, description="Article subtitle", examples=["Comment les architectures distribuées révolutionnent la performance"])
    content: str = Field(..., description="Article content in markdown", examples=["## Introduction\n\nL'edge computing représente..."])
    metadata: DraftMetadata = Field(..., description="Draft metadata")
    suggestions: Optional[DraftSuggestions] = Field(None, description="Improvement suggestions (optional)")
    generated_images: Optional[List[GeneratedImage]] = Field(None, description="Generated images (optional)")

