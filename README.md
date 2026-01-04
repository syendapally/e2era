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

### Auth (session-based)
- `POST /api/auth/login/` (username/password form fields) sets a session cookie.
- `POST /api/auth/logout/` clears the session.
- `GET /api/auth/me/` returns the current user if authenticated.

### Database
- Defaults to SQLite if `DB_HOST` is unset.
- For RDS/Aurora Postgres: set `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_SSL_MODE=require` in the secret/.env. Run:
  ```
  docker compose run --rm backend python manage.py migrate
  docker compose run --rm backend python manage.py createsuperuser
  ```

### RDS/Aurora setup (Postgres)
1) In AWS console, create an Aurora Postgres (or RDS Postgres) instance/cluster in the same VPC as your EC2. Disable public access; use a Security Group that allows inbound 5432 from the EC2 instance’s SG.  
2) Note the endpoint, DB name, username, password.  
3) Update your existing Secrets Manager entry with:
   - `DB_HOST=<cluster-endpoint>`
   - `DB_PORT=5432`
   - `DB_NAME=<your-db-name>`
   - `DB_USER=<your-db-user>`
   - `DB_PASSWORD=<your-db-password>`
   - `DB_SSL_MODE=require`
   (Keep existing Django vars and secret key.)  
4) On EC2: `./scripts/fetch_secrets.sh`, then:
   ```
   docker compose build
   docker compose up -d
   docker compose run --rm backend python manage.py migrate
   docker compose run --rm backend python manage.py createsuperuser
   ```
5) Test:
   ```
   curl -I http://localhost/healthz
   curl -I http://localhost/api/health/
   curl -i http://localhost/api/auth/login/ -d "username=<user>&password=<pass>"
   curl -i http://localhost/api/auth/me/
   ```
