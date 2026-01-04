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

escape_for_env() {
  # Escape $ for docker compose interpolation safety
  python3 - "$1" <<'PYCODE'
import sys
value = sys.argv[1]
print(value.replace("$", "$$"))
PYCODE
}

if [[ "${secret_raw:0:1}" == "{" ]]; then
  echo "Secret looks like JSON; rendering key=value lines to .env"
  env SECRET_RAW="$secret_raw" python3 - <<'PYCODE' > .env
import json, os

payload = json.loads(os.environ["SECRET_RAW"])
for key, value in payload.items():
    escaped = value.replace("$", "$$")
    print(f"{key}={escaped}")
PYCODE
else
  echo "Secret looks like plaintext; writing to .env"
  # Escape dollars in each line to avoid compose warnings
  printf "%s\n" "$secret_raw" | python3 - <<'PYCODE' > .env
import sys
for line in sys.stdin:
    line = line.rstrip("\n")
    if not line.strip() or "=" not in line:
        print(line)
        continue
    key, value = line.split("=", 1)
    value = value.replace("$", "$$")
    print(f"{key}={value}")
PYCODE
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

