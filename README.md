# LinkedIn Posting Agent

This repository includes a small Python agent that can post a sample text update
to LinkedIn. It supports:

- Company page posts when LinkedIn grants organization permissions.
- Personal profile posts with the `w_member_social` permission.

## Dry-run test

Dry-run mode is the default and does not call LinkedIn:

```bash
python3 linkedin_company_page_agent.py
```

To preview a custom message:

```bash
python3 linkedin_company_page_agent.py --message "Sample company page test message."
```

## Get a LinkedIn authorization code

If you only have a LinkedIn app client ID and client secret, first generate the
browser authorization URL. The redirect URI must already be registered in your
LinkedIn Developer app.

```bash
export LINKEDIN_CLIENT_ID="your-linkedin-client-id"
export LINKEDIN_REDIRECT_URI="http://localhost:3000/callback"

python3 linkedin_company_page_agent.py --auth-url
```

The command prints JSON with an `authorization_url`. Open that URL in a browser,
approve access with a LinkedIn account that can administer the company page, and
copy the `code` query parameter from the redirect URL.

You can also pass values directly:

```bash
python3 linkedin_company_page_agent.py \
  --auth-url \
  --client-id "your-linkedin-client-id" \
  --redirect-uri "http://localhost:3000/callback" \
  --state "random-string-for-testing"
```

By default the agent requests organization scopes:

- `w_organization_social`
- `r_organization_social`

To request different scopes:

```bash
python3 linkedin_company_page_agent.py \
  --auth-url \
  --scope "w_organization_social r_organization_social"
```

For personal profile posting, request the scopes available on a basic LinkedIn
app:

```bash
python3 linkedin_company_page_agent.py \
  --auth-url \
  --post-as member \
  --client-id "your-linkedin-client-id" \
  --redirect-uri "http://localhost:3000/callback"
```

That prints an authorization URL with these default personal posting scopes:

- `openid`
- `profile`
- `email`
- `w_member_social`

After you receive the authorization code, exchange it for an access token:

```bash
curl -X POST "https://www.linkedin.com/oauth/v2/accessToken" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code" \
  -d "code=AUTHORIZATION_CODE_FROM_REDIRECT" \
  -d "redirect_uri=http://localhost:3000/callback" \
  -d "client_id=your-linkedin-client-id" \
  -d "client_secret=your-linkedin-client-secret"
```

## Publish to LinkedIn

### Company page

Set the required company page credentials, then pass `--post`:

```bash
export LINKEDIN_ACCESS_TOKEN="your-linkedin-access-token"
export LINKEDIN_ORGANIZATION_ID="your-company-organization-id"

python3 linkedin_company_page_agent.py \
  --message "Sample company page test message." \
  --post
```

You can also provide a full organization URN:

```bash
export LINKEDIN_ORGANIZATION_URN="urn:li:organization:123456"
```

The access token must have permission to publish organic posts for the target
LinkedIn organization page.

### Personal profile

For personal profile testing, use `--post-as member`. The access token must
include `w_member_social`.

```bash
export LINKEDIN_ACCESS_TOKEN="your-linkedin-access-token"
export LINKEDIN_MEMBER_ID="your-authenticated-linkedin-member-id"

python3 linkedin_company_page_agent.py \
  --post-as member \
  --message "Sample personal profile test message." \
  --post
```

You can also provide a full member/person URN:

```bash
export LINKEDIN_MEMBER_URN="urn:li:person:abc123"
```

To attach an image, provide a local image path:

```bash
python3 linkedin_company_page_agent.py \
  --post-as member \
  --access-token "your-linkedin-access-token" \
  --member-id "your-authenticated-linkedin-member-id" \
  --message "Proud to share our latest employability ranking milestone." \
  --image-path "/path/to/employability-ranking-linkedin.png" \
  --image-title "Employability Ranking" \
  --image-description "Recognizing skills, readiness, and career potential" \
  --post
```

## Daily student content automation

`daily_story_linkedin_agent.py` creates one daily employability content post,
generates a related image, and can post both to LinkedIn. Captions are short,
comment-first LinkedIn posts rather than long teaching posts.

