from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from fastapi import APIRouter, HTTPException, Request, status
from passlib.context import CryptContext
from pydantic import BaseModel, Field

from .config import settings
from .db import Database
from .mail_engine import send_and_log_email
from .rbac import load_actor_context

AUTH_ROUTER = APIRouter(prefix='/auth', tags=['auth'])
PASSWORD_CONTEXT = CryptContext(schemes=['pbkdf2_sha256'], deprecated='auto')


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class PasswordResetRequest(BaseModel):
    username_or_email: str = Field(min_length=1, max_length=255)


class PasswordResetConfirmRequest(BaseModel):
    reset_token: str = Field(min_length=24)
    new_password: str = Field(min_length=10, max_length=255)


class InviteAcceptRequest(BaseModel):
    invite_token: str = Field(min_length=24)
    new_password: str = Field(min_length=10, max_length=255)


def hash_password(password: str) -> str:
    return PASSWORD_CONTEXT.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return PASSWORD_CONTEXT.verify(password, password_hash)


def _token_payload(
    *,
    employee_id: UUID,
    legal_entity_id: UUID,
    username: str,
    token_type: str,
    ttl_minutes: int,
) -> dict[str, Any]:
    issued_at = datetime.now(UTC)
    return {
        'sub': str(employee_id),
        'legal_entity_id': str(legal_entity_id),
        'username': username,
        'type': token_type,
        'iat': int(issued_at.timestamp()),
        'exp': int((issued_at + timedelta(minutes=ttl_minutes)).timestamp()),
    }


def create_access_token(*, employee_id: UUID, legal_entity_id: UUID, username: str) -> str:
    payload = _token_payload(
        employee_id=employee_id,
        legal_entity_id=legal_entity_id,
        username=username,
        token_type='access',
        ttl_minutes=settings.access_token_ttl_minutes,
    )
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(*, employee_id: UUID, legal_entity_id: UUID, username: str) -> str:
    payload = _token_payload(
        employee_id=employee_id,
        legal_entity_id=legal_entity_id,
        username=username,
        token_type='refresh',
        ttl_minutes=settings.refresh_token_ttl_minutes,
    )
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_type: str = 'access') -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid or expired token') from exc
    if payload.get('type') != expected_type:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unexpected token type')
    return payload


async def _authenticate_identity(db: Database, username: str, password: str) -> dict[str, Any]:
    row = await db.fetchrow(
        """
        SELECT ai.id,
               ai.employee_id,
               ai.username,
               ai.password_hash,
               ai.is_active,
               e.legal_entity_id,
               e.email,
               e.employment_status
          FROM auth_identities ai
          JOIN employees e ON e.id = ai.employee_id
         WHERE ai.username = $1
            OR e.email = $1
            OR e.employee_number = $1
         LIMIT 1
        """,
        username,
    )
    if row is None or not row['is_active'] or row['employment_status'] not in {'active', 'suspended'}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid credentials')
    if not verify_password(password, row['password_hash']):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid credentials')
    return dict(row)


def _request_tenant_legal_entity_id(request: Request) -> UUID | None:
    raw_tenant_legal_entity_id = getattr(request.state, 'tenant_legal_entity_id', None)
    if not raw_tenant_legal_entity_id:
        return None
    return UUID(str(raw_tenant_legal_entity_id))


async def _token_bundle(db: Database, *, employee_id: UUID, legal_entity_id: UUID, username: str) -> dict[str, Any]:
    actor = await load_actor_context(db, employee_id)
    access_token = create_access_token(
        employee_id=employee_id,
        legal_entity_id=legal_entity_id,
        username=username,
    )
    refresh_token = create_refresh_token(
        employee_id=employee_id,
        legal_entity_id=legal_entity_id,
        username=username,
    )
    return {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'token_type': 'bearer',
        'expires_in': settings.access_token_ttl_minutes * 60,
        'employee': {
            'employee_id': str(actor.employee_id),
            'legal_entity_id': str(actor.legal_entity_id),
            'department_id': str(actor.department_id) if actor.department_id else None,
            'role_codes': sorted(actor.role_codes),
            'permissions': sorted(actor.permissions),
        },
    }


@AUTH_ROUTER.post('/login')
async def login(request: Request, payload: LoginRequest) -> dict[str, Any]:
    db: Database = request.app.state.db
    identity = await _authenticate_identity(db, payload.username.strip(), payload.password)
    request_tenant_legal_entity_id = _request_tenant_legal_entity_id(request)
    if request_tenant_legal_entity_id and request_tenant_legal_entity_id != identity['legal_entity_id']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='ამ დომენზე სხვა კომპანიის მომხმარებელი ვერ შევა')
    await db.execute('UPDATE auth_identities SET last_login_at = now(), updated_at = now() WHERE id = $1', identity['id'])
    return await _token_bundle(
        db,
        employee_id=identity['employee_id'],
        legal_entity_id=identity['legal_entity_id'],
        username=identity['username'],
    )


@AUTH_ROUTER.post('/refresh')
async def refresh(request: Request, payload: RefreshRequest) -> dict[str, Any]:
    db: Database = request.app.state.db
    token_payload = decode_token(payload.refresh_token, expected_type='refresh')
    employee_id = UUID(str(token_payload['sub']))
    legal_entity_id = UUID(str(token_payload['legal_entity_id']))
    request_tenant_legal_entity_id = _request_tenant_legal_entity_id(request)
    if request_tenant_legal_entity_id and request_tenant_legal_entity_id != legal_entity_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Refresh token belongs to another tenant')
    username = str(token_payload.get('username') or employee_id)
    return await _token_bundle(
        db,
        employee_id=employee_id,
        legal_entity_id=legal_entity_id,
        username=username,
    )


