# Golden Dataset Backup/Restore Checklist

**Use this checklist to ensure safe, reliable backup and restoration of golden datasets**

---

## Pre-Backup Checklist

### Environment Verification

- [ ] **Database connection verified**
  ```bash
  psql -h localhost -p 5432 -U postgres -c "SELECT version();"
  # Expected: PostgreSQL 14+ with pgvector
  ```

- [ ] **Database contains expected data**
  ```bash
  psql -h localhost -p 5432 -U postgres -d myapp -c \
    "SELECT COUNT(*) FROM analyses WHERE status = 'completed';"
  # Expected: Your current dataset size
  ```

- [ ] **Embeddings generated for all chunks**
  ```bash
  psql -h localhost -p 5432 -U postgres -d myapp -c \
    "SELECT COUNT(*) FROM analysis_chunks WHERE embedding IS NULL;"
  # Expected: 0 (no chunks without embeddings)
  ```

### Data Quality Validation

- [ ] **URL contract verified (no placeholder URLs)**
  ```bash
  psql -h localhost -p 5432 -U postgres -d myapp -c \
    "SELECT COUNT(*) FROM analyses WHERE url LIKE '%placeholder%' OR url LIKE '%example.com%';"
  # Expected: 0 (no placeholder URLs)
  ```

- [ ] **All analyses have artifacts**
  ```bash
  psql -h localhost -p 5432 -U postgres -d myapp -c \
    "SELECT COUNT(*) FROM analyses a
     LEFT JOIN artifacts ar ON a.id = ar.analysis_id
     WHERE ar.id IS NULL AND a.status = 'completed';"
  # Expected: 0 (all completed analyses have artifacts)
  ```

- [ ] **No orphaned chunks**
  ```bash
  psql -h localhost -p 5432 -U postgres -d myapp -c \
    "SELECT COUNT(*) FROM analysis_chunks c
     LEFT JOIN analyses a ON c.analysis_id = a.id
     WHERE a.id IS NULL;"
  # Expected: 0 (all chunks belong to an analysis)
  ```

### Script Availability

- [ ] **Backup script exists**
  ```bash
  ls -lh backend/scripts/backup_golden_dataset.py
  # Expected: File exists
  ```

- [ ] **Dependencies installed**
  ```bash
  cd backend
  pip install -r requirements.txt
  # OR: uv sync
  # Expected: All dependencies installed
  ```

- [ ] **Data directory exists**
  ```bash
  mkdir -p backend/data
  ls -ld backend/data
  # Expected: Directory exists and is writable
  ```

---

## Backup Execution Checklist

### Run Backup

- [ ] **Execute backup command**
  ```bash
  cd backend
  python scripts/backup_golden_dataset.py backup
  # OR: uv run python scripts/backup_golden_dataset.py backup
  ```

- [ ] **Verify backup output shows success**
  - [ ] "BACKUP COMPLETE" message displayed
  - [ ] Analyses count matches expected
  - [ ] Artifacts count matches expected
  - [ ] Chunks count matches expected

- [ ] **Check backup file created**
  ```bash
  ls -lh backend/data/golden_dataset_backup.json
  # Expected: JSON file with reasonable size (1-10 MB typical)
  ```

- [ ] **Check metadata file created**
  ```bash
  ls -lh backend/data/golden_dataset_metadata.json
  # Expected: ~1 KB file
  ```

### Verify Backup

- [ ] **Run verification command**
  ```bash
  python scripts/backup_golden_dataset.py verify
  ```

- [ ] **Verify output shows valid backup**
  - [ ] "BACKUP IS VALID" message displayed
  - [ ] Analyses count correct
  - [ ] Artifacts count correct
  - [ ] Chunks count correct
  - [ ] Referential integrity: OK
  - [ ] All analyses have artifacts: OK
  - [ ] No placeholder URLs warning

- [ ] **Verify backup file is valid JSON**
  ```bash
  cat backend/data/golden_dataset_backup.json | jq '.'
  # Expected: Valid JSON, no parse errors
  ```

- [ ] **Check backup version**
  ```bash
  cat backend/data/golden_dataset_backup.json | jq '.version'
  # Expected: "2.0" or your current version
  ```

### Commit Backup

- [ ] **Stage backup files**
  ```bash
  git add backend/data/golden_dataset_backup.json
  git add backend/data/golden_dataset_metadata.json
  ```

- [ ] **Write descriptive commit message**
  ```bash
  git commit -m "chore: golden dataset backup (N analyses, M chunks)

  - Backup version: 2.0
  - Pass rate: X% (Y/Z queries)
  - Changes: [describe any additions/removals]"
  ```

- [ ] **Push to remote**
  ```bash
  git push origin main
  ```

---

## Pre-Restore Checklist

### Backup Verification

- [ ] **Backup file exists**
  ```bash
  ls -lh backend/data/golden_dataset_backup.json
  # Expected: File exists
  ```

- [ ] **Backup integrity verified**
  ```bash
  cd backend
  python scripts/backup_golden_dataset.py verify
  # Expected: "BACKUP IS VALID"
  ```

- [ ] **Backup version compatible**
  ```bash
  cat backend/data/golden_dataset_backup.json | jq '.version'
  # Expected: Compatible version (script should handle 1.0 and 2.0)
  ```

### Database State Assessment

- [ ] **Database accessible**
  ```bash
  psql -h localhost -p 5432 -U postgres -c "SELECT 1;"
  # Expected: "1"
  ```

- [ ] **Current data count known**
  ```bash
  psql -h localhost -p 5432 -U postgres -d myapp -c "SELECT COUNT(*) FROM analyses;"
  # Note the count for comparison after restore
  ```

