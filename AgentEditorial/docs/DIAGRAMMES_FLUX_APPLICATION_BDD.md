# Diagrammes de Flux - Application et Base de Données

## Vue d'ensemble

Ce document présente les diagrammes de flux de l'application **Agent Éditorial & Concurrentiel** et de sa base de données PostgreSQL.

---

## 1. Diagramme de Flux de l'Application

### 1.1 Architecture Générale

```mermaid
flowchart TB
    Client[👤 Client/Application<br/>📱 Frontend/API Client]
    API[🚀 FastAPI API<br/>🌐 Port 8000<br/>📡 REST + WebSocket]
    
    subgraph Routes["📋 Routes API"]
        direction TB
        Health[💚 Health Check<br/>/health]
        Sites[🏢 Sites<br/>/sites/analyze]
        Competitors[🔍 Competitors<br/>/competitors/search]
        Discovery[🔎 Discovery<br/>/discovery/scrape]
        Trend[📈 Trend Pipeline<br/>/trend-pipeline/analyze]
        Executions[⚙️ Executions<br/>/executions/{id}]
        Errors[❌ Errors<br/>/errors]
        Articles[📝 Articles<br/>/articles/enrich]
    end
    
    subgraph Agents["🤖 Agents Multi-LLM"]
        direction TB
        Editorial[📊 Editorial Analysis<br/>Agent]
        Competitor[🎯 Competitor Search<br/>Agent]
        Scraping[🕷️ Enhanced Scraping<br/>Agent]
        TrendPipeline[📈 Trend Pipeline<br/>Agent]
    end
    
    subgraph Services["🌍 Services Externes"]
        direction TB
        LLM[🧠 LLM Models<br/>Llama3 🤖<br/>Mistral 🌊<br/>Phi3 ⚡]
        Qdrant[🔍 Qdrant Vector DB<br/>📊 Embeddings]
        Tavily[🔎 Tavily Search API<br/>🌐 Web Search]
        DuckDuckGo[🦆 DuckDuckGo API<br/>🔍 Search]
    end
    
    subgraph Database["💾 PostgreSQL Database"]
        direction TB
        Tables[(🗄️ Tables de données<br/>📊 20+ tables)]
    end
    
    Client -->|HTTP/WebSocket| API
    API -->|Route| Routes
    Routes -->|Execute| Agents
    Agents -->|Query| LLM
    Agents -->|Store/Query| Qdrant
    Agents -->|Search| Tavily
    Agents -->|Search| DuckDuckGo
    Agents -->|CRUD| Database
    Database -->|Persist| Tables
    
    style Client fill:#4a90e2,stroke:#2c5aa0,stroke-width:3px,color:#fff
    style API fill:#50c878,stroke:#2d7a4e,stroke-width:3px,color:#fff
    style Routes fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style Agents fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style Services fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style Database fill:#9370db,stroke:#5e4a9e,stroke-width:3px,color:#fff
    style LLM fill:#ff6b6b,stroke:#c92a2a,stroke-width:2px,color:#fff
    style Qdrant fill:#ffa500,stroke:#cc8500,stroke-width:2px,color:#fff
```

### 1.2 Flux Fonctionnel Principal

```mermaid
flowchart TD
    Start([🚀 Démarrage Application])
    
    subgraph Workflow1["📊 1. Analyse Éditoriale"]
        direction TB
        A1[📥 POST /sites/analyze<br/>Domain: innosys.fr]
        A2[📝 Créer workflow_execution<br/>type: editorial_analysis]
        A3[🔍 Découvrir URLs<br/>via Sitemap]
        A4[🕷️ Crawler les pages<br/>httpx + robots.txt]
        A5[🧠 Analyse LLM<br/>Multi-modèles]
        A6[💾 Créer/Mettre à jour<br/>site_profile]
        A7[📊 Sauvegarder<br/>site_analysis_results]
    end
    
    subgraph Workflow2["🔍 2. Recherche Concurrents"]
        direction TB
        B1[📥 POST /competitors/search<br/>Domain: innosys.fr]
        B2[📝 Créer workflow_execution<br/>type: competitor_search]
        B3[🌐 Recherche Tavily<br/>+ DuckDuckGo]
        B4[✅ Validation LLM<br/>des candidats]
        B5[💾 Sauvegarder<br/>concurrents validés]
    end
    
    subgraph Workflow3["🕷️ 3. Scraping Amélioré"]
        direction TB
        C1[📥 POST /discovery/scrape<br/>Domains: concurrents]
        C2[📝 Créer workflow_execution<br/>type: enhanced_scraping]
        C3[🔍 Phase 0: Profiling<br/>CMS, APIs, RSS]
        C4[📡 Phase 1: Discovery<br/>Multi-sources]
        C5[📊 Phase 2: Scoring<br/>Probabilité articles]
        C6[✂️ Phase 3: Extraction<br/>Adaptive extractors]
        C7[💾 Sauvegarder<br/>competitor_articles]
    end
    
    subgraph Workflow4["📈 4. Trend Pipeline"]
        direction TB
        D1[📥 POST /trend-pipeline/analyze<br/>client_domain: innosys.fr]
        D2[📝 Créer workflow_execution<br/>type: trend_pipeline]
        D3[🎯 Stage 1: Clustering<br/>BERTopic + HDBSCAN]
        D4[⏱️ Stage 2: Analyse Temporelle<br/>Volume, Velocity, Freshness]
        D5[🧠 Stage 3: Enrichissement LLM<br/>Trend synthesis]
        D6[📊 Stage 4: Gap Analysis<br/>Coverage & Roadmap]
        D7[💾 Sauvegarder résultats<br/>Topics, Trends, Gaps]
    end
    
    Start --> A1
    A1 --> A2 --> A3 --> A4 --> A5 --> A6 --> A7
    
    Start --> B1
    B1 --> B2 --> B3 --> B4 --> B5
    
    Start --> C1
    C1 --> C2 --> C3 --> C4 --> C5 --> C6 --> C7
    
    Start --> D1
    D1 --> D2 --> D3 --> D4 --> D5 --> D6 --> D7
    
    A7 -.->|🔄 Peut déclencher| C1
    B5 -.->|📋 Fournit domaines| C1
    C7 -.->|📚 Fournit articles| D1
    
    style Start fill:#4a90e2,stroke:#2c5aa0,stroke-width:3px,color:#fff
    style Workflow1 fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style Workflow2 fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style Workflow3 fill:#e8f5e9,stroke:#388e3c,stroke-width:2px
    style Workflow4 fill:#fff3e0,stroke:#f57c00,stroke-width:2px
```

