import os
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
import httpx

app = FastAPI()

SOCKS5_PROXY = os.getenv("SOCKS5_PROXY")
OPENAI_BASE = os.getenv("OPENAI_BASE", "https://api.openai.com")

if not SOCKS5_PROXY:
    raise RuntimeError("SOCKS5_PROXY env variable not set")

client = httpx.AsyncClient(
    proxy=SOCKS5_PROXY,
    timeout=httpx.Timeout(
        connect=10.0,
        read=60.0,
        write=10.0,
        pool=5.0
    ),
    limits=httpx.Limits(
        max_connections=50,
        max_keepalive_connections=20
    )
)

@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(path: str, request: Request):
    url = f"{OPENAI_BASE}/v1/{path}"

    body = await request.body()

    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("transfer-encoding", None)

    is_stream = (
        "stream" in str(request.query_params).lower()
        or request.headers.get("accept") == "text/event-stream"
    )

    is_stream = (
        "stream" in str(request.query_params).lower()
        or request.headers.get("accept") == "text/event-stream"
    )

    if is_stream:
        async with client.stream(
            request.method,
            url,
            content=body,
            headers=headers,
        ) as resp:

            return StreamingResponse(
                resp.aiter_bytes(),
                status_code=resp.status_code,
                headers=dict(resp.headers),
            )

    else:
        resp = await client.request(
            request.method,
            url,
            content=body,
            headers=headers,
        )

        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=dict(resp.headers),
        )