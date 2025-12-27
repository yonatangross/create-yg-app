# Context Window Initialization Protocol

**Version:** 1.0
**Purpose:** Ensure Claude understands project state at the start of every conversation

---

## MANDATORY: Execute This Protocol on Every New Context Window

**EVERY TIME a new conversation/context window starts, YOU MUST follow these steps:**

---

## Step 1: Understand Current Project State (REQUIRED)

Read these files **in order** to understand where the project is at:

| Priority | File | What You'll Learn |
|----------|------|-------------------|
| 1 | `docs/CURRENT_STATUS.md` | Sprint progress, completed issues, blockers |
| 2 | `docs/ARCHITECTURE.md` | System design, tech stack, patterns |
| 3 | `.claude/context/` | Decisions and context from previous sessions |

**Command to read:**
```
Read docs/CURRENT_STATUS.md, docs/ARCHITECTURE.md
```

---

## Step 2: Check Recent Changes (REQUIRED)

Run these git commands to understand recent activity:

```bash
git log --oneline -10  # Recent commits
git status             # Uncommitted changes
git branch             # Current branch
```

---

## Step 3: Review Domain-Specific Docs (IF WORKING ON TASKS)

Based on the domain of work, read the relevant documentation:

| Domain | Files to Read |
|--------|---------------|
| Backend development | `.claude/skills/api-design-framework/`, `.claude/skills/database-schema-designer/` |
| Frontend development | `.claude/skills/performance-optimization/` |
| AI/ML work | `.claude/skills/langgraph-workflows/`, `.claude/skills/langfuse-observability/` |
| Quality/Testing | `.claude/skills/testing-strategy-builder/`, `.claude/skills/code-review-playbook/` |

---

## Quick Reference - Key Documentation Files

| Doc | Purpose | Read When |
|-----|---------|-----------|
| `docs/CURRENT_STATUS.md` | Sprint status, blockers | **Always first** |
| `docs/ARCHITECTURE.md` | System diagrams, patterns | Architecture questions |
| `CLAUDE.md` | Project overview, rules | Quick orientation |
| `.claude/agent-registry.json` | Agent capabilities | Agent selection |
| `.claude/instructions/*.md` | Behavior rules | Before coding |

---

## Why This Protocol Matters

Without reading these docs, you will lack context about:

1. **What has already been completed** - Avoid duplicate work
2. **Current priorities** - Know what's most important
3. **Existing patterns** - Follow established conventions
4. **Known issues** - Don't repeat past mistakes
5. **Architecture decisions** - Understand system design

---

## Context Persistence

After completing significant work, **always update** `docs/CURRENT_STATUS.md` with:
- What was completed
- Key decisions made
- Issues discovered
- Next steps

This ensures the next context window has access to your learnings.

---

## Checklist for New Context Window

- [ ] Read `docs/CURRENT_STATUS.md`
- [ ] Read `docs/ARCHITECTURE.md`
- [ ] Check `git log --oneline -10` and `git status`
- [ ] Read domain-specific docs based on task
- [ ] Understand current priorities
- [ ] Ready to work with full context

---

**Last Updated:** December 2025
