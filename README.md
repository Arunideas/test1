# LinkedIn Company Page Agent

This repository includes a small Python agent that can post a sample text update
to a LinkedIn company page.

## Dry-run test

Dry-run mode is the default and does not call LinkedIn:

```bash
python3 linkedin_company_page_agent.py
```

To preview a custom message:

```bash
python3 linkedin_company_page_agent.py --message "Sample company page test message."
```

## Publish to LinkedIn

Set the required credentials, then pass `--post`:

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

## Configuration

| Variable | Description |
| --- | --- |
| `LINKEDIN_ACCESS_TOKEN` | LinkedIn API bearer token. Required with `--post`. |
| `LINKEDIN_ORGANIZATION_ID` | Numeric organization id used to build `urn:li:organization:<id>`. |
| `LINKEDIN_ORGANIZATION_URN` | Full organization URN. Takes priority over organization id. |
| `LINKEDIN_POST_MESSAGE` | Optional default message for the agent. |
| `LINKEDIN_API_BASE_URL` | Optional API base URL. Defaults to `https://api.linkedin.com`. |
