import type { CSSProperties } from 'react'
import { useState } from 'react'

import { DndContext, DragEndEvent, DragOverlay, DragStartEvent, useDraggable, useDroppable } from '@dnd-kit/core'
import { BriefcaseBusiness, MapPin, UserRound } from 'lucide-react'

import { ka } from '../i18n/ka'
import type { AtsBoardData, AtsCard } from '../types'
import { classNames, formatDate, formatMoney, initials } from '../utils'

type AtsBoardProps = {
  board: AtsBoardData | null
  busy: boolean
  onMoveCard: (applicationId: string, targetStage: string) => Promise<void>
}

function CandidateCard(props: { candidate: AtsCard }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `candidate-${props.candidate.id}`,
    data: { applicationId: props.candidate.id, currentStage: props.candidate.stage_code, candidate: props.candidate }
  })
  const style: CSSProperties | undefined = transform
    ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` }
    : undefined

  return (
    <article
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      className={classNames(
        'rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition',
        isDragging && 'opacity-60'
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-slate-900 text-xs font-bold text-white">
            {initials(props.candidate.first_name, props.candidate.last_name)}
          </div>
          <div>
            <h3 className="font-semibold text-slate-950">{props.candidate.first_name} {props.candidate.last_name}</h3>
            <p className="text-xs text-slate-500">{props.candidate.job_title}</p>
          </div>
        </div>
        {props.candidate.actual_stage_code !== props.candidate.stage_code ? (
          <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-600">
            {props.candidate.actual_stage_code}
          </span>
        ) : null}
      </div>
      <div className="mt-4 grid gap-2 text-sm text-slate-600">
        <div className="flex items-center gap-2">
          <BriefcaseBusiness className="h-4 w-4 text-action-600" />
          <span>{props.candidate.posting_code} - {props.candidate.department_name ?? '-'}</span>
        </div>
        <div className="flex items-center gap-2">
          <UserRound className="h-4 w-4 text-action-600" />
          <span>{ka.candidateOwner}: {props.candidate.owner_name || '-'}</span>
        </div>
        <div className="flex items-center gap-2">
          <MapPin className="h-4 w-4 text-action-600" />
          <span>{props.candidate.city ?? props.candidate.email ?? props.candidate.phone ?? '-'}</span>
        </div>
      </div>
      <div className="mt-4 flex items-center justify-between text-xs text-slate-500">
        <span>{ka.appliedAt}: {formatDate(props.candidate.applied_at)}</span>
        <span>{props.candidate.salary_max ?? props.candidate.salary_min ? formatMoney(props.candidate.salary_max ?? props.candidate.salary_min ?? 0) : '-'}</span>
      </div>
    </article>
  )
}

function StageColumn(props: { code: string; title: string; candidates: AtsCard[] }) {
  const { isOver, setNodeRef } = useDroppable({
    id: `stage-${props.code}`,
    data: { stageCode: props.code }
  })
  return (
    <section ref={setNodeRef} className={classNames('rounded-xl border border-slate-200 bg-slate-50 p-4', isOver && 'border-action-300 bg-action-50')}>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-slate-950">{props.title}</h3>
          <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{props.candidates.length}</p>
        </div>
      </div>
      <div className="space-y-3">
        {props.candidates.map((candidate) => (
          <CandidateCard key={candidate.id} candidate={candidate} />
        ))}
        {!props.candidates.length ? (
          <div className="rounded-lg border border-dashed border-slate-300 px-4 py-10 text-center text-sm text-slate-500">
            {ka.noCandidates}
          </div>
        ) : null}
      </div>
    </section>
  )
}

export function AtsBoard(props: AtsBoardProps) {
  const [activeCard, setActiveCard] = useState<AtsCard | null>(null)

  function handleDragStart(event: DragStartEvent) {
    setActiveCard((event.active.data.current?.candidate as AtsCard | null) ?? null)
  }

  async function handleDragEnd(event: DragEndEvent) {
    const applicationId = event.active.data.current?.applicationId as string | undefined
    const currentStage = event.active.data.current?.currentStage as string | undefined
    const targetStage = (event.over?.data.current?.stageCode as string | undefined) ?? event.over?.id?.toString().replace('stage-', '')
    setActiveCard(null)
    if (!applicationId || !targetStage || targetStage === currentStage) {
      return
    }
    await props.onMoveCard(applicationId, targetStage)
  }

  return (
    <article className="panel-card">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-slate-950">{ka.recruitmentPipeline}</h2>
          <p className="mt-1 text-sm text-slate-500">{ka.dragToAssign}</p>
        </div>
        {props.busy ? <div className="rounded-full border border-action-200 bg-action-50 px-3 py-1 text-xs font-semibold text-action-600">Syncing</div> : null}
      </div>

      <DndContext onDragStart={handleDragStart} onDragEnd={(event) => void handleDragEnd(event)}>
        <div className="grid gap-4 xl:grid-cols-4">
          {props.board?.columns.map((column) => (
            <StageColumn key={column.code} code={column.code} title={column.name_ka} candidates={props.board?.cards[column.code] ?? []} />
          ))}
        </div>
        <DragOverlay>
          {activeCard ? <div className="w-[320px]"><CandidateCard candidate={activeCard} /></div> : null}
        </DragOverlay>
      </DndContext>
    </article>
  )
}
