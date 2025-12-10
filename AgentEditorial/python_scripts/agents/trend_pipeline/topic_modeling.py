"""Topic modeling with BERTopic (T119-T124 - US7)."""

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from bertopic import BERTopic
from hdbscan import HDBSCAN
from sentence_transformers import SentenceTransformer
from umap import UMAP

from python_scripts.config.settings import settings
from python_scripts.utils.exceptions import TopicModelingError
from python_scripts.utils.logging import get_logger
from python_scripts.vectorstore.embeddings_utils import EMBEDDING_MODEL_NAME, get_embedding_model

logger = get_logger(__name__)

# Stop words multilingues (français, anglais, allemand)
STOP_WORDS = {
    # Français
    "de", "et", "des", "la", "les", "le", "un", "une", "pour", "en", "dans", "sur", "avec", "par",
    "est", "sont", "être", "avoir", "a", "ont", "ce", "cette", "ces", "son", "sa", "ses", "leur",
    "leurs", "du", "au", "aux", "il", "elle", "ils", "elles", "nous", "vous", "ils", "elles",
    "qui", "que", "quoi", "où", "quand", "comment", "pourquoi", "mais", "ou", "donc", "car",
    "ne", "pas", "plus", "très", "tout", "tous", "toute", "toutes", "bien", "mal", "peu", "beaucoup",
    # Anglais
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by",
    "from", "up", "about", "into", "through", "during", "including", "against", "among", "throughout",
    "despite", "towards", "upon", "concerning", "to", "of", "in", "for", "on", "with", "at", "by",
    "from", "up", "about", "into", "through", "during", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "having", "do", "does", "did", "doing", "will", "would", "should",
    "could", "may", "might", "must", "can", "this", "that", "these", "those", "i", "you", "he", "she",
    "it", "we", "they", "me", "him", "her", "us", "them", "my", "your", "his", "her", "its", "our",
    "their", "mine", "yours", "hers", "ours", "theirs",
    # Allemand
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer", "eines", "einem", "einen",
    "und", "oder", "aber", "in", "auf", "für", "mit", "von", "zu", "bei", "über", "unter", "durch",
    "ist", "sind", "war", "waren", "sein", "haben", "hat", "hatte", "hatten", "wird", "werden",
    "wurde", "wurden", "kann", "können", "konnte", "konnten", "muss", "müssen", "musste", "mussten",
    "soll", "sollen", "sollte", "sollten", "darf", "dürfen", "durfte", "durften", "will", "wollen",
    "wollte", "wollten", "ich", "du", "er", "sie", "es", "wir", "ihr", "sie", "mich", "dich",
    "ihn", "ihr", "es", "uns", "euch", "sie", "mein", "dein", "sein", "ihr", "unser", "euer",
    # Mots courts génériques
    "à", "ça", "si", "ni", "se", "te", "me", "je", "tu", "il", "on", "nous", "vous", "ils",
    "elle", "elles", "ce", "c", "d", "l", "m", "n", "s", "t", "y", "z",
    # Nombres et caractères spéciaux
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
}

# Mots à exclure (trop courts ou non informatifs)
MIN_WORD_LENGTH = 2

# Paramètres de configuration pour la pertinence des topics
MIN_SIGNIFICANT_KEYWORDS = 3  # Nombre minimum de keywords significatifs
MAX_STOP_WORDS_RATIO = 0.3  # Ratio maximum de stop words dans les top keywords


def filter_stop_words(keywords: List[Tuple[str, float]], max_keywords: int = 10) -> List[Tuple[str, float]]:
    """
    Filter stop words from topic keywords.
    
    Args:
        keywords: List of (word, score) tuples from BERTopic
        max_keywords: Maximum number of keywords to return after filtering
        
    Returns:
        Filtered list of (word, score) tuples without stop words
    """
    filtered = []
    for word, score in keywords:
        # Normalize word (lowercase, strip)
        word_normalized = word.lower().strip()
        
        # Skip if too short
        if len(word_normalized) < MIN_WORD_LENGTH:
            continue
        
        # Skip if it's a stop word
        if word_normalized in STOP_WORDS:
            continue
        
        # Skip if it's only digits or special characters
        if re.match(r'^[\d\W]+$', word_normalized):
            continue
        
        filtered.append((word, score))
    
    # Return top N keywords after filtering
    return filtered[:max_keywords]


