#!/usr/bin/env bash
set -euo pipefail

echo "Claros deployment is defined only in .github/workflows/deploy.yml."
echo "Run it from GitHub Actions or with: gh workflow run deploy.yml"
exit 1

