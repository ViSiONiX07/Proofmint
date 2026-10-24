"""ASGI-level request body limit for multipart guideline uploads."""

import json

from app.core.config import settings


class GuidelineUploadBodyLimitMiddleware:
    """Stop oversized multipart bodies before Starlette parses/spools uploads."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return

        request_path = scope.get("path")
        if request_path == f"{settings.API_V1_STR}/guidelines/ingest":
            maximum = settings.GUIDELINE_MAX_REQUEST_BYTES + settings.GUIDELINE_MAX_MULTIPART_OVERHEAD_BYTES
        elif request_path in {
            f"{settings.API_V1_STR}/facts/import",
            f"{settings.API_V1_STR}/terms/import",
        }:
            maximum = settings.CSV_IMPORT_MAX_FILE_BYTES + settings.CSV_IMPORT_MAX_MULTIPART_OVERHEAD_BYTES
        else:
            await self.app(scope, receive, send)
            return
        received = 0
        rejected = False

        async def send_too_large():
            body = json.dumps({"detail": "Multipart request body exceeds the configured upload limit."}).encode()
            await send({
                "type": "http.response.start",
                "status": 413,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
            })
            await send({"type": "http.response.body", "body": body})

        async def limited_receive():
            nonlocal received, rejected
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > maximum:
                    rejected = True
                    await send_too_large()
                    raise _RequestBodyTooLarge
            return message

        async def limited_send(message):
            # Multipart parsing translates receive exceptions to a 400 response.
            # The 413 has already been sent, so suppress that secondary response.
            if not rejected:
                await send(message)

        try:
            await self.app(scope, limited_receive, limited_send)
        except _RequestBodyTooLarge:
            # Some ASGI apps do not catch the receive sentinel themselves.
            pass


class _RequestBodyTooLarge(Exception):
    pass