Posts follow a fixed weekly series so followers know what to expect:

| Day | Series |
| --- | --- |
| Monday | 🛠 AI Tool of the Week |
| Tuesday | 🎯 Prompt of the Week |
| Wednesday | 💼 Internship Opportunities |
| Thursday | 📄 Resume Makeover |
| Friday | 🤖 AI Career Tip |
| Saturday | 📊 Hiring Trends |
| Sunday | 🎓 Student Success Story |

Use `daily_linkedin_scheduler.py` to run the correct agent for today:

```bash
python3 daily_linkedin_scheduler.py --record-dry-run
```

Wednesday internship posts are handled by `daily_internship_intelligence_agent.py`.
The story agent skips Wednesday unless you pass `--force`.

Override the schedule while testing:

```bash
python3 daily_story_linkedin_agent.py --series resume_makeover --record-dry-run
python3 daily_story_linkedin_agent.py --date 2026-07-06 --record-dry-run
```

The content engine rotates through seven World of Interns pillars:

1. **Student Employability** — Resume Before vs After, Employability Score Explained,
   Resume Mistakes, Interview Questions, Skill Gap Analysis, Portfolio Reviews,
   Project Ideas, Career Roadmaps.

2. **Hire Interns in 10 Days** — Screened 250 to shortlist 12, startup hiring speed,
   AI screening reduction, hidden cost of unqualified interns.

3. **Internship Verification** — Stipend investigations, Verify My Internship checks,
   scam indicator posts.

4. **Recruiter Secrets** — 12-second rejects, top application mistakes, what HR
   notices first.

5. **Market Intelligence** — Top Skills This Week, Top Hiring Cities, Top Paying
   Internship Domains, Most Applied Jobs, Average Employability Score.

6. **Employer Branding** — Low application counts, improve your JD, salary
   benchmarks, campus hiring guide, internship program design.

7. **Campus Ambassador / Job Acquisition** — Campus Growth Partner role, earn while
   helping students get hired.

8. **AI Career Survival** — Jobs AI won't replace, AI as a 5× multiplier,
   AI + Humans vs Humans, how recruiters evaluate AI-assisted work, mentioning
   AI tools on resumes.

9. **Learn One AI Tool Every Week** — ChatGPT, Claude, Cursor, GitHub Copilot,
   Canva AI, Figma AI, Perplexity, Gemini, Notion AI, n8n, Zapier AI with real
   work examples.

10. **AI Challenge of the Week** — Portfolio website in 30 minutes, AI dataset
    dashboard challenge with featured submissions.

11. **AI Resume Upgrade** — Replace generic tool lines with AI-assisted workflow
    proof (e.g. Excel + AI reporting workflows).

12. **AI Interview Practice** — AI scoring for confidence, clarity, communication,
    and technical depth.

13. **AI Mythbusters** — Developers replaced myth, prompt engineering vs business
    problem solving.

14. **Future Skills** — Agentic AI, MCP, RAG, Vector Databases explained simply
    with practical examples.

The agent tracks used content in a JSON history file so successful posts are not
reused.

Content briefs live in the codebase as pillars and angles, but the published
LinkedIn caption and image prompt are generated by OpenAI — not assembled from
local templates.

Each run stores AI-generated assets in history:

1. `caption` - the full LinkedIn post text from the LLM
2. `visual` - the DALL-E image prompt from the LLM
3. `generation` - always `openai_llm` for captions and `ai_photo` for images

Captions should read like human LinkedIn posts: strong hook, proof or example,
one takeaway, and a checkbox question. They do not include a website CTA.
Each post also ends with meaningful hashtags based on the content pillar and
topic (for example `#WorldOfInterns`, `#ResumeTips`, `#Claude`).

Monday **AI Tool of the Week** posts also end with a fixed
**Why Students Should Care** block:

```text
Why this matters

✓ Save 2 hours/week
✓ Improve assignments
✓ Prepare for interviews
✓ Build better projects
✓ Write better documentation
```

Dry-run generation requires OpenAI:

```bash
export OPENAI_API_KEY="your-openai-api-key"

python3 daily_story_linkedin_agent.py
```