### 1.3 Flux Détaillé - Analyse Éditoriale

```mermaid
sequenceDiagram
    participant Client as 👤 Client
    participant API as 🚀 FastAPI Router
    participant DB as 💾 PostgreSQL
    participant Orchestrator as 🎯 Orchestrator
    participant Sitemap as 🔍 Sitemap Discovery
    participant Crawler as 🕷️ Page Crawler
    participant LLM as 🧠 Multi-LLM Agent
    participant Scraper as 🔎 Scraping Agent
    
    Client->>API: 📥 POST /api/v1/sites/analyze<br/>{domain: "innosys.fr", max_pages: 10}
    API->>DB: 📝 CREATE workflow_execution<br/>(status: pending, type: editorial_analysis)
    DB-->>API: ✅ execution_id (UUID)
    API-->>Client: ✅ 202 Accepted<br/>{execution_id, status: pending}
    
    rect rgb(200, 220, 255)
        Note over API,Scraper: 🔄 Background Task
    end
    
    API->>Orchestrator: 🚀 run_editorial_analysis(domain, execution_id)
    Orchestrator->>DB: 🔄 UPDATE workflow_execution<br/>(status: running)
    
    rect rgb(220, 255, 220)
        Note over Orchestrator,Sitemap: 📍 Phase 1: Discovery
        Orchestrator->>Sitemap: 🔍 get_sitemap_urls(domain)
        Sitemap-->>Orchestrator: 📋 List of URLs
    end
    
    rect rgb(255, 255, 200)
        Note over Orchestrator,Crawler: 🕷️ Phase 2: Crawling
        Orchestrator->>Crawler: 📥 crawl_multiple_pages(urls)
        Crawler->>Crawler: 🤖 Check robots.txt
        Crawler->>Crawler: 🌐 Fetch pages (httpx)
        Crawler-->>Orchestrator: 📄 Crawled content
    end
    
    Orchestrator->>Orchestrator: 🔗 Combine all pages content
    
    rect rgb(255, 200, 200)
        Note over Orchestrator,LLM: 🧠 Phase 3: LLM Analysis
        Orchestrator->>LLM: 🚀 execute(combined_content)
        LLM->>LLM: 🤖 Llama3: Editorial style
        LLM->>LLM: 🌊 Mistral: Content structure
        LLM->>LLM: ⚡ Phi3: Keywords & domains
        LLM-->>Orchestrator: ✅ Analysis results
    end
    
    rect rgb(200, 255, 255)
        Note over Orchestrator,DB: 💾 Phase 4: Persistence
        Orchestrator->>DB: 💾 CREATE/UPDATE site_profile<br/>(domain, language_level, editorial_tone, etc.)
        Orchestrator->>DB: 💾 CREATE site_analysis_results<br/>(site_profile_id, execution_id, phase_results)
        Orchestrator->>DB: ✅ UPDATE workflow_execution<br/>(status: completed, output_data)
    end
    
    rect rgb(255, 220, 220)
        Note over API,Scraper: 🔄 Background Scraping (optional)
        Orchestrator->>Scraper: 🕷️ Auto-scrape client site
        Scraper->>DB: 💾 CREATE client_articles
        Scraper->>DB: 💾 CREATE site_discovery_profiles
    end
```

### 1.4 Flux Détaillé - Trend Pipeline

```mermaid
flowchart TD
    Start([📥 POST /trend-pipeline/analyze<br/>client_domain: innosys.fr])
    
    CreateExec[📝 Créer workflow_execution<br/>type: trend_pipeline<br/>status: running]
    
    subgraph Stage1["🎯 Stage 1: Clustering"]
        direction TB
        S1A[📚 Récupérer articles<br/>concurrents]
        S1B[🔢 Générer embeddings<br/>Vector DB]
        S1C[🎯 BERTopic clustering<br/>Topic discovery]
        S1D[📊 HDBSCAN outliers<br/>Outlier detection]
        S1E[💾 Sauvegarder<br/>topic_clusters]
        S1F[💾 Sauvegarder<br/>topic_outliers]
    end
    
    subgraph Stage2["⏱️ Stage 2: Temporal Analysis"]
        direction TB
        S2A[📈 Calculer métriques<br/>temporelles]
        S2B[📊 Volume, Velocity<br/>Freshness]
        S2C[💾 Sauvegarder<br/>topic_temporal_metrics]
    end
    
    subgraph Stage3["🧠 Stage 3: LLM Enrichment"]
        direction TB
        S3A[✨ Enrichir chaque topic<br/>avec LLM]
        S3B[📝 Générer recommandations<br/>d'articles]
        S3C[💾 Sauvegarder<br/>trend_analysis]
        S3D[💾 Sauvegarder<br/>article_recommendations]
        S3E[💾 Sauvegarder<br/>weak_signals_analysis]
    end
    
    subgraph Stage4["📊 Stage 4: Gap Analysis"]
        direction TB
        S4A[🔍 Analyser couverture<br/>client]
        S4B[💪 Identifier forces<br/>client]
        S4C[⚠️ Identifier gaps<br/>éditoriaux]
        S4D[🗺️ Générer roadmap<br/>contenu]
        S4E[💾 Sauvegarder<br/>client_coverage_analysis]
        S4F[💾 Sauvegarder<br/>client_strengths]
        S4G[💾 Sauvegarder<br/>editorial_gaps]
        S4H[💾 Sauvegarder<br/>content_roadmap]
    end
    
    Final[✅ UPDATE workflow_execution<br/>status: completed<br/>was_success: true]
    
    Start --> CreateExec
    CreateExec --> S1A
    S1A --> S1B --> S1C --> S1D --> S1E --> S1F
    S1F --> S2A
    S2A --> S2B --> S2C
    S2C --> S3A
    S3A --> S3B --> S3C --> S3D --> S3E
    S3E --> S4A
    S4A --> S4B --> S4C --> S4D --> S4E --> S4F --> S4G --> S4H
    S4H --> Final
    
    style Start fill:#4a90e2,stroke:#2c5aa0,stroke-width:3px,color:#fff
    style CreateExec fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style Stage1 fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style Stage2 fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style Stage3 fill:#e8f5e9,stroke:#388e3c,stroke-width:2px
    style Stage4 fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style Final fill:#50c878,stroke:#2d7a4e,stroke-width:3px,color:#fff
```

