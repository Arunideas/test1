# World of Interns — Content Intelligence Platform

Generate high-quality, human-sounding LinkedIn posts with authentic supporting images in a
consistent **World of Interns** brand voice.

> **Deliverable met:** generate a LinkedIn-ready post *with* an image in **under 2 minutes** —
> in practice it takes well under a second with the built-in offline engine.

This is the foundation of the larger AI Content Intelligence vision. It now covers two phases:

- **Phase 1 — Content generation + brand voice** (Studio)
- **Phase 2 — Content intelligence & planning** (Calendar) — plan months of content
  automatically with **no duplicate topics**.

---

## Highlights

- **AI Content Generator** — one click produces a post *and* an image.
- **AI Writing Style Engine** — enforces and scores the permanent brand rules
  (short sentences, one idea per paragraph, `Hook → Problem → Evidence → Solution → Action → Question`,
  no AI/motivational/salesy language, no invented names, soft-question CTAs only).
- **Brand Voice & Tone** — a single source of truth applied to every post.
- **Topic Selection** — auto-pick (balances categories, avoids repeats), pick from tracked
  topics, or write your own.
- **Content Templates** — per content-type structure and prompts.
- **Image Prompt Generation** — documentary, authentic prompts (Indian environment,
  natural light, *no* glossy AI people or stock offices).
- **Image Generation** — authentic, minimal images rendered locally as SVG
  (statistics, checklist, before/after, question card, top list, timeline, comparison, quote),
  or real photos via OpenAI when a key is present.
- **Draft Preview** — a realistic LinkedIn card preview.
- **Manual Editing + Save Draft + Version History** — edit, re-score, and keep every version.
- **Quality Scoring + Brand Review** — educational / trust / actionable / authentic / human /
  promotional scores, plus concrete rule warnings.

### Phase 2 — Content Intelligence & Planning (`/calendar`)

Prevent repetitive content and plan months ahead automatically.

- **Content Calendar** — a month-grid view built from a weekday theme plan
  (Mon: AI Tool · Tue: Resume Review · Wed: Internship Jobs · Thu: Recruiter Insight ·
  Fri: Future Skill · Sat: Student Story · Sun: Weekly Report).
- **Topic Scheduler + Rotation** — picks the best topic per day and avoids repeating a topic
  within a configurable window (default **45 days**).
- **Duplicate Detection** — dependency-free text similarity (unigram + bigram Jaccard) flags
  near-duplicate topics against everything already scheduled or published.
- **Category Balancing** — rotates across each theme's categories and reports which pillars are
  underrepresented.
- **Trending Topic Suggestions** — ranks the topic bank by trend/popularity.
- **Content Scoring** — a topic score blends editorial priority, trend, popularity, past
  performance, and freshness.
- **Approval Workflow** — approve / reject / skip / reset per calendar entry, then generate the
  post + image directly from an entry.
- **Publishing Queue** and **Performance History** (record metrics → blended performance score
  feeds back into topic scoring).

**It answers:** *Have we posted this before? · Which topic should be next? · Which category is
underrepresented? · Which topics are trending?*

> **Phase 2 deliverable met:** one click produces a **90-day content calendar with 0 duplicate
> topics** (90 unique topics, max pairwise similarity ~0.26, 21 categories balanced).

### Content types

LinkedIn Post · AI Tool of the Week · Resume Review · Recruiter Tips · AI Career ·
Student Tips · Hiring Tips.

### Backend library (`/library`)

Categories (46 across Students / Companies / Market / Community pillars) · Topics ·
Brand Style · Prompt Library · Image Templates · Generated Posts / Images / Drafts.

---

## Works offline, upgrades with a key

The platform is designed to always work:

- **No API key** → uses the built-in **rule-based writing engine** and **local SVG image
  renderer**. Fully deterministic, no network, no cost.
- **`OPENAI_API_KEY` set** → transparently upgrades to OpenAI for post text and real photographic
  images, while still applying and scoring the same brand rules. Any failure gracefully falls back
  to the offline engine.

See `.env.example` for configuration.

---

## Getting started

```bash
npm install
npm run dev          # http://localhost:3000
```

Production:

```bash
npm run build
npm run start
```

Optional OpenAI mode:

```bash
cp .env.example .env
# set OPENAI_API_KEY=sk-...
npm run dev
```

Data is stored in a local JSON file at `data/db.json` (created and seeded on first run; git-ignored).

---

## Architecture

```
src/
  app/
    page.tsx              Studio: generate, preview, edit, versions, scores
    calendar/page.tsx     Content calendar, intelligence panel, approval workflow
    drafts/page.tsx       Saved drafts gallery
    library/page.tsx      Backend library (brand, categories, prompts, topics, templates)
    api/
      generate/           POST -> post + image
      posts/              list / get / update (version) / delete
      posts/[id]/image/   regenerate image (choose template)
      calendar/           list · plan (build calendar) · [id] (approve/reject) · [id]/generate
      queue/              publishing queue (approved/generated entries)
      insights/           answers the 4 planning questions
      duplicate-check/    "have we posted this before?"
      performance/        record metrics -> performance score
      meta/               content types, categories, brand, prompts, topics, config
  lib/
    voice/styleEngine.ts  brand rules + quality scoring
    content/generator.ts  rule-based post composition per content type
    content/topicBank.ts  curated topic bank (enough unique topics for 90+ days)
    content/contentTypes.ts
    image/imagePrompt.ts  documentary-style image prompts (+ negatives)
    image/svgRenderer.ts  local authentic SVG compositions
    llm/openai.ts         optional OpenAI text + image (graceful fallback)
    planning/similarity.ts  topic similarity / duplicate detection
    planning/planner.ts     scheduler, rotation, balancing, trending, scoring
    planning/service.ts     calendar persistence, approval, queue, insights, performance
    service.ts            content generation orchestration
    db.ts / seed.ts / types.ts
```

## Brand principles enforced in code

Every post aims to **educate, build trust, be actionable, authentic and human** — and never sound
like AI, motivation, or an advertisement. The engine flags banned/sales phrases, invented names
(e.g. "Rahul", "Priya" → "a final year student"), long paragraphs/sentences, missing soft-question
CTAs, and promotional density. Every post should stay valuable even if the brand name is removed.
