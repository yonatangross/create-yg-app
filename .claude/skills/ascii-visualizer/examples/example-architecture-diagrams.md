# Real-World Architecture Diagrams

Complete ASCII architecture visualizations showcasing modern web application patterns, microservices, and AI/ML integration systems.

## Modern SaaS Application Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          MODERN SAAS PLATFORM                                │
│              E-commerce Platform with AI Recommendations                     │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    React 19 SPA (Vite)                               │   │
│  │                      Port: 5173                                      │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │  Components:                                                         │   │
│  │  • ProductList (Infinite Scroll)                                     │   │
│  │  • CheckoutFlow (Multi-step Form)                                    │   │
│  │  • UserDashboard (Real-time Orders)                                  │   │
│  │  • RecommendationWidget (AI-powered)                                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                          HTTPS + SSE
                                 │
┌────────────────────────────────▼────────────────────────────────────────────┐
│                          APPLICATION LAYER                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    FastAPI Backend                                   │   │
│  │                      Port: 8000                                      │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │  Core Services:                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  Product     │  │   Order      │  │   User       │              │   │
│  │  │  Service     │  │   Service    │  │   Service    │              │   │
│  │  │              │  │              │  │              │              │   │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │   │
│  │         │                 │                 │                       │   │
│  │         └─────────────────┼─────────────────┘                       │   │
│  │                           │                                         │   │
│  │  ┌────────────────────────▼──────────────────────────┐              │   │
│  │  │         AI Recommendation Engine                  │              │   │
│  │  │  ┌────────────────────────────────────────────┐   │              │   │
│  │  │  │       Vector Similarity Search              │   │              │   │
│  │  │  │       (pgvector + embeddings)              │   │              │   │
│  │  │  └────────────────────────────────────────────┘   │              │   │
│  │  └──────────────────────────────────────────────────┘              │   │
│  │                                                                      │   │
│  │  ┌──────────────────────────────────────────────────┐               │   │
│  │  │          Event Broadcasting (SSE)                │               │   │
│  │  │  • Order status updates                          │               │   │
│  │  │  • Inventory changes                             │               │   │
│  │  │  • Recommendation refresh                        │               │   │
│  │  └──────────────────────────────────────────────────┘               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────────┐
│                            DATA LAYER                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────┐  ┌───────────────┐  ┌─────────────────────┐    │
│  │   PostgreSQL + PGVector│  │  Redis Cache  │  │   Elasticsearch     │    │
│  │      Port: 5432       │  │  Port: 6379   │  │   (Search Index)    │    │
│  ├───────────────────────┤  ├───────────────┤  └─────────────────────┘    │
│  │ Tables:               │  │ Caches:       │                              │
│  │ • users               │  │ • Sessions    │                              │
│  │ • products            │  │ • Cart data   │                              │
│  │ • orders              │  │ • Hot products│                              │
│  │ • product_embeddings  │  │ • User prefs  │                              │
│  │   (HNSW index)        │  └───────────────┘                              │
│  └───────────────────────┘                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Microservices with Event-Driven Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EVENT-DRIVEN MICROSERVICES                                │
│                  Real-time Order Processing System                           │
└─────────────────────────────────────────────────────────────────────────────┘

                           ┌──────────────────┐
                           │  API Gateway     │
                           │  (Kong/Traefik)  │
                           └────────┬─────────┘
                                    │
                ┌───────────────────┼───────────────────┐
                │                   │                   │
      ┌─────────▼────────┐ ┌────────▼────────┐ ┌───────▼──────────┐
      │  Order Service   │ │  Payment Svc    │ │  Inventory Svc   │
      │  (Node.js)       │ │  (Python)       │ │  (Go)            │
      └─────────┬────────┘ └────────┬────────┘ └───────┬──────────┘
                │                   │                   │
                └───────────────────┼───────────────────┘
                                    │
                          ┌─────────▼─────────┐
                          │   Kafka Cluster   │
                          │   (Event Stream)  │
                          └─────────┬─────────┘
                                    │
        ┌──────────────────────────┼──────────────────────┐
        │                          │                      │
┌───────▼────────┐        ┌────────▼───────┐    ┌────────▼───────┐
│  Notification  │        │  Analytics     │    │  Email Worker  │
│  Service       │        │  Service       │    │  (Celery)      │
│  (Serverless)  │        │  (Spark)       │    │                │
└────────────────┘        └────────────────┘    └────────────────┘


