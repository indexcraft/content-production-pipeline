#!/usr/bin/env python3
"""
AI Content Production Pipeline — CLI entry point.

    python run_pipeline.py --topic "Technical SEO Audits" --keyword "technical SEO audit checklist"

Runs the full 6-stage pipeline (researcher -> outliner -> writer -> editor
-> SEO specialist -> assembler) and writes three files to --output-dir:
  - final_article.md   (ready to publish, with YAML front matter + FAQ section)
  - seo_metadata.json    (title, meta description, JSON-LD schema, keyword/link analysis)
  - pipeline_log.md       (what each stage produced, for transparency/review)
"""

import argparse
import json
import os
import sys

from dotenv import load_dotenv

from content_pipeline.llm_client import get_configured_provider
from content_pipeline.pipeline import run_pipeline


def parse_existing_pages(pairs: list) -> list:
    """--existing-pages takes 'url|title' pairs from the command line."""
    pages = []
    for pair in pairs or []:
        if "|" in pair:
            url, title = pair.split("|", 1)
            pages.append({"url": url.strip(), "title": title.strip()})
    return pages


def main():
    parser = argparse.ArgumentParser(description="AI Content Production Pipeline — a virtual content team in one command")
    parser.add_argument("--topic", required=True, help="The article topic, e.g. 'Technical SEO Audits'")
    parser.add_argument("--keyword", required=True, help="Target SEO keyword")
    parser.add_argument("--tone", default="professional", help="e.g. professional, casual, technical, conversational")
    parser.add_argument("--audience", default="general readers", help="e.g. 'in-house SEO managers'")
    parser.add_argument("--word-count", type=int, default=1500, help="Target total article word count")
    parser.add_argument("--sections", type=int, default=6, help="Approximate number of H2 sections")
    parser.add_argument("--competitor-urls", nargs="*", default=[], help="Up to a few competitor URLs to ground the research brief")
    parser.add_argument("--existing-pages", nargs="*", default=[], help="Existing site pages for internal-link suggestions, as 'url|title' pairs")
    parser.add_argument("--author", default="Author")
    parser.add_argument("--site-name", default="Site")
    parser.add_argument("--base-url", default="https://example.com", help="Used to build the canonical URL in the schema")
    parser.add_argument("--num-faqs", type=int, default=5)
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args()

    provider = get_configured_provider()
    if not provider:
        print("[error] No LLM API key configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY (in .env or your environment) — unlike the other tools in this series, this pipeline requires an LLM at every stage.")
        sys.exit(1)
    print(f"[info] using {provider}")

    os.makedirs(args.output_dir, exist_ok=True)
    existing_pages = parse_existing_pages(args.existing_pages)

    result = run_pipeline(
        topic=args.topic,
        target_keyword=args.keyword,
        tone=args.tone,
        audience=args.audience,
        word_count_target=args.word_count,
        section_count=args.sections,
        competitor_urls=args.competitor_urls,
        existing_pages=existing_pages,
        author_name=args.author,
        site_name=args.site_name,
        base_url=args.base_url,
        num_faqs=args.num_faqs,
        provider=provider,
        progress_callback=print,
    )

    article_path = os.path.join(args.output_dir, "final_article.md")
    metadata_path = os.path.join(args.output_dir, "seo_metadata.json")
    log_path = os.path.join(args.output_dir, "pipeline_log.md")

    with open(article_path, "w", encoding="utf-8") as f:
        f.write(result["final_markdown"])
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(result["seo_metadata"], f, indent=2)
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(result["pipeline_log"])

    print(f"\n=== DONE ===")
    print(f"Article:      {article_path}")
    print(f"SEO metadata: {metadata_path}")
    print(f"Pipeline log: {log_path}")


if __name__ == "__main__":
    load_dotenv()
    main()
