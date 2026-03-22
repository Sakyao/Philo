import os


def llm():
    from philo.llm.openai import PhiloOpenAiLlm
    return PhiloOpenAiLlm(
        modelName="glm-5-fp8",
        url="http://192.168.1.13:18173/v1",
        apiKey="alice_glm5_xofe72789",
        maxRetry=2,
    )


def bochaApiKey():
    bochaApiKey = os.getenv("BOCHA_API_KEY")
    if not bochaApiKey:
        raise ValueError("Environment variable not set: BOCHA_API_KEY")
    return bochaApiKey


def oneshot():
    # return "Hi, 帮我做一次AI搜索：具身智能最新研究现状"
    return "创作一部类似三体的小说"


def mcps():
    from philo.config.pconfig import McpEntry
    return [
        McpEntry(
            name="bocha-mcp",
            transportType="streamableHttp",
            url="https://mcp.bochaai.com/mcp",
            headers={
                "Authorization": "Bearer {}".format(bochaApiKey())
            },
            timeout=300,
        )
    ]


def pcfg():
    from philo.config.pconfig import PhiloConfig
    pcfg = PhiloConfig("oneshot0")
    pcfg.workspace = "/z5s/ame/x/philo/oneshot0"
    pcfg.bochaApiKey = bochaApiKey()
    pcfg.llm = llm()
    pcfg.oneshotInput = oneshot()
    pcfg.mcpEntries = mcps()
    return pcfg


if __name__ == "__main__":
    import asyncio
    from philo.infra.engine.oneshot import PhiloOneshotEngine
    engine = PhiloOneshotEngine(pcfg=pcfg())
    asyncio.run(engine.runOneshot())