Event Flow:
┌─────────────────────────────────────────────────────────────┐
│ Order Created → Payment Processed → Inventory Reserved      │
│      ↓               ↓                    ↓                 │
│  Email Sent    Analytics Updated    Shipping Notification  │
└─────────────────────────────────────────────────────────────┘
```

## AI/ML Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│              ML CONTENT ANALYSIS PIPELINE                                    │
│         Document Processing with Multi-Agent Analysis                        │
└─────────────────────────────────────────────────────────────────────────────┘

User Upload
    │
    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  Ingestion API (FastAPI)                                                    │
│  • File validation                                                          │
│  • Format detection (PDF, DOCX, Markdown)                                   │
│  • Queue to processing pipeline                                             │
└────────────────┬───────────────────────────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  Document Processing                                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                     │
│  │ OCR Engine   │  │ Text Extract │  │ Chunking     │                     │
│  │ (Tesseract)  │  │ (PyPDF2)     │  │ (500-2000ch) │                     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                     │
│         └─────────────────┼─────────────────┘                              │
└───────────────────────────┼────────────────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  Embedding Generation                                                       │
│  ┌──────────────────────────────────────┐                                  │
│  │  OpenAI text-embedding-3-large       │                                  │
│  │  3072 dimensions                     │                                  │
│  │  Batched processing (100 chunks/req) │                                  │
│  └──────────────────┬───────────────────┘                                  │
└─────────────────────┼──────────────────────────────────────────────────────┘
                      │
                      ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  Multi-Agent Analysis (LangGraph)                                           │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │               Supervisor Agent (Router)                          │     │
│  └──────────────────────────────┬───────────────────────────────────┘     │
│                                 │                                         │
│      ┌──────────────────────────┼──────────────────────────┐             │
│      │                          │                          │             │
│  ┌───▼───────┐          ┌───────▼────┐          ┌─────────▼──────┐      │
│  │ Summarizer│          │ Code       │          │ Security       │      │
│  │ Agent     │          │ Analyzer   │          │ Auditor        │      │
│  │ (GPT-4)   │          │ (Claude)   │          │ (GPT-4)        │      │
│  └───┬───────┘          └───────┬────┘          └─────────┬──────┘      │
│      │                          │                          │             │
│      └──────────────────────────┼──────────────────────────┘             │
└─────────────────────────────────┼────────────────────────────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  Result Aggregation & Storage                                               │
│  ┌──────────────────────┐     ┌──────────────────────┐                    │
│  │  PostgreSQL          │     │  Vector Store        │                    │
│  │  • Document metadata │     │  (Pinecone/Weaviate) │                    │
│  │  • Analysis results  │     │  • Chunked embeddings│                    │
│  │  • Agent findings    │     │  • Hybrid search     │                    │
│  └──────────────────────┘     └──────────────────────┘                    │
└────────────────────────────────────────────────────────────────────────────┘
```

## Database Schema - E-commerce Platform

```
┌──────────────────────────────────────────────────────────────────┐
│                    E-COMMERCE DATABASE SCHEMA                     │
│                      PostgreSQL + Extensions                      │
└──────────────────────────────────────────────────────────────────┘

┌─────────────────────┐              ┌─────────────────────┐
│       users         │              │     products        │
├─────────────────────┤              ├─────────────────────┤
│ id (PK)       SERIAL│              │ id (PK)       SERIAL│
│ email        VARCHAR│              │ name          VARCHAR│
│ password_hash TEXT  │              │ description     TEXT│
│ created_at TIMESTAMP│              │ price       DECIMAL │
│ updated_at TIMESTAMP│              │ stock_qty       INT │
└───────┬─────────────┘              │ category_id (FK) INT│
        │                            │ created_at TIMESTAMP│
        │ 1                          └──────────┬──────────┘
        │                                       │
        │                                       │ 1
        │                                       │
        │ *                                     │ *
┌───────▼─────────────┐              ┌──────────▼──────────┐
│       orders        │              │  product_embeddings │
├─────────────────────┤              ├─────────────────────┤
│ id (PK)       SERIAL│              │ id (PK)       SERIAL│
│ user_id (FK)    INT │──┐           │ product_id (FK) INT │───┐
│ status         ENUM │  │           │ embedding    VECTOR │   │
│ total         DECIMAL│  │           │ model_version   INT │   │
│ created_at TIMESTAMP│  │           │ created_at TIMESTAMP│   │
└─────────────────────┘  │           │                     │   │
                         │           │ INDEXES:            │   │
                         │           │ • HNSW (embedding)  │   │
                         │           └─────────────────────┘   │
                         │                                     │
┌────────────────────────┘                                     │
│                                                              │
│  ┌──────────────────────┐                                   │
│  │   order_items        │                                   │
│  ├──────────────────────┤                                   │
│  │ id (PK)        SERIAL│                                   │
│  │ order_id (FK)    INT │                                   │
│  │ product_id (FK)  INT │───────────────────────────────────┘
│  │ quantity         INT │
│  │ price_at_time DECIMAL│
│  └──────────────────────┘
│
│  ┌──────────────────────┐
│  │     reviews          │
│  ├──────────────────────┤
│  │ id (PK)        SERIAL│
│  │ user_id (FK)     INT │
│  │ product_id (FK)  INT │
│  │ rating           INT │
│  │ comment          TEXT│
│  │ created_at TIMESTAMP │
│  └──────────────────────┘
```