Optional model overrides:

```bash
export OPENAI_TEXT_MODEL="gpt-4o-mini"
export OPENAI_IMAGE_MODEL="gpt-image-1"
export OPENAI_IMAGE_SIZE="1024x1024"
```

Both the LinkedIn caption and the image are AI-generated. There is no local
template caption builder and no graphic card fallback.

Data-led posts can use metrics from a JSON file:

```json
{
  "python_assessment_students": "12,487",
  "python_function_success_rate": "18%",
  "mechanical_resume_year": "2026",
  "mechanical_resume_missing_skills": "CAD documentation, Excel reporting, GD&T basics, manufacturing process knowledge, and project cost estimation",
  "github_interview_multiplier": "2.8x",
  "average_employability_score": "61/100",
  "top_college_score": "84/100",
  "bottom_college_score": "42/100",
  "data_analyst_resume_gap": "SQL portfolio projects",
  "startup_shortlist_rate": "31%",
  "role_ranking_top_role": "Data Analyst Intern",
  "intern_hiring_days": "10",
  "screening_time_saved": "42%",
  "campus_campaign_reach": "3,200",
  "bulk_recruitment_roles": "120",
  "hiring_trend_year": "2026",
  "salary_benchmark_role": "Data Analyst Intern",
  "salary_benchmark_growth": "22%",
  "students_screened": "250",
  "students_shortlisted": "12",
  "ai_screening_reduction": "80%",
  "internship_application_count": "14",
  "suspicious_stipend_amount": "₹50,000/month",
  "suspicious_hours_per_day": "2 hours/day",
  "top_skill_python": "Python",
  "top_skill_excel": "Excel",
  "top_skill_powerbi": "Power BI",
  "top_skill_java": "Java",
  "top_skill_prompt": "Prompt Engineering",
  "top_hiring_city": "Bangalore",
  "top_paying_domain": "Data Analytics",
  "most_applied_role": "Data Analyst Intern",
  "verification_checks_count": "7",
  "campus_partner_title": "Campus Growth Partner",
  "ai_speed_multiplier": "5×",
  "ai_challenge_minutes": "30",
  "ai_jobs_safe_count": "5",
  "future_skill_current": "Agentic AI",
  "future_skill_next": "MCP"
}
```

Pass that file to the automation:

```bash
python3 daily_story_linkedin_agent.py --metrics-path "/path/to/metrics.json"
```

If no metrics file is provided, built-in sample metrics are used. For production
scheduled posts, provide a metrics file populated from real assessment, resume,
skill-gap, college, and role-ranking data.

Dry-run with deterministic output for testing:

```bash
python3 daily_story_linkedin_agent.py --seed 42
```

Post to a personal LinkedIn profile:

```bash
export LINKEDIN_ACCESS_TOKEN="your-60-day-linkedin-token"
export LINKEDIN_MEMBER_ID="your-authenticated-linkedin-member-id"

python3 daily_story_linkedin_agent.py --post
```

By default the daily agent writes:

- `daily_story_history.json` for used content tracking.
- `daily_story_output/` for generated PNG images.

For a scheduled automation, configure the automation to run the command below
with the LinkedIn token and member id available as environment variables:

```bash
python3 daily_story_linkedin_agent.py \
  --history-path "/var/lib/worldofinterns/daily_story_history.json" \
  --output-dir "/var/lib/worldofinterns/daily_story_images" \
  --post
```

Dry runs do not mark content as used unless you pass `--record-dry-run`.

## Live internship scrapers

`collect_internships.py` pulls live listings into JSON feeds that the daily
intelligence agent can publish.

Supported source types:

| Type | What it pulls |
| --- | --- |
| `linkedin_search` | Live LinkedIn guest job search results |
| `greenhouse` | Public Greenhouse career boards |
| `lever` | Public Lever job boards |
| `career_page` | HTML career pages with internship links |

Configure sources in `data/source_config.example.json`:

