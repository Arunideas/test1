# LinkedIn Company Page Agent

This repository includes a small Python agent that can publish a text-only test
message to a LinkedIn company page.

The default sample message is:

```text
This is a sample company page test post from the LinkedIn Company Page Agent.
```

## Requirements

- Python 3.10 or newer
- A LinkedIn access token with permission to post for the company page
- The LinkedIn organization ID for the company page

Do not commit access tokens or other secrets to this repository.

## Dry run

Use a dry run first to inspect the payload without posting to LinkedIn:

```bash
python3 linkedin_company_page_agent.py \
  --organization-id 123456 \
  --dry-run
```

## Publish the sample message

Export the required credentials, then run the agent:

```bash
export LINKEDIN_ACCESS_TOKEN="your-linkedin-access-token"
export LINKEDIN_ORGANIZATION_ID="123456"

python3 linkedin_company_page_agent.py
```

To customize the text:

```bash
python3 linkedin_company_page_agent.py \
  --message "Testing a LinkedIn company page post from the automation agent."
```

The agent uses LinkedIn's UGC Posts API endpoint:
`https://api.linkedin.com/v2/ugcPosts`.
