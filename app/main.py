from __future__ import annotations

import asyncio
import base64
import csv
import io
import ipaddress
import json
import math
import re
import secrets
import string
import zipfile
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

try:  # pragma: no cover - exception classes available at runtime
    from asyncpg import PostgresError, UniqueViolationError
except ImportError:  # pragma: no cover - local tooling may not have asyncpg installed
    PostgresError = Exception  # type: ignore[assignment]
    UniqueViolationError = Exception  # type: ignore[assignment]

from .analytics import ANALYTICS_ROUTER, burnout_monitor_loop
from .api_support import get_db_from_request, require_actor
from .assets_lifecycle import ASSETS_ROUTER, ConditionEvidenceCreate, offboarding_monitor_loop
from .ats_onboarding import ATS_ROUTER
from .auth import AUTH_ROUTER, hash_password
from .config import settings
from .db import Database, DatabaseUnavailable
from .device_middleware import (
    ZK_ROUTER,
    add_employee_to_all_devices,
    add_employee_to_selected_devices,
    delete_employee_from_all_devices,
    device_ingestion_loop,
)
from .i18n_ka import KA_TRANSLATIONS
from .labor_engine import build_monthly_timesheet_from_db, payroll_export_rows, persist_monthly_timesheet
from .mail_engine import send_and_log_email
from .mattermost_integration import (
    MATTERMOST_ROUTER,
    celebration_monitor_loop,
    late_arrival_monitor_loop,
    send_leave_approval_request,
)
from .monitoring import MONITORING_ROUTER, metrics_middleware, node_heartbeat_loop
from .performance import PERFORMANCE_ROUTER
from .rbac import AuthorizationError, ensure_can_export_payroll, ensure_can_view_attendance, ensure_permission
from .runtime_setup import ensure_runtime_schema
from .tenant import DEFAULT_FEATURE_FLAGS, resolve_request_tenant
from .user_experience import UX_ROUTER
from .connect_suite import INTEGRATIONS_ROUTER

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / 'static'
UPLOADS_DIR = STATIC_DIR / 'uploads'
LEAVE_UPLOADS_DIR = UPLOADS_DIR / 'leave'
PROFILE_UPLOADS_DIR = UPLOADS_DIR / 'profile'


class EmployeeCreateRequest(BaseModel):
    legal_entity_id: UUID
    employee_number: str
    personal_number: str | None = None
    first_name: str
    last_name: str
    email: str | None = None
    mobile_phone: str | None = None
    department_id: UUID | None = None
    job_role_id: UUID | None = None
    manager_employee_id: UUID | None = None
    hire_date: date
    base_salary: Decimal = Field(ge=0)
    pay_policy_id: UUID
    hourly_rate_override: Decimal | None = Field(default=None, ge=0)
    is_pension_participant: bool = True
    access_role_codes: list[str] = Field(default_factory=lambda: ['EMPLOYEE'])
    default_device_user_id: str | None = None


class EmployeeDailyStatusRequest(BaseModel):
    status_date: date
    work_mode: str
    note: str | None = None


class SeparationRecordRequest(BaseModel):
    separation_date: date
    reason_category: str
    reason_details: str | None = None
    eligible_rehire: bool = True


class ChatAccountLinkRequest(BaseModel):
    mattermost_user_id: str | None = None
    mattermost_username: str | None = None


class EmployeeUpdateRequest(BaseModel):
    first_name: str
    last_name: str
    email: str | None = None
    mobile_phone: str | None = None
    department_id: UUID | None = None
    job_role_id: UUID | None = None
    manager_employee_id: UUID | None = None
    base_salary: Decimal = Field(ge=0)
    pay_policy_id: UUID
    hourly_rate_override: Decimal | None = Field(default=None, ge=0)
    is_pension_participant: bool = True
    default_device_user_id: str | None = None


class JobRoleCreateRequest(BaseModel):
    legal_entity_id: UUID
    title_ka: str
    title_en: str | None = None
    description: str | None = None
    is_managerial: bool = False


class EmployeeDeviceSyncRequest(BaseModel):
    device_ids: list[UUID] = Field(default_factory=list)




class EntityOperationSettingsUpsertRequest(BaseModel):
    late_arrival_threshold_minutes: int = Field(default=15, ge=1, le=240)
    require_asset_clearance_for_final_payroll: bool = True
    default_onboarding_course_id: UUID | None = None


class MattermostIntegrationUpsertRequest(BaseModel):
    enabled: bool = False
    server_base_url: str | None = None
    incoming_webhook_url: str | None = None
    hr_webhook_url: str | None = None
    general_webhook_url: str | None = None
    it_webhook_url: str | None = None
    bot_access_token: str | None = None
    command_token: str | None = None
    action_secret: str | None = None
    default_team: str | None = None
    hr_channel: str | None = None
    general_channel: str | None = None
    it_channel: str | None = None


class ShiftSegmentInput(BaseModel):
    day_index: int = Field(ge=1, le=366)
    start_time: str
    end_time: str
    break_minutes: int = Field(default=0, ge=0, le=720)
    label: str | None = None


class ShiftPatternUpsertRequest(BaseModel):
    code: str
    name: str
    pattern_type: str = Field(default='fixed_weekly')
    cycle_length_days: int = Field(default=7, ge=1, le=366)
    timezone: str = 'Asia/Tbilisi'
    standard_weekly_hours: Decimal = Field(default=Decimal('40.00'), gt=0)
    early_check_in_grace_minutes: int = Field(default=60, ge=0, le=720)
    late_check_out_grace_minutes: int = Field(default=240, ge=0, le=720)
    grace_period_minutes: int = Field(default=15, ge=0, le=240)
    segments: list[ShiftSegmentInput] = Field(default_factory=list)


class AttendanceOverrideRequest(BaseModel):
    session_id: UUID | None = None
    work_date: date
    corrected_check_in: datetime
    corrected_check_out: datetime | None = None
    resolution_note: str = Field(min_length=5)
    mark_review_status: str = Field(default='corrected')


class WebPunchRequest(BaseModel):
    direction: str = Field(default='auto')
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class VacancyFieldOption(BaseModel):
    label: str
    value: str


class VacancyFieldDefinition(BaseModel):
    key: str
    label: str
    field_type: str
    required: bool = True
    options: list[VacancyFieldOption] = Field(default_factory=list)


class VacancyUpsertRequest(BaseModel):
    posting_code: str
    title_en: str
    title_ka: str
    description: str
    public_description: str | None = None
    employment_type: str
    location_text: str | None = None
    status: str = Field(default='draft')
    open_positions: int = Field(default=1, ge=1)
    salary_min: Decimal | None = Field(default=None, ge=0)
    salary_max: Decimal | None = Field(default=None, ge=0)
    department_id: UUID | None = None
    job_role_id: UUID | None = None
    closes_at: datetime | None = None
    public_slug: str | None = None
    external_form_url: str | None = None
    is_public: bool = True
    application_form_schema: list[VacancyFieldDefinition] = Field(default_factory=list)


class PublicCandidateApplicationRequest(BaseModel):
    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    source: str = 'career_page'
    current_company: str | None = None
    current_position: str | None = None
    notes: str | None = None
    answers: dict[str, Any] = Field(default_factory=dict)


class InventoryItemUpsertRequest(BaseModel):
    category_id: UUID | None = None
    asset_tag: str
    asset_name: str
    brand: str | None = None
    model: str | None = None
    serial_number: str | None = None
    current_condition: str = Field(default='new')
    current_status: str = Field(default='in_stock')
    purchase_date: date | None = None
    purchase_cost: Decimal | None = Field(default=None, ge=0)
    currency_code: str = 'GEL'
    assigned_department_id: UUID | None = None
    notes: str | None = None


class InventoryAssignRequest(BaseModel):
    employee_id: UUID
    assigned_at: datetime
    expected_return_at: datetime | None = None
    condition_on_issue: str = Field(default='good')
    note: str | None = None
    employee_signature_name: str
    evidence: list[ConditionEvidenceCreate] = Field(default_factory=list)


class PayrollMarkPaidRequest(BaseModel):
    paid_at: datetime | None = None
    payment_method: str = 'bank_transfer'
    payment_reference: str | None = None
    note: str | None = None


class SystemConfigUpsertRequest(BaseModel):
    trade_name: str | None = None
    logo_url: str | None = None
    logo_text: str | None = None
    primary_color: str = '#1A2238'
    standalone_chat_url: str | None = None
    allowed_web_punch_ips: list[str] = Field(default_factory=list)
    geofence_latitude: float | None = Field(default=None, ge=-90, le=90)
    geofence_longitude: float | None = Field(default=None, ge=-180, le=180)
    geofence_radius_meters: int | None = Field(default=None, ge=10, le=50000)
    income_tax_rate: Decimal | None = Field(default=None, ge=0, le=1)
    employee_pension_rate: Decimal | None = Field(default=None, ge=0, le=1)
    late_arrival_threshold_minutes: int = Field(default=15, ge=1, le=240)
    require_asset_clearance_for_final_payroll: bool = True
    default_onboarding_course_id: UUID | None = None


class EmployeeRoleUpdateRequest(BaseModel):
    role_codes: list[str] = Field(default_factory=list)


class EmployeeAccessGrantRequest(BaseModel):
    username: str | None = None
    delivery_channel: str = Field(default='email')
    send_invite: bool = True


class TenantSubscriptionUpdateRequest(BaseModel):
    attendance_enabled: bool = True
    payroll_enabled: bool = True
    ats_enabled: bool = True
    chat_enabled: bool = True
    assets_enabled: bool = True
    org_chart_enabled: bool = True
    performance_enabled: bool = True


class TenantDomainUpsertRequest(BaseModel):
    host: str
    subdomain: str | None = None
    is_primary: bool = False
    is_active: bool = True


class LegalEntityCreateRequest(BaseModel):
    legal_name: str
    trade_name: str
    tax_id: str
    host: str | None = None
    subdomain: str | None = None
    admin_username: str
    admin_email: str
    admin_password: str = Field(min_length=8)
    admin_first_name: str = 'Company'
    admin_last_name: str = 'Administrator'


class DeviceRegistryUpsertRequest(BaseModel):
    legal_entity_id: UUID
    brand: str
    transport: str
    device_type: str = Field(default='biometric_terminal')
    device_name: str
    model: str
    serial_number: str
    host: str
    port: int = Field(ge=1, le=65535)
    api_base_url: str | None = None
    username: str | None = None
    password_ciphertext: str | None = None
    device_timezone: str = 'Asia/Tbilisi'
    is_active: bool = True
    poll_interval_seconds: int = Field(default=60, ge=10, le=86400)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ManualAttendanceAdjustmentRequest(BaseModel):
    employee_id: UUID
    session_id: UUID | None = None
    work_date: date
    corrected_check_in: datetime
    corrected_check_out: datetime | None = None
    reason_comment: str = Field(min_length=5)


EMAIL_PATTERN = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
TENANT_ADMIN_PERMISSIONS = [
    'employee.read_self',
    'employee.read_department',
    'employee.manage',
    'attendance.read_self',
    'attendance.read_department',
    'attendance.read_all',
    'attendance.review',
    'compensation.read_all',
    'payroll.export',
    'device.manage',
    'assets.read_self',
    'assets.read_all',
    'assets.manage',
    'recruitment.read',
    'recruitment.manage',
]


