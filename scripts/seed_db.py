"""
seed_db.py — Production-grade demo data seeder for HRMS Georgia Enterprise.

Populates:
  • 3 Legal Entities with system configs
  • 6 Departments per entity
  • 8 Job Roles per entity
  • 20+ Employees with line managers
  • Auth identities for all employees
  • Leave types + leave balances
  • 3 Shift patterns (already seeded by init_db, we assign them)
  • 30 days of raw attendance logs (with lates, OT, missing punches)
  • Attendance work sessions computed from logs
  • 3 Device registry entries (ZK, Dahua, Suprema)
  • Tenant domains (company1.test.hr, company2.test.hr, company3.test.hr)
  • Tenant subscriptions
  • ATS pipeline stages + 2 job postings + 3 candidates
  • OKR cycle + sample objectives
  • 5 Inventory items
  • Public holidays for 2025-2026
  • Entity operation settings + system config

Run: python scripts/seed_db.py
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import random
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

# Ensure app modules are importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncpg
from passlib.context import CryptContext

PWD_CTX = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://hrms:hrms@localhost:5432/hrms"
)
SEED_KEY = "enterprise_demo_v1"


async def ensure_seed_registry(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS demo_seed_runs (
            seed_key text PRIMARY KEY,
            status text NOT NULL,
            error text,
            started_at timestamptz NOT NULL DEFAULT now(),
            completed_at timestamptz
        )
        """
    )


async def run_seed_if_needed(conn: asyncpg.Connection) -> bool:
    await ensure_seed_registry(conn)
    status = await conn.fetchval(
        "SELECT status FROM demo_seed_runs WHERE seed_key = $1",
        SEED_KEY,
    )
    if status == "completed":
        print("[seed_db] Demo dataset already exists; skipping.")
        return False

    await conn.execute(
        """
        INSERT INTO demo_seed_runs (seed_key, status, error, started_at, completed_at)
        VALUES ($1, 'running', NULL, now(), NULL)
        ON CONFLICT (seed_key) DO UPDATE
           SET status = 'running',
               error = NULL,
               started_at = now(),
               completed_at = NULL
        """,
        SEED_KEY,
    )
    try:
        await seed(conn)
    except Exception as exc:
        await conn.execute(
            """
            UPDATE demo_seed_runs
               SET status = 'failed',
                   error = $2,
                   completed_at = now()
             WHERE seed_key = $1
            """,
            SEED_KEY,
            str(exc),
        )
        raise

    await conn.execute(
        """
        UPDATE demo_seed_runs
           SET status = 'completed',
               error = NULL,
               completed_at = now()
         WHERE seed_key = $1
        """,
        SEED_KEY,
    )
    return True

# ---------------------------------------------------------------------------
# Georgian names pool
# ---------------------------------------------------------------------------
FIRST_NAMES_M = [
    "გიორგი", "ნიკა", "ლუკა", "დავით", "ალექსანდრე",
    "ირაკლი", "ბექა", "თორნიკე", "ზურაბ", "ლევან",
    "გრიგოლ", "ვახტანგ", "ანდრია", "მიხეილ", "შოთა",
]
FIRST_NAMES_F = [
    "ნინო", "მარიამ", "ანა", "თამარ", "ეკატერინე",
    "ნათია", "სალომე", "ქეთევან", "ლიკა", "მაკა",
]
LAST_NAMES = [
    "ბერიძე", "კაპანაძე", "გელაშვილი", "ჯავახიშვილი", "წერეთელი",
    "მეგრელიშვილი", "ხარაიშვილი", "ნოზაძე", "ლომიძე", "ჩხეიძე",
    "გოგიჩაშვილი", "ბაქრაძე", "ხუციშვილი", "დარჩია", "ფხაკაძე",
    "ჩიქოვანი", "ტაბატაძე", "ქობალია", "ხვიჩია", "ბოჭორიშვილი",
]

DEPARTMENTS = [
    ("HR", "Human Resources", "ადამიანური რესურსები"),
    ("ENG", "Engineering", "ინჟინერია"),
    ("FIN", "Finance", "ფინანსები"),
    ("OPS", "Operations", "ოპერაციები"),
    ("SALES", "Sales", "გაყიდვები"),
    ("LEGAL", "Legal", "იურიდიული"),
]

JOB_ROLES = [
    ("CEO", "Chief Executive Officer", "გენერალური დირექტორი", True),
    ("CTO", "Chief Technology Officer", "ტექნოლოგიების დირექტორი", True),
    ("HR_DIR", "HR Director", "HR დირექტორი", True),
    ("FIN_DIR", "Finance Director", "ფინანსური დირექტორი", True),
    ("SR_ENG", "Senior Engineer", "უფროსი ინჟინერი", False),
    ("JR_ENG", "Junior Engineer", "უმცროსი ინჟინერი", False),
    ("ACCOUNTANT", "Accountant", "ბუღალტერი", False),
    ("SALES_REP", "Sales Representative", "გაყიდვების წარმომადგენელი", False),
]

