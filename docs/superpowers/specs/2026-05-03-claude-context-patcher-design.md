# Claude Context Patcher 设计文档

**日期**: 2026-05-03

## 概述

创建一个命令行工具，自动搜索并修补 Claude Code 2.1.126 原生二进制文件，解锁自定义 provider 功能和扩展上下文窗口。配合 claude-hud 插件实现上下文显示和计算校正。

## 核心功能

### 1. 自动搜索

工具在以下位置搜索 Claude Code 可执行文件：

```python
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
    # nvm/node 全局
    "~/.nvm/versions/node/*/bin/claude",
    # 系统路径
    "/usr/bin/claude",
    "/usr/local/bin/claude",
    # Windows
    "%LOCALAPPDATA%\\Programs\\Claude\\Claude.exe",
    "~/AppData/Local/Programs/Claude/Claude.exe",
]
```

### 2. 工作模式

| 模式 | 说明 |
|------|------|
| `--auto` | 自动选择第一个有效候选并修补 |
| `--dry-run` | 仅检查不修补，显示候选列表 |
| `--check` | 验证当前二进制是否已修补 |
| `--verbose` | 详细输出 |

### 3. 交互模式

- 找到多个候选时让用户选择
- 显示每个候选的版本信息
- 提供确认提示后才执行修补

### 4. 回滚支持

- 自动备份原始二进制到 `<binary>.bak`
- 提供 `--restore` 选项恢复备份

## 目录结构

```
claude-context-patcher/
├── README.md              # 包含完整使用指南和 claude-hud 安装步骤
├── src/
│   ├── __init__.py
│   ├── main.py            # CLI 入口
│   ├── searcher.py        # 搜索逻辑
│   ├── patcher.py         # 修补逻辑（复用原脚本）
│   └── installer.py       # 安装脚本生成
├── scripts/
│   └── patch.sh           # 一键修补脚本
├── Makefile               # 构建/安装
└── requirements.txt       # Python 依赖
```

## 修补内容

脚本修改 Claude Code 二进制文件中的两个模式：

1. **能力门控**: `function H7K(){return!1}` → `function H7K(){return!0}`
   - 启用自定义 provider 的 /v1/models 支持

2. **上下文查找**: 替换上下文窗口计算逻辑
   - 改为从 provider 的 `max_input_tokens` 读取
   - 仅当 >= 100000 时返回

## README 内容要求

1. 项目简介
2. 自动搜索机制说明
3. 快速开始
4. 使用示例
5. **claude-hud 插件安装步骤**（重点部分）
   - 如何启用 HUD 显示上下文
   - 配置说明
6. 回滚方法
7. 常见问题

## 依赖

- Python 3.8+
- 无需额外依赖（纯标准库）