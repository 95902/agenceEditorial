"""Main temporal analyzer (ETAGE 2)."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import numpy as np

from python_scripts.analysis.temporal.config import TemporalConfig
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


class TemporalAnalyzer:
    """Analyze temporal dynamics of topics."""
    
    def __init__(self, config: Optional[TemporalConfig] = None):
        """
        Initialize the temporal analyzer.
        
        Args:
            config: Temporal analysis configuration
        """
        self.config = config or TemporalConfig.default()
    
    def analyze_topic(
        self,
        topic_id: int,
        documents: List[Dict[str, Any]],
        centroids: Optional[Dict[int, np.ndarray]] = None,
        embeddings: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        """
        Analyze temporal metrics for a single topic.
        
        Args:
            topic_id: Topic ID
            documents: Documents in this topic with timestamps
            centroids: Topic centroids (optional)
            embeddings: Document embeddings (optional)
            
        Returns:
            Temporal metrics dictionary
        """
        if not documents:
            return self._empty_metrics(topic_id)
        
        now = datetime.now(timezone.utc)
        
        # Extract timestamps
        timestamps = []
        for doc in documents:
            ts = doc.get("published_date") or doc.get("created_at")
            if ts:
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except ValueError:
                        continue
                timestamps.append(ts)
        
        if not timestamps:
            return self._empty_metrics(topic_id)
        
        # Calculate metrics for each window
        metrics_by_window = {}
        total_count = len(timestamps)
        
        for window in self.config.windows:
            cutoff = now - timedelta(days=window.days)
            window_count = sum(1 for ts in timestamps if ts >= cutoff)
            
            metrics_by_window[window.name] = {
                "volume": window_count,
                "ratio": window_count / total_count if total_count > 0 else 0,
            }
        
        # Calculate velocity (7d vs 30d rate)
        vol_7d = metrics_by_window.get("7d", {}).get("volume", 0)
        vol_30d = metrics_by_window.get("30d", {}).get("volume", 0)
        
        if vol_30d > 0 and vol_7d > 0:
            rate_7d = vol_7d / 7
            rate_30d = vol_30d / 30
            velocity = rate_7d / rate_30d if rate_30d > 0 else 1.0
        else:
            velocity = 1.0
        
        # Calculate freshness
        freshness_ratio = metrics_by_window.get("7d", {}).get("ratio", 0)
        
        # Calculate source diversity
        domains = set()
        for doc in documents:
            domain = doc.get("domain")
            if domain:
                domains.add(domain)
        source_diversity = len(domains)
        
        # Calculate cohesion score if embeddings available
        cohesion_score = self._calculate_cohesion(
            topic_id, documents, embeddings
        ) if embeddings is not None else None
        
        # Check for drift if centroids available
        drift_detected = False
        drift_distance = None
        if self.config.drift_detection_enabled and centroids and embeddings is not None:
            drift_result = self._detect_drift(
                topic_id, documents, centroids, embeddings
            )
            drift_detected = drift_result.get("detected", False)
            drift_distance = drift_result.get("distance")
        
        # Calculate potential score
        potential_score = self._calculate_potential_score(
            velocity=velocity,
            freshness_ratio=freshness_ratio,
            source_diversity=source_diversity,
            cohesion_score=cohesion_score,
            total_count=total_count,
        )
        
        return {
            "topic_id": topic_id,
            "total_count": total_count,
            "metrics_by_window": metrics_by_window,
            "velocity": velocity,
            "velocity_trend": self._classify_velocity(velocity),
            "freshness_ratio": freshness_ratio,
            "freshness_trend": self._classify_freshness(freshness_ratio),
            "source_diversity": source_diversity,
            "diversity_level": self._classify_diversity(source_diversity),
            "cohesion_score": cohesion_score,
            "drift_detected": drift_detected,
            "drift_distance": drift_distance,
            "potential_score": potential_score,
        }
    
    def analyze_all_topics(
        self,
        clusters: List[Dict[str, Any]],
        documents_by_topic: Dict[int, List[Dict[str, Any]]],
        centroids: Optional[Dict[int, np.ndarray]] = None,
        embeddings: Optional[np.ndarray] = None,
    ) -> List[Dict[str, Any]]:
        """
        Analyze temporal metrics for all topics.
        
        Args:
            clusters: List of cluster dictionaries
            documents_by_topic: Documents grouped by topic ID
            centroids: Topic centroids (optional)
            embeddings: Document embeddings (optional)
            
        Returns:
            List of temporal metrics for each topic
        """
        results = []
        
        for cluster in clusters:
            topic_id = cluster["topic_id"]
            documents = documents_by_topic.get(topic_id, [])
            
            metrics = self.analyze_topic(
                topic_id=topic_id,
                documents=documents,
                centroids=centroids,
                embeddings=embeddings,
            )
            
            results.append(metrics)
        
        # Sort by potential score
        results.sort(key=lambda x: x.get("potential_score", 0), reverse=True)
        
        logger.info(
            "Analyzed temporal metrics",
            topics=len(results),
            top_potential=results[0]["potential_score"] if results else 0,
        )
        
        return results
    
    def detect_topics_over_time(
        self,
        documents: List[Dict[str, Any]],
        topics: List[int],
        num_bins: int = 20,
    ) -> Dict[str, Any]:
        """
        Analyze topic evolution over time bins.
        
        Args:
            documents: All documents with timestamps
            topics: Topic assignments
            num_bins: Number of time bins
            
        Returns:
            Topics over time data
        """
        if not documents or not topics:
            return {"bins": [], "data": {}}
        
        # Get timestamp range
        timestamps = []
        for doc in documents:
            ts = doc.get("published_date") or doc.get("created_at")
            if ts:
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except ValueError:
                        continue
                timestamps.append(ts)
        
        if not timestamps:
            return {"bins": [], "data": {}}
        
        min_ts = min(timestamps)
        max_ts = max(timestamps)
        
        # Create bins
        time_range = (max_ts - min_ts).total_seconds()
        bin_size = time_range / num_bins
        
        bins = []
        for i in range(num_bins):
            bin_start = min_ts + timedelta(seconds=i * bin_size)
            bin_end = min_ts + timedelta(seconds=(i + 1) * bin_size)
            bins.append({
                "index": i,
                "start": bin_start.isoformat(),
                "end": bin_end.isoformat(),
            })
        
        # Count topics per bin
        topic_ids = set(t for t in topics if t >= 0)
        data = {tid: [0] * num_bins for tid in topic_ids}
        
        for doc, topic, ts in zip(documents, topics, timestamps):
            if topic < 0 or ts is None:
                continue
            
            # Find bin
            bin_idx = int((ts - min_ts).total_seconds() / bin_size)
            bin_idx = min(bin_idx, num_bins - 1)
            
            if topic in data:
                data[topic][bin_idx] += 1
        
        return {
            "bins": bins,
            "data": data,
        }
    
    def _empty_metrics(self, topic_id: int) -> Dict[str, Any]:
        """Return empty metrics structure."""
        return {
            "topic_id": topic_id,
            "total_count": 0,
            "metrics_by_window": {},
            "velocity": 1.0,
            "velocity_trend": "stable",
            "freshness_ratio": 0,
            "freshness_trend": "cold",
            "source_diversity": 0,
            "diversity_level": "unknown",
            "cohesion_score": None,
            "drift_detected": False,
            "drift_distance": None,
            "potential_score": 0,
        }
    
    def _classify_velocity(self, velocity: float) -> str:
        """Classify velocity trend."""
        if velocity >= self.config.velocity_acceleration_threshold:
            return "accelerating"
        elif velocity <= self.config.velocity_deceleration_threshold:
            return "decelerating"
        return "stable"
    
    def _classify_freshness(self, ratio: float) -> str:
        """Classify freshness level."""
        if ratio >= self.config.freshness_hot_threshold:
            return "hot"
        elif ratio <= self.config.freshness_cold_threshold:
            return "cold"
        return "warm"
    
    def _classify_diversity(self, count: int) -> str:
        """Classify source diversity level."""
        if count >= self.config.diversity_mainstream_threshold:
            return "mainstream"
        elif count <= self.config.diversity_niche_threshold:
            return "niche"
        return "moderate"
    
    def _calculate_cohesion(
        self,
        topic_id: int,
        documents: List[Dict[str, Any]],
        embeddings: np.ndarray,
    ) -> Optional[float]:
        """Calculate intra-cluster cohesion."""
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            
            # Get document indices
            indices = [doc.get("index") for doc in documents if doc.get("index") is not None]
            
            if len(indices) < 2:
                return 1.0
            
            topic_embeddings = embeddings[indices]
            similarities = cosine_similarity(topic_embeddings)
            
            n = len(similarities)
            total_sim = (similarities.sum() - n) / (n * (n - 1)) if n > 1 else 1.0
            
            return float(total_sim)
            
        except Exception as e:
            logger.warning("Could not calculate cohesion", error=str(e))
            return None
    
    def _detect_drift(
        self,
        topic_id: int,
        documents: List[Dict[str, Any]],
        centroids: Dict[int, np.ndarray],
        embeddings: np.ndarray,
    ) -> Dict[str, Any]:
        """Detect semantic drift in topic."""
        try:
            if topic_id not in centroids:
                return {"detected": False}
            
            centroid = centroids[topic_id]
            now = datetime.now(timezone.utc)
            cutoff_7d = now - timedelta(days=7)
            cutoff_30d = now - timedelta(days=30)
            
            # Get recent and older documents
            recent_indices = []
            older_indices = []
            
            for doc in documents:
                idx = doc.get("index")
                ts = doc.get("published_date")
                
                if idx is None or ts is None:
                    continue
                
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except ValueError:
                        continue
                
                if ts >= cutoff_7d:
                    recent_indices.append(idx)
                elif ts >= cutoff_30d:
                    older_indices.append(idx)
            
            if len(recent_indices) < 3 or len(older_indices) < 3:
                return {"detected": False}
            
            # Calculate centroids for recent and older
            recent_centroid = np.mean(embeddings[recent_indices], axis=0)
            
            # Calculate distance
            distance = np.linalg.norm(recent_centroid - centroid)
            
            return {
                "detected": distance > self.config.drift_threshold,
                "distance": float(distance),
            }
            
        except Exception as e:
            logger.warning("Could not detect drift", error=str(e))
            return {"detected": False}
    
    def _calculate_potential_score(
        self,
        velocity: float,
        freshness_ratio: float,
        source_diversity: int,
        cohesion_score: Optional[float],
        total_count: int,
    ) -> float:
        """Calculate composite editorial potential score."""
        weights = self.config.potential_score_weights
        
        # Normalize metrics to 0-1
        velocity_score = min(velocity / 2.0, 1.0)  # Cap at 2x
        freshness_score = min(freshness_ratio / 0.5, 1.0)  # Cap at 50%
        diversity_score = min(source_diversity / 10.0, 1.0)  # Cap at 10 sources
        cohesion_normalized = cohesion_score if cohesion_score else 0.5
        size_score = min(total_count / 100.0, 1.0)  # Cap at 100 docs
        
        # Weighted sum
        score = (
            weights["velocity"] * velocity_score +
            weights["freshness"] * freshness_score +
            weights["diversity"] * diversity_score +
            weights["cohesion"] * cohesion_normalized +
            weights["size"] * size_score
        )
        
        return round(score, 4)

