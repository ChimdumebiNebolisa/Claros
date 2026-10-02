"""Select Cloud Run's advertised URL and verify the public homepage."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from urllib.parse import urlsplit
from urllib.request import urlopen


def public_origin(service: dict, *, service_name: str, region: str) -> str:
    metadata = service.get("metadata", {})
    if metadata.get("name") != service_name:
        raise ValueError("Cloud Run returned a different service")
    advertised = metadata.get("annotations", {}).get("run.googleapis.com/urls", "[]")
    urls = json.loads(advertised) if isinstance(advertised, str) else advertised
    if not isinstance(urls, list):
        raise ValueError("Cloud Run's advertised URLs must be a list")
    # status.url can be the legacy hash-based alias. Use the same numeric
    # project URL that gcloud prints for users, without inventing a hostname.
    candidates = [*urls, service.get("status", {}).get("url")]
    pattern = re.compile(
        rf"https://{re.escape(service_name)}-[0-9]+\.{re.escape(region)}\.run\.app"
    )
    for candidate in candidates:
        if isinstance(candidate, str) and pattern.fullmatch(candidate):
            return candidate
    raise ValueError("Cloud Run did not return its advertised numeric public URL")


def resolve_public_origin(
    origin: str,
    *,
    service_name: str | None = None,
    region: str | None = None,
    project_id: str | None = None,
) -> str:
    """Resolve a legacy alias using the authenticated deployment CLI."""
    host = urlsplit(origin).hostname or ""
    if not host.endswith(".a.run.app"):
        return origin
    service_name = service_name or os.environ.get("SERVICE_NAME")
    region = region or os.environ.get("REGION")
    project_id = project_id or os.environ.get("PROJECT_ID")
    if not all((service_name, region, project_id)):
        raise ValueError("Cloud Run URL resolution requires service, region, and project")
    result = subprocess.run(
        [
            "gcloud", "run", "services", "describe", service_name,
            "--project", project_id, "--region", region, "--format=json",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return public_origin(json.loads(result.stdout), service_name=service_name, region=region)


def verify_homepage(origin: str) -> None:
    with urlopen(f"{origin}/", timeout=30) as response:
        if response.status != 200 or response.geturl() != f"{origin}/":
            raise ValueError("The advertised homepage must return HTTP 200 without redirecting")
        if "text/html" not in response.headers.get("Content-Type", ""):
            raise ValueError("The advertised homepage did not return HTML")
        html = response.read(512 * 1024).decode("utf-8")
        if "<title>Claros:" not in html or 'id="root"' not in html:
            raise ValueError("The advertised homepage did not return the Claros app")


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    select = commands.add_parser("select")
    select.add_argument("--service-name", required=True)
    select.add_argument("--region", required=True)
    check = commands.add_parser("check")
    check.add_argument("--origin", required=True)
    args = parser.parse_args()
    try:
        if args.command == "select":
            print(public_origin(json.load(sys.stdin), service_name=args.service_name, region=args.region))
        else:
            verify_homepage(args.origin)
            print("Public Claros homepage: HTTP 200")
    except (ValueError, OSError) as error:
        print(f"Public homepage verification failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())