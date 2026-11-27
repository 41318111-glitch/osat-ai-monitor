import React from 'react'
import { AlertOctagon, CheckCircle2, Info, Terminal } from 'lucide-react'

const LEVEL_STYLES = {
  CRITICAL: {
    icon: AlertOctagon,
    color: 'text-rose-400',
    border: 'border-rose-500/30 bg-rose-950/20',
  },
  WARNING: {
    icon: AlertOctagon,
    color: 'text-amber-400',
    border: 'border-amber-500/30 bg-amber-950/20',
  },
  SUCCESS: {
    icon: CheckCircle2,
    color: 'text-emerald-400',
    border: 'border-emerald-500/25 bg-emerald-950/15',
  },
  INFO: {
    icon: Info,
    color: 'text-cyan-400',
    border: 'border-slate-800 bg-slate-950/50',
  },
}

export default function EventLogPanel({ logs }) {
  return (
    <div className="flex flex-col rounded-xl border border-slate-800 bg-slate-900/85 p-4 backdrop-blur-md">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-bold text-white">
          <Terminal className="h-4 w-4 text-cyan-400" />
          即時排程與異常日誌 (Telemetry Log)
        </h2>
        <span className="font-mono text-[11px] text-slate-400">{logs.length} 筆紀錄</span>
      </div>

      <div className="mt-3 max-h-[300px] space-y-2 overflow-y-auto pr-1">
        {logs.map((log) => {
          const style = LEVEL_STYLES[log.level] || LEVEL_STYLES.INFO
          const Icon = style.icon
          return (
            <div
              key={log.id}
              className={`flex items-start gap-2 rounded-lg border px-2.5 py-2 text-xs ${style.border}`}
            >
              <Icon className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${style.color}`} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2 text-[10px] text-slate-400">
                  <span className="font-mono font-semibold text-slate-300">[{log.category}]</span>
                  <span className="font-mono">{log.created_at.split(' ')[1] || log.created_at}</span>
                </div>
                <p className="mt-0.5 leading-relaxed text-slate-200">{log.message}</p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
