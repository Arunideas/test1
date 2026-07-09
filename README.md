# World of Interns — Content Intelligence Platform

Generate high-quality, human-sounding LinkedIn posts with authentic supporting images in a
consistent **World of Interns** brand voice.

> **Deliverable met:** generate a LinkedIn-ready post *with* an image in **under 2 minutes**.
>
> **Writing is AI-only.** Posts and outreach copy are written exclusively by an AI model
> (OpenAI). If `OPENAI_API_KEY` is not configured, generation returns a clear error instead of
> falling back to any templated text — there is no rule-based writing engine.

This is the foundation of the larger AI Content Intelligence vision. It now covers:

- **Phase 1 — Content generation + brand voice** (Studio)
- **Phase 2 — Content intelligence & planning** (Calendar) — plan months of content
  automatically with **no duplicate topics**.
- **Phase 3 — LinkedIn Engine** (Publish) — **auto-publish to LinkedIn** with immediate /
  scheduled / draft / approval modes and automatic retry.
- **Phase 4 — Employer & Student Growth Engine** (Campaigns) — turn content into growth with
  **one-click campaigns targeting HRs or students**.

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

### Phase 3 — LinkedIn Engine (`/publish`)

Auto-publish content to LinkedIn.

- **Publish modes** — Immediate, Scheduled (posts at a chosen time), Draft, and Approval-required.
- **Background scheduler** — an in-process loop publishes due scheduled jobs automatically; a
  `POST /api/publish/process` endpoint is also exposed for an external cron.
- **Automatic retry** — failed publishes retry with exponential backoff (up to 4 attempts), with a
  full per-job log; manual retry/cancel/approve actions too.
- **Auto-schedule the calendar** — one click turns every approved/generated calendar post into a
  scheduled LinkedIn job at a chosen time of day.
- **Real or simulated** — set `LINKEDIN_ACCESS_TOKEN` + `LINKEDIN_AUTHOR_URN` to post for real via
  the LinkedIn UGC Posts API; stored post images are converted to PNG and attached as LinkedIn
  feedshare image assets. Otherwise the entire flow runs in safe simulation mode (jobs progress
  end-to-end with a simulated post URL and image-attached status). Publishing a post also marks its
  topic and calendar entry as published.

You can publish from the Studio (per-post panel) or manage everything on the Publish page
(connection status, queue, live-updating log, and per-job actions).

### Phase 4 — Employer & Student Growth Engine (`/campaigns`)

Turn content into platform growth with **one-click campaigns**. Pick a target
(Employers/HR, Students, or Community), pick a service, and generate a ready-to-use asset bundle.

- **Employer services** — Hire Interns in 10 Days · Campus Hiring · Employer Branding ·
  Assessment Platform · Recruitment Automation. Each campaign includes an educational LinkedIn
  post plus an **outreach kit**: HR outreach email (subject + body), LinkedIn message
  (connection note + first message), follow-up email, and a proposal — all brand-voiced (honest,
  calm, no hype) with `[First name]` / `[Company]` / `[Role]` placeholders.
- **Student services** — Employability Score · Resume Review · AI Career · Interview Prep ·
  Internship Verification · Skill Gap Analysis. Each campaign includes a LinkedIn post, a poll,
  and a short quiz.
- **Community** — Polls · Weekly Quiz · Student Spotlight · Company Spotlight · Recruiter Insights.
  Spotlights are placeholder templates (never invented stories), staying true to the brand rules.

Every asset can be copied with one click; campaigns are saved and re-openable.

> **Phase 4 deliverable met:** one click builds a full campaign targeting HRs (post + email +
> message + follow-up + proposal) or students (post + poll + quiz).

### Content types

LinkedIn Post · AI Tool of the Week · Resume Review · Recruiter Tips · AI Career ·
Student Tips · Hiring Tips.

### Backend library (`/library`)

Categories (46 across Students / Companies / Market / Community pillars) · Topics ·
Brand Style · Prompt Library · Image Templates · Generated Posts / Images / Drafts.

---

## What needs an API key

- **Writing (AI-only, requires `OPENAI_API_KEY`)** — LinkedIn posts and outreach copy (HR emails,
  LinkedIn messages, follow-ups, proposals) are written **only** by the AI model. Without a key,
  these endpoints return a clear `422` error (`"AI writing is required…"`). There is **no**
  rule-based writing fallback.
- **Works without a key** — image generation (local SVG renderer; upgrades to OpenAI images when a
  key is set), the 90-day planner and duplicate detection, publishing/scheduling (LinkedIn
  simulation), and community scaffolds (poll options, quiz Q&A, spotlight fill-in templates).
- **Brand rules & scoring** are always applied to the AI's output (they validate, they don't write).

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

## Running on a schedule (automation)

There are three layers of automation, from least to most hands-off.

**1. Built-in background scheduler (nothing to configure).**
While the server is running, an in-process loop publishes any *due scheduled* jobs every ~10s.
So if you schedule posts (in the Studio or via auto-schedule), they go out on time on their own.

**2. Publish-only cron.**
For extra reliability (or serverless hosts where the process may sleep), hit the publish tick on a
schedule:

```bash
curl -X POST https://your-host/api/publish/process
```

**3. Full daily pipeline (recommended).**
One endpoint runs the entire loop: ensure a calendar exists → generate posts + images for entries
due today → auto-schedule them → publish what's due.

```bash
curl -X POST "https://your-host/api/cron/run?timeOfDay=09:00"
# optional query params: days=90, horizonDays=0, planIfEmpty=true, generate=true, secret=...
```

