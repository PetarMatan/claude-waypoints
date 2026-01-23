# Future Directions

This document outlines potential improvements to Claude Waypoints, informed by current gaps and frontier AI research. It serves as a discussion document for future development.

## Current Gaps

### 1. No Backtracking Between Phases

**Problem:** If Phase 4 (Implementation) reveals a fundamental design flaw, there's no formal mechanism to return to Phase 2 (Interfaces) or Phase 3 (Tests). Users must manually reset and lose progress.

**Impact:**
- Wasted implementation effort when design issues surface late
- Users may hack around the problem rather than properly redesigning
- Metrics don't capture "had to restart" scenarios

**Potential Solutions:**
- Add `wp:backtrack <phase>` command with state preservation
- Require justification for backtracking (captured in metrics)
- Preserve test files when backtracking from Phase 4 to Phase 2
- Add "design revision" as a tracked metric

---

### 2. Metrics Not Used for Learning

**Problem:** Metrics are collected (`~/.claude/waypoints/metrics/`) but not analyzed or used to improve future sessions. The data exists but provides no active value.

**Current State:** Local JSON files, planned Prometheus export.

**Impact:**
- Repeated mistakes across sessions
- No personalization based on user patterns
- No team-level insights

**Potential Solutions:**

**Short-term (Prometheus integration):**
- Export metrics to Prometheus for aggregation
- Build Grafana dashboards for team visibility
- Alert on high correction rates

**Medium-term (Session intelligence):**
- Analyze past sessions before starting new ones
- "Your last 5 sessions averaged 3.2 corrections in Phase 2 - consider more thorough requirements gathering"
- Identify common correction patterns per technology profile

**Long-term (Adaptive workflow):**
- Adjust phase depth based on historical data
- Auto-suggest additional clarifying questions based on past corrections
- Personalized agent prompts based on user's common mistakes

---

### 3. Single-Developer Focus

**Problem:** Waypoints assumes a single developer working alone. No support for:
- Shared context between team members
- Handoffs between sessions/developers
- Team-level metrics aggregation
- Collaborative requirements gathering

**Impact:**
- Can't use for pair programming scenarios
- No visibility into team AI effectiveness
- Requirements gathered by one person can't transfer to another's implementation session

**Potential Solutions:**
- Shared state storage (Redis, database)
- Session export/import for handoffs
- Team metrics dashboard
- Multi-user requirements gathering mode

---

### 4. Static Analysis is Post-Hoc

**Problem:** Code quality analysis runs only at session end, missing opportunities for early feedback.

**Current Flow:**
```
Phase 4: Edit → Compile → Test → ... → Session End → Static Analysis
```

**Better Flow:**
```
Phase 4: Edit → Compile → Static Analysis → Test → Iterate
```

**Impact:**
- Code quality issues discovered after implementation is "done"
- No opportunity to fix issues while context is fresh
- Static analysis feels like an afterthought

**Potential Solutions:**
- Run lightweight linting after each edit in Phase 4
- Full static analysis before marking implementation complete
- Integrate with existing IDE linters (LSP)
- Block phase completion if critical issues found

---

### 5. No External Specification Import

**Problem:** Requirements must be manually communicated. No integration with:
- Jira/Linear tickets
- PRDs or design docs
- OpenAPI specifications
- Existing test suites

**Impact:**
- Duplicate effort re-explaining requirements
- Risk of divergence from official specifications
- Can't leverage existing documentation

**Potential Solutions:**
- `wp:import jira TICKET-123` to pull ticket details
- `wp:import openapi ./api-spec.yaml` to seed interface design
- `wp:import tests ./existing-tests/` to understand expected behavior
- MCP server for external system integration

---

## Frontier Research Categories

These represent advanced AI techniques that could enhance Waypoints. They're ordered roughly by implementation complexity.

### 1. Auto-Planning with Self-Correction

**Current Waypoints:** Manual phase progression with human approval at each gate.

**Frontier Approach:** AI systems that can plan multi-step solutions, execute them, and self-correct when encountering obstacles.

**Key Techniques:**

| Technique | Description | Relevance to Waypoints |
|-----------|-------------|------------------------|
| **ReAct** | Reasoning + Acting - interleave thinking and tool use | Could enhance Phase 1 requirements gathering |
| **Tree of Thoughts** | Explore multiple solution paths, backtrack on failures | Could enable automatic backtracking between phases |
| **Plan-and-Solve** | Generate high-level plan, then execute steps | Similar to Waypoints phases but automatic |
| **Reflexion** | Learn from mistakes within a session | Could reduce corrections by learning from early phase errors |

**Potential Integration:**
- Auto-generate Phase 2 interfaces from Phase 1 requirements (with human approval)
- Detect when implementation is failing and suggest backtracking
- Self-critique interface designs before presenting to user