def generate_topic_name(keywords: List[Tuple[str, float]], topic_id: int) -> str:
    """
    Generate a descriptive topic name from filtered keywords.
    
    Args:
        keywords: List of (word, score) tuples (already filtered from stop words)
        topic_id: Topic ID number
        
    Returns:
        Descriptive topic name (e.g., "Sécurité cybersécurité protection" instead of "6_des_de_les_et")
    """
    if not keywords:
        return f"Topic {topic_id}"
    
    # Take top 3-5 keywords for the name
    top_keywords = [word for word, _ in keywords[:5]]
    
    # Join with underscores for consistency with BERTopic format
    # But use meaningful words only
    name = "_".join(top_keywords)
    
    # Fallback if name is too short
    if len(name) < 5:
        return f"Topic {topic_id}"
    
    return name


def is_topic_relevant(keywords: List[Tuple[str, float]], all_keywords: List[Tuple[str, float]]) -> Tuple[bool, float]:
    """
    Check if a topic is relevant by analyzing its keywords.
    
    Args:
        keywords: Filtered keywords (without stop words)
        all_keywords: All keywords from BERTopic (including stop words)
        
    Returns:
        Tuple of (is_relevant, stop_words_ratio)
    """
    if not all_keywords:
        return False, 1.0
    
    # Count stop words in top keywords
    top_n = min(10, len(all_keywords))
    top_keywords = all_keywords[:top_n]
    
    stop_words_count = 0
    for word, _ in top_keywords:
        word_normalized = word.lower().strip()
        if word_normalized in STOP_WORDS or len(word_normalized) < MIN_WORD_LENGTH:
            stop_words_count += 1
    
    stop_words_ratio = stop_words_count / top_n if top_n > 0 else 1.0
    
    # Check if topic has enough significant keywords
    significant_keywords_count = len(keywords)
    
    # Topic is relevant if:
    # 1. Has at least MIN_SIGNIFICANT_KEYWORDS significant keywords
    # 2. Stop words ratio is below MAX_STOP_WORDS_RATIO
    is_relevant = (
        significant_keywords_count >= MIN_SIGNIFICANT_KEYWORDS and
        stop_words_ratio <= MAX_STOP_WORDS_RATIO
    )
    
    return is_relevant, stop_words_ratio

# Default visualization output path
DEFAULT_VISUALIZATIONS_PATH = Path("/mnt/user-data/outputs/visualizations")
# Fallback to local path if default doesn't exist
LOCAL_VISUALIZATIONS_PATH = Path("outputs/visualizations")


def get_visualizations_path() -> Path:
    """Get the visualizations output path, creating it if needed."""
    path = DEFAULT_VISUALIZATIONS_PATH if DEFAULT_VISUALIZATIONS_PATH.exists() else LOCAL_VISUALIZATIONS_PATH
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_bertopic_model(
    min_topic_size: int = 10,
    nr_topics: str | int = "auto",
    calculate_probabilities: bool = True,
    verbose: bool = True,
) -> BERTopic:
    """
    Create and configure BERTopic model with optimal hyperparameters (T119 - US7).
    
    Args:
        min_topic_size: Minimum number of articles per topic (default: 10)
        nr_topics: Number of topics or "auto" for automatic discovery (default: "auto")
        calculate_probabilities: Whether to calculate topic probabilities (default: True)
        verbose: Whether to show progress (default: True)
        
    Returns:
        Configured BERTopic model
    """
    try:
        # Use same embedding model as Qdrant for consistency
        embedding_model = get_embedding_model()
        
        # Configure UMAP for dimensionality reduction (improved parameters)
        umap_model = UMAP(
            n_neighbors=20,  # Increased from 15 for better local structure capture
            n_components=10,  # Increased from 5 for more dimensions
            min_dist=0.0,
            metric="cosine",
            random_state=42,
        )
        
        # Configure HDBSCAN for clustering (improved parameters)
        hdbscan_model = HDBSCAN(
            min_cluster_size=min_topic_size,
            min_samples=3,  # Reduced from 5 for more flexibility
            metric="euclidean",
            cluster_selection_method="eom",
            cluster_selection_epsilon=0.1,  # Allow smaller but coherent clusters
            prediction_data=True,
        )
        
        # Create BERTopic model
        topic_model = BERTopic(
            embedding_model=embedding_model,
            umap_model=umap_model,
            hdbscan_model=hdbscan_model,
            min_topic_size=min_topic_size,
            nr_topics=nr_topics,
            calculate_probabilities=calculate_probabilities,
            verbose=verbose,
        )
        
        logger.info(
            "BERTopic model created",
            min_topic_size=min_topic_size,
            nr_topics=nr_topics,
            embedding_model=EMBEDDING_MODEL_NAME,
        )
        
        return topic_model
        
    except Exception as e:
        logger.error("Failed to create BERTopic model", error=str(e))
        raise TopicModelingError(f"Failed to create BERTopic model: {e}") from e


