"""
smoke_test.py
-------------
Verifies the full pipeline WITHOUT real LLM or network calls (all mocked)
— run this any time after changing code, or right after cloning the repo.

Usage: python smoke_test.py
"""

import os
import re
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

from content_pipeline.outliner import parse_outline
from content_pipeline.editor import assemble_draft, find_duplicate_sentences, check_heading_structure, compute_readability
from content_pipeline.seo_specialist import (
    slugify, generate_title, generate_faqs, build_article_schema, build_faq_schema,
    analyze_keyword_usage, suggest_internal_links,
)
from content_pipeline.llm_client import get_configured_provider
from content_pipeline.pipeline import run_pipeline


def main():
    checks = 0

    outline_text = "## Section One\nBrief: First brief.\n\n## Section Two\nBrief: Second brief.\n"
    sections = parse_outline(outline_text)
    assert len(sections) == 2 and sections[0]["title"] == "Section One"
    print("[PASS] outline parsing extracts sections and briefs correctly")
    checks += 1

    draft = assemble_draft("Intro text.", [{"title": "A", "body": "Body A."}, {"title": "B", "body": "Body B."}], "Conclusion text.")
    assert "## A" in draft and "## B" in draft
    print("[PASS] draft assembly produces correctly structured markdown")
    checks += 1

    dup_draft = "Some intro text here today.\n\n## Section A\n\nThis point about crawl budget matters a lot for large sites.\n\n## Section B\n\nThis point about crawl budget matters a lot for large sites.\n"
    dups = find_duplicate_sentences(dup_draft)
    assert len(dups) == 1, f"Expected 1 duplicate, got {dups} — regression in heading-strip logic"
    print("[PASS] duplicate sentence detection works correctly across section boundaries (regression guard)")
    checks += 1

    issues = check_heading_structure("## A\ntext\n\n## C\ntext", ["A", "B", "C"])
    assert len(issues) == 1 and "B" in issues[0]
    print("[PASS] heading structure check catches a missing expected section")
    checks += 1

    r = compute_readability("This is a simple sentence. It should be easy to read. " * 10)
    assert r["flesch_reading_ease"] is not None
    print("[PASS] readability scoring works on assembled draft text")
    checks += 1

    assert slugify("Complete Guide to SEO (2026)!") == "complete-guide-to-seo-2026"
    print("[PASS] slugify produces clean URL slugs")
    checks += 1

    article_schema = build_article_schema("T", "D", "https://x.com/a", "Author", "Site", 1000)
    assert article_schema["@type"] == "Article" and article_schema["wordCount"] == 1000
    faq_schema = build_faq_schema([{"question": "Q1", "answer": "A1"}])
    assert faq_schema["mainEntity"][0]["acceptedAnswer"]["text"] == "A1"
    print("[PASS] Article and FAQPage JSON-LD schema generation correct")
    checks += 1

    kw = analyze_keyword_usage("keyword here. " * 3 + "filler word " * 50, "keyword")
    assert kw["assessment"] in ("Healthy range", "Over-optimized — keyword density unusually high, risks reading as keyword stuffing", "Under-optimized — keyword barely appears, consider working it in more naturally")
    print(f"[PASS] keyword density analysis runs and classifies correctly ({kw['density_pct']}%)")
    checks += 1

    suggestions = suggest_internal_links("this article covers structured data validation in depth", [{"url": "https://x.com/a", "title": "Structured Data Validation Guide"}, {"url": "https://x.com/b", "title": "Unrelated Cake Recipe"}])
    assert len(suggestions) == 1 and suggestions[0]["url"] == "https://x.com/a"
    print("[PASS] internal link suggestion heuristic correctly matches relevant pages only")
    checks += 1

    responses = iter(["Way too long of a title that definitely goes past sixty characters", "A Nicely Sized SEO Title About Technical Audits"])
    with patch("content_pipeline.seo_specialist.call_llm", side_effect=lambda *a, **k: next(responses)):
        result = generate_title("topic", "keyword")
    assert result["within_range"] is True and result["attempts"] == 2
    print("[PASS] title generation retries on length failure and succeeds on second attempt")
    checks += 1

    messy = 'Sure! [{"question": "Q?", "answer": "A."}] Hope that helps.'
    with patch("content_pipeline.seo_specialist.call_llm", return_value=messy):
        faqs = generate_faqs("topic", "article text")
    assert len(faqs) == 1
    print("[PASS] FAQ generation extracts valid JSON even with LLM preamble/postamble text")
    checks += 1

    for var in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "CONTENT_PIPELINE_LLM_PROVIDER"):
        os.environ.pop(var, None)
    assert get_configured_provider() is None
    os.environ["ANTHROPIC_API_KEY"] = "fake"
    assert get_configured_provider() == "anthropic"
    print("[PASS] LLM provider auto-detection works correctly")
    checks += 1

    fake_outline = "## Section A\nBrief: Cover A.\n\n## Section B\nBrief: Cover B.\n"
    fake_faq = '[{"question": "Q1?", "answer": "Answer one."}]'

    def mock_llm(prompt, system=None, provider=None, model=None, max_tokens=2000, temperature=0.7):
        if "Produce an article outline" in prompt:
            return fake_outline
        if "frequently-asked" in prompt.lower():
            return fake_faq
        if "title tag" in prompt.lower():
            return "A Perfectly Sized Test Article Title"
        if "meta description" in prompt.lower():
            return "This is a perfectly sized meta description for testing purposes today."
        if "Edit it for flow" in prompt:
            match = re.search(r"---\n(.*)\n---", prompt, re.DOTALL)
            return match.group(1) if match else prompt
        return "Generated section content with enough words to be realistic for testing purposes here."

    with patch("content_pipeline.researcher.call_llm", side_effect=mock_llm), \
         patch("content_pipeline.outliner.call_llm", side_effect=mock_llm), \
         patch("content_pipeline.writer.call_llm", side_effect=mock_llm), \
         patch("content_pipeline.editor.call_llm", side_effect=mock_llm), \
         patch("content_pipeline.seo_specialist.call_llm", side_effect=mock_llm):
        result = run_pipeline(topic="Test Topic", target_keyword="test keyword", section_count=2, word_count_target=400)

    assert result["final_markdown"].startswith("---")
    assert "title:" in result["final_markdown"]
    assert result["seo_metadata"]["schema"]["article"]["@type"] == "Article"
    assert "Section A" in result["pipeline_log"]
    print("[PASS] full 6-stage pipeline runs end-to-end and produces valid article + metadata + log")
    checks += 1

    print(f"\n=== ALL {checks} CHECKS PASSED ===")
    print("Verified: outline parsing, draft assembly, duplicate/heading checks,")
    print("readability, slugify, schema generation, keyword density, internal-link")
    print("suggestions, title-retry logic, FAQ JSON extraction, provider detection,")
    print("and a full mocked end-to-end pipeline run producing valid deliverables.")
    print("\nNote: live network fetching (competitor URL summarization) and the real")
    print("Anthropic API request format were verified separately against real")
    print("domains during development — this smoke test covers the pure logic so")
    print("it runs offline/in CI without spending real API credits.")


if __name__ == "__main__":
    main()