---

## 2. Diagramme de Flux de la Base de Données

### 2.1 Schéma Entité-Relation Complet (Vue d'ensemble)

```mermaid
flowchart TB
    subgraph Core["💾 Tables Principales"]
        SP[🏢 site_profiles<br/>Site Client]
        WE[⚙️ workflow_executions<br/>Exécutions]
        SAR[📊 site_analysis_results<br/>Résultats Analyse]
    end
    
    subgraph Editorial["📊 Editorial Analysis"]
        CA[📚 client_articles<br/>Articles Client]
    end
    
    subgraph Competitor["🔍 Competitor & Scraping"]
        CompArt[📰 competitor_articles<br/>Articles Concurrents]
        SDP[🔍 site_discovery_profiles<br/>Profils Découverte]
        UDS[📊 url_discovery_scores<br/>Scores URLs]
        DL[📝 discovery_logs<br/>Logs Découverte]
    end
    
    subgraph Trend["📈 Trend Pipeline"]
        TPE[⚙️ trend_pipeline_executions<br/>Exécutions Pipeline]
        TC[🎯 topic_clusters<br/>Clusters Topics]
        TO[📌 topic_outliers<br/>Outliers]
        TTM[⏱️ topic_temporal_metrics<br/>Métriques Temporelles]
        TA[📊 trend_analysis<br/>Analyses Tendances]
        AR[📝 article_recommendations<br/>Recommandations]
        WSA[🔮 weak_signals_analysis<br/>Signaux Faibles]
        CCA[🔍 client_coverage_analysis<br/>Couverture Client]
        CS[💪 client_strengths<br/>Forces Client]
        EG[⚠️ editorial_gaps<br/>Gaps Éditoriaux]
        CR[🗺️ content_roadmap<br/>Roadmap Contenu]
    end
    
    subgraph Monitoring["📊 Monitoring & Logs"]
        AL[📋 audit_logs<br/>Logs Audit]
        EL[❌ error_logs<br/>Logs Erreurs]
        PM[📈 performance_metrics<br/>Métriques Performance]
    end
    
    subgraph Cache["💾 Cache"]
        CC[🔄 crawl_cache<br/>Cache Crawl]
        SPerm[🤖 scraping_permissions<br/>Permissions Scraping]
    end
    
    SP -->|1:N| SAR
    WE -->|1:N| SAR
    SP -->|1:N| CA
    WE -->|1:N| AL
    WE -->|1:N| EL
    WE -->|1:N| PM
    TPE -->|1:N| TC
    TPE -->|1:N| TO
    TPE -->|1:N| TTM
    TPE -->|1:N| TA
    TPE -->|1:N| AR
    TPE -->|1:N| WSA
    TPE -->|1:N| CCA
    TPE -->|1:N| CS
    TPE -->|1:N| EG
    TPE -->|1:N| CR
    TC -->|1:N| TTM
    TC -->|1:N| TA
    TC -->|1:N| AR
    TC -->|1:N| CCA
    TC -->|1:N| CS
    TC -->|1:N| EG
    EG -->|1:N| CR
    SDP -->|1:N| UDS
    SDP -->|1:N| DL
    
    style Core fill:#e3f2fd,stroke:#1976d2,stroke-width:3px
    style Editorial fill:#e8f5e9,stroke:#388e3c,stroke-width:2px
    style Competitor fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style Trend fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style Monitoring fill:#ffebee,stroke:#c62828,stroke-width:2px
    style Cache fill:#f1f8e9,stroke:#558b2f,stroke-width:2px
```

### 2.1.1 Schéma Entité-Relation Détaillé

