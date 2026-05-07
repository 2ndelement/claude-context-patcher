# Claude Context Patcher

自动搜索并修补 Claude Code 2.1.126 原生二进制文件，解锁自定义 provider 功能和扩展上下文窗口。

## 功能特性

- **自动搜索** - 无需手动指定路径，自动查找 Claude Code 安装位置
- **一键修补** - 解锁自定义 provider 功能和扩展上下文窗口
- **安全备份** - 自动备份原始二进制文件
- **轻松回滚** - 一键恢复到修补前状态
- **完整上下文** - 配合 claude-hud 显示实时上下文信息

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/2ndelement/claude-context-patcher.git
cd claude-context-patcher
```

### 2. 运行修补

```bash
# 自动搜索并修补第一个找到的安装
make patch

# 或使用 Python 直接运行
python3 -m src.main --auto
```

### 3. 重启 Claude Code

修补完成后需要重启 Claude Code 以加载修补后的二进制文件。

## 使用命令

| 命令 | 说明 |
|------|------|
| `make patch` | 自动搜索并修补 |
| `make check` | 检查当前修补状态 |
| `make restore` | 从备份恢复 |
| `make clean` | 清理备份文件 |
| `make help` | 显示帮助信息 |

### 高级用法

```bash
# 查看所有找到的 Claude Code 安装
python3 -m src.main --dry-run

# 手动指定二进制路径
python3 -m src.main /usr/local/bin/claude

# 跳过备份（不推荐）
python3 -m src.main --no-backup

# 检查特定安装
python3 -m src.main --check /path/to/claude
```

## 自动搜索路径

工具会自动在以下位置搜索 Claude Code：

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
python3 -m src.main --check

# 启动 Claude Code
claude

# 在 Claude Code 中验证 HUD 是否显示
/hud status
```

## 工作原理

本工具修改 Claude Code 二进制文件中的两个模式：

### 1. 能力门控

```
原始: function H7K(){return!1}
修补: function H7K(){return!0}
```

这启用了自定义 provider 的 /v1/models 支持。

### 2. 上下文查找

原始代码仅支持 `claude-sonnet-4-6` 模型，修补后改为：
- 从 provider 的 `max_input_tokens` 读取上下文窗口大小
- 仅当 `max_input_tokens >= 100000` 时返回有效值

## 常见问题

### Q: 为什么需要修补 Claude Code？

A: Claude Code 默认会对自定义 provider 施加限制。修补后可以：
- 启用完整的 /v1/models 支持
- 使用 provider 声明的 max_input_tokens 作为上下文窗口
- 配合 HUD 获得更准确的上下文容量显示

### Q: 修补后需要重启 Claude Code 吗？

A: 是的，必须重启才能加载修补后的二进制文件。

### Q: 如何回滚？

```bash
# 使用本工具回滚（自动选择找到的第一个安装）
python3 -m src.main --restore

# 或手动恢复备份
cp ~/.local/bin/claude.bak ~/.local/bin/claude
```

### Q: 修补后更新 Claude Code 会失效吗？

A: 是的，npm update 会覆盖修补。需要重新运行 `make patch`。

### Q: 修补安全吗？

A: 工具会自动创建 `.bak` 备份文件，并支持一键回滚。从未安装过 Claude Code 的系统不受影响。

## 依赖

- Python 3.8+
- 无需额外依赖（纯标准库）

## License

MIT