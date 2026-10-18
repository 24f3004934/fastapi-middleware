
import os
import uuid
import time
import requests

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

EMAIL = "24f3004934@ds.study.iitm.ac.in"
REDIS_URL = os.environ["UPSTASH_REDIS_REST_URL"].rstrip("/")
REDIS_TOKEN = os.environ["UPSTASH_REDIS_REST_TOKEN"]

app = FastAPI()



def check_rate_limit(client):
    import hashlib

    now = int(time.time() * 1000)
    key = "fastapi-middleware:rolling:" + hashlib.sha256(
        client.encode()
    ).hexdigest()

    script = """
    local key = KEYS[1]
    local now = tonumber(ARGV[1])
    local window = 10000
    local limit = 15

    redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)

    local count = redis.call('ZCARD', key)

    if count >= limit then
        return 0
    end

    redis.call('ZADD', key, now, ARGV[2])
    redis.call('PEXPIRE', key, window)

    return 1
    """

    response = requests.post(
        REDIS_URL,
        headers={
            "Authorization": f"Bearer {REDIS_TOKEN}",
            "Content-Type": "application/json"
        },
        json=[
            "EVAL",
            script,
            "1",
            key,
            str(now),
            f"{now}:{uuid.uuid4()}"
        ],
        timeout=5
    )

    response.raise_for_status()
    return int(response.json()["result"]) == 1



@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)

    client = request.headers.get("X-Client-ID", "anonymous")

    try:
        allowed = check_rate_limit(client)
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"detail": "Rate limiter unavailable"}
        )

    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"}
        )

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


app = CORSMiddleware(
    app,
    allow_origins=[
        "https://app-b3pq17.example.com",
        "https://exam.sanand.workers.dev"
    ],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"]
)
