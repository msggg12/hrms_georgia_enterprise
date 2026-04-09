from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from .api_support import get_db_from_request, require_actor
from .mattermost_integration import notify_it_prepare_workstation
from .rbac import ensure_permission

ATS_ROUTER = APIRouter(prefix='/ats', tags=['ats-onboarding'])


def q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class QuizOptionCreate(BaseModel):
    option_key: str
    option_text: str
    is_correct: bool = False


class QuizQuestionCreate(BaseModel):
    question_text: str
    options: list[QuizOptionCreate]


class CourseModuleCreate(BaseModel):
    module_type: Literal['video', 'quiz']
    title: str
    description: str | None = None
    media_url: str | None = None
    duration_seconds: int | None = Field(default=None, ge=0)
    passing_score: int | None = Field(default=None, ge=0, le=100)
    questions: list[QuizQuestionCreate] = Field(default_factory=list)


class OnboardingCourseCreateRequest(BaseModel):
    legal_entity_id: UUID
    code: str
    name_en: str
    name_ka: str
    description: str | None = None
    modules: list[CourseModuleCreate]


class HirePayload(BaseModel):
    hire_date: date
    pay_policy_id: UUID
    base_salary: Decimal = Field(ge=0)
    personal_number: str | None = None
    email: EmailStr | None = None
    mobile_phone: str | None = None
    manager_employee_id: UUID | None = None
    onboarding_course_id: UUID | None = None
    access_role_codes: list[str] = Field(default_factory=lambda: ['EMPLOYEE'])


class MoveCandidateStageRequest(BaseModel):
    stage_code: str
    comment: str | None = None
    hire_payload: HirePayload | None = None


class QuizSubmitRequest(BaseModel):
    selected_option_ids: list[UUID]


class VideoCompletionRequest(BaseModel):
    watched_seconds: int = Field(default=0, ge=0)


async def _generate_employee_number(conn: object, legal_entity_id: UUID) -> str:
    next_serial = await conn.fetchval(
        """
        SELECT coalesce(
            max(NULLIF(regexp_replace(employee_number, '\\D', '', 'g'), '')::bigint),
            0
        ) + 1
          FROM employees
         WHERE legal_entity_id = $1
        """,
        legal_entity_id,
    )
    return f"EMP-{datetime.now().year}-{int(next_serial):05d}"


async def _assign_course(conn: object, employee_id: UUID, course_id: UUID, assigned_by_employee_id: UUID | None) -> UUID:
    assignment_id = await conn.fetchval(
        """
        INSERT INTO onboarding_course_assignments (employee_id, course_id, assigned_by_employee_id, due_at, status)
        VALUES ($1, $2, $3, now() + interval '14 days', 'assigned')
        RETURNING id
        """,
        employee_id,
        course_id,
        assigned_by_employee_id,
    )
    modules = await conn.fetch(
        'SELECT id FROM onboarding_course_modules WHERE course_id = $1 ORDER BY sort_order',
        course_id,
    )
    await conn.executemany(
        """
        INSERT INTO onboarding_assignment_modules (assignment_id, module_id, status)
        VALUES ($1, $2, 'assigned')
        """,
        [(assignment_id, module['id']) for module in modules],
    )
    return assignment_id


