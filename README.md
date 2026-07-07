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
| `LINKEDIN_API_BASE_URL` | Optional API base URL. Defaults to `https://api.linkedin.com`. |
| `LINKEDIN_CLIENT_ID` | LinkedIn app client id used by `--auth-url`. |
| `LINKEDIN_REDIRECT_URI` | OAuth redirect URI used by `--auth-url`. |
| `LINKEDIN_OAUTH_SCOPES` | Optional space/comma-separated scopes for `--auth-url`. |
| `LINKEDIN_OAUTH_STATE` | Optional state value for `--auth-url`; generated when omitted. |
