"""
assembler.py
-------------
Stage 6, the final step. Takes everything produced by the earlier stages
and assembles the publish-ready deliverables:

  - final_article.md   : YAML front matter + the edited article body + an FAQ section
  - seo_metadata.json    : title, meta description, slug, both JSON-LD schemas, keyword analysis, internal link suggestions
  - pipeline_log.md       : a transparency log showing what each "team member" produced at each stage
"""

import yaml


def build_final_markdown(title: str, meta_description: str, slug: str, target_keyword: str,
                          article_body: str, faqs: list, word_count: int, author_name: str) -> str:
    front_matter = {
        "title": title,
        "meta_description": meta_description,
        "slug": slug,
        "target_keyword": target_keyword,
        "word_count": word_count,
        "author": author_name,
    }
    front_matter_yaml = yaml.dump(front_matter, sort_keys=False, allow_unicode=True)

    faq_section = ""
    if faqs:
        faq_lines = ["\n## Frequently Asked Questions\n"]
        for faq in faqs:
            faq_lines.append(f"**{faq['question']}**\n\n{faq['answer']}\n")
        faq_section = "\n".join(faq_lines)

    return f"---\n{front_matter_yaml}---\n\n{article_body.strip()}\n{faq_section}"


def build_seo_metadata(title_result: dict, meta_result: dict, slug: str, article_schema: dict,
                        faq_schema: dict, keyword_analysis: dict, internal_link_suggestions: list) -> dict:
    return {
        "title": title_result["title"],
        "title_length": title_result["length"],
        "meta_description": meta_result["meta_description"],
        "meta_description_length": meta_result["length"],
        "slug": slug,
        "keyword_analysis": keyword_analysis,
        "internal_link_suggestions": internal_link_suggestions,
        "schema": {
            "article": article_schema,
            "faq": faq_schema if faq_schema.get("mainEntity") else None,
        },
    }


def build_pipeline_log(topic: str, target_keyword: str, research: dict, outline: dict,
                        editor_result: dict, title_result: dict, meta_result: dict,
                        keyword_analysis: dict, internal_link_suggestions: list) -> str:
    lines = [f"# Pipeline Log — {topic}", ""]
    lines.append(f"**Target keyword:** {target_keyword}\n")

    lines.append("## 1. Researcher\n")
    lines.append(research["brief_text"] + "\n")
    if research["competitor_summaries"]:
        lines.append("**Competitor pages analyzed:**")
        for c in research["competitor_summaries"]:
            status = "failed to fetch" if c["error"] else f"{len(c['headings'])} headings extracted"
            lines.append(f"- {c['url']} — {status}")
        lines.append("")

    lines.append("## 2. Outliner\n")
    for s in outline["sections"]:
        lines.append(f"- **{s['title']}** — {s['brief']}")
    lines.append("")

    lines.append("## 3. Writer\n")
    lines.append(f"Wrote intro + {len(outline['sections'])} sections + conclusion, section-by-section.\n")

    lines.append("## 4. Editor\n")
    lines.append(f"- Duplicate sentences found and flagged for removal: {len(editor_result['duplicate_sentences_found'])}")
    lines.append(f"- Heading structure issues found: {len(editor_result['heading_issues_found'])}")
    before, after = editor_result["readability_before"], editor_result["readability_after"]
    if before["flesch_reading_ease"] is not None and after["flesch_reading_ease"] is not None:
        lines.append(f"- Readability (Flesch Reading Ease): {before['flesch_reading_ease']} → {after['flesch_reading_ease']}")
    lines.append("")

    lines.append("## 5. SEO Specialist\n")
    lines.append(f"- Title: \"{title_result['title']}\" ({title_result['length']} chars, {title_result['attempts']} attempt(s))")
    lines.append(f"- Meta description: {meta_result['length']} chars, {meta_result['attempts']} attempt(s)")
    lines.append(f"- Keyword density: {keyword_analysis['density_pct']}% ({keyword_analysis['assessment']})")
    if internal_link_suggestions:
        lines.append(f"- Internal link suggestions: {len(internal_link_suggestions)} found")
        for s in internal_link_suggestions:
            lines.append(f"  - {s['title']} ({s['url']}) — overlap {s['overlap_ratio']}")
    lines.append("")

    return "\n".join(lines)
