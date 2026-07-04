"""
editor.py
----------
Stage 4. Two parts:

1. Deterministic checks (no LLM) — heading structure, duplicate sentences
   across sections (a real failure mode of section-by-section generation:
   the writer doesn't see the whole draft at once, so it can accidentally
   repeat a point), and a readability score.

2. An LLM editing pass that gets the FULL assembled draft (unlike the
   writer, which only ever saw one section at a time) and can smooth
   transitions, cut redundancy, and fix tone consistency issues that only
   become visible once every section exists together.
"""

import re
import textstat
from content_pipeline.llm_client import call_llm

EDITOR_SYSTEM_PROMPT = """You are a meticulous copy editor. You improve flow and cut redundancy without changing the article's meaning or removing substantive content. You preserve the Markdown structure exactly as given — same headings, same order. You output the full revised article and nothing else — no commentary, no "here's the edited version"."""


def assemble_draft(intro: str, sections: list, conclusion: str) -> str:
    parts = [intro.strip()]
    for section in sections:
        parts.append(f"## {section['title']}\n\n{section['body'].strip()}")
    parts.append(conclusion.strip())
    return "\n\n".join(parts)


def find_duplicate_sentences(draft_text: str, min_length: int = 40) -> list:
    # Strip markdown heading lines first — otherwise "## Section B" gets
    # glued onto the start of the next sentence during splitting, making
    # an otherwise-identical repeated sentence look unique and slip past
    # detection right after a heading. Caught during testing.
    text_without_headings = re.sub(r"^#{1,6}\s+.*$", "", draft_text, flags=re.MULTILINE)

    sentences = re.split(r"(?<=[.!?])\s+", text_without_headings)
    seen = {}
    duplicates = []
    for sentence in sentences:
        normalized = re.sub(r"\s+", " ", sentence.strip().lower())
        if len(normalized) < min_length:
            continue
        if normalized in seen:
            duplicates.append(sentence.strip())
        else:
            seen[normalized] = True
    return duplicates


def check_heading_structure(draft_text: str, expected_titles: list) -> list:
    issues = []
    found_headings = re.findall(r"^##\s+(.+)$", draft_text, re.MULTILINE)
    for title in expected_titles:
        if title not in found_headings:
            issues.append(f"Expected section heading missing from draft: '{title}'")
    return issues


def compute_readability(draft_text: str) -> dict:
    plain_text = re.sub(r"[#*_`\[\]()]", "", draft_text)
    word_count = len(plain_text.split())
    if word_count < 50:
        return {"word_count": word_count, "flesch_reading_ease": None, "flesch_kincaid_grade": None}
    return {
        "word_count": word_count,
        "flesch_reading_ease": round(textstat.flesch_reading_ease(plain_text), 1),
        "flesch_kincaid_grade": round(textstat.flesch_kincaid_grade(plain_text), 1),
    }


def build_edit_prompt(draft_text: str, deterministic_notes: list) -> str:
    notes_block = ""
    if deterministic_notes:
        notes_block = "Automated checks flagged these specific issues — address them:\n" + "\n".join(f"- {n}" for n in deterministic_notes) + "\n\n"
    return f"""{notes_block}Here is a full article draft, written section by section (so it may have minor redundancy or rough transitions between sections that weren't visible to whoever wrote each part individually). Edit it for flow, cut any redundant sentences or repeated points, smooth transitions between sections, and fix any tone inconsistencies — but preserve the Markdown heading structure exactly and don't cut substantive content.

---
{draft_text}
---

Output the full revised article in Markdown, headings intact, nothing else."""


def edit_draft(draft_text: str, expected_titles: list, provider: str = None) -> dict:
    duplicate_sentences = find_duplicate_sentences(draft_text)
    heading_issues = check_heading_structure(draft_text, expected_titles)
    readability_before = compute_readability(draft_text)

    deterministic_notes = heading_issues.copy()
    if duplicate_sentences:
        deterministic_notes.append(f"{len(duplicate_sentences)} near-duplicate sentence(s) found across sections — remove the repeats")

    prompt = build_edit_prompt(draft_text, deterministic_notes)
    revised_text = call_llm(prompt, system=EDITOR_SYSTEM_PROMPT, provider=provider, max_tokens=4000, temperature=0.3)

    readability_after = compute_readability(revised_text)

    return {
        "revised_text": revised_text,
        "duplicate_sentences_found": duplicate_sentences,
        "heading_issues_found": heading_issues,
        "readability_before": readability_before,
        "readability_after": readability_after,
    }
