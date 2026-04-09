import type { TenantBranding } from '../tenantBranding'

export function CompanyBadge(props: { branding: TenantBranding; compact?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <div
        className="flex h-11 w-11 items-center justify-center rounded-2xl text-sm font-bold text-white"
        style={{ background: `linear-gradient(135deg, ${props.branding.primaryColor} 0%, #7c6cf7 100%)` }}
      >
        {props.branding.logoText}
      </div>
      {!props.compact ? (
        <div>
          <p className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Enterprise HRMS</p>
          <p className="mt-1 text-lg font-semibold tracking-[-0.02em] text-slate-900">{props.branding.companyName}</p>
        </div>
      ) : null}
    </div>
  )
}