def fit_topic_model(
    topic_model: BERTopic,
    texts: List[str],
    timestamps: Optional[List[datetime]] = None,
    embeddings: Optional[np.ndarray] = None,
) -> Tuple[List[int], List[float]]:
    """
    Fit BERTopic model on article texts.
    
    Args:
        topic_model: BERTopic model instance
        texts: List of article texts
        timestamps: Optional list of publication timestamps for temporal analysis
        embeddings: Optional pre-computed embeddings (numpy array of shape [n_texts, embedding_dim])
                    If provided, will use these instead of generating new embeddings
        
    Returns:
        Tuple of (topics, probabilities)
    """
    try:
        if not texts:
            raise TopicModelingError("No texts provided for topic modeling")
        
        if embeddings is not None:
            if len(texts) != len(embeddings):
                raise TopicModelingError(
                    f"Mismatch between texts ({len(texts)}) and embeddings ({len(embeddings)})"
                )
            logger.info(
                "Fitting BERTopic model with pre-computed embeddings",
                num_texts=len(texts),
                embedding_dim=embeddings.shape[1] if len(embeddings) > 0 else 0,
            )
        else:
            logger.info("Fitting BERTopic model", num_texts=len(texts))
        
        # Fit the model with or without pre-computed embeddings
        if embeddings is not None:
            topics, probs = topic_model.fit_transform(texts, embeddings=embeddings)
        else:
            topics, probs = topic_model.fit_transform(texts)
        
        logger.info(
            "BERTopic model fitted",
            num_topics=len(set(topics)) - (1 if -1 in topics else 0),  # Exclude noise topic -1
            num_texts=len(texts),
            used_precomputed_embeddings=embeddings is not None,
        )
        
        return topics, probs
        
    except Exception as e:
        logger.error("Failed to fit BERTopic model", error=str(e))
        raise TopicModelingError(f"Failed to fit BERTopic model: {e}") from e