async def _hire_candidate(db, application_id: UUID, payload: HirePayload, actor_employee_id: UUID) -> dict[str, str]:
    tx = await db.transaction()
    try:
        application = await tx.connection.fetchrow(
            """
            SELECT ca.id, c.first_name, c.last_name, c.email AS candidate_email, c.phone,
                   c.id AS candidate_id,
                   jp.legal_entity_id, jp.department_id, jp.job_role_id,
                   ca.current_stage_id
              FROM candidate_applications ca
              JOIN candidates c ON c.id = ca.candidate_id
              JOIN job_postings jp ON jp.id = ca.job_posting_id
             WHERE ca.id = $1
            """,
            application_id,
        )
        if application is None:
            raise HTTPException(status_code=404, detail='Candidate application not found')

        employee_number = await _generate_employee_number(tx.connection, application['legal_entity_id'])
        employee_id = await tx.connection.fetchval(
            """
            INSERT INTO employees (
                legal_entity_id, employee_number, personal_number, first_name, last_name,
                email, mobile_phone, department_id, job_role_id, manager_employee_id,
                hire_date, employment_status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'active')
            RETURNING id
            """,
            application['legal_entity_id'],
            employee_number,
            payload.personal_number,
            application['first_name'],
            application['last_name'],
            payload.email or application['candidate_email'],
            payload.mobile_phone or application['phone'],
            application['department_id'],
            application['job_role_id'],
            payload.manager_employee_id,
            payload.hire_date,
        )
        await tx.connection.execute(
            """
            INSERT INTO employee_compensation (
                employee_id, policy_id, effective_from, base_salary, is_pension_participant
            ) VALUES ($1, $2, $3, $4, true)
            """,
            employee_id,
            payload.pay_policy_id,
            payload.hire_date,
            q2(payload.base_salary),
        )
        role_rows = await tx.connection.fetch(
            'SELECT id FROM access_roles WHERE code = ANY($1::citext[])',
            payload.access_role_codes,
        )
        await tx.connection.executemany(
            """
            INSERT INTO employee_access_roles (employee_id, access_role_id, assigned_by_employee_id)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
            """,
            [(employee_id, row['id'], actor_employee_id) for row in role_rows],
        )
        await tx.connection.execute(
            """
            UPDATE candidate_applications
               SET application_status = 'hired', decided_at = now(), updated_at = now()
             WHERE id = $1
            """,
            application_id,
        )
        course_id = payload.onboarding_course_id or await tx.connection.fetchval(
            'SELECT default_onboarding_course_id FROM entity_operation_settings WHERE legal_entity_id = $1',
            application['legal_entity_id'],
        )
        assignment_id = None
        if course_id is not None:
            assignment_id = await _assign_course(tx.connection, employee_id, course_id, actor_employee_id)
        await tx.commit()
    except Exception:
        await tx.rollback()
        raise

    await notify_it_prepare_workstation(db, employee_id)
    return {'employee_id': str(employee_id), 'onboarding_assignment_id': str(assignment_id) if assignment_id else ''}


