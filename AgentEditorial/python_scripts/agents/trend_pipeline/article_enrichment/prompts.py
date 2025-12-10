"""LLM prompts for article enrichment."""

# Prompt 1: Outline Enrichment
OUTLINE_ENRICHMENT_PROMPT = """Tu es un expert en structuration éditoriale. Transforme cet outline générique en structure détaillée et actionnable.

**ARTICLE ORIGINAL:**
- Titre: {title}
- Hook: {hook}
- Outline actuel: {outline}

**CONTEXTE CLIENT:**
- Ton éditorial: {editorial_tone}
- Niveau de langue: {language_level}
- Public cible: {target_audience}
- Domaines d'activité: {activity_domains}
- Mots-clés principaux: {primary_keywords}

**STATISTIQUES DE TENDANCE:**
- Volume d'articles concurrents: {competitor_volume}
- Vélocité de croissance: {velocity}
- Score de priorité: {priority_score}
- Gap de couverture: {coverage_gap}

**INSTRUCTIONS:**
1. Crée une structure détaillée avec 3-5 sections principales
2. Chaque section doit avoir 2-4 sous-sections concrètes
3. Intègre des points clés spécifiques pour chaque section
4. Ajoute des statistiques pertinentes dans les sections appropriées
5. Adapte le ton et le style au contexte client
6. Utilise le vocabulaire et les domaines d'activité du client

**FORMAT DE RÉPONSE (JSON STRICT OBLIGATOIRE):**
IMPORTANT: Réponds UNIQUEMENT avec du JSON valide, sans texte avant ou après. Utilise des guillemets doubles.

```json
{{
  "introduction": {{
    "title": "Titre de l'introduction",
    "subsections": ["Sous-section 1", "Sous-section 2"],
    "key_points": ["Point clé 1", "Point clé 2"],
    "statistics": ["Statistique 1", "Statistique 2"]
  }},
  "section_1": {{
    "title": "Titre section 1",
    "subsections": ["Sous-section 1.1", "Sous-section 1.2", "Sous-section 1.3"],
    "key_points": ["Point clé 1", "Point clé 2", "Point clé 3"],
    "statistics": ["Statistique pertinente"]
  }},
  "section_2": {{
    "title": "Titre section 2",
    "subsections": ["Sous-section 2.1", "Sous-section 2.2"],
    "key_points": ["Point clé 1", "Point clé 2"],
    "statistics": ["Statistique pertinente"]
  }},
  "section_3": {{
    "title": "Titre section 3",
    "subsections": ["Sous-section 3.1", "Sous-section 3.2"],
    "key_points": ["Point clé 1", "Point clé 2"],
    "statistics": []
  }},
  "conclusion": {{
    "title": "Conclusion",
    "subsections": ["Synthèse des points clés", "Appel à l'action"],
    "key_points": ["Point de synthèse 1", "Point de synthèse 2"],
    "call_to_action": "Message d'appel à l'action personnalisé"
  }}
}}
```

Réponds uniquement avec le JSON ci-dessus, sans commentaires ni explications.
"""

# Prompt 2: Hook Personalization
HOOK_PERSONALIZATION_PROMPT = """Tu es un rédacteur expert. Personnalise ce hook d'article selon le contexte client.

**HOOK ORIGINAL:**
{hook}

**CONTEXTE CLIENT:**
- Ton éditorial: {editorial_tone}
- Public cible: {target_audience}
- Domaines d'activité: {activity_domains}
- Mots-clés à privilégier: {primary_keywords}
- Style: {style_features}

**INSTRUCTIONS:**
1. Adapte le ton au style éditorial du client
2. Utilise le vocabulaire et les domaines d'activité du client
3. Cible le public spécifique (business owners, IT managers, etc.)
4. Garde l'accroche percutante mais personnalisée
5. Longueur: 2-3 phrases (environ {target_length} mots)

**FORMAT DE RÉPONSE (JSON STRICT OBLIGATOIRE):**
IMPORTANT: Réponds UNIQUEMENT avec du JSON valide, sans texte avant ou après.

```json
{{
  "personalized_hook": "Hook personnalisé adapté au contexte client...",
  "tone_adaptation": "Explication de l'adaptation du ton",
  "keywords_used": ["mot-clé1", "mot-clé2"]
}}
```

Réponds uniquement avec le JSON ci-dessus, sans commentaires ni explications.
"""

