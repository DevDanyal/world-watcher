from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from backend.security import (
    SESSION_COOKIE,
    SESSION_TTL_SECONDS,
    create_session,
    delete_session,
    get_session,
    has_password,
    set_initial_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class PasswordIn(BaseModel):
    password: str = Field(min_length=8, max_length=128)


@router.get("/status")
async def status(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    return {
        "initialized": has_password(),
        "authenticated": get_session(token),
    }


@router.post("/setup")
async def setup(body: PasswordIn, response: Response):
    if has_password():
        raise HTTPException(status_code=409, detail="password already set")
    set_initial_password(body.password)
    token = create_session()
    _set_cookie(response, token)
    return {"ok": True, "initialized": True, "authenticated": True}


@router.post("/login")
async def login(body: PasswordIn, response: Response):
    if not has_password():
        raise HTTPException(status_code=400, detail="password not initialized")
    if not verify_password(body.password):
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = create_session()
    _set_cookie(response, token)
    return {"ok": True, "authenticated": True}


@router.post("/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE)
    delete_session(token)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True, "authenticated": False}


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
