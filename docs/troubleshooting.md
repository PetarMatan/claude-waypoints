# Troubleshooting Guide

## Common Issues

### Waypoints Mode Not Activating

**Symptoms:**
- `/wp-start` command doesn't activate Waypoints mode
- Phase guards not working

**Solutions:**

1. Check marker directory exists:
   ```bash
   mkdir -p ~/.claude/tmp
   ```

2. Verify markers can be created:
   ```bash
   touch ~/.claude/tmp/test && rm ~/.claude/tmp/test
   echo "Success"
   ```

3. Check permissions on settings.json allow marker operations:
   ```json
   "permissions": {
     "allow": [
       "Bash(mkdir -p ~/.claude/tmp:*)",
       "Bash(touch ~/.claude/tmp/:*)"
     ]
   }
   ```

### Hooks Not Running

**Symptoms:**
- No compilation after file changes
- Phase transitions not happening
- No blocking messages

**Solutions:**

1. Verify installation:
   ```bash
   ls -la ~/.claude/waypoints/hooks/
   ```

2. Check hooks are executable:
   ```bash
   chmod +x ~/.claude/waypoints/hooks/*.py
   ```

3. Verify settings.json has hooks configured:
   ```bash
   cat ~/.claude/settings.json | grep -A5 "wp-orchestrator"
   ```

4. Check for syntax errors in hooks:
   ```bash
   python3 -m py_compile ~/.claude/waypoints/hooks/wp-orchestrator.py
   ```

### Wrong Profile Detected

**Symptoms:**
- Compile command for wrong language
- Source patterns not matching files

**Solutions:**

1. Check detected profile:
   ```bash
   # In project directory
   cat ~/.claude/waypoints/config/wp-config.json | python3 -c "
   import json, sys
   config = json.load(sys.stdin)
   for name, profile in config['profiles'].items():
       print(f'{name}: {profile[\"detection\"]}')"
   ```

2. Force a specific profile:
   ```bash
   echo '{"activeProfile": "typescript-npm"}' > ~/.claude/wp-override.json
   ```

3. Clear override:
   ```bash
   rm ~/.claude/wp-override.json
   ```

### Stuck in a Phase

**Symptoms:**
- Can't advance to next phase
- Marker file not being created

**Solutions:**

1. Check current status:
   ```bash
   /wp-status
   ```

2. Check if marker file exists:
   ```bash
   ls -la ~/.claude/tmp/wp-*
   ```

3. Manually advance phase (if appropriate):
   ```bash
   true # wp:mark-complete requirements  # Phase 1->2
   true # wp:mark-complete interfaces    # Phase 2->3
   true # wp:mark-complete tests         # Phase 3->4
   ```

4. Reset and start over:
   ```bash
   /wp-reset
   ```

### Compilation Errors Not Displayed

**Symptoms:**
- Build fails but no errors shown
- Generic "compilation failed" message

**Solutions:**

1. Run compile command manually (based on your stack):
   ```bash
   # Maven (Kotlin/Java)
   mvn clean compile

   # Gradle (Kotlin/Java)
   ./gradlew compileKotlin

   # TypeScript/npm
   npm run build

   # Python
   python -m py_compile src/main.py

   # Go
   go build ./...

   # Rust
   cargo build
   ```

2. Check if Python 3 is available:
   ```bash
   python3 --version
   ```

### Tests Not Running in Phase 4

**Symptoms:**
- Compile works but tests don't run
- Test results not showing

**Solutions:**

1. Run test command manually (based on your stack):
   ```bash
   # Maven (Kotlin/Java)
   mvn test

   # Gradle (Kotlin/Java)
   ./gradlew test

   # TypeScript/npm
   npm test

   # Python/pytest
   python -m pytest

   # Go
   go test ./...

   # Rust
   cargo test
   ```

2. Verify Waypoints phase is 4:
   ```bash
   # Check session-scoped phase file
   cat ~/.claude/tmp/wp-*/wp-phase
   ```

## Logging

Claude Waypoints logs all activity for debugging and auditing. Both CLI and Supervisor modes write to the same unified location.

### Log Locations

```
~/.claude/waypoints/logs/
├── sessions/
│   ├── 2026-01-16-<session-id>.log         # CLI session logs
│   └── 2026-01-16-supervisor-<id>.log      # Supervisor session logs
├── 2026-01-16.log                          # Daily aggregated log
└── current.log                              # Symlink to active session
```

**Supervisor mode also writes to:**
```
~/.claude/tmp/wp-supervisor-<workflow-id>/workflow.log   # Per-workflow log
```

### Log Categories

- `WP` - Phase transitions and workflow events
- `BUILD` - Compilation/test commands and results
- `PHASE` - Phase start/complete events (supervisor)
- `HOOK` - Hook registration events
- `TOOL` - Tool usage (supervisor)
- `SESSION` - Session start/end events
- `ERROR` - Errors and failures

### View Recent Logs

```bash
# View current session log
cat ~/.claude/waypoints/logs/current.log

# View today's aggregated log (all sessions)
cat ~/.claude/waypoints/logs/$(date +%Y-%m-%d).log

# Search for Waypoints events
grep "\[WP\]" ~/.claude/waypoints/logs/current.log

# Search for build events
grep "\[BUILD\]" ~/.claude/waypoints/logs/current.log

# Search for errors
grep ERROR ~/.claude/waypoints/logs/current.log

# View supervisor workflow log
cat ~/.claude/tmp/wp-supervisor-*/workflow.log
```

### Common Log Patterns

**Successful phase transition:**
```
[2025-01-02 10:30:15] [WP] Phase 1 -> 2: Requirements confirmed, advancing to Interfaces
```

**Blocked operation:**
```
[2025-01-02 10:30:20] [WP] Phase 1: Blocked - requirements not confirmed
```

**Build failure:**
```
[2025-01-02 10:30:25] [BUILD] FAILED - Compilation errors in src/main/Service.java
```

## Reinstallation

If all else fails, reinstall:

```bash
# Uninstall
~/.claude/waypoints/uninstall.sh

# Clean up any remaining files
rm -rf ~/.claude/waypoints
rm -rf ~/.claude/tmp/wp-start-*

# Reinstall (using curl)
curl -fsSL https://raw.githubusercontent.com/PetarMatan/claude-waypoints/main/install.sh | bash
```

## Getting Help

1. Check the [README](../README.md) for basic usage
2. Review [Architecture](architecture.md) for system design
3. Open an issue on GitHub with:
   - Your OS and Claude Code version
   - Contents of `~/.claude/logs/current.log`
   - Output of `ls -la ~/.claude/waypoints/`
   - Your `~/.claude/settings.json` (redact sensitive info)
