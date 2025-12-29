---
name: Créer issue amélioration WorkflowExecution
overview: Créer un document d'issue Markdown dans `docs/issues/` documentant les améliorations proposées pour la gestion des WorkflowExecution dans la route `/audit`, permettant un suivi global de la progression avec statut détaillé de chaque étape.
todos: []
---

# Plan : Création d'une i

ssue pour l'amélioration de la gestion des WorkflowExecution

## Objectif

Créer un document d'issue Markdown (`docs/issues/004-amélioration-gestion-workflow-execution-audit.md`) qui documente :

- Le problème actuel avec la gestion des workflows dans la route `/audit`
- Les améliorations proposées pour un suivi global de la progression
- Les détails techniques d'implémentation

## Structure de l'issue

L'issue suivra le format des issues existantes (`003-assignation-topic-id-articles.md`) avec :

1. **En-tête** : Métadonnées (date, statut, priorité, type, labels)
2. **Contexte** : Description du problème actuel
3. **Objectif** : Ce qui doit être amélioré
4. **Analyse technique** : Analyse du code existant
5. **Solutions proposées** : Options avec recommandation
6. **Implémentation détaillée** : Détails techniques des changements
7. **Tests** : Tests à effectuer
8. **Historique** : Suivi des modifications

## Contenu à inclure

### Problèmes identifiés

- Les workflows enfants ne sont pas tous liés à l'orchestrator via `parent_execution_id`
- Pas de route pour récupérer le statut global de l'audit
- Pas de calcul de progression globale
- Les statuts des étapes ne sont pas mis à jour en temps réel

### Solutions proposées

- Lier tous les workflows enfants à l'orchestrator
- Créer une nouvelle route `GET /{domain}/audit/status/{execution_id}`
- Calculer la progression globale basée sur les étapes
- Ajouter des schémas de réponse détaillés (`AuditStatusResponse`, `WorkflowStepDetail`)

### Fichiers concernés

- `python_scripts/api/routers/sites.py` : Modifier `run_missing_workflows_chain` et ajouter la route de statut
- `python_scripts/api/schemas/responses.py` : Ajouter les nouveaux schémas
- `python_scripts/database/models.py` : Modèle `WorkflowExecution` (déjà existant)

## Diagramme de flux

Inclure un diagramme Mermaid montrant :