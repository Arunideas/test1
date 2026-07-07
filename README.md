# LinkedIn Company Page Test Agent

This repository includes a small Python agent that can post a sample text
message to a LinkedIn company page using LinkedIn's UGC Posts API.

The agent is dependency-free and defaults to a dry run so test executions do
not accidentally publish content.

## Configuration

Set these environment variables before publishing:

```bash
export LINKEDIN_ACCESS_TOKEN="your-linkedin-access-token"
export LINKEDIN_ORGANIZATION_ID="your-company-organization-id"
```

`LINKEDIN_ORGANIZATION_ID` can be either the numeric organization ID or the full
URN, such as `urn:li:organization:123456`.

The access token must have the LinkedIn permissions required to create
organization posts. Do not commit access tokens or other secrets to this
repository.

## Dry run

Preview the payload without posting:

```bash
python3 linkedin_company_page_agent.py
```

Use a custom sample message:

```bash
python3 linkedin_company_page_agent.py --message "Sample company page test post."
```

## Publish a test message

After setting the required environment variables, publish with:

```bash
python3 linkedin_company_page_agent.py \
  --message "Sample company page test post from automation." \
  --post
```

You can also pass `--organization-id` and `--access-token` directly, but
environment variables are preferred so secrets do not appear in shell history.

## Run tests

```bash
python3 -m unittest
```
