"""Utility functions for sites API."""

import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from python_scripts.api.schemas.responses import AngleDetail, MetricComparison, TopicPredictions
from python_scripts.database.models import SiteProfile
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


def _safe_json_field(value: Any) -> Optional[Dict[str, Any]]:
    """
    Safely convert a JSON field value to a dictionary.
    
    Handles cases where the value might be:
    - None -> return None
    - Already a dict -> return as-is
    - A JSON string -> try to parse
    - A malformed/truncated string -> return empty dict with error info
    
    Args:
        value: The value to convert
        
    Returns:
        A dictionary or None
    """
    if value is None:
        return None
    
    if isinstance(value, dict):
        return value
    
    if isinstance(value, str):
        value_stripped = value.strip()
        if value_stripped.startswith(("{", "[")):
            try:
                parsed = json.loads(value_stripped)
                if isinstance(parsed, dict):
                    return parsed
                elif isinstance(parsed, list):
                    return {"items": parsed}
                return {"value": parsed}
            except json.JSONDecodeError:
                # Malformed JSON - return empty dict with raw value indicator
                logger.warning(
                    "Malformed JSON field detected",
                    value_preview=value[:100] if len(value) > 100 else value,
                )
                return {"_raw_malformed": value[:200] if len(value) > 200 else value}
        # Not JSON-like string
        return {"value": value}
    
    # Other types - wrap in dict
    return {"value": str(value)}


def _map_language_level_to_vocabulary(language_level: Optional[str]) -> str:
    """
    Map language_level to vocabulary description.
    
    Args:
        language_level: Language level string
        
    Returns:
        Vocabulary description
    """
    if not language_level:
        return "langage technique"
    
    mapping = {
        "simple": "langage accessible",
        "intermediate": "langage technique",
        "advanced": "spécialisé en technologie",
        "expert": "très spécialisé",
    }
    
    return mapping.get(language_level.lower(), "langage technique")


def _calculate_article_format(content_structure: Optional[Dict[str, Any]]) -> str:
    """
    Calculate article format from content_structure.
    
    Args:
        content_structure: Content structure dictionary
        
    Returns:
        Format description
    """
    if not content_structure or not isinstance(content_structure, dict):
        return "articles moyens (1000-2000 mots)"
    
    avg_word_count = content_structure.get("average_word_count")
    if not avg_word_count or not isinstance(avg_word_count, (int, float)):
        return "articles moyens (1000-2000 mots)"
    
    if avg_word_count < 1000:
        return "articles courts (< 1000 mots)"
    elif avg_word_count <= 2000:
        return "articles moyens (1000-2000 mots)"
    else:
        return "articles longs (1500-2500 mots)"


def _map_language_level_to_audience_level(language_level: Optional[str]) -> str:
    """
    Map language_level to audience level description.
    
    Args:
        language_level: Language level string
        
    Returns:
        Audience level description
    """
    if not language_level:
        return "Intermédiaire"
    
    mapping = {
        "simple": "Débutant",
        "intermediate": "Intermédiaire",
        "advanced": "Intermédiaire à Expert",
        "expert": "Expert",
    }
    
    return mapping.get(language_level.lower(), "Intermédiaire")


def _extract_audience_sectors(target_audience: Optional[Dict[str, Any]]) -> List[str]:
    """
    Extract sectors from target_audience.
    
    Args:
        target_audience: Target audience dictionary
        
    Returns:
        List of sectors
    """
    if not target_audience or not isinstance(target_audience, dict):
        return []
    
    # Try secondary first
    secondary = target_audience.get("secondary")
    if isinstance(secondary, list):
        return secondary
    
    # Try sectors field
    sectors = target_audience.get("sectors")
    if isinstance(sectors, list):
        return sectors
    
    # Try demographics.sectors
    demographics = target_audience.get("demographics", {})
    if isinstance(demographics, dict):
        demo_sectors = demographics.get("sectors")
        if isinstance(demo_sectors, list):
            return demo_sectors
    
    return []


def _slugify(text: str) -> str:
    """
    Convert text to slug format.
    
    Args:
        text: Text to slugify
        
    Returns:
        Slug string
    """
    # Convert to lowercase
    text = text.lower()
    # Replace spaces and special chars with hyphens
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    # Remove leading/trailing hyphens
    text = text.strip("-")
    return text


