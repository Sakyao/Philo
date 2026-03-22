import asyncio
from philo.utils.log import log
from philo.config.pconfig import PhiloConfig
from philo.infra.bus import InboundMessage
from philo.infra.engine.base import PhiloEngineBase


class PhiloInteractiveEngine(PhiloEngineBase):
    def __init__(self, pcfg: PhiloConfig):
        super().__init__(pcfg)
        self.channel = "cli"
        self.senderId = "user"
        self.chatId = self.pcfg.cfgname

    async def runInteractive(self):
        log.cyan("Philo running interactively")
        self.cli.initPromptSession()
        inboundTask = asyncio.create_task(self.runInboundLoop())
        outboundTask = asyncio.create_task(self.runOutboundLoop())
        self.asyncTasks.append(inboundTask)
        self.asyncTasks.append(outboundTask)
        self.ready4Input.set()

        while True:
            try:
                self.cli.flushPendingTtyInput()
                userInput = await self.cli.readInteractiveInput()
                if userInput is None or len(userInput) == 0:
                    continue
                if userInput == "/stop":
                    self.cli.print("\nGoodbye!")
                    break
                self.ready4Input.clear()
                self.agentResponseList.clear()
                await self.bus.writeInbound(InboundMessage(
                    channel=self.channel,
                    senderId=self.senderId,
                    chatId=self.chatId,
                    content=userInput,
                ))
                with self.cli.thinkingContext():
                    await self.ready4Input.wait()
                for item in self.agentResponseList:
                    self.cli.renderMarkdown(item)

            except KeyboardInterrupt:
                self.cli.restoreTerminal()
                self.cli.print("\nGoodbye!")
                break
            except EOFError:
                self.cli.restoreTerminal()
                self.cli.print("\nGoodbye!")
                break

        await self.loop.mcpManager.disconnect()
        for task in self.asyncTasks:
            task.cancel()
