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

def escape(val: str) -> str:
    return val.replace("$", "$$")

payload = json.loads(os.environ["SECRET_RAW"])

# Map standard RDS secret keys if present
host = payload.get("host")
user = payload.get("username")
password = payload.get("password")
dbname = payload.get("dbname")
port = payload.get("port")
engine = payload.get("engine")

seen = set()
if host:
    print(f"DB_HOST={escape(str(host))}")
    seen.add("DB_HOST")
if user:
    print(f"DB_USER={escape(str(user))}")
    seen.add("DB_USER")
if password:
    print(f"DB_PASSWORD={escape(str(password))}")
    seen.add("DB_PASSWORD")
if dbname:
    print(f"DB_NAME={escape(str(dbname))}")
    seen.add("DB_NAME")
if port:
    print(f"DB_PORT={escape(str(port))}")
    seen.add("DB_PORT")
if engine:
    print(f"DB_ENGINE={escape(str(engine))}")
    seen.add("DB_ENGINE")

# Also emit all keys verbatim -> env-friendly names (uppercase), but don't override mapped DB_* above
for key, value in payload.items():
    env_key = key.upper()
    if env_key in seen:
        continue
    print(f"{env_key}={escape(str(value))}")
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

