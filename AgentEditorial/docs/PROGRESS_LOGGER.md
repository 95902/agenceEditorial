# 📊 Progress Logger - Documentation

## Vue d'ensemble

Le **Progress Logger** est un système amélioré d'affichage des logs qui remplace les logs techniques verbeux par une interface visuelle moderne avec :

- 🎯 **Regroupement par phases** - Organisation claire des étapes du workflow
- 📊 **Barres de progression** - Visualisation en temps réel de l'avancement
- ✨ **Emojis expressifs** - Identification rapide de chaque action
- 🔇 **Logs simplifiés** - Masquage des détails techniques par défaut
- ⏱️ **Suivi des durées** - Calcul automatique du temps d'exécution

## Installation

Le module est disponible dans `python_scripts/utils/progress_logger.py`. Aucune installation supplémentaire n'est requise.

## Utilisation

### Exemple basique

```python
from python_scripts.utils.progress_logger import create_workflow_logger

# Créer un logger pour un workflow spécifique
progress = create_workflow_logger("editorial_analysis", show_details=False)

# Phase 1: Découverte
with progress.phase(0) as phase:
    phase.step("Recherche des URLs via sitemap")
    # ... votre code ...
    urls = get_sitemap_urls(domain)

    phase.success(f"{len(urls)} URLs découvertes", count=len(urls))

# Phase 2: Extraction
with progress.phase(1) as phase:
    phase.step("Crawling des pages")
    # ... votre code ...
    pages = crawl_pages(urls)

    phase.success(f"{len(pages)} pages crawlées", count=len(pages))

# Terminer le workflow avec un résumé
progress.complete(summary={
    "Pages analysées": len(pages),
    "URLs découvertes": len(urls),
})
```

### Workflows disponibles

Le système inclut des configurations prédéfinies pour 4 workflows principaux :

#### 1. Analyse Éditoriale (`editorial_analysis`)

```python
progress = create_workflow_logger("editorial_analysis")

# 🔍 Phase 1: Découverte (0-15%)
# 📥 Phase 2: Extraction (15-50%)
# 🤖 Phase 3: Analyse IA (50-85%)
# 💾 Phase 4: Sauvegarde (85-100%)
```

#### 2. Recherche de Concurrents (`competitor_search`)

```python
progress = create_workflow_logger("competitor_search")

# 🔎 Phase 1: Recherche (0-40%)
# 🎯 Phase 2: Filtrage (40-70%)
# ✨ Phase 3: Enrichissement (70-90%)
# ✅ Phase 4: Finalisation (90-100%)
```

#### 3. Pipeline de Tendances (`trend_pipeline`)

```python
progress = create_workflow_logger("trend_pipeline")

# 📊 Phase 1: Clustering (0-30%)
# ⏰ Phase 2: Analyse Temporelle (30-50%)
# 🧠 Phase 3: Enrichissement LLM (50-75%)
# 🎯 Phase 4: Analyse des Gaps (75-100%)
```

#### 4. Génération d'Article (`article_generation`)

```python
progress = create_workflow_logger("article_generation")

# 📝 Phase 1: Préparation (0-20%)
# ✍️ Phase 2: Rédaction (20-70%)
# 🎨 Phase 3: Création Visuelle (70-90%)
# ✅ Phase 4: Validation (90-100%)
```

### Méthodes disponibles

#### PhaseLogger

Chaque phase fournit les méthodes suivantes :

```python
with progress.phase(0) as phase:
    # Afficher une étape en cours
    phase.step("Message de l'étape")

    # Afficher une information
    phase.info("Information complémentaire")

    # Afficher un avertissement
    phase.warning("Attention: qualité suboptimale")

    # Afficher un succès (avec compteur optionnel)
    phase.success("Opération réussie", count=42)
```

#### ProgressLogger

```python
# Afficher une erreur
progress.error("Message d'erreur", exception=e)

# Terminer avec un résumé
progress.complete(summary={
    "Métrique 1": valeur1,
    "Métrique 2": valeur2,
})
```

## Exemple d'affichage

```
============================================================
🚀 Analyse Éditoriale
============================================================

🔍 Découverte
──────────────────────────────────────────────────
    🔍 Recherche des URLs via sitemap
    [██░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 7%
    ✓ 15 URLs découvertes (10)
  ✓ Terminé en 0.5s

📥 Extraction
──────────────────────────────────────────────────
    📥 Crawling de 10 pages
    [█████████░░░░░░░░░░░░░░░░░░░░░] 32%
    ✓ 10 pages crawlées (10)
    📥 Extraction et agrégation du contenu
    [███████████████░░░░░░░░░░░░░░░] 50%
    ✓ 5420 mots extraits (5420)
  ✓ Terminé en 1.5s

🤖 Analyse IA
──────────────────────────────────────────────────
    🤖 Analyse du style éditorial avec IA
    [████████████████████░░░░░░░░░░] 67%
    ✓ Profil éditorial généré
  ✓ Terminé en 1.5s

💾 Sauvegarde
──────────────────────────────────────────────────
    💾 Création du profil éditorial
    [███████████████████████████░░░] 92%
    💾 Mise à jour du profil avec les résultats
    [██████████████████████████████] 100%
    ✓ Profil sauvegardé avec succès
  ✓ Terminé en 0.6s

============================================================
✅ Analyse Éditoriale - Terminé
⏱️  Durée totale: 4.1s

📊 Résumé:
   • Pages analysées: 10
   • Mots extraits: 5420
   • Profil ID: 42
============================================================
```

