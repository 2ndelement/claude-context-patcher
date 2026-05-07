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

# 2.1.132 变体：使用 F1K 作为 gate（控制 g1K 能否获取模型信息）
GATE_OLD_132_ALT = b"function F1K(){return!1}"
GATE_NEW_132_ALT = b"function F1K(){return!0}"

CONTEXT_OLD_132 = (
    b"function TF$(H){if(Y8H())return null;if(uG(H))return null;"
    b"if(G4(H)!==\"claude-sonnet-4-6\")return null;"
    b"let $=R$().clientDataCache?.kelp_forest_sonnet;"
    b"if(typeof $!==\"string\")return null;"
    b"let q=parseInt($,10);if(!Number.isFinite(q)||q<=0)return null;return q}"
)

# 新版本：使用 g1K(H) 获取模型对象，直接从模型读取 max_input_tokens
CONTEXT_NEW_132 = (
    b"function TF$(H){let $=g1K(H)?.max_input_tokens;if(!$)return null;"
    b"let q=parseInt($,10);if(!Number.isFinite(q)||q<=0)return null;return q}"
)
# 填充到相同长度
_pad_len_132 = len(CONTEXT_OLD_132) - len(CONTEXT_NEW_132)
if _pad_len_132 > 0:
    CONTEXT_NEW_132 = (
        b"function TF$(H){let $=g1K(H)?.max_input_tokens;if(!$)return null;"
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


def get_gate_patterns(version: str) -> tuple[bytes, bytes]:
    """获取版本的 gate 模式（尝试多种变体）"""
    info = VERSIONS[version]
    # 2.1.132 有多种 gate 变体
    if version == "2.1.132":
        return (GATE_OLD_132, GATE_NEW_132)
    return (info.gate_old, info.gate_new)


def find_alt_gate(data: bytes, version: str) -> tuple[bytes, bytes] | None:
    """查找备选 gate 模式"""
    if version == "2.1.132":
        if GATE_OLD_132_ALT in data:
            return (GATE_OLD_132_ALT, GATE_NEW_132_ALT)
    return None


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

    # 检查已修补但使用了错误模式的版本 (R$().max_input_tokens 应改为 g1K(H)?.max_input_tokens)
    WRONG_CONTEXT_NEW_132 = (
        b"function TF$(H){let $=R$().max_input_tokens;if(!$)return null;"
        b"let q=parseInt($,10);if(!Number.isFinite(q)||q<=0)return null;return q}"
    )
    if WRONG_CONTEXT_NEW_132 in data:
        return "2.1.132"

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

    # 检查是否使用了错误模式的修补 (R$().max_input_tokens)
    WRONG_CONTEXT_NEW_132 = (
        b"function TF$(H){let $=R$().max_input_tokens;if(!$)return null;"
        b"let q=parseInt($,10);if(!Number.isFinite(q)||q<=0)return null;return q}"
    )
    wrong_context_count = data.count(WRONG_CONTEXT_NEW_132)

    # 检查备选 gate 模式 (F1K for 2.1.132)
    alt_gate = find_alt_gate(data, version)
    has_alt_gate = alt_gate and data.count(alt_gate[0]) == 2
    alt_gate_patched = alt_gate and data.count(alt_gate[1]) == 2

    # 检查是否已修补
    # 情况1：标准模式（context_new=2 且 gate 为已修补或无 gate）
    if counts["context_new"] == 2 and (counts["gate_new"] == 2 or counts["gate_new"] == 0):
        # 确保备选 gate 也已修补（如果有）
        if has_alt_gate and not alt_gate_patched:
            return "patchable", version
        return "patched", version
    # 情况2：备选 gate 模式（F1K）- context 已修补且 alt gate 已修补
    if counts["context_new"] == 2 and alt_gate_patched:
        return "patched", version

    # 检查是否可修补（考虑备选 gate）
    if context_total == 2 and (gate_total == 2 or gate_total == 0):
        return "patchable", version
    if wrong_context_count >= 2:
        return "patchable", version
    if context_total == 2 and has_alt_gate:
        return "patchable", version
    if wrong_context_count >= 2 and has_alt_gate:
        return "patchable", version

    return "unsupported", version


def patch_binary(data: bytes, version: str) -> tuple[bytes, dict[str, int]]:
    """Apply patch to binary data for specific version."""
    info = VERSIONS[version]
    counts = count_patterns(data, info)

    gate_total = counts["gate_old"] + counts["gate_new"]
    context_total = counts["context_old"] + counts["context_new"]

    # 检查是否有错误模式的修补需要更正
    WRONG_CONTEXT_NEW_132 = (
        b"function TF$(H){let $=R$().max_input_tokens;if(!$)return null;"
        b"let q=parseInt($,10);if(!Number.isFinite(q)||q<=0)return null;return q}"
    )
    wrong_count = data.count(WRONG_CONTEXT_NEW_132)

    if wrong_count > 0:
        context_total = wrong_count

    # 对于 2.1.132，gate 可能不存在（已移除或重命名），尝试查找备选 gate
    if gate_total != 2 and gate_total != 0:
        alt_gate = find_alt_gate(data, version)
        if alt_gate and data.count(alt_gate[0]) == 2:
            gate_total = 2
            counts["gate_old"] = 2
            counts["gate_new"] = 0
        elif gate_total != 2 and gate_total != 0:
            raise ValueError(
                f"[{version}] expected 0 or 2 capability gate patterns, found {gate_total} "
                f"(old={counts['gate_old']}, new={counts['gate_new']})"
            )

    if context_total != 2:
        raise ValueError(
            f"[{version}] expected exactly 2 context lookup patterns, found {context_total} "
            f"(old={counts['context_old']}, new={counts['context_new']}, wrong={wrong_count})"
        )

    patched = data
    # 只修补存在的模式
    if counts["gate_old"] > 0:
        patched = patched.replace(info.gate_old, info.gate_new)
    # 处理备选 gate 模式 (F1K for 2.1.132)
    alt_gate = find_alt_gate(patched, version)
    if alt_gate and patched.count(alt_gate[0]) == 2:
        patched = patched.replace(alt_gate[0], alt_gate[1])
    if counts["context_old"] > 0:
        patched = patched.replace(info.context_old, info.context_new)
    # 更正错误模式的修补
    if wrong_count > 0:
        patched = patched.replace(WRONG_CONTEXT_NEW_132, info.context_new)
    return patched, counts


def apply_patch(src: Path, backup: bool = True, dry_run: bool = False) -> PatchResult:
    """Apply patch to Claude Code binary."""
    data = src.read_bytes()
    status, version = check_status(data)

    if version is None:
        raise ValueError(f"unsupported binary version at {src}")

    info = VERSIONS[version]
    counts_before = count_patterns(data, info)

    # 检查是否有错误模式的修补需要更正
    WRONG_CONTEXT_NEW_132 = (
        b"function TF$(H){let $=R$().max_input_tokens;if(!$)return null;"
        b"let q=parseInt($,10);if(!Number.isFinite(q)||q<=0)return null;return q}"
    )
    has_wrong_pattern = data.count(WRONG_CONTEXT_NEW_132) >= 2

    if status == "patched" and not has_wrong_pattern:
        return PatchResult(
            success=True,
            already_patched=True,
            version=version,
            counts_before=counts_before,
            counts_after=counts_before,
        )

    if status == "unsupported" and not has_wrong_pattern:
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