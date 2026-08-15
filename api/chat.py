import asyncio
import base64
import binascii
import json
from contextlib import suppress

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pydantic_ai import BinaryContent
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart

from .agents.main import agent
from .tools.filter import AirbnbFilters, form_snapshot

router = APIRouter()

MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    search: AirbnbFilters | None = None
    image: str | None = None


def decode_image_data_url(value: str) -> tuple[bytes, str]:
    """Decode and validate a browser-generated image data URL."""
    header, separator, encoded = value.partition(",")
    media_type = header.removeprefix("data:").split(";", 1)[0].lower()
    if (
        not separator
        or not header.startswith("data:")
        or ";base64" not in header
        or media_type not in ALLOWED_IMAGE_TYPES
    ):
        raise ValueError("Image must be a base64-encoded JPEG, PNG, WebP, or GIF")
    if len(encoded) > (MAX_IMAGE_BYTES * 4 // 3) + 4:
        raise ValueError("Image must be 5 MB or smaller")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Image data is invalid") from exc
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Image must be between 1 byte and 5 MB")
    return data, media_type


@router.post("/chat")
async def chat(request: ChatRequest):
    history = [
        ModelRequest(parts=[UserPromptPart(content=m.content)])
        if m.role == "user"
        else ModelResponse(parts=[TextPart(content=m.content)])
        for m in request.messages[:-1]
    ]
    user_message = request.messages[-1].content
    deps = request.search or AirbnbFilters()
    before = form_snapshot(deps)
    user_prompt: str | list[str | BinaryContent] = user_message
    if request.image:
        try:
            image_data, image_media_type = decode_image_data_url(request.image)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        deps._query_image = image_data
        deps._query_image_media_type = image_media_type
        user_prompt = [
            user_message or "Use this reference image to find visually similar listings.",
            BinaryContent(data=image_data, media_type=image_media_type),
        ]

    async def stream_response():
        events: asyncio.Queue[dict[str, object]] = asyncio.Queue()

        async def report_progress(message: str) -> None:
            await events.put({"type": "status", "message": message})

        deps._progress = report_progress

        async def run_agent() -> None:
            try:
                await report_progress("Understanding your request")
                async with agent.run_stream(
                    user_prompt,
                    message_history=history,
                    deps=deps,
                ) as result:
                    async for chunk in result.stream_text(delta=True):
                        await events.put({"type": "text", "delta": chunk})

                after = form_snapshot(deps)
                if after != before:
                    await events.put({"type": "search", "data": after})
                if deps._listing_results:
                    await events.put(
                        {"type": "listings", "data": deps._listing_results}
                    )
            except Exception as exc:
                await events.put({"type": "error", "message": str(exc)})
            finally:
                await events.put({"type": "done"})

        task = asyncio.create_task(run_agent())
        try:
            while True:
                event = await events.get()
                yield json.dumps(event, separators=(",", ":")) + "\n"
                if event["type"] == "done":
                    break
        finally:
            if not task.done():
                task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    return StreamingResponse(
        stream_response(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
