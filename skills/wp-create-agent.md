# Create Agent

Interactive agent generator. Walk the user through creating a custom agent for their workflow.

## Process

### Step 1: Gather Basic Information

Use AskUserQuestion to collect:

**Question 1: Agent Identity**
- "What should this agent be called?" (e.g., "API Designer", "Database Expert")
- "What is the agent's primary role in 1-2 sentences?"

**Question 2: Expertise Areas**
- "What are the 3-5 key areas of expertise for this agent?"
- Examples: "REST API design", "SQL optimization", "React components"

**Question 3: Core Principles**
- "What 2-3 guiding principles should this agent follow?"
- Examples: "Consistency over cleverness", "Security first", "Keep it simple"

**Question 4: Quality Standards**
- "What does 'good work' look like for this agent? List 3-5 criteria."

**Question 5: Communication Style**
- "How should this agent communicate?"
- Options: "Concise and technical" / "Detailed with explanations" / "Ask questions before acting"

### Step 2: Waypoints Phase Binding (Optional)

Ask: "Should this agent auto-load during specific Waypoints phases?"

If yes, ask: "Which phases?" with multi-select options:
- Phase 1: Requirements Gathering
- Phase 2: Interface Design
- Phase 3: Test Writing
- Phase 4: Implementation

### Step 3: Generate Agent File

Create the agent file at `~/.claude/waypoints/agents/{agent-name-slug}.md` with this structure:

```markdown
---
name: {Agent Name}
phases: [{selected phases as numbers, e.g., 2, 3}]
---

# {Agent Name} Agent

## Role
{Role description from user input}

## Core Expertise
{List expertise areas as bullet points}

## Core Principles
{List principles as bullet points}

## Quality Standards
{List quality criteria as bullet points}

## Communication Style
{Communication preference}
```

### Step 4: Confirm Creation

Output to user:
```
Created: ~/.claude/waypoints/agents/{filename}.md
{If phases selected: "Bound to Waypoints phases: {phase names} - will auto-load during these phases"}

To customize further, edit the file directly.
```

## Notes

- Keep generated agents minimal (under 100 lines)
- User can always edit the file to add more sections from the full template
- Slug the agent name for filename (lowercase, hyphens instead of spaces)
- If no phases selected, omit the `phases` field from frontmatter
