"""Attach the canonical Cashh Radar loop UI to the existing web shell.

The core index.html remains the product shell. This module injects one deferred
frontend enhancement script into the root document so the same UI connection is
present on Docker/Railway, Vercel, and compatibility entrypoints without
forking the static page.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse


SCRIPT_TAG = '<script src="/static/loop-ui.js" defer></script>'


def register_cashh_loop_ui(app: FastAPI) -> FastAPI:
    if getattr(app.state, "cashh_loop_ui_registered", False):
        return app

    app.state.cashh_loop_ui_registered = True

    @app.middleware("http")
    async def inject_cashh_loop_ui(request: Request, call_next: Any):
        response = await call_next(request)
        if request.url.path != "/" or response.status_code != 200:
            return response
        if "text/html" not in (response.headers.get("content-type") or ""):
            return response

        try:
            if hasattr(response, "body_iterator"):
                chunks = [chunk async for chunk in response.body_iterator]
                body = b"".join(chunk if isinstance(chunk, bytes) else str(chunk).encode("utf-8") for chunk in chunks)
            else:
                body = getattr(response, "body", b"")
            text = body.decode("utf-8")
        except Exception:
            return response

        if SCRIPT_TAG not in text:
            text = text.replace("</body>", f"  {SCRIPT_TAG}\n</body>")

        headers = dict(response.headers)
        headers.pop("content-length", None)
        return HTMLResponse(text, status_code=response.status_code, headers=headers)

    return app
