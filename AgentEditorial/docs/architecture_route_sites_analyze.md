# Diagramme d'Architecture - Route POST /api/v1/sites/analyze

## Vue d'ensemble

Ce document présente l'architecture complète de la route `POST /api/v1/sites/analyze` avec des diagrammes de séquence, de composants et de flux de données.

## Diagramme de Séquence

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI Router<br/>/api/v1/sites/analyze
    participant DB as PostgreSQL
    participant Orchestrator as EditorialAnalysisOrchestrator
    participant Sitemap as Sitemap Discovery
    participant Crawler as Page Crawler
    participant LLM as LLM Analysis Agent<br/>(Multi-LLM)
    participant Scraper as Scraping Agent<br/>(Background)

    Client->>API: POST /api/v1/sites/analyze<br/>{domain, max_pages}
    
    API->>DB: CREATE workflow_execution<br/>(status: pending)
    DB-->>API: execution_id
    
    API->>API: Start background task
    API-->>Client: 202 Accepted<br/>{execution_id, status: pending}
    
    Note over Orchestrator,Scraper: Background Task Execution
    
    Orchestrator->>DB: UPDATE workflow_execution<br/>(status: running)
    
    rect rgb(200, 220, 255)
        Note over Orchestrator,Sitemap: Phase 1: Discovery
        Orchestrator->>Sitemap: get_sitemap_urls(domain)
        Sitemap-->>Orchestrator: List of URLs
    end
    
    rect rgb(220, 255, 220)
        Note over Orchestrator,Crawler: Phase 2: Crawling
        Orchestrator->>Crawler: crawl_multiple_pages(urls)
        Crawler->>Crawler: Check robots.txt (basic)
        Crawler->>Crawler: Fetch pages (httpx)
        Crawler-->>Orchestrator: Crawled pages content
    end
    
    rect rgb(255, 255, 200)
        Note over Orchestrator,LLM: Phase 3: Analysis
        Orchestrator->>Orchestrator: Combine content
        Orchestrator->>LLM: execute(combined_content)
        
        LLM->>LLM: Analyze with Llama3:8b
        LLM->>LLM: Analyze with Mistral:7b
        LLM->>LLM: Analyze with Phi3:medium
        LLM->>LLM: Synthesize results
        
        LLM-->>Orchestrator: Analysis results
    end
    
    rect rgb(255, 220, 220)
        Note over Orchestrator,DB: Phase 4: Persistence
        Orchestrator->>DB: READ site_profile (by domain)
        alt Profile exists
            DB-->>Orchestrator: Existing profile
        else Profile not found
            Orchestrator->>DB: CREATE site_profile
            DB-->>Orchestrator: New profile
        end
        
        Orchestrator->>DB: UPDATE site_profile<br/>(with analysis results)
        Orchestrator->>DB: CREATE site_analysis_result
        Orchestrator->>DB: UPDATE workflow_execution<br/>(status: completed)
    end
    
    rect rgb(240, 240, 255)
        Note over Orchestrator,Scraper: Phase 5: Auto-Scraping (Background)
        Orchestrator->>Scraper: run_scraping_workflow<br/>(is_client_site=True)
        
        Scraper->>Scraper: Discovery (API, RSS, Sitemap)
        Scraper->>Scraper: Scoring & Selection
        Scraper->>Scraper: Extraction & Validation
        
        Scraper->>DB: CREATE client_articles
        Scraper->>DB: CREATE/UPDATE site_discovery_profiles
        Scraper->>DB: CREATE url_discovery_scores
        Scraper->>DB: CREATE discovery_logs
        
        Scraper->>Scraper: Index in Qdrant<br/>({domain}_client_articles)
        
        Scraper-->>Orchestrator: Scraping results
    end
    
    Orchestrator-->>API: Workflow completed
