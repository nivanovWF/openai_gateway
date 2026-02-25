import logging
import os
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
import httpx

app = FastAPI()

# === ENV ===
SOCKS5_PROXY = os.getenv("SOCKS5_PROXY")
OPENAI_BASE = os.getenv("OPENAI_BASE", "https://api.openai.com")

if not SOCKS5_PROXY:
    raise RuntimeError("SOCKS5_PROXY env variable not set")

# === Logging ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gateway")

# === HTTP Client ===
client = httpx.AsyncClient(
    proxy=SOCKS5_PROXY,
    timeout=httpx.Timeout(
        connect=15.0,
        read=300.0,
        write=30.0,
        pool=10.0
    ),
    limits=httpx.Limits(
        max_connections=100,
        max_keepalive_connections=50
    ),
)

# Hop-by-hop headers нельзя проксировать
EXCLUDED_HEADERS = {
    "content-encoding",
    "transfer-encoding",
    "connection",
    "keep-alive",
}


@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(path: str, request: Request):

    url = f"{OPENAI_BASE}/v1/{path}"
    logger.info(f"{request.method} {url}")

    body = await request.body()

    # Копируем headers запроса
    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("transfer-encoding", None)

    # Определяем streaming
    is_stream = (
        "stream=true" in str(request.query_params).lower()
        or request.headers.get("accept") == "text/event-stream"
    )

    try:

        # ================= STREAMING =================
        if is_stream:
            async with client.stream(
                request.method,
                url,
                content=body,
                headers=headers,
            ) as resp:

                response_headers = {
                    k: v for k, v in resp.headers.items()
                    if k.lower() not in EXCLUDED_HEADERS
                }

                return StreamingResponse(
                    resp.aiter_raw(),
                    status_code=resp.status_code,
                    headers=response_headers,
                )

        # ================= NORMAL RESPONSE =================
        else:
            resp = await client.request(
                request.method,
                url,
                content=body,
                headers=headers,
            )

            response_headers = {
                k: v for k, v in resp.headers.items()
                if k.lower() not in EXCLUDED_HEADERS
            }

            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=response_headers,
            )

    except httpx.RequestError as e:
        logger.error(f"Upstream request error: {e}")
        return Response(
            content=str(e),
            status_code=502,
        )