## Hybrid Search Architecture (BM25 + Vector)

```
┌─────────────────────────────────────────────────────────────────────┐
│               HYBRID SEARCH (PGVector + BM25 RRF)                    │
│          Reciprocal Rank Fusion for Optimal Results                 │
└─────────────────────────────────────────────────────────────────────┘

User Query: "Best wireless headphones under $200"
     │
     └─────────────────────┬─────────────────────┐
                           │                     │
                  ┌────────▼────────┐   ┌────────▼────────┐
                  │  Semantic       │   │  Keyword (BM25) │
                  │  Search         │   │  Search         │
                  ├─────────────────┤   ├─────────────────┤
                  │ 1. Embed query  │   │ 1. Parse terms  │
                  │    (OpenAI)     │   │ 2. ts_rank      │
                  │ 2. Vector sim   │   │    scoring      │
                  │    (cosine)     │   │ 3. GIN index    │
                  │ 3. HNSW index   │   │ 4. Fetch top 30 │
                  │ 4. Fetch top 30 │   │                 │
                  └────────┬────────┘   └────────┬────────┘
                           │                     │
                           │  Results (scored)   │
                           │                     │
                  ┌────────▼─────────────────────▼────────┐
                  │  Reciprocal Rank Fusion (RRF)         │
                  ├────────────────────────────────────────┤
                  │  For each result:                     │
                  │    score = Σ(1 / (k + rank))          │
                  │      k = 60 (RRF constant)            │
                  │                                       │
                  │  Merge & deduplicate by product_id    │
                  │  Sort by combined score               │
                  └────────┬───────────────────────────────┘
                           │
                  ┌────────▼───────────────────────────────┐
                  │  Metadata Boosting                     │
                  ├────────────────────────────────────────┤
                  │  • Category match: ×1.3                │
                  │  • Price range filter: ×1.2            │
                  │  • High rating (4.5+): ×1.15           │
                  │  • In stock: ×1.1                      │
                  └────────┬───────────────────────────────┘
                           │
                  ┌────────▼───────────────────────────────┐
                  │  Return Top 10 Products                │
                  │  Sorted by final boosted score         │
                  └────────────────────────────────────────┘

Example Results:
┌────┬──────────────────────────┬───────────┬──────────┬────────────┐
│Rank│      Product Name        │  Semantic │ Keyword  │ Final Score│
│    │                          │   Score   │  Score   │  (boosted) │
├────┼──────────────────────────┼───────────┼──────────┼────────────┤
│  1 │ Sony WH-1000XM5          │   0.94    │  0.89    │    2.01    │
│  2 │ Bose QuietComfort 45     │   0.91    │  0.92    │    1.98    │
│  3 │ Apple AirPods Max        │   0.88    │  0.76    │    1.72    │
│  4 │ Sennheiser HD 450BT      │   0.82    │  0.81    │    1.61    │
│  5 │ JBL Tour One             │   0.79    │  0.78    │    1.55    │
└────┴──────────────────────────┴───────────┴──────────┴────────────┘
```

## Deployment Architecture - Kubernetes

