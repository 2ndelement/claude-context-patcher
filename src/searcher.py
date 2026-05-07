#!/usr/bin/env python3
"""Auto-search for Claude Code installations."""

from __future__ import annotations

import glob
import os
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


SEARCH_PATHS = [
    # npm global (Linux)
    "/usr/local/lib/node_modules/@anthropic-ai/claude/claude",
    "/usr/lib/node_modules/@anthropic-ai/claude/claude",
    # Homebrew (macOS)
    "/usr/local/bin/claude",
    "/opt/homebrew/bin/claude",
    # User npm global
    "~/.npm-global/bin/claude",
    "~/.local/bin/claude",
    # nvm
    "~/.nvm/versions/node/*/bin/claude",
    # System paths
    "/usr/bin/claude",
    "/usr/local/bin/claude",
]

WINDOWS_PATHS = [
    "%LOCALAPPDATA%\\Programs\\Claude\\Claude.exe",
    "~/AppData/Local/Programs/Claude/Claude.exe",
]


@dataclass
class ClaudeLocation:
    """Represents a found Claude Code installation."""
    path: Path
    version: str = "unknown"

    def __repr__(self) -> str:
        return f"ClaudeLocation(path={self.path}, version={self.version})"


def expand_path(path_str: str) -> Path | None:
    """Expand environment variables and ~ in path."""
    expanded = os.path.expandvars(os.path.expanduser(path_str))
    if expanded == path_str:
        return None
    return Path(expanded)


def get_version(binary_path: Path) -> str:
    """Get Claude Code version by running --version."""
    try:
        result = os.popen(f'"{binary_path}" --version 2>&1').read().strip()
        if not result:
            return "unknown"
        return result.split("\n")[0]
    except Exception:
        return "unknown"


def is_valid_claude(binary_path: Path) -> bool:
    """Check if this is a valid Claude Code binary."""
    if not binary_path.exists():
        return False
    if not os.access(binary_path, os.X_OK):
        try:
            os.chmod(binary_path, 0o755)
        except Exception:
            return False
    return True


def search_claude() -> Iterator[ClaudeLocation]:
    """Search for Claude Code installations."""
    system = platform.system()
    paths_to_check = SEARCH_PATHS.copy()

    if system == "Windows":
        paths_to_check.extend(WINDOWS_PATHS)

    checked: set[Path] = set()

    for path_str in paths_to_check:
        if "*" in str(path_str):
            # Handle glob patterns
            expanded = expand_path(str(Path(path_str).parent))
            if expanded is None:
                continue
            pattern = Path(path_str).name
            if expanded.exists():
                for match in expanded.glob(pattern):
                    if match not in checked and is_valid_claude(match):
                        checked.add(match)
                        yield ClaudeLocation(match, get_version(match))
        else:
            path = expand_path(path_str)
            if path is None:
                continue
            if path not in checked and is_valid_claude(path):
                checked.add(path)
                yield ClaudeLocation(path, get_version(path))


def find_claude(verbose: bool = False) -> list[ClaudeLocation]:
    """Find all Claude Code installations."""
    locations = list(search_claude())

    if verbose:
        print(f"Searched {len(SEARCH_PATHS)} paths")
        print(f"Found {len(locations)} valid installation(s)")

    return locations
