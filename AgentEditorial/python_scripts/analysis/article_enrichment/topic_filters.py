"""Module de filtrage et classification des topics pour Innosys.

Ce module fournit des fonctions utilitaires pour :
- Déterminer si un topic est "majeur" (basé sur taille et cohérence)
- Classifier un topic selon la grille Innosys (core/adjacent/off_scope)
"""

from typing import Literal, Optional
import re


# =============================================================================
# Grille de classification Innosys
# =============================================================================

# Topics cœur de cible Innosys (cloud, cybersécurité, data, dev, product, conseil IT)
CORE_KEYWORDS = [
    "cloud", "cybersécurité", "cyber", "sécurité", "vulnerab",
    "data", "donnée", "intelligence", "ai", "ia", "machine learning", "ml",
    "développeur", "développement", "dev", "javascript", "python", "java", "framework",
    "product", "management", "agile", "scrum",
    "consulting", "conseil", "ingénieur", "consultant",
    "webtech", "web", "application", "mobile", "api",
    "test", "automatisation", "devops", "docker", "kubernetes",
    "microsoft", "365", "copilot", "aws", "azure", "gcp",
    "blockchain", "crypto", "architecture", "microservice",
]

# Topics adjacents intéressants (accessibilité, design, réglementation, RSE tech)
ADJACENT_KEYWORDS = [
    "accessibilité", "design", "ux", "ui", "ergonomie",
    "digital", "numérique", "transformation",
    "regulation", "réglementation", "rgpd", "compliance",
    "innovation", "startup", "scale", "croissance",
    "rse", "responsabilité", "environnement", "décarbonisation", "climat",
    "diversité", "inclusion", "fémin", "égalité",
    "emploi", "talent", "recrutement", "formation",
]

# Topics à faible priorité / hors-scope
OFF_SCOPE_KEYWORDS = [
    "accueil", "hospitalité", "hôtel", "hôtellerie",
    "région", "alpes", "loire", "bretagne", "normandie", "géographique",
    "comptable", "compta", "expert-comptable", "fiscal", "fiduci",
    "garage", "petit commerce", "vitrine", "boutique",
    "publicité", "pub", "marketing", "communication",
    "tgs france", "excilio", "kikas", "pickers", "smile groupe",
    "harington", "kit harington", "world clean up",
]


TopicScope = Literal["core", "adjacent", "off_scope"]


def classify_topic_label(label: str) -> TopicScope:
    """
    Classifier un topic_label selon la grille Innosys.
    
    Args:
        label: Le label du topic (ex: "cybersécurité_cloud")
        
    Returns:
        "core" si le topic est cœur de cible Innosys
        "adjacent" si le topic est adjacent intéressant
        "off_scope" si le topic est hors-scope / faible priorité
    """
    if not label:
        return "off_scope"
    
    label_lower = label.lower()
    
    # Vérifier d'abord off_scope (plus spécifique)
    for keyword in OFF_SCOPE_KEYWORDS:
        if keyword in label_lower:
            return "off_scope"
    
    # Puis core (priorité haute)
    for keyword in CORE_KEYWORDS:
        if keyword in label_lower:
            return "core"
    
    # Enfin adjacent
    for keyword in ADJACENT_KEYWORDS:
        if keyword in label_lower:
            return "adjacent"
    
    # Par défaut, considérer comme off_scope si aucun match
    return "off_scope"


def is_major_topic(
    size: int,
    coherence_score: Optional[float] = None,
    min_size: int = 20,
    min_coherence: float = 0.3,
) -> bool:
    """
    Déterminer si un topic est "majeur" selon des critères de qualité.
    
    Args:
        size: Nombre d'articles dans le cluster
        coherence_score: Score de cohérence du cluster (optionnel)
        min_size: Taille minimale pour considérer un topic comme majeur
        min_coherence: Cohérence minimale (si fournie)
        
    Returns:
        True si le topic est considéré comme majeur
    """
    # Critère principal : taille
    if size < min_size:
        return False
    
    # Critère secondaire : cohérence (si disponible)
    if coherence_score is not None and coherence_score < min_coherence:
        return False
    
    return True


def filter_by_scope(items: list, scope_filter: str, label_key: str = "topic_label") -> list:
    """
    Filtrer une liste d'items par scope (core/adjacent/off_scope).
    
    Args:
        items: Liste d'items à filtrer (dicts avec un champ topic_label)
        scope_filter: Scope voulu ("all", "core", "adjacent", "off_scope")
        label_key: Clé du label dans les dicts (défaut: "topic_label")
        
    Returns:
        Liste filtrée
    """
    if scope_filter == "all":
        return items
    
    filtered = []
    for item in items:
        label = item.get(label_key, "")
        if classify_topic_label(label) == scope_filter:
            filtered.append(item)
    
    return filtered


def get_scope_distribution(items: list, label_key: str = "topic_label") -> dict:
    """
    Calculer la distribution des topics par scope.
    
    Args:
        items: Liste d'items (dicts avec un champ topic_label)
        label_key: Clé du label dans les dicts
        
    Returns:
        Dict avec le compte par scope: {"core": n, "adjacent": m, "off_scope": p}
    """
    distribution = {"core": 0, "adjacent": 0, "off_scope": 0}
    
    for item in items:
        label = item.get(label_key, "")
        scope = classify_topic_label(label)
        distribution[scope] += 1
    
    return distribution