```mermaid
erDiagram
    %% Tables principales
    site_profiles ||--o{ site_analysis_results : "a plusieurs"
    workflow_executions ||--o{ site_analysis_results : "produit"
    site_profiles ||--o{ client_articles : "contient"
    
    %% Workflow executions et ses relations
    workflow_executions ||--o{ audit_logs : "génère"
    workflow_executions ||--o{ error_logs : "génère"
    workflow_executions ||--o{ performance_metrics : "mesure"
    workflow_executions ||--o| workflow_executions : "parent_execution_id"
    
    %% Trend Pipeline
    trend_pipeline_executions ||--o{ topic_clusters : "génère"
    trend_pipeline_executions ||--o{ topic_outliers : "génère"
    trend_pipeline_executions ||--o{ topic_temporal_metrics : "génère"
    trend_pipeline_executions ||--o{ trend_analysis : "génère"
    trend_pipeline_executions ||--o{ article_recommendations : "génère"
    trend_pipeline_executions ||--o{ weak_signals_analysis : "génère"
    trend_pipeline_executions ||--o{ client_coverage_analysis : "génère"
    trend_pipeline_executions ||--o{ client_strengths : "génère"
    trend_pipeline_executions ||--o{ editorial_gaps : "génère"
    trend_pipeline_executions ||--o{ content_roadmap : "génère"
    
    %% Scraping
    site_discovery_profiles ||--o{ url_discovery_scores : "score"
    site_discovery_profiles ||--o{ discovery_logs : "log"
    
    %% Tables
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
    }
    
    workflow_executions {
        int id PK
        uuid execution_id UK
        string workflow_type
        string status
        jsonb input_data
        jsonb output_data
        timestamp start_time
        timestamp end_time
        boolean was_success
    }
    
    site_analysis_results {
        int id PK
        int site_profile_id FK
        uuid execution_id FK
        string analysis_phase
        jsonb phase_results
        string llm_model_used
    }
    
    client_articles {
        int id PK
        int site_profile_id FK
        string url UK
        string title
        text content_text
        uuid qdrant_point_id
    }
    
    competitor_articles {
        int id PK
        string domain
        string url UK
        string title
        text content_text
        uuid qdrant_point_id
    }
    
    trend_pipeline_executions {
        int id PK
        uuid execution_id UK
        string client_domain
        jsonb domains_analyzed
        string stage_1_clustering_status
        string stage_2_temporal_status
        string stage_3_llm_status
        string stage_4_gap_status
    }
    
    topic_clusters {
        int id PK
        uuid analysis_id FK
        int topic_id
        string topic_name
        jsonb keywords
        int article_count
    }
    
    topic_temporal_metrics {
        int id PK
        uuid analysis_id FK
        int topic_cluster_id FK
        int volume
        float velocity
        float freshness
    }
    
    trend_analysis {
        int id PK
        uuid analysis_id FK
        int topic_cluster_id FK
        string trend_summary
        jsonb trend_details
    }
    
    article_recommendations {
        int id PK
        uuid analysis_id FK
        int topic_cluster_id FK
        string recommended_title
        jsonb recommended_content
    }
    
    client_coverage_analysis {
        int id PK
        uuid analysis_id FK
        string client_domain
        int topic_cluster_id FK
        float coverage_score
        jsonb coverage_details
    }
    
    client_strengths {
        int id PK
        uuid analysis_id FK
        string client_domain
        int topic_cluster_id FK
        float strength_score
        jsonb strength_details
    }
    
    editorial_gaps {
        int id PK
        uuid analysis_id FK
        string client_domain
        int topic_cluster_id FK
        string gap_type
        jsonb gap_details
    }
    
    content_roadmap {
        int id PK
        uuid analysis_id FK
        string client_domain
        int gap_topic_id FK
        string roadmap_item
        jsonb roadmap_details
    }
    
    site_discovery_profiles {
        int id PK
        string domain UK
        string cms_detected
        boolean has_rest_api
        jsonb api_endpoints
        jsonb sitemap_urls
        jsonb rss_feeds
    }
    
    url_discovery_scores {
        int id PK
        string domain
        string url
        float score
        jsonb score_details
    }
    
    discovery_logs {
        int id PK
        uuid execution_id
        string operation
        jsonb results
    }
    
    audit_logs {
        int id PK
        uuid execution_id FK
        string action
        string status
        text message
    }
    
    error_logs {
        int id PK
        uuid execution_id FK
        string error_type
        text error_message
        string component
    }
    
    performance_metrics {
        int id PK
        uuid execution_id FK
        string metric_type
        float metric_value
    }
```

### 2.2 Flux de Données - Workflow Editorial Analysis

```mermaid
flowchart LR
    subgraph Input["📥 Input"]
        Domain[🌐 Domain<br/>innosys.fr]
        MaxPages[📄 Max Pages<br/>10]
    end
    
    subgraph Create["📝 Création"]
        WE[💾 workflow_executions<br/>execution_id: UUID<br/>workflow_type: editorial_analysis<br/>status: pending → running → completed]
    end
    
    subgraph Process["⚙️ Traitement"]
        SP[🏢 site_profiles<br/>domain: innosys.fr<br/>id: 15<br/>language_level, editorial_tone]
        SAR[📊 site_analysis_results<br/>site_profile_id: 15<br/>execution_id: UUID<br/>phase: discovery, synthesis]
    end
    
    subgraph Output["📤 Output"]
        CA[📚 client_articles<br/>site_profile_id: 15<br/>Articles scrapés<br/>url, title, content]
        SDP[🔍 site_discovery_profiles<br/>domain: innosys.fr<br/>Profil de découverte<br/>CMS, APIs, RSS]
    end
    
    Domain -->|input_data| WE
    MaxPages -->|input_data| WE
    WE -->|CREATE| SP
    WE -->|CREATE| SAR
    SP -->|FK: site_profile_id| SAR
    SAR -->|Trigger| CA
    SAR -->|Trigger| SDP
    
    style Input fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style Create fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style Process fill:#e8f5e9,stroke:#388e3c,stroke-width:2px
    style Output fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
```

### 2.3 Flux de Données - Trend Pipeline

```mermaid
flowchart TD
    subgraph Input["📥 Input"]
        ClientDomain[🌐 client_domain<br/>innosys.fr]
        TimeWindow[⏱️ time_window_days<br/>90 jours]
    end
    
    subgraph Execution["⚙️ Exécution"]
        TPE[💾 trend_pipeline_executions<br/>execution_id: UUID<br/>client_domain: innosys.fr<br/>stages: 1→2→3→4]
    end
    
    subgraph Stage1["🎯 Stage 1: Clustering"]
        TC[📊 topic_clusters<br/>topic_id, topic_name<br/>keywords, article_count]
        TO[📌 topic_outliers<br/>outlier articles<br/>non-clustered]
    end
    
    subgraph Stage2["⏱️ Stage 2: Temporal"]
        TTM[📈 topic_temporal_metrics<br/>volume: nombre articles<br/>velocity: vitesse croissance<br/>freshness: récence]
    end
    
    subgraph Stage3["🧠 Stage 3: LLM"]
        TA[📊 trend_analysis<br/>trend_summary<br/>trend_details JSON]
        AR[📝 article_recommendations<br/>recommended_title<br/>recommended_content]
        WSA[🔮 weak_signals_analysis<br/>disruption_potential<br/>emerging trends]
    end
    
    subgraph Stage4["📊 Stage 4: Gap"]
        CCA[🔍 client_coverage_analysis<br/>coverage_score<br/>coverage_details]
        CS[💪 client_strengths<br/>strength_score<br/>strength_details]
        EG[⚠️ editorial_gaps<br/>gap_type<br/>gap_details]
        CR[🗺️ content_roadmap<br/>roadmap_item<br/>roadmap_details]
    end
    
    ClientDomain -->|input_data| TPE
    TimeWindow -->|input_data| TPE
    TPE -->|CREATE| TC
    TPE -->|CREATE| TO
    TC -->|FK: topic_cluster_id| TTM
    TTM -->|FK: topic_cluster_id| TA
    TTM -->|FK: topic_cluster_id| AR
    TTM -->|FK: topic_cluster_id| WSA
    TA -->|FK: topic_cluster_id| CCA
    AR -->|FK: topic_cluster_id| CS
    CCA -->|FK: topic_cluster_id| EG
    EG -->|FK: gap_topic_id| CR
    
    style Input fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style Execution fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style Stage1 fill:#e8f5e9,stroke:#388e3c,stroke-width:2px
    style Stage2 fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style Stage3 fill:#ffebee,stroke:#c62828,stroke-width:2px
    style Stage4 fill:#f1f8e9,stroke:#558b2f,stroke-width:2px
```