def _slugify(value: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')
    return slug or 'vacancy'


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _validate_email(value: str | None) -> str | None:
    cleaned = _clean_text(value)
    if cleaned is None:
        return None
    if not EMAIL_PATTERN.match(cleaned):
        raise HTTPException(status_code=422, detail='გთხოვთ, შეიყვანოთ სწორი ელ-ფოსტის ფორმატი')
    return cleaned.lower()


def _validate_personal_number(value: str | None) -> str | None:
    cleaned = _clean_text(value)
    if cleaned is None:
        return None
    digits = re.sub(r'\D', '', cleaned)
    if len(digits) != 11:
        raise HTTPException(status_code=422, detail='პირადი ნომერი უნდა შედგებოდეს 11 ციფრისგან')
    return digits


def _validate_phone(value: str | None) -> str | None:
    cleaned = _clean_text(value)
    if cleaned is None:
        return None
    digits = re.sub(r'\D', '', cleaned)
    if len(digits) < 9 or len(digits) > 15:
        raise HTTPException(status_code=422, detail='ტელეფონის ნომერი უნდა შეიცავდეს 9-დან 15 ციფრამდე')
    return cleaned


def _temporary_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits + '!@#$%'
    return ''.join(secrets.choice(alphabet) for _ in range(length))


async def _ensure_access_role(
    conn: Any,
    *,
    code: str,
    name_en: str,
    name_ka: str,
    description: str,
    permission_codes: list[str],
) -> UUID:
    role_id = await conn.fetchval(
        """
        INSERT INTO access_roles (code, name_en, name_ka, description)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (code) DO UPDATE
           SET name_en = EXCLUDED.name_en,
               name_ka = EXCLUDED.name_ka,
               description = EXCLUDED.description,
               updated_at = now()
        RETURNING id
        """,
        code,
        name_en,
        name_ka,
        description,
    )
    await conn.execute(
        """
        DELETE FROM access_role_permissions
         WHERE access_role_id = $1
           AND NOT (permission_code = ANY($2::text[]))
        """,
        role_id,
        permission_codes,
    )
    await conn.execute(
        """
        INSERT INTO access_role_permissions (access_role_id, permission_code)
        SELECT $1, permission_code
          FROM unnest($2::text[]) AS permission_code
        ON CONFLICT DO NOTHING
        """,
        role_id,
        permission_codes,
    )
    return role_id


def _invite_link(token: str) -> str:
    return f"{settings.public_base_url}/ux/app?invite_token={token}"


def _safe_file_name(value: str) -> str:
    return re.sub(r'[^a-zA-Z0-9._-]+', '_', value).strip('_') or 'upload.bin'


async def _store_upload(upload: UploadFile, target_dir: Path, prefix: str) -> tuple[str, int]:
    target_dir.mkdir(parents=True, exist_ok=True)
    file_name = _safe_file_name(upload.filename or 'attachment.bin')
    unique_name = f'{prefix}_{secrets.token_hex(8)}_{file_name}'
    destination = target_dir / unique_name
    content = await upload.read()
    destination.write_bytes(content)
    return f"/static/uploads/{target_dir.name}/{unique_name}", len(content)


def _role_code_seed(title_en: str | None, title_ka: str) -> str:
    base = _slugify((title_en or '').strip())
    if base == 'vacancy':
        return f'ROLE-{secrets.token_hex(3).upper()}'
    return base.upper()[:48]


async def _unique_job_role_code(conn: Any, legal_entity_id: UUID, title_en: str | None, title_ka: str) -> str:
    base = _role_code_seed(title_en, title_ka)
    candidate = base
    suffix = 1
    while await conn.fetchval('SELECT 1 FROM job_roles WHERE legal_entity_id = $1 AND code = $2', legal_entity_id, candidate):
        suffix_text = f'-{suffix}'
        candidate = f'{base[: max(1, 48 - len(suffix_text))]}{suffix_text}'
        suffix += 1
    return candidate


def _department_code_seed(name: str) -> str:
    base = _slugify(name).replace('-', '_').upper()
    if not base or base == 'VACANCY':
        return f'DEPT_{secrets.token_hex(3).upper()}'
    return base[:48]


async def _unique_department_code(conn: Any, legal_entity_id: UUID, name: str) -> str:
    base = _department_code_seed(name)
    candidate = base
    suffix = 1
    while await conn.fetchval('SELECT 1 FROM departments WHERE legal_entity_id = $1 AND code = $2', legal_entity_id, candidate):
        suffix_text = f'_{suffix}'
        candidate = f'{base[: max(1, 48 - len(suffix_text))]}{suffix_text}'
        suffix += 1
    return candidate


async def _ensure_department(conn: Any, legal_entity_id: UUID, name: str | None) -> UUID | None:
    cleaned = _clean_text(name)
    if cleaned is None:
        return None
    existing = await conn.fetchval(
        """
        SELECT id
          FROM departments
         WHERE legal_entity_id = $1
           AND (lower(name_en) = lower($2) OR lower(name_ka) = lower($2))
         LIMIT 1
        """,
        legal_entity_id,
        cleaned,
    )
    if existing is not None:
        return existing
    code = await _unique_department_code(conn, legal_entity_id, cleaned)
    return await conn.fetchval(
        """
        INSERT INTO departments (legal_entity_id, code, name_en, name_ka)
        VALUES ($1, $2, $3, $4)
        RETURNING id
        """,
        legal_entity_id,
        code,
        cleaned,
        cleaned,
    )


async def _ensure_job_role(conn: Any, legal_entity_id: UUID, title: str | None) -> UUID | None:
    cleaned = _clean_text(title)
    if cleaned is None:
        return None
    existing = await conn.fetchval(
        """
        SELECT id
          FROM job_roles
         WHERE legal_entity_id = $1
           AND (lower(title_en) = lower($2) OR lower(title_ka) = lower($2))
         LIMIT 1
        """,
        legal_entity_id,
        cleaned,
    )
    if existing is not None:
        return existing
    code = await _unique_job_role_code(conn, legal_entity_id, cleaned, cleaned)
    return await conn.fetchval(
        """
        INSERT INTO job_roles (legal_entity_id, code, title_en, title_ka, is_managerial)
        VALUES ($1, $2, $3, $4, false)
        RETURNING id
        """,
        legal_entity_id,
        code,
        cleaned,
        cleaned,
    )


def _normalize_import_header(value: str | None) -> str:
    return re.sub(r'[^a-z0-9]+', '', (value or '').strip().lower())


def _normalize_import_row(row: dict[str | None, str | None]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in row.items():
        clean_key = _normalize_import_header(key)
        if clean_key:
            normalized[clean_key] = (value or '').strip()
    return normalized


def _import_value(row: dict[str, str], *aliases: str) -> str | None:
    for alias in aliases:
        value = row.get(_normalize_import_header(alias), '').strip()
        if value:
            return value
    return None


def _split_import_name(row: dict[str, str], row_number: int) -> tuple[str, str]:
    first_name = _clean_text(_import_value(row, 'first_name', 'firstname', 'given_name', 'givenname'))
    last_name = _clean_text(_import_value(row, 'last_name', 'lastname', 'surname', 'family_name', 'familyname'))
    if first_name and last_name:
        return first_name, last_name

    full_name = _clean_text(_import_value(row, 'full_name', 'fullname', 'name', 'user_name', 'username'))
    if full_name is None:
        raise HTTPException(status_code=422, detail=f'იმპორტის სტრიქონი {row_number}: თანამშრომლის სახელი ვერ მოიძებნა')

    parts = full_name.split()
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[0], ' '.join(parts[1:])


def _parse_import_decimal(value: str | None, row_number: int, field_label: str) -> Decimal | None:
    cleaned = _clean_text(value)
    if cleaned is None:
        return None
    normalized = cleaned.replace(' ', '').replace(',', '')
    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise HTTPException(status_code=422, detail=f'იმპორტის სტრიქონი {row_number}: ველი "{field_label}" არასწორია') from exc


def _decode_import_file(raw_content: bytes) -> str:
    for encoding in ('utf-8-sig', 'utf-16', 'utf-16-le', 'utf-16-be', 'cp1251', 'cp1252', 'latin-1'):
        try:
            return raw_content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise HTTPException(status_code=422, detail='ფაილის კოდირება ვერ განისაზღვრა, გთხოვთ CSV შეინახოთ UTF-8 ფორმატში')


def _parse_time(value: str) -> datetime:
    return datetime.strptime(value, '%H:%M')


def _validate_shift_pattern_payload(payload: ShiftPatternUpsertRequest) -> None:
    if payload.pattern_type not in {'fixed_weekly', 'cycle'}:
        raise HTTPException(status_code=400, detail='ცვლის ტიპი უნდა იყოს fixed_weekly ან cycle')
    if not payload.segments:
        raise HTTPException(status_code=400, detail='მიუთითეთ მინიმუმ ერთი ცვლის სეგმენტი')
    if len({segment.day_index for segment in payload.segments}) != len(payload.segments):
        raise HTTPException(status_code=400, detail='day_index მნიშვნელობები უნიკალური უნდა იყოს')
    if payload.pattern_type == 'fixed_weekly' and any(segment.day_index > 7 for segment in payload.segments):
        raise HTTPException(status_code=400, detail='fixed_weekly ტიპი მხოლოდ 1-დან 7-მდე დღეებს უჭერს მხარს')


def _normalized_device_registry_payload(payload: DeviceRegistryUpsertRequest) -> dict[str, Any]:
    brand = payload.brand.strip().lower()
    transport = payload.transport.strip().lower()
    device_type = (_clean_text(payload.device_type) or 'biometric_terminal').strip().lower()
    allowed_pairs = {
        'zk': 'adms',
        'dahua': 'http_cgi',
        'suprema': 'biostar',
    }
    allowed_device_types = {'biometric_terminal', 'rfid_card_reader', 'access_control_gate'}
    expected_transport = allowed_pairs.get(brand)
    if expected_transport is None:
        raise HTTPException(status_code=422, detail='მოწყობილობის ბრენდი არ არის მხარდაჭერილი')
    if transport != expected_transport:
        raise HTTPException(status_code=422, detail='არჩეული ბრენდისთვის ტრანსპორტის ტიპი არასწორია')
    if device_type not in allowed_device_types:
        raise HTTPException(status_code=422, detail='მოწყობილობის ტიპი უნდა იყოს biometric_terminal, rfid_card_reader ან access_control_gate')

    device_name = _clean_text(payload.device_name)
    if not device_name:
        raise HTTPException(status_code=422, detail='მიუთითეთ მოწყობილობის სახელი')

    host = _clean_text(payload.host)
    if not host:
        raise HTTPException(status_code=422, detail='მიუთითეთ მოწყობილობის IP ან host')

    api_base_url = _clean_text(payload.api_base_url)
    if api_base_url is None and transport in {'http_cgi', 'biostar'}:
        scheme = 'https' if payload.port == 443 else 'http'
        api_base_url = f'{scheme}://{host}:{payload.port}'

    return {
        'brand': brand,
        'transport': transport,
        'device_type': device_type,
        'device_name': device_name,
        'model': _clean_text(payload.model) or 'Unknown Model',
        'serial_number': _clean_text(payload.serial_number) or 'N/A',
        'host': host,
        'port': payload.port,
        'api_base_url': api_base_url,
        'username': _clean_text(payload.username),
        'password_ciphertext': _clean_text(payload.password_ciphertext),
        'device_timezone': _clean_text(payload.device_timezone) or 'Asia/Tbilisi',
        'is_active': payload.is_active,
        'poll_interval_seconds': payload.poll_interval_seconds,
        'metadata': payload.metadata,
    }


def _segment_payload(segment: ShiftSegmentInput) -> tuple[int, int, bool]:
    start_dt = _parse_time(segment.start_time)
    end_dt = _parse_time(segment.end_time)
    crosses_midnight = end_dt <= start_dt
    if crosses_midnight:
        end_dt += timedelta(days=1)
    planned_minutes = int((end_dt - start_dt).total_seconds() // 60)
    if planned_minutes <= 0:
        raise HTTPException(status_code=400, detail='ცვლის სეგმენტის ხანგრძლივობა დადებითი უნდა იყოს')
    if segment.break_minutes > planned_minutes:
        raise HTTPException(status_code=400, detail='შესვენება ცვლის ხანგრძლივობას არ უნდა აღემატებოდეს')
    return planned_minutes, planned_minutes >= 1440 or crosses_midnight, crosses_midnight


def _escape_pdf_text(value: str) -> str:
    return value.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def _build_simple_payslip_pdf(lines: list[str]) -> bytes:
    stream_rows = ['BT', '/F1 11 Tf']
    y = 790
    for line in lines:
        stream_rows.append(f"1 0 0 1 50 {y} Tm ({_escape_pdf_text(line)}) Tj")
        y -= 16
    stream_rows.append('ET')
    content_stream = '\n'.join(stream_rows).encode('utf-8')
    objects = [
        b'1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n',
        b'2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n',
        b'3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n',
        b'4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n',
        f'5 0 obj << /Length {len(content_stream)} >> stream\n'.encode('utf-8') + content_stream + b'\nendstream endobj\n',
    ]
    output = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for obj in objects:
        offsets.append(len(output))
        output.extend(obj)
    xref_start = len(output)
    output.extend(f'xref\n0 {len(offsets)}\n'.encode('utf-8'))
    output.extend(b'0000000000 65535 f \n')
    for offset in offsets[1:]:
        output.extend(f'{offset:010d} 00000 n \n'.encode('utf-8'))
    output.extend(
        f'trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF'.encode('utf-8')
    )
    return bytes(output)


def _build_simple_table_pdf(title: str, lines: list[str]) -> bytes:
    return _build_simple_payslip_pdf([title, ''] + lines)


def _build_minimal_xlsx(sheet_name: str, headers: list[str], rows: list[list[str]]) -> bytes:
    def _escape_xml(value: str) -> str:
        return (
            value.replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&apos;')
        )

    def _cell_ref(col_idx: int, row_idx: int) -> str:
        result = ''
        value = col_idx
        while value >= 0:
            result = chr(value % 26 + 65) + result
            value = value // 26 - 1
        return f'{result}{row_idx}'

    all_rows = [headers, *rows]
    worksheet_rows: list[str] = []
    for row_idx, row in enumerate(all_rows, start=1):
        cells = []
        for col_idx, value in enumerate(row):
            escaped = _escape_xml(str(value))
            cells.append(
                f'<c r="{_cell_ref(col_idx, row_idx)}" t="inlineStr"><is><t>{escaped}</t></is></c>'
            )
        worksheet_rows.append(f'<row r="{row_idx}">{"".join(cells)}</row>')
    worksheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(worksheet_rows)}</sheetData>'
        '</worksheet>'
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{_escape_xml(sheet_name[:31] or "Sheet1")}" sheetId="1" r:id="rId1"/></sheets>'
        '</workbook>'
    )
    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
        '</Relationships>'
    )
    root_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        '</Relationships>'
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '</Types>'
    )
    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
        '<borders count="1"><border/></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        '</styleSheet>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', content_types_xml)
        archive.writestr('_rels/.rels', root_rels_xml)
        archive.writestr('xl/workbook.xml', workbook_xml)
        archive.writestr('xl/_rels/workbook.xml.rels', workbook_rels_xml)
        archive.writestr('xl/worksheets/sheet1.xml', worksheet_xml)
        archive.writestr('xl/styles.xml', styles_xml)
    return buffer.getvalue()


def _db_error_message(exc: Exception) -> str:
    text = str(exc).lower()
    if 'email' in text:
        return 'ეს ელ-ფოსტა უკვე დაკავებულია'
    if 'personal_number' in text:
        return 'ეს პირადი ნომერი უკვე გამოიყენება'
    if 'employee_number' in text:
        return 'ეს თანამშრომლის ნომერი უკვე არსებობს'
    if 'serial_number' in text:
        return 'ეს სერიული ნომერი უკვე რეგისტრირებულია'
    if 'username' in text:
        return 'ეს მომხმარებლის სახელი უკვე დაკავებულია'
    if 'device_name' in text:
        return 'ამ სახელით მოწყობილობა უკვე არსებობს'
    return 'მონაცემების შენახვა ვერ მოხერხდა. გადაამოწმეთ შეყვანილი მნიშვნელობები.'


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get('x-forwarded-for')
    candidate = forwarded.split(',')[0].strip() if forwarded else (request.client.host if request.client else None)
    if not candidate:
        return None
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def _distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c


async def _validate_web_punch(request: Request, db: Database, legal_entity_id: UUID, latitude: float | None, longitude: float | None) -> tuple[bool, str]:
    config = await db.fetchrow(
        """
        SELECT allowed_web_punch_ips, geofence_latitude, geofence_longitude, geofence_radius_meters
          FROM entity_system_config
         WHERE legal_entity_id = $1
        """,
        legal_entity_id,
    )
    if config is None:
        return False, 'ვებ დაფიქსირება ამ კომპანიისთვის ჯერ არ არის კონფიგურირებული'
    allowed_ips = [item for item in (config['allowed_web_punch_ips'] or []) if item]
    client_ip = _client_ip(request)
    if allowed_ips:
        if client_ip is None:
            return False, 'მომხმარებლის IP მისამართის განსაზღვრა ვერ მოხერხდა'
        if client_ip not in allowed_ips:
            return False, 'თქვენ არ იმყოფებით ნებადართულ საოფისე ქსელში'
        return True, f'საოფისე IP დადასტურებულია: {client_ip}'
    if config['geofence_latitude'] is not None and config['geofence_longitude'] is not None and config['geofence_radius_meters'] is not None:
        if latitude is None or longitude is None:
            return False, 'ლოკაციით დაფიქსირებისთვის საჭიროა GPS კოორდინატები'
        distance = _distance_meters(
            float(config['geofence_latitude']),
            float(config['geofence_longitude']),
            latitude,
            longitude,
        )
        if distance > int(config['geofence_radius_meters']):
            return False, 'თქვენ არ იმყოფებით ოფისის ტერიტორიაზე'
        return True, f'ოფისის გეოზონაში ხართ ({int(distance)}მ)'
    return False, 'ვებ დაფიქსირებისთვის არც IP სიაა და არც გეოზონა მითითებული'


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = Database(settings.database_url)
    await db.connect()
    await ensure_runtime_schema(db)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    LEAVE_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    app.state.db = db
    tasks: list[asyncio.Task[Any]] = []
    if settings.enable_device_workers:
        tasks.append(
            asyncio.create_task(
                device_ingestion_loop(db, settings.device_ingestion_interval_seconds),
                name='device-ingestion-loop',
            )
        )
    if settings.enable_ops_workers:
        tasks.extend(
            [
                asyncio.create_task(late_arrival_monitor_loop(db, settings.late_arrival_scan_interval_seconds), name='late-arrival-loop'),
                asyncio.create_task(celebration_monitor_loop(db, settings.celebration_scan_interval_seconds), name='celebration-loop'),
                asyncio.create_task(offboarding_monitor_loop(db, settings.offboarding_scan_interval_seconds), name='offboarding-loop'),
                asyncio.create_task(burnout_monitor_loop(db, settings.burnout_scan_interval_seconds), name='burnout-loop'),
            ]
        )
    if settings.enable_node_heartbeat:
        tasks.append(
            asyncio.create_task(
                node_heartbeat_loop(db, settings.monitoring_heartbeat_interval_seconds),
                name='node-heartbeat-loop',
            )
        )
    app.state.background_tasks = tasks
    try:
        yield
    finally:
        for task in app.state.background_tasks:
            task.cancel()
        for task in app.state.background_tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        await db.close()


app = FastAPI(title='HRMS Georgia Enterprise', version='2.0.0', lifespan=lifespan)
app.middleware('http')(metrics_middleware)


@app.middleware('http')
async def tenant_context_middleware(request: Request, call_next):
    db = getattr(request.app.state, 'db', None)
    tenant = None
    if db is not None:
        tenant = await resolve_request_tenant(db, request)
    request.state.tenant = tenant
    request.state.tenant_legal_entity_id = tenant['legal_entity_id'] if tenant else None
    request.state.feature_flags = tenant['feature_flags'] if tenant else DEFAULT_FEATURE_FLAGS
    return await call_next(request)


if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )
if STATIC_DIR.exists():
    app.mount('/static', StaticFiles(directory=str(STATIC_DIR)), name='static')

app.include_router(AUTH_ROUTER)
app.include_router(ZK_ROUTER)
app.include_router(MATTERMOST_ROUTER)
app.include_router(ATS_ROUTER)
app.include_router(ASSETS_ROUTER)
app.include_router(PERFORMANCE_ROUTER)
app.include_router(ANALYTICS_ROUTER)
app.include_router(UX_ROUTER)
app.include_router(INTEGRATIONS_ROUTER)
app.include_router(MONITORING_ROUTER)




@app.exception_handler(AuthorizationError)
async def authorization_error_handler(request: Request, exc: AuthorizationError) -> JSONResponse:
    return JSONResponse(status_code=403, content={'detail': str(exc)})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    first_error = exc.errors()[0] if exc.errors() else {'msg': 'არასწორი მონაცემებია შეყვანილი'}
    return JSONResponse(status_code=422, content={'detail': str(first_error.get('msg') or 'არასწორი მონაცემებია შეყვანილი')})


@app.exception_handler(UniqueViolationError)
async def unique_violation_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=409, content={'detail': _db_error_message(exc)})


@app.exception_handler(PostgresError)
async def postgres_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={'detail': _db_error_message(exc)})