**Research Papers:**
- "ReAct: Synergizing Reasoning and Acting in Language Models" (Yao et al., 2022)
- "Tree of Thoughts: Deliberate Problem Solving with Large Language Models" (Yao et al., 2023)
- "Reflexion: Language Agents with Verbal Reinforcement Learning" (Shinn et al., 2023)

---

### 2. Formal Verification & Property-Based Testing

**Current Waypoints:** Success = tests pass + code compiles.

**Frontier Approach:** Mathematical proof that code satisfies specifications, or automated generation of edge-case tests.

**Key Techniques:**

| Technique | Description | Relevance to Waypoints |
|-----------|-------------|------------------------|
| **Property-Based Testing** | Define properties that must hold, auto-generate test cases | Enhance Phase 3 test coverage |
| **Symbolic Execution** | Explore all code paths mathematically | Verify Phase 4 implementation correctness |
| **Formal Specification** | Mathematical description of expected behavior | More rigorous Phase 1 requirements |
| **Proof Assistants** | Tools like Coq, Lean for verified code | High-assurance implementations |

**Potential Integration:**
- Generate property-based tests in Phase 3 alongside example-based tests
- Use symbolic execution to find edge cases Phase 3 tests missed
- For critical code paths, generate formal specifications in Phase 1

**Tools/Frameworks:**
- Hypothesis (Python), QuickCheck (Haskell), fast-check (TypeScript)
- KLEE, angr (symbolic execution)
- Dafny, F* (verification-aware languages)

---

### 3. Retrieval-Augmented Generation (RAG) from Past Sessions

**Current Waypoints:** Each session starts fresh (or with phase summaries in Supervisor mode).

**Frontier Approach:** Augment AI context with relevant information retrieved from past sessions, documentation, or codebase.

**Key Techniques:**

| Technique | Description | Relevance to Waypoints |
|-----------|-------------|------------------------|
| **Session RAG** | Retrieve relevant past session fragments | "Last time you implemented auth, these were the corrections..." |
| **Codebase RAG** | Find similar existing implementations | "Here's how pagination was implemented elsewhere" |
| **Documentation RAG** | Pull relevant docs into context | Auto-include API docs when designing interfaces |
| **Error Pattern RAG** | Retrieve solutions to similar past errors | Speed up Phase 4 debugging |

**Potential Integration:**
- Before Phase 1, retrieve similar past requirements sessions
- In Phase 2, retrieve existing interfaces for similar features
- In Phase 4, retrieve solutions to similar compilation errors
- Build embeddings index of past sessions and codebase

**Technical Requirements:**
- Vector database (Pinecone, Weaviate, local FAISS)
- Embedding generation for sessions/code
- Relevance ranking

---

### 4. Multi-Agent Debate & Critic Agents

**Current Waypoints:** Single AI agent with phase-specific expert agents loaded into context.

**Frontier Approach:** Multiple AI agents with different roles that debate, critique, and refine each other's outputs.

**Key Techniques:**

| Technique | Description | Relevance to Waypoints |
|-----------|-------------|------------------------|
| **Debate** | Two agents argue opposing positions | Requirements: "Is this feature necessary?" |
| **Critic Agent** | Dedicated agent to find flaws | Review interfaces before Phase 3 |
| **Red Team Agent** | Adversarial agent finding security issues | Security review in Phase 2/4 |
| **Consensus Agents** | Multiple agents must agree | Higher confidence in design decisions |

**Potential Integration:**
- Phase 2: Critic agent reviews interface design before user approval
- Phase 3: Adversarial agent tries to find untested edge cases
- Phase 4: Security agent scans implementation for vulnerabilities
- Cross-phase: "Devil's advocate" agent challenges assumptions

**Architecture Considerations:**
- Cost (multiple LLM calls per decision)
- Latency (sequential debate rounds)
- Conflict resolution (when agents disagree)

**Research Papers:**
- "Improving Factuality and Reasoning in Language Models through Multiagent Debate" (Du et al., 2023)
- "Constitutional AI: Harmlessness from AI Feedback" (Anthropic, 2022)

---

### 5. Online Learning Within Sessions

**Current Waypoints:** AI behavior is static within a session. Corrections don't change future behavior.

**Frontier Approach:** AI that adapts its behavior based on feedback received during the session.

**Key Techniques:**

| Technique | Description | Relevance to Waypoints |
|-----------|-------------|------------------------|
| **In-Context Learning** | Learn from examples in the prompt | Include corrections as "don't do this" examples |
| **Verbal Reinforcement** | Natural language feedback shapes behavior | "You keep forgetting null checks" |
| **Prompt Refinement** | Automatically adjust prompts based on outcomes | Agent prompts evolve per session |
| **Memory Systems** | Persistent memory across conversation | Remember user preferences within session |

**Potential Integration:**
- After each correction, add it to a "lessons learned" context section
- Track correction patterns and preemptively warn about likely mistakes
- User can say "remember: always use Optional instead of null" and it persists
- Phase agents adapt based on what worked in earlier phases

