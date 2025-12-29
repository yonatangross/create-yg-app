#!/bin/bash
# ============================================================
# GitHub CLI Helper Functions
# Source this file: source .claude/skills/github-cli/scripts/gh-helpers.sh
# ============================================================

# Configuration - Update these for your project
export GH_REPO="${GH_REPO:-owner/repo}"  # Set via environment or update here
export GH_PROJECT_NUMBER="${GH_PROJECT_NUMBER:-1}"
export GH_PROJECT_OWNER="${GH_PROJECT_OWNER:-$(gh api user --jq '.login' 2>/dev/null || echo 'owner')}"
export GH_PROJECT_ID="${GH_PROJECT_ID:-}"  # Get from: gh project list --owner $GH_PROJECT_OWNER --format json
export GH_STATUS_FIELD_ID="${GH_STATUS_FIELD_ID:-}"  # Get from project field query

# Status Option IDs (update for your project's status field options)
export GH_STATUS_READY="${GH_STATUS_READY:-}"
export GH_STATUS_IN_DEV="${GH_STATUS_IN_DEV:-}"
export GH_STATUS_CODE_COMPLETE="${GH_STATUS_CODE_COMPLETE:-}"
export GH_STATUS_REVIEW_READY="${GH_STATUS_REVIEW_READY:-}"
export GH_STATUS_APPROVED="${GH_STATUS_APPROVED:-}"
export GH_STATUS_DEPLOYED="${GH_STATUS_DEPLOYED:-}"

# ============================================================
# ISSUE FUNCTIONS
# ============================================================

# Create issue and return number
ghx_issue_create() {
    local title="$1"
    local body="${2:-No description provided.}"
    local labels="${3:-enhancement}"
    local milestone="${4:-}"

    local cmd="gh issue create --repo $GH_REPO --title \"$title\" --body \"$body\" --label \"$labels\""
    [[ -n "$milestone" ]] && cmd="$cmd --milestone \"$milestone\""
    cmd="$cmd --json number --jq '.number'"

    eval "$cmd"
}

# Get issue URL
ghx_issue_url() {
    local issue_num="$1"
    echo "https://github.com/$GH_REPO/issues/$issue_num"
}

# List open issues by label
ghx_issues_by_label() {
    local label="$1"
    gh issue list --repo "$GH_REPO" --label "$label" --state open \
        --json number,title --jq '.[] | "#\(.number): \(.title)"'
}

# ============================================================
# PROJECT FUNCTIONS
# ============================================================

# Add issue to project board
ghx_project_add() {
    local issue_url="$1"
    gh project item-add "$GH_PROJECT_NUMBER" \
        --owner "$GH_PROJECT_OWNER" \
        --url "$issue_url" \
        --format json | jq -r '.id'
}

# Set project item status
ghx_project_set_status() {
    local item_id="$1"
    local status_option_id="$2"

    gh api graphql -f query='
        mutation($pid:ID!,$iid:ID!,$fid:ID!,$oid:String!) {
            updateProjectV2ItemFieldValue(input:{
                projectId:$pid,
                itemId:$iid,
                fieldId:$fid,
                value:{singleSelectOptionId:$oid}
            }) {
                projectV2Item { id }
            }
        }
    ' \
        -f pid="$GH_PROJECT_ID" \
        -f iid="$item_id" \
        -f fid="$GH_STATUS_FIELD_ID" \
        -f oid="$status_option_id"
}

# ============================================================
# BRANCH FUNCTIONS
# ============================================================

# Create feature branch from issue
ghx_feature_branch() {
    local issue_num="$1"

    # Get issue title
    local title=$(gh issue view "$issue_num" --repo "$GH_REPO" \
        --json title --jq '.title' | \
        tr '[:upper:]' '[:lower:]' | \
        sed 's/[^a-z0-9]/-/g' | \
        sed 's/--*/-/g' | \
        cut -c1-40)

    local branch="issue/${issue_num}-${title}"

    # Switch to dev and create branch
    git checkout dev && git pull origin dev
    git checkout -b "$branch"

    echo "$branch"
}

# ============================================================
# PR FUNCTIONS
# ============================================================

# Create PR with standard format
ghx_pr_create() {
    local title="$1"
    local body="$2"
    local base="${3:-dev}"

    gh pr create \
        --repo "$GH_REPO" \
        --title "$title" \
        --body "$body

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>" \
        --base "$base"
}

# Check if PR is ready to merge
ghx_pr_ready() {
    local pr_num="$1"

    local data=$(gh pr view "$pr_num" --repo "$GH_REPO" \
        --json reviewDecision,statusCheckRollupState,mergeable)

    local review=$(echo "$data" | jq -r '.reviewDecision')
    local checks=$(echo "$data" | jq -r '.statusCheckRollupState')
    local mergeable=$(echo "$data" | jq -r '.mergeable')

    echo "Review: $review"
    echo "Checks: $checks"
    echo "Mergeable: $mergeable"

    if [[ "$review" == "APPROVED" && "$checks" == "SUCCESS" && "$mergeable" == "MERGEABLE" ]]; then
        echo "✅ PR is ready to merge"
        return 0
    else
        echo "❌ PR is NOT ready to merge"
        return 1
    fi
}

