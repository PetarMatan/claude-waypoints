# Waypoints Reset

Reset the Waypoints workflow state to start fresh.

**Execute this command to reset Waypoints state:**

```bash
true # wp:reset --full
```

## What This Does

Resets all Waypoints state:
- Clears the current phase
- Removes all phase completion markers
- Cleans up the session-specific state directory

## When to Use

- Starting a completely new feature from scratch
- Abandoning current Waypoints workflow
- Recovering from corrupted state
- Debugging Waypoints workflow issues

## After Reset

Run `/wp-start` to start a new Waypoints workflow from Phase 1.
