from __future__ import annotations

import os
from dataclasses import dataclass


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def _as_int(value: str | None, default: int) -> int:
    if value is None or value == '':
        return default
    return int(value)


def _as_list(value: str | None) -> tuple[str, ...]:
    if value is None or value.strip() == '':
        return ()
    return tuple(item.strip() for item in value.split(',') if item.strip())


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    public_base_url: str
    cors_origins: tuple[str, ...]
    enable_background_jobs: bool
    enable_device_workers: bool
    enable_ops_workers: bool
    enable_node_heartbeat: bool
    node_code: str
    node_role: str
    node_region: str
    redis_url: str
    jwt_secret: str
    jwt_algorithm: str
    access_token_ttl_minutes: int
    refresh_token_ttl_minutes: int
    late_arrival_scan_interval_seconds: int
    celebration_scan_interval_seconds: int
    burnout_scan_interval_seconds: int
    offboarding_scan_interval_seconds: int
    monitoring_heartbeat_interval_seconds: int
    device_ingestion_interval_seconds: int
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_from_email: str
    smtp_use_tls: bool
    password_reset_ttl_minutes: int
    invite_ttl_minutes: int

    @classmethod
    def from_env(cls) -> 'Settings':
        enable_background_jobs = _as_bool(os.environ.get('ENABLE_BACKGROUND_JOBS'), default=False)
        return cls(
            database_url=os.environ.get('DATABASE_URL', '').strip(),
            public_base_url=os.environ.get('PUBLIC_BASE_URL', '').rstrip('/'),
            cors_origins=_as_list(os.environ.get('CORS_ORIGINS')),
            enable_background_jobs=enable_background_jobs,
            enable_device_workers=_as_bool(os.environ.get('ENABLE_DEVICE_WORKERS'), default=enable_background_jobs),
            enable_ops_workers=_as_bool(os.environ.get('ENABLE_OPS_WORKERS'), default=enable_background_jobs),
            enable_node_heartbeat=_as_bool(os.environ.get('ENABLE_NODE_HEARTBEAT'), default=True),
            node_code=os.environ.get('NODE_CODE', 'hrms-node'),
            node_role=os.environ.get('NODE_ROLE', 'api'),
            node_region=os.environ.get('NODE_REGION', 'georgia'),
            redis_url=os.environ.get('REDIS_URL', 'redis://redis:6379/0').strip(),
            jwt_secret=os.environ.get('JWT_SECRET', 'change-me-before-production').strip(),
            jwt_algorithm=os.environ.get('JWT_ALGORITHM', 'HS256').strip(),
            access_token_ttl_minutes=_as_int(os.environ.get('ACCESS_TOKEN_TTL_MINUTES'), 60),
            refresh_token_ttl_minutes=_as_int(os.environ.get('REFRESH_TOKEN_TTL_MINUTES'), 10080),
            late_arrival_scan_interval_seconds=_as_int(os.environ.get('LATE_ARRIVAL_SCAN_INTERVAL_SECONDS'), 600),
            celebration_scan_interval_seconds=_as_int(os.environ.get('CELEBRATION_SCAN_INTERVAL_SECONDS'), 3600),
            burnout_scan_interval_seconds=_as_int(os.environ.get('BURNOUT_SCAN_INTERVAL_SECONDS'), 21600),
            offboarding_scan_interval_seconds=_as_int(os.environ.get('OFFBOARDING_SCAN_INTERVAL_SECONDS'), 3600),
            monitoring_heartbeat_interval_seconds=_as_int(os.environ.get('MONITORING_HEARTBEAT_INTERVAL_SECONDS'), 60),
            device_ingestion_interval_seconds=_as_int(os.environ.get('DEVICE_INGESTION_INTERVAL_SECONDS'), 30),
            smtp_host=os.environ.get('SMTP_HOST', '').strip(),
            smtp_port=_as_int(os.environ.get('SMTP_PORT'), 587),
            smtp_username=os.environ.get('SMTP_USERNAME', '').strip(),
            smtp_password=os.environ.get('SMTP_PASSWORD', '').strip(),
            smtp_from_email=os.environ.get('SMTP_FROM_EMAIL', 'hrms@localhost').strip(),
            smtp_use_tls=_as_bool(os.environ.get('SMTP_USE_TLS'), default=True),
            password_reset_ttl_minutes=_as_int(os.environ.get('PASSWORD_RESET_TTL_MINUTES'), 30),
            invite_ttl_minutes=_as_int(os.environ.get('INVITE_TTL_MINUTES'), 1440),
        )


settings = Settings.from_env()
