"""LLM prompts for trend analysis (ETAGE 3)."""

# Prompt 1: Trend Synthesis (Editorial Analyst)
TREND_SYNTHESIS_PROMPT = """Tu es un analyste éditorial expert. Analyse cette tendance thématique et fournis une synthèse structurée.

**TENDANCE:**
- Label: {topic_label}
- Mots-clés principaux: {keywords}
- Volume: {volume} articles sur {time_period} jours
- Vélocité: {velocity} (tendance: {velocity_trend})
- Diversité des sources: {source_diversity} sources différentes

**ARTICLES REPRÉSENTATIFS:**
{representative_docs}

**INSTRUCTIONS:**
1. Résume la tendance en 2-3 phrases (contexte, importance, dynamique)
2. Identifie les angles saturés (déjà beaucoup traités)
3. Suggère des opportunités éditoriales (angles peu exploités)

**FORMAT DE RÉPONSE (JSON):**
```json
{{
  "synthesis": "...",
  "saturated_angles": ["angle1", "angle2", "angle3"],
  "opportunities": ["opportunity1", "opportunity2", "opportunity3"],
  "editorial_potential": "high|medium|low"
}}
```
"""

# Prompt 2: Article Angle Generation (Editor-in-Chief)
ANGLE_GENERATION_PROMPT = """Tu es un rédacteur en chef créatif. Génère des angles d'articles originaux pour cette tendance.

**TENDANCE:**
- Thème: {topic_label}
- Mots-clés: {keywords}
- Angles saturés à éviter: {saturated_angles}

**OPPORTUNITÉS IDENTIFIÉES:**
{opportunities}

**INSTRUCTIONS:**
Génère {num_angles} propositions d'articles avec:
1. Un titre accrocheur et différenciant
2. Un hook d'introduction (2-3 phrases)
3. Un plan en 3-5 points
4. Un niveau d'effort estimé (easy/medium/complex)
5. Un score de différenciation (0-1)

**FORMAT DE RÉPONSE (JSON):**
```json
{{
  "articles": [
    {{
      "title": "...",
      "hook": "...",
      "outline": ["point1", "point2", "point3"],
      "effort_level": "easy|medium|complex",
      "differentiation_score": 0.8
    }}
  ]
}}
```
"""

# Prompt 3: Outlier Analysis (Strategic Monitor)
OUTLIER_ANALYSIS_PROMPT = """Tu es un veilleur stratégique spécialisé dans la détection de signaux faibles.

**DOCUMENTS OUTLIERS (non classifiés):**
{outlier_summaries}

**CONTEXTE:**
Ces documents n'ont pas été classés dans les topics principaux. Ils peuvent représenter:
- Des signaux faibles / tendances émergentes
- Du bruit / contenu hors-sujet
- Des innovations ou disruptions potentielles

**INSTRUCTIONS:**
1. Analyse les points communs entre ces outliers
2. Identifie s'ils représentent un signal faible cohérent
3. Évalue le potentiel de disruption (0-1)
4. Recommande une action: "early_adopter" (agir maintenant) ou "wait" (surveiller)

**FORMAT DE RÉPONSE (JSON):**
```json
{{
  "common_thread": "...",
  "is_weak_signal": true|false,
  "disruption_potential": 0.7,
  "recommendation": "early_adopter|wait",
  "justification": "..."
}}
```
"""

