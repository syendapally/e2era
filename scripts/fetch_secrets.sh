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

AWS_REGION="${AWS_REGION:-us-east-1}"
: "${AWS_REGION:?AWS_REGION is required (defaulted to us-east-1 if unset)}"
: "${AWS_SECRET_ID:?AWS_SECRET_ID is required}"

secret_raw=$(aws secretsmanager get-secret-value \
  --region "$AWS_REGION" \
  --secret-id "$AWS_SECRET_ID" \
  --query SecretString \
  --output text)

if [[ "${secret_raw:0:1}" == "{" ]]; then
  echo "Secret looks like JSON; rendering key=value lines to .env"
  env SECRET_RAW="$secret_raw" python3 - <<'PYCODE' > .env
import json, os

payload = json.loads(os.environ["SECRET_RAW"])
for key, value in payload.items():
    print(f"{key}={value}")
PYCODE
else
  echo "Secret looks like plaintext; writing to .env"
  printf "%s\n" "$secret_raw" > .env
fi

python3 - <<'PYCODE' > .env.exports
from pathlib import Path

lines = []
for raw in Path(".env").read_text().splitlines():
    stripped = raw.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        continue
    key, value = stripped.split("=", 1)
    lines.append(f'export {key}="{value}"')

Path(".env.exports").write_text("\n".join(lines) + ("\n" if lines else ""))
PYCODE

echo ".env updated from Secrets Manager"
echo ".env.exports generated (source it to export env vars):"
echo "  source .env.exports"