```

## Diagramme de Composants

```mermaid
graph TB
    subgraph "API Layer"
        API[FastAPI Router<br/>/api/v1/sites/analyze]
        BG[Background Tasks<br/>FastAPI]
    end
    
    subgraph "Orchestration Layer"
        ORCH[EditorialAnalysisOrchestrator]
    end
    
    subgraph "Agent Layer"
        AGENT_ANALYSIS[EditorialAnalysisAgent<br/>Multi-LLM]
        AGENT_SCRAPING[ScrapingAgent<br/>Enhanced]
    end
    
    subgraph "Service Layer"
        SITEMAP[Sitemap Discovery<br/>get_sitemap_urls]
        CRAWLER[Page Crawler<br/>crawl_multiple_pages]
        LLM_FACTORY[LLM Factory<br/>Ollama]
    end
    
    subgraph "Data Layer"
        DB[(PostgreSQL)]
        QDRANT[(Qdrant<br/>Vector Store)]
    end
    
    subgraph "External Services"
        OLLAMA[Ollama<br/>LLM Server]
        TARGET[Target Website<br/>HTTP]
    end
    
    API -->|1. Create execution| DB
    API -->|2. Start background| BG
    BG -->|3. Execute workflow| ORCH
    
    ORCH -->|Step 1| SITEMAP
    SITEMAP -->|Fetch sitemap| TARGET
    
    ORCH -->|Step 2| CRAWLER
    CRAWLER -->|Fetch pages| TARGET
    
    ORCH -->|Step 3| AGENT_ANALYSIS
    AGENT_ANALYSIS -->|Use LLMs| LLM_FACTORY
    LLM_FACTORY -->|API calls| OLLAMA
    
    ORCH -->|Step 4-7| DB
    ORCH -->|Step 8| DB
    
    ORCH -->|Step 9| AGENT_SCRAPING
    AGENT_SCRAPING -->|Discovery| TARGET
    AGENT_SCRAPING -->|Save articles| DB
    AGENT_SCRAPING -->|Index vectors| QDRANT
    
    style API fill:#4a90e2,color:#fff
    style ORCH fill:#50c878,color:#fff
    style AGENT_ANALYSIS fill:#ff6b6b,color:#fff
    style AGENT_SCRAPING fill:#ff6b6b,color:#fff
    style DB fill:#f39c12,color:#fff
    style QDRANT fill:#9b59b6,color:#fff
    style OLLAMA fill:#3498db,color:#fff
```

## Diagramme de Flux de Données

```mermaid
flowchart TD
    START([Client Request<br/>POST /api/v1/sites/analyze])
    
    CREATE_EXEC[Create workflow_execution<br/>status: pending]
    
    START --> CREATE_EXEC
    
    CREATE_EXEC --> DISCOVER[Step 1: Discover URLs<br/>via Sitemap]
    
    DISCOVER --> CRAWL[Step 2: Crawl Pages<br/>httpx + robots.txt check]
    
    CRAWL --> COMBINE[Step 3: Combine Content<br/>Merge all pages text]
    
    COMBINE --> LLM_ANALYSIS[Step 4: LLM Analysis<br/>Multi-LLM: Llama3, Mistral, Phi3]
    
    LLM_ANALYSIS --> CHECK_PROFILE{Profile<br/>exists?}
    
    CHECK_PROFILE -->|No| CREATE_PROFILE[Step 5: Create<br/>site_profile]
    CHECK_PROFILE -->|Yes| UPDATE_PROFILE[Step 6: Update<br/>site_profile]
    
    CREATE_PROFILE --> UPDATE_PROFILE
    
    UPDATE_PROFILE --> SAVE_RESULTS[Step 7: Save<br/>site_analysis_result]
    
    SAVE_RESULTS --> UPDATE_EXEC[Step 8: Update execution<br/>status: completed]
    
    UPDATE_EXEC --> SCRAPE[Step 9: Auto-Scraping<br/>Background Task]
    
    SCRAPE --> DISCOVERY[Discovery Phase<br/>API, RSS, Sitemap]
    DISCOVERY --> SCORING[Scoring Phase<br/>Article probability]
    SCORING --> EXTRACTION[Extraction Phase<br/>Adaptive extractors]
    EXTRACTION --> VALIDATION[Validation Phase<br/>Content quality]
    
    VALIDATION --> SAVE_ARTICLES[Save client_articles]
    VALIDATION --> SAVE_PROFILES[Save discovery profiles]
    VALIDATION --> SAVE_SCORES[Save URL scores]
    VALIDATION --> SAVE_LOGS[Save discovery logs]
    
    SAVE_ARTICLES --> INDEX_QDRANT[Index in Qdrant<br/>{domain}_client_articles]
    
    SAVE_PROFILES --> END_SUCCESS([Success])
    SAVE_SCORES --> END_SUCCESS
    SAVE_LOGS --> END_SUCCESS
    INDEX_QDRANT --> END_SUCCESS
    
    UPDATE_EXEC -.->|If error| ERROR_HANDLER[Error Handler<br/>Update status: failed]
    ERROR_HANDLER --> END_ERROR([Error Response])
    
    style START fill:#4a90e2,color:#fff
    style LLM_ANALYSIS fill:#ff6b6b,color:#fff
    style SCRAPE fill:#50c878,color:#fff
    style END_SUCCESS fill:#50c878,color:#fff
    style END_ERROR fill:#e74c3c,color:#fff