# ============================================================
# RATE LIMIT FUNCTIONS
# ============================================================

# Check rate limit
ghx_rate_limit() {
    gh api rate_limit --jq '.resources.core | {
        remaining: .remaining,
        limit: .limit,
        reset: (.reset | strftime("%H:%M:%S"))
    }'
}

# Wait if rate limited
ghx_rate_limit_wait() {
    local min_remaining="${1:-50}"

    local remaining=$(gh api rate_limit --jq '.resources.core.remaining')

    if [[ "$remaining" -lt "$min_remaining" ]]; then
        local reset=$(gh api rate_limit --jq '.resources.core.reset')
        local wait=$((reset - $(date +%s) + 60))
        echo "Rate limit low ($remaining remaining). Waiting ${wait}s..."
        sleep "$wait"
    fi
}

# ============================================================
# COMPLETE WORKFLOWS
# ============================================================

# Create issue, branch, and add to project
ghx_start_feature() {
    local title="$1"
    local body="${2:-}"
    local labels="${3:-enhancement,backend}"

    echo "=== Creating Issue ==="
    local issue_num=$(ghx_issue_create "$title" "$body" "$labels")
    local issue_url=$(ghx_issue_url "$issue_num")
    echo "Created: #$issue_num - $issue_url"

    echo "=== Creating Branch ==="
    local branch=$(ghx_feature_branch "$issue_num")
    echo "Branch: $branch"

    echo "=== Adding to Project ==="
    local item_id=$(ghx_project_add "$issue_url" 2>/dev/null || echo "")
    if [[ -n "$item_id" ]]; then
        ghx_project_set_status "$item_id" "$GH_STATUS_IN_DEV" >/dev/null
        echo "Added to project: $item_id"
    fi

    echo ""
    echo "=== Ready to Work ==="
    echo "Issue:  #$issue_num"
    echo "Branch: $branch"
    echo "URL:    $issue_url"
}

# Finish feature (create PR)
ghx_finish_feature() {
    local branch=$(git branch --show-current)
    local issue_num=$(echo "$branch" | grep -o '[0-9]*' | head -1)

    if [[ -z "$issue_num" ]]; then
        echo "ERROR: Cannot extract issue number from branch: $branch"
        return 1
    fi

    # Get issue title
    local issue_title=$(gh issue view "$issue_num" --repo "$GH_REPO" \
        --json title --jq '.title')

    echo "=== Pushing Branch ==="
    git push -u origin "$branch"

    echo "=== Creating PR ==="
    ghx_pr_create \
        "feat(#${issue_num}): ${issue_title}" \
        "## Summary
Implements #${issue_num}

## Changes
- TODO: List changes

## Test Plan
- [ ] Unit tests pass
- [ ] Integration tests pass

Closes #${issue_num}"

    echo "=== Done ==="
}

# ============================================================
# HELP
# ============================================================

ghx_help() {
    cat << 'EOF'
GitHub CLI Extended Helpers (ghx_*)

ISSUE FUNCTIONS:
  ghx_issue_create "title" ["body"] ["labels"]  - Create issue
  ghx_issue_url <number>                        - Get issue URL
  ghx_issues_by_label <label>                   - List issues by label

PROJECT FUNCTIONS:
  ghx_project_add <issue_url>                   - Add to project board
  ghx_project_set_status <item_id> <status_id>  - Set status field

BRANCH FUNCTIONS:
  ghx_feature_branch <issue_num>                - Create feature branch

PR FUNCTIONS:
  ghx_pr_create "title" "body" [base]           - Create PR
  ghx_pr_ready <pr_num>                         - Check if ready to merge

RATE LIMIT:
  ghx_rate_limit                                - Check rate limit
  ghx_rate_limit_wait [min_remaining]           - Wait if rate limited

WORKFLOWS:
  ghx_start_feature "title" ["body"] ["labels"] - Full feature setup
  ghx_finish_feature                            - Create PR from current branch

ENVIRONMENT (set before sourcing or via export):
  $GH_REPO              - owner/repo (required)
  $GH_PROJECT_NUMBER    - Project number (default: 1)
  $GH_PROJECT_OWNER     - Project owner (default: current user)
  $GH_STATUS_IN_DEV     - Status ID for in-development
  $GH_STATUS_APPROVED   - Status ID for approved

USAGE:
  export GH_REPO="owner/repo"
  source .claude/skills/github-cli/scripts/gh-helpers.sh
  ghx_start_feature "Add hybrid search" "Implement RRF fusion" "enhancement,backend"
EOF
}

echo "GitHub CLI helpers loaded. Run 'ghx_help' for usage."
