# Waypoints Status

Check the current Waypoints workflow status:

```bash
true # wp:status
```

## Phase Overview

| Phase | Name | Goal | Command to Complete |
|-------|------|------|---------------------|
| 1 | Requirements | Understand what to build | `true # wp:mark-complete requirements` |
| 2 | Interfaces | Design structure without logic | `true # wp:mark-complete interfaces` |
| 3 | Tests | Write failing tests | `true # wp:mark-complete tests` |
| 4 | Implementation | Make tests pass | (automatic when tests pass) |

## Commands

- `/wp-start` - Start Waypoints mode
- `/wp-status` - Show current status (this command)
- `/wp-reset` - Reset Waypoints state and start fresh
