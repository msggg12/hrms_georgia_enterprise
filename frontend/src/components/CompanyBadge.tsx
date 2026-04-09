import type { TenantBranding } from '../tenantBranding'

export function CompanyBadge(props: { branding: TenantBranding; compact?: boolean }) {
  return (
    <div className="flex min-w-0 items-center gap-3 py-0.5">
      <div
        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl text-sm font-bold text-white shadow-sm"
        style={{ background: `linear-gradient(135deg, ${props.branding.primaryColor} 0%, #3b82f6 100%)` }}
      >
        {props.branding.logoText}
      </div>
      {!props.compact ? (
        <div className="min-w-0 leading-tight">
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-400">HRMS Georgia Enterprise</p>
          <p className="mt-1 truncate text-[15px] font-semibold tracking-[-0.02em] text-slate-50">{props.branding.companyName}</p>
        </div>
      ) : null}
    </div>
  )
}
