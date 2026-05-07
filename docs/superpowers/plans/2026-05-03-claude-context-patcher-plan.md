# Claude Context Patcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建自动搜索并修补 Claude Code 二进制的工具，配合 claude-hud 实现上下文显示

**Architecture:** 纯 Python CLI 工具，自动搜索常用路径找到 Claude Code 二进制，验证版本后修补，备份原文件

**Tech Stack:** Python 3.8+, 标准库（无外部依赖）

---

## 文件结构

```
claude-context-patcher/
├── README.md                    # 包含 claude-hud 安装指南
├── src/
│   ├── __init__.py
│   ├── main.py                  # CLI 入口
│   ├── searcher.py              # 搜索逻辑
│   ├── patcher.py               # 修补逻辑
│   └── installer.py             # 安装脚本生成
├── scripts/
│   └── patch.sh                 # 一键修补脚本
├── Makefile
├── requirements.txt
└── docs/
    └── superpowers/
        ├── specs/
        │   └── 2026-05-03-claude-context-patcher-design.md
        └── plans/
            └── 2026-05-03-claude-context-patcher-plan.md
```

---

## Task 1: 项目初始化

**Files:**
- Create: `requirements.txt`
- Create: `src/__init__.py`
- Create: `Makefile`

- [ ] **Step 1: 创建 requirements.txt**

```txt
# Claude Context Patcher
# No external dependencies - pure standard library
```

- [ ] **Step 2: 创建 src/__init__.py**

```python
"""Claude Context Patcher - Auto-patch Claude Code binary."""
__version__ = "1.0.0"
```

- [ ] **Step 3: 创建 Makefile**

```makefile
.PHONY: install patch check restore help

help:
	@echo "Claude Context Patcher"
	@echo ""
	@echo "Usage:"
	@echo "  make install    - Install the patcher"
	@echo "  make patch      - Search and patch Claude Code"
	@echo "  make check      - Check current patch status"
	@echo "  make restore    - Restore from backup"
	@echo "  make clean      - Remove backup files"

install:
	pip install -e .

patch:
	python -m src.main --auto

check:
	python -m src.main --check

restore:
	python -m src.main --restore

clean:
	rm -f *.bak
```

- [ ] **Step 4: 提交**

```bash
git add requirements.txt src/__init__.py Makefile
git commit -m "chore: initial project structure"
```

---

## Task 2: 搜索模块 (src/searcher.py)

**Files:**
- Create: `src/searcher.py`

- [ ] **Step 1: 编写搜索模块**

```python
#!/usr/bin/env python3
"""Auto-search for Claude Code installations."""

from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path
from typing import Iterator


# 搜索路径配置
SEARCH_PATHS = [
    # npm 全局安装 (Linux)
    "/usr/local/lib/node_modules/@anthropic-ai/claude/claude",
    "/usr/lib/node_modules/@anthropic-ai/claude/claude",
    # Homebrew (macOS)
    "/usr/local/bin/claude",
    "/opt/homebrew/bin/claude",
    # 用户 npm 全局
    "~/.npm-global/bin/claude",
    "~/.local/bin/claude",
    "~/.nvm/versions/node/*/bin/claude",
    # 系统路径
    "/usr/bin/claude",
    "/usr/local/bin/claude",
    # Windows
    "$LOCALAPPDATA\\Programs\\Claude\\Claude.exe",
]

WINDOWS_PATHS = [
    "%LOCALAPPDATA%\\Programs\\Claude\\Claude.exe",
    "~/AppData/Local/Programs/Claude/Claude.exe",
    "$LOCALAPPDATA/Programs/Claude/Claude.exe",
]


class ClaudeLocation:
    """Represents a found Claude Code installation."""

    def __init__(self, path: Path, version: str = "unknown"):
        self.path = path
        self.version = version

    def __repr__(self) -> str:
        return f"ClaudeLocation(path={self.path}, version={self.version})"


def expand_path(path_str: str) -> Path | None:
    """Expand environment variables and ~ in path."""
    expanded = os.path.expandvars(os.path.expanduser(path_str))
    if expanded == path_str:  # No expansion happened
        return None
    return Path(expanded)


def get_version(binary_path: Path) -> str:
    """Get Claude Code version by running --version."""
    try:
        result = os.popen(f'"{binary_path}" --version 2>&1').read().strip()
        if "version" in result.lower():
            return result
        return result.split("\n")[0] if result else "unknown"
    except Exception:
        return "unknown"


def is_valid_claude(binary_path: Path) -> bool:
    """Check if this is a valid Claude Code binary."""
    if not binary_path.exists():
        return False
    if not os.access(binary_path, os.X_OK):
        # Try to make it executable
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

    checked = set()

    for path_str in paths_to_check:
        path = expand_path(path_str)
        if path is None:
            continue

        # Handle glob patterns
        if "*" in str(path):
            parent = path.parent
            pattern = path.name
            if parent.exists():
                for match in parent.glob(pattern):
                    if match not in checked and is_valid_claude(match):
                        checked.add(match)
                        yield ClaudeLocation(match, get_version(match))
        else:
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
```