```
┌─────────────────────────────────────────────────────────────────────┐
│                      KUBERNETES DEPLOYMENT                           │
│                    Production Multi-Region Setup                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                          INTERNET                                    │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                  ┌──────────▼──────────┐
                  │  Cloudflare CDN     │
                  │  (SSL, DDoS, WAF)   │
                  └──────────┬──────────┘
                             │
┌────────────────────────────┼────────────────────────────────────────┐
│         Kubernetes Cluster (us-east-1)                              │
│                            │                                        │
│                  ┌─────────▼──────────┐                             │
│                  │  Ingress-Nginx     │                             │
│                  │  (Load Balancer)   │                             │
│                  └──┬────────────┬────┘                             │
│                     │            │                                  │
│        ┌────────────┘            └────────────┐                     │
│        │                                      │                     │
│  ┌─────▼──────────────┐            ┌──────────▼──────────┐          │
│  │  Frontend Pod      │            │  Backend Pod        │          │
│  │  ┌──────────────┐  │            │  ┌──────────────┐   │          │
│  │  │ React App    │  │            │  │  FastAPI     │   │          │
│  │  │ (Nginx)      │  │            │  │  + Gunicorn  │   │          │
│  │  │ Replicas: 3  │  │            │  │  Replicas: 5 │   │          │
│  │  └──────────────┘  │            │  └──────────────┘   │          │
│  └────────────────────┘            └──────────┬──────────┘          │
│                                               │                     │
│                                    ┌──────────┴──────────┐          │
│                                    │                     │          │
│                            ┌───────▼──────┐    ┌────────▼──────┐   │
│                            │  PostgreSQL  │    │  Redis        │   │
│                            │  StatefulSet │    │  StatefulSet  │   │
│                            │  Replicas: 3 │    │  Replicas: 3  │   │
│                            │  (Primary +  │    │  (Sentinel)   │   │
│                            │   Replicas)  │    └───────────────┘   │
│                            └──────────────┘                        │
│                                                                     │
│  Persistent Volumes:                                                │
│  • PostgreSQL: AWS EBS (gp3, 500GB)                                 │
│  • Redis: AWS EBS (gp3, 100GB)                                      │
│  • Logs: EFS (shared across pods)                                   │
└─────────────────────────────────────────────────────────────────────┘
```

## Caching Strategy - Multi-Level

```
┌─────────────────────────────────────────────────────────────────────┐
│            MULTI-LEVEL CACHING (85% Cache Hit Rate)                  │
└─────────────────────────────────────────────────────────────────────┘

Request: "GET /api/products/123"
    │
    └──────────────────┬──────────────────────────┐
                       │                          │
              ┌────────▼────────┐        ┌────────▼────────┐
              │  L1: CDN Edge   │        │ L2: Application │
              │  (Cloudflare)   │        │  Memory (LRU)   │
              ├─────────────────┤        ├─────────────────┤
              │ • 50+ locations │        │ • Hot data      │
              │ • TTL: 5 min    │        │ • TTL: 2 min    │
              │ • Hit: 40%      │        │ • Max: 1000 keys│
              └────────┬────────┘        │ • Hit: 25%      │
                   Hit │                 └────────┬────────┘
                       └──────────────┬───────Hit │
                                      │           │
                                 Miss │      Miss │
                              ┌───────▼───────────▼───┐
                              │ L3: Redis Cluster     │
                              │  (Distributed Cache)  │
                              ├───────────────────────┤
                              │ • Shared across pods  │
                              │ • TTL: 1 hour         │
                              │ • Persistence: AOF    │
                              │ • Hit: 20%            │
                              └────────┬──────────────┘
                                   Hit │
                                       │
                                  Miss │
                              ┌────────▼────────┐
                              │  PostgreSQL     │
                              │  (Source of     │
                              │   Truth)        │
                              ├─────────────────┤
                              │ • Full data     │
                              │ • Hit: 15%      │
                              │ • Backfill all  │
                              │   cache levels  │
                              └─────────────────┘

Cache Hit Rates:
┌─────────────┬──────────┬───────────────┬──────────────┐
│ Cache Level │ Hit Rate │ Avg Latency   │ Traffic %    │
├─────────────┼──────────┼───────────────┼──────────────┤
│ L1 CDN      │   40%    │    10-50ms    │     40%      │
│ L2 Memory   │   25%    │    < 1ms      │     25%      │
│ L3 Redis    │   20%    │    2-5ms      │     20%      │
│ DB Query    │   15%    │    20-100ms   │     15%      │
├─────────────┼──────────┼───────────────┼──────────────┤
│ Overall     │   85%    │    ~15ms      │    100%      │
└─────────────┴──────────┴───────────────┴──────────────┘
```

---

**Diagram Conventions:**
- `┌─┐ └─┘` Single-line boxes for components
- `╔═╗ ╚═╝` Double-line boxes for emphasis/grouping
- `→ ⇒` Arrows for data flow
- `[✓] [✗] [○] [▶]` Status indicators
- `████░░░░` Progress bars (filled/empty blocks)

**Real-World Examples:**
- E-commerce platform with AI recommendations
- Event-driven microservices with Kafka
- ML document processing pipeline
- Kubernetes multi-region deployment
- Multi-level caching strategy
