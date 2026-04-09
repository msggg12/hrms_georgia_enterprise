"""
Connect Suite: Dahua CGI (digest), Google Calendar hooks, Slack/email webhooks — incremental integration layer.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel

from .api_support import require_actor

INTEGRATIONS_ROUTER = APIRouter(prefix='/integrations', tags=['integrations'])


class DahuaFacePushResponse(BaseModel):
    status: str
    detail: str


@INTEGRATIONS_ROUTER.post('/dahua/face-push', response_model=DahuaFacePushResponse)
async def dahua_face_push(
    request: Request,
    device_id: str | None = Query(default=None),
    photo: UploadFile = File(...),
) -> DahuaFacePushResponse:
    """Queue JPG for Dahua terminal (digest CGI to face.uploadRecord / similar) — wire device registry host in production."""
    await require_actor(request)
    content_type = (photo.content_type or '').lower()
    if content_type not in {'image/jpeg', 'image/jpg'} and not (photo.filename or '').lower().endswith(('.jpg', '.jpeg')):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='JPG სავალდებულოა')
    _ = await photo.read()
    return DahuaFacePushResponse(
        status='queued',
        detail=f'სახის ფაილი მიღებულია; device_id={device_id or "default"} — დააკავშირეთ device registry-ში მითითებული host CGI-სთვის.',
    )


@INTEGRATIONS_ROUTER.get('/google-calendar/oauth-url')
async def google_calendar_oauth_url(request: Request, employee_id: str | None = None) -> dict[str, str]:
    """Placeholder OAuth URL for per-employee Google Calendar sync (upcoming ↔ HRMS shifts)."""
    await require_actor(request)
    base = 'https://accounts.google.com/o/oauth2/v2/auth'
    return {
        'authorize_url': f'{base}?client_id=CONFIGURE_ME&redirect_uri=/integrations/google-calendar/callback&response_type=code&scope=https://www.googleapis.com/auth/calendar',
        'employee_id': employee_id or '',
    }


@INTEGRATIONS_ROUTER.get('/webhooks')
async def get_webhook_settings(request: Request) -> dict[str, Any]:
    """Slack + email template placeholders (KA localization) — persist via system config UI later."""
    await require_actor(request)
    return {'slack_webhook_url': None, 'email_template_locale': 'ka', 'note': 'Configure in Settings → integrations rollout.'}
