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

IMPORTANT: 
- Extract ALL values from the content provided above, do NOT use placeholder or example values
- Respond ONLY with valid JSON. Do not include any text before or after the JSON. Do not use escaped quotes or nested JSON strings.

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
        "sentence_length_avg": "...",
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

IMPORTANT: 
- Extract ALL values from the content provided above, do NOT use placeholder or example values
- Respond ONLY with valid JSON. Do not include any text before or after the JSON. Do not use escaped quotes or nested JSON strings.

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

EDITORIAL_ANALYSIS_PROMPT_PHI3 = """Extract keywords, semantic analysis, and detailed activity domains from the following website content.

Content:
{content}

Extract:
1. Primary keywords (top 10)
2. Keyword density
3. Semantic keywords (related terms)
4. Activity domains - BE VERY DETAILED AND SPECIFIC:
   - Identify ALL business domains, services, and sectors mentioned in the content
   - Use specific, technical terms (e.g., "cloud infrastructure", "DevOps consulting", "penetration testing" instead of generic terms)
   - Include sub-domains and specializations
   - Minimum 5-8 primary domains, 8-12 secondary domains
   - Be precise: avoid generic terms like "IT services" or "information technology"
   - Extract ONLY from the content provided, do NOT use placeholder or example values

IMPORTANT: Respond ONLY with valid JSON. Do not include any text before or after the JSON. Do not use escaped quotes or nested JSON strings.

Format your response as JSON:
{{
    "keywords": {{
        "primary_keywords": ["extract from content", "extract from content"],
        "keyword_density": {{"keyword1": density_percentage, "keyword2": density_percentage}},
        "semantic_keywords": ["related term from content", "related term from content"]
    }},
    "activity_domains": {{
        "primary_domains": [
            "Specific domain extracted from content",
            "Specific domain extracted from content",
            "Specific domain extracted from content"
        ],
        "secondary_domains": [
            "Sub-domain or specialization from content",
            "Sub-domain or specialization from content",
            "Sub-domain or specialization from content"
        ]
    }}
}}
"""

EDITORIAL_SYNTHESIS_PROMPT = """Synthesize the following multiple LLM analyses into a unified editorial profile.

Llama3 Analysis:
{llama3_analysis}

Mistral Analysis:
{mistral_analysis}

Phi3 Analysis:
{phi3_analysis}

IMPORTANT: 
- Use Phi3's activity_domains (they are more detailed and specific than Llama3's)
- Extract ALL values from the analyses provided above, do NOT use placeholder or example values
- Respond ONLY with valid JSON. Do not include any text before or after the JSON. Do not use escaped quotes or nested JSON strings. All values must be properly formatted JSON (objects use {{}}, arrays use [], strings use "").

Create a comprehensive editorial profile that combines all insights. Format as JSON:
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
    "content_structure": {{
        "average_word_count": ...,
        "average_paragraph_count": ...,
        "heading_patterns": {{"H2": ..., "H3": ...}},
        "media_usage": {{"images": ..., "videos": ...}},
        "internal_linking": ...
    }},
    "keywords": {{
        "primary_keywords": [...],
        "keyword_density": {{"keyword": density_percentage}},
        "semantic_keywords": [...]
    }},
    "style_features": {{
        "sentence_length_avg": "...",
        "reading_level": "...",
        "formality_score": ...
    }}
}}
"""

# Competitor Search Prompts

COMPETITOR_FILTERING_PROMPT = """You are evaluating candidate domains to identify competitors for the target domain.

Target domain: {domain}

Context about the target domain:
{context}

Candidate domains to evaluate:
{candidates}

IMPORTANT EXCLUSIONS - DO NOT INCLUDE:
- Government services (.gouv.fr, .ameli.fr, .caf.fr, .francetravail.fr, .parcoursup.fr, .labanquepostale.fr)
- E-commerce sites (online shopping, retail stores)
- Public services and administration websites
- News/media websites
- Academic/educational institutions (.edu.fr, .ac.fr)

ONLY VALID COMPETITORS:
- ESN (Entreprise de Services du Numérique)
- SSII (Société de Services en Ingénierie Informatique)
- Digital agencies (agences digitales)
- IT services companies (sociétés de services informatiques)
- Software development companies
- IT consulting firms

For each candidate domain, determine if it is a relevant competitor. Rate each one with:
- relevance_score: 0.0 to 1.0 
  * 0.8-1.0 = direct competitor (same sector: ESN/SSII/IT services, similar services, same target market)
  * 0.6-0.79 = indirect competitor (only if same sector ESN/SSII/IT services but different focus)
  * 0.0-0.59 = not a competitor (different industry, government service, e-commerce, etc.)
- confidence_score: 0.0 to 1.0 (how confident you are in your assessment)
- reason: Brief explanation of why it is or isn't a competitor

Return your response as JSON in this format:
{{
    "competitors": [
        {{
            "domain": "example.com",
            "relevance_score": 0.85,
            "confidence_score": 0.9,
            "reason": "ESN/SSII with similar IT services and target market"
        }},
        {{
            "domain": "other.com",
            "relevance_score": 0.3,
            "confidence_score": 0.8,
            "reason": "Government service / e-commerce / different industry, not a competitor"
}}
    ]
}}

Only include domains that are actual competitors (relevance_score >= 0.6) AND in the ESN/SSII/IT services sector. 
Exclude all government services, e-commerce, and non-IT companies.
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