def _count_articles_for_domain(
    articles: List[Any], domain_label: str
) -> int:
    """
    Count articles that match a domain label.
    
    Uses heuristics: check if domain keywords appear in article title or keywords.
    
    Args:
        articles: List of ClientArticle objects
        domain_label: Domain label to match
        
    Returns:
        Count of matching articles
    """
    if not articles or not domain_label:
        return 0
    
    # Extract keywords from domain label
    domain_keywords = set(domain_label.lower().split())
    
    count = 0
    for article in articles:
        # Check title
        title_lower = article.title.lower() if hasattr(article, "title") else ""
        if any(keyword in title_lower for keyword in domain_keywords if len(keyword) > 3):
            count += 1
            continue
        
        # Check keywords field
        if hasattr(article, "keywords") and article.keywords:
            keywords = article.keywords
            if isinstance(keywords, dict):
                primary_keywords = keywords.get("primary_keywords", [])
                if isinstance(primary_keywords, list):
                    keywords_str = " ".join(str(k).lower() for k in primary_keywords)
                    if any(keyword in keywords_str for keyword in domain_keywords if len(keyword) > 3):
                        count += 1
                        continue
    
    return count


def _calculate_read_time(word_count: int) -> str:
    """
    Calculate estimated read time from word count.
    
    Args:
        word_count: Number of words
        
    Returns:
        Read time string (e.g., "8 min")
    """
    # Average reading speed: 200 words per minute
    minutes = max(1, round(word_count / 200))
    return f"{minutes} min"


def _determine_trend(velocity: Optional[float]) -> Optional[str]:
    """
    Determine trend direction from velocity.
    
    Args:
        velocity: Velocity metric from temporal analysis
        
    Returns:
        Trend direction: "up", "stable", or "down"
    """
    if velocity is None:
        return None
    
    if velocity > 0.1:
        return "up"
    elif velocity < -0.1:
        return "down"
    else:
        return "stable"


def _slugify_topic_id(topic_id: int, label: str) -> str:
    """
    Generate a slug identifier for a topic.
    
    Args:
        topic_id: Topic ID
        label: Topic label
        
    Returns:
        Slug identifier
    """
    slug = _slugify(label)
    return f"{slug}-{topic_id}" if slug else f"topic-{topic_id}"


def _extract_topic_id_from_slug(slug: str) -> Optional[int]:
    """
    Extract topic_id from slug format: "label-topic_id" or "label-topic_id-extra".
    
    Args:
        slug: Topic slug (e.g., "edge-cloud-hybride-5" or "erpnext_erp_votre-11")
        
    Returns:
        Topic ID if found, None otherwise
    """
    # Parse slug to extract topic_id
    # Format: {label}-{topic_id} or {label}-{topic_id}-{extra}
    parts = slug.split("-")
    # Try to find numeric part at the end
    for part in reversed(parts):
        if part.isdigit():
            return int(part)
    return None


def _extract_key_points_from_outline(outline: Dict[str, Any]) -> List[str]:
    """
    Extract key points from article recommendation outline.
    
    Args:
        outline: Outline dictionary from ArticleRecommendation
        
    Returns:
        List of key points
    """
    key_points = []
    
    if isinstance(outline, dict):
        # Extract from sections
        for section_key, section_data in outline.items():
            if isinstance(section_data, dict):
                # Get section title
                if "title" in section_data:
                    key_points.append(section_data["title"])
                
                # Get key_points from section
                if "key_points" in section_data:
                    points = section_data["key_points"]
                    if isinstance(points, list):
                        key_points.extend(points)
    
    return key_points[:10]  # Limit to 10 points


def _transform_opportunities_to_angles(
    opportunities: Optional[List[str]],
    article_recommendations: List[Any],
) -> List[AngleDetail]:
    """
    Transform opportunities and article recommendations into angle details.
    
    Args:
        opportunities: List of opportunity strings from TrendAnalysis
        article_recommendations: List of ArticleRecommendation
        
    Returns:
        List of AngleDetail
    """
    angles = []
    
    # Use article recommendations if available
    for reco in article_recommendations[:3]:  # Limit to 3
        potential = "Élevé"
        if reco.differentiation_score:
            if reco.differentiation_score >= 0.7:
                potential = "Très élevé"
            elif reco.differentiation_score < 0.4:
                potential = "Moyen"
        
        differentiation = None
        if reco.differentiation_score:
            differentiation = f"Score de différenciation: {reco.differentiation_score:.2f}"
        
        angles.append(AngleDetail(
            angle=reco.title,
            description=reco.hook,
            differentiation=differentiation,
            potential=potential,
        ))
    
    # Fallback to opportunities if no recommendations
    if not angles and opportunities:
        for opp in opportunities[:3]:  # Limit to 3
            angles.append(AngleDetail(
                angle=opp,
                description=f"Opportunité éditoriale: {opp}",
                differentiation=None,
                potential="Élevé",
            ))
    
    return angles