It's idempotent — running it repeatedly only acts on newly-due work. Returns a summary like
`{ "planned": 90, "generated": 1, "scheduled": 1, "published": 1 }`.

If `CRON_SECRET` is set, include `?secret=...` or an `x-cron-secret` header.

### Wiring it to a scheduler

**System crontab** (run daily at 09:00):

```cron
0 9 * * *  curl -fsS -X POST "https://your-host/api/cron/run?timeOfDay=09:00&secret=$CRON_SECRET" >/dev/null 2>&1
```

**GitHub Actions** (`.github/workflows/publish.yml`):

```yaml
on:
  schedule:
    - cron: "0 9 * * *"   # daily 09:00 UTC
jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - run: curl -fsS -X POST "${{ secrets.APP_URL }}/api/cron/run?timeOfDay=09:00&secret=${{ secrets.CRON_SECRET }}"
```

**Vercel Cron** (`vercel.json`):

```json
{ "crons": [{ "path": "/api/cron/run?timeOfDay=09:00", "schedule": "0 9 * * *" }] }
```

**systemd timer / Docker:** run the same `curl` from a `*.timer` unit or a sidecar loop
(`while true; do curl -X POST .../api/cron/run; sleep 3600; done`). Keep the app itself running
with `npm run start` (see the Dockerfile), and the background scheduler + your cron do the rest.

## Deploy to Portainer (GitHub Actions → GHCR → Portainer)

CI builds the image and pushes it to the GitHub Container Registry; Portainer pulls and runs it.

1. **Push to `master`.** The workflow `.github/workflows/docker-publish.yml` builds the Docker
   image and pushes it to `ghcr.io/<owner>/<repo>` (tags: `latest`, branch, `sha-…`). Check the
   run under the repo's **Actions** tab.
2. **Make the package pullable.** In GitHub → your profile/org → **Packages** → the image →
   *Package settings*: either set visibility to **Public**, or keep it private and create a PAT
   with `read:packages` to use as Portainer registry credentials.
3. **(Private only) Add the registry in Portainer:** *Registries → Add registry → Custom*, URL
   `ghcr.io`, username = your GitHub user, password = the `read:packages` PAT.
4. **Create the stack in Portainer:** *Stacks → Add stack*. Paste `docker-compose.yml` (or point it
   at this repo via *Git repository*). Set env vars: `IMAGE=ghcr.io/<owner>/<repo>:latest`,
   `OPENAI_API_KEY` (required for writing), optional `LINKEDIN_ACCESS_TOKEN` / `LINKEDIN_AUTHOR_URN`,
   and `CRON_SECRET`. Deploy.
5. **Auto-redeploy on new images:** enable the stack's **webhook** (Stack → *Webhook*), then add a
   final CI step (or a repository→Portainer integration) that `curl -X POST <portainer-webhook-url>`
   after the image is pushed, so Portainer pulls `:latest` and recreates the container.
6. **Scheduled runs:** the app's in-process scheduler publishes due posts automatically. For the
   full daily pipeline, point any cron at `POST https://<host>/api/cron/run?timeOfDay=09:00&secret=$CRON_SECRET`
   (see "Running on a schedule").

Data persists in the `woi-data` volume (`/app/data`). The container listens on port 3000.

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
    content/hashtags.ts   hashtag/tag helper (metadata, not writing)
    content/topicBank.ts  curated topic bank (enough unique topics for 90+ days)
    content/contentTypes.ts
    image/imagePrompt.ts  documentary-style image prompts (+ negatives)
    image/svgRenderer.ts  local authentic SVG compositions
    llm/openai.ts         optional OpenAI text + image (graceful fallback)
    planning/similarity.ts  topic similarity / duplicate detection
    planning/planner.ts     scheduler, rotation, balancing, trending, scoring
    planning/service.ts     calendar persistence, approval, queue, insights, performance
    growth/services.ts      employer/student/community service catalog + campaign templates
    growth/outreach.ts      HR emails, LinkedIn messages, follow-ups, proposals
    growth/community.ts     polls, quizzes, spotlights
    growth/campaign.ts      one-click campaign orchestration (build/list/get/delete)
    publishing/linkedin.ts  LinkedIn UGC client (real API + simulation)
    publishing/service.ts   schedule/approve/retry/cancel, background scheduler, auto-schedule
    publishing/pipeline.ts  one-call daily pipeline (plan -> generate -> schedule -> publish)
    service.ts            content generation orchestration
    db.ts / seed.ts / types.ts
```

API additions:
- Campaigns: `GET/POST /api/campaigns`, `GET/DELETE /api/campaigns/[id]`, `growthServices` in `/api/meta`.
- Publishing: `POST /api/publish`, `GET /api/publish/jobs`, `POST /api/publish/jobs/[id]`
  (approve/cancel/retry), `POST /api/publish/process` (cron tick), `GET /api/publish/status`,
  `POST /api/publish/auto-schedule`.
- Scheduling: `GET|POST /api/cron/run` — the full daily pipeline (plan → generate → schedule →
  publish), guarded by optional `CRON_SECRET`.

## Brand principles enforced in code

Every post aims to **educate, build trust, be actionable, authentic and human** — and never sound
like AI, motivation, or an advertisement. The engine flags banned/sales phrases, invented names
(e.g. "Rahul", "Priya" → "a final year student"), long paragraphs/sentences, missing soft-question
CTAs, and promotional density. Every post should stay valuable even if the brand name is removed.