**Challenges:**
- Context window limits
- Distinguishing session-specific vs. general lessons
- Avoiding over-fitting to one user's preferences

---

## Implementation Roadmap

This section defines the prioritized implementation plan based on impact, complexity, and alignment with Waypoints' philosophy of semi-autonomous AI development (AI handles technical execution, humans approve at phase gates).

### Priority Summary

| Priority | Feature | Status |
|----------|---------|--------|
| **P1** | RAG + Living Project Documents | **Implemented (v1.2.0)** |
| **P2** | External Specification Import | Planned |
| **P2** | Property-Based Testing in Phase 3 | **Implemented (v1.3.0)** |
| **P3** | Phase 2 Design Self-Critique | Future |
| **P3** | Backtracking Between Phases | Future |
| **P4** | Static Analysis in Phase 4 Loop | Planned |
| **On Hold** | Metrics Export (Prometheus) | Awaiting direction for open-source model |

---

### P4: Static Analysis in Phase 4 Loop

#### What It Is

Currently, static analysis (linting, code quality checks) runs only at the end of a session via `wp_static_analysis.py`. This means code quality issues are discovered after implementation is "complete," when the developer has mentally moved on and context is lost.

The improvement moves static analysis into the Phase 4 compile-test loop, so issues are caught and fixed while the code is still fresh in context.

#### Current Flow

```
Phase 4 Implementation:
  Developer requests change
       ↓
  Claude edits file
       ↓
  wp-auto-test.py runs:
    1. Compile
    2. Run tests
       ↓
  Report results to Claude
       ↓
  Repeat until tests pass
       ↓
  Session ends → Static analysis runs (too late!)
```

#### Proposed Flow

```
Phase 4 Implementation:
  Developer requests change
       ↓
  Claude edits file
       ↓
  wp-auto-test.py runs:
    1. Compile
    2. Lightweight lint (fast, critical issues only)
    3. Run tests
       ↓
  Report compile + lint + test results to Claude
       ↓
  Repeat until tests pass AND no critical lint issues
       ↓
  Before marking implementation complete:
    Full static analysis (comprehensive)
       ↓
  Block completion if critical issues remain
```

#### Implementation Details

**Step 1: Identify linting tools per technology profile**

Update `wp-config.json` to include lint commands for each profile:

```json
{
  "profiles": {
    "kotlin-maven": {
      "compile": "mvn clean compile -q",
      "test": "mvn test -q",
      "lint": "mvn detekt:check -q",
      "lintFast": "mvn detekt:check -q -Ddetekt.config=detekt-fast.yml"
    },
    "typescript-npm": {
      "compile": "npm run build",
      "test": "npm test",
      "lint": "npm run lint",
      "lintFast": "npm run lint -- --quiet"
    },
    "python-pytest": {
      "compile": "python -m py_compile",
      "test": "python -m pytest -q",
      "lint": "ruff check",
      "lintFast": "ruff check --select=E,F"
    }
  }
}
```

**Step 2: Modify wp-auto-test.py**

Add lint step between compile and test:

```python
# After successful compile
if phase == 4:
    # Run fast lint (critical issues only)
    lint_result = run_lint_fast(config)
    if lint_result.has_critical_issues:
        report_lint_issues(lint_result)
        # Don't block, but inform Claude

    # Run tests
    test_result = run_tests(config)
```

**Step 3: Add completion gate**

In `wp-activation.py`, when handling `wp:mark-complete implementation`:

```python
if 'implementation' in command:
    # Run full static analysis before allowing completion
    analysis_result = run_full_static_analysis(config)

    if analysis_result.has_blocking_issues:
        respond(f"Cannot complete: {analysis_result.issue_count} critical issues found. Fix these first.")
        return

    # Proceed with completion
    markers.mark_implementation_complete()
```

**Step 4: Configure severity levels**

Not all lint issues should block. Define severity in config:

```json
{
  "staticAnalysis": {
    "blockOnSeverity": ["error", "critical"],
    "warnOnSeverity": ["warning"],
    "ignoreOnSeverity": ["info", "style"]
  }
}
```

#### Benefits

1. **Issues fixed while context is fresh** - Claude just wrote the code, understands it perfectly
2. **Faster feedback loop** - Don't wait until session end to discover problems
3. **Quality gate** - Implementation can't be marked complete with critical issues
4. **Configurable strictness** - Teams can choose what blocks vs. warns

#### Complexity Assessment

- **Low complexity** - Mostly configuration and minor hook modifications
- **No new dependencies** - Uses existing linting tools
- **Backward compatible** - If no lint command configured, skip lint step

#### Files to Modify

1. `config/wp-config.json` - Add lint commands per profile
2. `hooks/wp-auto-test.py` - Add lint step to compile-test loop
3. `hooks/wp-activation.py` - Add completion gate
4. `hooks/lib/wp_static_analysis.py` - Add fast lint mode
5. `docs/architecture.md` - Update flow diagrams

