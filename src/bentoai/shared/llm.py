"""The one place a language model is called.

Every agent goes through generate_structured. Nothing else in the codebase
constructs a model client, which is what makes the provider a single decision
rather than four.

Built on LangChain since 2026-09-07. What that bought us:

  * retries on transient failures, which there were none of before
  * LangSmith tracing - a real answer to §10.3's "evaluation duration, provider
    latency, token counts", which had been log lines
  * one interface if a second provider is ever added

What it deliberately did NOT change: the agents. They call the same function
with the same arguments and get the same objects back. Swapping what sits behind
this function is the whole reason it exists.

TRACING is off unless you turn it on. Set these in .env to enable it, and know
what it means: prompts and responses - customer goals, product data - are sent
to LangSmith's servers.

    LANGSMITH_TRACING=true
    LANGSMITH_API_KEY=...
    LANGSMITH_PROJECT=bentoai
"""

import logging
from typing import TypeVar

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from openai import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)
from pydantic import BaseModel

from bentoai.config import get_settings

logger = logging.getLogger(__name__)

# Failures that are worth another attempt. Everything else fails immediately.
_TRANSIENT = (
    APITimeoutError,
    APIConnectionError,
    InternalServerError,
    RateLimitError,
)

TOutput = TypeVar("TOutput", bound=BaseModel)

_client: ChatOpenAI | None = None


class ModelRefused(Exception):
    """The model declined to answer instead of returning a result.

    Its own exception because it is not a bug and not a network problem - the
    model understood and chose not to reply. Retrying the same prompt gets the
    same answer, so callers handle it rather than retry. The evaluation and
    comparison agents both rely on this: a refusal costs them one requirement's
    judgement, not the whole mission.
    """


def get_llm_client() -> ChatOpenAI:
    """The shared model client, built once.

    Once because a client holds a connection pool. Building one per call would
    open a new pool per request and spend more time on handshakes than on the
    model.
    """
    global _client
    if _client is None:
        settings = get_settings()
        _client = ChatOpenAI(
            model=settings.llm.model,
            api_key=settings.llm.api_key.get_secret_value(),
            timeout=settings.llm.timeout_seconds,
            max_completion_tokens=settings.llm.max_tokens,
            # LangChain's own retry, separate from ours below. Zero here so
            # there is one retry policy rather than two multiplying together.
            max_retries=0,
        )

    return _client


async def generate_structured(
    *, system: str, user_message: str, output_model: type[TOutput]
) -> TOutput:
    """Ask the model a question and get back a validated object.

    output_model is a Pydantic class. The model is given its shape and is not
    free to answer in any other form - which is what lets an agent's result be
    used directly instead of parsed out of prose.
    """
    settings = get_settings()

    # with_structured_output binds the schema to the model. include_raw asks for
    # the underlying message as well as the parsed object, which we need for two
    # things the parsed object alone cannot tell us: whether the model refused,
    # and how many tokens it used.
    structured = get_llm_client().with_structured_output(
        output_model, include_raw=True
    )

    # Retry only the failures worth retrying. A timeout, a dropped connection,
    # a 429 or a 500 is weather and will probably work next time. A bad api key
    # or a malformed request is not - asking again spends the same money to be
    # told the same thing, three times slower (§10.2 rule 2).
    #
    # Without naming the types this retries everything, which is how a wrong
    # api key turns into three failed calls and a long wait instead of one
    # immediate error.
    runnable = structured.with_retry(
        retry_if_exception_type=_TRANSIENT,
        stop_after_attempt=max(1, settings.llm.max_retries),
        wait_exponential_jitter=True,
    )

    result = await runnable.ainvoke(
        [("system", system), ("user", user_message)]
    )

    raw: AIMessage | None = result.get("raw") if isinstance(result, dict) else None
    parsed = result.get("parsed") if isinstance(result, dict) else result

    _log_usage(raw)

    # The model was asked and said no. Newer OpenAI models put this in a
    # dedicated field rather than answering with a sentence about why not.
    refusal = (raw.additional_kwargs or {}).get("refusal") if raw else None
    if refusal:
        raise ModelRefused(str(refusal))

    if parsed is None:
        # Answered, but not in the shape it was given. Treated as a refusal
        # because the caller's options are the same either way - there is no
        # result to use.
        error = result.get("parsing_error") if isinstance(result, dict) else None
        raise ModelRefused(f"The model returned no usable result. {error or ''}".strip())

    return parsed


def _log_usage(raw: AIMessage | None) -> None:
    """Record what the call cost, in the same shape as before."""
    if raw is None:
        return

    usage = raw.usage_metadata or {}
    logger.info(
        "llm_call model=%s prompt_tokens=%s completion_tokens=%s",
        (raw.response_metadata or {}).get("model_name"),
        usage.get("input_tokens"),
        usage.get("output_tokens"),
    )