@app.exception_handler(DatabaseUnavailable)
async def database_unavailable_handler(request: Request, exc: DatabaseUnavailable) -> JSONResponse:
    return JSONResponse(status_code=503, content={'detail': 'ბაზასთან კავშირი დროებით მიუწვდომელია'})


@app.get('/')
async def root() -> dict[str, object]:
    return {
        'app': 'HRMS Georgia Enterprise',
        'version': '2.0.0',
        'features': [
            'Attendance and payroll for Georgia',
            'Mattermost chat-ops approvals',
            'ATS with onboarding automation',
            'Asset lifecycle and offboarding',
            'OKR and 360 feedback',
            'Burnout and turnover analytics',
            'Multi-company / multi-server monitoring',
        ],
    }


@app.get('/i18n/ka')
async def georgian_translations() -> dict[str, str]:
    return KA_TRANSLATIONS


@app.get('/employees')
async def employee_grid(
    request: Request,
    search: str | None = None,
    department_id: UUID | None = None,
    status_filter: str | None = None,
) -> list[dict[str, object]]:
    actor = await require_actor(request)
    ensure_permission(actor, 'employee.manage')
    db = get_db_from_request(request)
    rows = await db.fetch(
        """
        SELECT e.id,
               e.employee_number,
               e.first_name,
               e.last_name,
               e.email,
               e.mobile_phone,
               e.hire_date,
               e.employment_status::text AS employment_status,
               d.name_en AS department_name,
               jr.title_en AS job_title
          FROM employees e
          LEFT JOIN departments d ON d.id = e.department_id
          LEFT JOIN job_roles jr ON jr.id = e.job_role_id
         WHERE e.legal_entity_id = $1
           AND ($2::text IS NULL OR e.first_name ILIKE $2 OR e.last_name ILIKE $2 OR e.employee_number ILIKE $2 OR e.email::text ILIKE $2)
           AND ($3::uuid IS NULL OR e.department_id = $3)
           AND ($4::text IS NULL OR e.employment_status::text = $4)
         ORDER BY e.employee_number
         LIMIT 250
        """,
        actor.legal_entity_id,
        f'%{search.strip()}%' if search else None,
        department_id,
        status_filter,
    )
    return [dict(row) for row in rows]


@app.get('/employees/{employee_id}')
async def employee_detail(request: Request, employee_id: UUID) -> dict[str, object]:
    actor = await require_actor(request)
    db = get_db_from_request(request)
    row = await db.fetchrow(
        """
        SELECT e.id,
               e.legal_entity_id,
               e.employee_number,
               e.personal_number,
               e.first_name,
               e.last_name,
               e.email,
               e.mobile_phone,
               e.hire_date,
               e.termination_date,
               e.employment_status::text AS employment_status,
               e.default_device_user_id,
               d.id AS department_id,
               d.name_en AS department_name,
               jr.id AS job_role_id,
               jr.title_en AS job_title,
               m.id AS manager_employee_id,
               m.first_name || ' ' || m.last_name AS manager_name,
               p.file_url AS profile_photo_url,
               ec.policy_id AS pay_policy_id,
               ec.base_salary,
               ec.hourly_rate_override,
               ec.is_pension_participant
          FROM employees e
          LEFT JOIN departments d ON d.id = e.department_id
          LEFT JOIN job_roles jr ON jr.id = e.job_role_id
          LEFT JOIN employees m ON m.id = coalesce(e.line_manager_id, e.manager_employee_id)
          LEFT JOIN LATERAL (
              SELECT file_url
                FROM employee_file_uploads
               WHERE employee_id = e.id
                 AND file_category = 'profile_photo'
               ORDER BY created_at DESC
               LIMIT 1
          ) p ON true
          LEFT JOIN LATERAL (
              SELECT policy_id, base_salary, hourly_rate_override, is_pension_participant
                FROM employee_compensation
               WHERE employee_id = e.id
               ORDER BY effective_from DESC
               LIMIT 1
          ) ec ON true
         WHERE e.id = $1
        """,
        employee_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail='თანამშრომელი ვერ მოიძებნა')
    if row['legal_entity_id'] != actor.legal_entity_id and 'ADMIN' not in actor.role_codes:
        raise HTTPException(status_code=403, detail='თანამშრომელი სხვა იურიდიულ ერთეულს ეკუთვნის')
    if employee_id != actor.employee_id and not actor.has('employee.manage'):
        raise HTTPException(status_code=403, detail='ამ თანამშრომლის ნახვის უფლება არ გაქვთ')
    payload = dict(row)
    payload['id'] = str(payload['id'])
    payload['legal_entity_id'] = str(payload['legal_entity_id'])
    payload['department_id'] = str(payload['department_id']) if payload['department_id'] else None
    payload['job_role_id'] = str(payload['job_role_id']) if payload['job_role_id'] else None
    payload['manager_employee_id'] = str(payload['manager_employee_id']) if payload['manager_employee_id'] else None
    payload['pay_policy_id'] = str(payload['pay_policy_id']) if payload['pay_policy_id'] else None
    payload['base_salary'] = str(payload['base_salary']) if payload['base_salary'] is not None else None
    payload['hourly_rate_override'] = str(payload['hourly_rate_override']) if payload['hourly_rate_override'] is not None else None
    return payload


@app.post('/job-roles', status_code=status.HTTP_201_CREATED)
async def create_job_role(request: Request, payload: JobRoleCreateRequest) -> dict[str, str]:
    actor = await require_actor(request)
    ensure_permission(actor, 'employee.manage')
    if payload.legal_entity_id != actor.legal_entity_id and 'ADMIN' not in actor.role_codes:
        raise HTTPException(status_code=403, detail='სხვა იურიდიული ერთეულის პოზიციის შექმნა აკრძალულია')

    db = get_db_from_request(request)
    title_ka = _clean_text(payload.title_ka)
    title_en = _clean_text(payload.title_en) or title_ka
    description = _clean_text(payload.description)
    if title_ka is None:
        raise HTTPException(status_code=422, detail='პოზიციის ქართული დასახელება სავალდებულოა')

    if admin_email and await db.fetchval('SELECT 1 FROM employees WHERE lower(email) = lower($1)', admin_email):
        raise HTTPException(status_code=409, detail='ეს admin email უკვე დაკავებულია')
    if tax_id and await db.fetchval('SELECT 1 FROM legal_entities WHERE tax_id = $1', tax_id):
        raise HTTPException(status_code=409, detail='ეს tax id უკვე დარეგისტრირებულია')
    if resolved_host and await db.fetchval('SELECT 1 FROM tenant_domains WHERE host = $1', resolved_host):
        raise HTTPException(status_code=409, detail='ეს domain/host უკვე გამოყენებულია')

    tx = await db.transaction()
    try:
        existing = await tx.connection.fetchrow(
            """
            SELECT id, title_en, title_ka
              FROM job_roles
             WHERE legal_entity_id = $1
               AND (
                    lower(title_ka) = lower($2)
                    OR ($3::text IS NOT NULL AND lower(title_en) = lower($3))
               )
             LIMIT 1
            """,
            payload.legal_entity_id,
            title_ka,
            title_en,
        )
        if existing is not None:
            await tx.commit()
            return {
                'id': str(existing['id']),
                'title_ka': existing['title_ka'],
                'title_en': existing['title_en'],
            }

        code = await _unique_job_role_code(tx.connection, payload.legal_entity_id, title_en, title_ka)
        role_id = await tx.connection.fetchval(
            """
            INSERT INTO job_roles (legal_entity_id, code, title_en, title_ka, description, is_managerial)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
            """,
            payload.legal_entity_id,
            code,
            title_en,
            title_ka,
            description,
            payload.is_managerial,
        )
        await tx.commit()
    except Exception:
        await tx.rollback()
        raise

    return {'id': str(role_id), 'title_ka': title_ka, 'title_en': title_en or title_ka}


@app.post('/employees/import')
async def import_employees(request: Request, file: UploadFile = File(...), legal_entity_id: UUID | None = Form(default=None)) -> dict[str, int]:
    actor = await require_actor(request)
    ensure_permission(actor, 'employee.manage')

    target_legal_entity_id = legal_entity_id or actor.legal_entity_id
    if target_legal_entity_id != actor.legal_entity_id and 'ADMIN' not in actor.role_codes:
        raise HTTPException(status_code=403, detail='სხვა იურიდიული ერთეულისთვის თანამშრომლების იმპორტი აკრძალულია')

    file_name = (file.filename or '').lower()
    content_type = (file.content_type or '').lower()
    if not file_name.endswith('.csv') and 'csv' not in content_type and content_type not in {'text/plain', 'application/vnd.ms-excel'}:
        raise HTTPException(status_code=422, detail='SmartPSS იმპორტისთვის ატვირთეთ CSV ფაილი')

    raw_content = await file.read()
    if not raw_content:
        raise HTTPException(status_code=422, detail='იმპორტის ფაილი ცარიელია')

    decoded = _decode_import_file(raw_content)
    sample = decoded[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(decoded), dialect=dialect)
    if not reader.fieldnames:
        raise HTTPException(status_code=422, detail='CSV სათაურები ვერ მოიძებნა')

    rows = list(reader)
    if not rows:
        raise HTTPException(status_code=422, detail='იმპორტის CSV ცარიელია')

    db = get_db_from_request(request)
    tx = await db.transaction()
    try:
        pay_policy_id = await tx.connection.fetchval(
            """
            SELECT id
              FROM pay_policies
             WHERE legal_entity_id = $1
             ORDER BY code
             LIMIT 1
            """,
            target_legal_entity_id,
        )
        if pay_policy_id is None:
            raise HTTPException(status_code=422, detail='იურიდიული ერთეულისთვის pay policy ვერ მოიძებნა')

        employee_role_id = await tx.connection.fetchval("SELECT id FROM access_roles WHERE code = 'EMPLOYEE'")
        if employee_role_id is None:
            raise HTTPException(status_code=500, detail='EMPLOYEE role ვერ მოიძებნა')

        created_count = 0
        updated_count = 0
        skipped_count = 0
        imported_refs: dict[str, UUID] = {}
        pending_managers: list[tuple[UUID, str]] = []

        for row_number, source_row in enumerate(rows, start=2):
            row = _normalize_import_row(source_row)
            if not any(value.strip() for value in row.values()):
                skipped_count += 1
                continue

            employee_number = _clean_text(
                _import_value(
                    row,
                    'employee_number',
                    'employee_no',
                    'employee_code',
                    'person_no',
                    'personnel_no',
                    'user_id',
                    'userid',
                    'person_id',
                )
            ) or f'IMP-{row_number:04d}'
            first_name, last_name = _split_import_name(row, row_number)
            email = _validate_email(_import_value(row, 'email', 'mail', 'email_address'))
            mobile_phone = _validate_phone(_import_value(row, 'mobile_phone', 'mobile', 'phone', 'telephone'))
            personal_number = _validate_personal_number(_import_value(row, 'personal_number', 'personalno', 'id_number', 'national_id'))
            department_id = await _ensure_department(tx.connection, target_legal_entity_id, _import_value(row, 'department', 'department_name', 'dept', 'group_name'))
            job_role_id = await _ensure_job_role(tx.connection, target_legal_entity_id, _import_value(row, 'job_title', 'position', 'job_role', 'role', 'title'))
            default_device_user_id = _clean_text(_import_value(row, 'device_user_id', 'deviceuserid', 'user_id', 'userid')) or employee_number
            manager_ref = _clean_text(_import_value(row, 'manager_number', 'manager_employee_number', 'manager_email', 'manager_name', 'reportsto', 'line_manager'))
            salary_amount = _parse_import_decimal(_import_value(row, 'base_salary', 'salary', 'monthly_salary'), row_number, 'salary')
            hourly_rate_override = _parse_import_decimal(_import_value(row, 'hourly_rate', 'hourly_rate_override'), row_number, 'hourly_rate')

            existing = await tx.connection.fetchrow(
                """
                SELECT e.id,
                       ec.policy_id,
                       ec.base_salary,
                       ec.hourly_rate_override,
                       ec.is_pension_participant
                  FROM employees e
                  LEFT JOIN LATERAL (
                      SELECT policy_id, base_salary, hourly_rate_override, is_pension_participant
                        FROM employee_compensation
                       WHERE employee_id = e.id
                       ORDER BY effective_from DESC
                       LIMIT 1
                  ) ec ON true
                 WHERE e.legal_entity_id = $1
                   AND (
                        e.employee_number = $2
                        OR ($3::text IS NOT NULL AND lower(e.email) = lower($3))
                   )
                 ORDER BY CASE WHEN e.employee_number = $2 THEN 0 ELSE 1 END
                 LIMIT 1
                """,
                target_legal_entity_id,
                employee_number,
                email,
            )

            if existing is None:
                employee_id = await tx.connection.fetchval(
                    """
                    INSERT INTO employees (
                        legal_entity_id, employee_number, personal_number, first_name, last_name,
                        email, mobile_phone, department_id, job_role_id, manager_employee_id,
                        hire_date, default_device_user_id
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NULL, current_date, $10)
                    RETURNING id
                    """,
                    target_legal_entity_id,
                    employee_number,
                    personal_number,
                    first_name,
                    last_name,
                    email,
                    mobile_phone,
                    department_id,
                    job_role_id,
                    default_device_user_id,
                )
                await tx.connection.execute(
                    """
                    INSERT INTO employee_compensation (
                        employee_id, policy_id, effective_from, base_salary, hourly_rate_override, is_pension_participant
                    ) VALUES ($1, $2, current_date, $3, $4, true)
                    """,
                    employee_id,
                    pay_policy_id,
                    salary_amount if salary_amount is not None else Decimal('0'),
                    hourly_rate_override,
                )
                await tx.connection.execute(
                    """
                    INSERT INTO employee_access_roles (employee_id, access_role_id, assigned_by_employee_id)
                    VALUES ($1, $2, $3)
                    ON CONFLICT DO NOTHING
                    """,
                    employee_id,
                    employee_role_id,
                    actor.employee_id,
                )
                created_count += 1
            else:
                employee_id = existing['id']
                await tx.connection.execute(
                    """
                    UPDATE employees
                       SET personal_number = coalesce($2, personal_number),
                           first_name = $3,
                           last_name = $4,
                           email = coalesce($5, email),
                           mobile_phone = coalesce($6, mobile_phone),
                           department_id = coalesce($7, department_id),
                           job_role_id = coalesce($8, job_role_id),
                           default_device_user_id = coalesce($9, default_device_user_id),
                           updated_at = now()
                     WHERE id = $1
                    """,
                    employee_id,
                    personal_number,
                    first_name,
                    last_name,
                    email,
                    mobile_phone,
                    department_id,
                    job_role_id,
                    default_device_user_id,
                )

                next_policy_id = existing['policy_id'] or pay_policy_id
                next_base_salary = salary_amount if salary_amount is not None else (existing['base_salary'] if existing['base_salary'] is not None else Decimal('0'))
                next_hourly_rate = hourly_rate_override if hourly_rate_override is not None else existing['hourly_rate_override']
                next_pension = bool(existing['is_pension_participant']) if existing['is_pension_participant'] is not None else True
                await tx.connection.execute(
                    """
                    UPDATE employee_compensation
                       SET effective_to = current_date - interval '1 day',
                           updated_at = now()
                     WHERE employee_id = $1
                       AND effective_to IS NULL
                       AND (
                            policy_id <> $2
                            OR base_salary <> $3
                            OR coalesce(hourly_rate_override, 0) <> coalesce($4, 0)
                            OR is_pension_participant <> $5
                       )
                    """,
                    employee_id,
                    next_policy_id,
                    next_base_salary,
                    next_hourly_rate,
                    next_pension,
                )
                await tx.connection.execute(
                    """
                    INSERT INTO employee_compensation (
                        employee_id, policy_id, effective_from, base_salary, hourly_rate_override, is_pension_participant
                    )
                    SELECT $1, $2, current_date, $3, $4, $5
                     WHERE NOT EXISTS (
                        SELECT 1
                          FROM employee_compensation
                         WHERE employee_id = $1
                           AND effective_to IS NULL
                           AND policy_id = $2
                           AND base_salary = $3
                           AND coalesce(hourly_rate_override, 0) = coalesce($4, 0)
                           AND is_pension_participant = $5
                     )
                    """,
                    employee_id,
                    next_policy_id,
                    next_base_salary,
                    next_hourly_rate,
                    next_pension,
                )
                updated_count += 1

            imported_refs[employee_number.lower()] = employee_id
            imported_refs[f'{first_name} {last_name}'.strip().lower()] = employee_id
            if email:
                imported_refs[email.lower()] = employee_id
            if manager_ref:
                pending_managers.append((employee_id, manager_ref))

        for employee_id, manager_ref in pending_managers:
            lookup = manager_ref.lower()
            manager_id = imported_refs.get(lookup)
            if manager_id is None:
                manager_id = await tx.connection.fetchval(
                    """
                    SELECT id
                      FROM employees
                     WHERE legal_entity_id = $1
                       AND (
                            employee_number = $2
                            OR lower(coalesce(email, '')) = lower($2)
                            OR lower(trim(first_name || ' ' || last_name)) = lower($2)
                       )
                     LIMIT 1
                    """,
                    target_legal_entity_id,
                    manager_ref,
                )
            if manager_id is None or manager_id == employee_id:
                continue
            await tx.connection.execute(
                'UPDATE employees SET manager_employee_id = $2, line_manager_id = $2, updated_at = now() WHERE id = $1',
                employee_id,
                manager_id,
            )

        await tx.commit()
    except Exception:
        await tx.rollback()
        raise

    return {
        'created_count': created_count,
        'updated_count': updated_count,
        'skipped_count': skipped_count,
    }


