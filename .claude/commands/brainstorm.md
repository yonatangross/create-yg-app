---
description: Multi-perspective idea exploration with parallel agents and Socratic method
---

# Brainstorm: $ARGUMENTS

Deep exploration using 10-12 parallel agents for diverse perspectives.

## Phase 1: Initial Exploration (Sequential-Thinking MCP)

### 1a. Define the Problem Space

Use sequential-thinking for structured decomposition:

```python
mcp__sequential-thinking__sequentialthinking(
  thought="Exploring the problem space for: $ARGUMENTS",
  thoughtNumber=1,
  totalThoughts=7,
  nextThoughtNeeded=true
)
```

Key questions to answer:
- What problem are we solving?
- Who are the users?
- What constraints exist?
- What's already been tried?

### 1b. Load Brainstorming Skill

```python
Read(".claude/skills/brainstorming/capabilities.json")
Read(".claude/skills/brainstorming/SKILL.md")  # Full Socratic method
```

## Phase 2: Research & Context

### 2a. Web Search for Industry Solutions

```python
# PARALLEL - All searches in one message!
WebSearch("$ARGUMENTS best practices December 2025")
WebSearch("$ARGUMENTS industry solutions 2025")
WebSearch("$ARGUMENTS common pitfalls 2025")
WebSearch("$ARGUMENTS innovative approaches 2025")
WebSearch("$ARGUMENTS case studies 2025")
```

### 2b. Memory MCP - Previous Brainstorms

```python
mcp__memory__search_nodes(query="brainstorm")
mcp__memory__search_nodes(query="design decisions")
mcp__memory__search_nodes(query="$ARGUMENTS")
```

### 2c. Context7 for Technical Possibilities

```python
# Look up relevant technologies
mcp__context7__get-library-docs(context7CompatibleLibraryID="/facebook/react", topic="patterns")
mcp__context7__get-library-docs(context7CompatibleLibraryID="/tiangolo/fastapi", topic="advanced")
```

## Phase 3: Multi-Perspective Analysis (10 Parallel Agents)

Launch TEN agents for diverse perspectives - ALL in ONE message:

```python
# PARALLEL - All ten in ONE message!

Task(
  subagent_type="product-manager",
  prompt="""BUSINESS PERSPECTIVE

  Topic: $ARGUMENTS

  Analyze from product perspective:
  1. Market need - does this solve a real problem?
  2. User value proposition
  3. Competitive landscape
  4. Success metrics (KPIs)
  5. Go-to-market considerations

  Use frameworks:
  - Jobs-to-be-Done
  - Value proposition canvas
  - RICE prioritization

  Output: Business case analysis with recommendations.""",
  run_in_background=true
)

Task(
  subagent_type="product-manager",
  prompt="""REQUIREMENTS ANALYSIS

  Topic: $ARGUMENTS

  Define requirements:
  1. Functional requirements (must-have)
  2. Non-functional requirements (performance, security)
  3. User stories with acceptance criteria
  4. Edge cases and error scenarios
  5. Dependencies and constraints

  Format as structured user stories:
  "As a [user], I want [feature] so that [benefit]"

  Output: Requirements document.""",
  run_in_background=true
)

Task(
  subagent_type="ux-researcher",
  prompt="""USER EXPERIENCE PERSPECTIVE

  Topic: $ARGUMENTS

  Analyze user needs:
  1. User personas (who will use this?)
  2. User journey mapping
  3. Pain points addressed
  4. Delight opportunities
  5. Accessibility considerations

  Research methods to suggest:
  - User interviews
  - Usability testing
  - A/B testing opportunities

  Output: UX research plan and personas.""",
  run_in_background=true
)

Task(
  subagent_type="ux-researcher",
  prompt="""USABILITY ANALYSIS

  Topic: $ARGUMENTS

  Evaluate usability:
  1. Cognitive load assessment
  2. Information architecture
  3. Navigation patterns
  4. Error prevention
  5. Help and documentation needs

  Apply heuristics:
  - Nielsen's 10 heuristics
  - WCAG 2.1 guidelines

  Output: Usability recommendations.""",
  run_in_background=true
)

Task(
  subagent_type="backend-system-architect",
  prompt="""TECHNICAL ARCHITECTURE PERSPECTIVE

  Topic: $ARGUMENTS

  Analyze technical feasibility:
  1. Architecture options (monolith vs microservice vs serverless)
  2. Technology stack considerations
  3. Scalability requirements
  4. Performance implications
  5. Integration challenges

  Consider trade-offs:
  - Build vs buy
  - Complexity vs flexibility
  - Speed vs robustness

  Output: Technical options with pros/cons.""",
  run_in_background=true
)

Task(
  subagent_type="backend-system-architect",
  prompt="""DATA & SECURITY PERSPECTIVE

  Topic: $ARGUMENTS

  Analyze data needs:
  1. Data model requirements
  2. Storage options (SQL, NoSQL, hybrid)
  3. Data privacy (GDPR, CCPA)
  4. Security requirements (auth, encryption)
  5. Compliance considerations

  Output: Data strategy recommendations.""",
  run_in_background=true
)

Task(
  subagent_type="frontend-ui-developer",
  prompt="""FRONTEND IMPLEMENTATION PERSPECTIVE

  Topic: $ARGUMENTS

  Analyze frontend approach:
  1. Component architecture options
  2. State management strategy
  3. Rendering approach (SSR, CSR, hybrid)
  4. Performance optimization
  5. Testing strategy

  React 19 considerations:
  - Server Components applicability
  - Streaming opportunities
  - Suspense boundaries

  Output: Frontend implementation options.""",
  run_in_background=true
)

Task(
  subagent_type="ai-ml-engineer",
  prompt="""AI/ML OPPORTUNITIES

  Topic: $ARGUMENTS

  Evaluate AI integration:
  1. Where can AI add value?
  2. LLM use cases (generation, analysis, search)
  3. Embedding/RAG opportunities
  4. Automation possibilities
  5. Cost-benefit analysis

  Consider:
  - Build vs API
  - Latency requirements
  - Accuracy needs
  - Cost projections

  Output: AI opportunity assessment.""",
  run_in_background=true
)

Task(
  subagent_type="sprint-prioritizer",
  prompt="""IMPLEMENTATION PLANNING

  Topic: $ARGUMENTS

  Plan implementation:
  1. MVP scope (minimum viable)
  2. Phase breakdown (iterations)
  3. Risk assessment
  4. Resource requirements
  5. Timeline estimation

  Use frameworks:
  - MoSCoW prioritization
  - Story point estimation
  - Risk matrix

  Output: Implementation roadmap.""",
  run_in_background=true
)

Task(
  subagent_type="whimsy-injector",
  prompt="""CREATIVE & DELIGHTFUL IDEAS

  Topic: $ARGUMENTS

  Think creatively:
  1. What would make this delightful?
  2. Unexpected features users would love
  3. Gamification opportunities
  4. Easter eggs or personality
  5. Viral/shareable moments

  Push boundaries:
  - What if we had no constraints?
  - What would Apple/Google do?
  - What's the 10x version?

  Output: Creative enhancement ideas.""",
  run_in_background=true
)
```

