# AI Content Production Pipeline

A virtual content team in one command: **Researcher → Outliner → Writer → Editor → SEO Specialist → Assembler**. Give it a topic and target keyword; it hands back a publish-ready article with front matter, an FAQ section, JSON-LD schema, and a transparency log showing what each "team member" did.

Bring your own OpenAI or Anthropic API key — this is the one tool in the series that requires an LLM at every stage (unlike the audit tools, there's no meaningful deterministic-only mode for *writing* an article).

---

## What each stage actually does

| Stage | Role | What it produces |
|---|---|---|
| **1. Researcher** | Defines search intent, audience angle, and subtopics to cover. Can fetch and summarize competitor URLs to ground the brief in what's actually published, not just guess from training data. | Research brief |
| **2. Outliner** | Turns the brief into H2 sections, each with a one-line brief of what it should accomplish | Structured outline |
| **3. Writer** | Writes intro, each section, and conclusion — section-by-section (not one giant call), so each part stays focused and long articles don't hit output limits | Full draft |
| **4. Editor** | Deterministic checks first (duplicate sentences across sections, missing headings, readability score), then an LLM pass on the *full* draft to smooth transitions and cut redundancy the writer couldn't see | Revised draft |
| **5. SEO Specialist** | Title + meta description (generated, validated against length rules, and automatically retried up to 2x on failure), FAQ generation, Article + FAQPage JSON-LD, keyword density analysis, internal-link suggestions | SEO metadata + schema |
| **6. Assembler** | Combines everything into the final deliverables | 3 output files |

**Output files:**
- `final_article.md` — YAML front matter + article body + FAQ section, ready to paste into a CMS
- `seo_metadata.json` — title, meta description, slug, Article + FAQPage JSON-LD, keyword density, internal link suggestions
- `pipeline_log.md` — what each stage produced, for review before publishing

---

## 1. What you need

- **Python 3.10+**
- **An OpenAI or Anthropic API key** (required — see note above)

```bash
python3 --version
```

---

## 2. Setup

```bash
cd content-production-pipeline
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Open .env and paste in ONE of: OPENAI_API_KEY or ANTHROPIC_API_KEY
```

---

## 3. Run it

```bash
python run_pipeline.py \
  --topic "Technical SEO Audits" \
  --keyword "technical SEO audit checklist" \
  --audience "in-house SEO managers" \
  --tone professional \
  --word-count 1500
```

**Cost note:** a full run makes roughly 10-15 LLM calls (research, outline, one per section, intro, conclusion, edit pass, title, meta, FAQs). With the default Haiku/mini models this typically costs a few cents per article.

All options:

| Flag | Purpose |
|---|---|
| `--topic` | Required. The article subject. |
| `--keyword` | Required. Target SEO keyword. |
| `--tone` | `professional` (default), `casual`, `technical`, `conversational`, or anything you describe |
| `--audience` | Who it's written for, e.g. `"B2B marketing directors"` |
| `--word-count` | Target total length (default 1500) |
| `--sections` | Approximate H2 count (default 6) |
| `--competitor-urls` | Space-separated URLs to fetch and ground the research brief |
| `--existing-pages` | Space-separated `url\|title` pairs for internal-link suggestions |
| `--author` / `--site-name` / `--base-url` | Used in the Article JSON-LD |
| `--num-faqs` | How many FAQ entries to generate (default 5) |
| `--output-dir` | Where the 3 files land (default `output/`) |

Example with everything on:

```bash
python run_pipeline.py \
  --topic "Structured Data for E-commerce" \
  --keyword "product schema markup" \
  --audience "e-commerce SEO managers" \
  --competitor-urls https://example.com/schema-guide \
  --existing-pages "https://indexcraft.in/json-ld-guide|JSON-LD Validation Guide" \
  --author "Rohit Kunal" --site-name "IndexCraft" --base-url "https://indexcraft.in"
```

---

## 4. Verifying it works

```bash
python smoke_test.py
```

Runs 13 checks (fully mocked, no real API calls or cost) covering outline parsing, draft assembly, the duplicate-sentence and heading-structure checks, readability, slugify, schema generation, keyword density, internal-link suggestions, the title-retry logic, FAQ JSON extraction from messy LLM output, provider auto-detection, and a full mocked end-to-end run through all 6 stages. See `sample_output/` for what a real run produces.

---

## 5. Two real bugs this caught during development

**Duplicate-sentence detection glued headings onto sentences.** The section-by-section writing stage can accidentally repeat a point across two sections (the writer for section 2 doesn't see section 1's exact wording). The editor's duplicate-sentence check was supposed to catch this — but splitting on sentence-ending punctuation without first stripping `## Heading` lines meant the heading text got glued onto the start of the following sentence, making two otherwise-identical repeated sentences look different and slip past detection right after a heading. Fixed by stripping heading lines before sentence-splitting, with a permanent regression test.

**Title/meta retry logic needs a real length check, not a guess.** LLMs are inconsistent about hitting an exact character count when asked directly. The SEO specialist stage validates the actual returned length against the 30-60 (title) / 70-160 (meta) character rules and automatically retries with corrective feedback ("that was 71 chars, too long") up to twice before falling back to deterministic truncation — so a title tag is never silently published at the wrong length just because the model estimated poorly.

---

## Project structure

```
content-production-pipeline/
├── run_pipeline.py                  # CLI entry point
├── smoke_test.py                     # 13 automated checks, fully mocked
├── requirements.txt
├── .env.example                      # copy to .env, add an API key (required)
├── content_pipeline/
│   ├── llm_client.py                   # pluggable OpenAI/Anthropic client
│   ├── researcher.py                    # stage 1: brief + competitor analysis
│   ├── outliner.py                       # stage 2: structured outline + parser
│   ├── writer.py                          # stage 3: section-by-section drafting
│   ├── editor.py                           # stage 4: deterministic checks + LLM edit pass
│   ├── seo_specialist.py                   # stage 5: metadata, schema, keyword/link analysis
│   └── assembler.py                         # stage 6: final markdown + metadata + log
├── output/                            # your generated articles land here
└── sample_output/                     # example article + metadata + log
```

---

## Notes on using generated content responsibly

This produces a strong first draft, not a finished, fact-checked publication. The pipeline's own editor stage catches structural issues (duplication, missing sections, readability) but does not verify factual claims — always have a human review generated content for accuracy before publishing, especially for anything involving statistics, dates, or claims about specific products or companies.

---

## For your resume / portfolio

Suggested bullet:
> Built an open-source AI content production pipeline modeling a full content team (research, outline, writing, editing, SEO) as six discrete LLM-orchestrated stages, with deterministic validation (length constraints, duplicate detection, readability) layered around each generative step — bring-your-own OpenAI/Anthropic key.

Pairs with the SEO audit series as the "content creation" counterpart to the "content auditing" tools — together they cover both ends of a content team's workflow.
