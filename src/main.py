#!/usr/bin/env python3
"""Claude Context Patcher - CLI entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .searcher import find_claude, ClaudeLocation
from .patcher import apply_patch, check_status, restore_backup


def select_location(locations: list[ClaudeLocation]) -> ClaudeLocation | None:
    """Interactive location selection."""
    if not locations:
        return None

    if len(locations) == 1:
        loc = locations[0]
        response = input(
            f"Found Claude Code at {loc.path} (version: {loc.version})\n"
            f"Patch this installation? [y/N] "
        ).strip().lower()
        return loc if response == 'y' else None

    print("Found multiple Claude Code installations:")
    for i, loc in enumerate(locations, 1):
        print(f"  [{i}] {loc.path} (version: {loc.version})")

    while True:
        response = input(f"Select installation to patch [1-{len(locations)}]: ").strip()
        try:
            idx = int(response) - 1
            if 0 <= idx < len(locations):
                return locations[idx]
        except ValueError:
            pass
        print(f"Invalid selection. Please enter a number between 1 and {len(locations)}.")


def cmd_check(location: Path, verbose: bool) -> int:
    """Check if binary is patched."""
    data = location.read_bytes()
    status, version = check_status(data)

    if verbose:
        print(f"Binary: {location}")
        print(f"Version: {version or 'unknown'}")
        print(f"Status: {status}")
    else:
        print(status if status != "unsupported" else f"unsupported (version: {version or 'unknown'})")

    return 0 if status == "patched" else 1


def cmd_patch(location: Path, auto: bool, dry_run: bool, backup: bool) -> int:
    """Apply patch to binary."""
    data = location.read_bytes()
    status, version = check_status(data)

    if status == "patched":
        print(f"Claude Code at {location} is already patched (v{version}).")
        return 0

    if status == "unsupported":
        print(f"Error: Unsupported Claude Code version at {location}", file=sys.stderr)
        print(f"Detected version: {version or 'unknown'}", file=sys.stderr)
        print("Supported versions: 2.1.126, 2.1.132", file=sys.stderr)
        return 1

    if dry_run:
        result = apply_patch(location, backup=backup, dry_run=True)
        print(f"Dry run: would patch {location}")
        print(f"  Before: {result.counts_before}")
        print(f"  After: {result.counts_after}")
        return 0

    if not auto:
        response = input(f"Patch {location}? [y/N] ").strip().lower()
        if response != 'y':
            print("Aborted.")
            return 1

    result = apply_patch(location, backup=backup, dry_run=False)
    print(f"Patched successfully: {location}")
    print(f"  Before: gate_old={result.counts_before['gate_old']}, "
          f"context_old={result.counts_before['context_old']}")
    print(f"  After: gate_new={result.counts_after['gate_new']}, "
          f"context_new={result.counts_after['context_new']}")

    print("\nRemember to restart Claude Code to use the patched binary.")
    return 0


def cmd_restore(location: Path) -> int:
    """Restore binary from backup."""
    if restore_backup(location):
        print("Restore successful. Please restart Claude Code.")
        return 0
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Claude Context Patcher - Auto-patch Claude Code binary",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --check              Check if Claude Code is patched
  %(prog)s --auto               Auto-search and patch first found
  %(prog)s --dry-run            Show what would be patched
  %(prog)s --restore            Restore from backup
  %(prog)s /path/to/claude     Patch specific binary
        """
    )

    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=None,
        help="Path to Claude Code binary (auto-search if not specified)"
    )
    parser.add_argument("--auto", action="store_true", help="Auto-select first found installation")
    parser.add_argument("--check", action="store_true", help="Check patch status")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be patched")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup creation")
    parser.add_argument("--restore", action="store_true", help="Restore from backup")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Find Claude Code binary
    if args.path:
        location = args.path
        if not location.exists():
            print(f"Error: File not found: {location}", file=sys.stderr)
            return 2
    else:
        locations = find_claude(verbose=args.verbose)
        if not locations:
            print("Error: Claude Code not found in any of the searched locations.",
                  file=sys.stderr)
            return 2

        if args.auto and len(locations) == 1:
            location = locations[0].path
        elif args.check or args.restore:
            location = locations[0].path
        else:
            selected = select_location(locations)
            if not selected:
                print("No installation selected. Exiting.")
                return 1
            location = selected.path

    # Execute command
    if args.check:
        return cmd_check(location, args.verbose)
    elif args.restore:
        return cmd_restore(location)
    else:
        return cmd_patch(location, args.auto, args.dry_run, backup=not args.no_backup)


if __name__ == "__main__":
    raise SystemExit(main())