- [ ] **Step 2: 提交**

```bash
git add src/searcher.py
git commit -m "feat: add Claude Code searcher module"
```

---

## Task 3: 修补模块 (src/patcher.py)

**Files:**
- Create: `src/patcher.py`

- [ ] **Step 1: 编写修补模块（基于原脚本重构）**

```python
#!/usr/bin/env python3
"""Core patching logic for Claude Code binary."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple


# 修补模式
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
assert len(CONTEXT_OLD) == len(CONTEXT_NEW)


class PatchStatus(NamedTuple):
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


def apply_patch(src: Path, backup: bool = True, dry_run: bool = False) -> PatchStatus:
    """Apply patch to Claude Code binary."""
    data = src.read_bytes()
    counts_before = count_patterns(data)

    # Check current status
    status = check_status(data)

    if status == "patched":
        return PatchStatus(
            success=True,
            already_patched=True,
            counts_before=counts_before,
            counts_after=counts_before,
        )

    if status == "unsupported":
        raise ValueError(f"unsupported binary version at {src}")

    # Apply patch
    patched, _ = patch_binary(data)

    if dry_run:
        return PatchStatus(
            success=True,
            already_patched=False,
            counts_before=counts_before,
            counts_after=count_patterns(patched),
        )

    # Create backup
    if backup:
        backup_path = src.with_name(src.name + ".bak")
        if not backup_path.exists():
            shutil.copy2(src, backup_path)
            print(f"Backup created: {backup_path}")

    # Write patched binary (handle "text file busy" on running binaries)
    if src == Path(sys.argv[0]) or os.getpid() in _get_pids_using_file(src):
        # Can't patch self, use temp file approach
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
    else:
        src.write_bytes(patched)

    return PatchStatus(
        success=True,
        already_patched=False,
        counts_before=counts_before,
        counts_after=count_patterns(patched),
    )


def _get_pids_using_file(path: Path) -> set[int]:
    """Get PIDs of processes using the given file (Linux only)."""
    try:
        import subprocess
        result = subprocess.run(
            ["lsof", "-t", str(path)],
            capture_output=True,
            text=True,
        )
        return {int(pid) for pid in result.stdout.strip().split("\n") if pid}
    except Exception:
        return set()


def restore_backup(binary_path: Path) -> bool:
    """Restore binary from backup."""
    backup_path = binary_path.with_name(binary_path.name + ".bak")
    if not backup_path.exists():
        print(f"No backup found at {backup_path}", file=sys.stderr)
        return False

    shutil.copy2(backup_path, binary_path)
    print(f"Restored from: {backup_path}")
    return True
```

- [ ] **Step 2: 提交**

```bash
git add src/patcher.py
git commit -m "feat: add core patching module"
```

---

## Task 4: CLI 主模块 (src/main.py)

**Files:**
- Create: `src/main.py`

- [ ] **Step 1: 编写 CLI 模块**