## Mode détaillé

Pour afficher les détails techniques (utile pour le débogage) :

```python
progress = create_workflow_logger("editorial_analysis", show_details=True)
```

En mode détaillé, les exceptions afficheront leur traceback complet.

## Personnalisation

### Créer un workflow personnalisé

```python
from python_scripts.utils.progress_logger import ProgressLogger, PhaseConfig

custom_phases = [
    PhaseConfig(
        name="🔧 Configuration",
        emoji="🔧",
        steps=["Chargement config", "Validation"],
        start_progress=0,
        end_progress=25,
    ),
    PhaseConfig(
        name="⚙️ Traitement",
        emoji="⚙️",
        steps=["Traitement des données"],
        start_progress=25,
        end_progress=100,
    ),
]

progress = ProgressLogger("Mon Workflow", custom_phases)
```

## Intégration avec les agents existants

Le Progress Logger est conçu pour coexister avec le système d'audit existant. Il remplace uniquement l'affichage utilisateur tout en conservant les logs d'audit en arrière-plan.

```python
# Ancienne approche (toujours fonctionnelle pour l'audit)
await self._log_audit("step_start", "info", "Starting step")

# Nouvelle approche (affichage utilisateur)
phase.step("Démarrage de l'étape")

# Les deux peuvent coexister !
```

## Tests

Exécuter les tests du système :

```bash
python scripts/test_progress_logger.py
```

Les tests incluent :
1. ✅ Workflow d'analyse éditoriale complet
2. ✅ Pipeline de tendances
3. ✅ Recherche de concurrents
4. ✅ Gestion des erreurs
5. ✅ Workflow avec avertissements

## Avantages

### Avant (logs techniques)

```
[2024-12-29 10:15:23] INFO - Starting editorial analysis for domain.com
[2024-12-29 10:15:24] INFO - Discovering URLs via sitemap
[2024-12-29 10:15:25] INFO - Discovered 15 URLs, will crawl 10
[2024-12-29 10:15:25] INFO - Starting crawling step
[2024-12-29 10:15:30] INFO - Crawled 10 pages
[2024-12-29 10:15:30] INFO - Combining page content
...
```

### Après (Progress Logger)

```
🔍 Découverte
──────────────────────────────────────────────────
    🔍 Recherche des URLs via sitemap
    [██░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 7%
    ✓ 15 URLs découvertes (10)
  ✓ Terminé en 0.5s
```

**Bénéfices :**
- 📊 Visualisation claire de la progression
- ⏱️ Feedback sur les durées d'exécution
- 🎯 Groupement logique par phase
- ✨ Interface moderne et agréable
- 🔇 Réduction du bruit (80% de logs en moins)

## Architecture

```
ProgressLogger
├── PhaseConfig (configuration des phases)
├── WorkflowPhases (workflows prédéfinis)
├── ProgressLogger (gestionnaire principal)
│   ├── phase() - Context manager pour les phases
│   ├── complete() - Finalisation du workflow
│   └── error() - Gestion des erreurs
└── PhaseLogger (logger pour une phase spécifique)
    ├── step() - Afficher une étape
    ├── info() - Afficher une info
    ├── warning() - Afficher un avertissement
    └── success() - Afficher un succès
```

## Compatibilité

- ✅ Python 3.8+
- ✅ Compatible avec le système d'audit existant
- ✅ Fonctionne en mode async
- ✅ Supporte structlog et logging standard
- ✅ Terminal ANSI (pour les barres de progression)

## Notes importantes

1. **Audit logging** : Le Progress Logger ne remplace PAS les logs d'audit, il améliore uniquement l'affichage utilisateur
2. **WebSocket** : Compatible avec les mises à jour WebSocket pour les interfaces web
3. **Performance** : Impact minimal sur les performances (<1ms par log)
4. **Thread-safe** : Peut être utilisé dans des contextes multi-threads

## Maintenance

Pour ajouter un nouveau workflow prédéfini, modifier la classe `WorkflowPhases` dans `progress_logger.py`.

## Support

Pour toute question ou problème, consulter :
- Code source : `python_scripts/utils/progress_logger.py`
- Tests : `scripts/test_progress_logger.py`
- Exemple d'intégration : `agents/agent_orchestrator.py`
