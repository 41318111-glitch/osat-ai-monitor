import React from 'react'
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Cpu,
  Flame,
  Layers,
  PauseCircle,
  RotateCcw,
  Timer,
  Wrench,
} from 'lucide-react'

const STATUS_STYLE = {
  運行中: {
    border: 'border-emerald-500/35 hover:border-emerald-400/60',
    glow: 'shadow-[0_0_25px_-10px_rgba(16,185,129,0.45)]',
    badge: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40',
    dot: 'bg-emerald-400 animate-ping',
    dotSolid: 'bg-emerald-400',
    bar: 'from-cyan-500 via-emerald-400 to-teal-300',
  },
  閒置: {
    border: 'border-slate-700/80 hover:border-cyan-500/40',
    glow: 'shadow-none',
    badge: 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30',
    dot: 'hidden',
    dotSolid: 'bg-cyan-400',
    bar: 'from-slate-600 to-slate-500',
  },
  異常: {
    border: 'border-rose-500/70 hover:border-rose-400',
    glow: 'shadow-[0_0_32px_-8px_rgba(244,63,94,0.65)]',
    badge: 'bg-rose-500/20 text-rose-300 border-rose-500/50',
    dot: 'bg-rose-400 animate-ping',
    dotSolid: 'bg-rose-500',
    bar: 'from-rose-600 to-amber-500',
  },
}

