from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.agent import agent

router = APIRouter()


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]


@router.post("/chat")
async def chat(request: ChatRequest):
    history = [
        {"role": m.role, "content": m.content} for m in request.messages[:-1]
    ]
    user_message = request.messages[-1].content

    async def stream_response():
        async with agent.run_stream(
            user_message,
            message_history=history,
        ) as result:
            async for chunk in result.stream_text(delta=True):
                yield chunk

    return StreamingResponse(stream_response(), media_type="text/plain")