@app.post('/employees', status_code=status.HTTP_201_CREATED)
async def create_employee(request: Request, payload: EmployeeCreateRequest) -> dict[str, str]:
    actor = await require_actor(request)
    ensure_permission(actor, 'employee.manage')
    if payload.legal_entity_id != actor.legal_entity_id and 'ADMIN' not in actor.role_codes:
        raise HTTPException(status_code=403, detail='სხვა იურიდიული ერთეულისთვის თანამშრომლის შექმნა აკრძალულია')
    db = get_db_from_request(request)
    email = _validate_email(payload.email)
    personal_number = _validate_personal_number(payload.personal_number)
    mobile_phone = _validate_phone(payload.mobile_phone)
    tx = await db.transaction()
    try:
        employee_id = await tx.connection.fetchval(
            """
            INSERT INTO employees (
                legal_entity_id, employee_number, personal_number, first_name, last_name,
                email, mobile_phone, department_id, job_role_id, manager_employee_id,
                hire_date, default_device_user_id
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING id
            """,
            payload.legal_entity_id,
            payload.employee_number,
            personal_number,
            payload.first_name,
            payload.last_name,
            email,
            mobile_phone,
            payload.department_id,
            payload.job_role_id,
            payload.manager_employee_id,
            payload.hire_date,
            payload.default_device_user_id,
        )
        await tx.connection.execute(
            'UPDATE employees SET line_manager_id = $2 WHERE id = $1',
            employee_id,
            payload.manager_employee_id,
        )
        await tx.connection.execute(
            """
            INSERT INTO employee_compensation (
                employee_id, policy_id, effective_from, base_salary, hourly_rate_override, is_pension_participant
            ) VALUES ($1, $2, $3, $4, $5, $6)
            """,
            employee_id,
            payload.pay_policy_id,
            payload.hire_date,
            payload.base_salary,
            payload.hourly_rate_override,
            payload.is_pension_participant,
        )
        roles = await tx.connection.fetch('SELECT id FROM access_roles WHERE code = ANY($1::citext[])', payload.access_role_codes)
        if len(roles) != len(set(code.upper() for code in payload.access_role_codes)):
            raise HTTPException(status_code=400, detail='ერთი ან რამდენიმე role კოდი არასწორია')
        await tx.connection.executemany(
            """
            INSERT INTO employee_access_roles (employee_id, access_role_id, assigned_by_employee_id)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
            """,
            [(employee_id, role['id'], actor.employee_id) for role in roles],
        )
        await tx.commit()
    except Exception:
        await tx.rollback()
        raise

    await add_employee_to_all_devices(db, employee_id)
    return {'employee_id': str(employee_id)}


@app.put('/employees/{employee_id}')
async def update_employee(request: Request, employee_id: UUID, payload: EmployeeUpdateRequest) -> dict[str, str]:
    actor = await require_actor(request)
    ensure_permission(actor, 'employee.manage')
    db = get_db_from_request(request)
    email = _validate_email(payload.email)
    mobile_phone = _validate_phone(payload.mobile_phone)
    tx = await db.transaction()
    try:
        legal_entity_id = await tx.connection.fetchval('SELECT legal_entity_id FROM employees WHERE id = $1', employee_id)
        if legal_entity_id is None:
            raise HTTPException(status_code=404, detail='თანამშრომელი ვერ მოიძებნა')
        if legal_entity_id != actor.legal_entity_id and 'ADMIN' not in actor.role_codes:
            raise HTTPException(status_code=403, detail='თანამშრომელი სხვა იურიდიულ ერთეულს ეკუთვნის')
        await tx.connection.execute(
            """
            UPDATE employees
               SET first_name = $2,
                   last_name = $3,
                   email = $4,
                   mobile_phone = $5,
                   department_id = $6,
                   job_role_id = $7,
                   manager_employee_id = $8,
                   default_device_user_id = $9,
                   updated_at = now()
             WHERE id = $1
            """,
            employee_id,
            payload.first_name,
            payload.last_name,
            email,
            mobile_phone,
            payload.department_id,
            payload.job_role_id,
            payload.manager_employee_id,
            payload.default_device_user_id,
        )
        await tx.connection.execute(
            'UPDATE employees SET line_manager_id = $2, updated_at = now() WHERE id = $1',
            employee_id,
            payload.manager_employee_id,
        )
        await tx.connection.execute(
            """
            UPDATE employee_compensation
               SET effective_to = current_date - interval '1 day',
                   updated_at = now()
             WHERE employee_id = $1
               AND effective_to IS NULL
               AND (policy_id <> $2 OR base_salary <> $3 OR coalesce(hourly_rate_override, 0) <> coalesce($4, 0) OR is_pension_participant <> $5)
            """,
            employee_id,
            payload.pay_policy_id,
            payload.base_salary,
            payload.hourly_rate_override,
            payload.is_pension_participant,
        )
        await tx.connection.execute(
            """
            INSERT INTO employee_compensation (
                employee_id, policy_id, effective_from, base_salary, hourly_rate_override, is_pension_participant
            )
            SELECT $1, $2, current_date, $3, $4, $5
             WHERE NOT EXISTS (
                SELECT 1
                  FROM employee_compensation
                 WHERE employee_id = $1
                   AND effective_to IS NULL
                   AND policy_id = $2
                   AND base_salary = $3
                   AND coalesce(hourly_rate_override, 0) = coalesce($4, 0)
                   AND is_pension_participant = $5
             )
            """,
            employee_id,
            payload.pay_policy_id,
            payload.base_salary,
            payload.hourly_rate_override,
            payload.is_pension_participant,
        )
        await tx.commit()
    except Exception:
        await tx.rollback()
        raise
    return {'status': 'updated'}


@app.post('/employees/{employee_id}/profile-photo')
async def upload_employee_profile_photo(request: Request, employee_id: UUID, photo: UploadFile = File(...)) -> dict[str, str]:
    actor = await require_actor(request)
    ensure_permission(actor, 'employee.manage')
    db = get_db_from_request(request)
    employee_row = await db.fetchrow('SELECT legal_entity_id FROM employees WHERE id = $1', employee_id)
    if employee_row is None:
        raise HTTPException(status_code=404, detail='თანამშრომელი ვერ მოიძებნა')
    if employee_row['legal_entity_id'] != actor.legal_entity_id and 'ADMIN' not in actor.role_codes:
        raise HTTPException(status_code=403, detail='თანამშრომელი სხვა იურიდიულ ერთეულს ეკუთვნის')

    content_type = (photo.content_type or '').lower()
    file_name = (photo.filename or '').lower()
    if content_type not in {'image/jpeg', 'image/jpg'} and not file_name.endswith(('.jpg', '.jpeg')):
        raise HTTPException(status_code=422, detail='Dahua-სთვის პროფილის ფოტო უნდა იყოს JPG ან JPEG ფორმატში')

    file_url, file_size = await _store_upload(photo, PROFILE_UPLOADS_DIR, f'employee_{employee_id}')
    await db.execute(
        """
        INSERT INTO employee_file_uploads (
            employee_id, legal_entity_id, file_category, file_name, file_url,
            content_type, file_size, created_by_employee_id
        )
        VALUES ($1, $2, 'profile_photo', $3, $4, $5, $6, $7)
        """,
        employee_id,
        employee_row['legal_entity_id'],
        _safe_file_name(photo.filename or 'profile.jpg'),
        file_url,
        photo.content_type,
        file_size,
        actor.employee_id,
    )
    return {'photo_url': file_url}


@app.post('/employees/{employee_id}/device-sync')
async def sync_employee_to_devices(request: Request, employee_id: UUID, payload: EmployeeDeviceSyncRequest | None = None) -> dict[str, object]:
    actor = await require_actor(request)
    ensure_permission(actor, 'device.manage')
    db = get_db_from_request(request)
    legal_entity_id = await db.fetchval('SELECT legal_entity_id FROM employees WHERE id = $1', employee_id)
    if legal_entity_id is None:
        raise HTTPException(status_code=404, detail='თანამშრომელი ვერ მოიძებნა')
    if legal_entity_id != actor.legal_entity_id and 'ADMIN' not in actor.role_codes:
        raise HTTPException(status_code=403, detail='თანამშრომელი სხვა იურიდიულ ერთეულს ეკუთვნის')
    if payload and payload.device_ids:
        synced_count = await add_employee_to_selected_devices(db, employee_id, payload.device_ids)
    else:
        await add_employee_to_all_devices(db, employee_id)
        synced_count = 0
    return {'status': 'queued', 'synced_device_count': synced_count}


