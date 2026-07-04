"""
seo_specialist.py
-------------------
Stage 5. Mostly deterministic, with two small targeted LLM calls (title
and meta description) that get validated against length rules and
regenerated on failure — this is the one place worth spending an extra
LLM call to guarantee a hard constraint, since a title over 60 characters
gets truncated in search results regardless of how good the writing is.

Also generates FAQ content (LLM) and turns it into ready-to-publish
FAQPage + Article JSON-LD (deterministic), and does keyword density /
internal-linking analysis (fully deterministic).
"""

import re
import json
from datetime import date
from content_pipeline.llm_client import call_llm

TITLE_MIN, TITLE_MAX = 30, 60
META_MIN, META_MAX = 70, 160
MAX_RETRIES = 2

SEO_SYSTEM_PROMPT = """You are an SEO specialist writing metadata that is accurate to the article content, naturally incorporates the target keyword, and strictly respects length constraints. You never write clickbait that misrepresents the content."""


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")


def generate_title(topic: str, target_keyword: str, provider: str = None) -> dict:
    prompt = f'Write a compelling, accurate SEO title tag for an article about "{topic}", naturally including the keyword "{target_keyword}". STRICT constraint: between {TITLE_MIN} and {TITLE_MAX} characters total, counting spaces. Output ONLY the title text, nothing else — no quotes, no explanation.'

    for attempt in range(MAX_RETRIES + 1):
        title = call_llm(prompt, system=SEO_SYSTEM_PROMPT, provider=provider, max_tokens=60, temperature=0.6).strip().strip('"')
        if TITLE_MIN <= len(title) <= TITLE_MAX:
            return {"title": title, "length": len(title), "within_range": True, "attempts": attempt + 1}
        prompt = f'Your previous attempt was {len(title)} characters — {"too long" if len(title) > TITLE_MAX else "too short"}. Try again: a title for "{topic}" including "{target_keyword}", STRICTLY between {TITLE_MIN}-{TITLE_MAX} characters. Output ONLY the title.'

    truncated = title[:TITLE_MAX].rsplit(" ", 1)[0]
    return {"title": truncated, "length": len(truncated), "within_range": len(truncated) >= TITLE_MIN, "attempts": MAX_RETRIES + 1, "note": "fell back to deterministic truncation after retries"}


def generate_meta_description(topic: str, target_keyword: str, article_summary: str, provider: str = None) -> dict:
    prompt = f'Write an SEO meta description for an article about "{topic}" (keyword: "{target_keyword}"). Article summary: {article_summary[:500]}. STRICT constraint: between {META_MIN} and {META_MAX} characters. Output ONLY the meta description text.'

    for attempt in range(MAX_RETRIES + 1):
        meta = call_llm(prompt, system=SEO_SYSTEM_PROMPT, provider=provider, max_tokens=100, temperature=0.6).strip().strip('"')
        if META_MIN <= len(meta) <= META_MAX:
            return {"meta_description": meta, "length": len(meta), "within_range": True, "attempts": attempt + 1}
        prompt = f'Your previous attempt was {len(meta)} characters — {"too long" if len(meta) > META_MAX else "too short"}. Try again: STRICTLY between {META_MIN}-{META_MAX} characters. Output ONLY the meta description.'

    truncated = meta[:META_MAX].rsplit(" ", 1)[0]
    return {"meta_description": truncated, "length": len(truncated), "within_range": len(truncated) >= META_MIN, "attempts": MAX_RETRIES + 1, "note": "fell back to deterministic truncation after retries"}


def generate_faqs(topic: str, article_text: str, num_faqs: int = 5, provider: str = None) -> list:
    prompt = f"""Based on this article about "{topic}", generate {num_faqs} frequently-asked-questions with concise answers (2-4 sentences each) that would be genuinely useful as an FAQ section — questions a reader would actually have after reading this, not generic questions.

Article excerpt:
{article_text[:4000]}

Output as a JSON array only, no other text, in this exact format:
[{{"question": "...", "answer": "..."}}, ...]"""

    response = call_llm(prompt, system=SEO_SYSTEM_PROMPT, provider=provider, max_tokens=1200, temperature=0.5)
    json_match = re.search(r"\[.*\]", response, re.DOTALL)
    if not json_match:
        return []
    try:
        faqs = json.loads(json_match.group(0))
        return [f for f in faqs if isinstance(f, dict) and "question" in f and "answer" in f]
    except json.JSONDecodeError:
        return []


def build_article_schema(title: str, meta_description: str, url: str, author_name: str, site_name: str, word_count: int) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": meta_description,
        "url": url,
        "author": {"@type": "Person", "name": author_name},
        "publisher": {"@type": "Organization", "name": site_name},
        "datePublished": date.today().isoformat(),
        "dateModified": date.today().isoformat(),
        "wordCount": word_count,
    }


def build_faq_schema(faqs: list) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": faq["question"],
                "acceptedAnswer": {"@type": "Answer", "text": faq["answer"]},
            }
            for faq in faqs
        ],
    }


def analyze_keyword_usage(article_text: str, target_keyword: str) -> dict:
    plain_text = re.sub(r"[#*_`\[\]()]", " ", article_text).lower()
    word_count = len(plain_text.split())
    keyword_lower = target_keyword.lower()
    occurrences = len(re.findall(re.escape(keyword_lower), plain_text))
    density = round((occurrences / word_count) * 100, 2) if word_count else 0

    if density > 3:
        assessment = "Over-optimized — keyword density unusually high, risks reading as keyword stuffing"
    elif density < 0.2:
        assessment = "Under-optimized — keyword barely appears, consider working it in more naturally"
    else:
        assessment = "Healthy range"

    return {"occurrences": occurrences, "word_count": word_count, "density_pct": density, "assessment": assessment}


def suggest_internal_links(article_text: str, existing_pages: list) -> list:
    """existing_pages: list of {url, title} for pages already on the site.
    Simple keyword-overlap heuristic — not LLM-based, so it's fast, free,
    and fully deterministic/testable. Flags a page as a linking candidate
    if a meaningful chunk of its title words appear in the article body."""
    if not existing_pages:
        return []

    plain_text = re.sub(r"[#*_`\[\]()]", " ", article_text).lower()
    suggestions = []
    for page in existing_pages:
        title_words = {w for w in re.findall(r"[a-z0-9]+", page["title"].lower()) if len(w) > 3}
        if not title_words:
            continue
        matches = sum(1 for w in title_words if w in plain_text)
        overlap_ratio = matches / len(title_words)
        if overlap_ratio >= 0.5:
            suggestions.append({"url": page["url"], "title": page["title"], "overlap_ratio": round(overlap_ratio, 2)})

    return sorted(suggestions, key=lambda s: -s["overlap_ratio"])