```

## Architecture des Tables de Base de Données

```mermaid
erDiagram
    workflow_executions ||--o{ site_analysis_results : "has"
    site_profiles ||--o{ site_analysis_results : "has"
    site_profiles ||--o{ client_articles : "has"
    
    workflow_executions {
        uuid execution_id PK
        string workflow_type
        string status
        jsonb input_data
        jsonb output_data
        timestamp start_time
        timestamp end_time
        int duration_seconds
        boolean was_success
        text error_message
    }
    
    site_profiles {
        int id PK
        string domain UK
        timestamp analysis_date
        string language_level
        string editorial_tone
        jsonb target_audience
        jsonb activity_domains
        jsonb content_structure
        jsonb keywords
        jsonb style_features
        int pages_analyzed
        jsonb llm_models_used
    }
    
    site_analysis_results {
        int id PK
        int site_profile_id FK
        uuid execution_id FK
        string analysis_phase
        jsonb phase_results
        string llm_model_used
        int processing_time_seconds
    }
    
    client_articles {
        int id PK
        int site_profile_id FK
        string url UK
        string url_hash
        string title
        string author
        date published_date
        text content_text
        text content_html
        int word_count
        jsonb keywords
        jsonb article_metadata
        uuid qdrant_point_id
        int topic_id
    }
    
    site_discovery_profiles {
        int id PK
        string domain UK
        string cms_detected
        boolean has_rest_api
        jsonb api_endpoints
        jsonb sitemap_urls
        jsonb rss_feeds
        jsonb url_patterns
        string content_selector
        int total_urls_discovered
        int total_articles_valid
        float success_rate
    }
    
    url_discovery_scores {
        int id PK
        string domain
        string url
        string url_hash
        string discovery_source
        int initial_score
        int final_score
        jsonb score_breakdown
        boolean was_scraped
        string scrape_status
        boolean is_valid_article
    }
    
    discovery_logs {
        int id PK
        string domain
        uuid execution_id
        string operation
        string status
        int urls_found
        int urls_scraped
        int urls_valid
        jsonb sources_used
        jsonb errors
        float duration_seconds
    }
```

## Architecture LLM Multi-Modèle

```mermaid
graph LR
    subgraph "Input"
        CONTENT[Combined Content<br/>from crawled pages]
    end
    
    subgraph "LLM Analysis Pipeline"
        LLAMA3[Llama3:8b<br/>Analysis]
        MISTRAL[Mistral:7b<br/>Analysis]
        PHI3[Phi3:medium<br/>Analysis]
    end
    
    subgraph "Synthesis"
        SYNTHESIS[Llama3:8b<br/>Synthesis]
    end
    
    subgraph "Output"
        PROFILE[Editorial Profile<br/>JSON]
    end
    
    CONTENT --> LLAMA3
    CONTENT --> MISTRAL
    CONTENT --> PHI3
    
    LLAMA3 --> SYNTHESIS
    MISTRAL --> SYNTHESIS
    PHI3 --> SYNTHESIS
    
    SYNTHESIS --> PROFILE
    
    style CONTENT fill:#3498db,color:#fff
    style LLAMA3 fill:#e74c3c,color:#fff
    style MISTRAL fill:#9b59b6,color:#fff
    style PHI3 fill:#f39c12,color:#fff
    style SYNTHESIS fill:#27ae60,color:#fff
    style PROFILE fill:#16a085,color:#fff
```

## Architecture du Scraping Automatique

```mermaid
graph TB
    subgraph "Discovery Phase"
        API_DISC[API Discovery<br/>REST endpoints]
        RSS_DISC[RSS Discovery<br/>Feed parsing]
        SITEMAP_DISC[Sitemap Discovery<br/>XML parsing]
        HEURISTIC[Heuristic Discovery<br/>Pattern matching]
    end
    
    subgraph "Scoring Phase"
        SCORER[Article Scorer<br/>Probability calculation]
        SELECTOR[URL Selector<br/>Top N selection]
    end
    
    subgraph "Extraction Phase"
        EXTRACTOR[Adaptive Extractor<br/>CSS selectors]
        VALIDATOR[Content Validator<br/>Quality checks]
    end
    
    subgraph "Persistence Phase"
        DB_SAVE[(PostgreSQL)]
        QDRANT_SAVE[(Qdrant)]
    end
    
    API_DISC --> SCORER
    RSS_DISC --> SCORER
    SITEMAP_DISC --> SCORER
    HEURISTIC --> SCORER
    
    SCORER --> SELECTOR
    SELECTOR --> EXTRACTOR
    EXTRACTOR --> VALIDATOR
    VALIDATOR --> DB_SAVE
    VALIDATOR --> QDRANT_SAVE
    
    style SCORER fill:#ff6b6b,color:#fff
    style EXTRACTOR fill:#50c878,color:#fff
    style DB_SAVE fill:#f39c12,color:#fff
    style QDRANT_SAVE fill:#9b59b6,color:#fff
```

## Légende des Couleurs

- 🔵 **Bleu** : Points d'entrée/sortie (API, Client)
- 🟢 **Vert** : Orchestration et workflow
- 🔴 **Rouge** : Agents et traitement LLM
- 🟡 **Jaune** : Base de données PostgreSQL
- 🟣 **Violet** : Qdrant (Vector Store)
- 🔵 **Bleu clair** : Services externes

## Notes d'Architecture

### Points Clés

1. **Asynchrone** : La route retourne immédiatement un `execution_id` et le traitement se fait en arrière-plan
2. **Multi-LLM** : Utilise 3 modèles LLM différents pour une analyse robuste
3. **Scraping Automatique** : Lance automatiquement le scraping du site client après l'analyse
4. **Gestion d'Erreurs** : Les erreurs de scraping n'interrompent pas le workflow principal
5. **Collections Qdrant** : Les articles clients sont indexés dans une collection spécifique par domaine : `{domain}_client_articles`

### Performance

- **Temps typique** : 2-5 minutes pour l'analyse complète
- **Parallélisation** : Les analyses LLM peuvent être parallélisées
- **Cache** : Les tables de cache (`scraping_permissions`, `crawl_cache`) ne sont pas utilisées dans ce workflow

### Scalabilité

- **Background Tasks** : Utilise FastAPI BackgroundTasks pour ne pas bloquer l'API
- **Base de données** : Utilise des sessions async pour la performance
- **Qdrant** : Collections séparées par domaine pour l'isolation









