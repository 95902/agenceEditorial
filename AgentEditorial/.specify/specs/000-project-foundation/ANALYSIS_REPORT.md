openapi: 3.0.3
info:
  title: Agent Éditorial & Concurrentiel API
  version: 1.0.0
  description: |
    API REST pour le système d'analyse éditoriale et concurrentielle multi-agents.
    
    **Rate Limiting**: 100 req/min par défaut, 10 req/min pour endpoints d'analyse.
    
    **Note**: Pas d'authentification pour MVP (rate limiting par IP uniquement).
  contact:
    name: Development Team
  license:
    name: Proprietary

servers:
  - url: http://localhost:8000/api/v1
    description: Local development server
  - url: https://api.example.com/api/v1
    description: Production server (TBD)

tags:
  - name: Sites
    description: Analyse éditoriale de sites web
  - name: Competitors
    description: Recherche et gestion de concurrents
  - name: Scraping
    description: Scraping d'articles concurrents
  - name: Trends
    description: Analyse de tendances et topic modeling
  - name: Executions
    description: Suivi d'exécution de workflows
  - name: Health
    description: Health checks et monitoring

paths:
  /sites/analyze:
    post:
      tags:
        - Sites
      summary: Lancer une analyse éditoriale
      description: Lance une analyse éditoriale complète d'un site web en arrière-plan. Retourne immédiatement avec un execution_id pour suivre la progression.
      operationId: analyzeSite
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/SiteAnalysisRequest'
            example:
              domain: "example.com"
              max_pages: 50
      responses:
        '202':
          description: Analyse lancée avec succès
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ExecutionResponse'
        '400':
          description: Requête invalide
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        '429':
          description: Rate limit exceeded
          headers:
            Retry-After:
              schema:
                type: integer
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /sites:
    get:
      tags:
        - Sites
      summary: Lister les sites analysés
      description: Retourne la liste de tous les sites analysés avec leurs dernières analyses.
      operationId: listSites
      parameters:
        - name: limit
          in: query
          schema:
            type: integer
            default: 50
            minimum: 1
            maximum: 200
        - name: offset
          in: query
          schema:
            type: integer
            default: 0
            minimum: 0
      responses:
        '200':
          description: Liste des sites
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SitesListResponse'

  /sites/{domain}:
    get:
      tags:
        - Sites
      summary: Obtenir le profil d'un site
      description: Retourne le profil éditorial complet d'un domaine.
      operationId: getSiteProfile
      parameters:
        - name: domain
          in: path
          required: true
          schema:
            type: string
            pattern: '^[a-z0-9.-]+\.[a-z]{2,}$'
          example: "example.com"
      responses:
        '200':
          description: Profil éditorial
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SiteProfileResponse'
        '404':
          description: Site non trouvé
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /sites/{domain}/history:
    get:
      tags:
        - Sites
      summary: Historique d'analyses d'un site
      description: Retourne l'historique des analyses d'un domaine avec évolution des métriques.
      operationId: getSiteHistory
      parameters:
        - name: domain
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: Historique des analyses
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SiteHistoryResponse'

  /competitors/search:
    post:
      tags:
        - Competitors
      summary: Rechercher des concurrents
      description: Identifie automatiquement les concurrents d'un site analysé.
      operationId: searchCompetitors
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CompetitorSearchRequest'
      responses:
        '202':
          description: Recherche lancée
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ExecutionResponse'
        '400':
          description: Requête invalide

  /competitors/{domain}:
    get:
      tags:
        - Competitors
      summary: Obtenir la liste des concurrents
      description: Retourne la liste des concurrents identifiés pour un domaine.
      operationId: getCompetitors
      parameters:
        - name: domain
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: Liste des concurrents
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CompetitorsListResponse'

  /competitors/{domain}/validate:
    post:
      tags:
        - Competitors
      summary: Valider/ajuster la liste des concurrents
      description: Permet de valider, ajouter ou exclure des concurrents de la liste proposée.
      operationId: validateCompetitors
      parameters:
        - name: domain
          in: path
          required: true
          schema:
            type: string
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CompetitorValidationRequest'
            example:
              validated: ["competitor1.fr", "competitor2.fr"]
              added: ["competitor3.fr"]
              excluded: ["media-generaliste.fr"]
      responses:
        '200':
          description: Liste validée avec succès
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CompetitorsListResponse'
        '400':
          description: Requête invalide
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /scraping/competitors:
    post:
      tags:
        - Scraping
      summary: Scraper les articles des concurrents
      description: Lance le scraping des articles de blog pour une liste de concurrents.
      operationId: scrapeCompetitors
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ScrapingRequest'
      responses:
        '202':
          description: Scraping lancé
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ExecutionResponse'

  /scraping/articles:
    get:
      tags:
        - Scraping
      summary: Lister les articles scrapés
      description: Retourne la liste des articles scrapés avec filtres.
      operationId: listArticles
      parameters:
        - name: domain
          in: query
          schema:
            type: string
        - name: limit
          in: query
          schema:
            type: integer
            default: 50
        - name: offset
          in: query
          schema:
            type: integer
            default: 0
      responses:
        '200':
          description: Liste des articles
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ArticlesListResponse'

  /trends/analyze:
    post:
      tags:
        - Trends
      summary: Analyser les tendances avec BERTopic
      description: Lance une analyse BERTopic sur les articles concurrents pour découvrir les topics dominants.
      operationId: analyzeTrends
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/TrendAnalysisRequest'
      responses:
        '202':
          description: Analyse lancée
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ExecutionResponse'

  /trends/topics:
    get:
      tags:
        - Trends
      summary: Obtenir les topics découverts
      description: Retourne les topics BERTopic découverts pour une période donnée.
      operationId: getTopics
      parameters:
        - name: time_window_days
          in: query
          schema:
            type: integer
            enum: [7, 30, 90]
            default: 30
      responses:
        '200':
          description: Topics découverts
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/TopicsResponse'

  /trends/gaps:
    get:
      tags:
        - Trends
      summary: Identifier les gaps de contenu
      description: Compare les topics du site client avec ceux des concurrents pour identifier les gaps.
      operationId: getContentGaps
      parameters:
        - name: client_domain
          in: query
          required: true
          schema:
            type: string
      responses:
        '200':
          description: Gaps identifiés
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ContentGapsResponse'

  /executions/{execution_id}:
    get:
      tags:
        - Executions
      summary: Obtenir le statut d'une exécution
      description: Retourne le statut et les résultats d'une exécution de workflow.
      operationId: getExecutionStatus
      parameters:
        - name: execution_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        '200':
          description: Statut de l'exécution
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ExecutionStatusResponse'
        '404':
          description: Exécution non trouvée

  /executions/{execution_id}/stream:
    get:
      tags:
        - Executions
      summary: Stream de progression en temps réel (WebSocket)
      description: Connexion WebSocket pour recevoir les mises à jour de progression en temps réel.
      operationId: streamExecutionProgress
      parameters:
        - name: execution_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        '101':
          description: Switching Protocols (WebSocket)

  /health:
    get:
      tags:
        - Health
      summary: Health check
      description: Vérifie l'état de santé des services (PostgreSQL, Qdrant, Ollama).
      operationId: healthCheck
      responses:
        '200':
          description: Services opérationnels
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/HealthResponse'
        '503':
          description: Service indisponible