**Wait for all 10 to complete.**

## Phase 4: Synthesis & Socratic Dialogue (2 Agents)

After collecting all perspectives, synthesize:

```python
# PARALLEL - Both in ONE message!

Task(
  subagent_type="studio-coach",
  prompt="""SYNTHESIS: INTEGRATE ALL PERSPECTIVES

  Input: [Results from all 10 agents above]

  Create unified analysis:
  1. Common themes across perspectives
  2. Conflicting viewpoints and resolution
  3. Critical decisions needed
  4. Recommended approach
  5. Open questions for user

  Format: Executive summary with decision points.""",
  run_in_background=true
)

Task(
  subagent_type="Plan",
  prompt="""SOCRATIC QUESTIONS

  Based on all perspectives, generate:
  1. Clarifying questions (what's unclear?)
  2. Challenging questions (what assumptions?)
  3. Trade-off questions (what sacrifices?)
  4. Future questions (what might change?)
  5. Validation questions (how to test?)

  Goal: Surface decisions the user needs to make.""",
  run_in_background=true
)
```

## Phase 5: Interactive Refinement

Present findings to user with structured options:

```python
AskUserQuestion(questions=[
  {
    "header": "Approach",
    "question": "Which implementation approach resonates most?",
    "options": [
      {"label": "MVP First", "description": "Ship minimal version quickly, iterate"},
      {"label": "Full Build", "description": "Complete implementation upfront"},
      {"label": "Spike First", "description": "Technical proof-of-concept first"}
    ],
    "multiSelect": false
  },
  {
    "header": "Priorities",
    "question": "What matters most for this feature?",
    "options": [
      {"label": "Speed", "description": "Ship fast, iterate later"},
      {"label": "Quality", "description": "Get it right the first time"},
      {"label": "Scalability", "description": "Build for growth"},
      {"label": "Simplicity", "description": "Minimize complexity"}
    ],
    "multiSelect": true
  }
])
```

## Phase 6: Save Brainstorm to Memory

```python
mcp__memory__create_entities(entities=[{
  "name": "brainstorm-$ARGUMENTS-[date]",
  "entityType": "brainstorm-session",
  "observations": [
    "Topic: $ARGUMENTS",
    "Key decision: ...",
    "Chosen approach: ...",
    "Open questions: ...",
    "Next steps: ..."
  ]
}])
```

---

## Summary

**Total Parallel Agents: 12**
- Phase 3: 10 multi-perspective agents
- Phase 4: 2 synthesis agents

**Perspectives Covered:**
- 📊 Business (2 product-managers)
- 👤 User Experience (2 ux-researchers)
- 🏗️ Architecture (2 backend-system-architects)
- ⚛️ Frontend (1 frontend-ui-developer)
- 🤖 AI/ML (1 ai-ml-engineer)
- 📅 Planning (1 sprint-prioritizer)
- ✨ Creativity (1 whimsy-injector)

**MCPs Used:**
- 🧠 sequential-thinking (structured decomposition)
- 📚 context7 (technical possibilities)
- 💾 memory (previous decisions)
- 🔍 WebSearch (industry research)

**Skills Used:**
- brainstorming (Socratic method)

**Output:**
- Multi-perspective analysis
- Synthesized recommendations
- Socratic questions
- Interactive decision points
- Saved to memory for future reference
