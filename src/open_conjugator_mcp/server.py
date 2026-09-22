from __future__ import annotations

from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field
from starlette.requests import Request
from starlette.responses import JSONResponse

from .service import service


READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

server = MCPServer(
    name="open-conjugator-mcp",
    title="Open Conjugator MCP",
    description=(
        "Independent, read-only Arabic-first morphology server powered by CAMeL Tools, "
        "CAMeL Morph, and UniMorph."
    ),
    version="2.0.0",
    instructions=(
        "Use language='ar' by default. Arabic output preserves diacritics and RTL text. "
        "identify_verb_form can return multiple valid out-of-context analyses; do not discard "
        "ambiguity. All data is local and read-only."
    ),
)

Text = Annotated[str, Field(min_length=1, max_length=100, strip_whitespace=True)]
LanguageText = Annotated[str, Field(min_length=2, max_length=30, strip_whitespace=True)]


@server.tool(
    title="Conjugate a verb",
    description=(
        "Return a structured conjugation paradigm. Arabic uses CAMeL Morph generation and includes "
        "roots, patterns, voice, mood, person, full diacritics, and optional Buckwalter transliteration."
    ),
    annotations=READ_ONLY,
    structured_output=True,
)
def conjugate_verb(
    verb: Text,
    language: LanguageText = "ar",
    include_transliteration: bool = True,
    include_passive: bool = True,
    max_forms: Annotated[int, Field(ge=1, le=500)] = 250,
) -> dict[str, Any]:
    return service.conjugate(
        verb, language, include_transliteration, include_passive, max_forms
    )


@server.tool(
    title="Identify an inflected verb form",
    description=(
        "Analyze a surface form and return every compatible lemma and morphological reading. "
        "For Arabic, vocalized and unvocalized text and Buckwalter input are accepted."
    ),
    annotations=READ_ONLY,
    structured_output=True,
)
def identify_verb_form(
    verb_form: Text,
    language: LanguageText = "ar",
    include_transliteration: bool = True,
) -> dict[str, Any]:
    return service.identify(verb_form, language, include_transliteration)


@server.tool(
    title="Search for a verb",
    description=(
        "Search by lemma, inflected form, Arabic vocalization, Buckwalter transliteration, or a "
        "small spelling error. Returns exact analyses before fuzzy suggestions."
    ),
    annotations=READ_ONLY,
    structured_output=True,
)
def search_verb(
    query: Text,
    language: LanguageText = "ar",
    include_transliteration: bool = True,
    max_results: Annotated[int, Field(ge=1, le=50)] = 10,
) -> dict[str, Any]:
    return service.search(query, language, include_transliteration, max_results)


@server.tool(
    title="Get verb models and patterns",
    description=(
        "For Arabic, return CAMeL Morph roots, surface patterns, abstract patterns, and related "
        "lemmas. For UniMorph languages, return the attested paradigm feature bundles."
    ),
    annotations=READ_ONLY,
    structured_output=True,
)
def get_verb_models(
    language: LanguageText = "ar",
    query: Annotated[str | None, Field(max_length=100)] = None,
    limit: Annotated[int, Field(ge=1, le=100)] = 25,
) -> dict[str, Any]:
    return service.models(language, query, limit)


@server.tool(
    title="Get conjugation help",
    description=(
        "Return concise help for the installed morphology engine and links to the official CAMeL "
        "Tools, CAMeL Morph, or UniMorph documentation."
    ),
    annotations=READ_ONLY,
    structured_output=True,
)
def get_conjugation_help(
    language: LanguageText = "ar",
    topic: Annotated[str | None, Field(max_length=50)] = None,
) -> dict[str, Any]:
    return service.help(language, topic)


@server.tool(
    title="Get supported languages",
    description="List exactly the locally installed languages, engines, aliases, direction, and capabilities.",
    annotations=READ_ONLY,
    structured_output=True,
)
def get_supported_languages() -> dict[str, Any]:
    return service.supported_languages()


@server.custom_route("/health", methods=["GET"], include_in_schema=False)
async def health(_: Request) -> JSONResponse:
    readiness = service.readiness()
    return JSONResponse(readiness, status_code=200 if readiness["status"] == "ok" else 503)

