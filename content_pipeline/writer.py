"""
writer.py
----------
Stage 3. Writes the actual article, section by section, following the
outline from stage 2. Writing one section per LLM call (rather than the
whole article in one shot) keeps each section focused on its own brief,
avoids running into output-length limits on longer articles, and lets the
writer stay consistent even when the outline has many sections.

Also writes the introduction and conclusion as their own calls, since
those need the finished section list as context (an intro needs to know
what it's introducing).
"""

from content_pipeline.llm_client import call_llm

WRITER_SYSTEM_PROMPT_TEMPLATE = """You are a content writer producing a {tone} article for {audience}. You write clearly and specifically — you never pad with generic filler sentences, throat-clearing, or restating the obvious. You write in Markdown. You do not include the H2 heading itself in your output — just the body content for that section, since the heading is added separately."""


def build_section_prompt(topic: str, target_keyword: str, section_title: str, section_brief: str,
                          previous_sections_summary: str, target_word_count: int) -> str:
    context = f"Previously written sections (for context, don't repeat this content): {previous_sections_summary}\n\n" if previous_sections_summary else ""
    return f"""Article topic: {topic}
Target keyword (use naturally where relevant, do not force it): {target_keyword}

{context}Now write the section titled "{section_title}".
What this section should cover: {section_brief}

Target length: approximately {target_word_count} words. Write in Markdown (you can use sub-headings with ### if genuinely useful, bullet lists, bold for key terms). Do not include the "## {section_title}" heading itself — start directly with the body content."""


def build_intro_prompt(topic: str, target_keyword: str, section_titles: list, target_word_count: int) -> str:
    sections_list = "\n".join(f"- {t}" for t in section_titles)
    return f"""Article topic: {topic}
Target keyword: {target_keyword}

This article covers these sections:
{sections_list}

Write an introduction (~{target_word_count} words) that hooks the reader, establishes why this topic matters to them, and previews what the article covers — without being a boring "in this article we will discuss" list. Write in Markdown, no heading."""


def build_conclusion_prompt(topic: str, target_keyword: str, section_titles: list, target_word_count: int) -> str:
    sections_list = "\n".join(f"- {t}" for t in section_titles)
    return f"""Article topic: {topic}
Target keyword: {target_keyword}

This article covered these sections:
{sections_list}

Write a conclusion (~{target_word_count} words) that synthesizes the key takeaway (not a bullet-point recap of every section) and ends with a clear next step or forward-looking thought for the reader. Write in Markdown, no heading."""


def write_article(topic: str, target_keyword: str, outline_sections: list, tone: str = "professional",
                   audience: str = "general readers", section_word_count: int = 250, provider: str = None) -> dict:
    system = WRITER_SYSTEM_PROMPT_TEMPLATE.format(tone=tone, audience=audience)
    section_titles = [s["title"] for s in outline_sections]

    intro_prompt = build_intro_prompt(topic, target_keyword, section_titles, section_word_count)
    intro_text = call_llm(intro_prompt, system=system, provider=provider, max_tokens=600)

    written_sections = []
    running_summary_parts = []
    for section in outline_sections:
        summary_so_far = " | ".join(running_summary_parts)
        prompt = build_section_prompt(topic, target_keyword, section["title"], section["brief"], summary_so_far, section_word_count)
        body = call_llm(prompt, system=system, provider=provider, max_tokens=900)
        written_sections.append({"title": section["title"], "body": body})
        running_summary_parts.append(f"{section['title']}: covered")

    conclusion_prompt = build_conclusion_prompt(topic, target_keyword, section_titles, section_word_count)
    conclusion_text = call_llm(conclusion_prompt, system=system, provider=provider, max_tokens=500)

    return {"intro": intro_text, "sections": written_sections, "conclusion": conclusion_text}
