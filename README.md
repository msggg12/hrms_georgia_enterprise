# HRMS Georgia Enterprise

Production-oriented, multi-tenant HRMS for Georgia with FastAPI, React, PostgreSQL, Redis, attendance hardware sync, payroll exports, Mattermost integration, ESS, and operational monitoring.

## What Boots Automatically

On the first `docker compose up --build -d`, the app container now runs:

1. `python scripts/init_db.py`
2. schema migration from `sql/001_hrms_schema.sql`
3. enterprise extensions from `sql/002_enterprise_extensions.sql`
4. public holiday seed
5. superadmin bootstrap
6. full demo dataset seed from `scripts/seed_db.py`

The demo seed is idempotent. It is tracked in `demo_seed_runs` and will not duplicate the dataset on later restarts.

## Demo Dataset

The startup seed creates:

- 3 legal entities
- 22 employees per entity profile set, including line managers and login identities
- tenant domains:
  - `company1.test.hr`
  - `company2.test.hr`
  - `company3.test.hr`
- leave types and leave balances
- assets and assigned devices
- biometric device registry entries
- 30 days of raw attendance logs with late arrivals, overtime, and incomplete sessions
- monthly timesheet-ready attendance data
- ATS, OKR, dashboard, and tenant subscription demo records

## Deployment & Quick Start

Run the commands below from PowerShell on Windows.

### Step 1. Add local tenant domains

Run PowerShell as Administrator, then execute:

```powershell
@"
127.0.0.1 company1.test.hr
127.0.0.1 company2.test.hr
127.0.0.1 company3.test.hr
"@ | Add-Content $env:WINDIR\System32\drivers\etc\hosts
```

### Step 2. Boot the full stack

```powershell
cd C:\Users\User\hrms_georgia_enterprise\hrms_georgia_enterprise
docker compose up --build -d
```

### Step 3. Open the seeded system

```powershell
Start-Process "http://company1.test.hr:8000/ux/app"
```

Use these seeded credentials:

- Superadmin: `superadmin` / `ChangeMe123!`
- Employee ESS example: `emp001@company1.test.hr` / `Employee123!`

Optional endpoints:

- Swagger: `http://localhost:8000/docs`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

## Edge Middleware

Use the supplied edge stack when a device sits on a branch office LAN and should not be exposed directly over the public internet.

Start the branch middleware with:

```powershell
docker compose -f docker-compose.edge.yml up -d
```

Required environment variables for the edge host:

- `CENTRAL_DATABASE_URL`
- `CENTRAL_REDIS_URL`
- `JWT_SECRET`
- `EDGE_PUBLIC_BASE_URL`
- `NODE_CODE`
- `NODE_REGION`

`docker-compose.edge.yml` now runs the API directly and skips database initialization so branch nodes do not rerun schema and seed logic against the central database.

Detailed Dahua branch-office sync steps are in:

- `deployment/DAHUA_EDGE_SYNC.md`

## SMTP

Configure SMTP in `.env` next to `docker-compose.yml`, then rebuild the app:

```env
SMTP_HOST=mail.example.ge
SMTP_PORT=587
SMTP_USERNAME=hrms@example.ge
SMTP_PASSWORD=change-me
SMTP_FROM_EMAIL=hrms@example.ge
SMTP_USE_TLS=true
```

```powershell
docker compose up --build -d app
```

## Notes

- Tenant isolation is enforced from the request subdomain.
- Device registry supports tenant-specific assignment and superadmin cross-tenant visibility on the central host.
- Raw attendance logs remain immutable; HR corrections are stored as separate manual adjustment records.
- Timesheets can be exported from the payroll hub as `.xlsx` and `.pdf`.
