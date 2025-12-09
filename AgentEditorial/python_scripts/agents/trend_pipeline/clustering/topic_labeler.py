"""Topic labeling with c-TF-IDF (ETAGE 1)."""

from typing import Any, Dict, List, Optional, Tuple

from python_scripts.agents.trend_pipeline.clustering.config import ClusteringConfig
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


class TopicLabeler:
    """Generate meaningful labels for topics."""
    
    def __init__(self, config: Optional[ClusteringConfig] = None):
        """
        Initialize the topic labeler.
        
        Args:
            config: Clustering configuration
        """
        self.config = config or ClusteringConfig.default()
        
        # Common stop words to filter
        self._stop_words = {
            "de", "la", "le", "les", "et", "en", "un", "une", "du", "des",
            "pour", "dans", "sur", "avec", "par", "est", "sont", "plus",
            "the", "a", "an", "and", "or", "of", "to", "in", "for", "on",
            "is", "are", "was", "were", "be", "been", "being", "have", "has",
        }
    
    def generate_labels(
        self,
        clusters: List[Dict[str, Any]],
        max_words: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Generate human-readable labels for clusters.
        
        Args:
            clusters: List of cluster dictionaries
            max_words: Maximum words in label
            
        Returns:
            Clusters with updated labels
        """
        for cluster in clusters:
            top_terms = cluster.get("top_terms", [])
            
            if not top_terms:
                cluster["label"] = f"Topic_{cluster['topic_id']}"
                continue
            
            # Filter stop words and select top words
            filtered_terms = [
                t["word"] for t in top_terms
                if t["word"].lower() not in self._stop_words
                and len(t["word"]) > 2
            ][:max_words]
            
            if filtered_terms:
                cluster["label"] = "_".join(filtered_terms)
            else:
                # Fallback to first terms
                cluster["label"] = "_".join([t["word"] for t in top_terms[:max_words]])
        
        return clusters
    
    def enhance_with_representative_docs(
        self,
        clusters: List[Dict[str, Any]],
        texts: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Enhance cluster information with representative documents.
        
        Args:
            clusters: List of cluster dictionaries
            texts: Document texts
            
        Returns:
            Enhanced clusters
        """
        for cluster in clusters:
            doc_indices = cluster.get("document_indices", [])
            
            if not doc_indices or not texts:
                continue
            
            # Get representative documents (first 3)
            representative_docs = []
            for idx in doc_indices[:3]:
                if idx < len(texts):
                    text = texts[idx]
                    # Truncate long texts
                    if len(text) > 500:
                        text = text[:500] + "..."
                    representative_docs.append(text)
            
            cluster["representative_docs"] = representative_docs
        
        return clusters
    
    def calculate_coherence_scores(
        self,
        clusters: List[Dict[str, Any]],
        embeddings: Optional[Any] = None,
        topics: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Calculate coherence score for each cluster.
        
        Coherence measures how semantically similar documents
        within a cluster are to each other.
        
        Args:
            clusters: List of cluster dictionaries
            embeddings: Document embeddings
            topics: Topic assignments
            
        Returns:
            Clusters with coherence scores
        """
        if embeddings is None or topics is None:
            return clusters
        
        try:
            import numpy as np
            from sklearn.metrics.pairwise import cosine_similarity
            
            for cluster in clusters:
                topic_id = cluster["topic_id"]
                
                # Get embeddings for this topic
                topic_indices = [i for i, t in enumerate(topics) if t == topic_id]
                
                if len(topic_indices) < 2:
                    cluster["coherence_score"] = 1.0
                    continue
                
                topic_embeddings = embeddings[topic_indices]
                
                # Calculate pairwise cosine similarities
                similarities = cosine_similarity(topic_embeddings)
                
                # Average similarity (excluding diagonal)
                n = len(similarities)
                total_sim = (similarities.sum() - n) / (n * (n - 1)) if n > 1 else 1.0
                
                cluster["coherence_score"] = float(total_sim)
            
            return clusters
            
        except Exception as e:
            logger.warning("Could not calculate coherence", error=str(e))
            return clusters
    
    def merge_similar_topics(
        self,
        clusters: List[Dict[str, Any]],
        similarity_threshold: float = 0.8,
    ) -> List[Dict[str, Any]]:
        """
        Suggest merging similar topics.
        
        Args:
            clusters: List of cluster dictionaries
            similarity_threshold: Threshold for suggesting merge
            
        Returns:
            Clusters with merge suggestions
        """
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            
            # Create text from top terms
            topic_texts = []
            for cluster in clusters:
                terms = [t["word"] for t in cluster.get("top_terms", [])]
                topic_texts.append(" ".join(terms))
            
            if not topic_texts:
                return clusters
            
            # Calculate TF-IDF similarity
            vectorizer = TfidfVectorizer()
            tfidf_matrix = vectorizer.fit_transform(topic_texts)
            similarities = cosine_similarity(tfidf_matrix)
            
            # Find similar pairs
            merge_suggestions = []
            for i in range(len(clusters)):
                for j in range(i + 1, len(clusters)):
                    if similarities[i, j] >= similarity_threshold:
                        merge_suggestions.append({
                            "topic_a": clusters[i]["topic_id"],
                            "topic_b": clusters[j]["topic_id"],
                            "similarity": float(similarities[i, j]),
                        })
            
            if merge_suggestions:
                logger.info(
                    "Found similar topics to merge",
                    count=len(merge_suggestions),
                )
            
            return clusters
            
        except Exception as e:
            logger.warning("Could not check for similar topics", error=str(e))
            return clusters