components:
  schemas:
    SiteAnalysisRequest:
      type: object
      required:
        - domain
      properties:
        domain:
          type: string
          pattern: '^[a-z0-9.-]+\.[a-z]{2,}$'
          example: "example.com"
          description: Nom de domaine (sans protocole)
        max_pages:
          type: integer
          minimum: 10
          maximum: 200
          default: 50
          description: Nombre maximum de pages à analyser

    ExecutionResponse:
      type: object
      required:
        - execution_id
        - status
        - start_time
      properties:
        execution_id:
          type: string
          format: uuid
        status:
          type: string
          enum: [pending, running, completed, failed]
        start_time:
          type: string
          format: date-time
        estimated_duration_minutes:
          type: integer

    ExecutionStatusResponse:
      allOf:
        - $ref: '#/components/schemas/ExecutionResponse'
        - type: object
          properties:
            end_time:
              type: string
              format: date-time
            duration_seconds:
              type: integer
            progress_percent:
              type: number
              format: float
            result:
              type: object

    SitesListResponse:
      type: object
      properties:
        sites:
          type: array
          items:
            $ref: '#/components/schemas/SiteSummary'
        total:
          type: integer
        limit:
          type: integer
        offset:
          type: integer

    SiteSummary:
      type: object
      properties:
        domain:
          type: string
        analysis_date:
          type: string
          format: date-time
        status:
          type: string
          enum: [completed, pending, failed]
        pages_analyzed:
          type: integer

    SiteProfileResponse:
      type: object
      properties:
        domain:
          type: string
        analysis_date:
          type: string
          format: date-time
        language_level:
          type: string
          enum: [simple, intermediate, advanced, expert]
        editorial_tone:
          type: string
          enum: [professional, conversational, technical, marketing]
        target_audience:
          type: object
        activity_domains:
          type: array
          items:
            type: string
        content_structure:
          type: object
        keywords:
          type: object
        style_features:
          type: object
        pages_analyzed:
          type: integer

    SiteHistoryResponse:
      type: object
      properties:
        domain:
          type: string
        analyses:
          type: array
          items:
            type: object

    CompetitorSearchRequest:
      type: object
      required:
        - domain
      properties:
        domain:
          type: string
        max_competitors:
          type: integer
          default: 10
          minimum: 3
          maximum: 20

    CompetitorsListResponse:
      type: object
      properties:
        domain:
          type: string
        competitors:
          type: array
          items:
            type: object
            properties:
              domain:
                type: string
              relevance_score:
                type: number
                format: float

    CompetitorValidationRequest:
      type: object
      properties:
        validated:
          type: array
          items:
            type: string
          description: Liste des domaines à marquer comme validés
        added:
          type: array
          items:
            type: string
          description: Liste des domaines à ajouter manuellement
        excluded:
          type: array
          items:
            type: string
          description: Liste des domaines à exclure

    ScrapingRequest:
      type: object
      required:
        - domains
      properties:
        domains:
          type: array
          items:
            type: string
          minItems: 1
        max_articles_per_domain:
          type: integer
          default: 100

    ArticlesListResponse:
      type: object
      properties:
        articles:
          type: array
          items:
            type: object
        total:
          type: integer

    TrendAnalysisRequest:
      type: object
      properties:
        domains:
          type: array
          items:
            type: string
        time_window_days:
          type: integer
          enum: [7, 30, 90]
          default: 30

    TopicsResponse:
      type: object
      properties:
        topics:
          type: array
          items:
            type: object
        analysis_date:
          type: string
          format: date-time
        time_window_days:
          type: integer

    ContentGapsResponse:
      type: object
      properties:
        client_domain:
          type: string
        gaps:
          type: array
          items:
            type: object
            properties:
              topic:
                type: string
              gap_score:
                type: number
                format: float
              recommendation:
                type: string

    HealthResponse:
      type: object
      properties:
        status:
          type: string
          enum: [healthy, degraded, unhealthy]
        services:
          type: object
          properties:
            postgresql:
              type: object
              properties:
                status:
                  type: string
                latency_ms:
                  type: number
            qdrant:
              type: object
              properties:
                status:
                  type: string
                collections_count:
                  type: integer
            ollama:
              type: object
              properties:
                status:
                  type: string
                models:
                  type: array
                  items:
                    type: string

    ErrorResponse:
      type: object
      required:
        - error
        - message
      properties:
        error:
          type: string
        message:
          type: string
        details:
          type: object

  securitySchemes: {}
  # Pas d'authentification pour MVP - rate limiting par IP uniquement