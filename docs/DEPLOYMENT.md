# Deploying the Hospital Dashboard

The project is designed for **on-premise or internal cloud** only (no public cloud SaaS). Below are practical ways to deploy it.

---

## 1. Docker Compose (recommended)

Best for: a single Linux server (your own VM, internal data center, or a VPS you control).

### Requirements

- Linux server (e.g. Ubuntu 22.04, Debian 12) with Docker and Docker Compose
- Optional: domain or internal hostname, reverse proxy for HTTPS

### Steps

**1. Copy the project to the server**

```bash
# From your Mac, or clone from your repo
scp -r "/Users/esakkipandi/Desktop/Hospital Management" user@your-server:/opt/hospital-dashboard
ssh user@your-server "cd /opt/hospital-dashboard && docker compose up -d db api"
```

**2. On the server: apply schema and load data (first time only)**

```bash
cd /opt/hospital-dashboard

# If psql is installed on the server
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/hospital_analytics"
docker compose exec db psql -U postgres -d hospital_analytics -f - < database/schema.sql

# Seed data (run from host with Python, or use a one-off container)
docker compose run --rm -e DATABASE_URL=postgresql://postgres:postgres@db:5432/hospital_analytics api python database/seed_data.py
```

If the server doesn’t have `psql`, run schema from inside the API container by piping the file into the DB:

```bash
docker compose exec api sh -c 'cat database/schema.sql | PGPASSWORD=postgres psql -h db -U postgres -d hospital_analytics -f -'
docker compose run --rm -e DATABASE_URL=postgresql://postgres:postgres@db:5432/hospital_analytics api python database/seed_data.py
```

**3. (Optional) Run Superset**

```bash
docker compose up -d superset
# Superset: http://YOUR_SERVER_IP:8088  (admin / admin)
# In Superset, add DB: postgresql://postgres:postgres@db:5432/hospital_analytics
```

**4. Expose the API**

- **Direct:** Users hit `http://YOUR_SERVER_IP:8000` (docs at `/docs`).
- **Behind reverse proxy (recommended):** Put Nginx (or Caddy) in front and add HTTPS (see section 3).

**5. Restart and updates**

```bash
cd /opt/hospital-dashboard
docker compose pull   # if you use a registry
docker compose up -d --build
```

---

## 2. Manual deployment (no Docker)

Best for: a server where you install PostgreSQL, Python, and run the API (and optionally Superset) yourself.

### 2.1 Server prep (Ubuntu/Debian example)

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib python3.11 python3.11-venv python3-pip nginx libpq-dev
```

### 2.2 PostgreSQL

```bash
sudo -u postgres createuser -s hospital_app   # or use existing superuser
sudo -u postgres createdb -O hospital_app hospital_analytics
# If you set a password:
# sudo -u postgres psql -c "ALTER USER hospital_app PASSWORD 'your_secure_password';"
```

### 2.3 Application

```bash
sudo mkdir -p /opt/hospital-dashboard
# Copy project here (git clone, rsync, etc.)
cd /opt/hospital-dashboard

python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

export DATABASE_URL="postgresql://hospital_app:your_secure_password@localhost:5432/hospital_analytics"
psql "$DATABASE_URL" -f database/schema.sql
python database/seed_data.py
```

### 2.4 Run API with Gunicorn (production)

```bash
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

### 2.5 Systemd service (so it restarts on reboot)

Create `/etc/systemd/system/hospital-dashboard.service`:

```ini
[Unit]
Description=Hospital Dashboard API
After=network.target postgresql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/hospital-dashboard
Environment="DATABASE_URL=postgresql://hospital_app:your_secure_password@localhost:5432/hospital_analytics"
ExecStart=/opt/hospital-dashboard/venv/bin/gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable hospital-dashboard
sudo systemctl start hospital-dashboard
sudo systemctl status hospital-dashboard
```

The API listens on `127.0.0.1:8000`; Nginx (next step) will proxy to it.