```python
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
        response = input(f"Found Claude Code at {loc.path} (version: {loc.version})\n"
                        f"Patch this installation? [y/N] ").strip().lower()
        return loc if response == 'y' else None

    print("Found multiple Claude Code installations:")
    for i, loc in enumerate(locations, 1):
        print(f"  [{i}] {loc.path} (version: {loc.version})")

    while True:
        response = input("Select installation to patch [1-{}]: ".format(len(locations))).strip()
        try:
            idx = int(response) - 1
            if 0 <= idx < len(locations):
                return locations[idx]
        except ValueError:
            pass
        print("Invalid selection. Please enter a number between 1 and {}.".format(len(locations)))


def cmd_check(location: Path, verbose: bool) -> int:
    """Check if binary is patched."""
    data = location.read_bytes()
    status = check_status(data)

    if verbose:
        print(f"Binary: {location}")
        print(f"Status: {status}")
    else:
        print(status)

    return 0 if status == "patched" else 1


def cmd_patch(location: Path, auto: bool, dry_run: bool, backup: bool) -> int:
    """Apply patch to binary."""
    data = location.read_bytes()
    status = check_status(data)

    if status == "patched":
        print(f"Claude Code at {location} is already patched.")
        return 0

    if status == "unsupported":
        print(f"Error: Unsupported Claude Code version at {location}", file=sys.stderr)
        print("This patcher only supports Claude Code 2.1.126", file=sys.stderr)
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
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-select first found installation"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check patch status"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be patched without making changes"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backup creation"
    )
    parser.add_argument(
        "--restore",
        action="store_true",
        help="Restore from backup"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )

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
            print("\nSearched paths:")
            for p in [
                "/usr/local/lib/node_modules/@anthropic-ai/claude/claude",
                "/usr/local/bin/claude",
                "~/.local/bin/claude",
            ]:
                print(f"  - {p}")
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
```

- [ ] **Step 2: 提交**

```bash
git add src/main.py
git commit -m "feat: add CLI entry point"
```

---

## Task 5: 安装脚本 (scripts/patch.sh 和 src/installer.py)

**Files:**
- Create: `scripts/patch.sh`
- Create: `src/installer.py`

- [ ] **Step 1: 创建 scripts/patch.sh**

```bash
#!/bin/bash
# Claude Context Patcher - One-liner patch script
# Usage: curl -sSL https://.../patch.sh | bash

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Claude Context Patcher"
echo "====================="
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed."
    exit 1
fi

# Run the patcher
echo "Searching for Claude Code installation..."
python3 -m src.main --auto

echo ""
echo "Done! Please restart Claude Code."
```

- [ ] **Step 2: 创建 src/installer.py**

```python
#!/usr/bin/env python3
"""Generate shell installer script."""

from __future__ import annotations

import sys
from pathlib import Path


INSTALLER_TEMPLATE = '''#!/bin/bash
# Claude Context Patcher Installer
# Version: {version}

set -e

INSTALL_DIR="{{install_dir}}"

echo "Installing Claude Context Patcher to $INSTALL_DIR..."

# Clone or update repo
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull
else
    echo "Cloning repository..."
    git clone https://github.com/{{username}}/{{repo}}.git "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# Run patcher
echo ""
echo "Searching for Claude Code..."
python3 -m src.main --auto

echo ""
echo "Installation complete!"
echo "Run 'make' in $INSTALL_DIR for more commands."
'''

def generate_installer_script(
    username: str,
    repo: str,
    install_dir: str = "~/.claude-context-patcher",
    version: str = "1.0.0",
) -> str:
    """Generate installer script content."""
    return INSTALLER_TEMPLATE.format(
        version=version,
        install_dir=install_dir,
        username=username,
        repo=repo,
    )


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: python -m src.installer <github_username> <repo_name>")
        print("Example: python -m src.installer 2ndelement claude-context-patcher")
        return 1

    username = sys.argv[1]
    repo = sys.argv[2]

    script = generate_installer_script(username, repo)

    output_path = Path(__file__).parent.parent / "scripts" / "install.sh"
    output_path.write_text(script)
    output_path.chmod(0o755)

    print(f"Generated installer script: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: 提交**

```bash
git add scripts/patch.sh src/installer.py
chmod +x scripts/patch.sh
git commit -m "feat: add shell scripts and installer"
```

---

## Task 6: README.md（包含 claude-hud 安装指南）

**Files:**
- Create: `README.md`

- [ ] **Step 1: 编写 README.md**

```markdown
# Claude Context Patcher

自动搜索并修补 Claude Code 2.1.126 原生二进制文件，解锁自定义 provider 功能和扩展上下文窗口。

## 功能特性

- 自动搜索 Claude Code 常用安装位置
- 一键修补，无需手动指定路径
- 自动备份原始二进制
- 支持回滚恢复
- 配合 claude-hud 显示上下文信息

## 快速开始

### 安装

```bash
git clone https://github.com/YOUR_USERNAME/claude-context-patcher.git
cd claude-context-patcher
```

### 使用

