# Example Golden Dataset Workflow

**Real-world workflow for managing a production golden dataset for AI/ML applications**

---

## Use Case: E-Commerce Product Search

### Dataset Overview

**Application:** E-commerce platform with hybrid search (vector + keyword)

**Dataset Purpose:**
- Test product search quality across categories
- Benchmark different embedding models
- Regression testing for search algorithm changes
- A/B test ranking strategies

**Dataset Stats:**
- **150 product documents** (electronics, clothing, home goods)
- **600 chunks** (product descriptions, reviews, specs)
- **250 test queries** (customer search patterns)
- **Target: 92% pass rate** (queries returning relevant products)

---

## Workflow 1: Initial Dataset Creation

### Step 1: Curate Source Documents

```bash
# Prepare product catalog documents
mkdir -p data/products
cd data/products

# Export from production database (anonymized)
psql $DATABASE_URL -c "
  COPY (
    SELECT
      id,
      name,
      description,
      category,
      specifications,
      avg_rating,
      review_count
    FROM products
    WHERE is_published = true
      AND avg_rating >= 4.0
    ORDER BY review_count DESC
    LIMIT 150
  ) TO '/tmp/products.csv' CSV HEADER;
"

# Convert to JSON format
python scripts/csv_to_golden_dataset.py \
  --input /tmp/products.csv \
  --output data/products/documents_expanded.json \
  --content-type "product_catalog"
```

### Step 2: Generate Test Queries

```python
# scripts/generate_test_queries.py
"""Generate test queries from real search logs."""

import json
from collections import Counter
from pathlib import Path

def extract_queries_from_logs(log_file: Path) -> list[dict]:
    """Extract common search queries from production logs."""

    # Load search logs (anonymized)
    with open(log_file) as f:
        logs = [json.loads(line) for line in f]

    # Count query frequency
    query_counter = Counter(log["query"] for log in logs)

    # Generate test cases
    test_queries = []

    for idx, (query, count) in enumerate(query_counter.most_common(250)):
        # Find products that were clicked for this query
        clicked_products = [
            log["product_id"]
            for log in logs
            if log["query"] == query and log.get("clicked")
        ]

        if not clicked_products:
            continue

        # Create test query
        test_queries.append({
            "id": f"q-{idx+1}",
            "query": query,
            "expected_chunks": [f"product-{pid}" for pid in clicked_products[:5]],
            "min_score": 0.6,
            "modes": ["semantic", "hybrid"],
            "category": "specific",
            "difficulty": classify_difficulty(query),
            "description": f"Real user query: '{query}' (frequency: {count})",
        })

    return test_queries

# Run
queries = extract_queries_from_logs(Path("logs/search.jsonl"))
with open("data/products/queries.json", "w") as f:
    json.dump({"version": "1.0", "queries": queries}, f, indent=2)
```

### Step 3: Load Into Database

```bash
cd backend

# Load documents and generate embeddings
python scripts/load_golden_dataset.py \
  --documents data/products/documents_expanded.json \
  --queries data/products/queries.json \
  --embedding-model text-embedding-3-small

# Output:
# ✅ Loaded 150 documents
# ✅ Generated 600 chunks
# ✅ Created 250 test queries
# ⏱️  Embedding generation: 2.5 minutes
```

### Step 4: Validate Quality

```bash
# Run retrieval quality tests
pytest tests/smoke/retrieval/test_retrieval_quality.py -v

# Expected output:
# test_query_1_wireless_headphones PASSED (score: 0.87)
# test_query_2_laptop_under_1000 PASSED (score: 0.79)
# test_query_3_running_shoes_size_10 FAILED (score: 0.45)
# ...
# 230 passed, 20 failed (92% pass rate)

# Investigate failures
python scripts/analyze_query_failures.py \
  --threshold 0.6 \
  --output reports/query_failures.json
```

### Step 5: Create Baseline Backup

```bash
# Create initial backup
python scripts/backup_golden_dataset.py backup

# Expected output:
# ✅ BACKUP COMPLETE
#    Analyses:  150
#    Chunks:    600
#    Queries:   250
#    Location:  data/golden_dataset_backup.json

# Commit to version control
git add data/golden_dataset_backup.json
git add data/golden_dataset_metadata.json
git commit -m "feat: initial golden dataset (150 products, 92% pass rate)"
git push
```

---

## Workflow 2: Expanding Dataset

### Scenario: Add New Product Category

**Goal:** Improve search quality for "Home & Garden" category

### Step 1: Identify Coverage Gap

```python
# scripts/analyze_coverage.py
"""Analyze category coverage in golden dataset."""

import json

# Load current dataset
with open("data/golden_dataset_backup.json") as f:
    backup = json.load(f)

# Count by category
categories = {}
for doc in backup["analyses"]:
    category = doc.get("category", "unknown")
    categories[category] = categories.get(category, 0) + 1

# Report
for category, count in sorted(categories.items(), key=lambda x: -x[1]):
    print(f"{category:20} {count:3} ({count/len(backup['analyses'])*100:.1f}%)")

# Output:
# Electronics          60 (40.0%)
# Clothing             50 (33.3%)
# Home & Garden        20 (13.3%)  ← Underrepresented
# Sports              15 (10.0%)
# Other                5 ( 3.3%)
```