ENTITIES = [
    {
        "legal_name": "Georgia Enterprise Holding LLC",
        "trade_name": "Georgia Enterprise",
        "tax_id": "GE-000000001",
        "subdomain": "company1",
        "host": "company1.test.hr",
    },
    {
        "legal_name": "TechFlow Solutions LLC",
        "trade_name": "TechFlow",
        "tax_id": "GE-000000002",
        "subdomain": "company2",
        "host": "company2.test.hr",
    },
    {
        "legal_name": "Meridian Logistics LLC",
        "trade_name": "Meridian Logistics",
        "tax_id": "GE-000000003",
        "subdomain": "company3",
        "host": "company3.test.hr",
    },
]

LEAVE_TYPES = [
    ("ANNUAL", "Annual Leave", "ყოველწლიური შვებულება", 24, True),
    ("SICK", "Sick Leave", "ბიულეტინი", 40, True),
    ("MATERNITY", "Maternity Leave", "დეკრეტული შვებულება", 183, True),
    ("UNPAID", "Unpaid Leave", "აუნაზღაურებელი შვებულება", 0, True),
]

ATS_STAGES = [
    ("APPLIED", "Applied", "განაცხადი", 1, False, False, False),
    ("SCREENING", "Screening", "სკრინინგი", 2, False, False, False),
    ("INTERVIEW", "Interview", "გასაუბრება", 3, False, False, False),
    ("OFFER", "Offer", "შეთავაზება", 4, False, False, False),
    ("HIRED", "Hired", "აყვანილი", 5, True, True, False),
    ("REJECTED", "Rejected", "უარყოფილი", 6, True, False, True),
]

ASSET_CATEGORIES = [
    ("LAPTOP", "Laptop", "ლეპტოპი"),
    ("MONITOR", "Monitor", "მონიტორი"),
    ("PHONE", "Phone", "ტელეფონი"),
    ("FURNITURE", "Furniture", "ავეჯი"),
    ("VEHICLE", "Vehicle", "ავტომობილი"),
]


def _personal_number() -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(11))


def _phone() -> str:
    return f"+995 5{random.randint(10, 99)} {random.randint(100, 999)} {random.randint(100, 999)}"


def _hash(password: str) -> str:
    return PWD_CTX.hash(password)


