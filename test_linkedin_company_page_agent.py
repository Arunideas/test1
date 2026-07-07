import io
import json
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
            access_token="token",
            organization_id="urn:li:organization:12345",
        )

        self.assertEqual(config.author_urn, "urn:li:organization:12345")

    def test_build_post_payload_uses_linkedin_ugc_shape(self):
        agent = LinkedInCompanyPageAgent(
            LinkedInConfig(access_token="token", organization_id="12345"),
        )

        payload = agent.build_post_payload("  Hello from tests  ")

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

        self.assertEqual(exit_code, 1)

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

    @patch.dict("os.environ", {}, clear=True)
    def test_post_requires_credentials(self):
        error = io.StringIO()

        with redirect_stderr(error):
            exit_code = main(["--post"])

        self.assertEqual(exit_code, 1)
        self.assertIn("LINKEDIN_ACCESS_TOKEN", error.getvalue())
        self.assertIn("LINKEDIN_ORGANIZATION_ID", error.getvalue())

    def test_post_message_sends_expected_request(self):
        captured = {}

        class FakeResponse:
            status = 201
            headers = {"Location": "urn:li:share:abc"}

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return b'{"id": "abc"}'

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["headers"] = dict(request.header_items())
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            captured["method"] = request.get_method()
            return FakeResponse()

        config = LinkedInConfig(
            access_token="token-value",
            organization_id="12345",
            endpoint="https://example.test/ugcPosts",
            timeout_seconds=3.0,
        )

        with patch("linkedin_company_page_agent.urllib.request.urlopen", fake_urlopen):
            result = LinkedInCompanyPageAgent(config).post_message("Request test")

        self.assertEqual(result["status"], 201)
        self.assertEqual(result["body"], {"id": "abc"})
        self.assertEqual(captured["url"], "https://example.test/ugcPosts")
        self.assertEqual(captured["timeout"], 3.0)
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer token-value")
        self.assertEqual(captured["headers"]["Content-type"], "application/json")
        self.assertEqual(
            captured["headers"]["X-restli-protocol-version"],
            "2.0.0",
        )
        self.assertEqual(captured["payload"]["author"], "urn:li:organization:12345")


if __name__ == "__main__":
    unittest.main()
