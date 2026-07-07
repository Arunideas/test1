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

The agent tracks used content in a JSON history file so successful posts are not
reused.

Each generated post is built as five assets:

1. `hook` - one sharp sentence.
2. `proof` - one screenshot/resume/recruiter-comment style example.
3. `insight` - one takeaway only.
4. `visual` - the image direction used for AI photo/card generation.
5. `question` - an interactive comment prompt.

The five assets are preserved in the JSON output and history tracking. The
LinkedIn caption is formatted as a natural post without exposing internal labels.

Public captions use a show-first style: strong hook, before/after proof, short
human insight, and a pillar-specific interactive checkbox question to invite
comments. They do not include a website CTA.

Dry-run generation:

```bash
python3 daily_story_linkedin_agent.py
```

By default the daily agent tries to create a photorealistic AI image with a
curiosity-driven scene, not a generic stock photo. Visual prompts focus on
evidence objects such as recruiter desks, rejected resumes, application
dashboards, scorecards, highlighted gaps, before/after profile screens, and
assessment results. Configure:

```bash
export OPENAI_API_KEY="your-openai-api-key"
```

If `OPENAI_API_KEY` is not available, the agent falls back to a local graphic
card image. To fail instead of falling back:

```bash
python3 daily_story_linkedin_agent.py --require-ai-image
```

To force the local card image:

```bash
python3 daily_story_linkedin_agent.py --image-mode card
```

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
  "campus_partner_title": "Campus Growth Partner"
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
| `DAILY_STORY_IMAGE_MODE` | Optional image mode: `ai` or `card`. Defaults to `ai`. |
| `DAILY_CONTENT_METRICS_PATH` | Optional JSON file for assessment, resume, skill gap, college, and ranking metrics. |
| `OPENAI_API_KEY` | Required for photorealistic AI story images. |
| `OPENAI_IMAGE_MODEL` | Optional OpenAI image model. Defaults to `gpt-image-1`. |
| `OPENAI_IMAGE_SIZE` | Optional OpenAI image size. Defaults to `1024x1024`. |