### 2.4 Relations entre Workflows et Site Client

```mermaid
flowchart TB
    subgraph SiteClient["🏢 Site Client"]
        SP[💾 site_profiles<br/>id: 15<br/>domain: innosys.fr<br/>language_level, editorial_tone]
    end
    
    subgraph Workflows["⚙️ Workflows"]
        direction TB
        WE1[📊 workflow_executions<br/>execution_id: e855cd4f-...<br/>type: editorial_analysis<br/>✅ Lié via FK]
        WE2[🔍 workflow_executions<br/>execution_id: 378c14c4-...<br/>type: competitor_search<br/>❌ Référencé dans input_data]
        WE3[🕷️ workflow_executions<br/>execution_id: 19b5ba22-...<br/>type: enhanced_scraping<br/>❌ Référencé dans input_data]
        WE4[📈 workflow_executions<br/>execution_id: 08083962-...<br/>type: trend_pipeline<br/>❌ Référencé dans input_data]
    end
    
    subgraph Results["📊 Résultats"]
        direction TB
        SAR[📋 site_analysis_results<br/>site_profile_id: 15<br/>execution_id: e855cd4f-...<br/>phase: discovery, synthesis]
        CA[📚 client_articles<br/>site_profile_id: 15<br/>Articles du client]
        CompArt[📰 competitor_articles<br/>domain: concurrents<br/>Articles des concurrents]
        TPE[📈 trend_pipeline_executions<br/>client_domain: innosys.fr<br/>Résultats Trend Pipeline]
    end
    
    SP -->|FK: site_profile_id| SAR
    SP -->|FK: site_profile_id| CA
    WE1 -->|FK: execution_id| SAR
    WE2 -.->|input_data.domain<br/>"innosys.fr"| CompArt
    WE3 -.->|input_data.domain<br/>"concurrents"| CompArt
    WE4 -.->|input_data.client_domain<br/>"innosys.fr"| TPE
    
    style SiteClient fill:#e3f2fd,stroke:#1976d2,stroke-width:3px
    style Workflows fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style Results fill:#e8f5e9,stroke:#388e3c,stroke-width:2px
    style WE1 fill:#50c878,stroke:#2d7a4e,stroke-width:2px,color:#fff
    style WE2 fill:#ff9800,stroke:#cc7700,stroke-width:2px,color:#fff
    style WE3 fill:#ff9800,stroke:#cc7700,stroke-width:2px,color:#fff
    style WE4 fill:#ff9800,stroke:#cc7700,stroke-width:2px,color:#fff
```

---

## 3. Routes API et Fonctionnalités

### 3.1 Liste des Routes Principales

| Route | Méthode | Description | Workflow Type |
|-------|---------|-------------|---------------|
| `/api/v1/health` | GET | Health check | - |
| `/api/v1/sites/analyze` | POST | Analyse éditoriale | `editorial_analysis` |
| `/api/v1/sites/{domain}` | GET | Profil du site | - |
| `/api/v1/competitors/search` | POST | Recherche concurrents | `competitor_search` |
| `/api/v1/competitors/{domain}` | GET | Concurrents d'un domaine | - |
| `/api/v1/discovery/scrape` | POST | Scraping amélioré | `enhanced_scraping` |
| `/api/v1/discovery/{domain}` | GET | Profil de découverte | - |
| `/api/v1/trend-pipeline/analyze` | POST | Analyse des tendances | `trend_pipeline` |
| `/api/v1/trend-pipeline/{execution_id}` | GET | Résultats Trend Pipeline | - |
| `/api/v1/executions/{execution_id}` | GET | Statut d'exécution | - |
| `/api/v1/errors` | GET | Liste des erreurs | - |
| `/api/v1/articles/enrich` | POST | Enrichissement d'articles | - |

### 3.2 Types de Workflows

| Type | Objectif | Tables Principales | Lié à site_profiles ? |
|------|----------|-------------------|----------------------|
| `editorial_analysis` | Analyser le style éditorial | `site_profiles`, `site_analysis_results` | ✅ Oui (via FK) |
| `competitor_search` | Trouver les concurrents | - | ❌ Non (dans input_data) |
| `enhanced_scraping` | Scraper les articles | `competitor_articles`, `client_articles` | ⚠️ Peut-être |
| `trend_pipeline` | Analyser les tendances | `trend_pipeline_executions`, `topic_clusters`, etc. | ❌ Non (dans input_data) |

---

## 4. Explications Détaillées

### 4.1 Relation Site Client ↔ Workflows

**Point important** : Seul le workflow `editorial_analysis` est **directement lié** à `site_profiles` via la table de liaison `site_analysis_results`.

Les autres workflows (`competitor_search`, `enhanced_scraping`, `trend_pipeline`) référencent le domaine client dans leurs données d'entrée (`input_data.domain` ou `input_data.client_domain`) mais ne sont **pas liés** par une clé étrangère.

### 4.2 Flux de Données Typique

1. **Analyse Éditoriale** → Crée/met à jour `site_profiles`
2. **Recherche Concurrents** → Trouve les concurrents (stockés dans `output_data`)
3. **Scraping Amélioré** → Scrape les articles des concurrents → `competitor_articles`
4. **Trend Pipeline** → Analyse les tendances → Tables du Trend Pipeline