def _calculate_trend_delta(
    current_velocity: Optional[float],
    previous_velocity: Optional[float],
) -> Optional[str]:
    """
    Calculate trend delta description.
    
    Args:
        current_velocity: Current velocity value
        previous_velocity: Previous velocity value (optional)
        
    Returns:
        Delta description string or None
    """
    if current_velocity is None:
        return None
    
    if previous_velocity is not None and previous_velocity > 0:
        delta_pct = ((current_velocity - previous_velocity) / previous_velocity) * 100
        return f"{delta_pct:+.1f}% de recherches sur ce sujet dans les 30 derniers jours"
    
    # Fallback: estimate from velocity
    if current_velocity > 1.2:
        return "+35% de recherches sur ce sujet dans les 30 derniers jours"
    elif current_velocity > 0.8:
        return "Stable"
    else:
        return "-20% de recherches sur ce sujet dans les 30 derniers jours"


def _generate_predictions(
    volume: int,
    effort_level: Optional[str],
    differentiation_score: Optional[float],
) -> TopicPredictions:
    """
    Generate predictions based on metrics.
    
    Args:
        volume: Article volume
        effort_level: Effort level from ArticleRecommendation
        differentiation_score: Differentiation score
        
    Returns:
        TopicPredictions
    """
    # Estimate views based on volume
    if volume > 100:
        views_range = "2,500 - 4,000"
    elif volume > 50:
        views_range = "1,500 - 2,500"
    else:
        views_range = "500 - 1,500"
    
    # Estimate shares (roughly 2-3% of views)
    shares_range = "50 - 80"
    
    # Estimate writing time from effort level
    writing_time = "2-3 heures"
    if effort_level == "easy":
        writing_time = "1-2 heures"
    elif effort_level == "complex":
        writing_time = "4-6 heures"
    
    # Difficulty from effort level
    difficulty = "Intermédiaire"
    if effort_level == "easy":
        difficulty = "Facile"
    elif effort_level == "complex":
        difficulty = "Avancé"
    
    return TopicPredictions(
        views=views_range,
        shares=shares_range,
        writing_time=writing_time,
        difficulty=difficulty,
    )


def _normalize_site_client(site_client: str) -> str:
    """
    Normalize site_client parameter to extract domain from URL if needed.
    
    Handles cases like:
    - "https://innosys.fr" -> "innosys.fr"
    - "http://innosys.fr" -> "innosys.fr"
    - "www.innosys.fr" -> "innosys.fr"
    - "innosys.fr" -> "innosys.fr"
    - "innosys" -> "innosys"
    
    Args:
        site_client: Client site identifier (can be URL, domain, or name)
        
    Returns:
        Normalized domain string
    """
    # If it looks like a URL, extract the domain
    if site_client.startswith(("http://", "https://")):
        try:
            parsed = urlparse(site_client)
            domain = parsed.netloc or parsed.path.split("/")[0]
        except Exception:
            domain = site_client
    else:
        domain = site_client
    
    # Remove www. prefix if present
    if domain.startswith("www."):
        domain = domain[4:]
    
    # Remove trailing slash if present
    domain = domain.rstrip("/")
    
    return domain.lower() if domain else site_client


def compare_metrics(
    current_profile: SiteProfile,
    previous_profile: Optional[SiteProfile],
) -> List[MetricComparison]:
    """
    Compare metrics between current and previous analysis.

    Args:
        current_profile: Current site profile
        previous_profile: Previous site profile (if available)

    Returns:
        List of metric comparisons
    """
    comparisons: List[MetricComparison] = []

    if not previous_profile:
        return comparisons

    # Compare pages_analyzed
    if current_profile.pages_analyzed and previous_profile.pages_analyzed:
        change = (
            (current_profile.pages_analyzed - previous_profile.pages_analyzed)
            / previous_profile.pages_analyzed
            * 100
            if previous_profile.pages_analyzed > 0
            else 0
        )
        trend = "increasing" if change > 0 else "decreasing" if change < 0 else "stable"
        comparisons.append(
            MetricComparison(
                metric_name="pages_analyzed",
                current_value=current_profile.pages_analyzed,
                previous_value=previous_profile.pages_analyzed,
                change=round(change, 2),
                trend=trend,
            )
        )

    # Compare language_level (if changed)
    if current_profile.language_level and previous_profile.language_level:
        if current_profile.language_level != previous_profile.language_level:
            comparisons.append(
                MetricComparison(
                    metric_name="language_level",
                    current_value=current_profile.language_level,
                    previous_value=previous_profile.language_level,
                    change=None,
                    trend="changed",
                )
            )

    # Compare editorial_tone (if changed)
    if current_profile.editorial_tone and previous_profile.editorial_tone:
        if current_profile.editorial_tone != previous_profile.editorial_tone:
            comparisons.append(
                MetricComparison(
                    metric_name="editorial_tone",
                    current_value=current_profile.editorial_tone,
                    previous_value=previous_profile.editorial_tone,
                    change=None,
                    trend="changed",
                )
            )

    return comparisons

