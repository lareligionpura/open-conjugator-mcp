from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
async def test_all_six_tools_over_stdio() -> None:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src")
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "open_conjugator_mcp", "--transport", "stdio"],
        cwd=ROOT,
        env=environment,
    )
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            listed = await session.list_tools()
            names = {tool.name for tool in listed.tools}
            assert names == {
                "conjugate_verb",
                "identify_verb_form",
                "search_verb",
                "get_verb_models",
                "get_conjugation_help",
                "get_supported_languages",
            }
            calls = [
                ("conjugate_verb", {"verb": "كتب", "language": "ar"}),
                ("identify_verb_form", {"verb_form": "يَكْتُبُونَ", "language": "ar"}),
                ("search_verb", {"query": "kataba", "language": "ar"}),
                ("get_verb_models", {"query": "كتب", "language": "ar"}),
                ("get_conjugation_help", {"language": "ar"}),
                ("get_supported_languages", {}),
            ]
            for name, arguments in calls:
                result = await session.call_tool(name, arguments)
                assert result.is_error is not True
                assert result.structured_content
