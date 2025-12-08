# Tasks: Agent Éditorial & Concurrentiel

**Input**: Design documents from `/AgentEditorial/.specify/specs/000-project-foundation/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests are included as per spec requirements (coverage ≥ 80%)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create project structure per plan.md in python_scripts/
- [x] T002 Initialize Python project with uv and create pyproject.toml
- [x] T003 [P] Configure linting tools (ruff, black, isort) in pyproject.toml
- [x] T004 [P] Configure type checking (mypy) with strict mode in pyproject.toml
- [x] T005 [P] Create .env.example template with all required environment variables
- [x] T006 [P] Setup Docker Compose configuration in docker/docker-compose.yml (PostgreSQL, Qdrant, Ollama)
- [x] T007 [P] Create .gitignore with Python, IDE, and environment-specific patterns
- [x] T008 Create README.md with project overview and quickstart reference

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Database & Configuration

- [x] T009 Setup database connection configuration in python_scripts/config/settings.py (Pydantic Settings)
- [x] T010 [P] Create async database session factory in python_scripts/database/db_session.py
- [x] T011 [P] Initialize Alembic for migrations in python_scripts/database/migrations/
- [x] T012 Create database models base class in python_scripts/database/models.py
- [x] T013 [P] Create SiteProfile model in python_scripts/database/models.py (table: site_profiles)
- [x] T014 [P] Create WorkflowExecution model in python_scripts/database/models.py (table: workflow_executions)
- [x] T015 [P] Create SiteAnalysisResult model in python_scripts/database/models.py (table: site_analysis_results)
- [x] T016 [P] Create CompetitorArticle model in python_scripts/database/models.py (table: competitor_articles)
- [x] T017 [P] Create EditorialTrend model in python_scripts/database/models.py (table: editorial_trends)
- [x] T018 [P] Create BertopicAnalysis model in python_scripts/database/models.py (table: bertopic_analysis)
- [x] T019 [P] Create CrawlCache model in python_scripts/database/models.py (table: crawl_cache)
- [x] T020 [P] Create ScrapingPermission model in python_scripts/database/models.py (table: scraping_permissions)
- [x] T021 [P] Create PerformanceMetric model in python_scripts/database/models.py (table: performance_metrics)
- [x] T022 [P] Create AuditLog model in python_scripts/database/models.py (table: audit_log)
- [x] T023 Generate initial Alembic migration with all 10 tables (requires DB to be running: `alembic revision --autogenerate -m "Initial schema"`)
- [ ] T024 Create CRUD base utilities in python_scripts/database/ (shared patterns) - Deferred to user story implementation

### Utilities & Infrastructure

- [x] T025 [P] Create custom exceptions hierarchy in python_scripts/utils/exceptions.py
- [x] T026 [P] Setup structured logging (structlog) in python_scripts/utils/logging.py
- [x] T027 [P] Create Qdrant client wrapper in python_scripts/vectorstore/qdrant_client.py
- [x] T028 [P] Create embeddings utility (Sentence-Transformers) in python_scripts/vectorstore/embeddings_utils.py
- [x] T029 Initialize Qdrant collection "competitor_articles" (384 dimensions, cosine distance) - Script created in scripts/init_qdrant.py

### FastAPI Base Setup

- [x] T030 Create FastAPI app structure in python_scripts/api/main.py
- [x] T031 [P] Create API dependencies (DB session, rate limiting) in python_scripts/api/dependencies.py
- [x] T032 [P] Create rate limiting middleware in python_scripts/api/middleware/rate_limit.py (slowapi, IP-based)
- [x] T033 [P] Create Pydantic request schemas in python_scripts/api/schemas/requests.py
- [x] T034 [P] Create Pydantic response schemas in python_scripts/api/schemas/responses.py
- [x] T035 Create health check endpoint in python_scripts/api/routers/health.py
- [x] T036 Register health router in python_scripts/api/main.py
- [x] T037 Configure OpenAPI documentation (title, version, description from contracts/api.yaml)

### Agents Base Infrastructure

- [x] T038 [P] Create BaseAgent abstract class in python_scripts/agents/base_agent.py
- [x] T039 [P] Create LLM factory (Ollama) in python_scripts/agents/utils/llm_factory.py
- [x] T040 [P] Create prompts centralization module in python_scripts/agents/prompts.py (structure only)

### Ingestion Base

- [x] T041 [P] Create robots.txt parser in python_scripts/ingestion/robots_txt.py
- [x] T042 [P] Create text cleaner utility in python_scripts/ingestion/text_cleaner.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Analyser le style éditorial d'un site (Priority: Critical) 🎯 MVP

**Goal**: Analyser automatiquement le style éditorial d'un site web (crawl, analyse multi-LLM, génération profil)

**Independent Test**: POST /api/v1/sites/analyze avec domain valide → retourne execution_id → polling GET /api/v1/executions/{id} → status="completed" → GET /api/v1/sites/{domain} retourne profil complet

### Tests for User Story 1

- [x] T043 [P] [US1] Create unit test for robots.txt parser in tests/unit/test_robots_txt.py
- [x] T044 [P] [US1] Create unit test for text cleaner in tests/unit/test_text_cleaner.py
- [x] T045 [P] [US1] Create integration test for crawl workflow in tests/integration/test_crawl_workflow.py
- [x] T046 [P] [US1] Create E2E test for editorial analysis API in tests/e2e/test_api_sites.py (scenario: full workflow)

### Implementation for User Story 1

#### Ingestion & Crawling

- [x] T047 [P] [US1] Implement Crawl4AI async wrapper in python_scripts/ingestion/crawl_pages.py
- [x] T048 [US1] Implement sitemap detection in python_scripts/ingestion/detect_sitemaps.py
- [x] T049 [US1] Implement crawl_with_permissions function respecting robots.txt and crawl-delay in python_scripts/ingestion/crawl_pages.py
- [x] T050 [US1] Implement cache checking logic (30 days TTL) in python_scripts/ingestion/crawl_pages.py

#### Agent Analysis

- [x] T051 [US1] Implement agent_analysis.py with multi-LLM orchestration (llama3:8b, mistral:7b, phi3:medium)
- [x] T052 [US1] Add editorial style analysis prompts in python_scripts/agents/prompts.py (language level, tone, structure, keywords, audience)
- [x] T053 [US1] Implement LLM synthesis function merging 4 LLM analyses in python_scripts/agents/agent_analysis.py

#### Database CRUD

- [x] T054 [P] [US1] Implement CRUD operations for SiteProfile in python_scripts/database/crud_profiles.py
- [x] T055 [P] [US1] Implement CRUD operations for WorkflowExecution in python_scripts/database/crud_executions.py
- [x] T056 [P] [US1] Implement CRUD operations for SiteAnalysisResult in python_scripts/database/crud_executions.py

#### Workflow Orchestration

- [x] T057 [US1] Implement editorial analysis workflow function in python_scripts/agents/agent_orchestrator.py
- [x] T058 [US1] Implement background task runner for editorial analysis in python_scripts/api/routers/sites.py
- [x] T059 [US1] Add workflow state transitions (pending → running → completed/failed) in python_scripts/agents/agent_orchestrator.py

#### API Endpoints

- [x] T060 [US1] Implement POST /api/v1/sites/analyze endpoint in python_scripts/api/routers/sites.py
- [x] T061 [US1] Implement GET /api/v1/sites/{domain} endpoint in python_scripts/api/routers/sites.py
- [x] T062 [US1] Add request/response schemas for site analysis in python_scripts/api/schemas/requests.py and responses.py
- [x] T063 [US1] Register sites router in python_scripts/api/main.py

#### Audit & Metrics

- [x] T064 [US1] Add audit logging for workflow steps in python_scripts/agents/agent_orchestrator.py (integrated in orchestrator)
- [x] T065 [US1] Record performance metrics (duration, tokens consumed, pages crawled) in python_scripts/agents/agent_orchestrator.py
  - Duration tracked in `workflow_executions.duration_seconds`
  - Pages crawled tracked in `site_profiles.pages_analyzed`
  - Tokens consumed: NOT YET TRACKED (requires LLM response metadata extraction)
  - PerformanceMetrics table: NOT YET USED (table exists but no CRUD operations implemented)

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently. Can analyze a site and get editorial profile.

---

## Phase 4: User Story 2 - Consulter l'historique d'analyses (Priority: High)

**Goal**: Accéder à l'historique des analyses précédentes et comparer l'évolution

**Independent Test**: GET /api/v1/sites → liste des domaines analysés, GET /api/v1/sites/{domain}/history → évolution métriques dans le temps

### Tests for User Story 2

- [x] T066 [P] [US2] Create unit test for site history queries in tests/unit/test_crud_profiles.py
- [x] T067 [P] [US2] Create E2E test for site history API in tests/e2e/test_api_sites.py

### Implementation for User Story 2

- [x] T068 [US2] Implement GET /api/v1/sites endpoint (list all analyzed sites) in python_scripts/api/routers/sites.py
- [x] T069 [US2] Implement GET /api/v1/sites/{domain}/history endpoint in python_scripts/api/routers/sites.py
- [x] T070 [US2] Add query logic to fetch historical analyses for a domain in python_scripts/database/crud_profiles.py
- [x] T071 [US2] Add response schema for site history in python_scripts/api/schemas/responses.py
- [x] T072 [US2] Implement metrics comparison logic (temporal evolution) in python_scripts/api/routers/sites.py

**Checkpoint**: User Story 2 complete - can view analysis history and track evolution

---

## Phase 5: User Story 3 - Identifier les concurrents automatiquement (Priority: Critical)

**Goal**: Identifier automatiquement les concurrents via recherche multi-sources (Tavily, DuckDuckGo, Crawl4AI) et filtrage LLM

**Independent Test**: POST /api/v1/competitors/search avec domain → retourne execution_id → polling → GET /api/v1/competitors/{domain} retourne liste concurrents (min 3, max 20)

### Tests for User Story 3

- [x] T073 [P] [US3] Create unit test for competitor search sources (mocked) in tests/unit/test_competitor_search.py
- [x] T074 [P] [US3] Create integration test for competitor agent in tests/integration/test_agent_competitor.py
- [x] T075 [P] [US3] Create E2E test for competitor search API in tests/e2e/test_api_competitors.py

### Implementation for User Story 3

#### Competitor Search Agent

- [x] T076 [US3] Implement agent_competitor.py with multi-source search (Tavily, DuckDuckGo, Crawl4AI)
- [x] T077 [US3] Add competitor search prompts (LLM filtering) in python_scripts/agents/prompts.py
- [x] T078 [US3] Implement LLM filtering logic (phi3:medium) to remove false positives in python_scripts/agents/agent_competitor.py
- [x] T079 [US3] Implement result deduplication and ranking by relevance score in python_scripts/agents/agent_competitor.py

#### Database

- [x] T080 [US3] Create Competitor model (if needed for validation) or extend existing models
- [x] T081 [US3] Store competitor search results in workflow_executions.output_data (JSONB)

#### API Endpoints

- [x] T082 [US3] Implement POST /api/v1/competitors/search endpoint in python_scripts/api/routers/competitors.py
- [x] T083 [US3] Implement GET /api/v1/competitors/{domain} endpoint in python_scripts/api/routers/competitors.py
- [x] T084 [US3] Add request/response schemas for competitor search in python_scripts/api/schemas/requests.py and responses.py
- [x] T085 [US3] Register competitors router in python_scripts/api/main.py

#### Workflow Integration

- [x] T086 [US3] Integrate competitor search workflow in python_scripts/agents/agent_orchestrator.py
- [x] T087 [US3] Add competitor search background task runner in python_scripts/api/routers/competitors.py

**Checkpoint**: User Story 3 complete - can automatically identify competitors

---

## Phase 6: User Story 4 - Valider/ajuster la liste des concurrents (Priority: Medium)

**Goal**: Permettre validation/ajustement manuel de la liste de concurrents proposée

**Independent Test**: POST /api/v1/competitors/{domain}/validate avec liste modifiée → concurrents marqués validated/manual/excluded

### Tests for User Story 4

- [x] T088 [P] [US4] Create E2E test for competitor validation API in tests/e2e/test_api_competitors.py

### Implementation for User Story 4

- [x] T089 [US4] Implement POST /api/v1/competitors/{domain}/validate endpoint in python_scripts/api/routers/competitors.py
- [x] T090 [US4] Add validation logic (check domain existence, flag manual/excluded) in python_scripts/api/routers/competitors.py
- [x] T091 [US4] Update competitor storage in workflow_executions.output_data to include validation flags (validated, manual, excluded) as metadata
- [x] T092 [US4] Add request schema for competitor validation in python_scripts/api/schemas/requests.py

**Checkpoint**: User Story 4 complete - can validate and adjust competitor lists

---

## Phase 7: User Story 5 - Scraper les articles des concurrents (Priority: Critical)

**Goal**: Scraper automatiquement les articles de blog des concurrents en respectant robots.txt

**Independent Test**: POST /api/v1/scraping/competitors avec domaines → retourne execution_id → polling → GET /api/v1/scraping/articles retourne articles scrapés (max 100 par domaine)

### Tests for User Story 5

- [x] T093 [P] [US5] Create unit test for sitemap detection in tests/unit/test_detect_sitemaps.py
- [x] T094 [P] [US5] Create integration test for scraping workflow in tests/integration/test_scraping_workflow.py
- [x] T095 [P] [US5] Create E2E test for scraping API in tests/e2e/test_api_scraping.py

### Implementation for User Story 5

#### Scraping Agent

- [x] T096 [US5] Implement agent_scraping.py with article discovery (sitemap, RSS, heuristics)
- [x] T097 [US5] Implement article extraction from HTML (title, author, date, content, images) in python_scripts/ingestion/crawl_pages.py
- [x] T098 [US5] Add article filtering logic (min 250 words, max 2 years old) in python_scripts/agents/agent_scraping.py
- [x] T099 [US5] Implement URL deduplication by hash in python_scripts/agents/agent_scraping.py

#### Database

- [x] T100 [P] [US5] Implement CRUD operations for CompetitorArticle in python_scripts/database/crud_articles.py
- [x] T101 [US5] Implement scraping permissions caching (24h TTL) in python_scripts/ingestion/robots_txt.py
- [x] T102 [US5] Store scraping permissions in scraping_permissions table via CRUD

#### API Endpoints

- [x] T103 [US5] Implement POST /api/v1/scraping/competitors endpoint in python_scripts/api/routers/scraping.py (new router)
- [x] T104 [US5] Implement GET /api/v1/scraping/articles endpoint with filters (domain, limit, offset) in python_scripts/api/routers/scraping.py
- [x] T105 [US5] Add request/response schemas for scraping in python_scripts/api/schemas/requests.py and responses.py
- [x] T106 [US5] Register scraping router in python_scripts/api/main.py

#### Workflow Integration

- [x] T107 [US5] Integrate scraping workflow in python_scripts/agents/agent_orchestrator.py
- [x] T108 [US5] Add scraping background task runner in python_scripts/api/routers/scraping.py

**Checkpoint**: User Story 5 complete - can scrape competitor articles ethically

---

## Phase 8: User Story 6 - Indexer sémantiquement les articles (Priority: High)

**Goal**: Indexer les articles scrapés dans Qdrant avec embeddings pour recherche sémantique

**Independent Test**: After scraping, articles automatically indexed → search query returns semantically similar articles

### Tests for User Story 6

- [x] T109 [P] [US6] Create integration test for Qdrant indexing in tests/integration/test_qdrant_integration.py
- [x] T110 [P] [US6] Create unit test for embeddings generation in tests/unit/test_embeddings_utils.py

### Implementation for User Story 6

- [x] T111 [US6] Implement automatic embedding generation after article scraping in python_scripts/agents/agent_scraping.py
- [x] T112 [US6] Implement Qdrant indexing pipeline (generate embedding → upsert with payload) in python_scripts/vectorstore/qdrant_client.py
- [x] T113 [US6] Implement duplicate detection via cosine similarity (threshold 0.92) in python_scripts/vectorstore/qdrant_client.py
- [x] T114 [US6] Link Qdrant point_id to competitor_articles.qdrant_point_id in python_scripts/database/crud_articles.py
- [x] T115 [US6] Add semantic search function (query embedding → Qdrant search) in python_scripts/vectorstore/qdrant_client.py

**Checkpoint**: User Story 6 complete - articles indexed semantically with deduplication

---

## Phase 9: User Story 7 - Analyser les tendances avec BERTopic (Priority: Critical)

**Goal**: Découvrir automatiquement les topics dominants avec BERTopic et générer visualisations

**Independent Test**: POST /api/v1/trends/analyze avec domaines et time_window → retourne execution_id → polling → GET /api/v1/trends/topics retourne topics découverts (min 5, max 50)

### Tests for User Story 7

-  T116 [P] [US7] Create integration test for BERTopic pipeline in tests/integration/test_bertopic_pipeline.py
-  T117 [P] [US7] Create E2E test for trends analysis API in tests/e2e/test_api_trends.py

### Implementation for User Story 7

#### Topic Modeling

- [x] T118 [US7] Implement agent_topic_modeling.py with BERTopic pipeline (from research.md)
- [x] T119 [US7] Configure BERTopic with optimal hyperparameters (min_topic_size=10, nr_topics="auto") in python_scripts/analysis/topic_modeling.py
- [x] T120 [US7] Implement temporal topic evolution analysis in python_scripts/analysis/topic_modeling.py
- [x] T121 [US7] Implement emerging topics detection (comparison time windows) in python_scripts/analysis/topic_modeling.py
- [x] T122 [US7] Implement topic hierarchy generation in python_scripts/analysis/topic_modeling.py

#### Visualizations

- [x] T123 [US7] Generate BERTopic visualizations (topics 2D, barchart, evolution, heatmap) in python_scripts/analysis/topic_modeling.py
- [x] T124 [US7] Save visualizations to /mnt/user-data/outputs/visualizations/ (or configurable path) in python_scripts/analysis/topic_modeling.py

#### Database

- [x] T125 [P] [US7] Implement CRUD operations for BertopicAnalysis in python_scripts/database/crud_topics.py
- [x] T126 [US7] Store BERTopic results (topics, hierarchy, evolution, visualization paths) in bertopic_analysis table
- [x] T127 [US7] Link topics to articles via topic_id in competitor_articles table

#### API Endpoints

- [x] T128 [US7] Implement POST /api/v1/trends/analyze endpoint in python_scripts/api/routers/trends.py
- [x] T129 [US7] Implement GET /api/v1/trends/topics endpoint with time_window filter in python_scripts/api/routers/trends.py
- [x] T130 [US7] Add request/response schemas for trends in python_scripts/api/schemas/requests.py and responses.py
- [x] T131 [US7] Register trends router in python_scripts/api/main.py

#### Workflow Integration

- [x] T132 [US7] Integrate BERTopic analysis workflow in python_scripts/agents/agent_orchestrator.py
- [x] T133 [US7] Add trends analysis background task runner in python_scripts/api/routers/trends.py

**Checkpoint**: User Story 7 complete - can analyze trends with BERTopic and generate visualizations

---

## Phase 10: User Story 8 - Identifier les gaps de contenu (Priority: High)

**Goal**: Comparer topics client vs concurrents pour identifier gaps et générer recommandations

**Independent Test**: GET /api/v1/trends/gaps?client_domain=X → retourne gaps avec scores et recommandations

### Tests for User Story 8

-  T134 [P] [US8] Create unit test for gap analysis logic in tests/unit/test_gap_analysis.py
-  T135 [P] [US8] Create E2E test for gaps API in tests/e2e/test_api_trends.py

### Implementation for User Story 8

-  T136 [US8] Implement gap analysis logic (compare client topics vs competitor topics) in python_scripts/analysis/trend_synthesizer.py
-  T137 [US8] Calculate gap score (frequency × importance) in python_scripts/analysis/trend_synthesizer.py
-  T138 [US8] Implement content recommendations generation (title, keywords, angle) per gap in python_scripts/analysis/trend_synthesizer.py
-  T139 [US8] Implement gap tracking (mark addressed when client publishes on topic) in python_scripts/analysis/trend_synthesizer.py
-  T140 [US8] Implement GET /api/v1/trends/gaps endpoint in python_scripts/api/routers/trends.py
-  T141 [US8] Add response schema for gaps in python_scripts/api/schemas/responses.py

**Checkpoint**: User Story 8 complete - can identify content gaps and provide recommendations

---

## Phase 11: User Story 9 - Exposer tous les workflows via API REST (Priority: Critical)

**Goal**: Exposer tous les workflows via API REST avec documentation OpenAPI et WebSocket pour progression

**Independent Test**: All endpoints accessible via /docs (Swagger UI), WebSocket connection works for progress streaming

### Tests for User Story 9

-  T142 [P] [US9] Create E2E test for all API endpoints in tests/e2e/test_api_complete.py
-  T143 [P] [US9] Create WebSocket test for progress streaming in tests/e2e/test_websocket_progress.py

### Implementation for User Story 9

#### Execution Tracking

-  T144 [US9] Implement GET /api/v1/executions/{execution_id} endpoint in python_scripts/api/routers/executions.py
-  T145 [US9] Add response schema for execution status in python_scripts/api/schemas/responses.py

#### WebSocket Progress

-  T146 [US9] Implement WebSocket endpoint /api/v1/executions/{execution_id}/stream in python_scripts/api/routers/executions.py
-  T147 [US9] Integrate progress callbacks in workflow orchestration (emit progress events) in python_scripts/agents/agent_orchestrator.py
-  T148 [US9] Register executions router in python_scripts/api/main.py

#### API Documentation

-  T149 [US9] Verify OpenAPI schema matches contracts/api.yaml specification
-  T150 [US9] Add comprehensive docstrings to all endpoints (FastAPI docstrings)
-  T151 [US9] Ensure all endpoints have examples in OpenAPI schema

**Checkpoint**: User Story 9 complete - all workflows accessible via REST API with WebSocket support

---

## Phase 12: User Story 10 - Gérer les workflows avec traçabilité complète (Priority: High)

**Goal**: Tracer toutes les exécutions avec audit logs, métriques de performance, et gestion d'erreurs

**Independent Test**: Workflow execution → audit_log entries created → performance_metrics recorded → errors logged with stack traces

### Tests for User Story 10

-  T152 [P] [US10] Create unit test for audit logging in tests/unit/test_audit_logging.py
-  T153 [P] [US10] Create integration test for workflow traceability in tests/integration/test_workflow_traceability.py

### Implementation for User Story 10

#### Audit Logging

-  T154 [US10] Implement audit log creation for all workflow steps in python_scripts/agents/base_agent.py
-  T155 [US10] Add structured audit logging with context (execution_id, agent_name, step_name) in python_scripts/utils/logging.py
-  T156 [P] [US10] Implement CRUD operations for AuditLog in python_scripts/database/crud_executions.py

#### Performance Metrics

-  T157 [US10] Record performance metrics (duration, tokens, pages crawled) after each workflow step in python_scripts/agents/agent_orchestrator.py
-  T158 [P] [US10] Implement CRUD operations for PerformanceMetric in python_scripts/database/crud_executions.py

#### Error Handling

-  T159 [US10] Implement comprehensive error handling with stack trace logging in python_scripts/agents/agent_orchestrator.py
-  T160 [US10] Update workflow_executions status to "failed" with error_message on exceptions in python_scripts/agents/agent_orchestrator.py
-  T161 [US10] Implement retry logic with tenacity (max 3 attempts, exponential backoff) for I/O operations

**Checkpoint**: User Story 10 complete - full traceability and observability implemented

---

## Phase 13: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

### Data Retention & Purge

-  T162 [P] Implement scheduled purge job (APScheduler) for 90-day data retention in python_scripts/jobs/purge_old_data.py
-  T163 [P] Configure purge job to run daily at 2 AM UTC in python_scripts/jobs/purge_old_data.py
-  T164 [P] Implement cascade deletion (Qdrant + PostgreSQL) in python_scripts/jobs/purge_old_data.py
-  T165 [P] Add audit logging for purge operations in python_scripts/jobs/purge_old_data.py

### Cache Management

-  T166 [P] Implement crawl_cache expiration logic (30 days) in python_scripts/ingestion/crawl_pages.py
-  T167 [P] Implement scraping_permissions cache refresh (24h TTL) in python_scripts/ingestion/robots_txt.py

### Monitoring & Health Checks

-  T168 Enhance health check endpoint to verify PostgreSQL, Qdrant, Ollama connectivity in python_scripts/api/routers/health.py
-  T169 Add latency metrics to health check response in python_scripts/api/routers/health.py
-  T170 Add Ollama models availability check in health endpoint in python_scripts/api/routers/health.py

### Documentation

-  T171 [P] Update README.md with complete setup instructions referencing quickstart.md
-  T172 [P] Create architecture documentation in docs/architecture.md
-  T173 [P] Create agents documentation in docs/agents.md
-  T174 [P] Create database schema documentation in docs/database.md

### Code Quality

-  T175 [P] Run full test suite and ensure ≥80% coverage (pytest --cov)
-  T176 [P] Fix all linting errors (ruff, black, mypy strict)
-  T177 [P] Add missing type hints to all functions
-  T178 [P] Add Google-style docstrings to all public functions

### Validation

-  T179 Run quickstart.md validation (follow all steps, verify they work)
-  T180 Validate all API endpoints match contracts/api.yaml specification
-  T181 Verify all database migrations work (up and down)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - **BLOCKS all user stories**
- **User Stories (Phase 3-12)**: All depend on Foundational phase completion
  - User stories can proceed in parallel after Foundational (if staffed)
  - Or sequentially in priority order (US1 → US2 → US3 → ...)
- **Polish (Phase 13)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1 - MVP)**: Can start after Foundational - **No dependencies on other stories**
- **User Story 2 (High)**: Can start after Foundational - Depends on US1 (needs site_profiles)
- **User Story 3 (Critical)**: Can start after Foundational - Depends on US1 (needs site_profiles for competitor search context)
- **User Story 4 (Medium)**: Depends on US3 (needs competitor search results)
- **User Story 5 (Critical)**: Can start after Foundational - Depends on US3/US4 (needs validated competitors)
- **User Story 6 (High)**: Depends on US5 (needs scraped articles)
- **User Story 7 (Critical)**: Depends on US6 (needs indexed articles for embeddings)
- **User Story 8 (High)**: Depends on US1 and US7 (needs client profile + competitor topics)
- **User Story 9 (Critical)**: Can start after Foundational - Integrates with all workflows
- **User Story 10 (High)**: Can start after Foundational - Should be integrated throughout all workflows

### Within Each User Story

- Tests (if included) MUST be written and FAIL before implementation
- Models before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- **Setup Phase**: All [P] tasks can run in parallel
- **Foundational Phase**: All [P] tasks can run in parallel (models, utilities, base setup)
- **After Foundational**: All user stories can start in parallel (if team capacity allows)
- **Within each story**: Tests marked [P], models marked [P] can run in parallel
- **Polish Phase**: All [P] tasks can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all foundational models together:
T013, T014, T015, T016, T017, T018, T019, T020, T021, T022 (all [P])

# Launch all US1 tests together:
T043, T044, T045, T046 (all [P] [US1])

# Launch CRUD operations together:
T054, T055, T056 (all [P] [US1])
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. ✅ Complete Phase 1: Setup
2. ✅ Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. ✅ Complete Phase 3: User Story 1 (Editorial Analysis)
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

**MVP Deliverable**: System can analyze editorial style of a website and return complete profile via API

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo
4. Add User Story 3 → Test independently → Deploy/Demo
5. Add User Story 5 → Test independently → Deploy/Demo
6. Add User Story 6 → Test independently → Deploy/Demo
7. Add User Story 7 → Test independently → Deploy/Demo
8. Add remaining stories → Test independently → Deploy/Demo
9. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - **Developer A**: User Story 1 (MVP) - Editorial Analysis
   - **Developer B**: User Story 9 - API REST + WebSocket
   - **Developer C**: User Story 10 - Traceability
3. Next wave:
   - **Developer A**: User Story 3 - Competitor Search
   - **Developer B**: User Story 5 - Scraping
   - **Developer C**: User Story 7 - BERTopic Analysis
4. Final wave:
   - Remaining stories (US2, US4, US6, US8)
5. Polish phase: All developers contribute

---

## Task Summary

- **Total Tasks**: 181
- **Setup Phase**: 8 tasks
- **Foundational Phase**: 33 tasks
- **User Story 1 (MVP)**: 23 tasks
- **User Story 2**: 7 tasks
- **User Story 3**: 15 tasks
- **User Story 4**: 5 tasks
- **User Story 5**: 16 tasks
- **User Story 6**: 7 tasks
- **User Story 7**: 18 tasks
- **User Story 8**: 8 tasks
- **User Story 9**: 10 tasks
- **User Story 10**: 10 tasks
- **Polish Phase**: 22 tasks

### Parallel Opportunities

- **Setup**: 5 parallel tasks
- **Foundational**: 20+ parallel tasks (models, utilities)
- **User Stories**: Can be worked on in parallel after Foundational
- **Within stories**: Tests and models often parallelizable

### MVP Scope

**MVP includes**: Setup + Foundational + User Story 1 (Editorial Analysis)

**MVP delivers**: System that can analyze editorial style of websites via API

---

## Notes

- [P] tasks = different files, no dependencies - can run in parallel
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence

---

**Status**: ✅ **TASKS GENERATED - READY FOR IMPLEMENTATION**  
**Generated**: 2025-01-25  
**Total Tasks**: 181  
**MVP Tasks**: 64 (Setup + Foundational + US1)