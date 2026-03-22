import asyncio
import httpx
from typing import List
from contextlib import AsyncExitStack
from philo.utils.log import log
from philo.config.pconfig import McpEntry
from philo.agent.toolmanager import ToolManager
from philo.tools.mcp import McpToolWrapper


class McpManager(object):
    def __init__(self, toolManager: ToolManager, mcpEntries: List[McpEntry]):
        self.toolManager = toolManager
        self.mcpEntries = mcpEntries
        self.connected = False
        self.connecting = False
        self.mcpStack: AsyncExitStack | None = None
        self.cleanupLock = asyncio.Lock()

    async def disconnect(self):
        async with self.cleanupLock:
            if self.mcpStack is not None:
                try:
                    await self.mcpStack.aclose()
                except RuntimeError as e:
                    # MCP SDK's streamable_http_client uses anyio task groups which bind
                    # cancel scopes to the task that created them. When closing from a
                    # different task context, this error is expected and harmless.
                    if "cancel scope" in str(e):
                        pass  # Silently ignore cancel scope task mismatch
                    else:
                        log.red("Error closing MCP connections: {}".format(e))
                except Exception as e:
                    log.red("Error closing MCP connections: {}".format(e))
                finally:
                    self.mcpStack = None
                    self.connected = False

    async def connect(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.sse import sse_client
        from mcp.client.stdio import stdio_client
        from mcp.client.streamable_http import streamable_http_client

        for mcpEntry in self.mcpEntries:
            try:
                transportType = mcpEntry.transportType
                if not transportType:
                    if mcpEntry.command:
                        transportType = "stdio"
                    elif mcpEntry.url:
                        transportType = "sse" if mcpEntry.url.rstrip("/").endswith("/sse") else "streamableHttp"
                    else:
                        log.red("MCP server '{}': no command or url configured, skipping".format(mcpEntry.name))
                        continue

                if transportType == "stdio":
                    params = StdioServerParameters(
                        command=mcpEntry.command,
                        args=mcpEntry.args,
                        env=mcpEntry.env or None
                    )
                    read, write = await self.mcpStack.enter_async_context(stdio_client(params))
                elif transportType == "sse":
                    def httpx_client_factory(
                        headers: dict[str, str] | None = None,
                        timeout: httpx.Timeout | None = None,
                        auth: httpx.Auth | None = None,
                    ) -> httpx.AsyncClient:
                        merged_headers = {**(mcpEntry.headers or {}), **(headers or {})}
                        return httpx.AsyncClient(
                            headers=merged_headers or None,
                            follow_redirects=True,
                            timeout=timeout,
                            auth=auth,
                        )
                    read, write = await self.mcpStack.enter_async_context(
                        sse_client(mcpEntry.url, httpx_client_factory=httpx_client_factory)
                    )
                elif transportType == "streamableHttp":
                    # Always provide an explicit httpx client so MCP HTTP transport does not
                    # inherit httpx's default 5s timeout and preempt the higher-level tool timeout.
                    http_client = await self.mcpStack.enter_async_context(
                        httpx.AsyncClient(
                            headers=mcpEntry.headers or None,
                            follow_redirects=True,
                            timeout=None,
                        )
                    )
                    read, write, _ = await self.mcpStack.enter_async_context(
                        streamable_http_client(mcpEntry.url, http_client=http_client)
                    )
                else:
                    log.red("MCP server '{}': unknown transport type '{}'".format(mcpEntry.name, transportType))
                    continue

                session = await self.mcpStack.enter_async_context(ClientSession(read, write))
                await session.initialize()

                tools = await session.list_tools()
                for toolDef in tools.tools:
                    wrapper = McpToolWrapper(session, mcpEntry, toolDef)
                    self.toolManager.register(wrapper)
            except Exception as e:
                log.red("MCP server [{}]: Failed to connect: {}".format(mcpEntry.name, e))

    async def checkConnection(self):
        if len(self.mcpEntries) == 0:
            return
        if self.connecting or self.connected:
            return
        self.connecting = True
        try:
            self.mcpStack = AsyncExitStack()
            await self.mcpStack.__aenter__()
            await self.connect()
            self.connected = True
        except Exception as e:
            log.red("Failed to connect MCP servers (will retry next message): {}".format(e))
            if self.mcpStack:
                try:
                    await self.mcpStack.aclose()
                except Exception:
                    pass
                self.mcpStack = None
        finally:
            self.connecting = False
