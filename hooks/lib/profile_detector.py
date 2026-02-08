#!/usr/bin/env python3
"""
Waypoints Workflow - Profile Detector
Detects technology profile based on project files and configuration.

Usage:
    from profile_detector import get_override, detect_profile
    profile = get_override("~/.claude/wp-override.json")
    profile = detect_profile("/path/to/project", "config.json")
"""

import json
import os
from pathlib import Path


def get_override(override_file: str) -> str:
    """Read activeProfile from override file. Returns profile name or empty string."""
    try:
        with open(override_file, 'r') as f:
            profile = json.load(f).get('activeProfile', '')
            return profile or ''
    except Exception:
        return ''


def detect_profile(project_dir: str, config_file: str) -> str:
    """Auto-detect profile based on project files. Returns profile name or empty string."""
    project_path = Path(project_dir).resolve()

    try:
        with open(config_file, 'r') as f:
            config = json.load(f)

        profiles = config.get('profiles', {})

        # Score each profile based on detection criteria
        scores = {}
        for profile_name, profile in profiles.items():
            detection = profile.get('detection', {})
            files = detection.get('files', [])
            patterns = detection.get('patterns', [])

            score = 0

            # Check for detection files
            for f in files:
                if (project_path / f).exists():
                    score += 10

            # Check for source patterns (simplified glob check)
            for pattern in patterns:
                # Convert glob to simple check
                ext = pattern.split('*')[-1] if '*' in pattern else pattern
                pattern_matched = False
                for root, dirs, filenames in os.walk(project_path):
                    for filename in filenames:
                        if filename.endswith(ext):
                            score += 1
                            pattern_matched = True
                            break
                    if pattern_matched:
                        break

            if score > 0:
                scores[profile_name] = score

        # Return highest scoring profile, but only if unambiguous
        if scores:
            max_score = max(scores.values())
            # If no profile has a detection file match (score >= 10),
            # all matches are pattern-only. If multiple profiles tie,
            # the repo is ambiguous — return no profile rather than guessing.
            if max_score < 10:
                top_profiles = [p for p, s in scores.items() if s == max_score]
                if len(top_profiles) > 1:
                    return ''
            return max(scores, key=scores.get)
        return ''
    except Exception:
        return ''


