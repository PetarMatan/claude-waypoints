#!/usr/bin/env python3
"""
Waypoints Workflow - Configuration Reader

Library for reading values from JSON configuration files using dot-notation paths.
Used by wp_config.py to read profile settings.
"""

import json


def get_config_value(path: str, config_file: str):
    """Read a value from JSON config using dot-notation path. Returns the value or None."""
    parts = path.split('.')

    try:
        with open(config_file, 'r') as f:
            data = json.load(f)

        for part in parts:
            if isinstance(data, dict):
                data = data.get(part)
            else:
                return None

        return data
    except Exception:
        return None
