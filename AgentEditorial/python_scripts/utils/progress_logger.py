"""Enhanced progress logging with visual progress bars and emojis."""

import sys
import time
from contextlib import contextmanager
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

try:
    from python_scripts.utils.logging import get_logger
except ImportError:
    # Fallback for testing without dependencies
    import logging
    get_logger = logging.getLogger


@dataclass
class PhaseConfig:
    """Configuration for a workflow phase."""
    name: str
    emoji: str
    steps: List[str]
    start_progress: int
    end_progress: int


@dataclass
class WorkflowPhases:
    """Predefined workflow phases with emojis and progress ranges."""

    EDITORIAL_ANALYSIS = [
        PhaseConfig(
            name="🔍 Découverte",
            emoji="🔍",
            steps=["Recherche des URLs via sitemap", "Validation du domaine"],
            start_progress=0,
            end_progress=15,
        ),
        PhaseConfig(
            name="📥 Extraction",
            emoji="📥",
            steps=["Crawling des pages", "Extraction du contenu"],
            start_progress=15,
            end_progress=50,
        ),
        PhaseConfig(
            name="🤖 Analyse IA",
            emoji="🤖",
            steps=["Analyse du style éditorial", "Génération du profil"],
            start_progress=50,
            end_progress=85,
        ),
        PhaseConfig(
            name="💾 Sauvegarde",
            emoji="💾",
            steps=["Enregistrement du profil", "Mise à jour de la base"],
            start_progress=85,
            end_progress=100,
        ),
    ]

    COMPETITOR_SEARCH = [
        PhaseConfig(
            name="🔎 Recherche",
            emoji="🔎",
            steps=["Génération des requêtes", "Récupération des candidats"],
            start_progress=0,
            end_progress=40,
        ),
        PhaseConfig(
            name="🎯 Filtrage",
            emoji="🎯",
            steps=["Classification des sites", "Scoring de pertinence"],
            start_progress=40,
            end_progress=70,
        ),
        PhaseConfig(
            name="✨ Enrichissement",
            emoji="✨",
            steps=["Analyse détaillée", "Extraction des métadonnées"],
            start_progress=70,
            end_progress=90,
        ),
        PhaseConfig(
            name="✅ Finalisation",
            emoji="✅",
            steps=["Validation finale", "Sauvegarde des résultats"],
            start_progress=90,
            end_progress=100,
        ),
    ]

    TREND_PIPELINE = [
        PhaseConfig(
            name="📊 Clustering",
            emoji="📊",
            steps=["Récupération des embeddings", "Clustering BERTopic", "Génération des labels"],
            start_progress=0,
            end_progress=30,
        ),
        PhaseConfig(
            name="⏰ Analyse Temporelle",
            emoji="⏰",
            steps=["Détection des tendances", "Calcul des métriques"],
            start_progress=30,
            end_progress=50,
        ),
        PhaseConfig(
            name="🧠 Enrichissement LLM",
            emoji="🧠",
            steps=["Synthèse des tendances", "Génération de recommandations"],
            start_progress=50,
            end_progress=75,
        ),
        PhaseConfig(
            name="🎯 Analyse des Gaps",
            emoji="🎯",
            steps=["Analyse de couverture", "Identification des opportunités"],
            start_progress=75,
            end_progress=100,
        ),
    ]

    ARTICLE_GENERATION = [
        PhaseConfig(
            name="📝 Préparation",
            emoji="📝",
            steps=["Chargement du contexte", "Analyse du sujet"],
            start_progress=0,
            end_progress=20,
        ),
        PhaseConfig(
            name="✍️ Rédaction",
            emoji="✍️",
            steps=["Génération du contenu", "Structuration de l'article"],
            start_progress=20,
            end_progress=70,
        ),
        PhaseConfig(
            name="🎨 Création Visuelle",
            emoji="🎨",
            steps=["Génération de l'image", "Optimisation visuelle"],
            start_progress=70,
            end_progress=90,
        ),
        PhaseConfig(
            name="✅ Validation",
            emoji="✅",
            steps=["Vérification qualité", "Sauvegarde finale"],
            start_progress=90,
            end_progress=100,
        ),
    ]


