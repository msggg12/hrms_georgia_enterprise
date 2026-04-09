from __future__ import annotations

from .db import Database


async def ensure_runtime_schema(db: Database) -> None:
    statements = [
        """
        CREATE TABLE IF NOT EXISTS entity_system_config (
            legal_entity_id uuid PRIMARY KEY REFERENCES legal_entities(id) ON DELETE CASCADE,
            logo_url text,
            logo_text text,
            primary_color text NOT NULL DEFAULT '#1A2238',
            standalone_chat_url text,
            allowed_web_punch_ips text[] NOT NULL DEFAULT ARRAY[]::text[],
            geofence_latitude numeric(10,7),
            geofence_longitude numeric(10,7),
            geofence_radius_meters integer,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS tenant_subscriptions (
            legal_entity_id uuid PRIMARY KEY REFERENCES legal_entities(id) ON DELETE CASCADE,
            attendance_enabled boolean NOT NULL DEFAULT true,
            payroll_enabled boolean NOT NULL DEFAULT true,
            ats_enabled boolean NOT NULL DEFAULT true,
            chat_enabled boolean NOT NULL DEFAULT true,
            assets_enabled boolean NOT NULL DEFAULT true,
            org_chart_enabled boolean NOT NULL DEFAULT true,
            performance_enabled boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """,
        """
        INSERT INTO tenant_subscriptions (legal_entity_id)
        SELECT id
          FROM legal_entities
        ON CONFLICT (legal_entity_id) DO NOTHING
        """,
        """
        CREATE TABLE IF NOT EXISTS tenant_domains (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            legal_entity_id uuid NOT NULL REFERENCES legal_entities(id) ON DELETE CASCADE,
            host text NOT NULL UNIQUE,
            subdomain text,
            is_primary boolean NOT NULL DEFAULT false,
            is_active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_tenant_domains_entity
            ON tenant_domains (legal_entity_id, is_active, is_primary DESC)
        """,
        """
        ALTER TABLE employees
            ADD COLUMN IF NOT EXISTS line_manager_id uuid REFERENCES employees(id) ON DELETE SET NULL
        """,
        """
        UPDATE employees
           SET line_manager_id = manager_employee_id
         WHERE line_manager_id IS NULL
           AND manager_employee_id IS NOT NULL
        """,
        """
        ALTER TABLE shift_patterns
            ADD COLUMN IF NOT EXISTS grace_period_minutes integer NOT NULL DEFAULT 15
        """,
        """
        ALTER TABLE device_registry
            ADD COLUMN IF NOT EXISTS device_type text NOT NULL DEFAULT 'biometric_terminal'
        """,
        """
        ALTER TABLE job_postings
            ADD COLUMN IF NOT EXISTS public_slug text
        """,
        """
        ALTER TABLE job_postings
            ADD COLUMN IF NOT EXISTS application_form_schema jsonb NOT NULL DEFAULT '[]'::jsonb
        """,
        """
        ALTER TABLE job_postings
            ADD COLUMN IF NOT EXISTS external_form_url text
        """,
        """
        ALTER TABLE job_postings
            ADD COLUMN IF NOT EXISTS public_description text
        """,
        """
        ALTER TABLE job_postings
            ADD COLUMN IF NOT EXISTS is_public boolean NOT NULL DEFAULT true
        """,
        """
        ALTER TABLE candidate_applications
            ADD COLUMN IF NOT EXISTS application_payload jsonb NOT NULL DEFAULT '{}'::jsonb
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_job_postings_public_slug
            ON job_postings (public_slug)
            WHERE public_slug IS NOT NULL
        """,
        """
        CREATE TABLE IF NOT EXISTS web_punch_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            employee_id uuid NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
            legal_entity_id uuid NOT NULL REFERENCES legal_entities(id) ON DELETE CASCADE,
            direction attendance_direction NOT NULL DEFAULT 'unknown',
            punch_ts timestamptz NOT NULL DEFAULT now(),
            source_ip text,
            latitude numeric(10,7),
            longitude numeric(10,7),
            is_valid boolean NOT NULL DEFAULT false,
            validation_reason text,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_web_punch_events_employee_ts
            ON web_punch_events (employee_id, punch_ts DESC)
        """,
        """
        ALTER TABLE leave_requests
            ADD COLUMN IF NOT EXISTS attachment_url text
        """,
        """
        ALTER TABLE leave_requests
            ADD COLUMN IF NOT EXISTS approval_stage text NOT NULL DEFAULT 'manager_pending'
        """,
        """
        CREATE TABLE IF NOT EXISTS leave_request_files (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            leave_request_id uuid NOT NULL REFERENCES leave_requests(id) ON DELETE CASCADE,
            file_name text NOT NULL,
            file_url text NOT NULL,
            content_type text,
            file_size integer,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS auth_invites (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            employee_id uuid NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
            legal_entity_id uuid NOT NULL REFERENCES legal_entities(id) ON DELETE CASCADE,
            username citext NOT NULL,
            invite_token text NOT NULL UNIQUE,
            temp_password_hash text NOT NULL,
            recipient_email text,
            sent_via text NOT NULL DEFAULT 'email',
            expires_at timestamptz NOT NULL,
            accepted_at timestamptz,
            created_by_employee_id uuid REFERENCES employees(id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_auth_invites_employee
            ON auth_invites (employee_id, expires_at DESC)
        """,
        """
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            employee_id uuid NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
            identity_id uuid REFERENCES auth_identities(id) ON DELETE CASCADE,
            reset_token text NOT NULL UNIQUE,
            expires_at timestamptz NOT NULL,
            used_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS attendance_manual_adjustments (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            employee_id uuid NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
            legal_entity_id uuid NOT NULL REFERENCES legal_entities(id) ON DELETE CASCADE,
            session_id uuid REFERENCES attendance_work_sessions(id) ON DELETE SET NULL,
            work_date date NOT NULL,
            corrected_check_in timestamptz NOT NULL,
            corrected_check_out timestamptz,
            reason_comment text NOT NULL,
            created_by_employee_id uuid REFERENCES employees(id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_attendance_manual_adjustments_employee_work_date
            ON attendance_manual_adjustments (employee_id, work_date DESC)
        """,
        """
        CREATE TABLE IF NOT EXISTS employee_file_uploads (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            employee_id uuid NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
            legal_entity_id uuid NOT NULL REFERENCES legal_entities(id) ON DELETE CASCADE,
            file_category text NOT NULL,
            file_name text NOT NULL,
            file_url text NOT NULL,
            content_type text,
            file_size integer,
            created_by_employee_id uuid REFERENCES employees(id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS payroll_payment_records (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            timesheet_id uuid NOT NULL REFERENCES monthly_timesheets(id) ON DELETE CASCADE,
            employee_id uuid NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
            paid_at timestamptz NOT NULL,
            payment_method text NOT NULL,
            payment_reference text,
            note text,
            payslip_file_name text NOT NULL,
            payslip_pdf bytea NOT NULL,
            locked_by_employee_id uuid REFERENCES employees(id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (timesheet_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS asset_handover_forms (
            assignment_id uuid PRIMARY KEY REFERENCES asset_assignments(id) ON DELETE CASCADE,
            employee_signature_name text NOT NULL,
            handover_summary text NOT NULL,
            acknowledged_at timestamptz NOT NULL DEFAULT now(),
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """,
    ]
    for statement in statements:
        await db.execute(statement)