### 4.3 Requêtes SQL Utiles

#### Trouver tous les workflows d'un site client

```sql
-- Workflows directement liés (editorial_analysis)
SELECT 
    we.execution_id,
    we.workflow_type,
    we.status,
    we.start_time
FROM workflow_executions we
INNER JOIN site_analysis_results sar 
    ON sar.execution_id = we.execution_id
INNER JOIN site_profiles sp 
    ON sp.id = sar.site_profile_id
WHERE sp.domain = 'innosys.fr';

-- Tous les workflows qui mentionnent le domaine
SELECT 
    execution_id,
    workflow_type,
    status,
    input_data->>'domain' as domain,
    input_data->>'client_domain' as client_domain
FROM workflow_executions
WHERE input_data->>'domain' = 'innosys.fr'
   OR input_data->>'client_domain' = 'innosys.fr';
```

#### Trouver les résultats d'un Trend Pipeline

```sql
SELECT 
    tpe.execution_id,
    tpe.client_domain,
    COUNT(tc.id) as topics_count,
    COUNT(ar.id) as recommendations_count,
    COUNT(eg.id) as gaps_count
FROM trend_pipeline_executions tpe
LEFT JOIN topic_clusters tc ON tc.analysis_id = tpe.execution_id
LEFT JOIN article_recommendations ar ON ar.analysis_id = tpe.execution_id
LEFT JOIN editorial_gaps eg ON eg.analysis_id = tpe.execution_id
WHERE tpe.client_domain = 'innosys.fr'
GROUP BY tpe.execution_id, tpe.client_domain;
```

---

## 5. Résumé

### Points Clés

1. ✅ **4 types de workflows principaux** : `editorial_analysis`, `competitor_search`, `enhanced_scraping`, `trend_pipeline`
2. ✅ **Seul `editorial_analysis` est lié à `site_profiles`** via `site_analysis_results`
3. ✅ **Les autres workflows** référencent le domaine dans `input_data`
4. ✅ **Chaque workflow est indépendant** et peut être exécuté plusieurs fois
5. ✅ **Le Trend Pipeline** a sa propre table d'exécution (`trend_pipeline_executions`)

### Architecture

- **API FastAPI** avec routes modulaires
- **Agents Multi-LLM** pour l'analyse
- **PostgreSQL** pour la persistance
- **Qdrant** pour les embeddings vectoriels
- **Services externes** : Tavily, DuckDuckGo

---

## 6. Diagramme Visuel - Cycle de Vie Complet

### 6.1 Cycle de Vie d'un Workflow Editorial Analysis

```mermaid
stateDiagram-v2
    [*] --> Pending: 📥 POST /sites/analyze
    
    Pending: ⏳ Pending<br/>workflow_execution créé<br/>execution_id généré
    
    Pending --> Running: 🚀 Background Task Start
    
    Running: 🔄 Running<br/>Orchestrator actif<br/>Phases en cours
    
    state Running {
        [*] --> Discovery
        Discovery: 🔍 Discovery Phase<br/>Sitemap URLs
        Discovery --> Crawling
        Crawling: 🕷️ Crawling Phase<br/>Fetch pages
        Crawling --> Analysis
        Analysis: 🧠 LLM Analysis<br/>Multi-modèles
        Analysis --> Saving
        Saving: 💾 Saving Results<br/>site_profile<br/>site_analysis_results
        Saving --> [*]
    }
    
    Running --> Completed: ✅ Success<br/>All phases done
    Running --> Failed: ❌ Error<br/>Exception caught
    
    Completed: ✅ Completed<br/>was_success: true<br/>output_data filled
    Failed: ❌ Failed<br/>was_success: false<br/>error_message set
    
    Completed --> [*]
    Failed --> [*]
    
    note right of Pending
        Client reçoit execution_id
        Peut poller le statut
    end note
    
    note right of Running
        Phases exécutées:
        1. Discovery
        2. Crawling
        3. LLM Analysis
        4. Saving
    end note
    
    note right of Completed
        Résultats disponibles:
        - site_profile mis à jour
        - site_analysis_results créés
        - client_articles (optionnel)
    end note
```

### 6.2 Vue d'Ensemble Visuelle - Architecture Complète

```mermaid
graph TB
    subgraph ClientLayer["👤 Couche Client"]
        WebApp[🌐 Web Application]
        MobileApp[📱 Mobile App]
        API_Client[🔌 API Client]
    end
    
    subgraph APILayer["🚀 Couche API"]
        FastAPI[⚡ FastAPI Server<br/>Port 8000]
        WebSocket[🔌 WebSocket<br/>Real-time Updates]
        REST[📡 REST API<br/>8 Routes]
    end
    
    subgraph BusinessLayer["🤖 Couche Métier"]
        Orchestrator[🎯 Orchestrator]
        EditorialAgent[📊 Editorial Agent]
        CompetitorAgent[🔍 Competitor Agent]
        ScrapingAgent[🕷️ Scraping Agent]
        TrendAgent[📈 Trend Agent]
    end
    
    subgraph DataLayer["💾 Couche Données"]
        PostgreSQL[(🗄️ PostgreSQL<br/>20+ Tables)]
        Qdrant[(🔍 Qdrant<br/>Vector DB)]
    end
    
    subgraph ExternalLayer["🌍 Services Externes"]
        LLM_Services[🧠 LLM Services<br/>Llama3 🤖<br/>Mistral 🌊<br/>Phi3 ⚡]
        SearchAPIs[🔎 Search APIs<br/>Tavily 🔍<br/>DuckDuckGo 🦆]
    end
    
    WebApp --> FastAPI
    MobileApp --> FastAPI
    API_Client --> FastAPI
    FastAPI --> WebSocket
    FastAPI --> REST
    REST --> Orchestrator
    Orchestrator --> EditorialAgent
    Orchestrator --> CompetitorAgent
    Orchestrator --> ScrapingAgent
    Orchestrator --> TrendAgent
    EditorialAgent --> LLM_Services
    CompetitorAgent --> SearchAPIs
    ScrapingAgent --> SearchAPIs
    TrendAgent --> LLM_Services
    EditorialAgent --> PostgreSQL
    CompetitorAgent --> PostgreSQL
    ScrapingAgent --> PostgreSQL
    TrendAgent --> PostgreSQL
    EditorialAgent --> Qdrant
    ScrapingAgent --> Qdrant
    TrendAgent --> Qdrant
    
    style ClientLayer fill:#e3f2fd,stroke:#1976d2,stroke-width:3px
    style APILayer fill:#50c878,stroke:#2d7a4e,stroke-width:3px,color:#fff
    style BusinessLayer fill:#fff3e0,stroke:#f57c00,stroke-width:3px
    style DataLayer fill:#9370db,stroke:#5e4a9e,stroke-width:3px,color:#fff
    style ExternalLayer fill:#f3e5f5,stroke:#7b1fa2,stroke-width:3px
```

