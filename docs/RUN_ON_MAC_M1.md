# Running on MacBook M1 Air

Step-by-step guide to run the Hospital Dashboard on macOS (Apple Silicon M1).

---

## Option A: Native (Homebrew + Python)

### 1. Install PostgreSQL

```bash
# Install PostgreSQL 15
brew install postgresql@15

# Start PostgreSQL (run in background)
brew services start postgresql@15

# Create database (default user is your Mac username; no password on local)
createdb hospital_analytics
```

If `createdb` fails with "role does not exist", create a superuser first:

```bash
# Create postgres user (optional – only if you need it)
createuser -s postgres
# Then: createdb -U postgres hospital_analytics
```

If you prefer the default Mac user as DB owner:

```bash
createdb hospital_analytics
# Connection will be: postgresql://YOUR_MAC_USERNAME@localhost:5432/hospital_analytics
```

### 2. Install Python dependencies

```bash
cd "/Users/esakkipandi/Desktop/Hospital Management"

# Use Python 3.10+ (check: python3 --version)
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Apply schema and load data

**If your DB user is `postgres` with password `postgres`:**

```bash
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/hospital_analytics"
psql "$DATABASE_URL" -f database/schema.sql
python database/seed_data.py
```

**If you use your Mac username (no password):**

```bash
export DATABASE_URL="postgresql://$(whoami)@localhost:5432/hospital_analytics"
# or explicitly, e.g.:
# export DATABASE_URL="postgresql://esakkipandi@localhost:5432/hospital_analytics"

psql "$DATABASE_URL" -f database/schema.sql
python database/seed_data.py
```

### 4. Run the API

```bash
# From project root, with venv activated
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- **API:** http://localhost:8000  
- **Docs:** http://localhost:8000/docs  

---

## Option B: Docker (PostgreSQL + API on M1)

Docker Desktop for Mac supports Apple Silicon. Use it if you prefer everything in containers.

### 1. Install Docker Desktop

- Download from https://www.docker.com/products/docker-desktop/
- Choose **Apple Chip** version and install.

### 2. Start database and API

```bash
cd "/Users/esakkipandi/Desktop/Hospital Management"

docker compose up -d db api
```

Wait ~10 seconds for the DB to be ready, then apply schema and seed (from your Mac, not inside container):

```bash
# Install psql if needed: brew install libpq && brew link --force libpq
export PGHOST=localhost PGPORT=5432 PGUSER=postgres PGPASSWORD=postgres PGDATABASE=hospital_analytics
psql -h localhost -U postgres -d hospital_analytics -f database/schema.sql

export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/hospital_analytics"
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python database/seed_data.py
```

If you don’t have `psql` on the host, run schema and seed inside the API container (after first run):

```bash
docker compose exec api python -c "
import os
os.environ['DATABASE_URL'] = 'postgresql://postgres:postgres@db:5432/hospital_analytics'
# Schema: run via psql from host, or add a small script that runs schema.sql
"
# Seed (DB must be up and schema applied):
docker compose run --rm -e DATABASE_URL=postgresql://postgres:postgres@db:5432/hospital_analytics api python database/seed_data.py
```

Easiest is: run schema + seed **on your Mac** with `psql` and `python` as in Option A, but use `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/hospital_analytics` while `docker compose up -d db api` is running.

### 3. Open the API

- **API:** http://localhost:8000  
- **Docs:** http://localhost:8000/docs  

---

## Optional: Apache Superset on M1

### Native (pip)

```bash
cd "/Users/esakkipandi/Desktop/Hospital Management"
source venv/bin/activate
pip install apache-superset
superset db upgrade
export FLASK_APP=superset.app
superset fab create-admin --username admin --firstname Admin --lastname User --email admin@localhost --password admin
superset init
superset load_examples --no  # optional
superset run -h 0.0.0.0 -p 8088
```

Then in Superset: **Data → Databases → + Database → PostgreSQL**  
URI: `postgresql://postgres:postgres@host.docker.internal:5432/hospital_analytics` (if Superset runs in Docker) or `postgresql://YOUR_USER@localhost:5432/hospital_analytics` (if Superset runs natively).

### Docker

```bash
docker compose up -d superset
# Superset: http://localhost:8088 (admin / admin)
# Add database: postgresql://postgres:postgres@db:5432/hospital_analytics
```

---

## Quick reference (native on M1)

```bash
cd "/Users/esakkipandi/Desktop/Hospital Management"
brew install postgresql@15
brew services start postgresql@15
createdb hospital_analytics

python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

export DATABASE_URL="postgresql://$(whoami)@localhost:5432/hospital_analytics"   # or postgres:postgres if you set that up
psql "$DATABASE_URL" -f database/schema.sql
python database/seed_data.py

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# → http://localhost:8000/docs
```

If anything fails, check: PostgreSQL is running (`brew services list`), database exists (`psql -l`), and `DATABASE_URL` matches your user/host/port.