@app.delete('/employees/{employee_id}/device-access', status_code=status.HTTP_204_NO_CONTENT)
async def revoke_device_access(request: Request, employee_id: UUID) -> Response:
    actor = await require_actor(request)
    ensure_permission(actor, 'employee.manage')
    db = get_db_from_request(request)
    await delete_employee_from_all_devices(db, employee_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post('/employees/{employee_id}/daily-status')
async def set_daily_status(request: Request, employee_id: UUID, payload: EmployeeDailyStatusRequest) -> dict[str, str]:
    actor = await require_actor(request)
    if employee_id != actor.employee_id:
        ensure_permission(actor, 'employee.manage')
    db = get_db_from_request(request)
    await db.execute(
        """
        INSERT INTO employee_status_calendar (employee_id, status_date, work_mode, note, created_by_employee_id)
        VALUES ($1, $2, $3::work_mode, $4, $5)
        ON CONFLICT (employee_id, status_date) DO UPDATE
           SET work_mode = EXCLUDED.work_mode,
               note = EXCLUDED.note,
               created_by_employee_id = EXCLUDED.created_by_employee_id,
               updated_at = now()
        """,
        employee_id,
        payload.status_date,
        payload.work_mode,
        payload.note,
        actor.employee_id,
    )
    return {'status': 'saved'}


@app.post('/employees/{employee_id}/chat-account')
async def link_chat_account(request: Request, employee_id: UUID, payload: ChatAccountLinkRequest) -> dict[str, str]:
    actor = await require_actor(request)
    if employee_id != actor.employee_id:
        ensure_permission(actor, 'employee.manage')
    db = get_db_from_request(request)
    await db.execute(
        """
        INSERT INTO employee_chat_accounts (employee_id, mattermost_user_id, mattermost_username)
        VALUES ($1, $2, $3)
        ON CONFLICT (employee_id) DO UPDATE
           SET mattermost_user_id = EXCLUDED.mattermost_user_id,
               mattermost_username = EXCLUDED.mattermost_username,
               updated_at = now()
        """,
        employee_id,
        payload.mattermost_user_id,
        payload.mattermost_username,
    )
    return {'status': 'linked'}


@app.post('/employees/{employee_id}/grant-access')
async def grant_employee_access(
    request: Request,
    employee_id: UUID,
    payload: EmployeeAccessGrantRequest | None = None,
) -> dict[str, str]:
    actor = await require_actor(request)
    ensure_permission(actor, 'employee.manage')
    db = get_db_from_request(request)
    employee = await db.fetchrow(
        """
        SELECT e.id,
               e.legal_entity_id,
               e.employee_number,
               e.first_name,
               e.last_name,
               e.email,
               coalesce(eca.mattermost_username, '') AS mattermost_username
          FROM employees e
          LEFT JOIN employee_chat_accounts eca ON eca.employee_id = e.id
         WHERE e.id = $1
        """,
        employee_id,
    )
    if employee is None:
        raise HTTPException(status_code=404, detail='თანამშრომელი ვერ მოიძებნა')
    if employee['legal_entity_id'] != actor.legal_entity_id and 'ADMIN' not in actor.role_codes:
        raise HTTPException(status_code=403, detail='სხვა იურიდიული ერთეულის თანამშრომელზე წვდომის გაცემა აკრძალულია')

    preferred_username = _clean_text(payload.username if payload else None)
    default_username = (
        preferred_username
        or _clean_text(employee['email'])
        or str(employee['employee_number']).strip().lower()
    )
    if not default_username:
        raise HTTPException(status_code=400, detail='მომხმარებლის სახელი ვერ განისაზღვრა')
    existing_identity = await db.fetchrow(
        'SELECT employee_id FROM auth_identities WHERE username = $1 LIMIT 1',
        default_username,
    )
    if existing_identity is not None and existing_identity['employee_id'] != employee_id:
        raise HTTPException(status_code=409, detail='ეს მომხმარებლის სახელი უკვე დაკავებულია')

    invite_token = secrets.token_urlsafe(32)
    temporary_password = _temporary_password()
    tx = await db.transaction()
    try:
        await tx.connection.execute(
            'DELETE FROM auth_identities WHERE employee_id = $1 AND username <> $2',
            employee_id,
            default_username,
        )
        await tx.connection.execute(
            """
            INSERT INTO auth_identities (employee_id, username, password_hash, is_active, updated_at)
            VALUES ($1, $2, $3, true, now())
            ON CONFLICT (username) DO UPDATE
               SET employee_id = EXCLUDED.employee_id,
                   password_hash = EXCLUDED.password_hash,
                   is_active = true,
                   updated_at = now()
            """,
            employee_id,
            default_username,
            hash_password(temporary_password),
        )
        await tx.connection.execute(
            """
            INSERT INTO auth_invites (
                employee_id, legal_entity_id, username, invite_token, temp_password_hash,
                recipient_email, sent_via, expires_at, created_by_employee_id, updated_at
            )
            VALUES (
                $1, $2, $3, $4, $5, $6, $7,
                now() + make_interval(mins => $8), $9, now()
            )
            """,
            employee_id,
            employee['legal_entity_id'],
            default_username,
            invite_token,
            hash_password(temporary_password),
            _clean_text(employee['email']),
            (payload.delivery_channel if payload else 'email'),
            settings.invite_ttl_minutes,
            actor.employee_id,
        )
        await tx.commit()
    except Exception:
        await tx.rollback()
        raise

    invite_link = _invite_link(invite_token)
    recipient_email = _clean_text(employee['email'])
    if (payload.send_invite if payload else True) and recipient_email and settings.smtp_host:
        await send_and_log_email(
            db,
            legal_entity_id=employee['legal_entity_id'],
            event_type='employee_access_grant',
            event_key=str(employee_id),
            to_email=recipient_email,
            subject='HRMS სისტემაში წვდომა',
            body_text=(
                f"{employee['first_name']} {employee['last_name']},\n\n"
                f"თქვენთვის შეიქმნა ESS წვდომა.\n"
                f"მომხმარებელი: {default_username}\n"
                f"დროებითი პაროლი: {temporary_password}\n"
                f"ინვაიტის ბმული: {invite_link}\n\n"
                f"ბმული ვალიდურია {settings.invite_ttl_minutes} წუთის განმავლობაში."
            ),
            extra_payload={'employee_id': str(employee_id)},
        )
    return {
        'status': 'granted',
        'username': default_username,
        'temporary_password': temporary_password,
        'invite_link': invite_link,
    }


@app.post('/devices/registry', status_code=status.HTTP_201_CREATED)
async def create_device_registry_item(request: Request, payload: DeviceRegistryUpsertRequest) -> dict[str, str]:
    actor = await require_actor(request)
    ensure_permission(actor, 'device.manage')
    tenant_legal_entity_id = getattr(request.state, 'tenant_legal_entity_id', None)
    if tenant_legal_entity_id and str(payload.legal_entity_id) != str(tenant_legal_entity_id):
        raise HTTPException(status_code=403, detail='ამ დომენიდან სხვა კომპანიის მოწყობილობის მიბმა აკრძალულია')
    if payload.legal_entity_id != actor.legal_entity_id and 'ADMIN' not in actor.role_codes:
        raise HTTPException(status_code=403, detail='სხვა იურიდიული ერთეულისთვის მოწყობილობის რეგისტრაცია აკრძალულია')
    db = get_db_from_request(request)
    normalized = _normalized_device_registry_payload(payload)
    device_id = await db.fetchval(
        """
        INSERT INTO device_registry (
            legal_entity_id, brand, transport, device_type, device_name, model, serial_number,
            host, port, api_base_url, username, password_ciphertext, device_timezone,
            is_active, poll_interval_seconds, metadata
        )
        VALUES ($1, $2::device_brand, $3::device_transport, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16::jsonb)
        RETURNING id
        """,
        payload.legal_entity_id,
        normalized['brand'],
        normalized['transport'],
        normalized['device_type'],
        normalized['device_name'],
        normalized['model'],
        normalized['serial_number'],
        normalized['host'],
        normalized['port'],
        normalized['api_base_url'],
        normalized['username'],
        normalized['password_ciphertext'],
        normalized['device_timezone'],
        normalized['is_active'],
        normalized['poll_interval_seconds'],
        json.dumps(normalized['metadata']),
    )
    return {'device_id': str(device_id)}


@app.put('/devices/registry/{device_id}')
async def update_device_registry_item(request: Request, device_id: UUID, payload: DeviceRegistryUpsertRequest) -> dict[str, str]:
    actor = await require_actor(request)
    ensure_permission(actor, 'device.manage')
    db = get_db_from_request(request)
    current_entity_id = await db.fetchval('SELECT legal_entity_id FROM device_registry WHERE id = $1', device_id)
    if current_entity_id is None:
        raise HTTPException(status_code=404, detail='მოწყობილობა ვერ მოიძებნა')
    tenant_legal_entity_id = getattr(request.state, 'tenant_legal_entity_id', None)
    if tenant_legal_entity_id and (str(current_entity_id) != str(tenant_legal_entity_id) or str(payload.legal_entity_id) != str(tenant_legal_entity_id)):
        raise HTTPException(status_code=403, detail='ამ დომენიდან სხვა კომპანიის მოწყობილობის რედაქტირება აკრძალულია')
    if current_entity_id != actor.legal_entity_id and 'ADMIN' not in actor.role_codes:
        raise HTTPException(status_code=403, detail='სხვა იურიდიული ერთეულის მოწყობილობის განახლება აკრძალულია')
    normalized = _normalized_device_registry_payload(payload)
    await db.execute(
        """
        UPDATE device_registry
           SET legal_entity_id = $2,
               brand = $3::device_brand,
               transport = $4::device_transport,
               device_type = $5,
               device_name = $6,
               model = $7,
               serial_number = $8,
               host = $9,
               port = $10,
               api_base_url = $11,
               username = $12,
               password_ciphertext = coalesce($13, password_ciphertext),
                device_timezone = $14,
               is_active = $15,
               poll_interval_seconds = $16,
               metadata = $17::jsonb,
               updated_at = now()
         WHERE id = $1
        """,
        device_id,
        payload.legal_entity_id,
        normalized['brand'],
        normalized['transport'],
        normalized['device_type'],
        normalized['device_name'],
        normalized['model'],
        normalized['serial_number'],
        normalized['host'],
        normalized['port'],
        normalized['api_base_url'],
        normalized['username'],
        normalized['password_ciphertext'],
        normalized['device_timezone'],
        normalized['is_active'],
        normalized['poll_interval_seconds'],
        json.dumps(normalized['metadata']),
    )
    return {'status': 'updated'}




@app.put('/entities/{legal_entity_id}/settings')
async def upsert_entity_settings(request: Request, legal_entity_id: UUID, payload: EntityOperationSettingsUpsertRequest) -> dict[str, str]:
    actor = await require_actor(request)
    ensure_permission(actor, 'employee.manage')
    db = get_db_from_request(request)
    await db.execute(
        """
        INSERT INTO entity_operation_settings (
            legal_entity_id, late_arrival_threshold_minutes,
            require_asset_clearance_for_final_payroll, default_onboarding_course_id
        ) VALUES ($1, $2, $3, $4)
        ON CONFLICT (legal_entity_id) DO UPDATE
           SET late_arrival_threshold_minutes = EXCLUDED.late_arrival_threshold_minutes,
               require_asset_clearance_for_final_payroll = EXCLUDED.require_asset_clearance_for_final_payroll,
               default_onboarding_course_id = EXCLUDED.default_onboarding_course_id,
               updated_at = now()
        """,
        legal_entity_id,
        payload.late_arrival_threshold_minutes,
        payload.require_asset_clearance_for_final_payroll,
        payload.default_onboarding_course_id,
    )
    return {'status': 'saved'}


@app.put('/integrations/mattermost/{legal_entity_id}')
async def upsert_mattermost_integration(request: Request, legal_entity_id: UUID, payload: MattermostIntegrationUpsertRequest) -> dict[str, str]:
    actor = await require_actor(request)
    ensure_permission(actor, 'employee.manage')
    db = get_db_from_request(request)
    await db.execute(
        """
        INSERT INTO mattermost_integrations (
            legal_entity_id, enabled, server_base_url, incoming_webhook_url, hr_webhook_url,
            general_webhook_url, it_webhook_url, bot_access_token, command_token,
            action_secret, default_team, hr_channel, general_channel, it_channel
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        ON CONFLICT (legal_entity_id) DO UPDATE
           SET enabled = EXCLUDED.enabled,
               server_base_url = EXCLUDED.server_base_url,
               incoming_webhook_url = EXCLUDED.incoming_webhook_url,
               hr_webhook_url = EXCLUDED.hr_webhook_url,
               general_webhook_url = EXCLUDED.general_webhook_url,
               it_webhook_url = EXCLUDED.it_webhook_url,
               bot_access_token = EXCLUDED.bot_access_token,
               command_token = EXCLUDED.command_token,
               action_secret = EXCLUDED.action_secret,
               default_team = EXCLUDED.default_team,
               hr_channel = EXCLUDED.hr_channel,
               general_channel = EXCLUDED.general_channel,
               it_channel = EXCLUDED.it_channel,
               updated_at = now()
        """,
        legal_entity_id,
        payload.enabled,
        payload.server_base_url,
        payload.incoming_webhook_url,
        payload.hr_webhook_url,
        payload.general_webhook_url,
        payload.it_webhook_url,
        payload.bot_access_token,
        payload.command_token,
        payload.action_secret,
        payload.default_team,
        payload.hr_channel,
        payload.general_channel,
        payload.it_channel,
    )
    return {'status': 'configured'}


@app.post('/shifts/patterns', status_code=status.HTTP_201_CREATED)
async def create_shift_pattern(request: Request, payload: ShiftPatternUpsertRequest) -> dict[str, str]:
    actor = await require_actor(request)
    ensure_permission(actor, 'attendance.review')
    _validate_shift_pattern_payload(payload)
    db = get_db_from_request(request)
    tx = await db.transaction()
    try:
        pattern_id = await tx.connection.fetchval(
            """
            INSERT INTO shift_patterns (
                legal_entity_id, code, name, pattern_type, cycle_length_days, timezone,
                standard_weekly_hours, early_check_in_grace_minutes, late_check_out_grace_minutes, grace_period_minutes
            )
            VALUES ($1, $2, $3, $4::shift_pattern_type, $5, $6, $7, $8, $9, $10)
            RETURNING id
            """,
            actor.legal_entity_id,
            payload.code,
            payload.name,
            payload.pattern_type,
            payload.cycle_length_days,
            payload.timezone,
            payload.standard_weekly_hours,
            payload.early_check_in_grace_minutes,
            payload.late_check_out_grace_minutes,
            payload.grace_period_minutes,
        )
        segment_rows = []
        for segment in payload.segments:
            planned_minutes, _, crosses_midnight = _segment_payload(segment)
            segment_rows.append(
                (
                    pattern_id,
                    segment.day_index,
                    segment.start_time,
                    planned_minutes,
                    segment.break_minutes,
                    crosses_midnight,
                    segment.label,
                )
            )
        await tx.connection.executemany(
            """
            INSERT INTO shift_pattern_segments (
                shift_pattern_id, day_index, start_time, planned_minutes, break_minutes, crosses_midnight, label
            )
            VALUES ($1, $2, $3::time, $4, $5, $6, $7)
            """,
            segment_rows,
        )
        await tx.commit()
    except Exception:
        await tx.rollback()
        raise
    return {'pattern_id': str(pattern_id)}


@app.put('/shifts/patterns/{pattern_id}')
async def update_shift_pattern(request: Request, pattern_id: UUID, payload: ShiftPatternUpsertRequest) -> dict[str, str]:
    actor = await require_actor(request)
    ensure_permission(actor, 'attendance.review')
    _validate_shift_pattern_payload(payload)
    db = get_db_from_request(request)
    legal_entity_id = await db.fetchval('SELECT legal_entity_id FROM shift_patterns WHERE id = $1', pattern_id)
    if legal_entity_id is None:
        raise HTTPException(status_code=404, detail='ცვლის შაბლონი ვერ მოიძებნა')
    if legal_entity_id != actor.legal_entity_id and 'ADMIN' not in actor.role_codes:
        raise HTTPException(status_code=403, detail='სხვა იურიდიულ ერთეულზე ცვლის განახლება აკრძალულია')
    tx = await db.transaction()
    try:
        await tx.connection.execute(
            """
            UPDATE shift_patterns
               SET code = $2,
                   name = $3,
                   pattern_type = $4::shift_pattern_type,
                   cycle_length_days = $5,
                   timezone = $6,
                   standard_weekly_hours = $7,
                   early_check_in_grace_minutes = $8,
                   late_check_out_grace_minutes = $9,
                   grace_period_minutes = $10,
                   updated_at = now()
             WHERE id = $1
            """,
            pattern_id,
            payload.code,
            payload.name,
            payload.pattern_type,
            payload.cycle_length_days,
            payload.timezone,
            payload.standard_weekly_hours,
            payload.early_check_in_grace_minutes,
            payload.late_check_out_grace_minutes,
            payload.grace_period_minutes,
        )
        await tx.connection.execute('DELETE FROM shift_pattern_segments WHERE shift_pattern_id = $1', pattern_id)
        segment_rows = []
        for segment in payload.segments:
            planned_minutes, _, crosses_midnight = _segment_payload(segment)
            segment_rows.append(
                (
                    pattern_id,
                    segment.day_index,
                    segment.start_time,
                    planned_minutes,
                    segment.break_minutes,
                    crosses_midnight,
                    segment.label,
                )
            )
        await tx.connection.executemany(
            """
            INSERT INTO shift_pattern_segments (
                shift_pattern_id, day_index, start_time, planned_minutes, break_minutes, crosses_midnight, label
            )
            VALUES ($1, $2, $3::time, $4, $5, $6, $7)
            """,
            segment_rows,
        )
        await tx.commit()
    except Exception:
        await tx.rollback()
        raise
    return {'status': 'updated'}


@app.post('/attendance/web-punch', status_code=status.HTTP_201_CREATED)
async def submit_web_punch(request: Request, payload: WebPunchRequest) -> dict[str, object]:
    actor = await require_actor(request)
    db = get_db_from_request(request)
    direction = payload.direction
    if direction == 'auto':
        last = await db.fetchrow(
            """
            SELECT direction::text AS direction
              FROM web_punch_events
             WHERE employee_id = $1
               AND (punch_ts AT TIME ZONE 'Asia/Tbilisi')::date = (timezone('Asia/Tbilisi', now()))::date
             ORDER BY punch_ts DESC
             LIMIT 1
            """,
            actor.employee_id,
        )
        if last is None or (last['direction'] or '') in {'out', 'unknown'}:
            direction = 'in'
        else:
            direction = 'out'
    elif direction not in {'in', 'out', 'unknown'}:
        raise HTTPException(status_code=400, detail='მიმართულება უნდა იყოს auto, in, out ან unknown')
    is_valid, reason = await _validate_web_punch(request, db, actor.legal_entity_id, payload.latitude, payload.longitude)
    punch_id = await db.fetchval(
        """
        INSERT INTO web_punch_events (
            employee_id, legal_entity_id, direction, source_ip, latitude, longitude, is_valid, validation_reason
        ) VALUES ($1, $2, $3::attendance_direction, $4, $5, $6, $7, $8)
        RETURNING id
        """,
        actor.employee_id,
        actor.legal_entity_id,
        direction,
        _client_ip(request),
        payload.latitude,
        payload.longitude,
        is_valid,
        reason,
    )
    if not is_valid:
        raise HTTPException(status_code=403, detail=reason)
    return {'punch_id': str(punch_id), 'status': 'recorded', 'validation_reason': reason, 'direction': direction}


@app.post('/attendance/review-flags/{flag_id}/resolve')
async def resolve_attendance_flag(request: Request, flag_id: UUID, payload: AttendanceOverrideRequest) -> dict[str, str]:
    actor = await require_actor(request)
    ensure_permission(actor, 'attendance.review')
    if payload.corrected_check_out is not None and payload.corrected_check_out < payload.corrected_check_in:
        raise HTTPException(status_code=400, detail='გამოსვლის დრო შემოსვლის დროზე ადრე ვერ იქნება')
    db = get_db_from_request(request)
    flag = await db.fetchrow(
        """
        SELECT arf.id, arf.employee_id, arf.session_id, arf.work_date, e.department_id
          FROM attendance_review_flags arf
          JOIN employees e ON e.id = arf.employee_id
         WHERE arf.id = $1
        """,
        flag_id,
    )
    if flag is None:
        raise HTTPException(status_code=404, detail='დასწრების შესასწორებელი ჩანაწერი ვერ მოიძებნა')
    ensure_can_view_attendance(actor, flag['employee_id'], flag['department_id'])
    total_minutes = 0
    overtime_minutes = 0
    if payload.corrected_check_out is not None:
        total_minutes = int((payload.corrected_check_out - payload.corrected_check_in).total_seconds() // 60)
        overtime_minutes = max(total_minutes - 480, 0)
    tx = await db.transaction()
    try:
        session_id = payload.session_id or flag['session_id']
        if session_id is None:
            session_id = await tx.connection.fetchval(
                """
                INSERT INTO attendance_work_sessions (
                    employee_id, work_date, check_in_ts, check_out_ts, total_minutes, overtime_minutes, review_status, manager_review_required
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7::review_status, false)
                RETURNING id
                """,
                flag['employee_id'],
                payload.work_date,
                payload.corrected_check_in,
                payload.corrected_check_out,
                total_minutes,
                overtime_minutes,
                payload.mark_review_status,
            )
        else:
            await tx.connection.execute(
                """
                UPDATE attendance_work_sessions
                   SET check_in_ts = $2,
                       check_out_ts = $3,
                       total_minutes = $4,
                       overtime_minutes = $5,
                       review_status = $6::review_status,
                       manager_review_required = false,
                       incomplete_reason = NULL,
                       updated_at = now()
                 WHERE id = $1
                """,
                session_id,
                payload.corrected_check_in,
                payload.corrected_check_out,
                total_minutes,
                overtime_minutes,
                payload.mark_review_status,
            )
        await tx.connection.execute(
            """
            UPDATE attendance_review_flags
               SET session_id = $2,
                   resolved_at = now(),
                   resolved_by_employee_id = $3,
                   resolution_note = $4
             WHERE id = $1
            """,
            flag_id,
            session_id,
            actor.employee_id,
            payload.resolution_note,
        )
        await tx.connection.execute(
            """
            INSERT INTO attendance_manual_adjustments (
                employee_id, legal_entity_id, session_id, work_date,
                corrected_check_in, corrected_check_out, reason_comment, created_by_employee_id
            )
            SELECT $1, e.legal_entity_id, $2, $3, $4, $5, $6, $7
              FROM employees e
             WHERE e.id = $1
            """,
            flag['employee_id'],
            session_id,
            payload.work_date,
            payload.corrected_check_in,
            payload.corrected_check_out,
            payload.resolution_note,
            actor.employee_id,
        )
        await tx.commit()
    except Exception:
        await tx.rollback()
        raise
    return {'status': 'resolved'}


@app.post('/attendance/manual-adjustments', status_code=status.HTTP_201_CREATED)
async def create_manual_attendance_adjustment(
    request: Request,
    payload: ManualAttendanceAdjustmentRequest,
) -> dict[str, str]:
    actor = await require_actor(request)
    ensure_permission(actor, 'attendance.review')
    if payload.corrected_check_out is not None and payload.corrected_check_out < payload.corrected_check_in:
        raise HTTPException(status_code=400, detail='გასვლის დრო შემოსვლის დროზე ადრე ვერ იქნება')
    db = get_db_from_request(request)
    employee = await db.fetchrow(
        'SELECT legal_entity_id, department_id FROM employees WHERE id = $1',
        payload.employee_id,
    )
    if employee is None:
        raise HTTPException(status_code=404, detail='თანამშრომელი ვერ მოიძებნა')
    ensure_can_view_attendance(actor, payload.employee_id, employee['department_id'])
    total_minutes = 0
    overtime_minutes = 0
    if payload.corrected_check_out is not None:
        total_minutes = int((payload.corrected_check_out - payload.corrected_check_in).total_seconds() // 60)
        overtime_minutes = max(total_minutes - 480, 0)
    tx = await db.transaction()
    try:
        session_id = payload.session_id
        if session_id:
            await tx.connection.execute(
                """
                UPDATE attendance_work_sessions
                   SET check_in_ts = $2,
                       check_out_ts = $3,
                       total_minutes = $4,
                       overtime_minutes = $5,
                       review_status = 'corrected'::review_status,
                       manager_review_required = false,
                       incomplete_reason = $6,
                       updated_at = now()
                 WHERE id = $1
                """,
                session_id,
                payload.corrected_check_in,
                payload.corrected_check_out,
                total_minutes,
                overtime_minutes,
                payload.reason_comment,
            )
        else:
            session_id = await tx.connection.fetchval(
                """
                INSERT INTO attendance_work_sessions (
                    employee_id, work_date, check_in_ts, check_out_ts,
                    total_minutes, overtime_minutes, review_status, incomplete_reason, manager_review_required
                )
                VALUES ($1, $2, $3, $4, $5, $6, 'corrected'::review_status, $7, false)
                RETURNING id
                """,
                payload.employee_id,
                payload.work_date,
                payload.corrected_check_in,
                payload.corrected_check_out,
                total_minutes,
                overtime_minutes,
                payload.reason_comment,
            )
        adjustment_id = await tx.connection.fetchval(
            """
            INSERT INTO attendance_manual_adjustments (
                employee_id, legal_entity_id, session_id, work_date,
                corrected_check_in, corrected_check_out, reason_comment, created_by_employee_id
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
            """,
            payload.employee_id,
            employee['legal_entity_id'],
            session_id,
            payload.work_date,
            payload.corrected_check_in,
            payload.corrected_check_out,
            payload.reason_comment,
            actor.employee_id,
        )
        await tx.commit()
    except Exception:
        await tx.rollback()
        raise
    return {'adjustment_id': str(adjustment_id), 'status': 'saved'}


@app.post('/vacancies', status_code=status.HTTP_201_CREATED)
async def create_vacancy(request: Request, payload: VacancyUpsertRequest) -> dict[str, str]:
    actor = await require_actor(request)
    ensure_permission(actor, 'recruitment.manage')
    db = get_db_from_request(request)
    slug = payload.public_slug or f"{_slugify(payload.title_en)}-{payload.posting_code.lower()}"
    vacancy_id = await db.fetchval(
        """
        INSERT INTO job_postings (
            legal_entity_id, department_id, job_role_id, posting_code, title_en, title_ka,
            description, public_description, employment_type, location_text, status, open_positions,
            salary_min, salary_max, created_by_employee_id, published_at, closes_at,
            public_slug, external_form_url, is_public, application_form_schema
        )
        VALUES (
            $1, $2, $3, $4, $5, $6,
            $7, $8, $9, $10, $11::recruitment_posting_status, $12,
            $13, $14, $15, CASE WHEN $11 = 'published' THEN now() ELSE NULL END, $16,
            $17, $18, $19, $20::jsonb
        )
        RETURNING id
        """,
        actor.legal_entity_id,
        payload.department_id,
        payload.job_role_id,
        payload.posting_code,
        payload.title_en,
        payload.title_ka,
        payload.description,
        payload.public_description or payload.description,
        payload.employment_type,
        payload.location_text,
        payload.status,
        payload.open_positions,
        payload.salary_min,
        payload.salary_max,
        actor.employee_id,
        payload.closes_at,
        slug,
        payload.external_form_url,
        payload.is_public,
        json.dumps([field.model_dump() for field in payload.application_form_schema]),
    )
    return {'vacancy_id': str(vacancy_id), 'public_slug': slug}


@app.put('/vacancies/{vacancy_id}')
async def update_vacancy(request: Request, vacancy_id: UUID, payload: VacancyUpsertRequest) -> dict[str, str]:
    actor = await require_actor(request)
    ensure_permission(actor, 'recruitment.manage')
    db = get_db_from_request(request)
    legal_entity_id = await db.fetchval('SELECT legal_entity_id FROM job_postings WHERE id = $1', vacancy_id)
    if legal_entity_id is None:
        raise HTTPException(status_code=404, detail='ვაკანსია ვერ მოიძებნა')
    if legal_entity_id != actor.legal_entity_id and 'ADMIN' not in actor.role_codes:
        raise HTTPException(status_code=403, detail='სხვა იურიდიულ ერთეულზე ვაკანსიის განახლება აკრძალულია')
    slug = payload.public_slug or f"{_slugify(payload.title_en)}-{payload.posting_code.lower()}"
    await db.execute(
        """
        UPDATE job_postings
           SET department_id = $2,
               job_role_id = $3,
               posting_code = $4,
               title_en = $5,
               title_ka = $6,
               description = $7,
               public_description = $8,
               employment_type = $9,
               location_text = $10,
               status = $11::recruitment_posting_status,
               open_positions = $12,
               salary_min = $13,
               salary_max = $14,
               published_at = CASE WHEN $11 = 'published' AND published_at IS NULL THEN now() ELSE published_at END,
               closes_at = $15,
               public_slug = $16,
               external_form_url = $17,
               is_public = $18,
               application_form_schema = $19::jsonb,
               updated_at = now()
         WHERE id = $1
        """,
        vacancy_id,
        payload.department_id,
        payload.job_role_id,
        payload.posting_code,
        payload.title_en,
        payload.title_ka,
        payload.description,
        payload.public_description or payload.description,
        payload.employment_type,
        payload.location_text,
        payload.status,
        payload.open_positions,
        payload.salary_min,
        payload.salary_max,
        payload.closes_at,
        slug,
        payload.external_form_url,
        payload.is_public,
        json.dumps([field.model_dump() for field in payload.application_form_schema]),
    )
    return {'status': 'updated', 'public_slug': slug}


@app.get('/public/vacancies/{public_slug}')
async def public_vacancy_detail(public_slug: str, request: Request) -> dict[str, object]:
    db = get_db_from_request(request)
    row = await db.fetchrow(
        """
        SELECT id, legal_entity_id, posting_code, title_en, title_ka, description, public_description, employment_type,
               location_text, status::text AS status, open_positions, salary_min, salary_max,
               closes_at, public_slug, external_form_url, is_public, application_form_schema
          FROM job_postings
         WHERE public_slug = $1
           AND is_public = true
        """,
        public_slug,
    )
    if row is None:
        raise HTTPException(status_code=404, detail='საჯარო ვაკანსია ვერ მოიძებნა')
    tenant_legal_entity_id = getattr(request.state, 'tenant_legal_entity_id', None)
    if tenant_legal_entity_id and str(row['legal_entity_id']) != str(tenant_legal_entity_id):
        raise HTTPException(status_code=404, detail='საჯარო ვაკანსია ვერ მოიძებნა')
    payload = dict(row)
    payload['id'] = str(payload['id'])
    payload['application_form_schema'] = payload['application_form_schema'] or []
    payload['salary_min'] = str(payload['salary_min']) if payload['salary_min'] is not None else None
    payload['salary_max'] = str(payload['salary_max']) if payload['salary_max'] is not None else None
    payload['closes_at'] = payload['closes_at'].isoformat() if payload['closes_at'] else None
    payload['apply_url'] = f'/public/vacancies/{public_slug}/apply'
    return payload


@app.post('/public/vacancies/{public_slug}/apply', status_code=status.HTTP_201_CREATED)
async def public_vacancy_apply(public_slug: str, payload: PublicCandidateApplicationRequest, request: Request) -> dict[str, str]:
    db = get_db_from_request(request)
    email = _validate_email(payload.email)
    phone = _validate_phone(payload.phone)
    vacancy = await db.fetchrow(
        """
        SELECT id, legal_entity_id, external_form_url
          FROM job_postings
         WHERE public_slug = $1
           AND is_public = true
           AND status = 'published'
        """,
        public_slug,
    )
    if vacancy is None:
        raise HTTPException(status_code=404, detail='გამოქვეყნებული ვაკანსია ვერ მოიძებნა')
    tenant_legal_entity_id = getattr(request.state, 'tenant_legal_entity_id', None)
    if tenant_legal_entity_id and str(vacancy['legal_entity_id']) != str(tenant_legal_entity_id):
        raise HTTPException(status_code=404, detail='გამოქვეყნებული ვაკანსია ვერ მოიძებნა')
    if vacancy['external_form_url']:
        raise HTTPException(status_code=409, detail='ამ ვაკანსიაზე განაცხადი მიიღება გარე Google Form-ით')
    stage_id = await db.fetchval(
        """
        SELECT id
          FROM candidate_pipeline_stages
         WHERE legal_entity_id = $1
         ORDER BY CASE WHEN upper(code::text) = 'APPLIED' THEN 0 ELSE 1 END, sort_order
         LIMIT 1
        """,
        vacancy['legal_entity_id'],
    )
    if stage_id is None:
        raise HTTPException(status_code=500, detail='კანდიდატის ეტაპები კონფიგურირებული არ არის')
    tx = await db.transaction()
    try:
        candidate_id = None
        if email:
            candidate_id = await tx.connection.fetchval(
                'SELECT id FROM candidates WHERE legal_entity_id = $1 AND email = $2',
                vacancy['legal_entity_id'],
                email,
            )
        if candidate_id is None:
            candidate_id = await tx.connection.fetchval(
                """
                INSERT INTO candidates (
                    legal_entity_id, first_name, last_name, email, phone, city, source, current_company, current_position, notes
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING id
                """,
                vacancy['legal_entity_id'],
                payload.first_name,
                payload.last_name,
                email,
                phone,
                payload.city,
                payload.source,
                payload.current_company,
                payload.current_position,
                payload.notes,
            )
        application_id = await tx.connection.fetchval(
            """
            INSERT INTO candidate_applications (
                candidate_id, job_posting_id, current_stage_id, application_payload
            )
            VALUES ($1, $2, $3, $4::jsonb)
            ON CONFLICT (candidate_id, job_posting_id) DO UPDATE
               SET application_payload = EXCLUDED.application_payload,
                   updated_at = now()
            RETURNING id
            """,
            candidate_id,
            vacancy['id'],
            stage_id,
            json.dumps({'answers': payload.answers}),
        )
        await tx.connection.execute(
            """
            INSERT INTO candidate_pipeline (application_id, stage_id, comment)
            VALUES ($1, $2, $3)
            """,
            application_id,
            stage_id,
            'Public application submitted',
        )
        await tx.commit()
    except Exception:
        await tx.rollback()
        raise
    return {'application_id': str(application_id), 'status': 'submitted'}


@app.post('/inventory/items', status_code=status.HTTP_201_CREATED)
async def create_inventory_item(request: Request, payload: InventoryItemUpsertRequest) -> dict[str, str]:
    actor = await require_actor(request)
    ensure_permission(actor, 'assets.manage')
    db = get_db_from_request(request)
    item_id = await db.fetchval(
        """
        INSERT INTO inventory_items (
            legal_entity_id, category_id, asset_tag, asset_name, brand, model, serial_number,
            current_condition, current_status, purchase_date, purchase_cost, currency_code,
            assigned_department_id, notes
        )
        VALUES (
            $1, $2, $3, $4, $5, $6, $7,
            $8::asset_condition, $9::asset_status, $10, $11, $12,
            $13, $14
        )
        RETURNING id
        """,
        actor.legal_entity_id,
        payload.category_id,
        payload.asset_tag,
        payload.asset_name,
        payload.brand,
        payload.model,
        payload.serial_number,
        payload.current_condition,
        payload.current_status,
        payload.purchase_date,
        payload.purchase_cost,
        payload.currency_code,
        payload.assigned_department_id,
        payload.notes,
    )
    return {'item_id': str(item_id)}


@app.put('/inventory/items/{item_id}')
async def update_inventory_item(request: Request, item_id: UUID, payload: InventoryItemUpsertRequest) -> dict[str, str]:
    actor = await require_actor(request)
    ensure_permission(actor, 'assets.manage')
    db = get_db_from_request(request)
    legal_entity_id = await db.fetchval('SELECT legal_entity_id FROM inventory_items WHERE id = $1', item_id)
    if legal_entity_id is None:
        raise HTTPException(status_code=404, detail='ინვენტარის ჩანაწერი ვერ მოიძებნა')
    if legal_entity_id != actor.legal_entity_id and 'ADMIN' not in actor.role_codes:
        raise HTTPException(status_code=403, detail='სხვა იურიდიულ ერთეულზე ინვენტარის განახლება აკრძალულია')
    await db.execute(
        """
        UPDATE inventory_items
           SET category_id = $2,
               asset_tag = $3,
               asset_name = $4,
               brand = $5,
               model = $6,
               serial_number = $7,
               current_condition = $8::asset_condition,
               current_status = $9::asset_status,
               purchase_date = $10,
               purchase_cost = $11,
               currency_code = $12,
               assigned_department_id = $13,
               notes = $14,
               updated_at = now()
         WHERE id = $1
        """,
        item_id,
        payload.category_id,
        payload.asset_tag,
        payload.asset_name,
        payload.brand,
        payload.model,
        payload.serial_number,
        payload.current_condition,
        payload.current_status,
        payload.purchase_date,
        payload.purchase_cost,
        payload.currency_code,
        payload.assigned_department_id,
        payload.notes,
    )
    return {'status': 'updated'}


@app.post('/inventory/items/{item_id}/assign', status_code=status.HTTP_201_CREATED)
async def assign_inventory_item(request: Request, item_id: UUID, payload: InventoryAssignRequest) -> dict[str, str]:
    actor = await require_actor(request)
    ensure_permission(actor, 'assets.manage')
    db = get_db_from_request(request)
    tx = await db.transaction()
    try:
        assignment_id = await tx.connection.fetchval(
            """
            INSERT INTO asset_assignments (
                item_id, employee_id, assigned_by_employee_id, assigned_at, expected_return_at,
                condition_on_issue, note, employee_acknowledged_at
            )
            VALUES ($1, $2, $3, $4, $5, $6::asset_condition, $7, now())
            RETURNING id
            """,
            item_id,
            payload.employee_id,
            actor.employee_id,
            payload.assigned_at,
            payload.expected_return_at,
            payload.condition_on_issue,
            payload.note,
        )
        if payload.evidence:
            await tx.connection.executemany(
                """
                INSERT INTO asset_condition_evidence (assignment_id, evidence_phase, file_url, note, captured_by_employee_id)
                VALUES ($1, 'issue', $2, $3, $4)
                """,
                [(assignment_id, evidence.file_url, evidence.note, actor.employee_id) for evidence in payload.evidence],
            )
        await tx.connection.execute(
            """
            INSERT INTO asset_handover_forms (assignment_id, employee_signature_name, handover_summary)
            VALUES ($1, $2, $3)
            """,
            assignment_id,
            payload.employee_signature_name,
            payload.note or f'Digital handover completed by {payload.employee_signature_name}',
        )
        await tx.connection.execute(
            """
            UPDATE inventory_items
               SET current_status = 'assigned',
                   current_condition = $2::asset_condition,
                   updated_at = now()
             WHERE id = $1
            """,
            item_id,
            payload.condition_on_issue,
        )
        await tx.commit()
    except Exception:
        await tx.rollback()
        raise
    return {'assignment_id': str(assignment_id)}


@app.post('/payroll/timesheets/{timesheet_id}/mark-paid')
async def mark_timesheet_paid(request: Request, timesheet_id: UUID, payload: PayrollMarkPaidRequest) -> dict[str, str]:
    actor = await require_actor(request)
    ensure_can_export_payroll(actor)
    db = get_db_from_request(request)
    row = await db.fetchrow(
        """
        SELECT mts.id,
               mts.employee_id,
               mts.year,
               mts.month,
               mts.total_minutes,
               mts.overtime_minutes,
               mts.gross_pay,
               mts.employee_pension_amount,
               mts.income_tax_amount,
               mts.net_pay,
               e.employee_number,
               e.first_name,
               e.last_name
          FROM monthly_timesheets mts
          JOIN employees e ON e.id = mts.employee_id
         WHERE mts.id = $1
        """,
        timesheet_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail='ტაბელი ვერ მოიძებნა')
    payslip_name = f"payslip_{row['employee_number']}_{row['year']}_{int(row['month']):02d}.pdf"
    pdf_bytes = _build_simple_payslip_pdf(
        [
            'HRMS Georgia Enterprise Payslip',
            f"Employee: {row['first_name']} {row['last_name']} ({row['employee_number']})",
            f"Period: {row['year']}-{int(row['month']):02d}",
            f"Worked hours: {round(int(row['total_minutes']) / 60, 2)}",
            f"Overtime hours: {round(int(row['overtime_minutes']) / 60, 2)}",
            f"Gross pay: {row['gross_pay']} GEL",
            f"Pension: {row['employee_pension_amount']} GEL",
            f"Income tax: {row['income_tax_amount']} GEL",
            f"Net pay: {row['net_pay']} GEL",
            f"Locked by: {actor.employee_id}",
        ]
    )
    paid_at = payload.paid_at or datetime.utcnow()
    payment_id = await db.fetchval(
        """
        INSERT INTO payroll_payment_records (
            timesheet_id, employee_id, paid_at, payment_method, payment_reference, note,
            payslip_file_name, payslip_pdf, locked_by_employee_id
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (timesheet_id) DO UPDATE
           SET paid_at = EXCLUDED.paid_at,
               payment_method = EXCLUDED.payment_method,
               payment_reference = EXCLUDED.payment_reference,
               note = EXCLUDED.note,
               payslip_file_name = EXCLUDED.payslip_file_name,
               payslip_pdf = EXCLUDED.payslip_pdf,
               locked_by_employee_id = EXCLUDED.locked_by_employee_id,
               updated_at = now()
        RETURNING id
        """,
        timesheet_id,
        row['employee_id'],
        paid_at,
        payload.payment_method,
        payload.payment_reference,
        payload.note,
        payslip_name,
        pdf_bytes,
        actor.employee_id,
    )
    await db.execute(
        """
        UPDATE monthly_timesheets
           SET status = 'locked',
               approved_at = coalesce(approved_at, $2),
               approved_by_employee_id = coalesce(approved_by_employee_id, $3),
               updated_at = now()
         WHERE id = $1
        """,
        timesheet_id,
        paid_at,
        actor.employee_id,
    )
    return {'payment_id': str(payment_id), 'payslip_file_name': payslip_name}


@app.get('/payroll/timesheets/{timesheet_id}/payslip.pdf')
async def download_payslip(request: Request, timesheet_id: UUID) -> Response:
    actor = await require_actor(request)
    ensure_can_export_payroll(actor)
    db = get_db_from_request(request)
    row = await db.fetchrow(
        """
        SELECT payslip_file_name, payslip_pdf
          FROM payroll_payment_records
         WHERE timesheet_id = $1
        """,
        timesheet_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail='ხელფასის ფურცელი ვერ მოიძებნა')
    response = Response(content=row['payslip_pdf'], media_type='application/pdf')
    response.headers['Content-Disposition'] = f"inline; filename={row['payslip_file_name']}"
    return response


@app.put('/system/config/{legal_entity_id}')
async def upsert_system_config(request: Request, legal_entity_id: UUID, payload: SystemConfigUpsertRequest) -> dict[str, str]:
    actor = await require_actor(request)
    ensure_permission(actor, 'employee.manage')
    if actor.legal_entity_id != legal_entity_id and 'ADMIN' not in actor.role_codes:
        raise HTTPException(status_code=403, detail='სხვა იურიდიული ერთეულის კონფიგურაციის შეცვლა აკრძალულია')
    db = get_db_from_request(request)
    if payload.trade_name:
        await db.execute(
            'UPDATE legal_entities SET trade_name = $2, updated_at = now() WHERE id = $1',
            legal_entity_id,
            payload.trade_name,
        )
    await db.execute(
        """
        INSERT INTO entity_system_config (
            legal_entity_id, logo_url, logo_text, primary_color, standalone_chat_url,
            allowed_web_punch_ips, geofence_latitude, geofence_longitude, geofence_radius_meters, updated_at
        )
        VALUES ($1, $2, $3, $4, $5, $6::text[], $7, $8, $9, now())
        ON CONFLICT (legal_entity_id) DO UPDATE
           SET logo_url = EXCLUDED.logo_url,
               logo_text = EXCLUDED.logo_text,
               primary_color = EXCLUDED.primary_color,
               standalone_chat_url = EXCLUDED.standalone_chat_url,
               allowed_web_punch_ips = EXCLUDED.allowed_web_punch_ips,
               geofence_latitude = EXCLUDED.geofence_latitude,
               geofence_longitude = EXCLUDED.geofence_longitude,
               geofence_radius_meters = EXCLUDED.geofence_radius_meters,
               updated_at = now()
        """,
        legal_entity_id,
        payload.logo_url,
        payload.logo_text,
        payload.primary_color,
        payload.standalone_chat_url,
        payload.allowed_web_punch_ips,
        payload.geofence_latitude,
        payload.geofence_longitude,
        payload.geofence_radius_meters,
    )
    await db.execute(
        """
        INSERT INTO entity_operation_settings (
            legal_entity_id, late_arrival_threshold_minutes,
            require_asset_clearance_for_final_payroll, default_onboarding_course_id
        ) VALUES ($1, $2, $3, $4)
        ON CONFLICT (legal_entity_id) DO UPDATE
           SET late_arrival_threshold_minutes = EXCLUDED.late_arrival_threshold_minutes,
               require_asset_clearance_for_final_payroll = EXCLUDED.require_asset_clearance_for_final_payroll,
               default_onboarding_course_id = EXCLUDED.default_onboarding_course_id,
               updated_at = now()
        """,
        legal_entity_id,
        payload.late_arrival_threshold_minutes,
        payload.require_asset_clearance_for_final_payroll,
        payload.default_onboarding_course_id,
    )
    if payload.income_tax_rate is not None or payload.employee_pension_rate is not None:
        await db.execute(
            """
            UPDATE pay_policies
               SET income_tax_rate = coalesce($2, income_tax_rate),
                   employee_pension_rate = coalesce($3, employee_pension_rate),
                   updated_at = now()
             WHERE legal_entity_id = $1
            """,
            legal_entity_id,
            payload.income_tax_rate,
            payload.employee_pension_rate,
        )
    return {'status': 'saved'}


@app.put('/system/tenants/{legal_entity_id}/subscriptions')
async def update_tenant_subscriptions(
    request: Request,
    legal_entity_id: UUID,
    payload: TenantSubscriptionUpdateRequest,
) -> dict[str, str]:
    actor = await require_actor(request)
    ensure_permission(actor, 'employee.manage')
    if actor.legal_entity_id != legal_entity_id and 'ADMIN' not in actor.role_codes:
        raise HTTPException(status_code=403, detail='სხვა იურიდიული ერთეულის გამოწერის შეცვლა აკრძალულია')
    db = get_db_from_request(request)
    await db.execute(
        """
        INSERT INTO tenant_subscriptions (
            legal_entity_id, attendance_enabled, payroll_enabled, ats_enabled, chat_enabled,
            assets_enabled, org_chart_enabled, performance_enabled, updated_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, now())
        ON CONFLICT (legal_entity_id) DO UPDATE
           SET attendance_enabled = EXCLUDED.attendance_enabled,
               payroll_enabled = EXCLUDED.payroll_enabled,
               ats_enabled = EXCLUDED.ats_enabled,
               chat_enabled = EXCLUDED.chat_enabled,
               assets_enabled = EXCLUDED.assets_enabled,
               org_chart_enabled = EXCLUDED.org_chart_enabled,
               performance_enabled = EXCLUDED.performance_enabled,
               updated_at = now()
        """,
        legal_entity_id,
        payload.attendance_enabled,
        payload.payroll_enabled,
        payload.ats_enabled,
        payload.chat_enabled,
        payload.assets_enabled,
        payload.org_chart_enabled,
        payload.performance_enabled,
    )
    return {'status': 'saved'}


@app.post('/system/tenants', status_code=status.HTTP_201_CREATED)
async def create_legal_entity(request: Request, payload: LegalEntityCreateRequest) -> dict[str, str]:
    actor = await require_actor(request)
    ensure_permission(actor, 'employee.manage')
    if 'ADMIN' not in actor.role_codes:
        raise HTTPException(status_code=403, detail='კომპანიის დამატება მხოლოდ superadmin მომხმარებლისთვის არის ხელმისაწვდომი')

    db = get_db_from_request(request)
    legal_name = _clean_text(payload.legal_name)
    trade_name = _clean_text(payload.trade_name)
    tax_id = _clean_text(payload.tax_id)
    admin_username = _clean_text(payload.admin_username)
    admin_email = _validate_email(payload.admin_email)
    admin_first_name = _clean_text(payload.admin_first_name) or 'Company'
    admin_last_name = _clean_text(payload.admin_last_name) or 'Administrator'
    host = _clean_text(payload.host.lower() if payload.host else None)
    subdomain = _clean_text(payload.subdomain.lower() if payload.subdomain else None)
    resolved_host = host or (f'{subdomain}.test.hr' if subdomain else None)

    if legal_name is None or trade_name is None or tax_id is None or admin_username is None:
        raise HTTPException(status_code=422, detail='კომპანიის დასამატებლად შეავსეთ legal name, trade name, tax id და admin username')

    existing_username = await db.fetchval('SELECT 1 FROM auth_identities WHERE username = $1', admin_username)
    if existing_username:
        raise HTTPException(status_code=409, detail='ეს admin username უკვე დაკავებულია')

    tx = await db.transaction()
    try:
        legal_entity_id = await tx.connection.fetchval(
            """
            INSERT INTO legal_entities (legal_name, trade_name, tax_id, timezone, currency_code, city, country_code)
            VALUES ($1, $2, $3, 'Asia/Tbilisi', 'GEL', 'Tbilisi', 'GE')
            RETURNING id
            """,
            legal_name,
            trade_name,
            tax_id,
        )
        department_id = await tx.connection.fetchval(
            """
            INSERT INTO departments (legal_entity_id, code, name_en, name_ka)
            VALUES ($1, 'ADMIN', 'Administration', 'ადმინისტრაცია')
            RETURNING id
            """,
            legal_entity_id,
        )
        job_role_id = await tx.connection.fetchval(
            """
            INSERT INTO job_roles (legal_entity_id, code, title_en, title_ka, is_managerial)
            VALUES ($1, 'COMPANY_ADMIN', 'Company Admin', 'კომპანიის ადმინისტრატორი', true)
            RETURNING id
            """,
            legal_entity_id,
        )
        pay_policy_id = await tx.connection.fetchval(
            """
            INSERT INTO pay_policies (
                legal_entity_id, code, name, payroll_cycle, standard_weekly_hours,
                overtime_multiplier, night_bonus_multiplier, holiday_multiplier,
                employee_pension_rate, income_tax_rate
            )
            VALUES ($1, 'STD', 'Standard Georgia Policy', 'monthly', 40.00, 1.25, 0.20, 2.00, 0.02, 0.20)
            RETURNING id
            """,
            legal_entity_id,
        )
        employee_id = await tx.connection.fetchval(
            """
            INSERT INTO employees (
                legal_entity_id, employee_number, personal_number, first_name, last_name, email,
                department_id, job_role_id, hire_date, employment_status
            )
            VALUES ($1, 'ADM-0001', NULL, $2, $3, $4, $5, $6, current_date, 'active')
            RETURNING id
            """,
            legal_entity_id,
            admin_first_name,
            admin_last_name,
            admin_email,
            department_id,
            job_role_id,
        )
        await tx.connection.execute(
            """
            INSERT INTO employee_compensation (employee_id, policy_id, effective_from, base_salary, is_pension_participant)
            VALUES ($1, $2, current_date, 0, false)
            """,
            employee_id,
            pay_policy_id,
        )
        tenant_admin_role_id = await _ensure_access_role(
            tx.connection,
            code='TENANT_ADMIN',
            name_en='Tenant Administrator',
            name_ka='კომპანიის ადმინისტრატორი',
            description='Full tenant-level access without platform-wide cross-tenant override',
            permission_codes=TENANT_ADMIN_PERMISSIONS,
        )
        if tenant_admin_role_id is None:
            raise HTTPException(status_code=500, detail='ADMIN role ვერ მოიძებნა')
        await tx.connection.execute(
            """
            INSERT INTO employee_access_roles (employee_id, access_role_id, assigned_by_employee_id)
            VALUES ($1, $2, $1)
            ON CONFLICT DO NOTHING
            """,
            employee_id,
            tenant_admin_role_id,
        )
        await tx.connection.execute(
            """
            INSERT INTO auth_identities (employee_id, username, password_hash, is_active)
            VALUES ($1, $2, $3, true)
            """,
            employee_id,
            admin_username,
            hash_password(payload.admin_password),
        )
        await tx.connection.execute(
            """
            INSERT INTO entity_operation_settings (legal_entity_id, late_arrival_threshold_minutes, require_asset_clearance_for_final_payroll)
            VALUES ($1, 15, true)
            ON CONFLICT (legal_entity_id) DO NOTHING
            """,
            legal_entity_id,
        )
        await tx.connection.execute(
            """
            INSERT INTO entity_system_config (
                legal_entity_id, logo_url, logo_text, primary_color, standalone_chat_url,
                allowed_web_punch_ips, geofence_latitude, geofence_longitude, geofence_radius_meters
            )
            VALUES ($1, NULL, 'HR', '#0F172A', NULL, ARRAY[]::text[], NULL, NULL, NULL)
            ON CONFLICT (legal_entity_id) DO NOTHING
            """,
            legal_entity_id,
        )
        await tx.connection.execute(
            """
            INSERT INTO tenant_subscriptions (
                legal_entity_id, attendance_enabled, payroll_enabled, ats_enabled, chat_enabled,
                assets_enabled, org_chart_enabled, performance_enabled
            )
            VALUES ($1, true, true, true, true, true, true, true)
            ON CONFLICT (legal_entity_id) DO NOTHING
            """,
            legal_entity_id,
        )
        if resolved_host:
            domain_id = await tx.connection.fetchval(
                """
                INSERT INTO tenant_domains (legal_entity_id, host, subdomain, is_primary, is_active)
                VALUES ($1, $2, $3, true, true)
                RETURNING id
                """,
                legal_entity_id,
                resolved_host,
                subdomain,
            )
        else:
            domain_id = None
        await tx.commit()
    except PostgresError as exc:
        await tx.rollback()
        raise HTTPException(status_code=409, detail=_db_error_message(exc)) from exc
    except Exception:
        await tx.rollback()
        raise

    return {
        'legal_entity_id': str(legal_entity_id),
        'employee_id': str(employee_id),
        'domain_id': str(domain_id) if domain_id else '',
        'admin_username': admin_username,
    }


@app.post('/system/tenants/{legal_entity_id}/domains', status_code=status.HTTP_201_CREATED)
async def create_tenant_domain(
    request: Request,
    legal_entity_id: UUID,
    payload: TenantDomainUpsertRequest,
) -> dict[str, str]:
    actor = await require_actor(request)
    ensure_permission(actor, 'employee.manage')
    if actor.legal_entity_id != legal_entity_id and 'ADMIN' not in actor.role_codes:
        raise HTTPException(status_code=403, detail='სხვა იურიდიული ერთეულის დომენის შეცვლა აკრძალულია')
    db = get_db_from_request(request)
    domain_id = await db.fetchval(
        """
        INSERT INTO tenant_domains (legal_entity_id, host, subdomain, is_primary, is_active)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id
        """,
        legal_entity_id,
        payload.host.strip().lower(),
        _clean_text(payload.subdomain.lower() if payload.subdomain else None),
        payload.is_primary,
        payload.is_active,
    )
    if payload.is_primary:
        await db.execute(
            """
            UPDATE tenant_domains
               SET is_primary = false,
                   updated_at = now()
             WHERE legal_entity_id = $1
               AND id <> $2
            """,
            legal_entity_id,
            domain_id,
        )
    return {'domain_id': str(domain_id)}


@app.put('/system/tenants/domains/{domain_id}')
async def update_tenant_domain(
    request: Request,
    domain_id: UUID,
    payload: TenantDomainUpsertRequest,
) -> dict[str, str]:
    actor = await require_actor(request)
    ensure_permission(actor, 'employee.manage')
    db = get_db_from_request(request)
    legal_entity_id = await db.fetchval('SELECT legal_entity_id FROM tenant_domains WHERE id = $1', domain_id)
    if legal_entity_id is None:
        raise HTTPException(status_code=404, detail='კომპანიის დომენი ვერ მოიძებნა')
    if legal_entity_id != actor.legal_entity_id and 'ADMIN' not in actor.role_codes:
        raise HTTPException(status_code=403, detail='სხვა იურიდიული ერთეულის დომენის შეცვლა აკრძალულია')
    await db.execute(
        """
        UPDATE tenant_domains
           SET host = $2,
               subdomain = $3,
               is_primary = $4,
               is_active = $5,
               updated_at = now()
         WHERE id = $1
        """,
        domain_id,
        payload.host.strip().lower(),
        _clean_text(payload.subdomain.lower() if payload.subdomain else None),
        payload.is_primary,
        payload.is_active,
    )
    if payload.is_primary:
        await db.execute(
            """
            UPDATE tenant_domains
               SET is_primary = false,
                   updated_at = now()
             WHERE legal_entity_id = $1
               AND id <> $2
            """,
            legal_entity_id,
            domain_id,
        )
    return {'status': 'updated'}


@app.put('/rbac/employees/{employee_id}/roles')
async def update_employee_roles(request: Request, employee_id: UUID, payload: EmployeeRoleUpdateRequest) -> dict[str, str]:
    actor = await require_actor(request)
    ensure_permission(actor, 'employee.manage')
    db = get_db_from_request(request)
    employee_entity_id = await db.fetchval('SELECT legal_entity_id FROM employees WHERE id = $1', employee_id)
    if employee_entity_id is None:
        raise HTTPException(status_code=404, detail='თანამშრომელი ვერ მოიძებნა')
    if employee_entity_id != actor.legal_entity_id and 'ADMIN' not in actor.role_codes:
        raise HTTPException(status_code=403, detail='სხვა იურიდიულ ერთეულზე როლების მინიჭება აკრძალულია')
    requested_codes = list(dict.fromkeys(code.upper() for code in payload.role_codes))
    role_rows = await db.fetch('SELECT id, upper(code::text) AS code FROM access_roles WHERE upper(code::text) = ANY($1::text[])', requested_codes)
    if len(role_rows) != len(requested_codes):
        raise HTTPException(status_code=400, detail='ერთი ან რამდენიმე role კოდი არასწორია')
    tx = await db.transaction()
    try:
        await tx.connection.execute('DELETE FROM employee_access_roles WHERE employee_id = $1', employee_id)
        if role_rows:
            await tx.connection.executemany(
                """
                INSERT INTO employee_access_roles (employee_id, access_role_id, assigned_by_employee_id)
                VALUES ($1, $2, $3)
                """,
                [(employee_id, row['id'], actor.employee_id) for row in role_rows],
            )
        await tx.commit()
    except Exception:
        await tx.rollback()
        raise
    return {'status': 'updated'}


@app.post('/employees/{employee_id}/separation')
async def record_separation(request: Request, employee_id: UUID, payload: SeparationRecordRequest) -> dict[str, str]:
    actor = await require_actor(request)
    ensure_permission(actor, 'employee.manage')
    db = get_db_from_request(request)
    await db.execute(
        """
        INSERT INTO employee_separations (
            employee_id, separation_date, reason_category, reason_details, eligible_rehire, created_by_employee_id
        ) VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (employee_id) DO UPDATE
           SET separation_date = EXCLUDED.separation_date,
               reason_category = EXCLUDED.reason_category,
               reason_details = EXCLUDED.reason_details,
               eligible_rehire = EXCLUDED.eligible_rehire,
               created_by_employee_id = EXCLUDED.created_by_employee_id
        """,
        employee_id,
        payload.separation_date,
        payload.reason_category,
        payload.reason_details,
        payload.eligible_rehire,
        actor.employee_id,
    )
    await db.execute(
        "UPDATE employees SET termination_date = $2, employment_status = 'terminated', updated_at = now() WHERE id = $1",
        employee_id,
        payload.separation_date,
    )
    return {'status': 'recorded'}


@app.post('/ess/leave/sick', status_code=status.HTTP_201_CREATED)
async def create_sick_leave_request(
    request: Request,
    start_date: date = Form(...),
    end_date: date = Form(...),
    reason: str = Form(...),
    doctor_note: UploadFile | None = File(default=None),
) -> dict[str, str]:
    actor = await require_actor(request)
    db = get_db_from_request(request)
    if end_date < start_date:
        raise HTTPException(status_code=400, detail='დასრულების თარიღი დაწყების თარიღზე ადრე ვერ იქნება')
    leave_type_id = await db.fetchval(
        """
        SELECT id
          FROM leave_types
         WHERE legal_entity_id = $1
           AND upper(code::text) IN ('SICK', 'SICK_LEAVE', 'BULLETIN')
           AND is_active = true
         ORDER BY code
         LIMIT 1
        """,
        actor.legal_entity_id,
    )
    if leave_type_id is None:
        raise HTTPException(status_code=400, detail='ბიულეტინის ტიპი ჯერ კონფიგურირებული არ არის')
    manager_employee_id = await db.fetchval(
        'SELECT coalesce(line_manager_id, manager_employee_id) FROM employees WHERE id = $1',
        actor.employee_id,
    )
    requested_days = await get_db_from_request(request).fetchval(
        """
        SELECT count(*)
          FROM generate_series($1::date, $2::date, interval '1 day') AS d(day)
         WHERE extract(isodow FROM d.day) < 6
        """,
        start_date,
        end_date,
    )
    attachment_url = None
    attachment_size = None
    if doctor_note and doctor_note.filename:
        attachment_url, attachment_size = await _store_upload(doctor_note, LEAVE_UPLOADS_DIR, 'doctor_note')
    leave_request_id = await db.fetchval(
        """
        INSERT INTO leave_requests (
            employee_id, leave_type_id, manager_employee_id, start_date, end_date,
            requested_days, reason, status, approval_stage, attachment_url
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, 'submitted', 'manager_pending', $8)
        RETURNING id
        """,
        actor.employee_id,
        leave_type_id,
        manager_employee_id,
        start_date,
        end_date,
        Decimal(str(requested_days or 0)),
        reason.strip(),
        attachment_url,
    )
    if attachment_url:
        await db.execute(
            """
            INSERT INTO leave_request_files (leave_request_id, file_name, file_url, content_type, file_size)
            VALUES ($1, $2, $3, $4, $5)
            """,
            leave_request_id,
            _safe_file_name(doctor_note.filename or 'doctor_note.bin'),
            attachment_url,
            doctor_note.content_type,
            attachment_size,
        )
    await send_leave_approval_request(db, leave_request_id)
    return {'leave_request_id': str(leave_request_id)}


@app.post('/timesheets/{employee_id}/{year}/{month}/recalculate')
async def recalculate_monthly_timesheet(request: Request, employee_id: UUID, year: int, month: int) -> dict[str, object]:
    actor = await require_actor(request)
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail='თვე უნდა იყოს 1-დან 12-მდე')
    db = get_db_from_request(request)
    target_department_id = await db.fetchval('SELECT department_id FROM employees WHERE id = $1', employee_id)
    ensure_can_view_attendance(actor, employee_id, target_department_id)
    result = await build_monthly_timesheet_from_db(db, employee_id, year, month)
    await persist_monthly_timesheet(db, result, actor.employee_id)
    return {
        'employee_id': str(result.employee_id),
        'year': year,
        'month': month,
        'total_minutes': result.total_minutes,
        'night_minutes': result.night_minutes,
        'holiday_minutes': result.holiday_minutes,
        'overtime_minutes': result.overtime_minutes,
        'incomplete_session_count': result.incomplete_session_count,
        'gross_pay': str(result.payroll.gross_pay),
        'employee_pension_amount': str(result.payroll.employee_pension_amount),
        'income_tax_amount': str(result.payroll.income_tax_amount),
        'net_pay': str(result.payroll.net_pay),
    }


@app.get('/timesheets/{employee_id}/{year}/{month}/export.xlsx')
async def export_employee_timesheet_xlsx(request: Request, employee_id: UUID, year: int, month: int) -> Response:
    actor = await require_actor(request)
    db = get_db_from_request(request)
    target_department_id = await db.fetchval('SELECT department_id FROM employees WHERE id = $1', employee_id)
    ensure_can_view_attendance(actor, employee_id, target_department_id)
    result = await build_monthly_timesheet_from_db(db, employee_id, year, month)
    await persist_monthly_timesheet(db, result, actor.employee_id)
    rows = [
        ['თანამშრომელი', str(result.employee_id)],
        ['წელი', str(year)],
        ['თვე', str(month)],
        ['ნამუშევარი საათები', f'{round(result.total_minutes / 60, 2)}'],
        ['ზეგანაკვეთური საათები', f'{round(result.overtime_minutes / 60, 2)}'],
        ['ღამის საათები', f'{round(result.night_minutes / 60, 2)}'],
        ['დღესასწაულის საათები', f'{round(result.holiday_minutes / 60, 2)}'],
        ['მთლიანი ხელფასი', str(result.payroll.gross_pay)],
        ['დასარიცხი გადასახადი', str(result.payroll.income_tax_amount)],
        ['გასაცემი ხელფასი', str(result.payroll.net_pay)],
    ]
    workbook = _build_minimal_xlsx('Timesheet', ['ველი', 'მნიშვნელობა'], rows)
    response = Response(
        content=workbook,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response.headers['Content-Disposition'] = f'attachment; filename=timesheet_{year}_{month:02d}.xlsx'
    return response


@app.get('/timesheets/{employee_id}/{year}/{month}/export.pdf')
async def export_employee_timesheet_pdf(request: Request, employee_id: UUID, year: int, month: int) -> Response:
    actor = await require_actor(request)
    db = get_db_from_request(request)
    target_department_id = await db.fetchval('SELECT department_id FROM employees WHERE id = $1', employee_id)
    ensure_can_view_attendance(actor, employee_id, target_department_id)
    result = await build_monthly_timesheet_from_db(db, employee_id, year, month)
    await persist_monthly_timesheet(db, result, actor.employee_id)
    pdf = _build_simple_table_pdf(
        'Georgian Timesheet',
        [
            f'Employee: {result.employee_id}',
            f'Period: {year}-{month:02d}',
            f'Total hours: {round(result.total_minutes / 60, 2)}',
            f'Overtime: {round(result.overtime_minutes / 60, 2)}',
            f'Night: {round(result.night_minutes / 60, 2)}',
            f'Holiday: {round(result.holiday_minutes / 60, 2)}',
            f'Gross pay: {result.payroll.gross_pay}',
            f'Income tax: {result.payroll.income_tax_amount}',
            f'Net pay: {result.payroll.net_pay}',
        ],
    )
    response = Response(content=pdf, media_type='application/pdf')
    response.headers['Content-Disposition'] = f'inline; filename=timesheet_{year}_{month:02d}.pdf'
    return response


@app.get('/attendance/review-queue')
async def attendance_review_queue(request: Request) -> list[dict[str, object]]:
    actor = await require_actor(request)
    ensure_permission(actor, 'attendance.review')
    db = get_db_from_request(request)
    if actor.has('attendance.read_all'):
        rows = await db.fetch(
            """
            SELECT arf.id, arf.employee_id, e.employee_number, e.first_name, e.last_name,
                   arf.work_date, arf.flag_type, arf.severity, arf.details, arf.raised_at
              FROM attendance_review_flags arf
              JOIN employees e ON e.id = arf.employee_id
             WHERE arf.resolved_at IS NULL
             ORDER BY arf.raised_at DESC
            """
        )
    else:
        rows = await db.fetch(
            """
            SELECT arf.id, arf.employee_id, e.employee_number, e.first_name, e.last_name,
                   arf.work_date, arf.flag_type, arf.severity, arf.details, arf.raised_at
              FROM attendance_review_flags arf
              JOIN employees e ON e.id = arf.employee_id
             WHERE arf.resolved_at IS NULL
               AND e.department_id = ANY($1::uuid[])
             ORDER BY arf.raised_at DESC
            """,
            list(actor.managed_department_ids),
        )
    return [dict(row) for row in rows]


@app.get('/dashboard/summary')
async def dashboard_summary(request: Request) -> dict[str, object]:
    actor = await require_actor(request)
    db = get_db_from_request(request)
    headcounts = await db.fetchrow(
        """
        SELECT
            count(*) FILTER (WHERE employment_status = 'active') AS active_employees,
            count(*) FILTER (WHERE employment_status = 'terminated') AS terminated_employees,
            count(*) AS total_employees
          FROM employees
         WHERE legal_entity_id = $1
        """,
        actor.legal_entity_id,
    )
    open_flags = await db.fetchval(
        """
        SELECT count(*)
          FROM attendance_review_flags arf
          JOIN employees e ON e.id = arf.employee_id
         WHERE e.legal_entity_id = $1
           AND arf.resolved_at IS NULL
        """,
        actor.legal_entity_id,
    )
    open_leave = await db.fetchval(
        """
        SELECT count(*)
          FROM leave_requests lr
          JOIN employees e ON e.id = lr.employee_id
         WHERE e.legal_entity_id = $1
           AND lr.status = 'submitted'
        """,
        actor.legal_entity_id,
    )
    devices_online = await db.fetchval(
        """
        SELECT count(*)
          FROM device_registry
         WHERE legal_entity_id = $1
           AND is_active = true
           AND last_seen_at >= now() - interval '10 minutes'
        """,
        actor.legal_entity_id,
    )
    return {
        'legal_entity_id': str(actor.legal_entity_id),
        'active_employees': int(headcounts['active_employees'] or 0),
        'terminated_employees': int(headcounts['terminated_employees'] or 0),
        'total_employees': int(headcounts['total_employees'] or 0),
        'open_attendance_flags': int(open_flags or 0),
        'pending_leave_approvals': int(open_leave or 0),
        'devices_online': int(devices_online or 0),
    }


@app.get('/payroll/export/{year}/{month}')
async def payroll_export(request: Request, year: int, month: int) -> Response:
    actor = await require_actor(request)
    try:
        ensure_can_export_payroll(actor)
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail='თვე უნდა იყოს 1-დან 12-მდე')
    db = get_db_from_request(request)
    employee_rows = await db.fetch(
        """
        SELECT id, employee_number, first_name || ' ' || last_name AS full_name, termination_date
          FROM employees
         WHERE legal_entity_id = $1
           AND employment_status IN ('active', 'suspended', 'terminated')
         ORDER BY employee_number
        """,
        actor.legal_entity_id,
    )
    results = []
    employee_index: dict[UUID, tuple[str, str]] = {}
    skipped_for_holds = 0
    for employee in employee_rows:
        active_hold = await db.fetchval(
            'SELECT 1 FROM final_payroll_holds WHERE employee_id = $1 AND resolved_at IS NULL',
            employee['id'],
        )
        if employee['termination_date'] is not None and active_hold:
            skipped_for_holds += 1
            continue
        result = await build_monthly_timesheet_from_db(db, employee['id'], year, month)
        await persist_monthly_timesheet(db, result, actor.employee_id)
        results.append(result)
        employee_index[employee['id']] = (employee['employee_number'], employee['full_name'])
    rows = payroll_export_rows(results, employee_index)

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            'employee_number',
            'full_name',
            'year',
            'month',
            'total_hours',
            'night_hours',
            'overtime_hours',
            'holiday_hours',
            'base_salary',
            'overtime_pay',
            'night_pay',
            'holiday_pay',
            'gross_pay',
            'employee_pension_amount',
            'income_tax_amount',
            'net_pay',
        ],
    )
    writer.writeheader()
    writer.writerows(rows)
    response = Response(content=buffer.getvalue(), media_type='text/csv')
    response.headers['Content-Disposition'] = f'attachment; filename=payroll_{year}_{month:02d}.csv'
    response.headers['X-Skipped-Final-Payroll-Holds'] = str(skipped_for_holds)
    return response