---

### P1: RAG + Living Project Documents

#### What It Is

This feature creates persistent project knowledge that accumulates across sessions. Instead of each Waypoints session starting fresh, Claude has access to:

- **Architecture decisions** made in past sessions
- **Lessons learned** from corrections
- **Project patterns** and conventions
- **Known gotchas** specific to this codebase

This combines two frontier concepts:
1. **Retrieval-Augmented Generation (RAG)** - Pulling relevant past context into current session
2. **Online Learning** - Building knowledge from corrections that persists

#### The Vision: Living Documents

```
~/.claude/waypoints/knowledge/{project-id}/
├── architecture.md       # System architecture, evolves over time
├── decisions.md          # Architecture Decision Records (ADRs)
├── lessons-learned.md    # Corrections from past sessions
├── patterns.md           # "In this codebase, we do X this way"
└── gotchas.md            # "Don't forget: this API requires auth header"
```

Each document serves a specific purpose and is updated at specific points in the workflow.

#### Document Specifications

**architecture.md** - System Overview

Updated: End of Phase 2 (Interface Design)

Content:
- Service/module inventory
- Key interfaces and their responsibilities
- Integration points (databases, external APIs)
- Technology stack decisions

Example:
```markdown
# Project Architecture
Last updated: 2026-01-21

## Services
- **OrderService** - Order CRUD, validation, state transitions
- **PaymentService** - Payment processing, refunds
- **NotificationService** - Email/SMS notifications (async via Kafka)

## Data Layer
- PostgreSQL for transactional data
- Redis for caching (15min TTL)
- Kafka for async events

## External Integrations
- Stripe API for payments (requires API key in env)
- SendGrid for emails
```

**decisions.md** - Architecture Decision Records

Updated: When significant decisions are made (any phase)

Content:
- Decision context and date
- Options considered
- Decision made and rationale
- Consequences/trade-offs

Example:
```markdown
# Architecture Decisions

## 2026-01-21: Order Export Format
**Context:** Need to export orders for finance team
**Options:**
1. CSV - Simple, existing tooling expects this
2. Excel - Richer formatting
3. JSON - Machine-readable

**Decision:** CSV format
**Rationale:** Finance team's import tool only accepts CSV. Excel would require them to change their workflow.
**Consequences:** Limited formatting options, but immediate compatibility.

## 2026-01-20: Async Processing Threshold
**Context:** Large operations block the UI
**Decision:** Operations affecting >1000 records run async
**Rationale:** Based on P95 response time analysis
```

**lessons-learned.md** - Corrections Accumulated

Updated: After each correction in any phase (captured by judge)

Content:
- Date and phase
- What Claude assumed/did wrong
- What the correct approach was
- Generalized lesson

Example:
```markdown
# Lessons Learned

## 2026-01-21 (Phase 4)
**Mistake:** Assumed `OrderRepository.findAll()` was paginated
**Correction:** It returns ALL records, causing memory issues
**Lesson:** Always verify repository pagination. Use `findAllPaginated()` for bulk operations.

## 2026-01-20 (Phase 2)
**Mistake:** Proposed throwing exceptions for expected errors
**Correction:** User prefers `Result<T, E>` for expected failures
**Lesson:** Use Result type for expected errors, exceptions only for unexpected failures.

## 2026-01-19 (Phase 1)
**Mistake:** Assumed feature needed real-time updates
**Correction:** Polling every 30s is acceptable for this use case
**Lesson:** Always ask about real-time requirements - don't assume.
```

**patterns.md** - Project Conventions

Updated: End of Phase 4 when new patterns are established

Content:
- Recurring implementation patterns
- Code conventions specific to this project
- Reference implementations

Example:
```markdown
# Project Patterns

## Repository Pattern
All data access goes through repositories. Never access database directly from services.
Reference: `OrderRepository.kt`

## Async Job Pattern
For operations >1000 records:
1. Create job via `JobService.createJob(type, payload)`
2. Return job ID to caller immediately
3. Job executes async, updates status
4. Caller polls or subscribes to completion
Reference: `OrderService.exportOrders()`

## Error Handling
- Expected errors: Return `Result<T, DomainError>`
- Unexpected errors: Let exception propagate, global handler catches
- Always log at point of origin, not at catch site
```

**gotchas.md** - Quick Warnings

Updated: When non-obvious issues are discovered

Content:
- Short warnings about non-obvious behaviors
- Environment-specific issues
- Common mistakes

Example:
```markdown
# Gotchas

- **Stripe API:** Test mode keys start with `sk_test_`. Production starts with `sk_live_`. Check env before testing payments.

- **OrderRepository.findAll():** NOT paginated! Use `findAllPaginated()` for >100 records.

- **Kafka topics:** Must be created manually in prod. Dev auto-creates.

- **Date handling:** All dates stored as UTC. Convert to user timezone only in presentation layer.

- **Auth header:** External API calls require `X-API-Key` header, not Bearer token.
```

