"""Web-search capability — provider-agnostic, with selectable FREE backends.

The army's "no invented facts" doctrine (Constitution Art. I) needs LIVE web access. OpenAI's
hosted `WebSearchTool` only works when the brain runs on OpenAI's platform — it breaks on
Gemini / Anthropic / OpenRouter. This module decouples the **brain model** (chosen in models.py)
from the **search backend**, so you can test any brain while keeping search free.

`web_tools()` is the single source of truth for the web capability every unit receives. Pick a
backend with `AK_SEARCH` (or let it auto-detect from the keys present):

  AK_WEBSEARCH=0            -> [] (no web search; units must say "unknown")
  AK_SEARCH=ddg            -> DuckDuckGo (ddgs)        FREE, no key, no quota (unofficial)
  AK_SEARCH=tavily         -> Tavily (TAVILY_API_KEY)  free 1k/mo, LLM-clean output
  AK_SEARCH=gemini         -> Gemini grounding (GEMINI_API_KEY) free 1.5k/day
  AK_SEARCH=openai         -> OpenAI hosted WebSearchTool (OpenAI brain only)
  (unset) -> auto: TAVILY_API_KEY -> tavily ; else GEMINI_API_KEY -> gemini ; else OpenAI hosted

Each backend is a provider-agnostic function-tool: it works with ANY brain model.
"""

import os

from agents import WebSearchTool, function_tool

# Gemini / OpenRouter / any OpenAI-compatible endpoint implements /chat/completions, NOT the
# Agents SDK's default /responses API (which 404s there). When a custom OPENAI_BASE_URL is set,
# force chat-completions. (No-op under the test stub / if the symbol is absent.)
if os.getenv("OPENAI_BASE_URL"):
    try:
        from agents import set_default_openai_api

        set_default_openai_api("chat_completions")
    except (ImportError, AttributeError):
        pass


def _gemini_key():
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


def _websearch_disabled() -> bool:
    return os.getenv("AK_WEBSEARCH", "1").strip().lower() in ("0", "false", "no", "off")


@function_tool
def gemini_web_search(query: str) -> str:
    """Search the live web (Google Search via Gemini grounding) and return a concise, SOURCED
    answer. Use for any real fact — market sizes, benchmarks, dates, competitor claims. Returns the
    grounded answer followed by source URLs; if nothing is found or the tool is unavailable, say so
    so the caller can mark the fact 'unknown' (never invent it)."""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return ('web_search unavailable: install the Gemini extra '
                '(pip install "agency-kit[gemini]") or pick another AK_SEARCH backend.')
    key = _gemini_key()
    if not key:
        return "web_search unavailable: set GEMINI_API_KEY (Google AI Studio) or AK_WEBSEARCH=0."
    model = os.getenv("AK_SEARCH_MODEL", "gemini-2.5-flash")
    try:
        client = genai.Client(api_key=key)
        resp = client.models.generate_content(
            model=model,
            contents=query,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            ),
        )
        answer = (getattr(resp, "text", None) or "").strip()
        sources = []
        for cand in (getattr(resp, "candidates", None) or []):
            gm = getattr(cand, "grounding_metadata", None)
            for chunk in (getattr(gm, "grounding_chunks", None) or []):
                web = getattr(chunk, "web", None)
                uri = getattr(web, "uri", None) if web else None
                if uri:
                    title = getattr(web, "title", "") or uri
                    line = f"- {title}: {uri}"
                    if line not in sources:
                        sources.append(line)
        if sources:
            answer += "\n\nSources:\n" + "\n".join(sources)
        return answer or "No grounded result found."
    except Exception as e:  # network / quota / model errors — third-party libs throw unpredictable types; caller marks 'unknown'
        return f"web_search error: {type(e).__name__}: {str(e)[:200]}"


@function_tool
def tavily_web_search(query: str) -> str:
    """Search the live web (Tavily, built for LLM agents) and return a concise, SOURCED answer plus
    source URLs. Use for any real fact. If nothing is found or the tool is unavailable, say so so
    the caller can mark the fact 'unknown' (never invent it)."""
    try:
        from tavily import TavilyClient
    except ImportError:
        return ('web_search unavailable: install the Tavily extra '
                '(pip install "agency-kit[tavily]") or pick another AK_SEARCH backend.')
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        return "web_search unavailable: set TAVILY_API_KEY (free at tavily.com) or AK_WEBSEARCH=0."
    try:
        client = TavilyClient(api_key=key)
        r = client.search(query, max_results=5, include_answer=True)
        answer = (r.get("answer") or "").strip()
        sources = [f"- {x.get('title', '')}: {x.get('url', '')}" for x in (r.get("results") or [])]
        out = answer
        if sources:
            out += ("\n\n" if out else "") + "Sources:\n" + "\n".join(sources)
        return out or "No result found."
    except Exception as e:
        return f"web_search error: {type(e).__name__}: {str(e)[:200]}"


@function_tool
def duckduckgo_web_search(query: str) -> str:
    """Search the live web (DuckDuckGo — free, no API key) and return the top results (title,
    snippet, URL) for the caller to cite. Use for any real fact. If nothing is found or the tool is
    unavailable, say so so the caller can mark the fact 'unknown' (never invent it)."""
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS  # older package name
    except ImportError:
        return ('web_search unavailable: install the DuckDuckGo extra '
                '(pip install "agency-kit[ddg]") or pick another AK_SEARCH backend.')
    try:
        results = []
        with DDGS() as ddg:
            for r in ddg.text(query, max_results=5):
                results.append(r)
        if not results:
            return "No result found."
        lines = []
        for r in results:
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href") or r.get("url", "")
            lines.append(f"- {title}: {body}\n  {href}")
        return "Results (DuckDuckGo):\n" + "\n".join(lines)
    except Exception as e:
        return f"web_search error: {type(e).__name__}: {str(e)[:200]}"


_BACKENDS = {
    "ddg": lambda: [duckduckgo_web_search],
    "duckduckgo": lambda: [duckduckgo_web_search],
    "tavily": lambda: [tavily_web_search],
    "gemini": lambda: [gemini_web_search],
    "openai": lambda: [WebSearchTool()],
}


def web_tools() -> list:
    """The web-search capability every unit receives, selected by env. Single source of truth.

    Explicit `AK_SEARCH` wins; otherwise auto-detect from the keys present (Tavily, then Gemini),
    falling back to OpenAI's hosted WebSearchTool. `AK_WEBSEARCH=0` disables web search entirely.
    """
    if _websearch_disabled():
        return []
    choice = os.getenv("AK_SEARCH", "").strip().lower()
    if choice in _BACKENDS:
        return _BACKENDS[choice]()
    # auto-detect a provider-agnostic backend (DDG is opt-in only — unofficial/less reliable)
    if os.getenv("TAVILY_API_KEY"):
        return [tavily_web_search]
    if _gemini_key():
        return [gemini_web_search]
    # OpenAI's hosted WebSearchTool only works on OpenAI's own platform. If a custom base URL is
    # set (Gemini / OpenRouter / any compat endpoint), fall back to DuckDuckGo (free function-tool)
    # rather than a hosted tool that the endpoint can't run.
    if os.getenv("OPENAI_BASE_URL"):
        return [duckduckgo_web_search]
    return [WebSearchTool()]
