"""
LLM Service - OpenAI Client Wrapper

async and sync OpenAI clients for use across the application.
"""

from typing import Optional, Any, Iterable

from openai import OpenAI, AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from app.core.config import settings


class LLMService:

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
    ):

        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model_name = model_name or settings.OPENAI_MODEL_NAME
        self.base_url = base_url or settings.OPENAI_BASE_URL

        # sync and async clients
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.async_client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    def chat_completion(
        self,
        messages: Iterable[ChatCompletionMessageParam],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> str:
        response = self.client.chat.completions.create(
            model=model or self.model_name,
            messages=list(messages),
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        return response.choices[0].message.content or ""

    async def achat_completion(
        self,
        messages: Iterable[ChatCompletionMessageParam],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> str:

        response = await self.async_client.chat.completions.create(
            model=model or self.model_name,
            messages=list(messages),
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        return response.choices[0].message.content or ""

    def get_client(self) -> OpenAI:
        """Get synchronous OpenAI client"""
        return self.client

    def get_async_client(self) -> AsyncOpenAI:
        """Get asynchronous OpenAI client"""
        return self.async_client

    def get_structured_llm(self, output_schema: type):
        """Get LLM with structured output -json"""
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=self.model_name,
            api_key=self.api_key,
            temperature=0.0
        )
        return llm.with_structured_output(output_schema)