# Prompt 3: Statistics Integration
STATISTICS_INTEGRATION_PROMPT = """Tu es un analyste de données. Intègre ces statistiques dans le contenu de l'article de manière naturelle.

**CONTENU DE LA SECTION:**
{section_content}

**STATISTIQUES DISPONIBLES:**
- Volume d'articles concurrents: {competitor_volume}
- Vélocité de croissance: {velocity} (tendance: {velocity_trend})
- Score de priorité: {priority_score}
- Gap de couverture: {coverage_gap}
- Diversité des sources: {source_diversity}
- Fraîcheur du sujet: {freshness_ratio}

**CONTEXTE CLIENT:**
- Domaines d'activité: {activity_domains}
- Ton éditorial: {editorial_tone}

**INSTRUCTIONS:**
1. Intègre 2-3 statistiques pertinentes de manière naturelle
2. Formule les statistiques de façon compréhensible (ex: "87% des entreprises" plutôt que "0.87")
3. Adapte le langage au ton éditorial
4. Crée des phrases qui contextualisent les statistiques
5. Évite les listes de chiffres, privilégie l'intégration narrative

**FORMAT DE RÉPONSE (JSON STRICT OBLIGATOIRE):**
IMPORTANT: Réponds UNIQUEMENT avec du JSON valide, sans texte avant ou après.

```json
{{
  "enriched_content": "Contenu avec statistiques intégrées de manière naturelle...",
  "statistics_used": [
    {{"stat": "Volume concurrents", "value": "{competitor_volume}", "formulation": "..."}},
    {{"stat": "Vélocité", "value": "{velocity}", "formulation": "..."}}
  ]
}}
```

Réponds uniquement avec le JSON ci-dessus, sans commentaires ni explications.
"""

# Prompt 4: Complete Article Enrichment (All-in-one)
COMPLETE_ENRICHMENT_PROMPT = """Tu es un expert éditorial. Enrichis complètement cette recommandation d'article en utilisant le contexte client et les statistiques.

**ARTICLE ORIGINAL:**
- Titre: {title}
- Hook: {hook}
- Outline: {outline}
- Effort: {effort_level}
- Score différenciation: {differentiation_score}

**CONTEXTE CLIENT:**
- Ton éditorial: {editorial_tone}
- Niveau de langue: {language_level}
- Public cible: {target_audience}
- Domaines d'activité: {activity_domains}
- Mots-clés principaux: {primary_keywords}
- Style: {style_features}

**STATISTIQUES DE TENDANCE:**
- Volume concurrents: {competitor_volume}
- Vélocité: {velocity} (tendance: {velocity_trend})
- Priorité: {priority_score}
- Gap couverture: {coverage_gap}
- Diversité sources: {source_diversity}

**INSTRUCTIONS:**
1. Génère un outline détaillé (3-5 sections avec sous-sections)
2. Personnalise le hook selon le contexte client
3. Intègre des statistiques pertinentes dans chaque section
4. Adapte le ton et le vocabulaire au client
5. Ajoute des points clés actionnables

**FORMAT DE RÉPONSE (JSON STRICT OBLIGATOIRE):**
IMPORTANT: Réponds UNIQUEMENT avec du JSON valide, sans texte avant ou après.

```json
{{
  "enriched_hook": "Hook personnalisé...",
  "enriched_outline": {{
    "introduction": {{
      "title": "...",
      "subsections": [...],
      "key_points": [...],
      "statistics": [...]
    }},
    "section_1": {{
      "title": "...",
      "subsections": [...],
      "key_points": [...],
      "statistics": [...]
    }},
    "section_2": {{...}},
    "section_3": {{...}},
    "conclusion": {{
      "title": "Conclusion",
      "subsections": [...],
      "key_points": [...],
      "call_to_action": "..."
    }}
  }},
  "statistics_integrated": [
    {{"section": "introduction", "stat": "...", "value": "..."}},
    {{"section": "section_1", "stat": "...", "value": "..."}}
  ],
  "personalization_notes": "Notes sur l'adaptation au contexte client"
}}
```

Réponds uniquement avec le JSON ci-dessus, sans commentaires ni explications.
"""



