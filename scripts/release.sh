#!/bin/bash
set -e

# Waypoints Release Automation Script
#
# Usage:
#   ./scripts/release.sh 1.3.1
#   ./scripts/release.sh 1.4.0
#
# This script:
# 1. Validates version format and git state
# 2. Updates VERSION in install.sh to tagged version
# 3. Updates CHANGELOG.md date (if TBD)
# 4. Commits and tags the release
# 5. Pushes tag and creates GitHub release
# 6. Reverts VERSION to "main" for continued development
# 7. Pushes the revert commit

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
error() {
    echo -e "${RED}Error: $1${NC}" >&2
    exit 1
}

success() {
    echo -e "${GREEN}✓ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

info() {
    echo -e "$1"
}

# Validate arguments
if [[ $# -ne 1 ]]; then
    error "Usage: $0 <version>\nExample: $0 1.3.1"
fi

VERSION_NUMBER="$1"
VERSION_TAG="v${VERSION_NUMBER}"

# Validate version format (X.Y.Z)
if ! [[ "$VERSION_NUMBER" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    error "Invalid version format. Expected: X.Y.Z (e.g., 1.3.1)"
fi

# Check we're in the repo root
if [[ ! -f "install.sh" ]] || [[ ! -f "CHANGELOG.md" ]]; then
    error "Must run from repository root"
fi

# Check we're on main branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [[ "$CURRENT_BRANCH" != "main" ]]; then
    error "Must be on main branch (currently on: $CURRENT_BRANCH)"
fi

# Check working directory is clean
if ! git diff-index --quiet HEAD --; then
    error "Working directory has uncommitted changes. Commit or stash them first."
fi

# Check we're up to date with remote
git fetch origin
if [[ $(git rev-parse HEAD) != $(git rev-parse @{u}) ]]; then
    error "Local branch is not up to date with remote. Run 'git pull' first."
fi

# Check tag doesn't already exist
if git rev-parse "$VERSION_TAG" >/dev/null 2>&1; then
    error "Tag $VERSION_TAG already exists"
fi

# Check gh CLI is installed
if ! command -v gh &> /dev/null; then
    error "gh CLI is not installed. Install from: https://cli.github.com/"
fi

info "════════════════════════════════════════════════════════════════"
info "  Waypoints Release: $VERSION_TAG"
info "════════════════════════════════════════════════════════════════"
info ""

# Step 1: Update VERSION in install.sh
info "Step 1: Updating VERSION in install.sh..."
sed -i.bak "s/^VERSION=.*$/VERSION=\"$VERSION_TAG\"/" install.sh
rm install.sh.bak
success "Updated VERSION to $VERSION_TAG"

# Step 2: Update CHANGELOG.md date if TBD
info "Step 2: Checking CHANGELOG.md..."
TODAY=$(date +%Y-%m-%d)
if grep -q "\[$VERSION_NUMBER\] - TBD" CHANGELOG.md; then
    sed -i.bak "s/\[$VERSION_NUMBER\] - TBD/[$VERSION_NUMBER] - $TODAY/" CHANGELOG.md
    rm CHANGELOG.md.bak
    success "Updated CHANGELOG date to $TODAY"
else
    warning "CHANGELOG already has a date (not TBD)"
fi

# Verify CHANGELOG has entry for this version
if ! grep -q "## \[$VERSION_NUMBER\]" CHANGELOG.md; then
    error "CHANGELOG.md does not have an entry for [$VERSION_NUMBER]"
fi

# Step 3: Commit the release
info "Step 3: Creating release commit..."
git add install.sh CHANGELOG.md
git commit -m "Release $VERSION_TAG"
success "Created release commit"

# Step 4: Create and push tag
info "Step 4: Creating git tag..."
git tag "$VERSION_TAG"
success "Created tag $VERSION_TAG"

info "Step 5: Pushing commit and tag..."
git push origin main
git push origin "$VERSION_TAG"
success "Pushed commit and tag to GitHub"

# Step 6: Extract release notes from CHANGELOG
info "Step 6: Extracting release notes from CHANGELOG..."
RELEASE_NOTES_FILE="/tmp/waypoints-release-notes-$VERSION_NUMBER.md"

# Extract the section for this version from CHANGELOG
awk "/## \[$VERSION_NUMBER\]/,/## \[/" CHANGELOG.md | \
    sed '/## \['"$VERSION_NUMBER"'\]/d' | \
    sed '/## \[/,$d' | \
    sed '/^$/N;/^\n$/D' > "$RELEASE_NOTES_FILE"

# Add installation instructions
cat >> "$RELEASE_NOTES_FILE" << EOF

## 📦 Installation

\`\`\`bash
# Install from this release
curl -fsSL https://raw.githubusercontent.com/PetarMatan/claude-waypoints/$VERSION_TAG/install.sh | bash

# Or install latest
curl -fsSL https://raw.githubusercontent.com/PetarMatan/claude-waypoints/main/install.sh | bash
\`\`\`

For Supervisor mode (parallel exploration):
\`\`\`bash
pip install claude-agent-sdk
wp-supervisor
\`\`\`

---

**Full Changelog**: https://github.com/PetarMatan/claude-waypoints/blob/main/CHANGELOG.md
EOF

success "Generated release notes"

# Step 7: Create GitHub release
info "Step 7: Creating GitHub release..."
gh release create "$VERSION_TAG" \
    --title "$VERSION_TAG" \
    --notes-file "$RELEASE_NOTES_FILE" \
    --target main

RELEASE_URL=$(gh release view "$VERSION_TAG" --json url -q .url)
success "Created GitHub release: $RELEASE_URL"

# Step 8: Revert VERSION to "main" for continued development
info "Step 8: Reverting VERSION to 'main' for development..."
sed -i.bak 's/^VERSION=.*$/VERSION="main"/' install.sh
rm install.sh.bak
success "Reverted VERSION to main"

# Step 9: Commit and push the revert
info "Step 9: Committing revert..."
git add install.sh
git commit -m "Revert installer to main for development"
git push origin main
success "Pushed revert commit"

# Cleanup
rm -f "$RELEASE_NOTES_FILE"

info ""
info "════════════════════════════════════════════════════════════════"
success "Release $VERSION_TAG completed successfully!"
info "════════════════════════════════════════════════════════════════"
info ""
info "📦 Release URL: $RELEASE_URL"
info ""
info "Users can now install this version with:"
info "  curl -fsSL https://raw.githubusercontent.com/PetarMatan/claude-waypoints/$VERSION_TAG/install.sh | bash"
info ""