```bash
# 搜索并修补（自动选择第一个找到的安装）
make patch

# 或使用 Python 直接运行
python -m src.main --auto

# 检查当前状态
python -m src.main --check

# 查看所有找到的安装
python -m src.main --dry-run

# 回滚恢复
python -m src.main --restore
```

## 自动搜索路径

工具会在以下位置自动搜索 Claude Code：

| 路径 | 平台 |
|------|------|
| `/usr/local/lib/node_modules/@anthropic-ai/claude/claude` | Linux (npm 全局) |
| `/usr/lib/node_modules/@anthropic-ai/claude/claude` | Linux (npm 全局) |
| `/usr/local/bin/claude` | macOS/Linux (Homebrew/npm) |
| `/opt/homebrew/bin/claude` | macOS (Apple Silicon) |
| `~/.local/bin/claude` | Linux (用户安装) |
| `~/.npm-global/bin/claude` | 通用 |
| `/usr/bin/claude` | Linux |
| `%LOCALAPPDATA%\Programs\Claude\Claude.exe` | Windows |

## Claude HUD 插件安装（完整上下文显示）

配合 claude-hud 插件可以实现：
- 实时显示当前上下文窗口大小
- Token 使用量计算与校正
- 剩余上下文容量提醒

### 步骤 1: 安装 Claude Code HUD

在 Claude Code 中运行以下命令：

```
/hud setup
```

或在设置中启用 HUD：

1. 打开 Claude Code 设置 (Settings)
2. 找到 HUD 相关选项
3. 启用 HUD 功能

### 步骤 2: 配置 HUD

创建配置文件 `~/.claude/settings.json`：

```json
{
  "hud": {
    "enabled": true,
    "position": "bottom",
    "show_context": true,
    "show_tokens": true
  }
}
```

### 步骤 3: 验证安装

```bash
# 检查 patch 状态
python -m src.main --check

# 启动 Claude Code
claude

# 在 Claude Code 中验证 HUD 是否显示
/hud status
```

## 常见问题

### Q: 为什么需要修补 Claude Code？

A: Claude Code 默认会对自定义 provider 施加限制。修补后可以：
- 启用完整的 /v1/models 支持
- 使用 provider 声明的 max_input_tokens 作为上下文窗口
- 获得更准确的上下文容量计算

### Q: 修补后需要重启 Claude Code 吗？

A: 是的，必须重启才能加载修补后的二进制文件。

### Q: 如何回滚？

```bash
# 使用本工具回滚
python -m src.main --restore

# 或手动恢复备份
cp ~/.local/bin/claude.bak ~/.local/bin/claude
```

### Q: 修补后更新 Claude Code 会失效吗？

A: 是的，npm update 会覆盖修补。需要重新运行 patch。

## 工作原理

本工具修改 Claude Code 二进制文件中的两个模式：

1. **能力门控**: `function H7K(){return!1}` → `function H7K(){return!0}`
   - 启用自定义 provider 的 /v1/models 支持

2. **上下文查找**: 替换上下文窗口计算逻辑
   - 改为从 provider 的 `max_input_tokens` 读取
   - 仅当 >= 100000 时返回

## License

MIT
```

- [ ] **Step 2: 提交**

```bash
git add README.md
git commit -m "docs: add README with claude-hud installation guide"
```

---

## Task 7: GitHub 上传

**Files:**
- Modify: 初始化 git repo（如果需要）
- Create: .gitignore

- [ ] **Step 1: 创建 .gitignore**

```gitignore
__pycache__/
*.pyc
*.pyo
*.bak
*.patching
.env
.venv/
venv/
*.egg-info/
dist/
build/
```

- [ ] **Step 2: 创建 GitHub 仓库并推送**

```bash
cd claude-context-patcher

# 初始化 git（如果尚未初始化）
git init
git add .
git commit -m "feat: initial release"

# 创建 GitHub 仓库
gh repo create claude-context-patcher --public --source=. --push

# 或手动创建
# gh repo create claude-context-patcher --public
# git remote add origin git@github.com:$(gh api user --jq .login)/claude-context-patcher.git
# git push -u origin main
```

---

## 实现顺序

1. Task 1: 项目初始化
2. Task 2: 搜索模块
3. Task 3: 修补模块
4. Task 4: CLI 主模块
5. Task 5: 安装脚本
6. Task 6: README.md
7. Task 7: GitHub 上传

---

**计划完成时间**: 约 30-45 分钟

**建议执行方式**: Subagent-Driven（推荐）或 Inline Execution