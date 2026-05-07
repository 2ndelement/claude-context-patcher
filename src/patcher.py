#!/usr/bin/env python3
"""Core patching logic for Claude Code binary."""

from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


# =============================================================================
# 版本 2.1.126 的修补模式
# =============================================================================
GATE_OLD_126 = b"function H7K(){return!1}"
GATE_NEW_126 = b"function H7K(){return!0}"

CONTEXT_OLD_126 = (
    b"function eB$(H){if(G$H())return null;if(zG(H))return null;"
    b"if(e7(H)!==\"claude-sonnet-4-6\")return null;"
    b"let $=h$().clientDataCache?.kelp_forest_sonnet;"
    b"if(typeof $!==\"string\")return null;"
    b"let q=parseInt($,10);if(!Number.isFinite(q)||q<=0)return null;return q}"
)

_CONTEXT_BASE_126 = b"function eB$(H){let $=$7K(H)?.max_input_tokens;return $>=1e5?$:null;"
_pad_len_126 = len(CONTEXT_OLD_126) - len(_CONTEXT_BASE_126) - 1
if _pad_len_126 < 4:
    raise RuntimeError("126 context patch replacement cannot be padded safely")
CONTEXT_NEW_126 = _CONTEXT_BASE_126 + b"/*" + b"x" * (_pad_len_126 - 4) + b"*/" + b"}"
assert len(CONTEXT_OLD_126) == len(CONTEXT_NEW_126), "126 context patch pattern length mismatch"


# =============================================================================
# 版本 2.1.132 的修补模式
# =============================================================================
GATE_OLD_132 = b"function H7K(){return!1}"
GATE_NEW_132 = b"function H7K(){return!0}"

CONTEXT_OLD_132 = (
    b"function TF$(H){if(Y8H())return null;if(uG(H))return null;"
    b"if(G4(H)!==\"claude-sonnet-4-6\")return null;"
    b"let $=R$().clientDataCache?.kelp_forest_sonnet;"
    b"if(typeof $!==\"string\")return null;"
    b"let q=parseInt($,10);if(!Number.isFinite(q)||q<=0)return null;return q}"
)

# 新版本：移除 model 检查，直接使用 max_input_tokens
CONTEXT_NEW_132 = (
    b"function TF$(H){let $=R$().max_input_tokens;if(!$)return null;"
    b"let q=parseInt($,10);if(!Number.isFinite(q)||q<=0)return null;return q}"
)
# 填充到相同长度
_pad_len_132 = len(CONTEXT_OLD_132) - len(CONTEXT_NEW_132)
if _pad_len_132 > 0:
    CONTEXT_NEW_132 = (
        b"function TF$(H){let $=R$().max_input_tokens;if(!$)return null;"
        b"let q=parseInt($,10);if(!Number.isFinite(q)||q<=0)return null;return q}"
        b"/*" + b"x" * (_pad_len_132 - 4) + b"*/"
    )
assert len(CONTEXT_OLD_132) == len(CONTEXT_NEW_132), "132 context patch pattern length mismatch"


# =============================================================================
# 版本检测和选择
# =============================================================================
@dataclass
class VersionInfo:
    """版本修补信息"""
    gate_old: bytes
    gate_new: bytes
    context_old: bytes
    context_new: bytes


VERSIONS = {
    "2.1.126": VersionInfo(
        gate_old=GATE_OLD_126,
        gate_new=GATE_NEW_126,
        context_old=CONTEXT_OLD_126,
        context_new=CONTEXT_NEW_126,
    ),
    "2.1.132": VersionInfo(
        gate_old=GATE_OLD_132,
        gate_new=GATE_NEW_132,
        context_old=CONTEXT_OLD_132,
        context_new=CONTEXT_NEW_132,
    ),
}


def detect_version(data: bytes) -> str | None:
    """检测 Claude Code 版本"""
    # 先检查修补后的新模式（用于检测已修补的二进制）
    for version, info in VERSIONS.items():
        if info.context_new in data:
            return version

    # 再检查未修补的旧模式
    for version, info in VERSIONS.items():
        if info.context_old in data:
            return version

    return None


# =============================================================================
# 修补逻辑
# =============================================================================
@dataclass
class PatchResult:
    """Result of patch operation."""
    success: bool
    already_patched: bool
    version: str | None
    counts_before: dict[str, int]
    counts_after: dict[str, int]


def count_patterns(data: bytes, version_info: VersionInfo) -> dict[str, int]:
    """Count occurrences of each pattern for a specific version."""
    return {
        "gate_old": data.count(version_info.gate_old),
        "gate_new": data.count(version_info.gate_new),
        "context_old": data.count(version_info.context_old),
        "context_new": data.count(version_info.context_new),
    }


def check_status(data: bytes) -> tuple[str, str | None]:
    """
    Check if binary is patched, patchable, or unsupported.
    Returns: (status, version)
    """
    version = detect_version(data)
    if version is None:
        return "unsupported", None

    info = VERSIONS[version]
    counts = count_patterns(data, info)

    gate_total = counts["gate_old"] + counts["gate_new"]
    context_total = counts["context_old"] + counts["context_new"]

    # 检查是否已修补
    if counts["context_new"] == 2 and (counts["gate_new"] == 2 or counts["gate_new"] == 0):
        return "patched", version

    # 检查是否可修补
    if counts["context_old"] == 2 and (gate_total == 2 or gate_total == 0):
        return "patchable", version

    return "unsupported", version


def patch_binary(data: bytes, version: str) -> tuple[bytes, dict[str, int]]:
    """Apply patch to binary data for specific version."""
    info = VERSIONS[version]
    counts = count_patterns(data, info)

    gate_total = counts["gate_old"] + counts["gate_new"]
    context_total = counts["context_old"] + counts["context_new"]

    # 对于 2.1.132，gate 可能不存在（已移除或重命名）
    if gate_total != 2 and gate_total != 0:
        raise ValueError(
            f"[{version}] expected 0 or 2 capability gate patterns, found {gate_total} "
            f"(old={counts['gate_old']}, new={counts['gate_new']})"
        )
    if context_total != 2:
        raise ValueError(
            f"[{version}] expected exactly 2 context lookup patterns, found {context_total} "
            f"(old={counts['context_old']}, new={counts['context_new']})"
        )

    patched = data
    # 只修补存在的模式
    if counts["gate_old"] > 0:
        patched = patched.replace(info.gate_old, info.gate_new)
    if counts["context_old"] > 0:
        patched = patched.replace(info.context_old, info.context_new)
    return patched, counts


def apply_patch(src: Path, backup: bool = True, dry_run: bool = False) -> PatchResult:
    """Apply patch to Claude Code binary."""
    data = src.read_bytes()
    status, version = check_status(data)

    if version is None:
        raise ValueError(f"unsupported binary version at {src}")

    info = VERSIONS[version]
    counts_before = count_patterns(data, info)

    if status == "patched":
        return PatchResult(
            success=True,
            already_patched=True,
            version=version,
            counts_before=counts_before,
            counts_after=counts_before,
        )

    if status == "unsupported":
        raise ValueError(f"unsupported binary version at {src}")

    patched, _ = patch_binary(data, version)

    if dry_run:
        return PatchResult(
            success=True,
            already_patched=False,
            version=version,
            counts_before=counts_before,
            counts_after=count_patterns(patched, info),
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
        version=version,
        counts_before=counts_before,
        counts_after=count_patterns(patched, info),
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