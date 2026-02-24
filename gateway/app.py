import os
from fastapi import FastAPI, Request, Response
import httpx

app = FastAPI()

SOCKS5_PROXY = os.getenv("SOCKS5_PROXY")
OPENAI_BASE = os.getenv("OPENAI_BASE", "https://api.openai.com")

if not SOCKS5_PROXY:
    raise RuntimeError("SOCKS5_PROXY env variable not set")

client = httpx.AsyncClient(
    proxy=SOCKS5_PROXY,
    timeout=60.0,
)

@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(path: str, request: Request):
    url = f"{OPENAI_BASE}/v1/{path}"

    body = await request.body()

    headers = dict(request.headers)
    headers.pop("host", None)

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