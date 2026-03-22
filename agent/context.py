import base64
import mimetypes
from pathlib import Path
from typing import Any
from jinja2 import Environment, StrictUndefined
from philo.agent.memory import MemoryStore
from philo.agent.skillsloader import SkillsLoader
from philo.utils.misc import detectImageMime, getYaml
from philo.utils.yamlio import YamlLoader


class ContextBuilder(object):
    def __init__(self, pcfg):
        self.pcfg = pcfg
        self.memory = MemoryStore(pcfg)
        self.skills = SkillsLoader(pcfg)
        self.yamlTemplate = YamlLoader(getYaml("context.yaml"))
        self.systemPromptGen = Environment(undefined=StrictUndefined).from_string(self.yamlTemplate["system"])

    def buildSystemPrompt(self) -> str:
        return self.systemPromptGen.render(
            workspace=str(self.pcfg.workspace.absolute()),
            memory=self.memory.getMemoryContext(),
            activeSkills=self.skills.getActiveSkills(),
            skillsSummary=self.skills.buildSkillsSummary(),
        )

    def buildMessages(
        self,
        history: list[dict[str, Any]],
        currentMessage: str,
        files: list[str] | None = None,
    ):
        userContent = self.buildUserContent(currentMessage, files)
        return [
            {"role": "system", "content": self.buildSystemPrompt()},
            *history,
            {"role": "user", "content": userContent},
        ]

    def buildUserContent(self, text, files) -> str | list[dict[str, Any]]:
        if files is None or len(files) == 0:
            return text
        images = []
        for path in files:
            p = Path(path)
            if not p.is_file():
                continue
            raw = p.read_bytes()
            mime = detectImageMime(raw) or mimetypes.guess_type(path)[0]
            if not mime or not mime.startswith("image/"):
                continue
            b64 = base64.b64encode(raw).decode()
            images.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
        if len(images) == 0:
            return text
        return images + [{"type": "text", "text": text}]

    def addToolResult(self, messages, toolCallId, toolName, result):
        messages.append({"role": "tool", "tool_call_id": toolCallId, "name": toolName, "content": result})
        return messages

    def addAssistantMessage(self, messages, content, toolCalls=None, reasoningContent=None):
        msg: dict[str, Any] = {"role": "assistant", "content": content}
        if toolCalls:
            msg["tool_calls"] = toolCalls
            msg["tool_used"] = [x["function"]["name"] for x in toolCalls]
        if reasoningContent is not None:
            msg["reasoning_content"] = reasoningContent
        messages.append(msg)
        return messages
