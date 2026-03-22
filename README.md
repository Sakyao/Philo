# Philo 🐈

Philo 是一个基于 LLM 的 AI Agent 框架，设计为一个智能研究助手。它具备工具调用、记忆管理、技能扩展等核心能力，支持多渠道交互。

## ✨ 特性

- **ReAct 循环** - 实现经典的 Reasoning + Acting 模式，支持多轮工具调用
- **Function Calling** - 完整的工具注册、验证和执行机制
- **MCP 协议支持** - 集成 Model Context Protocol，可连接外部工具服务器
- **双层记忆系统** - 长期记忆 + 历史日志，支持自动记忆整合
- **技能系统** - 可扩展的技能模块，支持依赖声明和渐进式加载
- **多渠道支持** - CLI 交互式终端、飞书等即时通讯平台
- **会话持久化** - 自动保存会话历史，支持断点续聊
- **安全执行** - 命令执行有超时限制和危险命令过滤

## 📦 安装

```bash
# 克隆项目
git clone <repository-url>
cd philo

# 安装依赖
pip install -e .
```

## 🚀 快速开始

### 基本使用

```python
from philo.config.pconfig import PhiloConfig
from philo.agent.loop import PhiloLoop

# 创建配置
pcfg = PhiloConfig("default")
pcfg.workspace = "/path/to/workspace"
pcfg.llm = YourLlmBackend()  # 实现 PhiloLlmBase

# 初始化并运行
loop = PhiloLoop(pcfg)
response = await loop.processMessage(message)
```

### CLI 交互模式

```python
from philo.infra.engine.interactive import PhiloInteractiveEngine

engine = PhiloInteractiveEngine(pcfg)
await engine.runInteractive()
```

## 🏗️ 架构

```
philo/
├── agent/                 # Agent 核心
│   ├── loop.py           # 主循环 (ReAct)
│   ├── context.py        # 上下文构建
│   ├── memory.py         # 记忆管理
│   ├── toolmanager.py    # 工具管理
│   ├── mcpmanager.py     # MCP 协议管理
│   └── skillsloader.py   # 技能加载器
├── llm/                   # LLM 抽象层
│   ├── base.py           # 基类定义
│   └── openai.py         # OpenAI 实现
├── tools/                 # 内置工具
│   ├── base.py           # 工具基类
│   ├── exec.py           # 命令执行
│   ├── filesystem.py     # 文件操作
│   ├── message.py        # 消息发送
│   ├── websearch.py      # 网络搜索
│   └── mcp.py            # MCP 工具包装
├── infra/                 # 基础设施
│   ├── bus.py            # 消息总线
│   ├── session.py        # 会话管理
│   ├── cli.py            # CLI 界面
│   └── engine/           # 运行引擎
├── config/                # 配置管理
└── resources/             # 资源文件
    ├── skills/           # 内置技能
    └── yamls/            # 提示词模板
```

## 🔧 内置工具

| 工具名 | 描述 |
|--------|------|
| `exec` | 执行 shell 命令（有安全限制） |
| `read_file` | 读取文件内容 |
| `write_file` | 写入文件 |
| `list_dir` | 列出目录内容 |
| `edit_file` | 编辑文件（搜索替换） |
| `message` | 发送消息到指定渠道 |
| `web_search` | 网络搜索（博查 API） |
| `web_fetch` | 获取网页内容 |

## 🧠 记忆系统

Philo 实现了两层记忆架构：

### 长期记忆 (`MEMORY.md`)
存储重要事实和信息，跨会话持久化。

### 历史日志 (`HISTORY.md`)
记录事件和决策的时间线，支持 grep 搜索。

### 记忆整合
当未整合消息数超过阈值时，系统会自动：
1. 提取对话摘要
2. 更新长期记忆
3. 归档历史记录

## 🔌 MCP 协议

支持连接 MCP (Model Context Protocol) 服务器扩展能力：

```python
from philo.config.pconfig import McpEntry

# 配置 MCP 服务器
mcpEntry = McpEntry(
    name="my-server",
    transportType="stdio",  # 或 "sse", "streamableHttp"
    command="npx",
    args=["-y", "@example/mcp-server"],
)
pcfg.mcpEntries = [mcpEntry]
```

支持的传输方式：
- `stdio` - 标准输入输出
- `sse` - Server-Sent Events
- `streamableHttp` - HTTP 流式传输

## 📝 技能系统

技能是扩展 Agent 能力的模块，通过 `SKILL.md` 文件定义：

```markdown
---
description: "示例技能描述"
always: true
metadata: |
  {
    "nanobot": {
      "requires": {
        "bins": ["node"],
        "env": ["API_KEY"]
      }
    }
  }
---

## 技能说明
这里是技能的详细说明和使用指南...
```

技能文件位置：
- 内置技能: `resources/skills/<name>/SKILL.md`
- 用户技能: `<workspace>/skills/<name>/SKILL.md`

## ⚙️ 配置选项

```python
pcfg = PhiloConfig("default")

# 基础配置
pcfg.workspace = "/path/to/workspace"  # 工作目录
pcfg.llm = YourLlmBackend()            # LLM 后端
pcfg.bus = MessageBus()                # 消息总线（可选）

# 行为参数
pcfg.temperature = 0.5           # LLM 温度
pcfg.maxToolIterations = 40      # 最大工具调用轮数
pcfg.memoryWindow = 100          # 记忆窗口大小
pcfg.execTimeout = 60            # 命令执行超时（秒）

# 安全选项
pcfg.restrictToWorkspace = True  # 限制文件操作到工作目录
pcfg.pathAppends = []            # 额外的 PATH 路径
```

## 🔒 安全特性

- **命令过滤** - 阻止危险命令（`rm -rf`、`dd`、`sudo` 等）
- **路径限制** - 可限制文件操作在工作目录内
- **超时控制** - 命令执行有超时限制
- **输出截断** - 防止过大的输出

## 📄 License

MIT License
