#!/bin/bash
# =============================================================================
# YG Starter - Project Initialization Script
# =============================================================================
# Usage: ./init.sh "My Project Name"
#
# This script:
# 1. Renames the project (yg-starter → your-project)
# 2. Generates cryptographic secrets
# 3. Creates .env from .env.example
# 4. Resets git history for a fresh start
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

log_info() { echo -e "${BLUE}ℹ${NC} $1"; }
log_success() { echo -e "${GREEN}✓${NC} $1"; }
log_warn() { echo -e "${YELLOW}⚠${NC} $1"; }
log_error() { echo -e "${RED}✗${NC} $1"; }

generate_secret() {
    openssl rand -base64 32 | tr -d '/+=' | cut -c1-24
}

generate_hex() {
    openssl rand -hex 32
}

slugify() {
    echo "$1" | tr '[:upper:]' '[:lower:]' | tr ' -' '_' | tr -cd 'a-z0-9_'
}

# -----------------------------------------------------------------------------
# Main Script
# -----------------------------------------------------------------------------

PROJECT_NAME="${1:-}"

if [ -z "$PROJECT_NAME" ]; then
    echo ""
    echo "Usage: ./init.sh \"My Project Name\""
    echo ""
    echo "Example: ./init.sh \"Customer Support Agent\""
    echo ""
    exit 1
fi

PROJECT_SLUG=$(slugify "$PROJECT_NAME")
PROJECT_TITLE=$(echo "$PROJECT_NAME" | sed 's/_/ /g' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) tolower(substr($i,2))}1')

echo ""
echo "╭──────────────────────────────────────────────────────────────────────────────╮"
echo "│                                                                              │"
echo "│   YG Starter - Project Initialization                                        │"
echo "│                                                                              │"
echo "╰──────────────────────────────────────────────────────────────────────────────╯"
echo ""
log_info "Project Name: $PROJECT_NAME"
log_info "Project Slug: $PROJECT_SLUG"
echo ""

# -----------------------------------------------------------------------------
# Step 1: Generate Secrets
# -----------------------------------------------------------------------------

log_info "Generating cryptographic secrets..."

POSTGRES_PASSWORD=$(generate_secret)
REDIS_PASSWORD=$(generate_secret)
JWT_SECRET=$(generate_secret)
JWT_REFRESH_SECRET=$(generate_secret)
LANGFUSE_PG_PASSWORD=$(generate_secret)
CLICKHOUSE_PASSWORD=$(generate_secret)
MINIO_PASSWORD=$(generate_secret)
NEXTAUTH_SECRET=$(generate_secret)
NEXTAUTH_SALT=$(generate_hex | cut -c1-32)
ENCRYPTION_KEY=$(generate_hex)
LANGFUSE_REDIS_PASSWORD=$(generate_secret)

log_success "Generated 11 unique secrets"

# -----------------------------------------------------------------------------
# Step 2: Create .env file
# -----------------------------------------------------------------------------

log_info "Creating .env file..."

cp .env.example .env

# Replace GENERATE_ME placeholders with actual secrets
sed -i '' "s/GENERATE_ME_POSTGRES/$POSTGRES_PASSWORD/g" .env
sed -i '' "s/GENERATE_ME_REDIS/$REDIS_PASSWORD/g" .env
sed -i '' "s/GENERATE_ME_JWT_REFRESH/$JWT_REFRESH_SECRET/g" .env
sed -i '' "s/GENERATE_ME_JWT/$JWT_SECRET/g" .env
sed -i '' "s/GENERATE_ME_LANGFUSE_PG/$LANGFUSE_PG_PASSWORD/g" .env
sed -i '' "s/GENERATE_ME_CLICKHOUSE/$CLICKHOUSE_PASSWORD/g" .env
sed -i '' "s/GENERATE_ME_MINIO/$MINIO_PASSWORD/g" .env
sed -i '' "s/GENERATE_ME_NEXTAUTH/$NEXTAUTH_SECRET/g" .env
sed -i '' "s/GENERATE_ME_SALT/$NEXTAUTH_SALT/g" .env
sed -i '' "s/GENERATE_ME_ENCRYPTION/$ENCRYPTION_KEY/g" .env
sed -i '' "s/GENERATE_ME_LANGFUSE_REDIS/$LANGFUSE_REDIS_PASSWORD/g" .env

