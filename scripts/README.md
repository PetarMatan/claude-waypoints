# Scripts

Automation scripts for Waypoints development and releases.

## Release Script

**Usage**: `./scripts/release.sh <version>`

Automates the complete release process:

```bash
# Example: Release version 1.3.1
./scripts/release.sh 1.3.1
```

### What it does

1. ✅ **Validates** version format (X.Y.Z) and git state
2. ✅ **Updates** VERSION in install.sh to tagged version (e.g., "v1.3.1")
3. ✅ **Updates** CHANGELOG.md date (if TBD)
4. ✅ **Commits** release changes
5. ✅ **Tags** the release (e.g., v1.3.1)
6. ✅ **Pushes** tag to GitHub
7. ✅ **Creates** GitHub release with notes extracted from CHANGELOG
8. ✅ **Reverts** VERSION to "main" for continued development
9. ✅ **Commits** and pushes the revert

### Prerequisites

- Must be on `main` branch
- Working directory must be clean
- Local branch must be up to date with remote
- Tag must not already exist
- `gh` CLI must be installed and authenticated

### Result

After running, users can install the specific version:

```bash
# Install specific version
curl -fsSL https://raw.githubusercontent.com/PetarMatan/claude-waypoints/v1.3.1/install.sh | bash

# Or install latest (main)
curl -fsSL https://raw.githubusercontent.com/PetarMatan/claude-waypoints/main/install.sh | bash
```

Each tagged version has `VERSION="vX.Y.Z"` hardcoded in its install.sh, while main always has `VERSION="main"`.
