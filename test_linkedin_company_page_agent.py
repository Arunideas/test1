import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from linkedin_company_page_agent import (
    DEFAULT_MESSAGE,
    LinkedInCompanyPageAgent,
    LinkedInConfig,
    main,
)


class LinkedInCompanyPageAgentTests(unittest.TestCase):
    def test_author_urn_accepts_numeric_organization_id(self):
        config = LinkedInConfig(access_token="token", organization_id="12345")

        self.assertEqual(config.author_urn, "urn:li:organization:12345")

    def test_author_urn_accepts_full_organization_urn(self):
        config = LinkedInConfig(
            access_token="token", organization_id="urn:li:organization:12345"
        )

        self.assertEqual(config.author_urn, "urn:li:organization:12345")

    def test_build_post_payload_uses_linkedin_ugc_shape(self):
        agent = LinkedInCompanyPageAgent(
            LinkedInConfig(access_token="token", organization_id="12345")
        )

        payload = agent.build_post_payload("Hello from tests")

        self.assertEqual(payload["author"], "urn:li:organization:12345")
        self.assertEqual(payload["lifecycleState"], "PUBLISHED")
        self.assertEqual(
            payload["specificContent"]["com.linkedin.ugc.ShareContent"][
                "shareCommentary"
            ]["text"],
            "Hello from tests",
        )
        self.assertEqual(
            payload["specificContent"]["com.linkedin.ugc.ShareContent"][
                "shareMediaCategory"
            ],
            "NONE",
        )
        self.assertEqual(
            payload["visibility"]["com.linkedin.ugc.MemberNetworkVisibility"],
            "PUBLIC",
        )

    @patch.dict("os.environ", {}, clear=True)
    def test_main_defaults_to_dry_run(self):
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main([])

        self.assertEqual(exit_code, 0)
        self.assertIn("Dry run: no message was posted.", output.getvalue())
        self.assertIn(DEFAULT_MESSAGE, output.getvalue())
        self.assertIn("<set LINKEDIN_ORGANIZATION_ID>", output.getvalue())

    def test_main_rejects_empty_message(self):
        with redirect_stderr(io.StringIO()):
            exit_code = main(["--message", "   "])

        self.assertEqual(exit_code, 2)

    @patch.dict(
        "os.environ",
        {
            "LINKEDIN_ACCESS_TOKEN": "token",
            "LINKEDIN_ORGANIZATION_ID": "999",
        },
        clear=True,
    )
    @patch("linkedin_company_page_agent.LinkedInCompanyPageAgent.post_message")
    def test_main_posts_when_explicitly_requested(self, post_message):
        post_message.return_value = {"status": 201, "headers": {}, "body": None}
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(["--message", "Post this", "--post"])

        self.assertEqual(exit_code, 0)
        post_message.assert_called_once_with("Post this")
        self.assertIn("posted successfully", output.getvalue())
        self.assertIn('"status": 201', output.getvalue())


if __name__ == "__main__":
    unittest.main()