@AUTH_ROUTER.get('/me')
async def me(request: Request) -> dict[str, Any]:
    from .api_support import require_actor

    actor = await require_actor(request)
    return {
        'employee_id': str(actor.employee_id),
        'legal_entity_id': str(actor.legal_entity_id),
        'department_id': str(actor.department_id) if actor.department_id else None,
        'role_codes': sorted(actor.role_codes),
        'permissions': sorted(actor.permissions),
        'managed_department_ids': [str(dep_id) for dep_id in sorted(actor.managed_department_ids, key=str)],
    }


@AUTH_ROUTER.post('/logout')
async def logout() -> dict[str, str]:
    return {'status': 'logged_out'}


@AUTH_ROUTER.post('/password-reset/request')
async def request_password_reset(request: Request, payload: PasswordResetRequest) -> dict[str, str]:
    db: Database = request.app.state.db
    identity = await db.fetchrow(
        """
        SELECT ai.id AS identity_id,
               ai.employee_id,
               ai.username,
               e.legal_entity_id,
               e.first_name,
               e.last_name,
               e.email
          FROM auth_identities ai
          JOIN employees e ON e.id = ai.employee_id
         WHERE ai.username = $1
            OR e.email = $1
         LIMIT 1
        """,
        payload.username_or_email.strip(),
    )
    if identity is None:
        return {'status': 'accepted'}
    request_tenant_legal_entity_id = _request_tenant_legal_entity_id(request)
    if request_tenant_legal_entity_id and request_tenant_legal_entity_id != identity['legal_entity_id']:
        return {'status': 'accepted'}
    if not identity['email']:
        return {'status': 'accepted'}
    if not settings.smtp_host:
        return {'status': 'accepted'}

    reset_token = secrets.token_urlsafe(32)
    await db.execute(
        """
        INSERT INTO password_reset_tokens (employee_id, identity_id, reset_token, expires_at)
        VALUES ($1, $2, $3, now() + make_interval(mins => $4))
        """,
        identity['employee_id'],
        identity['identity_id'],
        reset_token,
        settings.password_reset_ttl_minutes,
    )
    reset_link = f"{settings.public_base_url}/ux/app?reset_token={reset_token}"
    await send_and_log_email(
        db,
        legal_entity_id=identity['legal_entity_id'],
        event_type='password_reset',
        event_key=str(identity['employee_id']),
        to_email=identity['email'],
        subject='HRMS პაროლის აღდგენა',
        body_text=(
            f"{identity['first_name']} {identity['last_name']},\n\n"
            f"პაროლის აღსადგენად გამოიყენეთ ეს ბმული:\n{reset_link}\n\n"
            f"ბმული ვალიდურია {settings.password_reset_ttl_minutes} წუთის განმავლობაში."
        ),
        extra_payload={'employee_id': str(identity['employee_id'])},
    )
    return {'status': 'accepted'}


@AUTH_ROUTER.post('/password-reset/confirm')
async def confirm_password_reset(request: Request, payload: PasswordResetConfirmRequest) -> dict[str, str]:
    db: Database = request.app.state.db
    reset_row = await db.fetchrow(
        """
        SELECT id, employee_id, identity_id
          FROM password_reset_tokens
         WHERE reset_token = $1
           AND used_at IS NULL
           AND expires_at >= now()
         ORDER BY created_at DESC
         LIMIT 1
        """,
        payload.reset_token,
    )
    if reset_row is None:
        raise HTTPException(status_code=400, detail='პაროლის აღდგენის ბმული აღარ არის ვალიდური')
    await db.execute(
        'UPDATE auth_identities SET password_hash = $2, updated_at = now() WHERE id = $1',
        reset_row['identity_id'],
        hash_password(payload.new_password),
    )
    await db.execute('UPDATE password_reset_tokens SET used_at = now() WHERE id = $1', reset_row['id'])
    return {'status': 'reset'}


@AUTH_ROUTER.post('/invite/accept')
async def accept_invite(request: Request, payload: InviteAcceptRequest) -> dict[str, str]:
    db: Database = request.app.state.db
    invite = await db.fetchrow(
        """
        SELECT ai.id AS invite_id,
               ai.employee_id,
               ai.username
          FROM auth_invites ai
         WHERE ai.invite_token = $1
           AND ai.accepted_at IS NULL
           AND ai.expires_at >= now()
         ORDER BY ai.created_at DESC
         LIMIT 1
        """,
        payload.invite_token,
    )
    if invite is None:
        raise HTTPException(status_code=400, detail='ინვაიტის ბმული ვადაგასულია ან უკვე გამოყენებულია')
    await db.execute(
        """
        UPDATE auth_identities
           SET password_hash = $2,
               is_active = true,
               updated_at = now()
         WHERE employee_id = $1
        """,
        invite['employee_id'],
        hash_password(payload.new_password),
    )
    await db.execute('UPDATE auth_invites SET accepted_at = now(), updated_at = now() WHERE id = $1', invite['invite_id'])
    return {'status': 'accepted', 'username': invite['username']}
