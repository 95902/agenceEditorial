"""Script de test pour le nouveau système de progress logger."""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from python_scripts.utils.progress_logger import create_workflow_logger


def test_editorial_analysis_logger():
    """Test du logger pour l'analyse éditoriale."""
    print("\n" + "="*80)
    print("TEST 1: Analyse Éditoriale - Workflow Complet")
    print("="*80)

    progress = create_workflow_logger("editorial_analysis", show_details=False)

    # PHASE 1: Découverte
    with progress.phase(0) as phase:
        phase.step("Recherche des URLs via sitemap")
        asyncio.run(asyncio.sleep(0.5))
        phase.success("15 URLs découvertes", count=10)

    # PHASE 2: Extraction
    with progress.phase(1) as phase:
        phase.step("Crawling de 10 pages")
        asyncio.run(asyncio.sleep(1))
        phase.success("10 pages crawlées", count=10)

        phase.step("Extraction et agrégation du contenu")
        asyncio.run(asyncio.sleep(0.5))
        phase.success("5420 mots extraits", count=5420)

    # PHASE 3: Analyse IA
    with progress.phase(2) as phase:
        phase.step("Analyse du style éditorial avec IA")
        asyncio.run(asyncio.sleep(1.5))
        phase.success("Profil éditorial généré")

    # PHASE 4: Sauvegarde
    with progress.phase(3) as phase:
        phase.step("Création du profil éditorial")
        asyncio.run(asyncio.sleep(0.3))

        phase.step("Mise à jour du profil avec les résultats")
        asyncio.run(asyncio.sleep(0.3))

        phase.success("Profil sauvegardé avec succès")

    # Completion
    progress.complete(summary={
        "Pages analysées": 10,
        "Mots extraits": 5420,
        "Profil ID": 42,
    })


def test_trend_pipeline_logger():
    """Test du logger pour le pipeline de tendances."""
    print("\n" + "="*80)
    print("TEST 2: Pipeline de Tendances - Workflow Complet")
    print("="*80)

    progress = create_workflow_logger("trend_pipeline", show_details=False)

    # PHASE 1: Clustering
    with progress.phase(0) as phase:
        phase.step("Récupération des embeddings")
        asyncio.run(asyncio.sleep(0.5))
        phase.info("150 articles trouvés dans Qdrant")

        phase.step("Clustering BERTopic")
        asyncio.run(asyncio.sleep(1))

        phase.step("Génération des labels")
        asyncio.run(asyncio.sleep(0.5))
        phase.success("12 clusters identifiés", count=12)

    # PHASE 2: Analyse Temporelle
    with progress.phase(1) as phase:
        phase.step("Détection des tendances")
        asyncio.run(asyncio.sleep(0.8))

        phase.step("Calcul des métriques")
        asyncio.run(asyncio.sleep(0.5))
        phase.success("Métriques temporelles calculées")

    # PHASE 3: Enrichissement LLM
    with progress.phase(2) as phase:
        phase.step("Synthèse des tendances")
        asyncio.run(asyncio.sleep(1.2))

        phase.step("Génération de recommandations")
        asyncio.run(asyncio.sleep(1))
        phase.success("36 recommandations générées", count=36)

    # PHASE 4: Analyse des Gaps
    with progress.phase(3) as phase:
        phase.step("Analyse de couverture")
        asyncio.run(asyncio.sleep(0.7))

        phase.step("Identification des opportunités")
        asyncio.run(asyncio.sleep(0.6))
        phase.success("8 gaps identifiés", count=8)

    # Completion
    progress.complete(summary={
        "Clusters": 12,
        "Recommandations": 36,
        "Gaps identifiés": 8,
    })


