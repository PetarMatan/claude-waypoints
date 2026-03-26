"""
Resolve shared module paths for hooks/lib imports.

The modules wp_agents, wp_config, wp_knowledge, and wp_state live in hooks/lib/
and are shared between CLI hooks (standalone scripts) and wp_supervisor (package).

This module adds the correct path to sys.path so bare imports work:
    from wp_agents import AgentLoader
    from wp_knowledge import KnowledgeManager

Path resolution order:
1. Already importable (pip install -e . or already on sys.path) — no action needed
2. Relative to this file: ../../hooks/lib (repo layout or install script layout)
3. WP_INSTALL_DIR environment variable (set by bin/wp-supervisor script)
"""

import os
import sys
from pathlib import Path


def _find_hooks_lib() -> str | None:
    """Find hooks/lib directory. Returns path or None."""
    # Relative to this file: wp_supervisor/_paths.py → ../../hooks/lib
    relative = Path(__file__).parent.parent / "hooks" / "lib"
    if relative.is_dir() and (relative / "wp_agents.py").exists():
        return str(relative)

    # From WP_INSTALL_DIR environment variable
    install_dir = os.environ.get("WP_INSTALL_DIR")
    if install_dir:
        env_path = Path(install_dir) / "hooks" / "lib"
        if env_path.is_dir() and (env_path / "wp_agents.py").exists():
            return str(env_path)

    return None


def ensure_hooks_lib_importable() -> None:
    """Add hooks/lib to sys.path if needed. Call once at package init."""
    # Already importable?
    try:
        import wp_agents  # noqa: F401
        return
    except ImportError:
        pass

    hooks_lib = _find_hooks_lib()
    if hooks_lib and hooks_lib not in sys.path:
        sys.path.insert(0, hooks_lib)


# Run on import
ensure_hooks_lib_importable()
