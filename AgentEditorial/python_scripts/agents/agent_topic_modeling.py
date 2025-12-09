"""Topic modeling agent with BERTopic (T118 - US7)."""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.agents.base_agent import BaseAgent
from python_scripts.analysis.topic_modeling import (
    analyze_temporal_evolution,
    create_bertopic_model,
    detect_emerging_topics,
    fit_topic_model,
    generate_topic_hierarchy,
    generate_visualizations,
    get_topic_info,
    refine_topic_assignments_with_similarity,
)
from python_scripts.database.crud_articles import (
    list_competitor_articles,
    update_articles_topic_ids_batch,
)
from python_scripts.database.crud_topics import (
    create_bertopic_analysis,
    get_latest_bertopic_analysis,
)
from python_scripts.utils.logging import get_logger
from python_scripts.vectorstore.embeddings_utils import generate_embeddings_batch
from python_scripts.vectorstore.qdrant_client import qdrant_client

logger = get_logger(__name__)


class TopicModelingAgent(BaseAgent):
    """Agent for topic modeling with BERTopic."""

    def __init__(
        self,
        min_topic_size: int = 10,
        nr_topics: str | int = "auto",
    ) -> None:
        """
        Initialize the topic modeling agent.
        
        Args:
            min_topic_size: Minimum number of articles per topic
            nr_topics: Number of topics or "auto" for automatic discovery
        """
        super().__init__("topic_modeling")
        self.min_topic_size = min_topic_size
        self.nr_topics = nr_topics

    async def execute(
        self,
        execution_id: UUID,
        input_data: Dict[str, Any],
        db_session: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Execute topic modeling workflow (T118 - US7).
        
        Args:
            execution_id: Unique execution ID
            input_data: Input data containing:
                - domains: List of domains to analyze
                - time_window_days: Time window in days (optional)
                - min_topic_size: Override default min_topic_size (optional)
                - nr_topics: Override default nr_topics (optional)
            db_session: Database session
            
        Returns:
            Dictionary with analysis results
        """
        self.log_step("start", "running", "Starting topic modeling workflow")
        
        try:
            domains = input_data.get("domains", [])
            if not domains:
                raise ValueError("No domains provided for topic modeling")
            
            time_window_days = input_data.get("time_window_days", 365)  # Default 1 year
            min_topic_size = input_data.get("min_topic_size", self.min_topic_size)
            nr_topics = input_data.get("nr_topics", self.nr_topics)
            
            self.logger.info(
                "Topic modeling started",
                execution_id=str(execution_id),
                domains=domains,
                time_window_days=time_window_days,
            )
            
            # Step 1: Retrieve articles
            self.log_step("retrieve_articles", "running", "Retrieving articles from database")
            use_qdrant = input_data.get("use_qdrant_embeddings", True)
            filter_duplicates = input_data.get("filter_semantic_duplicates", True)
            min_quality = input_data.get("min_semantic_quality")
            
            articles_data = await self._retrieve_articles(
                db_session,
                domains,
                time_window_days,
                use_qdrant_embeddings=use_qdrant,
                filter_semantic_duplicates=filter_duplicates,
                min_semantic_quality=min_quality,
            )
            
            if not articles_data["texts"]:
                self.log_step("retrieve_articles", "failed", "No articles found")
                return {
                    "success": False,
                    "error": "No articles found for the specified domains and time window",
                    "statistics": {
                        "total_articles": 0,
                        "domains_analyzed": domains,
                    },
                }
            
            self.log_step(
                "retrieve_articles",
                "completed",
                f"Retrieved {len(articles_data['texts'])} articles",
            )
            
            # Step 2: Create BERTopic model
            self.log_step("create_model", "running", "Creating BERTopic model")
            topic_model = create_bertopic_model(
                min_topic_size=min_topic_size,
                nr_topics=nr_topics,
            )
            self.log_step("create_model", "completed", "BERTopic model created")
            
            # Step 3: Fit model
            self.log_step("fit_model", "running", "Fitting BERTopic model")
            embeddings = articles_data.get("embeddings")
            topics, probabilities = fit_topic_model(
                topic_model,
                articles_data["texts"],
                articles_data["timestamps"],
                embeddings=embeddings,
            )
            self.log_step("fit_model", "completed", f"Model fitted with {len(set(topics))} topics")
            
            # Step 3.5: Refine topic assignments with similarity (optional)
            refine_similarity = input_data.get("refine_topic_assignments", False)
            if refine_similarity and embeddings is not None:
                self.log_step("refine_assignments", "running", "Refining topic assignments with similarity")
                similarity_threshold = input_data.get("similarity_threshold", 0.7)
                topics, refine_stats = refine_topic_assignments_with_similarity(
                    topic_model,
                    articles_data["texts"],
                    topics,
                    embeddings=embeddings,
                    similarity_threshold=similarity_threshold,
                )
                self.log_step(
                    "refine_assignments",
                    "completed",
                    f"Refined assignments: {refine_stats.get('reassigned', 0)} articles reassigned",
                )
            
            # Step 4: Extract topic information
            self.log_step("extract_topics", "running", "Extracting topic information")
            # Get optional parameters for topic filtering
            min_keywords = input_data.get("min_keywords_significatifs", 3)
            max_stop_ratio = input_data.get("max_stop_words_ratio", 0.3)
            topics_dict = get_topic_info(
                topic_model,
                min_keywords_significatifs=min_keywords,
                max_stop_words_ratio=max_stop_ratio,
            )
            
            # Recalculate counts from actual topic assignments (after refinement)
            from collections import Counter
            topic_counts = Counter(topics)
            # Update counts in topics_dict
            for topic_id in topics_dict:
                if topic_id in topic_counts:
                    topics_dict[topic_id]["count"] = topic_counts[topic_id]
                else:
                    topics_dict[topic_id]["count"] = 0
            
            self.log_step(
                "extract_topics",
                "completed",
                f"Extracted {len(topics_dict)} relevant topics",
            )
            
            # Step 5: Generate topic hierarchy
            self.log_step("hierarchy", "running", "Generating topic hierarchy")
            hierarchy = generate_topic_hierarchy(topic_model)
            self.log_step("hierarchy", "completed", "Topic hierarchy generated")
            
            # Step 6: Analyze temporal evolution
            self.log_step("temporal", "running", "Analyzing temporal evolution")
            topics_over_time = analyze_temporal_evolution(
                topic_model,
                articles_data["texts"],
                articles_data["timestamps"],
                topics=topics,
            )
            self.log_step("temporal", "completed", "Temporal evolution analyzed")
            
            # Step 7: Detect emerging topics
            self.log_step("emerging", "running", "Detecting emerging topics")
            previous_analysis = await get_latest_bertopic_analysis(db_session)
            previous_topics = previous_analysis.topics if previous_analysis else None
            emerging_topics = detect_emerging_topics(topics_dict, previous_topics)
            self.log_step(
                "emerging",
                "completed",
                f"Detected {len(emerging_topics)} emerging topics",
            )
            
            # Step 8: Generate visualizations
            self.log_step("visualizations", "running", "Generating visualizations")
            # Convert topics_over_time dict back to DataFrame if needed for visualization
            topics_over_time_df = None
            if topics_over_time and "data" in topics_over_time:
                try:
                    import pandas as pd
                    topics_over_time_df = pd.DataFrame(topics_over_time["data"])
                except Exception as e:
                    logger.warning("Failed to convert topics_over_time to DataFrame", error=str(e))
            
            visualizations = generate_visualizations(
                topic_model,
                topics_over_time_data=topics_over_time_df,
            )
            self.log_step(
                "visualizations",
                "completed",
                f"Generated {len(visualizations)} visualizations",
            )
            
            # Step 9: Link topics to articles
            self.log_step("link_articles", "running", "Linking topics to articles")
            article_topic_mapping = {
                articles_data["article_ids"][i]: topics[i]
                for i in range(len(articles_data["article_ids"]))
                if topics[i] != -1  # Exclude noise topic
            }
            await update_articles_topic_ids_batch(db_session, article_topic_mapping)
            self.log_step(
                "link_articles",
                "completed",
                f"Linked {len(article_topic_mapping)} articles to topics",
            )
            
            # Step 10: Store results in database
            self.log_step("store_results", "running", "Storing results in database")
            analysis = await create_bertopic_analysis(
                db_session,
                analysis_date=datetime.now(timezone.utc),
                time_window_days=time_window_days,
                domains_included={domain: True for domain in domains},
                topics=topics_dict,
                topic_hierarchy=hierarchy,
                topics_over_time=topics_over_time,
                visualizations=visualizations,
                model_parameters={
                    "min_topic_size": min_topic_size,
                    "nr_topics": nr_topics,
                    "embedding_model": "mixedbread-ai/mxbai-embed-large-v1",
                },
            )
            self.log_step("store_results", "completed", f"Results stored (analysis_id={analysis.id})")
            
            # Prepare output
            result = {
                "success": True,
                "analysis_id": analysis.id,
                "statistics": {
                    "total_articles": len(articles_data["texts"]),
                    "num_topics": len(topics_dict),
                    "num_emerging_topics": len(emerging_topics),
                    "domains_analyzed": domains,
                    "time_window_days": time_window_days,
                },
                "topics": topics_dict,
                "emerging_topics": emerging_topics,
                "visualizations": visualizations,
            }
            
            self.log_step("complete", "completed", "Topic modeling workflow completed")
            
            return result
            
        except Exception as e:
            self.log_step("error", "failed", f"Topic modeling failed: {str(e)}")
            self.logger.error(
                "Topic modeling workflow failed",
                execution_id=str(execution_id),
                error=str(e),
            )
            raise

    async def _retrieve_articles(
        self,
        db_session: AsyncSession,
        domains: List[str],
        time_window_days: int,
        use_qdrant_embeddings: bool = True,
        filter_semantic_duplicates: bool = True,
        min_semantic_quality: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve articles for topic modeling with Qdrant integration.
        
        Args:
            db_session: Database session
            domains: List of domains to analyze
            time_window_days: Time window in days
            use_qdrant_embeddings: Whether to retrieve embeddings from Qdrant (default: True)
            filter_semantic_duplicates: Whether to filter semantic duplicates (default: True)
            min_semantic_quality: Minimum semantic quality threshold (optional, uses percentile if provided)
            
        Returns:
            Dictionary with texts, timestamps, article_ids, and embeddings
        """
        texts = []
        timestamps = []
        article_ids = []
        article_objects = []  # Store article objects for later processing
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=time_window_days)
        
        # Step 1: Retrieve articles from database
        for domain in domains:
            articles = await list_competitor_articles(
                db_session,
                domain=domain,
                limit=10000,  # Large limit to get all articles
                min_word_count=150,  # Minimum word count for quality
                max_age_days=time_window_days,
            )
            
            for article in articles:
                # Only filter articles that have a published_date and are too old
                # Articles without published_date are included (they were already filtered by list_competitor_articles)
                if article.published_date and time_window_days:
                    article_date = article.published_date
                    if isinstance(article_date, date):
                        if article_date < cutoff_date.date():
                            continue
                
                # Prepare text: title + content
                text = f"{article.title}\n{article.content_text}"
                texts.append(text)
                
                # Use published_date or created_at as timestamp
                if article.published_date:
                    if isinstance(article.published_date, date):
                        timestamp = datetime.combine(
                            article.published_date,
                            datetime.min.time(),
                        ).replace(tzinfo=timezone.utc)
                    else:
                        timestamp = article.published_date
                else:
                    timestamp = article.created_at
                
                timestamps.append(timestamp)
                article_ids.append(article.id)
                article_objects.append(article)
        
        if not texts:
            self.logger.warning("No articles found for topic modeling", domains=domains)
            return {
                "texts": [],
                "timestamps": [],
                "article_ids": [],
                "embeddings": None,
            }
        
        self.logger.info(
            "Articles retrieved from database",
            total=len(texts),
            domains=domains,
        )
        
        # Step 2: Retrieve embeddings from Qdrant if enabled
        embeddings_dict = {}
        missing_article_ids = []
        
        if use_qdrant_embeddings:
            try:
                # Get embeddings for articles that have qdrant_point_id
                articles_with_qdrant = [aid for aid, art in zip(article_ids, article_objects) if art.qdrant_point_id]
                
                if articles_with_qdrant:
                    embeddings_dict = qdrant_client.get_embeddings_by_article_ids(articles_with_qdrant)
                    missing_article_ids = [aid for aid in article_ids if aid not in embeddings_dict]
                    
                    self.logger.info(
                        "Embeddings retrieved from Qdrant",
                        retrieved=len(embeddings_dict),
                        missing=len(missing_article_ids),
                    )
                else:
                    missing_article_ids = article_ids
                    self.logger.info("No articles with Qdrant embeddings found, will generate all")
            except Exception as e:
                self.logger.warning(
                    "Failed to retrieve embeddings from Qdrant, will generate all",
                    error=str(e),
                )
                missing_article_ids = article_ids
        else:
            missing_article_ids = article_ids
        
        # Step 3: Generate embeddings for missing articles
        if missing_article_ids:
            missing_indices = [i for i, aid in enumerate(article_ids) if aid in missing_article_ids]
            missing_texts = [texts[i] for i in missing_indices]
            
            try:
                generated_embeddings = generate_embeddings_batch(missing_texts, batch_size=32)
                
                # Map generated embeddings to article IDs
                for idx, article_id in enumerate(missing_article_ids):
                    if idx < len(generated_embeddings):
                        embeddings_dict[article_id] = generated_embeddings[idx]
                
                self.logger.info(
                    "Embeddings generated for missing articles",
                    generated=len(generated_embeddings),
                )
            except Exception as e:
                self.logger.error(
                    "Failed to generate embeddings, will use BERTopic default",
                    error=str(e),
                )
        
        # Step 4: Filter semantic duplicates if enabled
        if filter_semantic_duplicates and embeddings_dict:
            filtered_indices = []
            seen_embeddings = []
            duplicate_threshold = 0.92
            
            for i, article_id in enumerate(article_ids):
                if article_id in embeddings_dict:
                    embedding = embeddings_dict[article_id]
                    is_duplicate = False
                    
                    # Check similarity with already seen embeddings
                    for seen_emb in seen_embeddings:
                        similarity = np.dot(embedding, seen_emb) / (
                            np.linalg.norm(embedding) * np.linalg.norm(seen_emb)
                        )
                        if similarity >= duplicate_threshold:
                            is_duplicate = True
                            break
                    
                    if not is_duplicate:
                        filtered_indices.append(i)
                        seen_embeddings.append(embedding)
                else:
                    # Keep articles without embeddings (will be generated by BERTopic)
                    filtered_indices.append(i)
            
            if len(filtered_indices) < len(article_ids):
                texts = [texts[i] for i in filtered_indices]
                timestamps = [timestamps[i] for i in filtered_indices]
                article_ids = [article_ids[i] for i in filtered_indices]
                article_objects = [article_objects[i] for i in filtered_indices]
                
                # Rebuild embeddings_dict with filtered articles
                filtered_embeddings_dict = {
                    aid: embeddings_dict[aid]
                    for aid in article_ids
                    if aid in embeddings_dict
                }
                embeddings_dict = filtered_embeddings_dict
                
                self.logger.info(
                    "Semantic duplicates filtered",
                    original=len(article_ids) + (len(article_ids) - len(filtered_indices)),
                    filtered=len(filtered_indices),
                    removed=len(article_ids) - len(filtered_indices),
                )
        
        # Step 5: Filter by semantic quality if enabled
        if min_semantic_quality is not None and embeddings_dict and len(embeddings_dict) > 10:
            # Calculate average similarity for each article with others in same domain
            article_qualities = {}
            
            for i, article_id in enumerate(article_ids):
                if article_id in embeddings_dict:
                    embedding = embeddings_dict[article_id]
                    similarities = []
                    
                    # Compare with other articles from same domain
                    article_domain = article_objects[i].domain
                    for j, other_id in enumerate(article_ids):
                        if i != j and other_id in embeddings_dict:
                            other_domain = article_objects[j].domain
                            if other_domain == article_domain:
                                other_emb = embeddings_dict[other_id]
                                similarity = np.dot(embedding, other_emb) / (
                                    np.linalg.norm(embedding) * np.linalg.norm(other_emb)
                                )
                                similarities.append(similarity)
                    
                    if similarities:
                        avg_similarity = np.mean(similarities)
                        article_qualities[article_id] = avg_similarity
            
            if article_qualities:
                # Use percentile as threshold
                quality_values = list(article_qualities.values())
                threshold = np.percentile(quality_values, min_semantic_quality * 100)
                
                filtered_indices = [
                    i
                    for i, aid in enumerate(article_ids)
                    if aid not in article_qualities or article_qualities[aid] >= threshold
                ]
                
                if len(filtered_indices) < len(article_ids):
                    texts = [texts[i] for i in filtered_indices]
                    timestamps = [timestamps[i] for i in filtered_indices]
                    article_ids = [article_ids[i] for i in filtered_indices]
                    article_objects = [article_objects[i] for i in filtered_indices]
                    
                    filtered_embeddings_dict = {
                        aid: embeddings_dict[aid]
                        for aid in article_ids
                        if aid in embeddings_dict
                    }
                    embeddings_dict = filtered_embeddings_dict
                    
                    self.logger.info(
                        "Articles filtered by semantic quality",
                        original=len(article_ids) + (len(article_ids) - len(filtered_indices)),
                        filtered=len(filtered_indices),
                        removed=len(article_ids) - len(filtered_indices),
                        threshold=threshold,
                    )
        
        # Step 6: Build embeddings array in same order as texts
        embeddings_array = None
        if embeddings_dict and len(embeddings_dict) == len(texts):
            try:
                embeddings_list = [embeddings_dict.get(aid) for aid in article_ids]
                # Filter out None values and create array
                valid_embeddings = [e for e in embeddings_list if e is not None]
                if len(valid_embeddings) == len(texts):
                    embeddings_array = np.array(valid_embeddings)
                    self.logger.info(
                        "Embeddings array prepared",
                        shape=embeddings_array.shape,
                        reused_from_qdrant=len([aid for aid in article_ids if aid in embeddings_dict]),
                    )
            except Exception as e:
                self.logger.warning(
                    "Failed to build embeddings array, will use BERTopic default",
                    error=str(e),
                )
        
        self.logger.info(
            "Articles retrieved for topic modeling",
            total=len(texts),
            domains=domains,
            embeddings_available=embeddings_array is not None,
        )
        
        return {
            "texts": texts,
            "timestamps": timestamps,
            "article_ids": article_ids,
            "embeddings": embeddings_array,
        }