@ATS_ROUTER.post('/courses', status_code=201)
async def create_onboarding_course(request: Request, payload: OnboardingCourseCreateRequest) -> dict[str, str]:
    actor = await require_actor(request)
    ensure_permission(actor, 'recruitment.manage')
    if payload.legal_entity_id != actor.legal_entity_id and 'ADMIN' not in actor.role_codes:
        raise HTTPException(status_code=403, detail='Cross-entity course creation is not allowed')
    video_count = sum(1 for module in payload.modules if module.module_type == 'video')
    quiz_modules = [module for module in payload.modules if module.module_type == 'quiz']
    if video_count < 3 or not quiz_modules:
        raise HTTPException(status_code=400, detail='An onboarding course must include at least 3 videos and 1 quiz module')
    for module in quiz_modules:
        if not module.questions:
            raise HTTPException(status_code=400, detail='Quiz modules require at least one question')
        for question in module.questions:
            if len([option for option in question.options if option.is_correct]) != 1:
                raise HTTPException(status_code=400, detail='Each quiz question must have exactly one correct option')

    db = get_db_from_request(request)
    tx = await db.transaction()
    try:
        course_id = await tx.connection.fetchval(
            """
            INSERT INTO onboarding_courses (legal_entity_id, code, name_en, name_ka, description)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            payload.legal_entity_id,
            payload.code,
            payload.name_en,
            payload.name_ka,
            payload.description,
        )
        for index, module in enumerate(payload.modules, start=1):
            module_id = await tx.connection.fetchval(
                """
                INSERT INTO onboarding_course_modules (
                    course_id, sort_order, module_type, title, description, media_url, duration_seconds, passing_score
                ) VALUES ($1, $2, $3::onboarding_module_type, $4, $5, $6, $7, $8)
                RETURNING id
                """,
                course_id,
                index,
                module.module_type,
                module.title,
                module.description,
                module.media_url,
                module.duration_seconds,
                module.passing_score,
            )
            if module.module_type == 'quiz':
                for question_index, question in enumerate(module.questions, start=1):
                    question_id = await tx.connection.fetchval(
                        """
                        INSERT INTO onboarding_quiz_questions (module_id, sort_order, question_text)
                        VALUES ($1, $2, $3)
                        RETURNING id
                        """,
                        module_id,
                        question_index,
                        question.question_text,
                    )
                    await tx.connection.executemany(
                        """
                        INSERT INTO onboarding_quiz_options (question_id, option_key, option_text, is_correct)
                        VALUES ($1, $2, $3, $4)
                        """,
                        [
                            (question_id, option.option_key, option.option_text, option.is_correct)
                            for option in question.options
                        ],
                    )
        await tx.commit()
    except Exception:
        await tx.rollback()
        raise
    return {'course_id': str(course_id)}


@ATS_ROUTER.get('/kanban/{legal_entity_id}')
async def recruitment_kanban(request: Request, legal_entity_id: UUID) -> dict[str, list[dict[str, object]]]:
    actor = await require_actor(request)
    ensure_permission(actor, 'recruitment.read')
    if actor.legal_entity_id != legal_entity_id and 'ADMIN' not in actor.role_codes:
        raise HTTPException(status_code=403, detail='Cross-entity recruitment access is not allowed')
    db = get_db_from_request(request)
    rows = await db.fetch(
        """
        SELECT job_posting_id, posting_code, title_en, title_ka, posting_status, board_column,
               total_candidates, hired_candidates
          FROM v_ats_kanban_board
         WHERE legal_entity_id = $1
         ORDER BY posting_code
        """,
        legal_entity_id,
    )
    board = {'Draft': [], 'Published': [], 'Interview': [], 'Offer': [], 'Hired': []}
    for row in rows:
        board[row['board_column']].append(dict(row))
    return board


@ATS_ROUTER.post('/applications/{application_id}/move')
async def move_application_stage(request: Request, application_id: UUID, payload: MoveCandidateStageRequest) -> dict[str, str]:
    actor = await require_actor(request)
    ensure_permission(actor, 'recruitment.manage')
    db = get_db_from_request(request)
    stage = await db.fetchrow(
        """
        SELECT cps.id, cps.code::text AS code, cps.is_hired, cps.is_rejected, cps.is_terminal,
               jp.legal_entity_id
          FROM candidate_applications ca
          JOIN job_postings jp ON jp.id = ca.job_posting_id
          JOIN candidate_pipeline_stages cps ON cps.legal_entity_id = jp.legal_entity_id
         WHERE ca.id = $1
           AND upper(cps.code::text) = upper($2)
         LIMIT 1
        """,
        application_id,
        payload.stage_code,
    )
    if stage is None:
        raise HTTPException(status_code=404, detail='Target stage not found for this legal entity')
    if actor.legal_entity_id != stage['legal_entity_id'] and 'ADMIN' not in actor.role_codes:
        raise HTTPException(status_code=403, detail='Cross-entity stage updates are not allowed')
    if stage['is_hired'] and payload.hire_payload is None:
        raise HTTPException(status_code=400, detail='hire_payload is required when moving a candidate to HIRED')

    tx = await db.transaction()
    try:
        await tx.connection.execute(
            """
            UPDATE candidate_applications
               SET current_stage_id = $2,
                   application_status = CASE
                       WHEN $3 THEN 'hired'
                       WHEN $4 THEN 'rejected'
                       ELSE application_status
                   END,
                   decided_at = CASE WHEN $5 THEN now() ELSE decided_at END,
                   updated_at = now()
             WHERE id = $1
            """,
            application_id,
            stage['id'],
            stage['is_hired'],
            stage['is_rejected'],
            stage['is_terminal'],
        )
        await tx.connection.execute(
            """
            INSERT INTO candidate_pipeline (application_id, stage_id, moved_by_employee_id, comment)
            VALUES ($1, $2, $3, $4)
            """,
            application_id,
            stage['id'],
            actor.employee_id,
            payload.comment,
        )
        await tx.commit()
    except Exception:
        await tx.rollback()
        raise

    result: dict[str, str] = {'stage_code': stage['code']}
    if stage['is_hired']:
        result.update(await _hire_candidate(db, application_id, payload.hire_payload, actor.employee_id))
    return result


@ATS_ROUTER.post('/assignments/{assignment_id}/modules/{module_id}/complete-video')
async def complete_video_module(request: Request, assignment_id: UUID, module_id: UUID, payload: VideoCompletionRequest) -> dict[str, object]:
    actor = await require_actor(request)
    db = get_db_from_request(request)
    row = await db.fetchrow(
        """
        SELECT oca.employee_id, ocm.module_type::text AS module_type
          FROM onboarding_course_assignments oca
          JOIN onboarding_assignment_modules oam ON oam.assignment_id = oca.id
          JOIN onboarding_course_modules ocm ON ocm.id = oam.module_id
         WHERE oca.id = $1
           AND ocm.id = $2
        """,
        assignment_id,
        module_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail='Assignment module not found')
    if actor.employee_id != row['employee_id'] and not actor.has('recruitment.manage'):
        raise HTTPException(status_code=403, detail='You can only complete your own onboarding modules')
    if row['module_type'] != 'video':
        raise HTTPException(status_code=400, detail='This endpoint is only for video modules')
    await db.execute(
        """
        UPDATE onboarding_assignment_modules
           SET watched_seconds = greatest(watched_seconds, $3),
               status = 'completed',
               completed_at = now(),
               updated_at = now()
         WHERE assignment_id = $1
           AND module_id = $2
        """,
        assignment_id,
        module_id,
        payload.watched_seconds,
    )
    await _refresh_assignment_status(db, assignment_id)
    return {'assignment_id': str(assignment_id), 'module_id': str(module_id), 'status': 'completed'}


@ATS_ROUTER.post('/assignments/{assignment_id}/modules/{module_id}/submit-quiz')
async def submit_quiz(request: Request, assignment_id: UUID, module_id: UUID, payload: QuizSubmitRequest) -> dict[str, object]:
    actor = await require_actor(request)
    db = get_db_from_request(request)
    assignment = await db.fetchrow(
        'SELECT employee_id FROM onboarding_course_assignments WHERE id = $1',
        assignment_id,
    )
    if assignment is None:
        raise HTTPException(status_code=404, detail='Assignment not found')
    if actor.employee_id != assignment['employee_id'] and not actor.has('recruitment.manage'):
        raise HTTPException(status_code=403, detail='You can only submit your own onboarding quiz')

    questions = await db.fetch(
        """
        SELECT oqq.id AS question_id, oqo.id AS option_id, oqo.is_correct
          FROM onboarding_quiz_questions oqq
          JOIN onboarding_quiz_options oqo ON oqo.question_id = oqq.id
         WHERE oqq.module_id = $1
        """,
        module_id,
    )
    if not questions:
        raise HTTPException(status_code=404, detail='Quiz module has no questions')
    correct_option_ids = {row['option_id'] for row in questions if row['is_correct']}
    question_ids = {row['question_id'] for row in questions}
    total_questions = len(question_ids)
    selected_option_ids = set(payload.selected_option_ids)
    correct_answers = len(correct_option_ids & selected_option_ids)
    score = int((Decimal(correct_answers) / Decimal(total_questions) * Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    passing_score = await db.fetchval('SELECT coalesce(passing_score, 100) FROM onboarding_course_modules WHERE id = $1', module_id)
    passed = score >= passing_score
    await db.execute(
        """
        UPDATE onboarding_assignment_modules
           SET score_percent = $3,
               status = CASE WHEN $4 THEN 'completed'::onboarding_assignment_status ELSE 'in_progress'::onboarding_assignment_status END,
               completed_at = CASE WHEN $4 THEN now() ELSE completed_at END,
               updated_at = now()
         WHERE assignment_id = $1
           AND module_id = $2
        """,
        assignment_id,
        module_id,
        score,
        passed,
    )
    await _refresh_assignment_status(db, assignment_id)
    return {'assignment_id': str(assignment_id), 'module_id': str(module_id), 'score': score, 'passed': passed}


async def _refresh_assignment_status(db, assignment_id: UUID) -> None:
    counts = await db.fetchrow(
        """
        SELECT count(*) AS total_count,
               count(*) FILTER (WHERE status = 'completed') AS completed_count
          FROM onboarding_assignment_modules
         WHERE assignment_id = $1
        """,
        assignment_id,
    )
    total_count = counts['total_count']
    completed_count = counts['completed_count']
    if total_count and total_count == completed_count:
        await db.execute(
            """
            UPDATE onboarding_course_assignments
               SET status = 'completed', completed_at = now(), updated_at = now()
             WHERE id = $1
            """,
            assignment_id,
        )
    else:
        await db.execute(
            """
            UPDATE onboarding_course_assignments
               SET status = 'in_progress', updated_at = now()
             WHERE id = $1
            """,
            assignment_id,
        )


@ATS_ROUTER.post('/seed-default-stages/{legal_entity_id}')
async def seed_default_stages(request: Request, legal_entity_id: UUID) -> dict[str, str]:
    actor = await require_actor(request)
    ensure_permission(actor, 'recruitment.manage')
    if actor.legal_entity_id != legal_entity_id and 'ADMIN' not in actor.role_codes:
        raise HTTPException(status_code=403, detail='Cross-entity stage seeding is not allowed')
    db = get_db_from_request(request)
    await db.execute('SELECT hrms.seed_default_candidate_pipeline_stages($1)', legal_entity_id)
    return {'status': 'seeded'}