- [ ] **Decision made: Add or Replace?**
  - [ ] **ADD mode:** Keep existing data, add from backup (use `restore`)
  - [ ] **REPLACE mode:** Delete existing data, restore from backup (use `restore --replace`)

  **WARNING:** REPLACE mode is DESTRUCTIVE. Use only if:
  - [ ] Setting up fresh environment
  - [ ] Recovering from data corruption
  - [ ] You have confirmed backup is valid

### Environment Setup

- [ ] **PostgreSQL running**
  ```bash
  docker compose ps postgres
  # OR: pg_isready -h localhost -p 5432
  # Expected: Database is ready
  ```

- [ ] **Database migrations applied**
  ```bash
  cd backend
  alembic current
  # Expected: Shows latest migration revision
  ```

- [ ] **OpenAI API key set** (for embedding regeneration)
  ```bash
  echo $OPENAI_API_KEY
  # Expected: sk-... (valid API key)

  # OR check .env file
  grep OPENAI_API_KEY backend/.env
  # Expected: OPENAI_API_KEY=sk-...
  ```

- [ ] **Sufficient disk space**
  ```bash
  df -h backend/data
  # Expected: At least 1 GB free
  ```

---

## Restore Execution Checklist

### Run Restore

**Option A: Add to existing data (non-destructive)**

- [ ] **Execute restore command**
  ```bash
  cd backend
  python scripts/backup_golden_dataset.py restore
  ```

**Option B: Replace existing data (DESTRUCTIVE)**

- [ ] **CONFIRM backup is valid** (run verify again)
  ```bash
  python scripts/backup_golden_dataset.py verify
  # Expected: "BACKUP IS VALID"
  ```

- [ ] **CONFIRM you want to delete existing data** (no turning back)
  - [ ] Yes, I understand this is destructive
  - [ ] Yes, I have verified the backup
  - [ ] Yes, I am ready to proceed

- [ ] **Execute restore with --replace flag**
  ```bash
  python scripts/backup_golden_dataset.py restore --replace
  ```

### Monitor Restore Progress

- [ ] **Watch for restore stages**
  - [ ] "Loaded backup from: ..." (backup file loaded)
  - [ ] "Backup version: 2.0" (schema version)
  - [ ] "Restoring N analyses..." (analyses being inserted)
  - [ ] "Restoring N artifacts..." (artifacts being inserted)
  - [ ] "Restoring M chunks (regenerating embeddings)..." (chunks + embeddings)
  - [ ] Progress updates showing chunk restoration

- [ ] **Check for errors during embedding generation**
  - [ ] No "Failed to generate embedding" warnings
  - [ ] No OpenAI API errors
  - [ ] All chunks processed successfully

- [ ] **Verify restore completion message**
  - [ ] "RESTORE COMPLETE" displayed
  - [ ] Counts match backup metadata

### Post-Restore Verification

- [ ] **Check database counts**
  ```bash
  # Analyses
  psql -h localhost -p 5432 -U postgres -d myapp -c \
    "SELECT COUNT(*) FROM analyses WHERE status = 'completed';"
  # Expected: Matches backup metadata

  # Artifacts
  psql -h localhost -p 5432 -U postgres -d myapp -c "SELECT COUNT(*) FROM artifacts;"
  # Expected: Matches backup metadata

  # Chunks
  psql -h localhost -p 5432 -U postgres -d myapp -c "SELECT COUNT(*) FROM analysis_chunks;"
  # Expected: Matches backup metadata
  ```

- [ ] **Verify embeddings generated**
  ```bash
  psql -h localhost -p 5432 -U postgres -d myapp -c \
    "SELECT COUNT(*) FROM analysis_chunks WHERE embedding IS NULL;"
  # Expected: 0 (all chunks have embeddings)
  ```

- [ ] **Verify URL contract maintained**
  ```bash
  psql -h localhost -p 5432 -U postgres -d myapp -c \
    "SELECT COUNT(*) FROM analyses WHERE url LIKE '%placeholder%';"
  # Expected: 0 (no placeholder URLs)
  ```

---

## Validation Testing Checklist

### Retrieval Quality Tests

- [ ] **Run smoke tests**
  ```bash
  cd backend
  pytest tests/smoke/retrieval/test_retrieval_quality.py -v
  ```

- [ ] **Check pass rate**
  - [ ] Total queries tested
  - [ ] Expected pass rate (your baseline, e.g., 90%)
  - [ ] Actual pass rate from test output
  - [ ] Pass rate within acceptable range (±2%)

- [ ] **No critical regressions**
  - [ ] If pass rate dropped >5%, investigate:
    - [ ] Embedding model matches (check model version)
    - [ ] Hybrid search config unchanged
    - [ ] Backup file not corrupted

---

## Quick Reference

### Full Backup Workflow
```bash
cd backend
python scripts/backup_golden_dataset.py backup
python scripts/backup_golden_dataset.py verify
git add data/golden_dataset_backup.json data/golden_dataset_metadata.json
git commit -m "chore: golden dataset backup"
git push
```

### Full Restore Workflow (New Environment)
```bash
cd backend
docker compose up -d postgres
sleep 5
alembic upgrade head
python scripts/backup_golden_dataset.py verify
python scripts/backup_golden_dataset.py restore
pytest tests/smoke/retrieval/test_retrieval_quality.py -v
```

### Full Restore Workflow (Replace Existing)
```bash
cd backend
python scripts/backup_golden_dataset.py verify
# CONFIRM: I understand this is destructive
python scripts/backup_golden_dataset.py restore --replace
pytest tests/smoke/retrieval/test_retrieval_quality.py -v
```

---

**Remember:** Golden datasets are critical infrastructure. Always verify backups, test restores in staging, and document all changes.