```json
{
  "output_dir": "data/live_sources",
  "sources": [
    {
      "type": "linkedin_search",
      "source_name": "linkedin_internship_india",
      "enabled": true,
      "keywords": "internship",
      "location": "India",
      "pages": 2
    },
    {
      "type": "greenhouse",
      "source_name": "greenhouse_stripe",
      "enabled": true,
      "board": "stripe",
      "company_name": "Stripe"
    }
  ]
}
```

Collect live jobs:

```bash
python3 collect_internships.py \
  --config-path data/source_config.example.json \
  --output-dir data/live_sources
```

Then build the daily briefing from the collected feeds:

```bash
python3 daily_internship_intelligence_agent.py \
  --sources-path data/live_sources \
  --include-unverified
```

Live scrapes are marked `verified: false` until your verification workflow
approves them. The post shows `Proceed with Caution ⚠️` instead of `Verified ✅`
for those listings.

Recommended schedule:

```bash
python3 collect_internships.py --config-path data/source_config.json --output-dir data/live_sources
python3 daily_internship_intelligence_agent.py --sources-path data/live_sources --include-unverified --post
```

Notes:

- LinkedIn guest search is live but can break if LinkedIn changes HTML or blocks requests.
- Greenhouse and Lever use official public JSON APIs and are the most stable sources.
- Career page scraping depends on each site's HTML structure; tune `link_keywords` per site.
- Respect site terms of service and rate limits in production.

## Daily Internship Intelligence

`daily_internship_intelligence_agent.py` is separate from the employability
content engine. It collects verified internship openings from one or more JSON
source files, builds a daily briefing, saves artifacts locally, and can post
the update to LinkedIn.

This agent powers **Wednesday's 💼 Internship Opportunities** series. Each post
starts with that series header, then the verified openings list.

For scheduled automation, prefer:

```bash
python3 daily_linkedin_scheduler.py --post
```

Or run the internship agent directly on Wednesdays:

```bash
python3 daily_internship_intelligence_agent.py --skip-unless-wednesday --post
```

Example output:

```text
🔥 Today's Verified Internship Opportunities (24)

📍 Software Engineering
5 Openings

📍 Digital Marketing
8 Openings

📍 Data Analytics
4 Openings

📍 HR
3 Openings

📍 Finance
4 Openings
```

Each job listing includes:

- Company
- Location
- Stipend
- Remote/Hybrid/Onsite
- Duration
- Apply Link
- Last Date
- Verified ✅

Every briefing also ends with meaningful hashtags based on the categories,
work modes, and locations in that day's list (for example
`#VerifiedInternships`, `#DigitalMarketing`, `#RemoteInternship`).

Dry-run with the bundled sample sources:

```bash
python3 daily_internship_intelligence_agent.py
```

The sample sources under `data/sample_sources/` contain 24 verified openings
across five categories. The agent also writes:

- `daily_internship_output/<date>-daily-internship-intelligence.txt`
- `daily_internship_output/<date>-daily-internship-intelligence.json`

Use your own source directory in production:

```bash
python3 daily_internship_intelligence_agent.py \
  --sources-path "/var/lib/worldofinterns/internship_sources"
```

Each source file can be either a JSON array of jobs or an object with metadata:

```json
{
  "source": "company_feeds",
  "collected_at": "2026-07-07T08:30:00Z",
  "jobs": [
    {
      "company": "NovaStack Labs",
      "role": "Backend Engineering Intern",
      "category": "Software Engineering",
      "location": "Bangalore",
      "stipend": "₹30,000/month",
      "work_mode": "Hybrid",
      "duration": "6 months",
      "apply_link": "https://example.com/jobs/novastack-backend",
      "last_date": "2026-07-20",
      "verified": true,
      "verification_notes": "Company website and LinkedIn verified"
    }
  ]
}
```

Only jobs marked `"verified": true` are included by default. To include
unverified jobs during testing:

```bash
python3 daily_internship_intelligence_agent.py --include-unverified
```

LinkedIn posts are limited to about 3000 characters. When the full daily list
is too long, the agent truncates the post and can point to a full list URL:

```bash
export INTERNSHIP_CONTINUE_URL="https://student.worldofinterns.com/internships"

python3 daily_internship_intelligence_agent.py \
  --continue-url "$INTERNSHIP_CONTINUE_URL"
```