export default function MachineCard({ machine, onRecover, onSimulateFault }) {
  const style = STATUS_STYLE[machine.status] || STATUS_STYLE['閒置']
  const isFault = machine.status === '異常'
  const isIdle = machine.status === '閒置'
  const isRunning = machine.status === '運行中'

  const tempColor =
    machine.core_temp >= 100
      ? 'text-rose-400'
      : machine.core_temp >= 87
        ? 'text-amber-300'
        : isIdle
          ? 'text-slate-400'
          : 'text-cyan-300'

  const yieldColor =
    machine.yield_rate < 90
      ? 'text-rose-400'
      : machine.yield_rate < 97.5
        ? 'text-amber-300'
        : 'text-emerald-300'

  return (
    <div
      className={`relative flex flex-col justify-between rounded-xl border bg-slate-900/85 p-3.5 backdrop-blur-md transition-all duration-300 ${style.border} ${style.glow}`}
    >
      {/* Top Row */}
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm font-bold tracking-tight text-white">
              {machine.id}
            </span>
            <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[10px] text-slate-400">
              {machine.bay}
            </span>
          </div>
          <p className="mt-0.5 text-[11px] text-slate-400">{machine.name}</p>
        </div>

        <span
          className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${style.badge}`}
        >
          <span className="relative flex h-2 w-2">
            <span className={`absolute inline-flex h-full w-full rounded-full opacity-75 ${style.dot}`} />
            <span className={`relative inline-flex h-2 w-2 rounded-full ${style.dotSolid}`} />
          </span>
          {machine.status}
        </span>
      </div>

      {/* Chip & Multi-site */}
      <div className="mt-3 rounded-lg border border-slate-800/90 bg-slate-950/65 p-2.5">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 min-w-0">
            <Cpu className="h-3.5 w-3.5 shrink-0 text-cyan-400" />
            <span className="truncate font-mono text-xs font-semibold text-slate-100">
              {machine.chip_model || '待命待機中 (Standby)'}
            </span>
          </div>
          <span
            className={`inline-flex shrink-0 items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[10px] font-medium ${
              machine.multi_site > 0
                ? 'border-indigo-500/40 bg-indigo-500/15 text-indigo-300'
                : 'border-slate-700 bg-slate-800/70 text-slate-400'
            }`}
          >
            <Layers className="h-2.5 w-2.5" />
            {machine.multi_site > 0 ? `${machine.multi_site}-Site` : '0-Site'}
          </span>
        </div>

        <div className="mt-1.5 flex items-center justify-between text-[11px] text-slate-400">
          <span className="font-mono truncate">
            Lot: <span className="text-slate-200">{machine.current_lot_id || '--'}</span>
          </span>
          <span className="inline-flex items-center gap-1 font-mono text-[11px]">
            <Timer className="h-3 w-3 text-slate-400" />
            {isIdle ? (
              <span className="text-cyan-300">立即可用</span>
            ) : isFault ? (
              <span className="text-rose-400">停機鎖定</span>
            ) : (
              <span className="text-amber-300">{machine.est_release_sec}s 釋出</span>
            )}
          </span>
        </div>
      </div>

      {/* Burn-In Progress */}
      <div className="mt-3">
        <div className="mb-1 flex items-center justify-between text-[11px]">
          <span className="flex items-center gap-1 text-slate-400">
            <Activity className="h-3 w-3 text-emerald-400" />
            預燒進度 (Burn-In)
          </span>
          <span className="font-mono font-semibold text-slate-200">
            {machine.burn_in_progress.toFixed(1)}%
          </span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
          <div
            className={`h-full rounded-full bg-gradient-to-r transition-all duration-500 ${style.bar}`}
            style={{ width: `${Math.min(100, Math.max(0, machine.burn_in_progress))}%` }}
          />
        </div>
      </div>

      {/* Core Temp & Yield */}
      <div className="mt-3 grid grid-cols-2 gap-2">
        <div className="rounded-lg border border-slate-800/80 bg-slate-950/50 px-2.5 py-1.5">
          <div className="flex items-center gap-1 text-[10px] text-slate-400">
            <Flame className="h-3 w-3 text-orange-400" />
            核心溫度
          </div>
          <div className={`mt-0.5 font-mono text-sm font-bold ${tempColor}`}>
            {machine.core_temp.toFixed(1)}°C
          </div>
        </div>
        <div className="rounded-lg border border-slate-800/80 bg-slate-950/50 px-2.5 py-1.5">
          <div className="flex items-center gap-1 text-[10px] text-slate-400">
            <CheckCircle2 className="h-3 w-3 text-emerald-400" />
            即時良率
          </div>
          <div className={`mt-0.5 font-mono text-sm font-bold ${yieldColor}`}>
            {isIdle ? '--' : `${machine.yield_rate.toFixed(2)}%`}
          </div>
        </div>
      </div>

      {/* Probe Card Compatibility */}
      <div className="mt-2.5 flex flex-wrap items-center gap-1 border-t border-slate-800/80 pt-2">
        <span className="text-[10px] text-slate-500">探針卡:</span>
        <span className="rounded border border-cyan-500/30 bg-cyan-500/10 px-1.5 py-0.5 font-mono text-[10px] font-medium text-cyan-300">
          {machine.probe_card}
        </span>
        {machine.compatible_probe_cards
          .filter((c) => c !== machine.probe_card)
          .map((card) => (
            <span
              key={card}
              className="rounded border border-slate-700/80 bg-slate-800/60 px-1.5 py-0.5 font-mono text-[10px] text-slate-400"
              title="相容支援之探針卡"
            >
              +{card}
            </span>
          ))}
      </div>

      {/* Anomaly Alert / Quick Action */}
      {isFault ? (
        <div className="mt-2.5 rounded-lg border border-rose-500/40 bg-rose-950/50 p-2">
          <div className="flex items-start gap-1.5 text-[11px] text-rose-200">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-rose-400" />
            <span className="leading-snug">{machine.anomaly_reason || '偵測到機台異常停機'}</span>
          </div>
          <button
            onClick={() => onRecover(machine.id)}
            className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-md border border-emerald-500/40 bg-emerald-500/15 px-2.5 py-1 text-xs font-medium text-emerald-300 transition hover:bg-emerald-500/25"
          >
            <Wrench className="h-3.5 w-3.5" />
            排除異常並復歸機台
          </button>
        </div>
      ) : (
        isRunning && (
          <button
            onClick={() => onSimulateFault(machine.id)}
            className="mt-2 flex items-center justify-center gap-1 rounded-md border border-slate-800 bg-slate-950/50 py-1 text-[11px] text-slate-400 transition hover:border-rose-500/40 hover:bg-rose-500/10 hover:text-rose-300"
          >
            <PauseCircle className="h-3 w-3" />
            模擬此機台異常
          </button>
        )
      )}
    </div>
  )
}