---

## 3. Reverse proxy and HTTPS (recommended for production)

Use Nginx (or Caddy) in front of the API (and optionally Superset) to add HTTPS and optional auth.

### Nginx example (API only)

Install Nginx, then create a site config (e.g. `/etc/nginx/sites-available/hospital-dashboard`):

```nginx
server {
    listen 80;
    server_name your-domain.or.internal.hostname;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable and reload:

```bash
sudo ln -s /etc/nginx/sites-available/hospital-dashboard /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

For HTTPS, use Let’s Encrypt (if the server is reachable from the internet) or your internal CA:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.or.internal.hostname
```

If Superset runs on port 8088:

```nginx
location /superset/ {
    proxy_pass http://127.0.0.1:8088/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

---

## 4. Where you can deploy (on-premise / internal)

| Environment | How |
|-------------|-----|
| **Your own Linux VM / server** | Docker Compose or manual steps above. |
| **Internal data center** | Same; use internal DNS and firewall rules. |
| **VPS (e.g. DigitalOcean, Linode, self‑hosted)** | Treat as “your server”; use Docker Compose or manual. |
| **Internal Kubernetes** | Use the same Docker images; add Deployment + Service + Ingress for `api` and optional Superset; run PostgreSQL via operator or StatefulSet. |
| **Internal OpenStack / private cloud** | Deploy a VM, then follow Docker Compose or manual. |

Constraint: **no public cloud SaaS** (no managed DB or managed BI as a service). You run PostgreSQL, FastAPI, and Superset yourself (or on IaaS VMs/containers).

---

## 5. Security checklist

- Use **strong passwords** for PostgreSQL and Superset admin; store them in env or a secrets manager, not in code.
- Prefer **HTTPS** (reverse proxy + cert) for API and Superset.
- Restrict **firewall**: only expose 80/443 (and optionally 8088 for Superset) if needed; keep 5432 and 8000 internal.
- Run the app as a **non-root** user (e.g. `www-data` or a dedicated `hospital` user).
- Keep **dependencies** updated (`pip install -r requirements.txt` after updating the file; rebuild Docker images when you change code or deps).
- If the server is shared, consider **rate limiting** and **auth** (e.g. Nginx basic auth or an API key layer) for the API and Superset.

---

## 6. Summary

| Goal | Approach |
|------|----------|
| **Easiest** | Docker Compose on one Linux server; expose port 8000 (and 8088 for Superset) or put Nginx in front. |
| **No Docker** | Install PostgreSQL + Python on the server, run schema + seed, then Gunicorn + systemd; put Nginx in front for HTTPS. |
| **HTTPS / production** | Nginx (or Caddy) as reverse proxy; TLS via Let’s Encrypt or internal CA. |
| **Internal K8s** | Use the same images; define Deployment/Service/Ingress and a PostgreSQL instance (operator or StatefulSet). |

---

## 7. PaaS / hosted options (Render, Railway, Fly.io)

For **portfolio demos** or **non–on-premise** use, you can run the **FastAPI backend + PostgreSQL** on a hosted PaaS. Apache Superset usually runs separately (or is skipped) on these platforms.

### Render

**Good fit:** FastAPI API + PostgreSQL. Render has Web Services and managed Postgres.

**→ For a full step-by-step Render deploy, use [docs/DEPLOY_ON_RENDER.md](DEPLOY_ON_RENDER.md).**

Short version:

1. **Create a PostgreSQL database**  
   - [Dashboard](https://dashboard.render.com) → **New** → **PostgreSQL**.  
   - Note the **Internal Database URL** (use this from your API service).

2. **Create a Web Service for the API**  
   - **New** → **Web Service**.  
   - Connect your repo (GitHub/GitLab).  
   - **Root directory:** leave blank or set to repo root.  
   - **Build command:**  
     `pip install -r requirements.txt`  
   - **Start command:**  
     `gunicorn app.main:app -w 2 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT`  
   - **Environment:** Add `DATABASE_URL` = the **Internal Database URL** from step 1 (same Render account so it resolves).

3. **Apply schema and seed (first time)**  
   - Use **Shell** in the Web Service (if available), or run locally with `DATABASE_URL` set to the **External Database URL** from Render Postgres:  
     `psql "$DATABASE_URL" -f database/schema.sql`  
     `python database/seed_data.py`  
   - Or call your API after adding one-off ETL endpoints that run schema + seed (keep them disabled or protected in production).

4. **Result**  
   - API: `https://your-service-name.onrender.com` (docs at `/docs`).  
   - **Superset:** Not hosted on Render in this setup; run locally or on another service if needed.

**Note:** Free-tier services spin down after inactivity; first request may be slow.

---

### Railway

**Good fit:** FastAPI + Postgres in one project.

1. [Railway](https://railway.app) → **New Project** → **Deploy from GitHub** (your repo).  
2. Add **PostgreSQL** from the Railway dashboard; note `DATABASE_URL`.  
3. Add a **Service** for the API: use the same repo, set **Start Command** to:  
   `gunicorn app.main:app -w 2 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT`  
   and set `DATABASE_URL` from the Postgres service.  
4. Run schema + seed once (Railway CLI or one-off job):  
   `railway run psql $DATABASE_URL -f database/schema.sql`  
   `railway run python database/seed_data.py`  
5. API will be at `https://your-app.up.railway.app`.

---

### Fly.io

**Good fit:** Run the API and Postgres as Fly apps.

1. Install [flyctl](https://fly.io/docs/hands-on/install-flyctl/) and log in.  
2. From the project root:  
   `fly launch`  
   (add Postgres when prompted or with `fly postgres create`).  
3. Set `DATABASE_URL` to the Postgres connection string Fly gives you.  
4. **Start command:**  
   `gunicorn app.main:app -w 2 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8080`  
   (or use Fly’s `PORT` if set).  
5. Run schema + seed once via `fly ssh console` or a one-off run.  
6. API: `https://your-app-name.fly.dev`.

---

### Netlify

**Not a good fit** for this FastAPI backend.

- Netlify is built for **static sites** and **serverless functions** (short-lived, event-driven).  
- This app is a **long-running ASGI server** (FastAPI + Uvicorn/Gunicorn) with a persistent PostgreSQL connection.  
- Running it on Netlify would require turning the API into **Netlify Functions** (rewrite), which is a big change and not ideal for this codebase.

**You can use Netlify for:**  
- A **static frontend** (e.g. a simple HTML/JS dashboard that calls your API hosted on Render/Railway/Fly).  
- The **Hospital Dashboard API** itself should be deployed on **Render**, **Railway**, **Fly.io**, or your own server (sections 1–2).

---

## 8. Summary

| Goal | Approach |
|------|----------|
| **Easiest** | Docker Compose on one Linux server; expose port 8000 (and 8088 for Superset) or put Nginx in front. |
| **No Docker** | Install PostgreSQL + Python on the server, run schema + seed, then Gunicorn + systemd; put Nginx in front for HTTPS. |
| **HTTPS / production** | Nginx (or Caddy) as reverse proxy; TLS via Let’s Encrypt or internal CA. |
| **Internal K8s** | Use the same images; define Deployment/Service/Ingress and a PostgreSQL instance (operator or StatefulSet). |
| **PaaS (portfolio/demo)** | **Render** or **Railway** or **Fly.io** for FastAPI + Postgres; run schema + seed once; Superset elsewhere or skip. |
| **Netlify** | Use only for a static frontend; **do not** use for the FastAPI backend. |

For a **MacBook M1** you only run it locally (see `docs/RUN_ON_MAC_M1.md`). For **deployment**, use a Linux server (sections 1–2), internal K8s, or a PaaS (section 7) as above.
