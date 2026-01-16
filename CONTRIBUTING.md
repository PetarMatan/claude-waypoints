# Contributing to Claude Waypoints

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## How to Contribute

### Reporting Issues

1. Check existing issues to avoid duplicates
2. Use the issue template if provided
3. Include:
   - OS and Claude Code version
   - Steps to reproduce
   - Expected vs actual behavior
   - Relevant log output (`~/.claude/waypoints/logs/current.log`)

### Suggesting Features

1. Open an issue with `[Feature]` prefix
2. Describe the use case and benefit
3. Consider implementation complexity

### Pull Requests

1. Create a feature branch from main: `git checkout -b feature/my-feature`
2. Make your changes
3. Test thoroughly
4. Commit with clear messages
5. Push and create a PR to main

## Development Setup

```bash
# Clone the repository
git clone https://github.com/PetarMatan/claude-waypoints.git
cd claude-waypoints

# Create a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate
pip install pytest

# Run tests
python3 -m pytest tests/unit/python/ -v

# Test hooks locally
export WP_INSTALL_DIR="$(pwd)"
python3 hooks/wp-orchestrator.py < test-input.json
```

## Code Guidelines

### Shell Scripts

- Use `#!/bin/bash` shebang
- Set `set -e` for error handling
- Source shared libraries from `lib/`
- Add version comment at top
- Use lowercase variable names with underscores
- Quote all variables: `"$variable"`

### JSON Configuration

- Use 2-space indentation
- Include `$schema` reference where applicable
- Document new fields in README

### Markdown

- Use ATX-style headers (`#`)
- Include code language in fenced blocks
- Keep lines under 100 characters

## Testing

### Manual Testing

1. Install locally: `./install.sh`
2. Start Claude Code
3. Run `/wp-start` and verify each phase
4. Test with different project types

### Test Script (Future)

```bash
# When bats tests are added
bats tests/hooks/
```

## Pull Request Checklist

- [ ] Code follows project style
- [ ] Changes are documented
- [ ] CHANGELOG.md updated (for features/fixes)
- [ ] Manual testing performed
- [ ] No sensitive data committed

## Code of Conduct

- Be respectful and constructive
- Welcome newcomers
- Focus on technical merit

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