async def seed(conn: asyncpg.Connection) -> None:
    print("🌱 Starting HRMS seed...")

    # ── 1. Legal Entities ──────────────────────────────────────────────
    entity_ids: dict[str, UUID] = {}
    for ent in ENTITIES:
        eid = await conn.fetchval(
            """
            INSERT INTO legal_entities (legal_name, trade_name, tax_id)
            VALUES ($1, $2, $3)
            ON CONFLICT (tax_id) DO UPDATE SET trade_name = EXCLUDED.trade_name
            RETURNING id
            """,
            ent["legal_name"],
            ent["trade_name"],
            ent["tax_id"],
        )
        entity_ids[ent["tax_id"]] = eid
        print(f"  ✓ Entity: {ent['trade_name']} ({eid})")

    primary_entity_id = entity_ids["GE-000000001"]

    # ── 2. Departments ─────────────────────────────────────────────────
    dept_ids: dict[str, dict[str, UUID]] = {}
    for tax_id, eid in entity_ids.items():
        dept_ids[tax_id] = {}
        for code, name_en, name_ka in DEPARTMENTS:
            did = await conn.fetchval(
                """
                INSERT INTO departments (legal_entity_id, code, name_en, name_ka)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (legal_entity_id, code) DO UPDATE SET name_en = EXCLUDED.name_en
                RETURNING id
                """,
                eid, code, name_en, name_ka,
            )
            dept_ids[tax_id][code] = did
    print(f"  ✓ Departments: {len(DEPARTMENTS)} × {len(ENTITIES)} entities")

    # ── 3. Job Roles ───────────────────────────────────────────────────
    role_ids: dict[str, dict[str, UUID]] = {}
    for tax_id, eid in entity_ids.items():
        role_ids[tax_id] = {}
        for code, title_en, title_ka, is_mgr in JOB_ROLES:
            rid = await conn.fetchval(
                """
                INSERT INTO job_roles (legal_entity_id, code, title_en, title_ka, is_managerial)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (legal_entity_id, code) DO UPDATE SET title_en = EXCLUDED.title_en
                RETURNING id
                """,
                eid, code, title_en, title_ka, is_mgr,
            )
            role_ids[tax_id][code] = rid
    print(f"  ✓ Job Roles: {len(JOB_ROLES)} × {len(ENTITIES)} entities")

    # ── 4. Pay Policies ────────────────────────────────────────────────
    policy_ids: dict[str, UUID] = {}
    for tax_id, eid in entity_ids.items():
        pid = await conn.fetchval(
            """
            INSERT INTO pay_policies (
                legal_entity_id, code, name, standard_weekly_hours,
                overtime_multiplier, night_bonus_multiplier, holiday_multiplier,
                employee_pension_rate, income_tax_rate
            ) VALUES ($1, 'STANDARD', 'Standard Policy', 40.00, 1.25, 0.15, 2.00, 0.02, 0.20)
            ON CONFLICT (legal_entity_id, code) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
            """,
            eid,
        )
        policy_ids[tax_id] = pid
    print(f"  ✓ Pay Policies: {len(policy_ids)}")

    # ── 5. Employees ───────────────────────────────────────────────────
    all_employees: list[dict] = []
    employee_ids_by_entity: dict[str, list[UUID]] = {t: [] for t in entity_ids}

    # Employee definitions per entity
    employee_templates = [
        # (emp_num, first, last, dept_code, role_code, salary, is_manager)
        ("EMP-001", "გიორგი", "ბერიძე", "HR", "CEO", 12000, True),
        ("EMP-002", "ნინო", "კაპანაძე", "HR", "HR_DIR", 8000, True),
        ("EMP-003", "დავით", "გელაშვილი", "ENG", "CTO", 10000, True),
        ("EMP-004", "მარიამ", "ჯავახიშვილი", "FIN", "FIN_DIR", 8500, True),
        ("EMP-005", "ირაკლი", "წერეთელი", "ENG", "SR_ENG", 6000, False),
        ("EMP-006", "ანა", "მეგრელიშვილი", "ENG", "SR_ENG", 5800, False),
        ("EMP-007", "ბექა", "ხარაიშვილი", "ENG", "JR_ENG", 3500, False),
        ("EMP-008", "თამარ", "ნოზაძე", "ENG", "JR_ENG", 3200, False),
        ("EMP-009", "ლუკა", "ლომიძე", "FIN", "ACCOUNTANT", 4500, False),
        ("EMP-010", "ეკატერინე", "ჩხეიძე", "FIN", "ACCOUNTANT", 4200, False),
        ("EMP-011", "ნიკა", "გოგიჩაშვილი", "SALES", "SALES_REP", 3800, False),
        ("EMP-012", "სალომე", "ბაქრაძე", "SALES", "SALES_REP", 3600, False),
        ("EMP-013", "თორნიკე", "ხუციშვილი", "OPS", "SR_ENG", 5500, False),
        ("EMP-014", "ქეთევან", "დარჩია", "OPS", "JR_ENG", 3400, False),
        ("EMP-015", "ზურაბ", "ფხაკაძე", "LEGAL", "SR_ENG", 5000, False),
        ("EMP-016", "ლიკა", "ჩიქოვანი", "LEGAL", "ACCOUNTANT", 4000, False),
        ("EMP-017", "ვახტანგ", "ტაბატაძე", "ENG", "SR_ENG", 6200, False),
        ("EMP-018", "მაკა", "ქობალია", "HR", "ACCOUNTANT", 4100, False),
        ("EMP-019", "ალექსანდრე", "ხვიჩია", "SALES", "SALES_REP", 3700, False),
        ("EMP-020", "ნათია", "ბოჭორიშვილი", "OPS", "JR_ENG", 3300, False),
        ("EMP-021", "გრიგოლ", "ბერიძე", "ENG", "JR_ENG", 3100, False),
        ("EMP-022", "ანდრია", "კაპანაძე", "FIN", "ACCOUNTANT", 4300, False),
    ]

    # Manager mapping: dept_code -> emp_num of manager
    manager_map = {
        "HR": "EMP-001",
        "ENG": "EMP-003",
        "FIN": "EMP-004",
        "OPS": "EMP-001",
        "SALES": "EMP-001",
        "LEGAL": "EMP-001",
    }

    for tax_id, eid in entity_ids.items():
        emp_id_map: dict[str, UUID] = {}
        for emp_num, first, last, dept_code, role_code, salary, is_mgr in employee_templates:
            pn = _personal_number()
            email = f"{emp_num.lower().replace('-', '')}@{ENTITIES[[e['tax_id'] for e in ENTITIES].index(tax_id)]['subdomain']}.test.hr"
            hire_date = date(2023, random.randint(1, 12), random.randint(1, 28))

            emp_id = await conn.fetchval(
                """
                INSERT INTO employees (
                    legal_entity_id, employee_number, personal_number,
                    first_name, last_name, email, mobile_phone,
                    department_id, job_role_id, hire_date,
                    employment_status, default_device_user_id
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'active', $2)
                ON CONFLICT (legal_entity_id, employee_number)
                DO UPDATE SET first_name = EXCLUDED.first_name
                RETURNING id
                """,
                eid, emp_num, pn, first, last, email, _phone(),
                dept_ids[tax_id][dept_code],
                role_ids[tax_id][role_code],
                hire_date,
            )
            emp_id_map[emp_num] = emp_id
            employee_ids_by_entity[tax_id].append(emp_id)
            all_employees.append({
                "id": emp_id, "entity_id": eid, "tax_id": tax_id,
                "emp_num": emp_num, "first": first, "last": last,
                "dept_code": dept_code, "salary": salary,
                "hire_date": hire_date, "email": email,
            })

            # Compensation
            await conn.execute(
                """
                INSERT INTO employee_compensation (
                    employee_id, policy_id, effective_from, base_salary,
                    hourly_rate_override, is_pension_participant
                ) VALUES ($1, $2, $3, $4, NULL, true)
                ON CONFLICT DO NOTHING
                """,
                emp_id, policy_ids[tax_id], hire_date, Decimal(str(salary)),
            )

        # Set line managers
        for emp_num, first, last, dept_code, role_code, salary, is_mgr in employee_templates:
            if not is_mgr and dept_code in manager_map:
                mgr_num = manager_map[dept_code]
                if mgr_num in emp_id_map:
                    await conn.execute(
                        """
                        UPDATE employees
                        SET manager_employee_id = $2, line_manager_id = $2
                        WHERE id = $1
                        """,
                        emp_id_map[emp_num], emp_id_map[mgr_num],
                    )

        # Set department managers
        for dept_code, mgr_num in manager_map.items():
            if mgr_num in emp_id_map:
                await conn.execute(
                    "UPDATE departments SET manager_employee_id = $2 WHERE id = $1",
                    dept_ids[tax_id][dept_code], emp_id_map[mgr_num],
                )

    print(f"  ✓ Employees: {len(all_employees)} total")

    # ── 6. Auth Identities ─────────────────────────────────────────────
    default_password_hash = _hash("Employee123!")
    for emp in all_employees:
        username = emp["email"]
        await conn.execute(
            """
            INSERT INTO auth_identities (employee_id, username, password_hash, is_active)
            VALUES ($1, $2, $3, true)
            ON CONFLICT (username) DO UPDATE SET password_hash = EXCLUDED.password_hash
            """,
            emp["id"], username, default_password_hash,
        )

    # Ensure superadmin identity exists and stays aligned with init_db.py
    superadmin_username = os.environ.get("SUPERADMIN_USERNAME", "superadmin").strip() or "superadmin"
    superadmin_password = os.environ.get("SUPERADMIN_PASSWORD", "ChangeMe123!")
    superadmin_emp = await conn.fetchval(
        """
        SELECT e.id
          FROM employees e
          LEFT JOIN auth_identities ai ON ai.employee_id = e.id
         WHERE ai.username = $1
            OR e.employee_number IN ('ADM-0001', 'SUPER-001')
         ORDER BY CASE WHEN ai.username = $1 THEN 0 ELSE 1 END, e.created_at
         LIMIT 1
        """,
        superadmin_username,
    )
    if superadmin_emp:
        await conn.execute(
            """
            INSERT INTO auth_identities (employee_id, username, password_hash, is_active)
            VALUES ($1, $2, $3, true)
            ON CONFLICT (username) DO UPDATE
               SET employee_id = EXCLUDED.employee_id,
                   password_hash = EXCLUDED.password_hash,
                   is_active = true
            """,
            superadmin_emp, superadmin_username, _hash(superadmin_password),
        )

    # Grant ADMIN + HR roles to EMP-001 and EMP-002 in primary entity
    admin_role_id = await conn.fetchval("SELECT id FROM access_roles WHERE code = 'ADMIN'")
    hr_role_id = await conn.fetchval("SELECT id FROM access_roles WHERE code = 'HR'")
    employee_role_id = await conn.fetchval("SELECT id FROM access_roles WHERE code = 'EMPLOYEE'")
    manager_role_id = await conn.fetchval("SELECT id FROM access_roles WHERE code = 'MANAGER'")

    for emp in all_employees:
        role_id = employee_role_id
        if emp["emp_num"] == "EMP-001":
            role_id = admin_role_id
        elif emp["emp_num"] == "EMP-002":
            role_id = hr_role_id
        elif emp["emp_num"] in ("EMP-003", "EMP-004"):
            role_id = manager_role_id

        if role_id:
            await conn.execute(
                """
                INSERT INTO employee_access_roles (employee_id, access_role_id)
                VALUES ($1, $2)
                ON CONFLICT DO NOTHING
                """,
                emp["id"], role_id,
            )
            # Also give EMPLOYEE role to managers/admins
            if role_id != employee_role_id and employee_role_id:
                await conn.execute(
                    """
                    INSERT INTO employee_access_roles (employee_id, access_role_id)
                    VALUES ($1, $2)
                    ON CONFLICT DO NOTHING
                    """,
                    emp["id"], employee_role_id,
                )

    print(f"  ✓ Auth identities & roles assigned")

    # ── 7. Leave Types & Balances (columns aligned with sql/002_enterprise_extensions.sql + init_db) ──
    balance_year = 2026
    for tax_id, eid in entity_ids.items():
        for code, name_en, name_ka, default_days, is_active in LEAVE_TYPES:
            carryover = min(Decimal('10'), Decimal(str(default_days))) if default_days > 0 else Decimal('0')
            lt_id = await conn.fetchval(
                """
                INSERT INTO leave_types (
                    legal_entity_id, code, name_en, name_ka, is_paid,
                    annual_allowance_days, carryover_limit_days, is_active
                ) VALUES ($1, $2, $3, $4, true, $5, $6, $7)
                ON CONFLICT (legal_entity_id, code) DO UPDATE SET
                    name_en = EXCLUDED.name_en,
                    name_ka = EXCLUDED.name_ka,
                    annual_allowance_days = EXCLUDED.annual_allowance_days,
                    carryover_limit_days = EXCLUDED.carryover_limit_days,
                    is_active = EXCLUDED.is_active,
                    updated_at = now()
                RETURNING id
                """,
                eid,
                code,
                name_en,
                name_ka,
                Decimal(str(default_days)),
                carryover,
                is_active,
            )
            for emp_id in employee_ids_by_entity[tax_id]:
                used = random.randint(0, min(5, default_days)) if default_days > 0 else 0
                opening = Decimal(str(max(default_days - used, 0)))
                await conn.execute(
                    """
                    INSERT INTO leave_balances (
                        employee_id, leave_type_id, balance_year,
                        opening_days, earned_days, used_days, adjusted_days
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT DO NOTHING
                    """,
                    emp_id,
                    lt_id,
                    balance_year,
                    opening,
                    Decimal('0'),
                    Decimal(str(used)),
                    Decimal('0'),
                )
    print(f"  ✓ Leave types & balances")

    # ── 8. Tenant Domains ──────────────────────────────────────────────
    for ent in ENTITIES:
        eid = entity_ids[ent["tax_id"]]
        await conn.execute(
            """
            INSERT INTO tenant_domains (legal_entity_id, host, subdomain, is_primary, is_active)
            VALUES ($1, $2, $3, true, true)
            ON CONFLICT DO NOTHING
            """,
            eid, ent["host"], ent["subdomain"],
        )
    print(f"  ✓ Tenant domains: {len(ENTITIES)}")

    # ── 9. Tenant Subscriptions ────────────────────────────────────────
    for tax_id, eid in entity_ids.items():
        await conn.execute(
            """
            INSERT INTO tenant_subscriptions (
                legal_entity_id, attendance_enabled, payroll_enabled,
                ats_enabled, chat_enabled, assets_enabled,
                org_chart_enabled, performance_enabled
            ) VALUES ($1, true, true, true, true, true, true, true)
            ON CONFLICT (legal_entity_id) DO NOTHING
            """,
            eid,
        )
    print(f"  ✓ Tenant subscriptions")

    # ── 10. Entity System Config ───────────────────────────────────────
    for tax_id, eid in entity_ids.items():
        await conn.execute(
            """
            INSERT INTO entity_system_config (
                legal_entity_id, logo_text, primary_color,
                geofence_latitude, geofence_longitude, geofence_radius_meters,
                allowed_web_punch_ips
            ) VALUES ($1, $2, '#1E293B', 41.7151, 44.8271, 500, ARRAY['0.0.0.0/0']::text[])
            ON CONFLICT (legal_entity_id) DO UPDATE
            SET logo_text = EXCLUDED.logo_text, primary_color = EXCLUDED.primary_color
            """,
            eid,
            ENTITIES[[e["tax_id"] for e in ENTITIES].index(tax_id)]["trade_name"],
        )
        await conn.execute(
            """
            INSERT INTO entity_operation_settings (
                legal_entity_id, late_arrival_threshold_minutes,
                require_asset_clearance_for_final_payroll
            ) VALUES ($1, 15, true)
            ON CONFLICT (legal_entity_id) DO NOTHING
            """,
            eid,
        )
    print(f"  ✓ Entity system configs")

    # ── 11. Shift Patterns (use existing ones seeded by init_db) ───────
    # Seed standard shift patterns for all entities
    for tax_id, eid in entity_ids.items():
        await conn.execute("SELECT hrms.seed_standard_shift_patterns($1)", eid)
    print(f"  ✓ Shift patterns seeded for all entities")

    # Assign shifts to employees
    for tax_id, eid in entity_ids.items():
        fixed_pattern_id = await conn.fetchval(
            "SELECT id FROM shift_patterns WHERE legal_entity_id = $1 AND code = 'FIXED_9_6'",
            eid,
        )
        if fixed_pattern_id:
            for emp_id in employee_ids_by_entity[tax_id]:
                await conn.execute(
                    """
                    INSERT INTO assigned_shifts (
                        shift_pattern_id, employee_id, effective_from
                    ) VALUES ($1, $2, '2024-01-01')
                    ON CONFLICT DO NOTHING
                    """,
                    fixed_pattern_id, emp_id,
                )
    print(f"  ✓ Shift assignments")

    # ── 12. Device Registry ────────────────────────────────────────────
    devices = [
        ("zk", "adms", "biometric_terminal", "ZK Main Entrance", "SpeedFace V5L", "ZK-SN-001", "192.168.1.201", 4370),
        ("dahua", "http_cgi", "access_control_gate", "Dahua Parking Gate", "ASI7213Y-V3", "DH-SN-002", "192.168.1.202", 80),
        ("suprema", "biostar", "rfid_card_reader", "Suprema RFID Reader", "BioEntry W2", "SUP-SN-003", "192.168.1.203", 443),
    ]
    for brand, transport, dtype, dname, model, serial, host, port in devices:
        await conn.execute(
            """
            INSERT INTO device_registry (
                legal_entity_id, brand, transport, device_type,
                device_name, model, serial_number, host, port,
                device_timezone, is_active, poll_interval_seconds, metadata
            ) VALUES ($1, $2::device_brand, $3::device_transport, $4, $5, $6, $7, $8, $9, 'Asia/Tbilisi', true, 60, '{}'::jsonb)
            ON CONFLICT DO NOTHING
            """,
            primary_entity_id, brand, transport, dtype, dname, model, serial, host, port,
        )
    print(f"  ✓ Device registry: {len(devices)} devices")

    # ── 13. Raw Attendance Logs (30 days) ──────────────────────────────
    today = date.today()
    start_date = today - timedelta(days=30)
    log_count = 0

    for emp in all_employees:
        if emp["tax_id"] != "GE-000000001":
            continue  # Only seed attendance for primary entity

        device_id = await conn.fetchval(
            "SELECT id FROM device_registry WHERE legal_entity_id = $1 LIMIT 1",
            emp["entity_id"],
        )

        current = start_date
        while current <= today:
            weekday = current.isoweekday()
            if weekday > 5:  # Skip weekends
                current += timedelta(days=1)
                continue

            # Simulate realistic check-in times (some late, some early)
            base_hour = 9
            base_minute = 0
            variation = random.randint(-15, 30)  # -15 to +30 minutes
            check_in_minute = base_minute + variation
            check_in_hour = base_hour
            if check_in_minute < 0:
                check_in_hour -= 1
                check_in_minute += 60
            elif check_in_minute >= 60:
                check_in_hour += 1
                check_in_minute -= 60

            check_in_ts = datetime(
                current.year, current.month, current.day,
                check_in_hour, check_in_minute, random.randint(0, 59),
            )

            # Check-out: 17:30-19:30 (some OT)
            checkout_hour = random.choice([17, 17, 18, 18, 18, 19])
            checkout_minute = random.randint(0, 59)
            check_out_ts = datetime(
                current.year, current.month, current.day,
                checkout_hour, checkout_minute, random.randint(0, 59),
            )

            # 5% chance of missing check-out
            has_checkout = random.random() > 0.05

            # Insert IN log
            await conn.execute(
                """
                INSERT INTO raw_attendance_logs (
                    employee_id, device_id, device_user_id,
                    event_ts, direction, verify_mode
                ) VALUES ($1, $2, $3, $4, 'in'::attendance_direction, 'fingerprint')
                """,
                emp["id"], device_id, emp["emp_num"], check_in_ts,
            )
            log_count += 1

            if has_checkout:
                await conn.execute(
                    """
                    INSERT INTO raw_attendance_logs (
                        employee_id, device_id, device_user_id,
                        event_ts, direction, verify_mode
                    ) VALUES ($1, $2, $3, $4, 'out'::attendance_direction, 'fingerprint')
                    """,
                    emp["id"], device_id, emp["emp_num"], check_out_ts,
                )
                log_count += 1

                # Create work session
                total_minutes = int((check_out_ts - check_in_ts).total_seconds() / 60)
                overtime = max(0, total_minutes - 540)  # 9 hours = 540 min
                night_min = 0
                if checkout_hour >= 22 or check_in_hour < 6:
                    night_min = random.randint(0, 60)

                is_late = check_in_ts.hour > 9 or (check_in_ts.hour == 9 and check_in_ts.minute > 15)
                review_status = "flagged" if is_late else "approved"

                session_id = await conn.fetchval(
                    """
                    INSERT INTO attendance_work_sessions (
                        employee_id, work_date, check_in_ts, check_out_ts,
                        total_minutes, night_minutes, overtime_minutes,
                        review_status, manager_review_required
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8::review_status, $9)
                    RETURNING id
                    """,
                    emp["id"], current, check_in_ts, check_out_ts,
                    total_minutes, night_min, overtime,
                    review_status, is_late,
                )

                # Create review flags for late arrivals
                if is_late:
                    await conn.execute(
                        """
                        INSERT INTO attendance_review_flags (
                            employee_id, session_id, work_date,
                            flag_type, severity, details
                        ) VALUES ($1, $2, $3, 'late_arrival', 'medium', $4)
                        """,
                        emp["id"], session_id, current,
                        f"დაგვიანება: შემოსვლა {check_in_ts.strftime('%H:%M')}, გეგმიური 09:00",
                    )
            else:
                # Missing checkout session
                await conn.fetchval(
                    """
                    INSERT INTO attendance_work_sessions (
                        employee_id, work_date, check_in_ts,
                        total_minutes, review_status, incomplete_reason,
                        manager_review_required
                    ) VALUES ($1, $2, $3, 0, 'open'::review_status, 'missing_check_out', true)
                    RETURNING id
                    """,
                    emp["id"], current, check_in_ts,
                )

            current += timedelta(days=1)

    print(f"  ✓ Attendance logs: {log_count} raw logs")

    # ── 14. ATS Pipeline ───────────────────────────────────────────────
    for tax_id, eid in entity_ids.items():
        for code, name_en, name_ka, sort, is_term, is_hired, is_rej in ATS_STAGES:
            await conn.execute(
                """
                INSERT INTO candidate_pipeline_stages (
                    legal_entity_id, code, name_en, name_ka,
                    sort_order, is_terminal, is_hired, is_rejected
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (legal_entity_id, code) DO NOTHING
                """,
                eid, code, name_en, name_ka, sort, is_term, is_hired, is_rej,
            )

    # Job postings for primary entity
    creator_id = all_employees[0]["id"]  # CEO
    for posting in [
        ("VP-2026-001", "Senior Python Developer", "უფროსი Python დეველოპერი", "full_time", 5000, 8000),
        ("VP-2026-002", "HR Specialist", "HR სპეციალისტი", "full_time", 3000, 4500),
    ]:
        code, title_en, title_ka, emp_type, sal_min, sal_max = posting
        jp_id = await conn.fetchval(
            """
            INSERT INTO job_postings (
                legal_entity_id, posting_code, title_en, title_ka,
                description, employment_type, status, open_positions,
                salary_min, salary_max, created_by_employee_id,
                published_at, public_slug, public_description, is_public
            ) VALUES ($1, $2, $3, $4, $5, $6, 'published', 2, $7, $8, $9, now(), $10, $5, true)
            ON CONFLICT (legal_entity_id, posting_code) DO NOTHING
            RETURNING id
            """,
            primary_entity_id, code, title_en, title_ka,
            f"We are looking for a {title_en} to join our team.",
            emp_type, Decimal(str(sal_min)), Decimal(str(sal_max)),
            creator_id, f"{title_en.lower().replace(' ', '-')}-{code.lower()}",
        )

    # Sample candidates
    applied_stage = await conn.fetchval(
        "SELECT id FROM candidate_pipeline_stages WHERE legal_entity_id = $1 AND code = 'APPLIED'",
        primary_entity_id,
    )
    first_posting = await conn.fetchval(
        "SELECT id FROM job_postings WHERE legal_entity_id = $1 LIMIT 1",
        primary_entity_id,
    )
    if applied_stage and first_posting:
        candidates_data = [
            ("ლაშა", "მამულაშვილი", "lasha@example.ge", "career_page"),
            ("ნანა", "ხარატიშვილი", "nana@example.ge", "linkedin"),
            ("გიგა", "ცინცაძე", "giga@example.ge", "referral"),
        ]
        for first, last, email, source in candidates_data:
            cand_id = await conn.fetchval(
                """
                INSERT INTO candidates (
                    legal_entity_id, first_name, last_name, email, source
                ) VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT DO NOTHING
                RETURNING id
                """,
                primary_entity_id, first, last, email, source,
            )
            if cand_id:
                app_id = await conn.fetchval(
                    """
                    INSERT INTO candidate_applications (
                        candidate_id, job_posting_id, current_stage_id
                    ) VALUES ($1, $2, $3)
                    ON CONFLICT DO NOTHING
                    RETURNING id
                    """,
                    cand_id, first_posting, applied_stage,
                )
                if app_id:
                    await conn.execute(
                        """
                        INSERT INTO candidate_pipeline (application_id, stage_id, comment)
                        VALUES ($1, $2, 'Application received')
                        """,
                        app_id, applied_stage,
                    )
    print(f"  ✓ ATS pipeline, postings, candidates")

    # ── 15. Asset Categories & Inventory ───────────────────────────────
    for tax_id, eid in entity_ids.items():
        for code, name_en, name_ka in ASSET_CATEGORIES:
            await conn.execute(
                """
                INSERT INTO asset_categories (legal_entity_id, code, name_en, name_ka)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (legal_entity_id, code) DO NOTHING
                """,
                eid, code, name_en, name_ka,
            )

    # Inventory items for primary entity
    laptop_cat = await conn.fetchval(
        "SELECT id FROM asset_categories WHERE legal_entity_id = $1 AND code = 'LAPTOP'",
        primary_entity_id,
    )
    monitor_cat = await conn.fetchval(
        "SELECT id FROM asset_categories WHERE legal_entity_id = $1 AND code = 'MONITOR'",
        primary_entity_id,
    )
    phone_cat = await conn.fetchval(
        "SELECT id FROM asset_categories WHERE legal_entity_id = $1 AND code = 'PHONE'",
        primary_entity_id,
    )

    inventory_items = [
        (laptop_cat, "ASSET-001", "MacBook Pro 16\"", "Apple", "MacBook Pro", "C02X12345", "good", "in_stock", 5500),
        (laptop_cat, "ASSET-002", "ThinkPad X1 Carbon", "Lenovo", "X1 Carbon Gen 11", "PF3ABCDE", "good", "assigned", 3200),
        (monitor_cat, "ASSET-003", "Dell UltraSharp 27\"", "Dell", "U2723QE", "CN-0ABC123", "new", "in_stock", 1200),
        (phone_cat, "ASSET-004", "iPhone 15 Pro", "Apple", "iPhone 15 Pro", "F2LXK1234", "good", "assigned", 2800),
        (laptop_cat, "ASSET-005", "Dell Latitude 5540", "Dell", "Latitude 5540", "SVC-TAG-005", "good", "in_stock", 2400),
    ]
    for cat_id, tag, name, brand, model, serial, condition, status, cost in inventory_items:
        await conn.execute(
            """
            INSERT INTO inventory_items (
                legal_entity_id, category_id, asset_tag, asset_name,
                brand, model, serial_number, current_condition,
                current_status, purchase_cost, currency_code
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8::asset_condition, $9::asset_status, $10, 'GEL')
            ON CONFLICT DO NOTHING
            """,
            primary_entity_id, cat_id, tag, name, brand, model, serial,
            condition, status, Decimal(str(cost)),
        )
    print(f"  ✓ Asset categories & inventory items")

    # ── 16. OKR Cycle ──────────────────────────────────────────────────
    for tax_id, eid in entity_ids.items():
        cycle_id = await conn.fetchval(
            """
            INSERT INTO okr_cycles (
                legal_entity_id, name, start_date, end_date, status
            ) VALUES ($1, 'Q2 2026', '2026-04-01', '2026-06-30', 'active')
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            eid,
        )
        if cycle_id and employee_ids_by_entity[tax_id]:
            owner = employee_ids_by_entity[tax_id][0]
            obj_id = await conn.fetchval(
                """
                INSERT INTO okr_objectives (
                    cycle_id, legal_entity_id, scope, title,
                    description, owner_employee_id, weight
                ) VALUES ($1, $2, 'company', 'Increase Revenue by 20%',
                    'Drive company-wide revenue growth', $3, 100)
                ON CONFLICT DO NOTHING
                RETURNING id
                """,
                cycle_id, eid, owner,
            )
            if obj_id:
                await conn.execute(
                    """
                    INSERT INTO okr_key_results (
                        objective_id, title, metric_unit,
                        start_value, target_value, current_value
                    ) VALUES ($1, 'Monthly recurring revenue', 'GEL', 0, 500000, 125000)
                    ON CONFLICT DO NOTHING
                    """,
                    obj_id,
                )
    print(f"  ✓ OKR cycles & objectives")

    # ── 17. Public Holidays ────────────────────────────────────────────
    from app.labor_engine import georgian_public_holidays
    for year in (2025, 2026):
        holidays = georgian_public_holidays(year)
        for hdate, payload in holidays.items():
            await conn.execute(
                """
                INSERT INTO public_holidays_ge (holiday_date, holiday_code, name_en, name_ka, is_movable)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (holiday_date) DO NOTHING
                """,
                hdate, payload["holiday_code"], payload["name_en"], payload["name_ka"], payload["is_movable"],
            )
    print(f"  ✓ Public holidays 2025-2026")

    # ── 18. Dashboard Widget Catalog ───────────────────────────────────
    widgets = [
        ("headcount", "Headcount", "თანამშრომლების რაოდენობა", "metric"),
        ("attendance_today", "Today's Attendance", "დღევანდელი დასწრება", "metric"),
        ("open_flags", "Open Flags", "ღია ფლაგები", "metric"),
        ("pending_leaves", "Pending Leaves", "მოლოდინში შვებულებები", "metric"),
        ("devices_online", "Devices Online", "ონლაინ მოწყობილობები", "metric"),
        ("live_feed", "Live Feed", "პირდაპირი არხი", "feed"),
    ]
    for code, name_en, name_ka, wtype in widgets:
        await conn.execute(
            """
            INSERT INTO dashboard_widget_catalog (code, name_en, name_ka, widget_type, is_default)
            VALUES ($1, $2, $3, $4, true)
            ON CONFLICT DO NOTHING
            """,
            code, name_en, name_ka, wtype,
        )
    print(f"  ✓ Dashboard widget catalog")

    # ── 19. Mattermost Integration (placeholder) ──────────────────────
    for tax_id, eid in entity_ids.items():
        await conn.execute(
            """
            INSERT INTO mattermost_integrations (legal_entity_id, enabled)
            VALUES ($1, false)
            ON CONFLICT (legal_entity_id) DO NOTHING
            """,
            eid,
        )
    print(f"  ✓ Mattermost integration placeholders")

    # ── 20. Onboarding Course (placeholder) ────────────────────────────
    for tax_id, eid in entity_ids.items():
        await conn.execute(
            """
            INSERT INTO onboarding_courses (legal_entity_id, code, title_en, title_ka, is_active)
            VALUES ($1, 'ONBOARD_DEFAULT', 'Default Onboarding', 'სტანდარტული ონბორდინგი', true)
            ON CONFLICT DO NOTHING
            """,
            eid,
        )

    # ── 21. Hiring Checklist Template ──────────────────────────────────
    for tax_id, eid in entity_ids.items():
        tmpl_id = await conn.fetchval(
            """
            INSERT INTO hiring_checklist_templates (legal_entity_id, code, name_en, name_ka)
            VALUES ($1, 'DEFAULT', 'Default Checklist', 'სტანდარტული ჩეკლისტი')
            ON CONFLICT (legal_entity_id, code) DO NOTHING
            RETURNING id
            """,
            eid,
        )
        if tmpl_id:
            items = [
                (1, "ID_COPY", "ID Copy", "პირადობის ასლი"),
                (2, "CONTRACT", "Employment Contract", "შრომითი ხელშეკრულება"),
                (3, "BANK_DETAILS", "Bank Details", "საბანკო რეკვიზიტები"),
                (4, "PHOTO", "Photo", "ფოტოსურათი"),
            ]
            for sort, code, label_en, label_ka in items:
                await conn.execute(
                    """
                    INSERT INTO hiring_checklist_items (template_id, sort_order, item_code, label_en, label_ka)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (template_id, item_code) DO NOTHING
                    """,
                    tmpl_id, sort, code, label_en, label_ka,
                )
    print(f"  ✓ Hiring checklist templates")

    print("\n🎉 Seed complete! Dashboard should now be fully populated.")
    print(f"   Login: superadmin / ChangeMe123!")
    print(f"   Or any employee: emp001@company1.test.hr / Employee123!")


async def main() -> None:
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute("SET search_path TO hrms, public")
        await run_seed_if_needed(conn)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