# Replace project name in .env
sed -i '' "s/yg-starter/$PROJECT_SLUG/g" .env

log_success "Created .env with generated secrets"

# -----------------------------------------------------------------------------
# Step 3: Rename Project Throughout Codebase
# -----------------------------------------------------------------------------

log_info "Renaming project: yg-starter → $PROJECT_SLUG"

# Files to update (excluding .git, node_modules, .venv, etc.)
find . -type f \( \
    -name "*.yml" -o -name "*.yaml" -o -name "*.json" -o -name "*.toml" \
    -o -name "*.md" -o -name "*.py" -o -name "*.ts" -o -name "*.tsx" \
    -o -name "*.html" -o -name "*.css" -o -name "*.js" \
    -o -name "Makefile" -o -name "Dockerfile" -o -name "*.ini" \
    -o -name ".env.example" \
\) -not -path "./.git/*" -not -path "./node_modules/*" -not -path "./.venv/*" \
   -not -name "init.sh" \
   -exec sed -i '' "s/yg-starter/$PROJECT_SLUG/g" {} \; 2>/dev/null || true

# Replace display name (YG Starter → Project Title)
find . -type f \( -name "*.md" -o -name "*.json" -o -name "*.yml" \) \
    -not -path "./.git/*" \
    -exec sed -i '' "s/YG Starter/$PROJECT_TITLE/g" {} \; 2>/dev/null || true

log_success "Renamed project references"

# -----------------------------------------------------------------------------
# Step 4: Copy backend .env
# -----------------------------------------------------------------------------

log_info "Setting up backend environment..."

if [ -f "backend/.env.example" ]; then
    cp backend/.env.example backend/.env
    sed -i '' "s/yg-starter/$PROJECT_SLUG/g" backend/.env 2>/dev/null || true
    log_success "Created backend/.env"
fi

# -----------------------------------------------------------------------------
# Step 5: Reset Git History (Optional)
# -----------------------------------------------------------------------------

if [ -d ".git" ]; then
    log_info "Resetting git history for fresh start..."
    rm -rf .git
    git init
    git add .
    git commit -m "Initial commit: $PROJECT_NAME

🚀 Generated from yg-starter template
"
    log_success "Initialized fresh git repository"
fi

# -----------------------------------------------------------------------------
# Step 6: Self-Destruct (Remove init.sh)
# -----------------------------------------------------------------------------

log_info "Cleaning up..."
rm -f init.sh
log_success "Removed init.sh (no longer needed)"

# -----------------------------------------------------------------------------
# Done!
# -----------------------------------------------------------------------------

echo ""
echo "╭──────────────────────────────────────────────────────────────────────────────╮"
echo "│                                                                              │"
echo "│   ✅ Project initialized: $PROJECT_NAME"
echo "│                                                                              │"
echo "╰──────────────────────────────────────────────────────────────────────────────╯"
echo ""
echo "Next steps:"
echo ""
echo "  1. Add at least one LLM API key to .env:"
echo "     ${YELLOW}OPENAI_API_KEY=sk-...${NC}"
echo "     ${YELLOW}ANTHROPIC_API_KEY=sk-ant-...${NC}"
echo "     ${YELLOW}GOOGLE_API_KEY=...${NC}"
echo ""
echo "  2. Start the development environment:"
echo "     ${GREEN}docker compose up -d${NC}"
echo ""
echo "  3. Access your application:"
echo "     🚀 Chat UI:     http://localhost:5183"
echo "     📊 Langfuse:    http://localhost:3010"
echo "     📚 API Docs:    http://localhost:8600/docs"
echo ""
