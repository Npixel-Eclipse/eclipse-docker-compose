"""OpenRouter API client for LLM interactions."""

import httpx
from typing import AsyncIterator, Optional, Any
from ..models import Message, LLMResponse

# Removed local Message and LLMResponse classes to use shared ones from ..models


class LLMClient:
    """Asynchronous client for OpenRouter API."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        default_model: str = "google/gemini-3-flash-preview",
        timeout: float = 60.0,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.default_model = default_model
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://eclipse-bot.local",
                    "X-Title": "Eclipse Bot",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(self.timeout),
            )
        return self._client

    async def chat(
        self,
        messages: list[Message],
        model: Optional[str] = None,
        tools: Optional[list[dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Send chat completion request."""
        client = await self._get_client()

        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": [],
            "temperature": temperature,
        }

        # Format messages for the API
        for m in messages:
            msg_dict: dict[str, Any] = {"role": m.role}
            if m.content is not None:
                msg_dict["content"] = m.content
            if m.tool_calls:
                msg_dict["tool_calls"] = m.tool_calls
            if m.tool_call_id:
                msg_dict["tool_call_id"] = m.tool_call_id
            payload["messages"].append(msg_dict)

        if tools:
            payload["tools"] = tools
        if max_tokens:
            payload["max_tokens"] = max_tokens

        response = await client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]["message"]
        
        return LLMResponse(
            content=choice.get("content"),
            model=data.get("model", model or self.default_model),
            usage=data.get("usage", {}),
            tool_calls=choice.get("tool_calls"),
        )

    async def chat_stream(
        self,
        messages: list[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """Stream chat completion response."""
        client = await self._get_client()

        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": [],
            "temperature": temperature,
            "stream": True,
        }

        # Format messages for the API (same as chat method)
        for m in messages:
            msg_dict: dict[str, Any] = {"role": m.role}
            if m.content is not None:
                msg_dict["content"] = m.content
            if m.tool_calls:
                msg_dict["tool_calls"] = m.tool_calls
            if m.tool_call_id:
                msg_dict["tool_call_id"] = m.tool_call_id
            payload["messages"].append(msg_dict)

        if max_tokens:
            payload["max_tokens"] = max_tokens

        async with client.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    
                    import json
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})
                        if delta.get("content"):
                            yield delta["content"]
                    except (json.JSONDecodeError, KeyError, IndexError) as e:
                        logger.warning(f"Error parsing SSE chunk: {e}")
                        continue

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
