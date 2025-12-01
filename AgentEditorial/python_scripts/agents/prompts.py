"""Centralized prompts for all LLM agents."""

# Editorial Analysis Prompts

EDITORIAL_ANALYSIS_PROMPT_LLAMA3 = """Analyze the editorial style of the following website content.

Content:
{content}

Provide a detailed analysis including:
1. Language level (simple, intermediate, advanced, expert)
2. Editorial tone (professional, conversational, technical, marketing)
3. Target audience identification
4. Activity domains
5. Key stylistic features

Format your response as JSON with the following structure:
{{
    "language_level": "...",
    "editorial_tone": "...",
    "target_audience": {{
        "primary": "...",
        "secondary": [...]
    }},
    "activity_domains": {{
        "primary_domains": [...],
        "secondary_domains": [...]
    }},
    "style_features": {{
        "sentence_length_avg": ...,
        "reading_level": "...",
        "formality_score": ...
    }}
}}
"""

EDITORIAL_ANALYSIS_PROMPT_MISTRAL = """Analyze the content structure of the following website content.

Content:
{content}

Focus on:
1. Average word count per page
2. Paragraph structure
3. Heading patterns (H1, H2, H3 usage)
4. Media usage (images, videos)
5. Internal linking patterns

Format your response as JSON:
{{
    "content_structure": {{
        "average_word_count": ...,
        "average_paragraph_count": ...,
        "heading_patterns": [...],
        "media_usage": {{"images": ..., "videos": ...}},
        "internal_linking": ...
    }}
}}
"""

EDITORIAL_ANALYSIS_PROMPT_PHI3 = """Extract keywords and semantic analysis from the following website content.

Content:
{content}

Extract:
1. Primary keywords (top 10)
2. Keyword density
3. Semantic keywords (related terms)

Format your response as JSON:
{{
    "keywords": {{
        "primary_keywords": [...],
        "keyword_density": {{"keyword": density_percentage}},
        "semantic_keywords": [...]
    }}
}}
"""

# Competitor Search Prompts

COMPETITOR_FILTERING_PROMPT = """Evaluate if the following domain is a relevant competitor for the target domain.

Target domain: {target_domain}
Target description: {target_description}
Target services: {target_services}
Target keywords: {target_keywords}

Candidate domain: {candidate_domain}
Candidate description: {candidate_description}
Candidate services: {candidate_services}

Rate the relevance from 0.0 to 1.0 where:
- 0.8-1.0: Direct competitor (same products/services, same market)
- 0.6-0.79: Indirect competitor (same industry, complementary services)
- 0.0-0.59: Not a competitor

Provide your response as JSON:
{{
    "relevance_score": ...,
    "reason": "...",
    "category": "direct" | "indirect" | "not_competitor"
}}
"""

# Topic Modeling Prompts (for post-processing)

TOPIC_DESCRIPTION_PROMPT = """Describe the following topic based on its keywords.

Keywords: {keywords}

Provide a concise topic name and description.
"""

# Gap Analysis Prompts

GAP_ANALYSIS_PROMPT = """Analyze content gaps between client and competitors.

Client topics: {client_topics}
Competitor topics: {competitor_topics}

Identify topics present in competitors but missing in client content.
For each gap, provide:
1. Gap score (frequency × importance)
2. Content recommendation (title, keywords, angle)

Format as JSON:
{{
    "gaps": [
        {{
            "topic_id": ...,
            "topic_keywords": [...],
            "gap_score": ...,
            "frequency": ...,
            "recommendation": {{
                "title": "...",
                "keywords": [...],
                "angle": "..."
            }}
        }}
    ]
}}
"""

