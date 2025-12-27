"""Chat endpoint with SSE streaming."""

import asyncio
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.agent.graph import get_agent
from app.core.logging import get_logger
from app.db.session import get_session
from app.middleware.rate_limit import limiter
from app.shared.services.cache.redis_service import get_chat_history
from app.shared.services.memory.embedding_service import get_embedding_service
from app.shared.services.memory.memory_service import MemoryService

router = APIRouter(prefix="/chat", tags=["chat"])
logger = get_logger(__name__)

# Maximum messages to keep in Redis sliding window
MAX_CONTEXT_MESSAGES = 20


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""

    message: str = Field(..., min_length=1, max_length=10000)
    conversation_id: str | None = Field(default=None)


class ChatResponse(BaseModel):
    """Response body for non-streaming chat."""

    response: str
    conversation_id: str


@router.post("")
@limiter.limit("10/minute")
async def chat(request: Request, body: ChatRequest) -> ChatResponse:  # noqa: ARG001
    """Send a message and get a response (non-streaming).

    Rate limited to 10 requests per minute per IP address.
    Overall timeout: 30 seconds.

    Args:
        request: FastAPI Request object (used by rate limiter decorator)
        body: Chat request body with message and conversation_id
    """
    conversation_id = body.conversation_id or "default"

    try:
        # 1. LOAD SHORT-TERM MEMORY (Redis) with timeout
        chat_history = get_chat_history(conversation_id)
        try:
            async with asyncio.timeout(5.0):
                messages = await chat_history.aget_messages()
        except TimeoutError:
            logger.warning("chat_history_timeout", conversation_id=conversation_id)
            messages = []

        # Apply sliding window: keep only last MAX_CONTEXT_MESSAGES
        if len(messages) > MAX_CONTEXT_MESSAGES:
            messages = messages[-MAX_CONTEXT_MESSAGES:]
            logger.debug(
                "sliding_window_applied",
                conversation_id=conversation_id,
                kept_messages=len(messages),
            )

        # 2. LOAD LONG-TERM MEMORY (PostgreSQL) with graceful degradation
        proactive_context = ""
        try:
            async with asyncio.timeout(2.0):
                async with get_session() as session:
                    memory_service = MemoryService(session, get_embedding_service())
                    proactive_context = await memory_service.proactive_recall(body.message)
        except TimeoutError:
            logger.warning(
                "proactive_recall_timeout",
                conversation_id=conversation_id,
                degraded_mode=True,
            )
        except Exception as e:
            logger.warning(
                "proactive_recall_failed",
                conversation_id=conversation_id,
                error=str(e),
                degraded_mode=True,
            )

        # 3. INVOKE AGENT with timeout
        agent = get_agent()
        try:
            async with asyncio.timeout(30.0):
                result = await agent.ainvoke(
                    {
                        "query": body.message,
                        "conversation_id": conversation_id,
                        "messages": messages,
                        "proactive_context": proactive_context,
                    }
                )
        except TimeoutError:
            logger.error("agent_timeout", conversation_id=conversation_id)
            return ChatResponse(
                response=(
                    "I'm taking longer than expected to process your request. Please try again."
                ),
                conversation_id=conversation_id,
            )

        # 4. SAVE SHORT-TERM MEMORY (Redis)
        response_text = result.get("response", "")
        try:
            async with asyncio.timeout(3.0):
                await chat_history.aadd_messages(
                    [
                        HumanMessage(content=body.message),
                        AIMessage(content=response_text),
                    ]
                )
        except TimeoutError:
            logger.warning("save_history_timeout", conversation_id=conversation_id)
            # Continue - don't fail the request if we can't save history

        logger.info(
            "chat_completed",
            conversation_id=conversation_id,
            message_length=len(body.message),
            response_length=len(response_text),
            has_proactive_context=bool(proactive_context),
        )

        return ChatResponse(
            response=response_text,
            conversation_id=conversation_id,
        )

    except Exception as e:
        logger.error(
            "chat_error",
            conversation_id=conversation_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return ChatResponse(
            response="I encountered an error processing your request. Please try again.",
            conversation_id=conversation_id,
        )


@router.post("/stream")
@limiter.limit("10/minute")
async def chat_stream(request: Request, body: ChatRequest):  # noqa: ARG001
    """Send a message and stream the response via SSE.

    Rate limited to 10 requests per minute per IP address.

    Args:
        request: FastAPI Request object (used by rate limiter and disconnect detection)
        body: Chat request body with message and conversation_id
    """
    conversation_id = body.conversation_id or "default"

    # 1. LOAD SHORT-TERM MEMORY (Redis) with timeout
    chat_history = get_chat_history(conversation_id)
    try:
        async with asyncio.timeout(5.0):
            messages = await chat_history.aget_messages()
    except TimeoutError:
        logger.warning("chat_history_timeout", conversation_id=conversation_id)
        messages = []

    # Apply sliding window: keep only last MAX_CONTEXT_MESSAGES
    if len(messages) > MAX_CONTEXT_MESSAGES:
        messages = messages[-MAX_CONTEXT_MESSAGES:]
        logger.debug(
            "sliding_window_applied",
            conversation_id=conversation_id,
            kept_messages=len(messages),
        )

    # 2. LOAD LONG-TERM MEMORY (PostgreSQL) with graceful degradation
    proactive_context = ""
    try:
        async with asyncio.timeout(2.0):
            async with get_session() as session:
                memory_service = MemoryService(session, get_embedding_service())
                proactive_context = await memory_service.proactive_recall(body.message)
    except TimeoutError:
        logger.warning(
            "proactive_recall_timeout",
            conversation_id=conversation_id,
            degraded_mode=True,
        )
    except Exception as e:
        logger.warning(
            "proactive_recall_failed",
            conversation_id=conversation_id,
            error=str(e),
            degraded_mode=True,
        )

    async def event_generator() -> AsyncGenerator[dict, None]:
        agent = get_agent()
        accumulated_response = []

        try:
            async for event in agent.astream_events(
                {
                    "query": body.message,
                    "conversation_id": conversation_id,
                    "messages": messages,
                    "proactive_context": proactive_context,
                },
                version="v2",
            ):
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info("client_disconnected")
                    break

                event_type = event.get("event")

                # Stream tokens from the LLM and accumulate
                if event_type == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        accumulated_response.append(chunk.content)
                        yield {
                            "event": "token",
                            "data": chunk.content,
                        }

            # Stream completed - save to Redis
            if accumulated_response:
                full_response = "".join(accumulated_response)
                yield {
                    "event": "complete",
                    "data": full_response,
                }

                # 3. SAVE SHORT-TERM MEMORY (Redis) - after stream completes
                await chat_history.aadd_messages(
                    [
                        HumanMessage(content=body.message),
                        AIMessage(content=full_response),
                    ]
                )

                logger.info(
                    "chat_stream_completed",
                    conversation_id=conversation_id,
                    message_length=len(body.message),
                    response_length=len(full_response),
                    has_proactive_context=bool(proactive_context),
                )

        except asyncio.CancelledError:
            logger.info("stream_cancelled")
        except Exception as e:
            logger.error("stream_error", error=str(e))
            yield {
                "event": "error",
                "data": str(e),
            }

        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_generator())
