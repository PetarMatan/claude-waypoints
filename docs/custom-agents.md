# Custom Agents Guide

Custom agents are one of the most powerful features of Claude Waypoints. They let you inject domain expertise, coding standards, and specialized knowledge into each phase of development.

## What is an Agent?

An agent is a markdown file that gets loaded into Claude's context during specific phases. Think of it as a system prompt that shapes how Claude thinks about your particular problem space.

When you start Phase 2 (Interface Design), for example, any agents bound to Phase 2 are automatically loaded. Claude then has access to that agent's expertise, principles, and standards while working through that phase.

Agents are stored in `~/.claude/waypoints/agents/` and use YAML frontmatter to specify which phases they activate in.

## Why Create Custom Agents?

### Domain Expertise

Your business has specific rules, patterns, and conventions that Claude doesn't know about. An agent can encode this knowledge:

- Your API naming conventions
- Your database schema patterns
- Your error handling standards
- Industry-specific regulations or requirements

### Quality Standards

Different teams have different definitions of "good code." Agents can enforce your standards:

- Code style preferences
- Documentation requirements
- Testing coverage expectations
- Performance considerations

### Phase-Specific Guidance

Different phases benefit from different types of expertise:

| Phase | Agent Type | Example |
|-------|------------|---------|
| 1 - Requirements | Domain expert, Business analyst | Someone who knows your product deeply |
| 2 - Interfaces | Architect, API designer | Someone who thinks about structure |
| 3 - Tests | Testing specialist | Someone obsessed with edge cases |
| 4 - Implementation | Senior developer | Someone who knows the codebase patterns |

### Consistency Across Sessions

Without agents, you'd need to re-explain your preferences every session. Agents make that knowledge persistent.

## Creating an Agent

### Option 1: Interactive Creation

Run `/wp-create-agent` in Claude Code. Claude will walk you through:

1. **Agent Identity** - Name and primary role
2. **Expertise Areas** - 3-5 key areas of knowledge
3. **Core Principles** - 2-3 guiding rules
4. **Quality Standards** - What "good work" looks like
5. **Communication Style** - How the agent should interact
6. **Phase Binding** - Which Waypoints phases should auto-load this agent

The agent file is created automatically at `~/.claude/waypoints/agents/{name}.md`.

### Option 2: Manual Creation

Create a markdown file in `~/.claude/waypoints/agents/` with this structure:

```markdown
---
name: Your Agent Name
phases: [2, 3]
---

# Your Agent Name

## Role
One or two sentences describing what this agent does.

## Core Expertise
- Area of knowledge 1
- Area of knowledge 2
- Area of knowledge 3

## Core Principles
- Principle that guides decisions
- Another guiding principle

## Quality Standards
- What good output looks like
- Another quality criterion

## Communication Style
How this agent should interact (concise, detailed, questioning, etc.)
```

The `phases` field is optional. If omitted, the agent won't auto-load but can still be manually referenced.

## Examples

### API Designer (Phase 2)

```markdown
---
name: API Designer
phases: [2]
---

# API Designer

## Role
Expert in REST API design, focused on consistency and developer experience.

## Core Expertise
- RESTful resource modeling
- HTTP semantics (methods, status codes, headers)
- API versioning strategies
- Request/response schema design

## Core Principles
- Consistency over cleverness
- Predictable patterns across all endpoints
- Errors should be actionable

## Quality Standards
- All endpoints follow REST conventions
- Error responses include error codes and messages
- Resource names are plural nouns
- Relationships expressed through nested routes or links

## Communication Style
Ask clarifying questions about edge cases before proposing designs.
```

### Testing Specialist (Phase 3)

```markdown
---
name: Testing Specialist
phases: [3]
---

# Testing Specialist

## Role
Obsessed with test coverage, edge cases, and failure modes.

## Core Expertise
- Unit testing patterns
- Integration test design
- Mocking strategies
- Test data management

## Core Principles
- Test behavior, not implementation
- Every requirement needs at least one test
- Edge cases are where bugs hide

## Quality Standards
- Happy path covered
- Error cases covered
- Boundary conditions tested
- Tests are readable and self-documenting

## Communication Style
Challenge assumptions. Ask "what happens if..." questions.
```

### Domain Expert (Phase 1)

```markdown
---
name: E-commerce Domain Expert
phases: [1]
---

# E-commerce Domain Expert

## Role
Deep knowledge of e-commerce patterns, payment flows, and inventory management.

## Core Expertise
- Shopping cart behavior
- Checkout flows
- Payment processing
- Inventory and stock management
- Order lifecycle

## Core Principles
- Never lose a customer's cart
- Payment failures must be recoverable
- Stock accuracy is critical

## Quality Standards
- All money calculations use decimal precision
- Cart state is persisted
- Concurrent stock updates handled correctly

## Communication Style
Ask about business rules. Clarify what happens in failure scenarios.
```

## Tips for Effective Agents

### Keep It Focused

An agent that tries to cover everything covers nothing well. Better to have multiple focused agents than one sprawling one.

### Be Specific

Vague: "Write good code"
Specific: "Functions should be under 20 lines. Use early returns to reduce nesting."

### Include the "Why"

When stating principles, include reasoning. This helps Claude make good decisions in novel situations.

### Think About Phase Fit

- Phase 1 agents should ask good questions
- Phase 2 agents should think about structure
- Phase 3 agents should think about failure modes
- Phase 4 agents should think about clean implementation

### Iterate

Your first agent won't be perfect. Use it, notice where Claude goes off track, and refine the agent's instructions.

## Managing Agents

**List all agents:**
```bash
ls ~/.claude/waypoints/agents/
```

**Edit an agent:**
```bash
$EDITOR ~/.claude/waypoints/agents/your-agent.md
```

**Remove an agent:**
```bash
rm ~/.claude/waypoints/agents/your-agent.md
```

**Temporarily disable an agent:**
Remove its phases or rename the file to `.md.disabled`.
