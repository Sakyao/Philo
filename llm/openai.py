import time
from openai import AsyncOpenAI
from philo.llm.base import PhiloLlmBase, LLMResponse, ToolCallRequest


class PhiloOpenAiLlm(PhiloLlmBase):
    def __init__(self, modelName, url, apiKey="", maxRetry=1):
        self.modelName = modelName
        self.client = AsyncOpenAI(
            api_key=apiKey,
            base_url=url,
        )
        self.maxRetry = maxRetry

    def extractContent(self, response) -> str | None:
        if hasattr(response, "choices") and response.choices:
            message = response.choices[0].message
            if hasattr(message, "content") and message.content:
                return message.content
            if isinstance(message, dict):
                return message.get("content", None)
        return None

    def extractReasoningContent(self, response) -> str | None:
        if hasattr(response, "choices") and response.choices:
            message = response.choices[0].message
            if hasattr(message, "reasoning") and message.reasoning:
                return message.reasoning
            if hasattr(message, "reasoning_content") and message.reasoning_content:
                return message.reasoning_content
            if isinstance(message, dict):
                return message.get("reasoning", None) or message.get("reasoning_content", None)
        return None

    def extractToolCalls(self, response) -> list[ToolCallRequest]:
        toolCalls = []
        if hasattr(response, "choices") and response.choices:
            message = response.choices[0].message
            if hasattr(message, "tool_calls") and message.tool_calls:
                for tc in message.tool_calls:
                    toolCalls.append(ToolCallRequest(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=tc.function.arguments if isinstance(tc.function.arguments, dict) else eval(tc.function.arguments) if isinstance(tc.function.arguments, str) else {},
                    ))
            elif isinstance(message, dict) and "tool_calls" in message:
                for tc in message["tool_calls"]:
                    toolCalls.append(ToolCallRequest(
                        id=tc.get("id", ""),
                        name=tc.get("function", {}).get("name", ""),
                        arguments=tc.get("function", {}).get("arguments", {}),
                    ))
        return toolCalls

    def extractFinishReason(self, response) -> str:
        if hasattr(response, "choices") and response.choices:
            choice = response.choices[0]
            if hasattr(choice, "finish_reason") and choice.finish_reason:
                return choice.finish_reason
            if isinstance(choice, dict):
                return choice.get("finish_reason", "stop")
        return "stop"

    def extractUsage(self, response, secs) -> dict[str, int]:
        if hasattr(response, "usage") and response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
                "speed": int(response.usage.completion_tokens / secs) if secs > 0 else 0,
            }
            return usage
        return {}

    async def chat(self, messages, tools=None, **kwargs) -> LLMResponse:
        t0 = time.time()
        errored = False
        ee = None
        response = None
        for _ in range(self.maxRetry):
            try:
                params = {
                    "model": self.modelName,
                    "messages": messages,
                }
                if tools is not None and len(tools) > 0:
                    params["tools"] = tools
                if "temperature" in kwargs:
                    params["temperature"] = kwargs["temperature"]
                response = await self.client.chat.completions.create(**params)
                errored = False
                break
            except Exception as e:
                errored = True
                ee = e
                time.sleep(1)
        if errored and ee is not None:
            raise ee
        t1 = time.time()

        return LLMResponse(
            content=self.extractContent(response),
            toolCalls=self.extractToolCalls(response),
            finishReason=self.extractFinishReason(response),
            usage=self.extractUsage(response, t1 - t0),
            reasoningContent=self.extractReasoningContent(response),
        )
