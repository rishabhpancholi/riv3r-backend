from uuid import uuid4
from time import perf_counter
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

class RequestTimeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = perf_counter()
        request.state.start_time = start
        response = await call_next(request)
        response.headers["X-Process-Time"] = f"{(perf_counter() - start)*1000:.2f} ms"
        return response

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = uuid4().hex
        request.state.request_id = req_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response