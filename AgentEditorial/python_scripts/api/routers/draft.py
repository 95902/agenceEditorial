"""API router for draft article generation."""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.agents.article_generation.crew import PlanningCrew, ReviewCrew, VisualizationCrew, WritingCrew
from python_scripts.api.dependencies import get_db_session as get_db
from python_scripts.api.schemas.draft import (
    DraftMetadata,
    DraftRequest,
    DraftResponse,
    DraftSuggestions,
    GeneratedImage,
    ImageSuggestion,
)
from python_scripts.config.settings import settings
from python_scripts.database.crud_clusters import get_topic_cluster_by_topic_id
from python_scripts.database.crud_generated_articles import (
    create_article,
    get_article_images,
    list_articles,
    update_article_content,
    update_article_plan,
    update_article_status,
)
from python_scripts.database.crud_images import save_image_generation
from python_scripts.database.crud_llm_results import (
    get_article_recommendations_by_topic_cluster,
    get_trend_analyses_by_topic_cluster,
)
from python_scripts.database.crud_profiles import get_site_profile_by_domain
from python_scripts.database.models import (
    ArticleRecommendation,
    CompetitorArticle,
    SiteProfile,
    TopicCluster,
    TrendAnalysis,
    TrendPipelineExecution,
)
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/draft", tags=["Draft Generation"])


def _calculate_reading_time(word_count: int) -> str:
    """
    Calculate reading time from word count.
    
    Args:
        word_count: Number of words
        
    Returns:
        Reading time string (e.g., "8 min")
    """
    # Average reading speed: 200-250 words/min (using 200 for conservative estimate)
    minutes = max(1, round(word_count / 200))
    return f"{minutes} min"


def _extract_subtitle(
    hook: Optional[str],
    synthesis: Optional[str],
    title: str,
) -> str:
    """
    Extract or generate subtitle from hook, synthesis, or title.
    
    Args:
        hook: Article hook from ArticleRecommendation
        synthesis: Trend analysis synthesis
        title: Article title
        
    Returns:
        Subtitle string
    """
    # Use hook if available (first 2-3 sentences)
    if hook:
        sentences = hook.split(". ")
        if len(sentences) >= 2:
            return ". ".join(sentences[:2]).strip()
        return hook.strip()
    
    # Fallback to synthesis (first sentence)
    if synthesis:
        first_sentence = synthesis.split(". ")[0]
        if len(first_sentence) > 20:  # Ensure meaningful subtitle
            return first_sentence.strip() + "."
    
    # Fallback: generate from title (remove common patterns)
    # This is a simple fallback, could be improved with LLM
    return title.replace(" : Guide complet", "").replace(" : Guide", "").strip()


