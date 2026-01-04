# E2ERA Hello World

React + Django + Nginx, orchestrated with Docker Compose. Frontend serves a simple tab UI, backend exposes `/api/hello/` and `/api/health/`, Nginx fronts both.

### Prereqs
- Docker + Docker Compose plugin
- AWS CLI (for secrets fetching) configured with access to Secrets Manager
- Python 3 if you want to run Django locally outside containers

### Secrets
Keep runtime env in AWS Secrets Manager. Expect either:
- Plaintext `.env` style in the secret value, **or**
- JSON object (converted to `.env` automatically).

Sample values live in `env.example`.

Fetch to `.env`:
```
export AWS_REGION=us-east-1
export AWS_SECRET_ID=e2era-app-secrets
chmod +x scripts/fetch_secrets.sh
./scripts/fetch_secrets.sh
```

### Local (containers)
```
docker compose build
docker compose up -d
# open http://localhost (nginx → frontend, /api/* → backend)
```

### Local (backend bare)
```
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

### Deployment to EC2 (single host)
1) Provision EC2 (e.g., Ubuntu 22.04); Security Group open 80/443 public, 22 only from your IP.  
2) Install Docker + Compose plugin + AWS CLI.  
3) Clone repo (or pull images from your registry).  
4) Fetch secrets to `.env` with the script above.  
5) `docker compose pull` (if using a registry) or `docker compose build`.  
6) `docker compose up -d`.  
7) Hit `http://<public-ip>/`.

Auto-start on reboot: add a simple systemd unit that runs `scripts/fetch_secrets.sh` then `docker compose up -d`.

### Compose services
- `frontend`: Vite-built React served via `serve` on 3000 (internal only)
- `backend`: Django + gunicorn on 8000 (internal only)
- `nginx`: exposes 80, proxies `/` → frontend, `/api/` → backend

### Health endpoints
- Nginx: `/healthz`
- Backend: `/api/health/`