### 6.3 Flux de Données Visuel - End-to-End

```mermaid
flowchart LR
    subgraph Input["📥 INPUT"]
        User[👤 Utilisateur]
        Domain[🌐 Domain: innosys.fr]
    end
    
    subgraph API["🚀 API"]
        Request[📥 POST Request]
        Response[📤 Response<br/>execution_id]
    end
    
    subgraph Processing["⚙️ PROCESSING"]
        Workflow[⚙️ Workflow Execution]
        Agent[🤖 Agent Processing]
        LLM[🧠 LLM Analysis]
    end
    
    subgraph Storage["💾 STORAGE"]
        DB[(🗄️ PostgreSQL)]
        Vector[(🔍 Qdrant)]
    end
    
    subgraph Output["📤 OUTPUT"]
        Results[📊 Results]
        Profile[🏢 Site Profile]
        Articles[📚 Articles]
    end
    
    User -->|Request| Request
    Domain -->|Input| Request
    Request -->|Create| Workflow
    Request -->|Return| Response
    Response -->|execution_id| User
    Workflow -->|Execute| Agent
    Agent -->|Query| LLM
    Agent -->|Save| DB
    Agent -->|Index| Vector
    DB -->|Read| Results
    DB -->|Read| Profile
    DB -->|Read| Articles
    Results -->|Display| User
    Profile -->|Display| User
    Articles -->|Display| User
    
    style Input fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style API fill:#50c878,stroke:#2d7a4e,stroke-width:3px,color:#fff
    style Processing fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style Storage fill:#9370db,stroke:#5e4a9e,stroke-width:3px,color:#fff
    style Output fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
```

---

## 7. Diagramme de Flux Principal - Workflow Complet (Style Processus)

### 7.1 Workflow Principal - De la Demande au Résultat Final

```mermaid
flowchart TD
    Start([🌐 Demande Client<br/>Domain: innosys.fr])
    
    subgraph Inputs["📥 Inputs Externes"]
        Domain((🌐 Domain<br/>innosys.fr))
        MaxPages((📄 Max Pages<br/>10))
        TimeWindow((⏱️ Time Window<br/>90 jours))
    end
    
    subgraph Init["🚀 Initialisation"]
        CreateWE[📝 Créer workflow_execution<br/>type: editorial_analysis<br/>status: pending]
    end
    
    subgraph Analysis["📊 Analyse Éditoriale"]
        Discovery[🔍 Découverte URLs<br/>Sitemap]
        Crawling[🕷️ Crawling Pages<br/>httpx + robots.txt]
        LLMAnalysis[🧠 Analyse LLM<br/>Multi-modèles]
    end
    
    subgraph Profile["🏢 Profil Site"]
        CreateProfile[💾 Créer/Mettre à jour<br/>site_profiles<br/>id: 15]
        SaveResults[📊 Sauvegarder<br/>site_analysis_results<br/>site_profile_id: 15]
    end
    
    subgraph Workflows["⚙️ Workflows Parallèles"]
        direction TB
        CompSearch[🔍 Recherche Concurrents<br/>competitor_search]
        Scraping[🕷️ Scraping Amélioré<br/>enhanced_scraping]
        TrendPipe[📈 Trend Pipeline<br/>trend_pipeline]
    end
    
    subgraph Results["📊 Résultats"]
        direction TB
        ClientArticles[📚 client_articles<br/>Articles du client]
        CompArticles[📰 competitor_articles<br/>Articles concurrents]
        Trends[📈 Topics & Trends<br/>topic_clusters<br/>trend_analysis]
        Gaps[⚠️ Gaps & Roadmap<br/>editorial_gaps<br/>content_roadmap]
    end
    
    subgraph Final["✅ Finalisation"]
        Distribution[📤 Distribution<br/>Résultats disponibles<br/>via API]
    end
    
    Start --> CreateWE
    Domain --> Discovery
    MaxPages --> Crawling
    CreateWE --> Discovery
    Discovery --> Crawling
    Crawling --> LLMAnalysis
    LLMAnalysis --> CreateProfile
    CreateProfile --> SaveResults
    
    SaveResults --> CompSearch
    SaveResults --> Scraping
    SaveResults --> TrendPipe
    
    TimeWindow --> TrendPipe
    
    CompSearch --> CompArticles
    Scraping --> CompArticles
    Scraping --> ClientArticles
    TrendPipe --> Trends
    TrendPipe --> Gaps
    
    CompArticles --> Distribution
    ClientArticles --> Distribution
    Trends --> Distribution
    Gaps --> Distribution
    
    style Start fill:#4a90e2,stroke:#2c5aa0,stroke-width:3px,color:#fff
    style Inputs fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style Init fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style Analysis fill:#e8f5e9,stroke:#388e3c,stroke-width:2px
    style Profile fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style Workflows fill:#ffebee,stroke:#c62828,stroke-width:2px
    style Results fill:#f1f8e9,stroke:#558b2f,stroke-width:2px
    style Final fill:#50c878,stroke:#2d7a4e,stroke-width:3px,color:#fff
```

### 7.2 Workflow Détaillé - Relations Site Client et Workflows