#### How Documents Are Updated

**Automatic Updates (via hooks):**

1. **Session Start (`wp:init`):**
   - Load all knowledge documents into context
   - Display summary: "Loaded project knowledge: 3 decisions, 5 lessons, 2 patterns"

2. **Phase Completion:**
   - Phase 1 complete: Prompt Claude to identify any decisions made
   - Phase 2 complete: Prompt Claude to update architecture.md
   - Phase 4 complete: Prompt Claude to identify new patterns

3. **Correction Detected (via judge):**
   - Automatically append to lessons-learned.md
   - Include phase, context, and generalized lesson

**Manual Updates (Claude-initiated):**

Claude can update documents anytime via commands:
```bash
true # wp:knowledge update architecture "Added new CacheService for Redis integration"
true # wp:knowledge gotcha "Redis connection pool max is 10, increase for high-traffic"
```

#### How Documents Are Used

**Session Start:**
```
[System] Loading project knowledge for project-abc123...
  - Architecture: 4 services, PostgreSQL + Redis + Kafka
  - Decisions: 7 recorded
  - Lessons: 12 learned
  - Patterns: 3 established
  - Gotchas: 5 warnings

Key lessons relevant to common tasks:
  - Use Result<T,E> for expected errors (corrected 2026-01-20)
  - Verify repository pagination before bulk operations (corrected 2026-01-21)
```

**During Requirements (Phase 1):**
```
User: "I need to add bulk delete for orders"

Claude (with RAG): "Based on project patterns, bulk operations affecting
>1000 records should run async (see Async Job Pattern). Should bulk
delete follow this pattern?

Also noting from lessons-learned: verify that OrderRepository has a
paginated delete method before assuming it exists."
```

**During Implementation (Phase 4):**
```
Claude about to write: orderRepository.findAll()

[System injects from gotchas.md]:
"Warning: OrderRepository.findAll() is NOT paginated.
Use findAllPaginated() for >100 records."

Claude revises to: orderRepository.findAllPaginated(pageSize = 100)
```

#### Implementation Phases

**Phase 1: Simple File-Based (MVP)**

- Store documents as plain markdown files
- Load all documents into context at session start
- Claude updates via explicit commands
- No semantic search, just full document inclusion

Complexity: Low
Value: High - immediately useful

**Phase 2: Automatic Updates**

- Hooks automatically prompt for updates at phase boundaries
- Judge results auto-append to lessons-learned.md
- Claude summarizes and updates without explicit commands

Complexity: Medium
Value: Medium - reduces friction

**Phase 3: Semantic Search (RAG)**

- Generate embeddings for document chunks
- Only load relevant chunks based on current task
- Use vector similarity to find related past work

Complexity: High (requires embedding infrastructure)
Value: High for large projects with extensive history

#### Technical Considerations

**Project Identification:**
- Use git remote URL hash, or
- Use project directory path hash, or
- Manual project ID in `.waypoints-project` file

**Context Window Management:**
- MVP: Load all docs (works for small projects)
- Later: Summarize or use RAG for large knowledge bases

**Storage Location:**
```
~/.claude/waypoints/knowledge/
├── {project-hash-1}/
│   ├── architecture.md
│   ├── decisions.md
│   └── ...
├── {project-hash-2}/
│   └── ...
└── index.json  # Maps project paths to hashes
```

#### Files to Create/Modify

1. `hooks/lib/wp_knowledge.py` - Knowledge management library
2. `hooks/wp-activation.py` - Load knowledge on init, update on phase complete
3. `hooks/lib/wp_judge.py` - Auto-append corrections to lessons-learned
4. `config/wp-config.json` - Knowledge settings (enable/disable, paths)
5. `agents/wp-developer.md` - Instructions for using knowledge commands
6. New skill: `/wp-knowledge` - View/manage project knowledge

---

### P2: External Specification Import

#### What It Is

Allow users to import requirements from external sources rather than manually explaining them. This reduces duplicate effort and ensures alignment with official specifications.

#### Supported Import Sources

**Jira/Linear Tickets:**
```bash
true # wp:import jira PROJ-123
true # wp:import linear ISSUE-456
```

Imports:
- Ticket title and description
- Acceptance criteria
- Linked tickets/epics
- Comments (optional)

**OpenAPI Specifications:**
```bash
true # wp:import openapi ./api-spec.yaml
```

Imports:
- Endpoint definitions
- Request/response schemas
- Authentication requirements
- Seeds Phase 2 interface design

**Existing Test Files:**
```bash
true # wp:import tests ./src/test/OrderServiceTest.kt
```

Imports:
- Test names as requirements ("should calculate total correctly")
- Test structure as behavior specification
- Helps when adding features to existing code

