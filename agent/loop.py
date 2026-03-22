import json
import weakref
import asyncio
from philo.utils.log import log
from philo.agent.context import ContextBuilder
from philo.agent.toolmanager import ToolManager
from philo.agent.mcpmanager import McpManager
from philo.config.pconfig import PhiloConfig
from philo.llm.base import PhiloLlmBase
from philo.infra.bus import InboundMessage, OutboundMessage
from philo.infra.session import SessionManager, Session
from philo.infra.mdexport import SessionMarkdownExporter


class PhiloLoop(object):
    def __init__(self, pcfg: PhiloConfig):
        self.pcfg = pcfg
        self.llm: PhiloLlmBase = pcfg.llm
        self.sessionManager = SessionManager(self.pcfg.workspace)
        self.contextBuilder = ContextBuilder(self.pcfg)
        self.toolManager = self.initToolManager()
        self.mcpManager = McpManager(self.toolManager, self.pcfg.mcpEntries)
        self.mdExporter = SessionMarkdownExporter(self.pcfg.workspace)
        self.consolidatingSessions: set[str] = set()  # Session keys with consolidation in progress
        self.consolidationTasks: set[asyncio.Task] = set()  # Strong refs to in-flight tasks
        self.consolidationLocks: weakref.WeakValueDictionary[str, asyncio.Lock] = weakref.WeakValueDictionary()

    def initToolManager(self):
        from philo.tools.exec import ExecTool
        from philo.tools.filesystem import ReadFileTool, WriteFileTool, ListDirTool, EditFileTool
        from philo.tools.message import MessageTool
        from philo.tools.websearch import BochaWebSearchTool, WebFetchTool
        toolManager = ToolManager()
        toolManager.register(ExecTool(workspace=self.pcfg.workspace, pathAppends=self.pcfg.pathAppends))
        toolManager.register(ReadFileTool(workspace=self.pcfg.workspace))
        toolManager.register(WriteFileTool(workspace=self.pcfg.workspace))
        toolManager.register(ListDirTool(workspace=self.pcfg.workspace))
        toolManager.register(EditFileTool(workspace=self.pcfg.workspace))
        toolManager.register(MessageTool(bus=self.pcfg.bus))
        toolManager.register(BochaWebSearchTool(apiKey=self.pcfg.bochaApiKey))
        toolManager.register(WebFetchTool())
        return toolManager

    def checkMemoryConsolidation(self, session: Session):
        unconsolidated = len(session.messages) - session.nConsolidated
        if (unconsolidated >= self.pcfg.memoryWindow and session.sessionId not in self.consolidatingSessions):
            self.consolidatingSessions.add(session.sessionId)
            lock = self.consolidationLocks.setdefault(session.sessionId, asyncio.Lock())
            async def consolidateAndUnlock():
                try:
                    async with lock:
                        await self.contextBuilder.memory.consolidate(session)
                finally:
                    self.consolidatingSessions.discard(session.sessionId)
                    task = asyncio.current_task()
                    if task is not None:
                        self.consolidationTasks.discard(task)
            task = asyncio.create_task(consolidateAndUnlock())
            self.consolidationTasks.add(task)

    async def processMessage(self, msg: InboundMessage, onProgressCallback=None):
        session = self.sessionManager.getSession(msg.sessionId, nobuf=self.pcfg.nobuf)
        history = session.getHistory(maxMessages=self.pcfg.memoryWindow)
        initialMessages = self.contextBuilder.buildMessages(
            history=history,
            currentMessage=msg.content,
            files=msg.files,
        )
        self.checkMemoryConsolidation(session)
        finalMsg, _, messages = await self.innerLoop(msg, initialMessages, onProgressCallback)
        if finalMsg is None:
            finalMsg = "Done."
        session.addMessages(messages, 1 + len(history))
        self.sessionManager.dumpSession(session)
        self.mdExporter.exportMessages(msg.sessionId, messages)
        return OutboundMessage(
            channel=msg.channel,
            chatId=msg.chatId,
            content=finalMsg,
            metadata=msg.metadata,
        )

    async def innerLoop(self, msg, initialMessages, onProgressCallback):
        messages = initialMessages
        iteration = 0
        finalMsg = None
        toolsUsed: list[str] = []

        while iteration < self.pcfg.maxToolIterations:
            iteration += 1
            response = await self.llm.chat(
                messages=messages,
                tools=self.toolManager.getToolsSchema(),
                temperature=self.pcfg.temperature,
            )
            if response.hasToolCalls:
                if onProgressCallback is not None:
                    await onProgressCallback(msg, response.content)
                    await onProgressCallback(msg, response.formatToolHint(), toolHint=True)

                toolCallDictList = [{
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False)
                    }
                } for tc in response.toolCalls]
                messages = self.contextBuilder.addAssistantMessage(
                    messages=messages,
                    content=response.content,
                    toolCalls=toolCallDictList,
                    reasoningContent=response.reasoningContent,
                )
                for tc in response.toolCalls:
                    toolsUsed.append(tc.name)
                    args_str = json.dumps(tc.arguments, ensure_ascii=False)
                    log.inf("Tool call: {}({})", tc.name, args_str[:100])
                    result = await self.toolManager.execute(tc.name, tc.arguments)
                    messages = self.contextBuilder.addToolResult(
                        messages=messages,
                        toolCallId=tc.id,
                        toolName=tc.name,
                        result=result,
                    )
            else:
                # Don't persist error responses to session history — they can poison the context and cause permanent 400 loops (#1303).
                if response.finishReason == "error":
                    log.red("LLM returned error: {}", (response.content or "")[:200])
                    finalMsg = response.content or "Sorry, I encountered an error calling the AI model."
                    break
                messages = self.contextBuilder.addAssistantMessage(
                    messages=messages,
                    content=response.content,
                    reasoningContent=response.reasoningContent,
                )
                finalMsg = response.content
                break

        if finalMsg is None and iteration >= self.pcfg.maxToolIterations:
            log.yellow("Max iterations ({}) reached", self.pcfg.maxToolIterations)
            finalMsg = f"I reached the maximum number of tool call iterations ({self.pcfg.maxToolIterations}) without completing the task. You can try breaking the task into smaller steps."
        return finalMsg, toolsUsed, messages
