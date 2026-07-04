"""
pipeline.py
------------
Orchestrates the full run: researcher -> outliner -> writer -> editor ->
SEO specialist -> assembler. Each stage's output feeds the next, and
everything is captured for the transparency log.
"""

from content_pipeline.researcher import generate_research_brief
from content_pipeline.outliner import generate_outline
from content_pipeline.writer import write_article
from content_pipeline.editor import assemble_draft, edit_draft
from content_pipeline.seo_specialist import (
    slugify, generate_title, generate_meta_description, generate_faqs,
    build_article_schema, build_faq_schema, analyze_keyword_usage, suggest_internal_links,
)
from content_pipeline.assembler import build_final_markdown, build_seo_metadata, build_pipeline_log


def run_pipeline(topic: str, target_keyword: str, tone: str = "professional", audience: str = "general readers",
                  word_count_target: int = 1500, section_count: int = 6, competitor_urls: list = None,
                  existing_pages: list = None, author_name: str = "Author", site_name: str = "Site",
                  base_url: str = "https://example.com", num_faqs: int = 5, provider: str = None,
                  progress_callback=None) -> dict:
    competitor_urls = competitor_urls or []
    existing_pages = existing_pages or []

    def log(msg):
        if progress_callback:
            progress_callback(msg)

    log("[1/6] Researcher: generating brief...")
    research = generate_research_brief(topic, target_keyword, audience, competitor_urls, provider=provider)

    log("[2/6] Outliner: structuring sections...")
    outline = generate_outline(topic, target_keyword, research["brief_text"], section_count, provider=provider)
    if not outline["sections"]:
        raise RuntimeError("Outliner produced zero parseable sections — check the raw LLM output in outline['raw_text']")

    section_word_count = max(100, word_count_target // (len(outline["sections"]) + 2))

    log(f"[3/6] Writer: drafting intro + {len(outline['sections'])} sections + conclusion...")
    draft = write_article(topic, target_keyword, outline["sections"], tone, audience, section_word_count, provider=provider)

    assembled_draft = assemble_draft(draft["intro"], draft["sections"], draft["conclusion"])

    log("[4/6] Editor: reviewing full draft...")
    expected_titles = [s["title"] for s in outline["sections"]]
    editor_result = edit_draft(assembled_draft, expected_titles, provider=provider)
    final_body = editor_result["revised_text"]

    log("[5/6] SEO Specialist: generating metadata, schema, and FAQs...")
    title_result = generate_title(topic, target_keyword, provider=provider)
    meta_result = generate_meta_description(topic, target_keyword, draft["intro"], provider=provider)
    slug = slugify(title_result["title"])
    faqs = generate_faqs(topic, final_body, num_faqs=num_faqs, provider=provider)
    keyword_analysis = analyze_keyword_usage(final_body, target_keyword)
    internal_link_suggestions = suggest_internal_links(final_body, existing_pages)

    word_count = editor_result["readability_after"]["word_count"] or editor_result["readability_before"]["word_count"]
    article_url = f"{base_url.rstrip('/')}/{slug}"
    article_schema = build_article_schema(title_result["title"], meta_result["meta_description"], article_url, author_name, site_name, word_count)
    faq_schema = build_faq_schema(faqs) if faqs else {"@type": "FAQPage", "mainEntity": []}

    log("[6/6] Assembler: writing final deliverables...")
    final_markdown = build_final_markdown(title_result["title"], meta_result["meta_description"], slug, target_keyword, final_body, faqs, word_count, author_name)
    seo_metadata = build_seo_metadata(title_result, meta_result, slug, article_schema, faq_schema, keyword_analysis, internal_link_suggestions)
    pipeline_log = build_pipeline_log(topic, target_keyword, research, outline, editor_result, title_result, meta_result, keyword_analysis, internal_link_suggestions)

    return {
        "final_markdown": final_markdown,
        "seo_metadata": seo_metadata,
        "pipeline_log": pipeline_log,
        "raw": {"research": research, "outline": outline, "draft": draft, "editor_result": editor_result},
    }
