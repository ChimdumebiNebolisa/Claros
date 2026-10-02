"""Public deployment URLs must match the advertised, reachable homepage."""

import runpy
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

HELPERS = runpy.run_path(str(Path(__file__).resolve().parents[3] / "scripts/gate3-public-url.py"))
SELECT = HELPERS["public_origin"]
CHECK = HELPERS["verify_homepage"]
RESOLVE = HELPERS["resolve_public_origin"]
ORIGIN = "https://claros-123456789.us-central1.run.app"


class PublicUrlTests(unittest.TestCase):
    def service(self, urls=None):
        return {
            "metadata": {
                "name": "claros",
                "annotations": {"run.googleapis.com/urls": urls or f'["{ORIGIN}"]'},
            },
            "status": {"url": "https://claros-hash-uc.a.run.app"},
        }

    def select(self, service):
        return SELECT(service, service_name="claros", region="us-central1")

    def test_advertised_numeric_url_wins_over_legacy_status_url(self):
        self.assertEqual(self.select(self.service()), ORIGIN)

    def test_numeric_status_url_is_supported(self):
        service = self.service("[]")
        service["status"]["url"] = ORIGIN
        self.assertEqual(self.select(service), ORIGIN)

    def test_missing_advertised_url_fails_explicitly(self):
        with self.assertRaises(ValueError):
            self.select(self.service("[]"))

    def test_other_services_and_regions_are_rejected(self):
        for url in (ORIGIN.replace("claros-", "other-"), ORIGIN.replace("us-central1", "us-east1")):
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.select(self.service(f'["{url}"]'))

    def test_untrusted_url_syntax_is_rejected(self):
        for url in (ORIGIN + "/evil", ORIGIN.replace("https:", "http:"), ORIGIN + ".evil.com"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.select(self.service(f'["{url}"]'))

    def test_service_identity_is_checked(self):
        service = self.service()
        service["metadata"]["name"] = "other"
        with self.assertRaises(ValueError):
            self.select(service)

    def test_non_cloud_run_origins_do_not_call_gcloud(self):
        with patch.object(RESOLVE.__globals__["subprocess"], "run") as run:
            self.assertEqual(RESOLVE("https://claros.example"), "https://claros.example")
            self.assertEqual(RESOLVE(ORIGIN), ORIGIN)
            run.assert_not_called()

    def test_legacy_origin_is_resolved_from_authenticated_service_metadata(self):
        import json

        with patch.object(
            RESOLVE.__globals__["subprocess"], "run",
            return_value=SimpleNamespace(stdout=json.dumps(self.service())),
        ) as run:
            self.assertEqual(
                RESOLVE(
                    "https://claros-hash-uc.a.run.app",
                    service_name="claros", region="us-central1", project_id="claros-project",
                ),
                ORIGIN,
            )
            self.assertEqual(run.call_args.kwargs["check"], True)
            self.assertEqual(run.call_args.args[0][-1], "--format=json")

    def test_renderer_configures_the_advertised_host(self):
        import json

        root = Path(__file__).resolve().parents[3]
        renderer = runpy.run_path(str(root / "scripts/gate3-container-render.py"))
        with patch.object(
            RESOLVE.__globals__["subprocess"], "run",
            return_value=SimpleNamespace(stdout=json.dumps(self.service())),
        ):
            rendered = renderer["render_template"](
                (root / "deploy/cloud-run.service.template.yaml").read_text(),
                project_id="claros-project", region="us-central1", service_name="claros",
                image_uri="us-central1-docker.pkg.dev/claros-project/cloud-run-source-deploy/claros@sha256:" + "a" * 64,
                gcs_bucket="claros-tests", public_origin="https://claros-hash-uc.a.run.app",
                release_sha="b" * 40, cookie_secret_version="1",
                review_secret_version="2", openai_secret_version="3",
            )
        self.assertIn(ORIGIN, rendered)
        self.assertNotIn("claros-hash-uc.a.run.app", rendered)

    def test_smoke_uses_the_same_advertised_host(self):
        import json

        root = Path(__file__).resolve().parents[3]
        smoke = runpy.run_path(str(root / "scripts/gate3-container-staging-smoke.py"))
        with patch.dict("os.environ", {
            "SERVICE_NAME": "claros", "REGION": "us-central1", "PROJECT_ID": "claros-project",
        }), patch.object(
            RESOLVE.__globals__["subprocess"], "run",
            return_value=SimpleNamespace(stdout=json.dumps(self.service())),
        ):
            self.assertEqual(smoke["base_url"]("https://claros-hash-uc.a.run.app"), ORIGIN)

    def response(self):
        response = MagicMock()
        response.status = 200
        response.geturl.return_value = ORIGIN + "/"
        response.headers = {"Content-Type": "text/html; charset=utf-8"}
        response.read.return_value = b'<title>Claros: homepage</title><div id="root"></div>'
        response.__enter__.return_value = response
        return response

    def test_homepage_is_checked(self):
        with patch.dict(CHECK.__globals__, {"urlopen": MagicMock(return_value=self.response())}):
            CHECK(ORIGIN)

    def test_bad_status_redirect_and_wrong_page_are_rejected(self):
        for kind in ("status", "redirect", "content_type", "html"):
            response = self.response()
            if kind == "status":
                response.status = 400
            elif kind == "redirect":
                response.geturl.return_value = "https://other.example/"
            elif kind == "content_type":
                response.headers = {"Content-Type": "application/json"}
            else:
                response.read.return_value = b"Invalid host header"
            with self.subTest(kind=kind), patch.dict(
                CHECK.__globals__, {"urlopen": MagicMock(return_value=response)}
            ), self.assertRaises(ValueError):
                CHECK(ORIGIN)


if __name__ == "__main__":
    unittest.main()