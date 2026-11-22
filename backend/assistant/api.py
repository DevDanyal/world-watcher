from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from backend.assistant.runner import AssistantRunner

router = APIRouter(prefix="/assistant", tags=["assistant"])


class ToolCallIn(BaseModel):
    tool: str
    args: dict = Field(default_factory=dict)
    confirmed: bool = False


class ConfirmIn(BaseModel):
    action_id: str
    yes: bool


def _runner(request: Request) -> AssistantRunner:
    runner = getattr(request.app.state, "assistant_runner", None)
    if runner is None:
        runner = AssistantRunner(request.app)
        request.app.state.assistant_runner = runner
    return runner


@router.post("/tool")
async def run_tool(body: ToolCallIn, request: Request):
    return await _runner(request).execute(body.tool, body.args, confirmed=body.confirmed)


@router.post("/confirm")
async def confirm(body: ConfirmIn, request: Request):
    return await _runner(request).confirm(body.action_id, body.yes)
