from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, Request

from .auth import decode_token
from .db import Database
from .rbac import ActorContext, AuthorizationError, load_actor_context


def get_db_from_request(request: Request) -> Database:
    db = getattr(request.app.state, 'db', None)
    if db is None:
        raise HTTPException(status_code=503, detail='Database is not initialized')
    return db


def _bearer_token(request: Request) -> str | None:
    authorization = request.headers.get('Authorization', '')
    if not authorization.lower().startswith('bearer '):
        return None
    return authorization[7:].strip() or None


def get_request_tenant_legal_entity_id(request: Request) -> UUID | None:
    raw_tenant_legal_entity_id = getattr(request.state, 'tenant_legal_entity_id', None)
    if not raw_tenant_legal_entity_id:
        return None
    return UUID(str(raw_tenant_legal_entity_id))


async def require_actor(request: Request) -> ActorContext:
    token = _bearer_token(request)
    if token:
        payload = decode_token(token, expected_type='access')
        raw_employee_id = str(payload.get('sub') or '')
    else:
        raw_employee_id = request.headers.get('X-Employee-ID')
    if not raw_employee_id:
        raise HTTPException(status_code=401, detail='Bearer token or X-Employee-ID header is required')
    try:
        employee_id = UUID(raw_employee_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail='Actor identifier must be a UUID') from exc

    db = get_db_from_request(request)
    try:
        actor = await load_actor_context(db, employee_id)
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if token:
        token_legal_entity = payload.get('legal_entity_id')
        if token_legal_entity and str(actor.legal_entity_id) != str(token_legal_entity):
            raise HTTPException(status_code=403, detail='Token legal_entity_id does not match the actor')
    request_tenant_legal_entity_id = get_request_tenant_legal_entity_id(request)
    if request_tenant_legal_entity_id and actor.legal_entity_id != request_tenant_legal_entity_id:
        raise HTTPException(status_code=403, detail='ამ დომენზე ამ კომპანიის მონაცემებზე წვდომა არ გაქვთ')
    return actor