### Step 2: Curate New Documents

```bash
# Export top Home & Garden products
psql $DATABASE_URL -c "
  SELECT id, name, description, category
  FROM products
  WHERE category = 'Home & Garden'
    AND avg_rating >= 4.5
  ORDER BY review_count DESC
  LIMIT 30;
" > home_garden_products.txt

# Add to documents_expanded.json manually or via script
```

### Step 3: Add and Validate

```bash
# Reload dataset
python scripts/load_golden_dataset.py \
  --documents data/products/documents_expanded.json \
  --mode update  # Only add new documents

# Run tests
pytest tests/smoke/retrieval/test_retrieval_quality.py -v

# New stats:
# 180 documents (was 150)
# 720 chunks (was 600)
# 280 queries (was 250)
# 93% pass rate (improved!)
```

### Step 4: Create Incremental Backup

```bash
# Backup with changelog
python scripts/backup_golden_dataset.py backup

# Commit
git add data/golden_dataset_backup.json
git commit -m "feat: expand golden dataset with Home & Garden products

- Added 30 new product documents
- Added 120 new chunks
- Added 30 new test queries
- Pass rate improved: 92% → 93%
- Total: 180 documents, 720 chunks, 280 queries"
```

---

## Workflow 3: Model Migration

### Scenario: Upgrade Embedding Model

**From:** `text-embedding-ada-002` (1536 dims)
**To:** `text-embedding-3-small` (1536 dims, better quality)

### Step 1: Backup Current State

```bash
# Create pre-migration backup
python scripts/backup_golden_dataset.py backup

# Tag the backup
git add data/golden_dataset_backup.json
git commit -m "chore: backup before embedding model migration"
git tag v1.0-ada-002
git push --tags
```

### Step 2: Regenerate Embeddings

```bash
# Update embedding model in config
export EMBEDDING_MODEL=text-embedding-3-small

# Regenerate all embeddings
python scripts/regenerate_embeddings.py \
  --model text-embedding-3-small \
  --batch-size 100

# Output:
# ⏱️  Regenerating embeddings for 720 chunks...
#    Processed 100/720 chunks (13.9%)
#    Processed 200/720 chunks (27.8%)
#    ...
# ✅ Regeneration complete: 5.2 minutes
# 💰 Cost: $0.52 (720 chunks × ~500 tokens × $0.00002/1k)
```

### Step 3: Compare Quality

```bash
# Run tests with new embeddings
pytest tests/smoke/retrieval/test_retrieval_quality.py -v

# Compare results
python scripts/compare_pass_rates.py \
  --baseline reports/ada-002-results.json \
  --current reports/3-small-results.json

# Output:
# Model Comparison: ada-002 → 3-small
# =====================================
# Pass rate:  92.0% → 94.3% (+2.3%)
# Avg score:  0.72 → 0.76 (+0.04)
# Median score: 0.75 → 0.80 (+0.05)
#
# Improved queries: 18
# Degraded queries: 3
# Net improvement: +15 queries
```

### Step 4: Commit New Baseline

```bash
# Backup with new embeddings
python scripts/backup_golden_dataset.py backup

git add data/golden_dataset_backup.json
git commit -m "feat: migrate to text-embedding-3-small

- Regenerated all 720 chunk embeddings
- Pass rate improved: 92.0% → 94.3%
- Avg score improved: 0.72 → 0.76
- Model: text-embedding-3-small (1536 dims)"
git tag v1.1-3-small
git push --tags
```

---

## Workflow 4: CI/CD Integration

### GitHub Actions: Automated Backup

```yaml
# .github/workflows/backup-golden-dataset.yml
name: Backup Golden Dataset

on:
  schedule:
    - cron: '0 2 * * 0'  # Weekly on Sunday at 2am
  workflow_dispatch:  # Manual trigger

jobs:
  backup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt

      - name: Setup PostgreSQL
        run: |
          docker run -d \
            --name postgres \
            -e POSTGRES_PASSWORD=postgres \
            -p 5432:5432 \
            pgvector/pgvector:pg16

      - name: Restore and re-backup
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/postgres
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          cd backend
          python scripts/backup_golden_dataset.py restore
          python scripts/backup_golden_dataset.py backup
          python scripts/backup_golden_dataset.py verify

      - name: Commit if changed
        run: |
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          git add data/golden_dataset_backup.json
          git diff-index --quiet HEAD || \
            git commit -m "chore: automated golden dataset backup [skip ci]"
          git push
```

---

## Best Practices Learned

### 1. Version Control Everything
- Commit backups to git (JSON format)
- Tag major versions (`v1.0-ada-002`, `v2.0-3-small`)
- Include changelog in commit messages

### 2. Maintain High Pass Rate
- Target: 90-95% pass rate
- Investigate failures immediately
- Update queries or documents as needed

### 3. Balance Coverage
- Equal representation across categories
- Mix of difficulty levels
- Real user queries, not synthetic

### 4. Automate Validation
- CI/CD runs tests on every PR
- Alert if pass rate drops >2%
- Auto-backup weekly

### 5. Document Everything
- Why queries fail
- Model migration results
- Dataset expansion rationale

---

**Key Takeaway:** Golden datasets are living artifacts. Treat them like production code: version control, test coverage, CI/CD, and continuous improvement.
