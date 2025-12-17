"""Tests unitaires pour le module topic_filters."""

import pytest
from python_scripts.analysis.article_enrichment.topic_filters import (
    classify_topic_label,
    is_major_topic,
    filter_by_scope,
    get_scope_distribution,
)


class TestClassifyTopicLabel:
    """Tests pour classify_topic_label."""
    
    def test_core_topics(self):
        """Test de classification des topics core."""
        assert classify_topic_label("cybersécurité cloud") == "core"
        assert classify_topic_label("développement Python") == "core"
        assert classify_topic_label("data intelligence") == "core"
        assert classify_topic_label("devops docker kubernetes") == "core"
        assert classify_topic_label("product management agile") == "core"
    
    def test_adjacent_topics(self):
        """Test de classification des topics adjacents."""
        assert classify_topic_label("accessibilité web") == "adjacent"
        assert classify_topic_label("design UX UI") == "adjacent"
        assert classify_topic_label("réglementation RGPD") == "adjacent"
        assert classify_topic_label("innovation startup") == "adjacent"
        assert classify_topic_label("diversité inclusion") == "adjacent"
    
    def test_off_scope_topics(self):
        """Test de classification des topics off-scope."""
        assert classify_topic_label("accueil hôtellerie") == "off_scope"
        assert classify_topic_label("région Bretagne") == "off_scope"
        assert classify_topic_label("comptabilité fiscale") == "off_scope"
        assert classify_topic_label("TGS France actualités") == "off_scope"
    
    def test_priority_order(self):
        """Test de la priorité de classification (off_scope > core > adjacent)."""
        # Si un label contient à la fois des mots core et off_scope, off_scope gagne
        assert classify_topic_label("cloud accueil") == "off_scope"
        
        # Si un label ne contient que des mots core, core gagne
        assert classify_topic_label("cloud cybersécurité") == "core"
    
    def test_empty_label(self):
        """Test avec un label vide."""
        assert classify_topic_label("") == "off_scope"
        assert classify_topic_label(None) == "off_scope"
    
    def test_unknown_label(self):
        """Test avec un label inconnu (par défaut off_scope)."""
        assert classify_topic_label("sujet totalement inconnu") == "off_scope"


class TestIsMajorTopic:
    """Tests pour is_major_topic."""
    
    def test_major_topic_by_size(self):
        """Test de détection d'un topic majeur par taille."""
        assert is_major_topic(size=25, min_size=20) is True
        assert is_major_topic(size=50, min_size=20) is True
    
    def test_not_major_topic_by_size(self):
        """Test de détection d'un topic non-majeur par taille."""
        assert is_major_topic(size=15, min_size=20) is False
        assert is_major_topic(size=5, min_size=20) is False
    
    def test_major_topic_with_coherence(self):
        """Test avec score de cohérence."""
        # Taille OK + cohérence OK = majeur
        assert is_major_topic(size=25, coherence_score=0.5, min_size=20, min_coherence=0.3) is True
        
        # Taille OK mais cohérence trop faible = non-majeur
        assert is_major_topic(size=25, coherence_score=0.2, min_size=20, min_coherence=0.3) is False
    
    def test_custom_thresholds(self):
        """Test avec des seuils personnalisés."""
        assert is_major_topic(size=10, min_size=5) is True
        assert is_major_topic(size=10, coherence_score=0.6, min_size=5, min_coherence=0.7) is False


class TestFilterByScope:
    """Tests pour filter_by_scope."""
    
    def test_filter_all(self):
        """Test sans filtre (scope=all)."""
        items = [
            {"topic_label": "cybersécurité", "value": 1},
            {"topic_label": "accessibilité", "value": 2},
            {"topic_label": "accueil", "value": 3},
        ]
        filtered = filter_by_scope(items, "all")
        assert len(filtered) == 3
    
    def test_filter_core(self):
        """Test de filtrage sur scope=core."""
        items = [
            {"topic_label": "cybersécurité", "value": 1},
            {"topic_label": "accessibilité", "value": 2},
            {"topic_label": "accueil", "value": 3},
        ]
        filtered = filter_by_scope(items, "core")
        assert len(filtered) == 1
        assert filtered[0]["value"] == 1
    
    def test_filter_adjacent(self):
        """Test de filtrage sur scope=adjacent."""
        items = [
            {"topic_label": "cybersécurité", "value": 1},
            {"topic_label": "accessibilité", "value": 2},
            {"topic_label": "accueil", "value": 3},
        ]
        filtered = filter_by_scope(items, "adjacent")
        assert len(filtered) == 1
        assert filtered[0]["value"] == 2
    
    def test_filter_off_scope(self):
        """Test de filtrage sur scope=off_scope."""
        items = [
            {"topic_label": "cybersécurité", "value": 1},
            {"topic_label": "accessibilité", "value": 2},
            {"topic_label": "accueil", "value": 3},
        ]
        filtered = filter_by_scope(items, "off_scope")
        assert len(filtered) == 1
        assert filtered[0]["value"] == 3
    
    def test_filter_custom_label_key(self):
        """Test avec une clé de label personnalisée."""
        items = [
            {"label": "cybersécurité", "value": 1},
            {"label": "accueil", "value": 2},
        ]
        filtered = filter_by_scope(items, "core", label_key="label")
        assert len(filtered) == 1
        assert filtered[0]["value"] == 1


class TestGetScopeDistribution:
    """Tests pour get_scope_distribution."""
    
    def test_distribution(self):
        """Test de calcul de distribution."""
        items = [
            {"topic_label": "cybersécurité"},
            {"topic_label": "cloud"},
            {"topic_label": "accessibilité"},
            {"topic_label": "accueil"},
            {"topic_label": "région"},
        ]
        dist = get_scope_distribution(items)
        assert dist["core"] == 2
        assert dist["adjacent"] == 1
        assert dist["off_scope"] == 2
    
    def test_empty_list(self):
        """Test avec une liste vide."""
        dist = get_scope_distribution([])
        assert dist["core"] == 0
        assert dist["adjacent"] == 0
        assert dist["off_scope"] == 0
    
    def test_custom_label_key(self):
        """Test avec une clé de label personnalisée."""
        items = [
            {"label": "cybersécurité"},
            {"label": "cloud"},
        ]
        dist = get_scope_distribution(items, label_key="label")
        assert dist["core"] == 2




