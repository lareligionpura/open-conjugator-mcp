from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client


ROOT = Path(__file__).resolve().parents[1]


def unused_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.mark.asyncio
async def test_streamable_http_transport() -> None:
    port = unused_port()
    environment = dict(os.environ)
    environment.update(
        {
            "PYTHONPATH": str(ROOT / "src"),
            "HOST": "127.0.0.1",
            "PORT": str(port),
            "MCP_PATH": "/api/open-conjugator-mcp",
        }
    )
    process = subprocess.Popen(
        [sys.executable, "-m", "open_conjugator_mcp", "--transport", "http"],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        health_url = f"http://127.0.0.1:{port}/health"
        for _ in range(80):
            try:
                with urllib.request.urlopen(health_url, timeout=0.5) as response:
                    if response.status == 200:
                        break
            except Exception:
                time.sleep(0.1)
        else:
            raise AssertionError("HTTP server did not become ready")

        url = f"http://127.0.0.1:{port}/api/open-conjugator-mcp"
        async with streamable_http_client(url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(
                    "identify_verb_form", {"verb_form": "يَكْتُبُونَ", "language": "ar"}
                )
                assert result.is_error is not True
                assert result.structured_content["canonicalVerb"] == "كَتَب"
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
