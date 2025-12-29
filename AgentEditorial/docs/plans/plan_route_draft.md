# Plan d'implémentation : Route POST /api/v1/draft

## Objectif
Créer une route POST `/draft` qui génère un brouillon d'article complet de manière synchrone à partir d'un `topic_id`, incluant le contenu, les métriques SEO/readability, et les suggestions d'images.

## Structure de la route

**Endpoint** : `POST /api/v1/draft`

**Payload attendu** :
```json
{
  "topic_id": "edge-cloud-hybride"
}
```

**Réponse attendue** :
```json
{
  "id": "draft-edge-cloud-hybride",
  "topic_id": "edge-cloud-hybride",
  "title": "L'avenir de l'edge computing dans le cloud hybride : Guide complet 2024",
  "subtitle": "Comment les architectures distribuées révolutionnent la performance et réduisent la latence",
  "content": "## Introduction\n\nL'edge computing représente...",
  "metadata": {
    "word_count": 547,
    "reading_time": "8 min",
    "seo_score": 87,
    "readability_score": 72
  },
  "suggestions": {
    "images": [...],
    "seo": [...],
    "readability": [...]
  }
}
```

## Fichiers à modifier/créer

### 1. Créer les schémas de requête/réponse

**Fichier** : `python_scripts/api/schemas/draft.py` (nouveau fichier)

Créer les schémas Pydantic :
- `DraftRequest` : Requête avec `topic_id`
- `ImageSuggestion` : Suggestion d'image (description, type, placement)
- `DraftSuggestions` : Suggestions (images, seo, readability)
- `DraftMetadata` : Métadonnées (word_count, reading_time, seo_score, readability_score)
- `DraftResponse` : Réponse complète du draft

### 2. Créer les fonctions utilitaires

**Fichier** : `python_scripts/api/routers/draft.py` (nouveau fichier)

#### 2.1. Fonction pour parser le review result
```python
def _parse_review_result(review_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse ReviewCrew raw_review to extract seo_score, readability_score, improvements.
    
    Args:
        review_result: Review result from ReviewCrew
        
    Returns:
        Dictionary with parsed scores and suggestions
    """
    # Parse JSON from raw_review string
    # Extract seo_score, readability_score, improvements
    # Return structured data
```

#### 2.2. Fonction pour générer des suggestions d'images
```python
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
    # Analyze plan_json sections
    # Extract key sections (introduction, sections principales, conclusion)
    # Generate suggestions for each section
    # Return list of ImageSuggestion
```

#### 2.3. Fonction pour calculer le reading_time
```python
def _calculate_reading_time(word_count: int) -> str:
    """
    Calculate reading time from word count.
    
    Args:
        word_count: Number of words
        
    Returns:
        Reading time string (e.g., "8 min")
    """
    # Average reading speed: 200-250 words/min
    # Calculate and format
```

#### 2.4. Fonction pour extraire le subtitle
```python
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
    # Use hook if available
    # Fallback to synthesis
    # Fallback to generate from title
```

### 3. Implémenter la fonction principale de génération

**Fichier** : `python_scripts/api/routers/draft.py`

Créer la fonction `_generate_draft_sync(db, topic_id_slug, site_client, domain_topic) -> DraftResponse` qui :

1. **Récupère les données du topic** :
   - Valide le site_profile et domain_topic
   - Extrait le topic_id depuis le slug
   - Récupère TopicCluster, ArticleRecommendation, TrendAnalysis

2. **Prépare les paramètres de génération** :
   - Topic depuis cluster.label ou ArticleRecommendation.title
   - Keywords depuis cluster.top_terms
   - Tone depuis site_profile.editorial_tone
   - Target words (par défaut 2000)
   - Language (par défaut "fr")

3. **Génère l'article de manière synchrone** :
   - Crée un GeneratedArticle en base (pour avoir un article_id)
   - Exécute PlanningCrew pour obtenir le plan
   - Exécute WritingCrew pour générer le contenu markdown
   - Exécute ReviewCrew pour calculer les métriques
   - Parse le review_result pour extraire seo_score, readability_score, improvements

4. **Génère les suggestions** :
   - Suggestions d'images basées sur le plan_json
   - Suggestions SEO depuis improvements du review
   - Suggestions readability depuis improvements du review

5. **Construit la réponse** :
   - ID : "draft-{topic_id_slug}"
   - Title : depuis ArticleRecommendation.title ou cluster.label
   - Subtitle : depuis hook ou synthesis
   - Content : content_markdown généré
   - Metadata : word_count, reading_time, seo_score, readability_score
   - Suggestions : images, seo, readability

### 4. Créer la route endpoint

**Fichier** : `python_scripts/api/routers/draft.py`

Créer la route `POST /draft` qui :
- Accepte `DraftRequest` en body
- Appelle `_generate_draft_sync`
- Retourne `DraftResponse`
- Gère les erreurs (404 si topic non trouvé, 500 si génération échoue)

### 5. Enregistrer la route dans main.py

**Fichier** : `python_scripts/api/main.py`

Ajouter :
```python
from python_scripts.api.routers import draft

app.include_router(draft.router, prefix="/api/v1")
```

## Détails d'implémentation

### Parsing du review_result

Le `ReviewCrew` retourne `{"raw_review": "..."}` qui contient un JSON string. Il faut :
1. Parser le JSON depuis la string
2. Extraire `seo_score`, `readability_score`
3. Extraire `improvements` (liste de suggestions)
4. Séparer les suggestions SEO des suggestions readability

### Génération des suggestions d'images

Basée sur le `plan_json` qui contient :
- `title`, `h1`
- `sections` : liste avec `h2`, `objectifs`, `points clés`

Pour chaque section importante :
- Identifier le type d'image approprié (Infographie, Chart, Timeline, Illustration)
- Générer une description basée sur le contenu de la section
- Déterminer le placement (après l'introduction, section X, etc.)

### Gestion du temps de génération

La génération synchrone peut prendre 30-60 secondes. Options :
1. **Timeout** : Définir un timeout (ex: 120 secondes)
2. **Optimisation** : Ne pas générer d'images réelles, seulement des suggestions
3. **Cache** : Vérifier si un draft existe déjà pour ce topic_id

### Gestion des erreurs

- 400 : Format topic_id invalide
- 404 : Topic, site_profile, ou domain non trouvé
- 500 : Erreur lors de la génération (avec message détaillé)

## Ordre d'implémentation

1. Créer les schémas Pydantic dans `draft.py`
2. Créer le fichier `routers/draft.py` avec les fonctions utilitaires
3. Implémenter `_generate_draft_sync` avec génération synchrone
4. Créer la route POST `/draft`
5. Enregistrer la route dans `main.py`
6. Tester avec un topic_id existant

## Notes importantes

- La génération est **synchrone** : la requête attend la fin de la génération
- Les **images ne sont pas générées** : seulement des suggestions
- Le **ReviewCrew** doit être exécuté pour obtenir les métriques
- Le **plan_json** doit être parsé pour générer les suggestions d'images
- Utiliser les données existantes (ArticleRecommendation, TrendAnalysis) pour enrichir le draft

## Données disponibles vs à générer

### Disponibles
- TopicCluster : label, top_terms
- ArticleRecommendation : title, hook, outline
- TrendAnalysis : synthesis
- SiteProfile : editorial_tone, target_audience

### À générer
- Content markdown : via WritingCrew
- Plan JSON : via PlanningCrew
- SEO/Readability scores : via ReviewCrew
- Suggestions d'images : basées sur plan_json
- Suggestions SEO/Readability : depuis ReviewCrew improvements




