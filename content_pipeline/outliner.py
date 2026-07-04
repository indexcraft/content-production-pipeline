"""
outliner.py
------------
Stage 2. Turns the research brief into a structured outline: H2/H3
sections with a one-line brief for what each section should accomplish.
Parses the LLM's markdown-style outline into a structured list so the
writer stage can generate section-by-section (staying within any single
call's token limits, and keeping each section focused).
"""

import re
from content_pipeline.llm_client import call_llm

OUTLINER_SYSTEM_PROMPT = """You are a content strategist who turns research briefs into structured article outlines. You produce outlines that flow logically, avoid redundant sections, and match how the target audience actually thinks about a topic — not a generic template."""

SECTION_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
NOTE_RE = re.compile(r"^\s*Brief:\s*(.+)$", re.MULTILINE | re.IGNORECASE)


def build_outline_prompt(topic: str, target_keyword: str, research_brief: str, target_section_count: int) -> str:
    return f"""Topic: {topic}
Target keyword: {target_keyword}

Research brief:
{research_brief}

Produce an article outline with approximately {target_section_count} H2 sections (you can adjust slightly if the topic genuinely needs more or fewer — don't force a count that doesn't fit). For each section, use this exact format:

## Section Title Here
Brief: One sentence describing what this section should cover and accomplish.

## Next Section Title
Brief: One sentence for this section.

Do not include an introduction or conclusion as separate H2 sections — those will be handled separately. Focus only on the body sections covering the subtopics from the research brief. Start directly with the first "##" — no preamble."""


def parse_outline(outline_text: str) -> list:
    """Returns a list of {title, brief} dicts, one per section."""
    sections = []
    chunks = SECTION_RE.split(outline_text)[1:]  # first element is pre-amble text, discard
    # chunks alternates [title, body, title, body, ...]
    for i in range(0, len(chunks) - 1, 2):
        title = chunks[i].strip()
        body = chunks[i + 1]
        note_match = NOTE_RE.search(body)
        brief = note_match.group(1).strip() if note_match else ""
        sections.append({"title": title, "brief": brief})
    return sections


def generate_outline(topic: str, target_keyword: str, research_brief: str, target_section_count: int = 6, provider: str = None) -> dict:
    prompt = build_outline_prompt(topic, target_keyword, research_brief, target_section_count)
    outline_text = call_llm(prompt, system=OUTLINER_SYSTEM_PROMPT, provider=provider, max_tokens=800)
    sections = parse_outline(outline_text)
    return {"raw_text": outline_text, "sections": sections}