```mermaid
flowchart TD
    ClientRequest([👤 Demande Client<br/>POST /sites/analyze<br/>domain: innosys.fr])
    
    subgraph ExternalInputs["📥 Inputs Externes"]
        DomainInput((🌐 Domain<br/>innosys.fr))
        ConfigInput((⚙️ Configuration<br/>max_pages: 10))
    end
    
    subgraph Creation["📝 Création"]
        WorkflowExec[📝 workflow_executions<br/>execution_id: UUID<br/>workflow_type: editorial_analysis<br/>status: pending → running]
    end
    
    subgraph Processing["⚙️ Traitement"]
        SiteProfile[🏢 site_profiles<br/>id: 15<br/>domain: innosys.fr<br/>language_level, editorial_tone]
        AnalysisResults[📊 site_analysis_results<br/>site_profile_id: 15<br/>execution_id: UUID<br/>phase: discovery, synthesis]
    end
    
    subgraph ParallelWorkflows["⚙️ Workflows Parallèles"]
        direction TB
        W1[🔍 competitor_search<br/>Recherche concurrents<br/>execution_id: 378c14c4-...]
        W2[🕷️ enhanced_scraping<br/>Scraping amélioré<br/>execution_id: 19b5ba22-...]
        W3[📈 trend_pipeline<br/>Analyse tendances<br/>execution_id: 08083962-...]
    end
    
    subgraph DataStorage["💾 Stockage Données"]
        direction TB
        ClientArts[📚 client_articles<br/>site_profile_id: 15<br/>Articles client]
        CompArts[📰 competitor_articles<br/>domain: concurrents<br/>Articles concurrents]
        TrendData[📈 Trend Pipeline Data<br/>topic_clusters<br/>trend_analysis<br/>editorial_gaps]
    end
    
    subgraph FinalOutput["📤 Résultats Finaux"]
        APIResponse[📡 API Response<br/>GET /sites/innosys.fr<br/>GET /trend-pipeline/{id}]
    end
    
    ClientRequest --> WorkflowExec
    DomainInput --> SiteProfile
    ConfigInput --> WorkflowExec
    
    WorkflowExec --> SiteProfile
    WorkflowExec --> AnalysisResults
    SiteProfile --> AnalysisResults
    
    AnalysisResults -.->|Déclenche| W1
    AnalysisResults -.->|Déclenche| W2
    AnalysisResults -.->|Déclenche| W3
    
    W1 --> CompArts
    W2 --> CompArts
    W2 --> ClientArts
    W3 --> TrendData
    
    SiteProfile --> APIResponse
    ClientArts --> APIResponse
    CompArts --> APIResponse
    TrendData --> APIResponse
    
    style ClientRequest fill:#4a90e2,stroke:#2c5aa0,stroke-width:3px,color:#fff
    style ExternalInputs fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style Creation fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style Processing fill:#e8f5e9,stroke:#388e3c,stroke-width:2px
    style ParallelWorkflows fill:#ffebee,stroke:#c62828,stroke-width:2px
    style DataStorage fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style FinalOutput fill:#50c878,stroke:#2d7a4e,stroke-width:3px,color:#fff
```

### 7.3 Workflow Trend Pipeline - 4 Stages Détaillés

```mermaid
flowchart TD
    Start([📥 POST /trend-pipeline/analyze<br/>client_domain: innosys.fr])
    
    subgraph Inputs["📥 Inputs"]
        ClientDomain((🌐 Client Domain<br/>innosys.fr))
        TimeWindow((⏱️ Time Window<br/>90 jours))
        Competitors((🔍 Concurrents<br/>Domains list))
    end
    
    subgraph Execution["⚙️ Exécution"]
        CreateExec[📝 Créer trend_pipeline_executions<br/>execution_id: UUID<br/>client_domain: innosys.fr]
    end
    
    subgraph Stage1["🎯 Stage 1: Clustering"]
        S1A[📚 Récupérer articles<br/>competitor_articles]
        S1B[🔢 Générer embeddings<br/>Vector DB]
        S1C[🎯 BERTopic clustering<br/>Topic discovery]
        S1D[💾 Sauvegarder<br/>topic_clusters<br/>topic_outliers]
    end
    
    subgraph Stage2["⏱️ Stage 2: Temporal"]
        S2A[📈 Calculer métriques<br/>temporelles]
        S2B[💾 Sauvegarder<br/>topic_temporal_metrics]
    end
    
    subgraph Stage3["🧠 Stage 3: LLM Enrichment"]
        S3A[✨ Enrichir topics<br/>avec LLM]
        S3B[💾 Sauvegarder<br/>trend_analysis<br/>article_recommendations<br/>weak_signals_analysis]
    end
    
    subgraph Stage4["📊 Stage 4: Gap Analysis"]
        S4A[🔍 Analyser couverture<br/>client]
        S4B[💾 Sauvegarder<br/>client_coverage_analysis<br/>client_strengths<br/>editorial_gaps<br/>content_roadmap]
    end
    
    subgraph Results["📊 Résultats"]
        FinalResults[📤 Résultats disponibles<br/>Topics, Trends, Gaps, Roadmap]
    end
    
    Start --> CreateExec
    ClientDomain --> CreateExec
    TimeWindow --> CreateExec
    Competitors --> S1A
    
    CreateExec --> S1A
    S1A --> S1B
    S1B --> S1C
    S1C --> S1D
    
    S1D --> S2A
    S2A --> S2B
    
    S2B --> S3A
    S3A --> S3B
    
    S3B --> S4A
    S4A --> S4B
    
    S4B --> FinalResults
    
    style Start fill:#4a90e2,stroke:#2c5aa0,stroke-width:3px,color:#fff
    style Inputs fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style Execution fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style Stage1 fill:#e8f5e9,stroke:#388e3c,stroke-width:2px
    style Stage2 fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style Stage3 fill:#ffebee,stroke:#c62828,stroke-width:2px
    style Stage4 fill:#f1f8e9,stroke:#558b2f,stroke-width:2px
    style Results fill:#50c878,stroke:#2d7a4e,stroke-width:3px,color:#fff
```

---

**Date de création** : 2025-12-10  
**Version** : 1.0.0  
**Dernière mise à jour** : 2025-12-10












