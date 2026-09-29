import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.publishing import adapters, nodes


BLOG = {"title": "A useful guide", "content": "# Guide\n\nSafe Markdown.", "description": "Summary", "tags": ["python", "agents"], "cover_image": None, "canonical_url": ""}


class PublishingWorkflowTests(unittest.TestCase):
    def test_review_node_returns_structured_review(self):
        fake = Mock()
        fake.with_structured_output.return_value.invoke.return_value = {"status": "approved", "issues": [], "suggestions": []}
        with patch.object(nodes, "_llm", return_value=fake):
            result = nodes.review_node({"topic": "guide", "final": "# Guide", "plan": None, "evidence": []})
        self.assertEqual(result["review"]["status"], "approved")

    def test_revision_routes_back_to_review(self):
        self.assertEqual(nodes.route_blog_approval({"human_blog_decision": {"action": "revise"}}), "revision")

    def test_human_blog_approval_routes_to_parallel_sends(self):
        sends = nodes.route_blog_approval({"topic": "x", "final": "body", "human_blog_decision": {"action": "approve"}, "workflow_id": "run-1", "publish_platforms": ["wordpress", "ghost"]})
        self.assertEqual([send.node for send in sends], ["publisher", "publisher"])
        self.assertEqual({send.arg["platform"] for send in sends}, {"wordpress", "ghost"})

    def test_each_platform_adapter_is_invoked_independently(self):
        for platform in ("wordpress", "devto", "ghost"):
            with self.subTest(platform=platform), patch.object(nodes, f"publish_{'devto' if platform == 'devto' else platform}", return_value={"platform": platform, "status": "published", "url": "https://example.com/post", "post_id": "1", "error": None}) as publisher:
                result = nodes.publisher_task({"platform": platform, "blog": BLOG, "workflow_id": "run"})
                publisher.assert_called_once()
                self.assertEqual(result["published_results"][0]["status"], "published")

    def test_partial_failure_is_aggregated_without_cancelling_success(self):
        result = nodes.aggregate_publications({"published_results": [
            {"platform": "wordpress", "status": "published", "url": "https://sample.wordpress.com/a"},
            {"platform": "devto", "status": "failed", "url": None},
        ]})
        self.assertEqual(result["successful_platforms"], ["wordpress"])
        self.assertEqual(result["failed_platforms"], ["devto"])
        self.assertEqual(result["all_published_urls"], ["https://sample.wordpress.com/a"])
        self.assertEqual(result["primary_blog_url"], "https://sample.wordpress.com/a")

    def test_linkedin_content_node_uses_published_urls(self):
        fake = Mock()
        fake.with_structured_output.return_value.invoke.return_value = {"text": "Useful post #Python", "hashtags": ["Python"]}
        with patch.object(nodes, "_llm", return_value=fake):
            result = nodes.linkedin_content_node({"blog_plan": BLOG, "final": BLOG["content"], "published_links": {"devto": {"status": "published", "url": "https://dev.to/a"}}, "primary_blog_url": "https://dev.to/a"})
        self.assertIn("Useful post", result["linkedin_draft"]["text"])
        self.assertEqual(result["linkedin_draft"]["hashtags"], ["Python"])

    def test_linkedin_approval_edit_is_shown_again_before_publish(self):
        state = {"linkedin_draft": {"text": "Old"}}
        with patch.object(nodes, "interrupt", return_value={"action": "edit", "text": "Edited"}):
            updated = nodes.linkedin_approval_node(state)
        self.assertEqual(updated["linkedin_draft"]["text"], "Edited")
        self.assertEqual(nodes.route_linkedin_approval({**state, **updated}), "linkedin_approval")
        self.assertEqual(nodes.route_linkedin_approval({"linkedin_human_decision": {"action": "approve"}}), "linkedin_publish")

    def test_duplicate_protection_returns_previously_published_result(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"PUBLISHING_DB_PATH": os.path.join(tmp, "posts.db")}):
            send = Mock(return_value=("post-1", "https://example.com/post"))
            first = adapters._publish_once("wordpress", "workflow", BLOG, send)
            second = adapters._publish_once("wordpress", "workflow", BLOG, send)
        self.assertEqual(first["status"], "published")
        self.assertEqual(second["post_id"], "post-1")
        send.assert_called_once()

    def test_retry_transient_and_do_not_retry_permanent_4xx(self):
        transient = Mock()
        transient.side_effect = [Mock(status_code=503, headers={}), Mock(status_code=200, headers={}, ok=True)]
        with patch.object(adapters.requests, "request", transient), patch.object(adapters.time, "sleep"):
            self.assertEqual(adapters._request("GET", "https://example.com").status_code, 200)
        permanent = Mock(return_value=Mock(status_code=401, headers={}, ok=False))
        with patch.object(adapters.requests, "request", permanent):
            with self.assertRaisesRegex(RuntimeError, "http_401"):
                adapters._request("GET", "https://example.com")
        permanent.assert_called_once()

    def test_wordpress_com_official_rest_adapter(self):
        response = Mock()
        response.json.return_value = {"ID": 5, "URL": "https://sample.wordpress.com/post/"}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"WORDPRESS_SITE_ID": "123", "PUBLISHING_DB_PATH": os.path.join(tmp, "posts.db")}), patch("src.publishing.linkedin_oauth.get_wordpress_token", return_value="oauth-token"), patch("src.publishing.linkedin_oauth.get_wordpress_site_id", return_value="123"), patch.object(adapters, "_request", return_value=response) as request:
            result = adapters.publish_wordpress(BLOG, "wp-run")
        self.assertEqual(result["url"], "https://sample.wordpress.com/post/")
        self.assertIn("/rest/v1.1/sites/123/posts/new/", request.call_args.args[1])
        self.assertEqual(request.call_args.kwargs["data_body"]["status"], "publish")

    def test_devto_api_adapter(self):
        response = Mock()
        response.json.return_value = {"id": 12, "url": "https://dev.to/user/post"}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"DEV_API_KEY": "secret", "PUBLISHING_DB_PATH": os.path.join(tmp, "posts.db")}), patch.object(adapters, "_request", return_value=response) as request:
            result = adapters.publish_devto(BLOG, "dev-run")
        self.assertEqual(result["post_id"], "12")
        article = request.call_args.kwargs["json_body"]["article"]
        self.assertTrue(article["published"])
        self.assertEqual(article["body_markdown"], BLOG["content"])

    def test_ghost_api_adapter(self):
        response = Mock()
        response.json.return_value = {"posts": [{"id": "ghost-1", "url": "https://ghost.example.com/post"}]}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"GHOST_URL": "https://ghost.example.com", "GHOST_ADMIN_API_KEY": "kid:" + "ab" * 32, "PUBLISHING_DB_PATH": os.path.join(tmp, "posts.db")}), patch.object(adapters, "_request", return_value=response):
            result = adapters.publish_ghost(BLOG, "ghost-run")
        self.assertEqual(result["post_id"], "ghost-1")

    def test_linkedin_posts_api_adapter(self):
        response = Mock()
        response.headers = {"x-restli-id": "urn:li:share:123"}
        with patch.dict(os.environ, {"LINKEDIN_ACCESS_TOKEN": "token", "LINKEDIN_AUTHOR_URN": "urn:li:person:1"}), patch("src.publishing.linkedin_oauth.get_linkedin_token", return_value=None), patch("src.publishing.linkedin_oauth.get_linkedin_author", return_value="urn:li:person:1"), patch.object(adapters, "_request", return_value=response) as request:
            result = adapters.publish_linkedin("hello")
        self.assertEqual(result["status"], "published")
        self.assertIn("LinkedIn-Version", request.call_args.kwargs["headers"])


if __name__ == "__main__":
    unittest.main()
