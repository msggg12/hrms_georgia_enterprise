import { ExternalLink, MessagesSquare } from 'lucide-react'

import { ka } from '../i18n/ka'
import type { TeamChatConfig } from '../types'

export function TeamChat(props: { config: TeamChatConfig | null }) {
  const linked = Boolean(props.config?.linked && props.config?.channel_url)

  return (
    <article className="panel-card overflow-hidden p-0">
      <div className="flex items-center justify-between border-b border-slate-200 px-6 py-5">
        <div>
          <h2 className="text-xl font-semibold text-slate-950">{ka.teamChat}</h2>
          <p className="mt-1 text-sm text-slate-500">
            {props.config?.mattermost_username ? `${ka.linkedAs}: @${props.config.mattermost_username}` : ka.chatNotLinked}
          </p>
        </div>
        <div className="brand-soft rounded-lg border border-slate-200 p-3">
          <MessagesSquare className="h-5 w-5" />
        </div>
      </div>

      {linked ? (
        <div className="p-5">
          <div className="mb-4 flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
            <span>{ka.currentChannel}: {props.config?.preferred_channel}</span>
            <a className="inline-flex items-center gap-2 font-semibold text-action-600" href={props.config?.channel_url ?? '#'} target="_blank" rel="noreferrer">
              {ka.openMattermost}
              <ExternalLink className="h-4 w-4" />
            </a>
          </div>
          <iframe
            title="Mattermost"
            src={props.config?.channel_url ?? undefined}
            className="h-[720px] w-full rounded-xl border border-slate-200"
            referrerPolicy="strict-origin-when-cross-origin"
          />
        </div>
      ) : (
        <div className="p-5">
          <div className="rounded-xl border border-dashed border-slate-300 px-6 py-16 text-center text-slate-500">
            {ka.chatNotLinked}
          </div>
        </div>
      )}
    </article>
  )
}
