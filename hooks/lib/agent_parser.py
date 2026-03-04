#!/usr/bin/env python3
"""
Waypoints Workflow - Agent Parser

Library for parsing agent markdown files with YAML frontmatter.
Used by wp_agents.py to load phase-bound agents.
"""

import json
import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

KNOWN_MODES = {'cli', 'supervisor'}


def parse_frontmatter(filepath: str) -> Optional[dict]:
    """Parse YAML frontmatter from markdown file."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()

        # Check for frontmatter delimiters
        if not content.startswith('---'):
            return None

        # Find end of frontmatter
        end_match = re.search(r'\n---\s*\n', content[3:])
        if not end_match:
            return None

        frontmatter = content[3:end_match.start() + 3]
        data = {}

        # Parse name
        name_match = re.search(r'name:\s*(.+)', frontmatter)
        if name_match:
            data['name'] = name_match.group(1).strip()

        # Parse phases: [1, 2, 3] or phases: [1,2,3]
        phases_match = re.search(r'phases:\s*\[([^\]]*)\]', frontmatter)
        if phases_match:
            phases_str = phases_match.group(1)
            data['phases'] = [int(p.strip()) for p in phases_str.split(',') if p.strip().isdigit()]

        # Parse mode: [cli, supervisor] or mode: [cli] (optional, omit for both)
        mode_match = re.search(r'mode:\s*\[([^\]]*)\]', frontmatter)
        if mode_match:
            modes_str = mode_match.group(1)
            modes = [m.strip().lower() for m in modes_str.split(',') if m.strip()]
            for m in modes:
                if m not in KNOWN_MODES:
                    logger.warning("Unrecognized mode '%s' in %s (known modes: %s)", m, filepath, ', '.join(sorted(KNOWN_MODES)))
            data['mode'] = modes

        return data if data else None
    except Exception:
        return None


def get_content_without_frontmatter(filepath: str) -> str:
    """Get markdown content without frontmatter."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()

        # Remove frontmatter if present
        if content.startswith('---'):
            end_match = re.search(r'\n---\s*\n', content[3:])
            if end_match:
                content = content[end_match.end() + 3:]

        return content
    except Exception:
        return ""


def get_phases_list(agent_file: str) -> list:
    """Get phases list. Returns list of phase numbers or empty list."""
    frontmatter = parse_frontmatter(agent_file)
    if frontmatter and 'phases' in frontmatter:
        return frontmatter['phases']
    return []


def get_agent_name(agent_file: str) -> str:
    """Get agent name. Returns name from frontmatter or derived from filename."""
    frontmatter = parse_frontmatter(agent_file)

    if frontmatter and 'name' in frontmatter:
        return frontmatter['name']
    else:
        # Fallback: derive from filename
        filename = os.path.basename(agent_file)
        return filename.replace('.md', '').replace('-', ' ').title()


def get_agent_content(agent_file: str) -> Optional[str]:
    """Get agent content without frontmatter. Returns content or None."""
    content = get_content_without_frontmatter(agent_file)
    return content if content else None


def list_agents_data(agents_dir: str) -> list:
    """Get list of agents with phase bindings. Returns list of dicts."""
    result = []

    if not os.path.isdir(agents_dir):
        return result

    for filename in os.listdir(agents_dir):
        if not filename.endswith('.md'):
            continue

        filepath = os.path.join(agents_dir, filename)
        if not os.path.isfile(filepath):
            continue

        frontmatter = parse_frontmatter(filepath)
        if frontmatter and 'phases' in frontmatter:
            name = frontmatter.get('name', filename.replace('.md', '').replace('-', ' ').title())
            agent_data = {
                'name': name,
                'file': filepath,
                'phases': frontmatter['phases']
            }
            if 'mode' in frontmatter:
                agent_data['mode'] = frontmatter['mode']
            result.append(agent_data)

    return result


def get_agents_for_phase(agents_dir: str, phase: int, mode: str = None) -> list:
    """Get agent file paths that match the given phase and optional mode filter.

    Args:
        agents_dir: Directory containing agent markdown files
        phase: Phase number to filter by
        mode: Optional mode filter ('cli' or 'supervisor'). If provided,
              excludes agents whose mode list doesn't include it. Agents
              without a mode field load in both modes.
    """
    result = []
    if not os.path.isdir(agents_dir):
        return result

    for filename in os.listdir(agents_dir):
        if not filename.endswith('.md'):
            continue

        filepath = os.path.join(agents_dir, filename)
        if not os.path.isfile(filepath):
            continue

        frontmatter = parse_frontmatter(filepath)
        if frontmatter and 'phases' in frontmatter:
            if phase in frontmatter['phases']:
                agent_modes = frontmatter.get('mode')
                if mode and agent_modes and mode not in agent_modes:
                    continue
                result.append(filepath)

    return result


def list_agents(agents_dir: str) -> str:
    """List all agents with phase bindings as JSON string."""
    result = list_agents_data(agents_dir)
    return json.dumps(result)
