# Deploy the Hospital Dashboard on Render — Step by Step

Follow these steps in order. You need a **GitHub** (or GitLab) repo with this project.

---

## Step 1: Push your project to GitHub

If the project is not in a repo yet:

```bash
cd "/Users/esakkipandi/Desktop/Hospital Management"
git init
git add .
git commit -m "Initial commit - Hospital Dashboard"
# Create a new repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git branch -M main
git push -u origin main
```

---

## Step 2: Create a PostgreSQL database on Render

1. Go to **[dashboard.render.com](https://dashboard.render.com)** and sign in (or sign up with GitHub).
2. Click **New +** → **PostgreSQL**.
3. Choose a **name** (e.g. `hospital-analytics-db`).
4. Pick **Region** (e.g. Oregon).
5. Select a **Plan** (Free or paid).
6. Click **Create Database**.
7. Wait until the DB is **Available**. Then open it and go to **Info** (or **Connect**).
8. Copy **Internal Database URL** (use this for the Web Service). It looks like:
   ```
   postgresql://user:password@dpg-xxxxx-a.oregon-postgres.render.com/hospital_analytics
   ```
   If the database name is different (e.g. `hospital_analytics_xxxx`), that’s fine — use the URL as given.

**Important:** The **Internal** URL only works from other Render services in the same account. You will need the **External** URL later to run schema and seed from your Mac.

---

## Step 3: Create the Web Service (API) on Render

1. In the Render dashboard, click **New +** → **Web Service**.
2. **Connect** your GitHub account if needed, then select the **repository** that contains this project.
3. Configure:
   - **Name:** e.g. `hospital-dashboard-api`
   - **Region:** same as the database (e.g. Oregon).
   - **Branch:** `main` (or the branch you use).
   - **Root Directory:** leave **empty** (project at repo root).
   - **Runtime:** **Python 3**.
   - **Build Command:**
     ```bash
     pip install -r requirements.txt
     ```
   - **Start Command:**
     ```bash
     gunicorn app.main:app -w 2 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT
     ```
4. **Plan:** Free or paid.
5. Click **Advanced** and add one **Environment Variable**:
   - **Key:** `DATABASE_URL`
   - **Value:** paste the **Internal Database URL** from Step 2 (the full `postgresql://...` string).
6. Click **Create Web Service**.

Render will build and deploy. Wait until the service shows **Live** (green). The first deploy may take a few minutes.

Your API URL will be like: `https://hospital-dashboard-api.onrender.com`  
Docs: `https://hospital-dashboard-api.onrender.com/docs`

---

## Step 4: Create the database and load data (first time only)

Render’s PostgreSQL is created empty. You must run the schema and seed **once** from your Mac (using the **External** DB URL).

### 4.1 Get the External Database URL

1. In Render dashboard, open your **PostgreSQL** service.
2. Under **Connect** / **Info**, copy the **External Database URL** (not Internal). It looks like:
   ```
   postgresql://user:password@dpg-xxxxx-a.oregon-postgres.render.com/hospital_analytics?sslmode=require
   ```
   If you see `sslmode=require`, keep it.

### 4.2 Run schema and seed on your Mac

Open Terminal on your Mac and run (replace the URL with your **External** URL):

```bash
cd "/Users/esakkipandi/Desktop/Hospital Management"

# Use the EXTERNAL Database URL from Render (with ?sslmode=require if present)
export DATABASE_URL="postgresql://USER:PASSWORD@HOST/DATABASE?sslmode=require"

# Create tables and views
psql "$DATABASE_URL" -f database/schema.sql

# Activate venv if you have one, then run seed
source venv/bin/activate   # if you use a venv
pip install -r requirements.txt   # if needed
python database/seed_data.py
```

If `psql` is not installed:

```bash
brew install libpq
brew link --force libpq
```

Then run the same `psql` and `python` commands again.

When seed finishes without errors, the database is ready. Your API on Render will now return data.

---

## Step 5: Verify the deployment

1. Open **https://YOUR-SERVICE-NAME.onrender.com** — you should see a short JSON response.
2. Open **https://YOUR-SERVICE-NAME.onrender.com/docs** — Swagger UI should load.
3. Try **GET /api/analytics/kpis** (with optional `date_from` / `date_to`) — you should get KPI data.

If you get **503** or timeouts on the first request after a while, that’s normal on the **free tier**: the service spins down when idle; the next request wakes it up (may take 30–60 seconds).

---

## Step 6: (Optional) Run schema/seed via API instead of Mac

If you prefer not to use `psql` from your Mac, you can run schema and seed once via the API after deploy:

1. In Render, add a **secret** env var (e.g. `RUN_ETL_SECRET=your-secret-string`).
2. Call from your machine (replace URL and secret):
   ```bash
   curl -X POST "https://YOUR-SERVICE-NAME.onrender.com/api/etl/run-schema" \
     -H "Authorization: Bearer your-secret-string"
   curl -X POST "https://YOUR-SERVICE-NAME.onrender.com/api/etl/seed" \
     -H "Authorization: Bearer your-secret-string"
   ```
   **Note:** The current API does **not** enforce this header; it’s for your own tracking. For real security, you’d add a check in the app for `RUN_ETL_SECRET` before running ETL. For now, running schema/seed from your Mac (Step 4) is simpler and recommended.

---

## Checklist

| Step | What you did |
|------|----------------|
| 1 | Pushed project to GitHub |
| 2 | Created PostgreSQL on Render, copied **Internal** and **External** URLs |
| 3 | Created Web Service, set Build/Start commands and `DATABASE_URL` (Internal URL) |
| 4 | Ran `psql ... -f database/schema.sql` and `python database/seed_data.py` with **External** URL from your Mac |
| 5 | Checked `/` and `/docs` and `/api/analytics/kpis` |

---

## Troubleshooting

- **Build fails:** Check the Render **Logs** tab. Often it’s a missing dependency in `requirements.txt` or wrong **Root Directory**.
- **Service won’t start:** Ensure **Start Command** is exactly:
  `gunicorn app.main:app -w 2 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT`
- **Database connection errors:** Confirm `DATABASE_URL` in the Web Service is the **Internal** URL (not External), and that it has no extra spaces or quotes.
- **Empty or 500 on /api/analytics/kpis:** You probably didn’t run schema and seed (Step 4). Run them with the **External** URL from your Mac.
- **First request very slow:** On the free tier, the service sleeps when idle; the first request after that wakes it (30–60 s). Subsequent requests are fast.

---

## Summary

1. **PostgreSQL** on Render → copy Internal + External URL.  
2. **Web Service** on Render → repo, `pip install -r requirements.txt`, gunicorn start command, `DATABASE_URL` = Internal URL.  
3. From your **Mac**: `psql` (schema) + `python database/seed_data.py` (seed) using External URL.  
4. Use **https://YOUR-SERVICE.onrender.com/docs** to call the API.

Apache Superset is not part of this Render deploy; run it locally (see README) if you need the dashboards.