def refine_topic_assignments_with_similarity(
    topic_model: BERTopic,
    texts: List[str],
    topics: List[int],
    embeddings: Optional[np.ndarray] = None,
    similarity_threshold: float = 0.7,
) -> Tuple[List[int], Dict[str, Any]]:
    """
    Refine topic assignments using semantic similarity.
    
    For each article, calculates similarity with topic centroids and reassigns
    articles that are poorly matched (low similarity with current topic but high
    similarity with another topic).
    
    Args:
        topic_model: Fitted BERTopic model
        texts: List of article texts
        topics: Current topic assignments
        embeddings: Pre-computed embeddings (optional, will generate if not provided)
        similarity_threshold: Minimum similarity to consider reassignment (default: 0.7)
        
    Returns:
        Tuple of (refined_topics, statistics_dict)
    """
    try:
        if not texts or not topics:
            logger.warning("No texts or topics provided for refinement")
            return topics, {"reassigned": 0, "total": len(topics)}
        
        # Get embeddings if not provided
        if embeddings is None:
            embedding_model = get_embedding_model()
            embeddings = embedding_model.encode(texts, normalize_embeddings=True)
        
        embeddings = np.array(embeddings)
        
        # Calculate topic centroids (mean embedding per topic)
        topic_centroids = {}
        topic_counts = {}
        
        for topic_id in set(topics):
            if topic_id == -1:  # Skip noise topic
                continue
            
            topic_indices = [i for i, t in enumerate(topics) if t == topic_id]
            if topic_indices:
                topic_embeddings = embeddings[topic_indices]
                topic_centroids[topic_id] = np.mean(topic_embeddings, axis=0)
                topic_counts[topic_id] = len(topic_indices)
        
        if not topic_centroids:
            logger.warning("No valid topics found for refinement")
            return topics, {"reassigned": 0, "total": len(topics)}
        
        # Refine assignments
        refined_topics = topics.copy()
        reassigned_count = 0
        
        for i, (text, current_topic, embedding) in enumerate(zip(texts, topics, embeddings)):
            if current_topic == -1:  # Skip noise topic
                continue
            
            # Calculate similarity with current topic centroid
            if current_topic in topic_centroids:
                current_centroid = topic_centroids[current_topic]
                current_similarity = np.dot(embedding, current_centroid) / (
                    np.linalg.norm(embedding) * np.linalg.norm(current_centroid)
                )
            else:
                current_similarity = 0.0
            
            # Find best matching topic
            best_topic = current_topic
            best_similarity = current_similarity
            
            for topic_id, centroid in topic_centroids.items():
                if topic_id == current_topic:
                    continue
                
                similarity = np.dot(embedding, centroid) / (
                    np.linalg.norm(embedding) * np.linalg.norm(centroid)
                )
                
                if similarity > best_similarity and similarity >= similarity_threshold:
                    best_topic = topic_id
                    best_similarity = similarity
            
            # Reassign if better match found
            if best_topic != current_topic:
                refined_topics[i] = best_topic
                reassigned_count += 1
        
        logger.info(
            "Topic assignments refined with similarity",
            total=len(topics),
            reassigned=reassigned_count,
            threshold=similarity_threshold,
        )
        
        return refined_topics, {
            "reassigned": reassigned_count,
            "total": len(topics),
            "threshold": similarity_threshold,
        }
        
    except Exception as e:
        logger.warning("Failed to refine topic assignments, using original", error=str(e))
        return topics, {"reassigned": 0, "total": len(topics), "error": str(e)}


def get_topic_info(
    topic_model: BERTopic,
    min_keywords_significatifs: int = MIN_SIGNIFICANT_KEYWORDS,
    max_stop_words_ratio: float = MAX_STOP_WORDS_RATIO,
) -> Dict[str, Any]:
    """
    Extract topic information from fitted model with improved relevance filtering.
    
    Args:
        topic_model: Fitted BERTopic model
        min_keywords_significatifs: Minimum number of significant keywords (default: 3)
        max_stop_words_ratio: Maximum ratio of stop words in top keywords (default: 0.3)
        
    Returns:
        Dictionary with topic information (only relevant topics)
    """
    try:
        topic_info_df = topic_model.get_topic_info()
        
        # Convert to dictionary format with filtering
        topics_dict = {}
        excluded_count = 0
        
        for _, row in topic_info_df.iterrows():
            topic_id = int(row["Topic"])
            if topic_id == -1:  # Skip noise topic
                continue
            
            # Get all keywords from BERTopic (take more to have enough after filtering)
            all_keywords = topic_model.get_topic(topic_id)
            if not all_keywords:
                excluded_count += 1
                logger.debug(f"Topic {topic_id} excluded: no keywords")
                continue
            
            # Filter stop words (take 15-20 before filtering to have enough after)
            filtered_keywords = filter_stop_words(all_keywords, max_keywords=15)
            
            # Check if topic is relevant
            is_relevant, stop_words_ratio = is_topic_relevant(filtered_keywords, all_keywords)
            
            if not is_relevant:
                excluded_count += 1
                logger.debug(
                    f"Topic {topic_id} excluded: stop_words_ratio={stop_words_ratio:.2f}, "
                    f"significant_keywords={len(filtered_keywords)}"
                )
                continue
            
            # Generate improved topic name
            topic_name = generate_topic_name(filtered_keywords, topic_id)
            
            # Keep only top 10 filtered keywords for storage
            final_keywords = filtered_keywords[:10]
            
            topics_dict[topic_id] = {
                "topic_id": topic_id,
                "count": int(row["Count"]),
                "name": topic_name,
                "keywords": final_keywords,
            }
        
        logger.info(
            "Topic info extracted",
            total_topics=len(topic_info_df) - 1,  # Exclude noise topic
            relevant_topics=len(topics_dict),
            excluded_topics=excluded_count,
        )
        
        return topics_dict
        
    except Exception as e:
        logger.error("Failed to get topic info", error=str(e))
        raise TopicModelingError(f"Failed to get topic info: {e}") from e


