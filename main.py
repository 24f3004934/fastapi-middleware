
import time
import uuid
from collections import defaultdict, deque
from threading import Lock

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

EMAIL = "24f3004934@ds.study.iitm.ac.in"
ALLOWED_ORIGINS = [
    "https://app-b3pq17.example.com",
    "https://exam.sanand.workers.dev",
]

app = FastAPI()

buckets = defaultdict(deque)
lock = Lock()

@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)

    client = request.headers.get("X-Client-ID", "anonymous")
    now = time.monotonic()

    with lock:
        bucket = buckets[client]
        while bucket and now - bucket[0] >= 10:
            bucket.popleft()

        if len(bucket) >= 15:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"}
            )
        bucket.append(now)

    return await call_next(request)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/ping")
async def ping(request: Request):
    return {
        "email": EMAIL,
        "request_id": request.state.request_id
    }


# Outermost middleware handles CORS, including 429 responses.
app = CORSMiddleware(
    app,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)
