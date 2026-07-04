"""
researcher.py
--------------
Stage 1 of the pipeline. Plays the "researcher" role: given a topic and
target keyword, produces a research brief covering search intent, target
audience angle, and the subtopics a thorough piece needs to cover.

If competitor URLs are provided, fetches and summarizes each one first —
this grounds the brief in what's actually already published, rather than
having the LLM guess at a topic landscape from training data alone.
"""

import requests
from bs4 import BeautifulSoup
from content_pipeline.llm_client import call_llm

RESEARCHER_SYSTEM_PROMPT = """You are a senior content researcher at a B2B content agency. You specialize in identifying what a genuinely comprehensive, non-generic article needs to cover for a given topic and audience. You are concise and specific — you never pad your output with generic advice."""


def fetch_competitor_summary(url: str, timeout: int = 20) -> dict:
    """Fetches a competitor URL and returns its title + a truncated text
    extract, ready to feed into the research prompt. Fails soft — a
    competitor page that can't be fetched is just skipped, not fatal."""
    try:
        resp = requests.get(url, headers={"User-Agent": "ContentPipelineResearcher/1.0"}, timeout=timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else url

        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)

        h2s = [h.get_text(strip=True) for h in soup.find_all(["h2", "h3"])][:15]

        return {"url": url, "title": title, "text_excerpt": text[:2500], "headings": h2s, "error": None}
    except Exception as e:
        return {"url": url, "title": url, "text_excerpt": "", "headings": [], "error": str(e)}


def build_research_prompt(topic: str, target_keyword: str, target_audience: str, competitor_summaries: list) -> str:
    competitor_block = ""
    if competitor_summaries:
        parts = []
        for c in competitor_summaries:
            if c["error"]:
                continue
            headings_text = "; ".join(c["headings"]) if c["headings"] else "no headings extracted"
            parts.append(f"- {c['title']} ({c['url']})\n  Headings covered: {headings_text}")
        if parts:
            competitor_block = "Existing published content on this topic (for context on what's already covered — your job is to identify gaps and a better angle, not to copy structure):\n" + "\n".join(parts) + "\n\n"

    return f"""Topic: {topic}
Target keyword: {target_keyword}
Target audience: {target_audience}

{competitor_block}Produce a research brief with these sections:

1. Search intent (1-2 sentences: what is someone searching this keyword actually trying to accomplish?)
2. Target audience angle (1-2 sentences: what does THIS specific audience need that a generic version of this article wouldn't give them?)
3. Subtopics to cover (a bulleted list of 6-10 specific subtopics/questions a genuinely thorough article needs to address — be specific to this topic, not generic "introduction/conclusion" structure)
4. Differentiation angle (1-2 sentences: given what's already published on this topic, what's an angle or emphasis that would make this piece stand out rather than being one more generic version)

Be concise and specific throughout. No preamble, no "Sure, here's the brief" — start directly with section 1."""


def generate_research_brief(topic: str, target_keyword: str, target_audience: str = "general readers",
                             competitor_urls: list = None, provider: str = None) -> dict:
    competitor_urls = competitor_urls or []
    competitor_summaries = [fetch_competitor_summary(url) for url in competitor_urls]

    prompt = build_research_prompt(topic, target_keyword, target_audience, competitor_summaries)
    brief_text = call_llm(prompt, system=RESEARCHER_SYSTEM_PROMPT, provider=provider, max_tokens=1200)

    return {"brief_text": brief_text, "competitor_summaries": competitor_summaries}
