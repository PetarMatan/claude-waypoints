# Waypoints Workflow Activation

**MANDATORY FIRST STEP** - Execute this command IMMEDIATELY to activate Waypoints mode:

```bash
true # wp:init
```

After executing the command above, load the Waypoints developer agent from the installed location or use the built-in guidance below.

---

## Waypoints Workflow Activated

You are now in **Waypoints** mode. The workflow enforces these phases:

1. **Phase 1: Requirements** - Gather and clarify requirements with user
2. **Phase 2: Interfaces** - Create class/method skeletons (no logic)
3. **Phase 3: Tests** - Write failing tests, get user approval
4. **Phase 4: Implementation** - Autonomous loop until tests pass

**Current Phase: 1 - Requirements Gathering**

## Phase Transitions

To advance through phases after user approval:

- Phase 1 -> 2: `true # wp:mark-complete requirements`
- Phase 2 -> 3: `true # wp:mark-complete interfaces`
- Phase 3 -> 4: `true # wp:mark-complete tests`

## Getting Started

Begin by asking the user to describe the feature they want to implement. Ask clarifying questions for any ambiguities.

**Required Questions:**
1. What is the feature/functionality needed?
2. What are the expected inputs and outputs?
3. What error scenarios should be handled?
4. Are there any edge cases to consider?
5. What external dependencies are involved?

Once requirements are clear and user confirms, mark requirements complete and proceed to interface design.
