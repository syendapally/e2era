#!/usr/bin/env bash
set -euo pipefail

# Requires: AWS CLI configured with permissions for Secrets Manager.
# Usage:
#   export AWS_REGION=us-east-1
#   export AWS_SECRET_ID=e2era-app-secrets
#   ./scripts/fetch_secrets.sh
#
# The secret value can be either:
# - Plaintext .env style (KEY=VALUE per line), which is written as-is
# - JSON object, which will be rendered to KEY=VALUE lines

: "${AWS_REGION:?AWS_REGION is required}"
: "${AWS_SECRET_ID:?AWS_SECRET_ID is required}"

secret_raw=$(aws secretsmanager get-secret-value \
  --region "$AWS_REGION" \
  --secret-id "$AWS_SECRET_ID" \
  --query SecretString \
  --output text)

if [[ "${secret_raw:0:1}" == "{" ]]; then
  echo "Secret looks like JSON; rendering key=value lines to .env"
  python3 - <<'PYCODE' "$secret_raw" > .env
import json, os, sys
payload = json.loads(os.environ["secret_raw"])
for key, value in payload.items():
    print(f"{key}={value}")
PYCODE
else
  echo "Secret looks like plaintext; writing to .env"
  printf "%s\n" "$secret_raw" > .env
fi

echo ".env updated from Secrets Manager"