class ProgressLogger:
    """
    Enhanced logger with visual progress bars and phase grouping.

    Features:
    - Visual progress bars with emojis
    - Grouped logs by phase
    - Simplified output (details hidden by default)
    - Time tracking per phase

    Usage:
        logger = ProgressLogger("Editorial Analysis", WorkflowPhases.EDITORIAL_ANALYSIS)

        with logger.phase(0) as phase:
            phase.step("Recherche des URLs via sitemap")
            # ... do work ...
            phase.step("Validation du domaine")

        with logger.phase(1) as phase:
            phase.step("Crawling des pages")
            # ... do work ...
    """

    def __init__(
        self,
        workflow_name: str,
        phases: List[PhaseConfig],
        show_details: bool = False,
        use_colors: bool = True,
    ):
        """
        Initialize progress logger.

        Args:
            workflow_name: Name of the workflow
            phases: List of phase configurations
            show_details: Show technical details (default: False)
            use_colors: Use ANSI colors (default: True)
        """
        self.workflow_name = workflow_name
        self.phases = phases
        self.show_details = show_details
        self.use_colors = use_colors
        self.logger = get_logger(__name__)

        self.current_phase_idx: Optional[int] = None
        self.current_progress = 0
        self.start_time = time.time()
        self.phase_start_time: Optional[float] = None

        self._print_header()

    def _print_header(self):
        """Print workflow header."""
        border = "=" * 60
        print(f"\n{border}")
        print(f"🚀 {self.workflow_name}")
        print(f"{border}\n")

    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}min"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"

    def _draw_progress_bar(
        self,
        progress: int,
        width: int = 40,
        show_percentage: bool = True,
    ) -> str:
        """
        Draw a visual progress bar.

        Args:
            progress: Progress percentage (0-100)
            width: Width of the progress bar
            show_percentage: Show percentage text

        Returns:
            Formatted progress bar string
        """
        filled = int(width * progress / 100)
        bar = "█" * filled + "░" * (width - filled)

        if show_percentage:
            return f"[{bar}] {progress}%"
        return f"[{bar}]"

    def _print(self, message: str, indent: int = 0):
        """Print message with optional indentation."""
        indent_str = "  " * indent
        print(f"{indent_str}{message}")
        sys.stdout.flush()

    @contextmanager
    def phase(self, phase_idx: int):
        """
        Context manager for a workflow phase.

        Args:
            phase_idx: Index of the phase

        Yields:
            PhaseLogger instance
        """
        if phase_idx >= len(self.phases):
            raise ValueError(f"Invalid phase index: {phase_idx}")

        phase_config = self.phases[phase_idx]
        self.current_phase_idx = phase_idx
        self.phase_start_time = time.time()

        # Print phase header
        print()
        self._print(f"{phase_config.name}", indent=0)
        self._print("─" * 50, indent=0)

        phase_logger = PhaseLogger(self, phase_config)

        try:
            yield phase_logger
        finally:
            # Print phase completion
            duration = time.time() - self.phase_start_time
            self._print(
                f"✓ Terminé en {self._format_duration(duration)}",
                indent=1,
            )

            # Update global progress
            self.current_progress = phase_config.end_progress

            # Log to structured logger (for audit)
            if self.show_details:
                self.logger.info(
                    "Phase completed",
                    phase=phase_config.name,
                    duration_seconds=duration,
                    progress=self.current_progress,
                )

    def complete(self, summary: Optional[Dict[str, Any]] = None):
        """
        Mark workflow as completed.

        Args:
            summary: Optional summary statistics
        """
        total_duration = time.time() - self.start_time

        print()
        print("=" * 60)
        print(f"✅ {self.workflow_name} - Terminé")
        print(f"⏱️  Durée totale: {self._format_duration(total_duration)}")

        if summary:
            print("\n📊 Résumé:")
            for key, value in summary.items():
                print(f"   • {key}: {value}")

        print("=" * 60)
        print()

    def error(self, error_message: str, exception: Optional[Exception] = None):
        """
        Log an error.

        Args:
            error_message: Error message
            exception: Optional exception object
        """
        print()
        print("=" * 60)
        print(f"❌ Erreur: {error_message}")

        if exception and self.show_details:
            print(f"\nDétails techniques:")
            print(f"   {type(exception).__name__}: {str(exception)}")

        print("=" * 60)
        print()

        # Log to structured logger
        try:
            # Try structlog-style logging first
            if exception:
                self.logger.error(
                    "Workflow error",
                    error=error_message,
                    exception=str(exception),
                    exc_info=True,
                )
            else:
                self.logger.error("Workflow error", error=error_message)
        except TypeError:
            # Fallback to standard logging
            if exception:
                self.logger.error(f"Workflow error: {error_message} - {type(exception).__name__}: {str(exception)}", exc_info=True)
            else:
                self.logger.error(f"Workflow error: {error_message}")


