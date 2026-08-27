import logging
from typing import TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from bentoai.config import get_settings

logger = logging.getLogger(__name__)

TOutput = TypeVar("TOutput", bound=BaseModel)

_client: AsyncOpenAI | None = None



class ModelRefused(Exception):
    """The model declined to answer instead of returning a result.

    Its own exception because it is not a bug and not a network problem — the
    model understood and chose not to reply. Retrying the same prompt will get
    the same answer, so callers should handle it rather than retry.
    """

def get_llm_client() -> AsyncOpenAI:

    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncOpenAI(
            api_key=settings.llm.api_key.get_secret_value(),
            timeout=settings.llm.timeout_seconds,
        )

    return _client

async def generate_structured(*, system:str, user_message:str, output_model:type[TOutput]) -> TOutput:

    settings = get_settings()
    client = get_llm_client()

    response = await client.chat.completions.parse(
        model=settings.llm.model,
        max_completion_tokens=settings.llm.max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role":"user","content":user_message},
        ],
        response_format=output_model,
    )

    message= response.choices[0].message

    if message.refusal:
        raise ModelRefused(message.refusal)

    if message.parsed is None:
        raise ModelRefused("The model returned no parsed result")

    logger.info(
        "llm_call model=%s prompt_tokens=%s completion_tokens=%s",
        response.model,
        response.usage.prompt_tokens if response.usage else None,
        response.usage.completion_tokens if response.usage else None,
    )

    return message.parsed