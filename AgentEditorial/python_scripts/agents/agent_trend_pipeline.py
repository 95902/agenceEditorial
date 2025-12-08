"""Trend Pipeline Agent - Orchestrates the 4-stage hybrid trend extraction pipeline."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.agents.base_agent import BaseAgent
from python_scripts.analysis.clustering import BertopicClusterer, ClusteringConfig, EmbeddingFetcher, OutlierHandler, TopicLabeler
from python_scripts.analysis.temporal import TemporalAnalyzer, TemporalConfig
from python_scripts.analysis.llm_enrichment import LLMEnricher, LLMEnrichmentConfig
from python_scripts.analysis.gap_analysis import GapAnalyzer, GapAnalysisConfig
from python_scripts.database.crud_clusters import (
    create_topic_clusters_batch,
    create_topic_outliers_batch,
)
from python_scripts.database.models import TrendPipelineExecution
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


class TrendPipelineAgent(BaseAgent):
    """
    Orchestrator for the 4-stage trend extraction pipeline.
    
    Stages:
    1. Clustering (BERTopic + HDBSCAN)
    2. Temporal Analysis
    3. LLM Validation & Enrichment
    4. Gap Analysis
    """
    
    def __init__(
        self,
        db_session: AsyncSession,
        clustering_config: Optional[ClusteringConfig] = None,
        temporal_config: Optional[TemporalConfig] = None,
        llm_config: Optional[LLMEnrichmentConfig] = None,
        gap_config: Optional[GapAnalysisConfig] = None,
    ):
        """
        Initialize the trend pipeline agent.
        
        Args:
            db_session: Database session
            clustering_config: Clustering configuration
            temporal_config: Temporal analysis configuration
            llm_config: LLM enrichment configuration
            gap_config: Gap analysis configuration
        """
        super().__init__(agent_name="trend_pipeline")
        self.db_session = db_session
        
        # Initialize configs
        self.clustering_config = clustering_config or ClusteringConfig.default()
        self.temporal_config = temporal_config or TemporalConfig.default()
        self.llm_config = llm_config or LLMEnrichmentConfig.default()
        self.gap_config = gap_config or GapAnalysisConfig.default()
        
        # Initialize analyzers
        self._clusterer = BertopicClusterer(self.clustering_config)
        self._embedding_fetcher = EmbeddingFetcher(self.clustering_config)
        self._outlier_handler = OutlierHandler(self.clustering_config)
        self._topic_labeler = TopicLabeler(self.clustering_config)
        self._temporal_analyzer = TemporalAnalyzer(self.temporal_config)
        self._llm_enricher = LLMEnricher(self.llm_config)
        self._gap_analyzer = GapAnalyzer(self.gap_config)
    
    async def execute(
        self,
        domains: List[str],
        client_domain: Optional[str] = None,
        time_window_days: int = 365,
        skip_llm: bool = False,
        skip_gap_analysis: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute the full 4-stage pipeline.
        
        Args:
            domains: List of domains to analyze
            client_domain: Client domain for gap analysis
            time_window_days: Time window in days
            skip_llm: Skip LLM enrichment stage
            skip_gap_analysis: Skip gap analysis stage
            
        Returns:
            Pipeline execution results
        """
        execution_id = str(uuid4())
        start_time = datetime.now(timezone.utc)
        
        logger.info(
            "Starting trend pipeline",
            execution_id=execution_id,
            domains=domains,
            client_domain=client_domain,
        )
        
        # Create execution record
        execution = TrendPipelineExecution(
            execution_id=execution_id,
            client_domain=client_domain,
            domains_analyzed={"domains": domains},
            time_window_days=time_window_days,
        )
        self.db_session.add(execution)
        await self.db_session.commit()
        
        results = {
            "execution_id": execution_id,
            "stages": {},
            "success": True,
        }
        
        try:
            # STAGE 1: Clustering
            logger.info("Starting Stage 1: Clustering")
            execution.stage_1_clustering_status = "in_progress"
            await self.db_session.commit()
            
            stage1_result = await self._execute_stage_1_clustering(
                domains=domains,
                time_window_days=time_window_days,
            )
            
            results["stages"]["clustering"] = stage1_result
            
            if not stage1_result.get("success"):
                execution.stage_1_clustering_status = "failed"
                execution.error_message = stage1_result.get("error")
                await self.db_session.commit()
                results["success"] = False
                return results
            
            execution.stage_1_clustering_status = "completed"
            execution.total_clusters = len(stage1_result.get("clusters", []))
            execution.total_outliers = len(stage1_result.get("outliers", []))
            execution.total_articles = stage1_result.get("total_articles", 0)
            await self.db_session.commit()
            
            # Save clusters to database
            if stage1_result.get("clusters"):
                await create_topic_clusters_batch(
                    self.db_session,
                    analysis_id=execution.id,
                    clusters_data=stage1_result["clusters"],
                )
            
            if stage1_result.get("outliers"):
                await create_topic_outliers_batch(
                    self.db_session,
                    analysis_id=execution.id,
                    outliers_data=stage1_result["outliers"],
                )
            
            # STAGE 2: Temporal Analysis
            logger.info("Starting Stage 2: Temporal Analysis")
            execution.stage_2_temporal_status = "in_progress"
            await self.db_session.commit()
            
            stage2_result = await self._execute_stage_2_temporal(
                clusters=stage1_result["clusters"],
                documents=stage1_result.get("documents", []),
                topics=stage1_result.get("topics", []),
                embeddings=stage1_result.get("embeddings"),
                centroids=stage1_result.get("centroids"),
            )
            
            results["stages"]["temporal"] = stage2_result
            execution.stage_2_temporal_status = "completed"
            await self.db_session.commit()
            
            # STAGE 3: LLM Enrichment
            if not skip_llm:
                logger.info("Starting Stage 3: LLM Enrichment")
                execution.stage_3_llm_status = "in_progress"
                await self.db_session.commit()
                
                stage3_result = await self._execute_stage_3_llm(
                    clusters=stage1_result["clusters"],
                    temporal_metrics=stage2_result.get("metrics", []),
                    outliers=stage1_result.get("outliers", []),
                    texts=stage1_result.get("texts", []),
                )
                
                results["stages"]["llm_enrichment"] = stage3_result
                execution.stage_3_llm_status = "completed"
                execution.total_recommendations = len(stage3_result.get("recommendations", []))
                await self.db_session.commit()
            else:
                execution.stage_3_llm_status = "skipped"
                await self.db_session.commit()
            
            # STAGE 4: Gap Analysis
            if not skip_gap_analysis and client_domain:
                logger.info("Starting Stage 4: Gap Analysis")
                execution.stage_4_gap_status = "in_progress"
                await self.db_session.commit()
                
                stage4_result = await self._execute_stage_4_gap_analysis(
                    client_domain=client_domain,
                    clusters=stage1_result["clusters"],
                    documents=stage1_result.get("documents", []),
                    topics=stage1_result.get("topics", []),
                    temporal_metrics=stage2_result.get("metrics", []),
                    recommendations=results["stages"].get("llm_enrichment", {}).get("recommendations", []),
                )
                
                results["stages"]["gap_analysis"] = stage4_result
                execution.stage_4_gap_status = "completed"
                execution.total_gaps = len(stage4_result.get("gaps", []))
                await self.db_session.commit()
            else:
                execution.stage_4_gap_status = "skipped"
                await self.db_session.commit()
            
            # Finalize
            end_time = datetime.now(timezone.utc)
            execution.end_time = end_time
            execution.duration_seconds = int((end_time - start_time).total_seconds())
            await self.db_session.commit()
            
            results["duration_seconds"] = execution.duration_seconds
            
            logger.info(
                "Trend pipeline completed",
                execution_id=execution_id,
                duration=execution.duration_seconds,
                clusters=execution.total_clusters,
                gaps=execution.total_gaps,
            )
            
            return results
            
        except Exception as e:
            logger.error("Pipeline failed", error=str(e))
            execution.error_message = str(e)
            await self.db_session.commit()
            
            results["success"] = False
            results["error"] = str(e)
            return results
    
    async def _execute_stage_1_clustering(
        self,
        domains: List[str],
        time_window_days: int,
    ) -> Dict[str, Any]:
        """Execute Stage 1: Clustering."""
        # Fetch embeddings from Qdrant
        embeddings, metadata, document_ids = self._embedding_fetcher.fetch_embeddings(
            domains=domains,
            max_age_days=time_window_days,
        )
        
        if len(embeddings) < self.clustering_config.min_articles:
            return {
                "success": False,
                "error": f"Not enough articles ({len(embeddings)}). Minimum: {self.clustering_config.min_articles}",
            }
        
        # Extract texts for clustering
        texts = [m.get("content_text", m.get("title", "")) for m in metadata]
        
        # Run clustering
        cluster_result = self._clusterer.cluster(
            texts=texts,
            embeddings=embeddings,
            metadata=metadata,
        )
        
        if not cluster_result.get("success"):
            return cluster_result
        
        # Generate labels
        clusters = self._topic_labeler.generate_labels(cluster_result["clusters"])
        clusters = self._topic_labeler.calculate_coherence_scores(
            clusters,
            embeddings=embeddings,
            topics=cluster_result["topics"],
        )
        
        # Prepare clusters for database
        for cluster in clusters:
            cluster["document_ids"] = {
                "indices": cluster.get("document_indices", []),
                "ids": [document_ids[i] for i in cluster.get("document_indices", []) if i < len(document_ids)],
            }
            cluster["top_terms"] = {"terms": cluster.get("top_terms", [])}
        
        # Process outliers
        outliers = self._outlier_handler.extract_outliers(
            topics=cluster_result["topics"],
            metadata=metadata,
            document_ids=document_ids,
            embeddings=embeddings,
            centroids=cluster_result.get("centroids"),
        )
        
        # Categorize outliers
        self._outlier_handler.categorize_outliers(outliers, texts)
        
        # Prepare outliers for database
        for outlier in outliers:
            outlier["embedding_distance"] = outlier.get("distance_to_nearest")
        
        # Prepare documents with index
        documents = []
        for i, (meta, doc_id) in enumerate(zip(metadata, document_ids)):
            doc = dict(meta)
            doc["index"] = i
            doc["document_id"] = doc_id
            documents.append(doc)
        
        return {
            "success": True,
            "clusters": clusters,
            "outliers": outliers,
            "topics": cluster_result["topics"],
            "embeddings": embeddings,
            "centroids": cluster_result.get("centroids"),
            "documents": documents,
            "texts": texts,
            "total_articles": len(embeddings),
        }
    
    async def _execute_stage_2_temporal(
        self,
        clusters: List[Dict[str, Any]],
        documents: List[Dict[str, Any]],
        topics: List[int],
        embeddings: Optional[np.ndarray],
        centroids: Optional[Dict[int, np.ndarray]],
    ) -> Dict[str, Any]:
        """Execute Stage 2: Temporal Analysis."""
        # Group documents by topic
        documents_by_topic = {}
        for doc, topic_id in zip(documents, topics):
            if topic_id < 0:
                continue
            if topic_id not in documents_by_topic:
                documents_by_topic[topic_id] = []
            documents_by_topic[topic_id].append(doc)
        
        # Analyze temporal metrics
        metrics = self._temporal_analyzer.analyze_all_topics(
            clusters=clusters,
            documents_by_topic=documents_by_topic,
            centroids=centroids,
            embeddings=embeddings,
        )
        
        # Detect topics over time
        topics_over_time = self._temporal_analyzer.detect_topics_over_time(
            documents=documents,
            topics=topics,
        )
        
        return {
            "success": True,
            "metrics": metrics,
            "topics_over_time": topics_over_time,
        }
    
    async def _execute_stage_3_llm(
        self,
        clusters: List[Dict[str, Any]],
        temporal_metrics: List[Dict[str, Any]],
        outliers: List[Dict[str, Any]],
        texts: List[str],
    ) -> Dict[str, Any]:
        """Execute Stage 3: LLM Enrichment."""
        # Build temporal lookup
        temporal_lookup = {m["topic_id"]: m for m in temporal_metrics}
        
        syntheses = []
        recommendations = []
        
        # Process top topics by potential score
        top_topics = sorted(
            temporal_metrics,
            key=lambda x: x.get("potential_score", 0),
            reverse=True,
        )[:10]
        
        for metrics in top_topics:
            topic_id = metrics["topic_id"]
            
            # Find cluster
            cluster = next((c for c in clusters if c["topic_id"] == topic_id), None)
            if not cluster:
                continue
            
            # Extract keywords
            keywords = [t["word"] for t in cluster.get("top_terms", {}).get("terms", [])[:10]]
            
            # Get representative docs
            doc_indices = cluster.get("document_ids", {}).get("indices", [])[:3]
            rep_docs = [texts[i] for i in doc_indices if i < len(texts)]
            
            try:
                # Generate synthesis
                synthesis = await self._llm_enricher.synthesize_trend(
                    topic_label=cluster["label"],
                    keywords=keywords,
                    volume=cluster["size"],
                    time_period=365,
                    velocity=metrics.get("velocity", 1.0),
                    velocity_trend=metrics.get("velocity_trend", "stable"),
                    source_diversity=metrics.get("source_diversity", 1),
                    representative_docs=rep_docs,
                )
                
                synthesis["topic_id"] = topic_id
                syntheses.append(synthesis)
                
                # Generate article angles
                angles = await self._llm_enricher.generate_article_angles(
                    topic_label=cluster["label"],
                    keywords=keywords,
                    saturated_angles=synthesis.get("saturated_angles", []),
                    opportunities=synthesis.get("opportunities", []),
                    num_angles=3,
                )
                
                for angle in angles:
                    angle["topic_cluster_id"] = topic_id
                    recommendations.append(angle)
                    
            except Exception as e:
                logger.warning(f"LLM enrichment failed for topic {topic_id}", error=str(e))
        
        # Analyze outliers for weak signals
        weak_signal_analysis = None
        if outliers:
            try:
                weak_signal_analysis = await self._llm_enricher.analyze_outliers(
                    outliers=outliers,
                    texts=texts,
                )
            except Exception as e:
                logger.warning("Outlier analysis failed", error=str(e))
        
        return {
            "success": True,
            "syntheses": syntheses,
            "recommendations": recommendations,
            "weak_signal_analysis": weak_signal_analysis,
        }
    
    async def _execute_stage_4_gap_analysis(
        self,
        client_domain: str,
        clusters: List[Dict[str, Any]],
        documents: List[Dict[str, Any]],
        topics: List[int],
        temporal_metrics: List[Dict[str, Any]],
        recommendations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Execute Stage 4: Gap Analysis."""
        # Group documents by topic
        documents_by_topic = {}
        for doc, topic_id in zip(documents, topics):
            if topic_id < 0:
                continue
            if topic_id not in documents_by_topic:
                documents_by_topic[topic_id] = []
            documents_by_topic[topic_id].append(doc)
        
        # Analyze coverage
        coverage = self._gap_analyzer.analyze_coverage(
            client_domain=client_domain,
            clusters=clusters,
            documents_by_topic=documents_by_topic,
        )
        
        # Identify gaps
        gaps = self._gap_analyzer.identify_gaps(
            coverage_results=coverage,
            temporal_metrics=temporal_metrics,
        )
        
        # Identify strengths
        strengths = self._gap_analyzer.identify_strengths(coverage)
        
        # Build roadmap
        roadmap = self._gap_analyzer.build_roadmap(
            gaps=gaps,
            recommendations=recommendations,
        )
        
        return {
            "success": True,
            "coverage": coverage,
            "gaps": gaps,
            "strengths": strengths,
            "roadmap": roadmap,
        }