**Markdown/Text Files:**
```bash
true # wp:import spec ./requirements.md
```

Imports:
- PRD or design document
- User stories
- Technical specifications

#### Implementation Approach

**MCP Server Integration (Recommended):**

Create an MCP server that handles imports:

```typescript
// mcp-waypoints-import/src/index.ts
server.addTool({
  name: "import_jira",
  description: "Import Jira ticket as requirements",
  parameters: { ticketId: "string" },
  handler: async ({ ticketId }) => {
    const ticket = await jiraClient.getTicket(ticketId);
    return formatAsRequirements(ticket);
  }
});
```

Benefits:
- Authentication handled by MCP server
- Extensible to new sources
- Keeps Waypoints core simple

**Direct Integration (Alternative):**

Add import handlers to wp-activation.py:

```python
if 'wp:import' in command:
    if 'jira' in command:
        ticket_id = extract_ticket_id(command)
        requirements = fetch_jira_ticket(ticket_id)
        respond(f"Imported requirements from {ticket_id}:\n\n{requirements}")
```

#### User Experience

```
User: /wp-start
Claude: Waypoints initialized. Phase 1: Requirements Gathering.

User: true # wp:import jira PROJ-123

Claude: Imported from PROJ-123:

**Title:** Add bulk order export feature

**Description:**
As a finance team member, I need to export orders to CSV
so I can import them into our accounting system.

**Acceptance Criteria:**
- [ ] Export includes order ID, date, total, status
- [ ] Can filter by date range
- [ ] Can filter by status
- [ ] Large exports (>1000) should be async

**Questions before proceeding:**
1. The ticket mentions CSV - should we support other formats?
2. "Large exports should be async" - is 1000 the right threshold?
3. Should the export include line items or just order summary?
```

#### Priority Justification

Medium priority because:
- Users can copy/paste ticket content (workaround exists)
- Improves UX but doesn't enable new capabilities
- Requires external service authentication (complexity)

---

### P2: Property-Based Testing in Phase 3

#### What It Is

Enhance Phase 3 (Test Writing) to include property-based tests alongside traditional example-based tests. Property-based testing defines invariants that must always hold, then auto-generates hundreds of test cases to find edge cases.

#### The Problem with Example-Based Tests

Traditional tests check specific examples:

```kotlin
@Test
fun `should calculate order total`() {
    val order = Order(items = listOf(
        Item(price = 10.0),
        Item(price = 20.0)
    ))
    assertEquals(30.0, order.total())
}
```