class PhaseLogger:
    """Logger for a specific phase."""

    def __init__(self, parent: ProgressLogger, config: PhaseConfig):
        """
        Initialize phase logger.

        Args:
            parent: Parent ProgressLogger
            config: Phase configuration
        """
        self.parent = parent
        self.config = config
        self.current_step_idx = 0

    def step(self, message: str, details: Optional[Dict[str, Any]] = None):
        """
        Log a step within the phase.

        Args:
            message: Step message
            details: Optional details (only shown if show_details=True)
        """
        # Calculate step progress within phase range
        total_steps = len(self.config.steps)
        if total_steps > 0:
            step_progress = self.config.start_progress + (
                (self.config.end_progress - self.config.start_progress)
                * (self.current_step_idx + 1)
                / total_steps
            )
        else:
            step_progress = self.config.start_progress

        # Print step with progress bar
        progress_bar = self.parent._draw_progress_bar(int(step_progress), width=30)
        self.parent._print(f"  {self.config.emoji} {message}", indent=1)
        self.parent._print(progress_bar, indent=2)

        # Print details if enabled
        if details and self.parent.show_details:
            for key, value in details.items():
                self.parent._print(f"→ {key}: {value}", indent=3)

        self.current_step_idx += 1

        # Update parent progress
        self.parent.current_progress = int(step_progress)

    def info(self, message: str):
        """
        Log an info message.

        Args:
            message: Info message
        """
        self.parent._print(f"ℹ️  {message}", indent=2)

    def warning(self, message: str):
        """
        Log a warning message.

        Args:
            message: Warning message
        """
        self.parent._print(f"⚠️  {message}", indent=2)

    def success(self, message: str, count: Optional[int] = None):
        """
        Log a success message.

        Args:
            message: Success message
            count: Optional count to display
        """
        if count is not None:
            self.parent._print(f"✓ {message} ({count})", indent=2)
        else:
            self.parent._print(f"✓ {message}", indent=2)


# Convenience function to create logger for common workflows
def create_workflow_logger(
    workflow_type: str,
    show_details: bool = False,
) -> ProgressLogger:
    """
    Create a progress logger for a specific workflow type.

    Args:
        workflow_type: Type of workflow (editorial_analysis, competitor_search, trend_pipeline, article_generation)
        show_details: Show technical details

    Returns:
        Configured ProgressLogger
    """
    workflow_configs = {
        "editorial_analysis": ("Analyse Éditoriale", WorkflowPhases.EDITORIAL_ANALYSIS),
        "competitor_search": ("Recherche Concurrents", WorkflowPhases.COMPETITOR_SEARCH),
        "trend_pipeline": ("Pipeline de Tendances", WorkflowPhases.TREND_PIPELINE),
        "article_generation": ("Génération d'Article", WorkflowPhases.ARTICLE_GENERATION),
    }

    if workflow_type not in workflow_configs:
        raise ValueError(f"Unknown workflow type: {workflow_type}")

    name, phases = workflow_configs[workflow_type]
    return ProgressLogger(name, phases, show_details=show_details)