def test_competitor_search_logger():
    """Test du logger pour la recherche de concurrents."""
    print("\n" + "="*80)
    print("TEST 3: Recherche Concurrents - Workflow Complet")
    print("="*80)

    progress = create_workflow_logger("competitor_search", show_details=False)

    # PHASE 1: Recherche
    with progress.phase(0) as phase:
        phase.step("Génération des requêtes")
        asyncio.run(asyncio.sleep(0.3))

        phase.step("Récupération des candidats")
        asyncio.run(asyncio.sleep(1))
        phase.success("245 candidats trouvés", count=245)

    # PHASE 2: Filtrage
    with progress.phase(1) as phase:
        phase.step("Classification des sites")
        asyncio.run(asyncio.sleep(0.8))

        phase.step("Scoring de pertinence")
        asyncio.run(asyncio.sleep(0.6))
        phase.success("85 sites pertinents", count=85)

    # PHASE 3: Enrichissement
    with progress.phase(2) as phase:
        phase.step("Analyse détaillée")
        asyncio.run(asyncio.sleep(1))

        phase.step("Extraction des métadonnées")
        asyncio.run(asyncio.sleep(0.5))
        phase.success("Métadonnées extraites")

    # PHASE 4: Finalisation
    with progress.phase(3) as phase:
        phase.step("Validation finale")
        asyncio.run(asyncio.sleep(0.4))

        phase.step("Sauvegarde des résultats")
        asyncio.run(asyncio.sleep(0.3))
        phase.success("Résultats sauvegardés")

    # Completion
    progress.complete(summary={
        "Candidats trouvés": 245,
        "Concurrents retenus": 85,
    })


def test_error_handling():
    """Test de la gestion des erreurs."""
    print("\n" + "="*80)
    print("TEST 4: Gestion des Erreurs")
    print("="*80)

    progress = create_workflow_logger("editorial_analysis", show_details=True)

    try:
        # PHASE 1: Découverte
        with progress.phase(0) as phase:
            phase.step("Recherche des URLs via sitemap")
            asyncio.run(asyncio.sleep(0.5))
            phase.success("15 URLs découvertes", count=10)

        # PHASE 2: Extraction (avec erreur)
        with progress.phase(1) as phase:
            phase.step("Crawling de 10 pages")
            asyncio.run(asyncio.sleep(0.5))

            # Simuler une erreur
            raise ValueError("Impossible de crawler le domaine: connexion refusée")

    except Exception as e:
        progress.error("Échec du workflow", exception=e)


def test_with_warnings():
    """Test avec des avertissements."""
    print("\n" + "="*80)
    print("TEST 5: Workflow avec Avertissements")
    print("="*80)

    progress = create_workflow_logger("article_generation", show_details=False)

    # PHASE 1: Préparation
    with progress.phase(0) as phase:
        phase.step("Chargement du contexte")
        asyncio.run(asyncio.sleep(0.4))

        phase.step("Analyse du sujet")
        asyncio.run(asyncio.sleep(0.5))
        phase.success("Contexte chargé")

    # PHASE 2: Rédaction
    with progress.phase(1) as phase:
        phase.step("Génération du contenu")
        asyncio.run(asyncio.sleep(1.2))

        phase.step("Structuration de l'article")
        asyncio.run(asyncio.sleep(0.6))
        phase.success("Article rédigé (2500 mots)", count=2500)

    # PHASE 3: Création Visuelle
    with progress.phase(2) as phase:
        phase.step("Génération de l'image")
        asyncio.run(asyncio.sleep(1))

        phase.warning("Qualité de l'image suboptimale, nouvelle tentative...")
        asyncio.run(asyncio.sleep(1))

        phase.step("Optimisation visuelle")
        asyncio.run(asyncio.sleep(0.5))
        phase.success("Image générée (score: 0.82)")

    # PHASE 4: Validation
    with progress.phase(3) as phase:
        phase.step("Vérification qualité")
        asyncio.run(asyncio.sleep(0.6))

        phase.step("Sauvegarde finale")
        asyncio.run(asyncio.sleep(0.3))
        phase.success("Article publié")

    # Completion
    progress.complete(summary={
        "Mots": 2500,
        "Images": 1,
        "Score qualité": "0.82",
    })


if __name__ == "__main__":
    print("\n" + "="*80)
    print("🧪 TESTS DU NOUVEAU SYSTÈME DE PROGRESS LOGGER")
    print("="*80)

    # Run all tests
    test_editorial_analysis_logger()
    test_trend_pipeline_logger()
    test_competitor_search_logger()
    test_error_handling()
    test_with_warnings()

    print("\n" + "="*80)
    print("✅ TOUS LES TESTS TERMINÉS")
    print("="*80 + "\n")
