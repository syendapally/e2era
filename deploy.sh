#!/usr/bin/env bash
set -euo pipefail

# Deploy/update helper for EC2 host.
# Usage:
#   ./deploy.sh
#
# Prereqs on the host:
# - Docker + docker compose plugin
# - AWS CLI with permission to read the secret below
# - Git (if pulling updates)
#
# Notes:
# - Update AWS_SECRET_ID / AWS_REGION below if needed.
# - This script rebuilds images; remove --build/--no-cache if you only want to pull.

AWS_SECRET_ID=${AWS_SECRET_ID:-e2era-app-dev-secrets}
AWS_REGION=${AWS_REGION:-us-east-1}

echo "Using secret: $AWS_SECRET_ID (region: $AWS_REGION)"

chmod +x scripts/fetch_secrets.sh
AWS_SECRET_ID="$AWS_SECRET_ID" AWS_REGION="$AWS_REGION" ./scripts/fetch_secrets.sh

echo "Stopping existing stack..."
docker compose down || true

echo "Building images..."
docker compose build --no-cache

echo "Starting stack..."
docker compose up -d

echo "Running migrations..."
docker compose run --rm backend python manage.py migrate

echo "Done. Health checks:"
echo "  curl -I http://localhost/healthz"
echo "  curl -I http://localhost/api/health/"