To post only the daily summary block and link to the full verified list:

```bash
python3 daily_internship_intelligence_agent.py --summary-only --continue-url "$INTERNSHIP_CONTINUE_URL"
```

Post to LinkedIn:

```bash
export LINKEDIN_ACCESS_TOKEN="your-60-day-linkedin-token"
export LINKEDIN_MEMBER_ID="your-authenticated-linkedin-member-id"

python3 daily_internship_intelligence_agent.py --post
```

For a scheduled automation:

```bash
python3 daily_internship_intelligence_agent.py \
  --sources-path "/var/lib/worldofinterns/internship_sources" \
  --history-path "/var/lib/worldofinterns/daily_internship_history.json" \
  --output-dir "/var/lib/worldofinterns/daily_internship_output" \
  --post
```

| Variable | Description |
| --- | --- |
| `INTERNSHIP_SOURCES_PATH` | Directory or JSON file containing internship source feeds. |
| `INTERNSHIP_COLLECTOR_CONFIG` | JSON config for `collect_internships.py`. |
| `INTERNSHIP_LIVE_SOURCES_DIR` | Output directory for live scraped JSON feeds. |
| `INTERNSHIP_HISTORY_PATH` | JSON file for posted daily report tracking. |
| `INTERNSHIP_OUTPUT_DIR` | Directory for generated `.txt` and `.json` artifacts. |
| `INTERNSHIP_MAX_LINKEDIN_CHARS` | LinkedIn post character limit. Defaults to `3000`. |
| `INTERNSHIP_CONTINUE_URL` | Optional URL for full list when post is truncated or summary-only. |

## Configuration

| Variable | Description |
| --- | --- |
| `LINKEDIN_ACCESS_TOKEN` | LinkedIn API bearer token. Required with `--post`. |
| `LINKEDIN_POST_AS` | Optional author type: `organization` or `member`. Defaults to `organization`. |
| `LINKEDIN_ORGANIZATION_ID` | Numeric organization id used to build `urn:li:organization:<id>`. |
| `LINKEDIN_ORGANIZATION_URN` | Full organization URN. Takes priority over organization id. |
| `LINKEDIN_MEMBER_ID` | Authenticated LinkedIn member id used to build `urn:li:person:<id>`. |
| `LINKEDIN_MEMBER_URN` | Full member/person URN. Takes priority over member id. |
| `LINKEDIN_POST_MESSAGE` | Optional default message for the agent. |
| `LINKEDIN_IMAGE_PATH` | Optional local image path to upload and attach to the post. |
| `LINKEDIN_IMAGE_TITLE` | Optional title for the attached image. |
| `LINKEDIN_IMAGE_DESCRIPTION` | Optional description for the attached image. |
| `LINKEDIN_API_BASE_URL` | Optional API base URL. Defaults to `https://api.linkedin.com`. |
| `LINKEDIN_CLIENT_ID` | LinkedIn app client id used by `--auth-url`. |
| `LINKEDIN_REDIRECT_URI` | OAuth redirect URI used by `--auth-url`. |
| `LINKEDIN_OAUTH_SCOPES` | Optional space/comma-separated scopes for `--auth-url`. |
| `LINKEDIN_OAUTH_STATE` | Optional state value for `--auth-url`; generated when omitted. |
| `DAILY_STORY_HISTORY_PATH` | Optional JSON path for daily content tracking. |
| `DAILY_STORY_OUTPUT_DIR` | Optional directory for generated daily story images. |
| `DAILY_CONTENT_METRICS_PATH` | Optional JSON file for assessment, resume, skill gap, college, and ranking metrics. |
| `OPENAI_API_KEY` | Required for AI caption and image generation. |
| `OPENAI_TEXT_MODEL` | Optional OpenAI chat model. Defaults to `gpt-4o-mini`. |
| `OPENAI_IMAGE_MODEL` | Optional OpenAI image model. Defaults to `gpt-image-1`. |
| `OPENAI_IMAGE_SIZE` | Optional OpenAI image size. Defaults to `1024x1024`. |