def _parse_review_result(review_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse ReviewCrew raw_review to extract seo_score, readability_score, improvements.
    
    Args:
        review_result: Review result from ReviewCrew
        
    Returns:
        Dictionary with parsed scores and suggestions
    """
    parsed = {
        "seo_score": None,
        "readability_score": None,
        "improvements": [],
    }
    
    raw_review = review_result.get("raw_review", "")
    if not raw_review:
        return parsed
    
    try:
        # Try to parse as JSON first
        if raw_review.strip().startswith("{"):
            review_json = json.loads(raw_review)
            parsed["seo_score"] = review_json.get("seo_score")
            parsed["readability_score"] = review_json.get("readability_score")
            parsed["improvements"] = review_json.get("improvements", [])
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass
    
    # Fallback: regex extraction
    seo_match = re.search(r'"seo_score":\s*(\d+)', raw_review)
    if seo_match:
        parsed["seo_score"] = int(seo_match.group(1))
    
    readability_match = re.search(r'"readability_score":\s*(\d+)', raw_review)
    if readability_match:
        parsed["readability_score"] = int(readability_match.group(1))
    
    # Extract improvements (try to find JSON array)
    improvements_match = re.search(r'"improvements":\s*\[(.*?)\]', raw_review, re.DOTALL)
    if improvements_match:
        improvements_str = improvements_match.group(1)
        # Try to extract individual items
        items = re.findall(r'"([^"]+)"', improvements_str)
        parsed["improvements"] = items
    
    return parsed


def _generate_image_suggestions(
    plan_json: Dict[str, Any],
    content_markdown: str,
) -> List[ImageSuggestion]:
    """
    Generate image suggestions based on article plan and content.
    
    Args:
        plan_json: Article plan from PlanningCrew
        content_markdown: Article content
        
    Returns:
        List of image suggestions
    """
    suggestions = []
    
    if not plan_json:
        return suggestions
    
    # Try to parse plan_json if it's a string
    if isinstance(plan_json, str):
        try:
            plan_json = json.loads(plan_json)
        except (json.JSONDecodeError, ValueError):
            # Try to extract from raw_outline
            if "raw_outline" in plan_json:
                try:
                    plan_json = json.loads(plan_json["raw_outline"])
                except (json.JSONDecodeError, ValueError):
                    return suggestions
    
    # Extract sections from plan
    sections = plan_json.get("sections", [])
    if not isinstance(sections, list):
        sections = []
    
    # Generate suggestion for introduction
    if plan_json.get("title") or plan_json.get("h1"):
        suggestions.append(ImageSuggestion(
            description="Illustration principale représentant le concept central de l'article",
            type="Infographie",
            placement="Après l'introduction",
        ))
    
    # Generate suggestions for main sections
    section_types = {
        "architecture": "Infographie",
        "comparaison": "Chart",
        "évolution": "Timeline",
        "guide": "Infographie",
        "cas d'usage": "Illustration",
        "roi": "Chart",
        "roadmap": "Timeline",
    }
    
    for i, section in enumerate(sections[:5]):  # Limit to 5 sections
        if not isinstance(section, dict):
            continue
        
        h2 = section.get("h2", "")
        section_lower = h2.lower()
        
        # Determine image type based on section content
        image_type = "Infographie"
        for keyword, img_type in section_types.items():
            if keyword in section_lower:
                image_type = img_type
                break
        
        # Generate description
        description = f"Visualisation pour la section '{h2}'"
        if section.get("objectifs"):
            description = f"Représentation visuelle des objectifs de la section '{h2}'"
        
        placement = f"Section {i + 1}: {h2}"
        suggestions.append(ImageSuggestion(
            description=description,
            type=image_type,
            placement=placement,
        ))
    
    return suggestions


def _separate_suggestions(improvements: List[str]) -> Dict[str, List[str]]:
    """
    Separate improvements into SEO and readability suggestions.
    
    Args:
        improvements: List of improvement strings
        
    Returns:
        Dictionary with 'seo' and 'readability' lists
    """
    seo_keywords = ["seo", "mots-clés", "keywords", "meta", "titre", "h2", "h3", "liens", "longue traîne"]
    readability_keywords = ["simplifier", "phrases", "exemples", "listes", "puces", "clarté", "compréhension"]
    
    seo_suggestions = []
    readability_suggestions = []
    
    for improvement in improvements:
        if not isinstance(improvement, str):
            continue
        
        improvement_lower = improvement.lower()
        is_seo = any(keyword in improvement_lower for keyword in seo_keywords)
        is_readability = any(keyword in improvement_lower for keyword in readability_keywords)
        
        if is_seo and not is_readability:
            seo_suggestions.append(improvement)
        elif is_readability:
            readability_suggestions.append(improvement)
        else:
            # Default to readability if unclear
            readability_suggestions.append(improvement)
    
    return {
        "seo": seo_suggestions if seo_suggestions else None,
        "readability": readability_suggestions if readability_suggestions else None,
    }


async def _get_existing_draft(
    db: AsyncSession,
    topic_id_slug: str,
    site_client: Optional[str] = None,
) -> Optional[DraftResponse]:
    """
    Retrieve an existing draft from database.
    
    Args:
        db: Database session
        topic_id_slug: Topic ID slug (e.g., "edge-cloud-hybride-5")
        site_client: Client site identifier (optional)
        
    Returns:
        DraftResponse if found, None otherwise
    """
    # 1. Extract topic_id from slug
    topic_id = await _extract_topic_id_from_slug(topic_id_slug)
    if topic_id is None:
        return None
    
    # 2. Get site profile if site_client provided
    site_profile = None
    site_profile_id = None
    if site_client:
        site_profile = await get_site_profile_by_domain(db, site_client)
        if site_profile:
            site_profile_id = site_profile.id
    
    # 3. Find trend pipeline execution
    trend_execution = None
    if site_profile:
        stmt = (
            select(TrendPipelineExecution)
            .where(
                TrendPipelineExecution.client_domain == site_profile.domain,
                TrendPipelineExecution.stage_1_clustering_status == "completed",
                TrendPipelineExecution.is_valid == True,  # noqa: E712
            )
            .order_by(desc(TrendPipelineExecution.start_time))
            .limit(1)
        )
        result = await db.execute(stmt)
        trend_execution = result.scalar_one_or_none()
    
    if not trend_execution:
        # Fallback: search all executions
        stmt = (
            select(TrendPipelineExecution)
            .where(
                TrendPipelineExecution.stage_1_clustering_status == "completed",
                TrendPipelineExecution.is_valid == True,  # noqa: E712
            )
            .order_by(desc(TrendPipelineExecution.start_time))
            .limit(10)
        )
        result = await db.execute(stmt)
        executions = list(result.scalars().all())
        
        for exec in executions:
            cluster = await get_topic_cluster_by_topic_id(db, exec.id, topic_id)
            if cluster:
                trend_execution = exec
                break
    
    if not trend_execution:
        return None
    
    # 4. Get topic cluster
    cluster = await get_topic_cluster_by_topic_id(db, trend_execution.id, topic_id)
    if not cluster:
        return None
    
    # 5. Get ArticleRecommendation and TrendAnalysis
    article_recommendations = await get_article_recommendations_by_topic_cluster(db, cluster.id)
    article_recommendation = article_recommendations[0] if article_recommendations else None
    
    trend_analyses = await get_trend_analyses_by_topic_cluster(db, cluster.id)
    trend_analysis = trend_analyses[0] if trend_analyses else None
    
    # 6. Find existing generated article
    # Search by topic and site_profile_id
    # Don't filter by status - check if article has content (meaning it's been generated)
    articles = await list_articles(
        db_session=db,
        site_profile_id=site_profile_id,
        status=None,  # Don't filter by status
        limit=100,
    )
    
    # Filter by topic matching cluster label or article recommendation title
    # And ensure article has content (has been generated)
    topic = article_recommendation.title if article_recommendation else cluster.label
    matching_article = None
    for article in articles:
        if (article.topic == topic or article.topic.lower() == topic.lower()) and article.content_markdown:
            matching_article = article
            break
    
    if not matching_article:
        return None
    
    # 7. Get article images
    images = await get_article_images(db, article_id=matching_article.id)
    
    # 8. Build response
    content_markdown = matching_article.content_markdown or ""
    word_count = matching_article.final_word_count or len(content_markdown.split())
    
    # Parse quality metrics
    quality_metrics = matching_article.quality_metrics or {}
    review_result = quality_metrics.get("review", {})
    parsed_review = _parse_review_result(review_result)
    seo_score = parsed_review.get("seo_score")
    readability_score = parsed_review.get("readability_score")
    improvements = parsed_review.get("improvements", [])
    
    # Generate suggestions from plan_json
    plan_json = matching_article.plan_json or {}
    image_suggestions = _generate_image_suggestions(plan_json, content_markdown)
    separated_suggestions = _separate_suggestions(improvements)
    
    suggestions = None
    if image_suggestions or separated_suggestions.get("seo") or separated_suggestions.get("readability"):
        suggestions = DraftSuggestions(
            images=image_suggestions if image_suggestions else None,
            seo=separated_suggestions.get("seo"),
            readability=separated_suggestions.get("readability"),
        )
    
    # Build generated images list
    generated_images_list = []
    for img in images:
        # Convert local_path to URL path
        local_path = img.local_path or ""
        if local_path:
            # Extract filename and build URL
            filename = Path(local_path).name
            image_url = f"/outputs/articles/images/{filename}"
        else:
            image_url = ""
        
        generated_images_list.append(GeneratedImage(
            path=image_url,
            prompt=img.prompt,
            quality_score=float(img.quality_score) if img.quality_score else None,
            generation_time_seconds=float(img.generation_time_seconds) if img.generation_time_seconds else None,
        ))
    
    # Extract subtitle
    hook = article_recommendation.hook if article_recommendation else None
    synthesis = trend_analysis.synthesis if trend_analysis else None
    subtitle = _extract_subtitle(hook, synthesis, topic)
    
    reading_time = _calculate_reading_time(word_count)
    
    return DraftResponse(
        id=f"draft-{topic_id_slug}",
        topic_id=topic_id_slug,
        title=topic,
        subtitle=subtitle,
        content=content_markdown,
        metadata=DraftMetadata(
            word_count=word_count,
            reading_time=reading_time,
            seo_score=seo_score,
            readability_score=readability_score,
        ),
        suggestions=suggestions,
        generated_images=generated_images_list if generated_images_list else None,
    )


async def _extract_topic_id_from_slug(slug: str) -> Optional[int]:
    """
    Extract topic_id from slug format: "label-topic_id".
    
    Args:
        slug: Topic slug (e.g., "edge-cloud-hybride-5")
        
    Returns:
        Topic ID if found, None otherwise
    """
    parts = slug.split("-")
    for part in reversed(parts):
        if part.isdigit():
            return int(part)
    return None


async def _generate_draft_sync(
    db: AsyncSession,
    topic_id_slug: str,
    site_client: Optional[str] = None,
    domain_topic: Optional[str] = None,
) -> DraftResponse:
    """
    Generate draft article synchronously from topic_id.
    
    Args:
        db: Database session
        topic_id_slug: Topic ID slug (e.g., "edge-cloud-hybride-5")
        site_client: Client site identifier (optional, for site_profile)
        domain_topic: Activity domain label (optional, for validation)
        
    Returns:
        DraftResponse with complete draft
        
    Raises:
        HTTPException: If topic not found or generation fails
    """
    from python_scripts.agents.article_generation.crew import PlanningCrew, ReviewCrew, WritingCrew
    
    # 1. Extract topic_id from slug
    topic_id = await _extract_topic_id_from_slug(topic_id_slug)
    if topic_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid topic_id format: {topic_id_slug}",
        )
    
    # 2. Get site profile if site_client provided
    site_profile = None
    site_profile_id = None
    if site_client:
        site_profile = await get_site_profile_by_domain(db, site_client)
        if site_profile:
            site_profile_id = site_profile.id
            # Validate domain_topic if provided
            if domain_topic:
                activity_domains = site_profile.activity_domains or {}
                all_domains = (
                    activity_domains.get("primary_domains", []) +
                    activity_domains.get("secondary_domains", [])
                )
                if domain_topic not in all_domains:
                    logger.warning(
                        "Domain topic not found in activity domains",
                        domain_topic=domain_topic,
                        site_client=site_client,
                    )
    
    # 3. Get latest trend pipeline execution
    # Try to find execution for site_client domain, or use most recent
    trend_execution = None
    if site_profile:
        stmt = (
            select(TrendPipelineExecution)
            .where(
                TrendPipelineExecution.client_domain == site_profile.domain,
                TrendPipelineExecution.stage_1_clustering_status == "completed",
                TrendPipelineExecution.is_valid == True,  # noqa: E712
            )
            .order_by(desc(TrendPipelineExecution.start_time))
            .limit(1)
        )
        result = await db.execute(stmt)
        trend_execution = result.scalar_one_or_none()
    
    # If no execution found for site, try to find any execution with this topic_id
    if not trend_execution:
        # We need to find the cluster first to get the analysis_id
        # This is a fallback - ideally site_client should be provided
        logger.warning("No trend pipeline execution found for site, will try to find cluster by topic_id")
    
    # 4. Get topic cluster
    # We need analysis_id to get the cluster, so we'll search across all executions
    cluster = None
    if trend_execution:
        cluster = await get_topic_cluster_by_topic_id(
            db, trend_execution.id, topic_id
        )
    
    if not cluster:
        # Fallback: search all trend pipeline executions
        stmt = (
            select(TrendPipelineExecution)
            .where(
                TrendPipelineExecution.stage_1_clustering_status == "completed",
                TrendPipelineExecution.is_valid == True,  # noqa: E712
            )
            .order_by(desc(TrendPipelineExecution.start_time))
            .limit(10)  # Check last 10 executions
        )
        result = await db.execute(stmt)
        executions = list(result.scalars().all())
        
        for exec in executions:
            cluster = await get_topic_cluster_by_topic_id(
                db, exec.id, topic_id
            )
            if cluster:
                trend_execution = exec
                break
    
    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Topic cluster not found for topic_id: {topic_id}",
        )
    
    # 5. Get ArticleRecommendation and TrendAnalysis
    article_recommendations = await get_article_recommendations_by_topic_cluster(
        db, cluster.id
    )
    article_recommendation = article_recommendations[0] if article_recommendations else None
    
    trend_analyses = await get_trend_analyses_by_topic_cluster(db, cluster.id)
    trend_analysis = trend_analyses[0] if trend_analyses else None
    
    # 6. Prepare generation parameters
    topic = article_recommendation.title if article_recommendation else cluster.label
    keywords_list = []
    if cluster.top_terms:
        terms = cluster.top_terms.get("terms", [])
        if isinstance(terms, list):
            keywords_list = [
                str(t.get("word", t) if isinstance(t, dict) else t)
                for t in terms[:10]
            ]
    
    tone = "professional"
    if site_profile and site_profile.editorial_tone:
        tone = site_profile.editorial_tone
    
    target_words = 2000
    language = "fr"
    
    # 7. Create article in database (for tracking)
    generated_article = await create_article(
        db_session=db,
        topic=topic,
        keywords=keywords_list,
        tone=tone,
        target_words=target_words,
        language=language,
        site_profile_id=site_profile_id,
    )
    await db.commit()
    
    try:
        # 8. Generate article synchronously
        logger.info("Starting synchronous draft generation", topic_id=topic_id, topic=topic)
        
        # 8.1. Planning
        await update_article_status(
            db_session=db,
            plan_id=generated_article.plan_id,
            status="planning",
            current_step="planning",
            progress_percentage=10,
        )
        await db.commit()
        
        planning_crew = PlanningCrew()
        planning_result = await planning_crew.run(topic=topic, keywords=keywords_list)
        
        # Parse planning result
        plan_json = planning_result.get("raw_outline", {})
        if isinstance(plan_json, str):
            try:
                plan_json = json.loads(plan_json)
            except (json.JSONDecodeError, ValueError):
                # If parsing fails, create a basic structure
                plan_json = {
                    "title": topic,
                    "h1": topic,
                    "sections": [],
                }
        
        await update_article_plan(
            db_session=db,
            plan_id=generated_article.plan_id,
            plan_json=plan_json,
        )
        await db.commit()
        
        # 8.2. Writing
        await update_article_status(
            db_session=db,
            plan_id=generated_article.plan_id,
            status="writing",
            current_step="writing",
            progress_percentage=50,
        )
        await db.commit()
        
        writing_crew = WritingCrew()
        outline_str = json.dumps(plan_json, ensure_ascii=False)
        content_markdown = await writing_crew.run(
            topic=topic,
            tone=tone,
            target_words=target_words,
            language=language,
            outline=outline_str,
        )
        
        # Calculate word count
        word_count = len(content_markdown.split())
        
        await update_article_content(
            db_session=db,
            plan_id=generated_article.plan_id,
            content_markdown=content_markdown,
        )
        await update_article_status(
            db_session=db,
            plan_id=generated_article.plan_id,
            status="reviewing",
            current_step="reviewing",
            progress_percentage=75,
        )
        await db.commit()
        
        # 8.3. Review
        review_crew = ReviewCrew()
        review_result = await review_crew.run(content_markdown=content_markdown)
        
        # Parse review result
        parsed_review = _parse_review_result(review_result)
        seo_score = parsed_review.get("seo_score")
        readability_score = parsed_review.get("readability_score")
        improvements = parsed_review.get("improvements", [])
        
        # Update article with scores
        await update_article_content(
            db_session=db,
            plan_id=generated_article.plan_id,
            quality_metrics={"review": review_result},
        )
        await db.commit()
        
        # 8.4. Visualization (image generation)
        generated_images_list: List[GeneratedImage] = []
        image_suggestions: List[ImageSuggestion] = []  # Initialize for later use
        if settings.z_image_enabled:
            try:
                await update_article_status(
                    db_session=db,
                    plan_id=generated_article.plan_id,
                    status="generating_images",
                    current_step="generating_images",
                    progress_percentage=80,
                )
                await db.commit()
                
                # Prepare site_profile for image generation
                site_profile_dict = None
                if site_profile:
                    site_profile_dict = {
                        "editorial_tone": site_profile.editorial_tone or "professional",
                        "target_audience": site_profile.target_audience or {},
                        "activity_domains": site_profile.activity_domains or {},
                        "keywords": site_profile.keywords or {},
                        "style_features": site_profile.style_features or {},
                    }
                
                # Generate image suggestions first to determine how many images to generate
                image_suggestions = _generate_image_suggestions(plan_json, content_markdown)
                
                # Determine number of images to generate (1-3 based on suggestions)
                # Always generate at least 1 main image, plus up to 2 additional based on suggestions
                num_images_to_generate = min(3, max(1, len(image_suggestions)))
                
                logger.info(
                    "Generating multiple images for article",
                    article_id=generated_article.id,
                    num_suggestions=len(image_suggestions),
                    num_images_to_generate=num_images_to_generate,
                )
                
                visualization_crew = VisualizationCrew()
                base_output_dir = Path(settings.article_images_dir)
                
                # Generate multiple images
                for i in range(num_images_to_generate):
                    try:
                        # For the first image, use the main topic
                        # For subsequent images, use the suggestion description as additional context
                        image_topic = topic
                        if i > 0 and i <= len(image_suggestions):
                            # Use suggestion description to enrich the topic for additional images
                            suggestion = image_suggestions[i - 1]
                            image_topic = f"{topic} - {suggestion.description}"
                        
                        logger.info(
                            "Generating image",
                            image_number=i + 1,
                            total=num_images_to_generate,
                            article_id=generated_article.id,
                        )
                        
                        image_info = await visualization_crew.run(
                            article_title=topic,
                            topic=image_topic,
                            base_output_dir=base_output_dir,
                            site_profile=site_profile_dict,
                            article_id=generated_article.id,
                        )
                        
                        # Save image to database if generation succeeded
                        if image_info.get("image_path") and not image_info.get("error"):
                            try:
                                saved_image = await save_image_generation(
                                    db=db,
                                    site_profile_id=site_profile_id,
                                    article_topic=topic,
                                    prompt_used=image_info.get("prompt", ""),
                                    output_path=image_info.get("image_path", ""),
                                    generation_params=image_info.get("generation_params", {}),
                                    quality_score=image_info.get("quality_score"),
                                    negative_prompt=image_info.get("negative_prompt"),
                                    critique_details=image_info.get("critique_details"),
                                    retry_count=image_info.get("retry_count", 0),
                                    final_status=image_info.get("final_status", "success"),
                                    generation_time_seconds=image_info.get("generation_time_seconds"),
                                    article_id=generated_article.id,
                                )
                                await db.flush()
                                
                                if saved_image:
                                    logger.info(
                                        "Image generation saved to database",
                                        image_id=saved_image.id,
                                        article_id=generated_article.id,
                                        image_number=i + 1,
                                    )
                                    
                                    # Add to generated_images list
                                    image_path = image_info.get("image_path", "")
                                    if image_path:
                                        filename = Path(image_path).name
                                        image_url = f"/outputs/articles/images/{filename}"
                                    else:
                                        image_url = ""
                                    
                                    generated_images_list.append(GeneratedImage(
                                        path=image_url,
                                        prompt=image_info.get("prompt"),
                                        quality_score=image_info.get("quality_score"),
                                        generation_time_seconds=image_info.get("generation_time_seconds"),
                                    ))
                            except Exception as db_error:
                                logger.error(
                                    "Failed to save image generation to database",
                                    error=str(db_error),
                                    article_id=generated_article.id,
                                    image_number=i + 1,
                                )
                                # Continue even if database save fails, but still add image to response
                                if image_info.get("image_path"):
                                    image_path = image_info.get("image_path", "")
                                    filename = Path(image_path).name
                                    image_url = f"/outputs/articles/images/{filename}"
                                    
                                    generated_images_list.append(GeneratedImage(
                                        path=image_url,
                                        prompt=image_info.get("prompt"),
                                        quality_score=image_info.get("quality_score"),
                                        generation_time_seconds=image_info.get("generation_time_seconds"),
                                    ))
                        else:
                            logger.warning(
                                "Image generation failed or returned no path",
                                image_number=i + 1,
                                article_id=generated_article.id,
                                error=image_info.get("error"),
                            )
                    
                    except Exception as single_image_error:
                        logger.error(
                            "Failed to generate single image",
                            error=str(single_image_error),
                            image_number=i + 1,
                            article_id=generated_article.id,
                        )
                        # Continue with next image even if one fails
                        continue
                
                logger.info(
                    "Image generation completed",
                    article_id=generated_article.id,
                    total_generated=len(generated_images_list),
                    requested=num_images_to_generate,
                )
                
                await update_article_status(
                    db_session=db,
                    plan_id=generated_article.plan_id,
                    status="reviewing",
                    current_step="visualization_completed",
                    progress_percentage=85,
                )
                await db.commit()
                
            except Exception as image_error:
                logger.error(
                    "Image generation failed",
                    error=str(image_error),
                    topic_id=topic_id,
                    article_id=generated_article.id,
                )
                # Continue without failing the entire draft generation
                await update_article_status(
                    db_session=db,
                    plan_id=generated_article.plan_id,
                    status="reviewing",
                    current_step="visualization_failed",
                    progress_percentage=75,
                )
                await db.commit()
        
        # 9. Generate suggestions (reuse if already generated, otherwise generate)
        if not image_suggestions:
            image_suggestions = _generate_image_suggestions(plan_json, content_markdown)
        separated_suggestions = _separate_suggestions(improvements)
        
        suggestions = None
        if image_suggestions or separated_suggestions.get("seo") or separated_suggestions.get("readability"):
            suggestions = DraftSuggestions(
                images=image_suggestions if image_suggestions else None,
                seo=separated_suggestions.get("seo"),
                readability=separated_suggestions.get("readability"),
            )
        
        # 10. Extract subtitle
        hook = article_recommendation.hook if article_recommendation else None
        synthesis = trend_analysis.synthesis if trend_analysis else None
        subtitle = _extract_subtitle(hook, synthesis, topic)
        
        # 11. Build response
        reading_time = _calculate_reading_time(word_count)
        
        return DraftResponse(
            id=f"draft-{topic_id_slug}",
            topic_id=topic_id_slug,
            title=topic,
            subtitle=subtitle,
            content=content_markdown,
            metadata=DraftMetadata(
                word_count=word_count,
                reading_time=reading_time,
                seo_score=seo_score,
                readability_score=readability_score,
            ),
            suggestions=suggestions,
            generated_images=generated_images_list if generated_images_list else None,
        )
    
    except Exception as e:
        logger.error("Draft generation failed", error=str(e), topic_id=topic_id)
        # Update article status to failed
        await update_article_status(
            db_session=db,
            plan_id=generated_article.plan_id,
            status="failed",
            current_step="generation_failed",
            progress_percentage=0,
            error_message=str(e),
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Draft generation failed: {str(e)}",
        )


@router.get(
    "",
    response_model=DraftResponse,
    summary="Get existing draft",
    description="""
    Retrieve an existing draft article by topic_id.
    
    Returns a previously generated draft if it exists in the database.
    If no draft exists, returns 404.
    
    Example:
        GET /api/v1/draft?topic_id=edge-cloud-hybride&site_client=innosys.fr
    """,
    responses={
        200: {
            "description": "Draft retrieved successfully",
        },
        404: {
            "description": "Draft not found",
        },
    },
)
async def get_draft(
    topic_id: str = Query(..., description="Topic identifier (slug)", examples=["edge-cloud-hybride"]),
    site_client: Optional[str] = Query(None, description="Client site identifier", examples=["innosys.fr"]),
    db: AsyncSession = Depends(get_db),
) -> DraftResponse:
    """
    Get existing draft by topic_id.
    
    Args:
        topic_id: Topic identifier (slug)
        site_client: Client site identifier (optional, helps find the right draft)
        db: Database session
        
    Returns:
        DraftResponse with existing draft
        
    Raises:
        HTTPException: 404 if draft not found
    """
    draft = await _get_existing_draft(db, topic_id, site_client)
    
    if not draft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Draft not found for topic_id: {topic_id}",
        )
    
    return draft


@router.post(
    "",
    response_model=DraftResponse,
    summary="Generate article draft",
    description="""
    Generate a complete article draft synchronously from a topic_id.
    
    First checks if a draft already exists. If yes, returns it.
    Otherwise, generates a new draft.
    
    This endpoint generates a full article draft including:
    - Article content in markdown
    - SEO and readability scores
    - Image suggestions
    - Generated images (if enabled)
    - SEO and readability improvement suggestions
    
    Note: This is a synchronous operation that may take 30-60 seconds (or more if images are generated).
    
    Example:
        POST /api/v1/draft
        {
          "topic_id": "edge-cloud-hybride",
          "site_client": "innosys.fr"
        }
    """,
    responses={
        200: {
            "description": "Draft generated successfully",
        },
        400: {
            "description": "Invalid topic_id format",
        },
        404: {
            "description": "Topic not found",
        },
        500: {
            "description": "Draft generation failed",
        },
    },
)
async def generate_draft(
    request: DraftRequest,
    db: AsyncSession = Depends(get_db),
) -> DraftResponse:
    """
    Generate article draft from topic_id.
    
    First checks if a draft already exists. If yes, returns it.
    Otherwise, generates a new draft.
    
    Args:
        request: DraftRequest with topic_id and optional site_client
        db: Database session
        
    Returns:
        DraftResponse with complete draft
        
    Raises:
        HTTPException: If topic not found or generation fails
    """
    # Check if draft already exists
    existing_draft = await _get_existing_draft(
        db,
        request.topic_id,
        site_client=request.site_client,
    )
    
    if existing_draft:
        logger.info(
            "Returning existing draft",
            topic_id=request.topic_id,
            site_client=request.site_client,
        )
        return existing_draft
    
    # Generate new draft
    return await _generate_draft_sync(
        db,
        request.topic_id,
        site_client=request.site_client,
        domain_topic=None,
    )

