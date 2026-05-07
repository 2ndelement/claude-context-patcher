#!/usr/bin/env python3
"""Core patching logic for Claude Code binary."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


# Patch patterns
GATE_OLD = b"function H7K(){return!1}"
GATE_NEW = b"function H7K(){return!0}"

CONTEXT_OLD = (
    b"function eB$(H){if(G$H())return null;if(zG(H))return null;"
    b"if(e7(H)!==\"claude-sonnet-4-6\")return null;"
    b"let $=h$().clientDataCache?.kelp_forest_sonnet;"
    b"if(typeof $!==\"string\")return null;"
    b"let q=parseInt($,10);if(!Number.isFinite(q)||q<=0)return null;return q}"
)

_CONTEXT_BASE = b"function eB$(H){let $=$7K(H)?.max_input_tokens;return $>=1e5?$:null;"
_pad_len = len(CONTEXT_OLD) - len(_CONTEXT_BASE) - 1
if _pad_len < 4:
    raise RuntimeError("context patch replacement cannot be padded safely")
CONTEXT_NEW = _CONTEXT_BASE + b"/*" + b"x" * (_pad_len - 4) + b"*/" + b"}"
assert len(CONTEXT_OLD) == len(CONTEXT_NEW), "patch pattern length mismatch"


@dataclass
class PatchResult:
    """Result of patch operation."""
    success: bool
    already_patched: bool
    counts_before: dict[str, int]
    counts_after: dict[str, int]


def count_patterns(data: bytes) -> dict[str, int]:
    """Count occurrences of each pattern."""
    return {
        "gate_old": data.count(GATE_OLD),
        "gate_new": data.count(GATE_NEW),
        "context_old": data.count(CONTEXT_OLD),
        "context_new": data.count(CONTEXT_NEW),
    }


def check_status(data: bytes) -> str:
    """Check if binary is patched, patchable, or unsupported."""
    counts = count_patterns(data)

    gate_total = counts["gate_old"] + counts["gate_new"]
    context_total = counts["context_old"] + counts["context_new"]

    if counts["gate_new"] == 2 and counts["context_new"] == 2:
        return "patched"
    if gate_total == 2 and context_total == 2:
        return "patchable"
    return "unsupported"


def patch_binary(data: bytes) -> tuple[bytes, dict[str, int]]:
    """Apply patch to binary data."""
    counts = count_patterns(data)

    gate_total = counts["gate_old"] + counts["gate_new"]
    context_total = counts["context_old"] + counts["context_new"]

    if gate_total != 2:
        raise ValueError(
            f"expected exactly 2 capability gate patterns, found {gate_total} "
            f"(old={counts['gate_old']}, new={counts['gate_new']})"
        )
    if context_total != 2:
        raise ValueError(
            f"expected exactly 2 context lookup patterns, found {context_total} "
            f"(old={counts['context_old']}, new={counts['context_new']})"
        )

    patched = data.replace(GATE_OLD, GATE_NEW).replace(CONTEXT_OLD, CONTEXT_NEW)
    return patched, counts


def apply_patch(src: Path, backup: bool = True, dry_run: bool = False) -> PatchResult:
    """Apply patch to Claude Code binary."""
    data = src.read_bytes()
    counts_before = count_patterns(data)

    status = check_status(data)

    if status == "patched":
        return PatchResult(
            success=True,
            already_patched=True,
            counts_before=counts_before,
            counts_after=counts_before,
        )

    if status == "unsupported":
        raise ValueError(f"unsupported binary version at {src}")

    patched, _ = patch_binary(data)

    if dry_run:
        return PatchResult(
            success=True,
            already_patched=False,
            counts_before=counts_before,
            counts_after=count_patterns(patched),
        )

    if backup:
        backup_path = src.with_name(src.name + ".bak")
        if not backup_path.exists():
            shutil.copy2(src, backup_path)
            print(f"Backup created: {backup_path}")

    # Write patched binary (handle "text file busy" on running binaries)
    fd, tmp = tempfile.mkstemp(dir=str(src.parent), suffix=".patching")
    try:
        os.write(fd, patched)
        os.fchmod(fd, src.stat().st_mode)
        os.close(fd)
        os.replace(tmp, src)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

    return PatchResult(
        success=True,
        already_patched=False,
        counts_before=counts_before,
        counts_after=count_patterns(patched),
    )


def restore_backup(binary_path: Path) -> bool:
    """Restore binary from backup."""
    backup_path = binary_path.with_name(binary_path.name + ".bak")
    if not backup_path.exists():
        print(f"No backup found at {backup_path}", file=sys.stderr)
        return False

    shutil.copy2(backup_path, binary_path)
    print(f"Restored from: {backup_path}")
    return True
