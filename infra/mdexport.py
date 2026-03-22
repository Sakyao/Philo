from typing import Any
from pathlib import Path


class SessionMarkdownExporter:
    def __init__(self, workspace: Path):
        self.outputDir = workspace / "markdown"
        self.outputDir.mkdir(parents=True, exist_ok=True)

    def formatMessage(self, msg: dict[str, Any], index: int) -> str:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        timestamp = msg.get("timestamp", "")
        name = msg.get("name", "")
        toolCallId = msg.get("tool_call_id", "")
        toolCalls = msg.get("tool_calls", [])
        reasoningContent = msg.get("reasoning_content", "")
        roleIcons = {
            "system": "⚙️",
            "user": "👤",
            "assistant": "🤖",
            "tool": "🔧"
        }
        icon = roleIcons.get(role, "📝")
        lines = []
        lines.append(f"## {icon} Message {index}: `{role}`")
        lines.append("")

        if timestamp:
            lines.append(f"| **Timestamp** | `{timestamp}` |")
        if name:
            lines.append(f"| **Tool Name** | `{name}` |")
        if toolCallId:
            lines.append(f"| **Tool Call ID** | `{toolCallId}` |")
        lines.append("")

        if reasoningContent:
            lines.append("### 🧠 Reasoning")
            lines.append("")
            lines.append("```")
            lines.append(reasoningContent)
            lines.append("```")
            lines.append("")

        if toolCalls:
            lines.append("### 🔧 Tool Calls")
            lines.append("")
            for i, tc in enumerate(toolCalls, 1):
                tcId = tc.get("id", "")
                tcType = tc.get("type", "")
                func = tc.get("function", {})
                funcName = func.get("name", "")
                funcArgs = func.get("arguments", "")
                lines.append(f"**Call {i}:** `{funcName}`")
                lines.append("")
                lines.append(f"- ID: `{tcId}`")
                lines.append(f"- Type: `{tcType}`")
                lines.append("- Arguments:")
                lines.append("```json")
                lines.append(funcArgs)
                lines.append("```")
                lines.append("")

        lines.append("### 📄 Content")
        lines.append("")

        if isinstance(content, str):
            if content:
                lines.append(content)
            else:
                lines.append("*(empty)*")
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    partType = part.get("type", "")
                    if partType == "text":
                        lines.append(part.get("text", ""))
                    elif partType == "image_url":
                        imgUrl = part.get("image_url", {}).get("url", "")
                        if imgUrl:
                            lines.append(f"![Image]({imgUrl})")
                    else:
                        lines.append(f"```json\n{part}\n```")
                else:
                    lines.append(str(part))
        else:
            lines.append(f"```json\n{content}\n```")

        lines.append("")
        lines.append("---")
        lines.append("")
        return "\n".join(lines)

    def exportMessages(self, sessionId, messages) -> Path:
        safeSessionId = sessionId.replace(":", "_").replace("/", "_")
        filename = f"session_{safeSessionId}"
        outputPath = self.outputDir / f"{filename}.md"
        lines = []
        lines.append(f"# Session Record: `{sessionId}`")
        lines.append("")
        lines.append("## 💬 Messages")
        lines.append("")
        for i, msg in enumerate(messages, 1):
            lines.append(self.formatMessage(msg, i))
        content = "\n".join(lines)
        outputPath.write_text(content, encoding="utf-8")
        return outputPath