def generate_topic_hierarchy(topic_model: BERTopic) -> Optional[Dict[str, Any]]:
    """
    Generate topic hierarchy (T122 - US7).
    
    Args:
        topic_model: Fitted BERTopic model
        
    Returns:
        Topic hierarchy dictionary or None if not available
    """
    try:
        # BERTopic can generate hierarchical topics
        hierarchical_topics = topic_model.hierarchical_topics(topic_model.topic_embeddings_)
        
        if hierarchical_topics is None or len(hierarchical_topics) == 0:
            logger.warning("No hierarchical topics generated")
            return None
        
        # Convert to dictionary format
        hierarchy = {
            "num_levels": len(hierarchical_topics),
            "topics": hierarchical_topics.to_dict(orient="records") if hasattr(hierarchical_topics, "to_dict") else hierarchical_topics,
        }
        
        logger.info("Topic hierarchy generated", num_levels=hierarchy["num_levels"])
        return hierarchy
        
    except Exception as e:
        logger.warning("Failed to generate topic hierarchy", error=str(e))
        # Not critical, return None
        return None


def analyze_temporal_evolution(
    topic_model: BERTopic,
    texts: List[str],
    timestamps: List[datetime],
    topics: Optional[List[int]] = None,
    evolution_topic_model: Optional[BERTopic] = None,
) -> Optional[Dict[str, Any]]:
    """
    Analyze temporal topic evolution (T120 - US7).
    
    Args:
        topic_model: Fitted BERTopic model
        texts: List of article texts
        timestamps: List of publication timestamps
        topics: List of topic assignments (optional, uses model.topics_ if not provided)
        evolution_topic_model: Optional separate model for evolution analysis
        
    Returns:
        Dictionary with topics over time or None if not available
    """
    try:
        if not timestamps or len(timestamps) != len(texts):
            logger.warning("Timestamps not provided or mismatch, skipping temporal analysis")
            return None
        
        # Use evolution model if provided, otherwise use main model
        model = evolution_topic_model if evolution_topic_model else topic_model
        
        # Get topics if not provided
        if topics is None:
            topics = model.topics_ if hasattr(model, "topics_") else None
        
        if topics is None or len(topics) != len(texts):
            logger.warning("Topics not available or mismatch, skipping temporal analysis")
            return None
        
        # Analyze topics over time
        topics_over_time = model.topics_over_time(
            texts,
            timestamps,
            topics=topics,
            evolution_tuning=True,
            nr_bins=20,  # Number of time bins
        )
        
        if topics_over_time is None or len(topics_over_time) == 0:
            logger.warning("No temporal evolution data generated")
            return None
        
        # Convert to dictionary format
        evolution_dict = {
            "num_bins": 20,
            "data": topics_over_time.to_dict(orient="records") if hasattr(topics_over_time, "to_dict") else topics_over_time,
        }
        
        logger.info("Temporal evolution analyzed", num_bins=evolution_dict["num_bins"])
        return evolution_dict
        
    except Exception as e:
        logger.warning("Failed to analyze temporal evolution", error=str(e))
        # Not critical, return None
        return None