This tests ONE case. But what about:
- Empty orders?
- Orders with 10,000 items?
- Items with price = 0?
- Items with negative prices (if that's invalid)?
- Prices that would overflow?

You'd need to manually think of and write each edge case.

#### Property-Based Testing Solution

Instead of examples, define properties that must ALWAYS be true:

```kotlin
@Property
fun `total equals sum of item prices`(
    @ForAll items: List<@Positive Double>
) {
    val order = Order(items.map { Item(price = it) })
    assertEquals(items.sum(), order.total(), 0.001)
}

@Property
fun `total is non-negative for valid items`(
    @ForAll @Size(max = 1000) items: List<@Positive Double>
) {
    val order = Order(items.map { Item(price = it) })
    assertTrue(order.total() >= 0)
}

@Property
fun `adding item increases total`(
    @ForAll existingItems: List<@Positive Double>,
    @ForAll @Positive newItemPrice: Double
) {
    val order = Order(existingItems.map { Item(it) })
    val originalTotal = order.total()

    order.addItem(Item(newItemPrice))

    assertTrue(order.total() > originalTotal)
}
```

The testing framework auto-generates hundreds of inputs:
- Empty list, single item, many items
- Boundary values (0.001, MAX_DOUBLE)
- Random combinations

If any input violates the property, it reports the minimal failing case.

#### Waypoints Integration

**Enhanced Phase 3 Flow:**

```
Current Phase 3:
  Claude writes example-based tests for:
    - Happy path
    - Known edge cases from requirements
    - Error scenarios

Enhanced Phase 3:
  Step 1: Claude writes example-based tests (same as current)

  Step 2: Claude identifies properties:
    "What must ALWAYS be true about this code?"
    - "Total is never negative"
    - "Adding item increases total"
    - "Removing item decreases total"
    - "Empty order has zero total"

  Step 3: Claude generates property-based tests

  Step 4: Framework runs property tests, may find edge cases

  Step 5: If edge cases found, add them as explicit tests
```

**Example Output:**

```kotlin
// ========== Example-Based Tests ==========

@Test
fun `should calculate total for typical order`() {
    // given
    val order = Order(listOf(Item(10.0), Item(20.0)))

    // when
    val total = order.total()

    // then
    assertEquals(30.0, total)
}

@Test
fun `should return zero for empty order`() {
    val order = Order(emptyList())
    assertEquals(0.0, order.total())
}

// ========== Property-Based Tests ==========

@Property
fun `total equals sum of prices`(@ForAll items: List<@Positive Double>) {
    val order = Order(items.map { Item(it) })
    assertEquals(items.sum(), order.total(), 0.001)
}

@Property
fun `total is associative - order of items doesnt matter`(
    @ForAll items: List<@Positive Double>
) {
    val order1 = Order(items.map { Item(it) })
    val order2 = Order(items.shuffled().map { Item(it) })
    assertEquals(order1.total(), order2.total(), 0.001)
}
```

#### Libraries by Language

| Language | Library | Notes |
|----------|---------|-------|
| Kotlin | Kotest Property Testing | Built into Kotest |
| Java | jqwik | JUnit 5 compatible |
| Python | Hypothesis | Most mature, excellent |
| TypeScript | fast-check | Good TS support |
| Go | gopter | Property-based for Go |
| Rust | proptest | Rust standard |

#### Implementation Details

**Step 1: Update Phase 3 agent instructions**

In `agents/wp-developer.md`, add to Phase 3 section:

```markdown
### Phase 3: Test Writing

After writing example-based tests, identify properties:

1. **Invariants**: What must ALWAYS be true?
   - "Balance is never negative"
   - "List size equals count"

2. **Relationships**: How do operations relate?
   - "add then remove = original"
   - "sort is idempotent"

3. **Boundaries**: What are the limits?
   - "Max 100 items per order"
   - "Price between 0 and 1,000,000"

Generate property-based tests using [language-appropriate library].
```

**Step 2: Add property test detection to wp-auto-test.py**

Detect if property tests exist and run them:

```python
def run_tests(config):
    # Run regular tests
    result = run_command(config.test_command)

    # Check for property test failures
    if "Property test failed" in result.output:
        # Extract the minimal failing case
        failing_case = extract_failing_case(result.output)
        return TestResult(
            passed=False,
            message=f"Property test found edge case: {failing_case}"
        )
```

#### Benefits

1. **Finds edge cases humans miss** - Framework explores input space systematically
2. **Living documentation** - Properties describe behavior precisely
3. **Regression prevention** - Future changes must satisfy all properties
4. **Minimal effort** - Once properties defined, framework generates tests

#### Complexity Assessment

- **Medium complexity** - Requires understanding property testing concepts
- **Library dependent** - Need to add library to project dependencies
- **High value** - Significantly improves test coverage with little manual effort

---

### P4: Phase 2 Design Self-Critique

#### What It Is

Before presenting interface designs to the user for approval, Claude performs a self-critique pass to identify potential issues. This catches design problems before they propagate to tests and implementation.

#### How It Works

```
Phase 2 Flow (Current):
  Claude designs interfaces
       ↓
  Present to user
       ↓
  User approves or requests changes

Phase 2 Flow (Enhanced):
  Claude designs interfaces
       ↓
  Claude critiques own design:
    "What could go wrong with this?"
    "What's missing?"
    "What will be hard to test?"
       ↓
  Claude revises based on critique
       ↓
  Present to user WITH critique notes
       ↓
  User approves or requests changes
```

#### Implementation

This doesn't require a separate agent - it's a two-pass prompt:

**Pass 1 - Design:**
```
Design interfaces for [requirements].
Follow project patterns from architecture.md.
```

**Pass 2 - Critique:**
```
Review this interface design and identify:
1. Missing error cases
2. Unclear responsibilities
3. Potential testing difficulties
4. Violations of project patterns
5. Security considerations

Then revise the design to address critical issues.
```

#### Example Output

```
## Proposed Interface Design

class OrderExportService(
    private val orderRepository: OrderRepository,
    private val exportJobService: ExportJobService
) {
    suspend fun exportOrders(
        filter: OrderFilter,
        format: ExportFormat = ExportFormat.CSV
    ): Result<ExportJob, ExportError>

    suspend fun getExportStatus(jobId: String): Result<ExportStatus, ExportError>

    suspend fun downloadExport(jobId: String): Result<ByteArray, ExportError>
}

## Self-Critique Notes

**Addressed in design:**
- ✅ Large exports are async (returns job, not data)
- ✅ Uses Result type per project patterns
- ✅ Filter is separate class for extensibility

**Potential concerns:**
- ⚠️ `downloadExport` returns ByteArray - may cause memory issues for large exports
  - Consider: Return InputStream or presigned URL instead?
- ⚠️ No pagination for `getExportStatus` if user has many jobs
  - Consider: Add `listExportJobs(page, size)` method?
- ⚠️ `ExportFormat` enum - what if we need custom formats later?
  - Consider: Keep as enum for now, refactor if needed

**Questions for user:**
1. Should download return a stream/URL instead of ByteArray?
2. Do we need to list past export jobs?
```

#### When to Enable

This adds latency (extra LLM pass) so could be opt-in:

```bash
# Explicit request
true # wp:mark-complete requirements --with-review

# Or automatic for certain keywords
# (detected "api", "interface", "contract" in requirements)
```

#### Priority Justification

P4 because:
- Adds cost and latency
- User can catch issues during review anyway
- Most valuable for complex/public APIs, less for internal code

---

### P4: Backtracking Between Phases

#### What It Is

Allow returning to a previous phase without losing all progress. Currently, if Phase 4 reveals a design flaw, users must reset and start over.

#### Proposed Commands

```bash
true # wp:backtrack interfaces   # Return to Phase 2
true # wp:backtrack tests        # Return to Phase 3
true # wp:backtrack requirements # Return to Phase 1
```

#### What Gets Preserved

| Backtrack To | Preserved | Discarded |
|--------------|-----------|-----------|
| Phase 1 | Nothing (fresh start) | All work |
| Phase 2 | Requirements summary | Interfaces, tests, implementation |
| Phase 3 | Requirements + interfaces | Tests, implementation |

#### Implementation

```python
# In wp-activation.py

if 'wp:backtrack' in command:
    target = extract_backtrack_target(command)
    current_phase = markers.get_phase()

    if target == 'interfaces':  # Back to Phase 2
        markers.set_phase(2)
        markers.clear_marker('interfaces-designed')
        markers.clear_marker('tests-approved')
        metrics.record_backtrack(from_phase=current_phase, to_phase=2)
        respond("Returning to Phase 2: Interface Design. Tests and implementation discarded.")

    # Similar for other targets
```

#### Metrics Tracking

Backtracking is valuable data:
- Which phase transitions cause backtracking?
- How often do designs need revision after implementation starts?
- Are certain types of requirements more likely to need redesign?

#### Priority Justification

P4 because:
- Users can work around with `/wp-reset`
- Adds complexity to state management
- Useful but not blocking adoption

---

### On Hold: Metrics Export (Prometheus)

#### Current Status

Metrics are collected locally in `~/.claude/waypoints/metrics/{session-id}.json`. This was implemented to validate that metrics collection works correctly.

#### The Question

For an open-source tool:
1. **Should metrics be exported centrally?**
   - Legal/privacy concerns with collecting user data
   - Users may not want their development patterns tracked

2. **Who benefits from aggregated metrics?**
   - Tool maintainer: Understand usage patterns, improve tool
   - Enterprise users: Track team AI effectiveness
   - Individual users: Personal insights

#### Possible Directions

**Option A: Local-Only (Current)**
- Metrics stay on user's machine
- User can analyze their own data
- No privacy concerns
- No aggregated insights for tool improvement

**Option B: Opt-In Export**
- Users explicitly enable export
- Clear privacy policy
- Anonymized data only
- Legal review required

**Option C: Enterprise Feature**
- Local metrics for open-source
- Prometheus export for paid/enterprise version
- Clear value proposition for companies

#### Decision

On hold until:
1. Clear direction on open-source vs. enterprise model
2. Legal review of data collection for open-source
3. User feedback on whether they want aggregated insights

---

## Implementation Priority Matrix (Updated)

| Priority | Feature | Impact | Complexity | Status |
|----------|---------|--------|------------|--------|
| **P1** | RAG + Living Project Documents | High | Medium | **Implemented (v1.2.0)** |
| **P2** | External Specification Import | Medium | Medium | Planned |
| **P2** | Property-Based Testing in Phase 3 | Medium | Medium | **Implemented (v1.3.0)** |
| **P3** | Phase 2 Design Self-Critique | Medium | Low | Future |
| **P3** | Backtracking Between Phases | Medium | Medium | Future |
| **P4** | Static Analysis in Phase 4 Loop | Low | Low | Planned |
| **On Hold** | Metrics Export | Medium | Low | Awaiting direction |

---

## Discussion Questions

1. **Autonomy vs. Control:** How much should we automate vs. keep human-in-the-loop? Backtracking could be automatic or require approval.

2. **Cost Considerations:** Multi-agent approaches multiply API costs. Is the quality improvement worth it?

3. **Complexity Budget:** Each feature adds complexity. What's the maximum acceptable complexity for a workflow tool?

4. **Target Users:** Are we optimizing for individual developers or teams? This affects prioritization significantly.

5. **Integration Depth:** Should Waypoints integrate deeply with specific tools (Jira, GitHub) or stay tool-agnostic?

---

## References

- Yao, S., et al. (2022). "ReAct: Synergizing Reasoning and Acting in Language Models"
- Yao, S., et al. (2023). "Tree of Thoughts: Deliberate Problem Solving with Large Language Models"
- Shinn, N., et al. (2023). "Reflexion: Language Agents with Verbal Reinforcement Learning"
- Du, Y., et al. (2023). "Improving Factuality and Reasoning in Language Models through Multiagent Debate"
- Anthropic (2022). "Constitutional AI: Harmlessness from AI Feedback"
- Wei, J., et al. (2022). "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models"