def detect_emerging_topics(
    current_topics: Dict[str, Any],
    previous_topics: Optional[Dict[str, Any]],
    threshold_growth: float = 0.5,
) -> List[Dict[str, Any]]:
    """
    Detect emerging topics by comparing time windows (T121 - US7).
    
    Args:
        current_topics: Current time window topics
        previous_topics: Previous time window topics (optional)
        threshold_growth: Minimum growth rate to consider a topic emerging (default: 0.5)
        
    Returns:
        List of emerging topics with growth metrics
    """
    if previous_topics is None:
        logger.info("No previous topics for comparison, all current topics considered new")
        return [
            {
                "topic_id": topic_id,
                "growth_rate": 1.0,
                "is_emerging": True,
                **topic_data,
            }
            for topic_id, topic_data in current_topics.items()
        ]
    
    emerging_topics = []
    
    for topic_id, current_topic in current_topics.items():
        current_count = current_topic.get("count", 0)
        
        # Check if topic existed in previous window
        if topic_id in previous_topics:
            previous_count = previous_topics[topic_id].get("count", 0)
            
            if previous_count > 0:
                growth_rate = (current_count - previous_count) / previous_count
                
                if growth_rate >= threshold_growth:
                    emerging_topics.append({
                        "topic_id": topic_id,
                        "growth_rate": growth_rate,
                        "is_emerging": True,
                        "previous_count": previous_count,
                        "current_count": current_count,
                        **current_topic,
                    })
        else:
            # New topic - use a large finite number instead of infinity for JSON serialization
            emerging_topics.append({
                "topic_id": topic_id,
                "growth_rate": 999999.0,  # New topic (use large finite number instead of inf)
                "is_emerging": True,
                "previous_count": 0,
                "current_count": current_count,
                **current_topic,
            })
    
    logger.info(
        "Emerging topics detected",
        num_emerging=len(emerging_topics),
        threshold_growth=threshold_growth,
    )
    
    return emerging_topics


def generate_visualizations(
    topic_model: BERTopic,
    output_path: Optional[Path] = None,
    topics_over_time_data: Optional[Any] = None,
) -> Dict[str, str]:
    """
    Generate BERTopic visualizations (T123, T124 - US7).
    
    Args:
        topic_model: Fitted BERTopic model
        output_path: Output directory for visualizations (optional)
        topics_over_time: Topics over time data for evolution visualization (optional)
        
    Returns:
        Dictionary mapping visualization type to file path
    """
    try:
        if output_path is None:
            output_path = get_visualizations_path()
        
        visualizations = {}
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        
        # 1. Topics 2D visualization
        try:
            fig_2d = topic_model.visualize_topics()
            path_2d = output_path / f"topics_2d_{timestamp}.html"
            fig_2d.write_html(str(path_2d))
            visualizations["topics_2d"] = str(path_2d)
            logger.info("Topics 2D visualization generated", path=str(path_2d))
        except Exception as e:
            logger.warning("Failed to generate 2D visualization", error=str(e))
        
        # 2. Barchart visualization
        try:
            fig_barchart = topic_model.visualize_barchart()
            path_barchart = output_path / f"topics_barchart_{timestamp}.html"
            fig_barchart.write_html(str(path_barchart))
            visualizations["barchart"] = str(path_barchart)
            logger.info("Barchart visualization generated", path=str(path_barchart))
        except Exception as e:
            logger.warning("Failed to generate barchart", error=str(e))
        
        # 3. Topics over time (if available)
        if topics_over_time_data is not None:
            try:
                # topics_over_time_data should be a DataFrame or compatible format
                fig_evolution = topic_model.visualize_topics_over_time(topics_over_time_data)
                path_evolution = output_path / f"topics_evolution_{timestamp}.html"
                fig_evolution.write_html(str(path_evolution))
                visualizations["evolution"] = str(path_evolution)
                logger.info("Evolution visualization generated", path=str(path_evolution))
            except Exception as e:
                logger.warning("Failed to generate evolution visualization", error=str(e))
        
        # 4. Heatmap (if hierarchical topics available)
        try:
            hierarchical_topics = topic_model.hierarchical_topics(topic_model.topic_embeddings_)
            if hierarchical_topics is not None and len(hierarchical_topics) > 0:
                fig_heatmap = topic_model.visualize_hierarchy(hierarchical_topics=hierarchical_topics)
                path_heatmap = output_path / f"topics_heatmap_{timestamp}.html"
                fig_heatmap.write_html(str(path_heatmap))
                visualizations["heatmap"] = str(path_heatmap)
                logger.info("Heatmap visualization generated", path=str(path_heatmap))
        except Exception as e:
            logger.debug("Heatmap not available or failed", error=str(e))
        
        logger.info(
            "Visualizations generated",
            count=len(visualizations),
            output_path=str(output_path),
        )
        
        return visualizations
        
    except Exception as e:
        logger.error("Failed to generate visualizations", error=str(e))
        raise TopicModelingError(f"Failed to generate visualizations: {e}") from e

