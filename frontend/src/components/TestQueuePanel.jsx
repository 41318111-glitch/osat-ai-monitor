import React, { useState } from 'react'
import { ArrowRight, Clock, Flame, Plus, Sparkles } from 'lucide-react'

const CHIP_PRESETS = [
  { chip: 'NV-B200-AI', card: 'PC-HBM3E-16S', sites: 16, customer: 'NVIDIA' },
  { chip: 'GOOG-TPU-V6', card: 'PC-N3P-32S', sites: 32, customer: 'Google' },
  { chip: 'AMD-MI350X', card: 'PC-COWOS-8S', sites: 8, customer: 'AMD' },
  { chip: 'MTK-DIM-AI', card: 'PC-BGA-16S', sites: 16, customer: 'MediaTek' },
]

const STATUS_BADGE = {
  待排程: 'border-amber-500/40 bg-amber-500/15 text-amber-300',
  已預約排程: 'border-cyan-500/40 bg-cyan-500/15 text-cyan-300',
  '已排程-進行中': 'border-emerald-500/40 bg-emerald-500/15 text-emerald-300',
  已完成: 'border-slate-700 bg-slate-800/80 text-slate-400',
}

export default function TestQueuePanel({ queue, onAddLot, onSmartSchedule, scheduling }) {
  const [showAdd, setShowAdd] = useState(false)
  const [presetIdx, setPresetIdx] = useState(0)
  const [priority, setPriority] = useState('急件')
  const [waferQty, setWaferQty] = useState(25)

  const handleSubmit = async (e) => {
    e.preventDefault()
    const preset = CHIP_PRESETS[presetIdx]
    await onAddLot({
      customer: preset.customer,
      chip_model: preset.chip,
      required_probe_card: preset.card,
      priority,
      multi_site_req: preset.sites,
      wafer_qty: Number(waferQty) || 25,
      est_duration_sec: 85,
    })
    setShowAdd(false)
  }

  const urgentPending = queue.filter((q) => q.priority === '急件' && q.status === '待排程').length

  return (
    <div className="flex flex-col rounded-xl border border-slate-800 bg-slate-900/85 p-4 backdrop-blur-md">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 className="flex items-center gap-2 text-sm font-bold text-white">
            待測晶片佇列 (Test Queue)
            {urgentPending > 0 && (
              <span className="rounded-full bg-rose-500/20 px-2 py-0.5 font-mono text-xs text-rose-300 border border-rose-500/40">
                {urgentPending} 急件待派
              </span>
            )}
          </h2>
          <p className="mt-0.5 text-xs text-slate-400">
            依優先權與探針卡相容性自動匹配最快釋出機台
          </p>
        </div>

        <button
          onClick={() => setShowAdd((v) => !v)}
          className="inline-flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-800/80 px-2.5 py-1.5 text-xs font-medium text-slate-200 transition hover:border-cyan-500/50 hover:text-cyan-300"
        >
          <Plus className="h-3.5 w-3.5" />
          新增插單
        </button>
      </div>

      {showAdd && (
        <form
          onSubmit={handleSubmit}
          className="mt-3 space-y-2.5 rounded-lg border border-cyan-500/30 bg-slate-950/80 p-3"
        >
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-[11px] text-slate-400">晶片型號 / 探針卡</label>
              <select
                value={presetIdx}
                onChange={(e) => setPresetIdx(Number(e.target.value))}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-1.5 text-xs text-slate-100 focus:border-cyan-500 focus:outline-none"
              >
                {CHIP_PRESETS.map((p, idx) => (
                  <option key={p.chip} value={idx}>
                    {p.chip} ({p.card})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[11px] text-slate-400">優先等級</label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-1.5 text-xs text-slate-100 focus:border-cyan-500 focus:outline-none"
              >
                <option value="急件">急件 (Hot Lot)</option>
                <option value="一般">一般 (Normal)</option>
              </select>
            </div>
          </div>
          <div className="flex items-end justify-between gap-2">
            <div className="w-28">
              <label className="block text-[11px] text-slate-400">晶圓片數</label>
              <input
                type="number"
                min="1"
                max="50"
                value={waferQty}
                onChange={(e) => setWaferQty(e.target.value)}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-100 focus:border-cyan-500 focus:outline-none"
              />
            </div>
            <button
              type="submit"
              className="rounded-lg bg-cyan-500 px-3 py-1.5 text-xs font-semibold text-slate-950 transition hover:bg-cyan-400"
            >
              加入佇列
            </button>
          </div>
        </form>
      )}

      {/* Queue Items */}
      <div className="mt-3 max-h-[340px] space-y-2 overflow-y-auto pr-1">
        {queue.map((lot) => {
          const isUrgent = lot.priority === '急件'
          return (
            <div
              key={lot.lot_id}
              className={`rounded-lg border p-2.5 transition ${
                isUrgent && lot.status === '待排程'
                  ? 'border-rose-500/40 bg-rose-950/20'
                  : 'border-slate-800 bg-slate-950/60'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5">
                  {isUrgent ? (
                    <span className="inline-flex items-center gap-0.5 rounded bg-rose-500/20 px-1.5 py-0.5 text-[10px] font-bold text-rose-300 border border-rose-500/40">
                      <Flame className="h-2.5 w-2.5" />
                      急件
                    </span>
                  ) : (
                    <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-medium text-slate-400">
                      一般
                    </span>
                  )}
                  <span className="font-mono text-xs font-bold text-slate-100">{lot.lot_id}</span>
                  <span className="text-[11px] text-slate-400">· {lot.customer}</span>
                </div>

                <span
                  className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${
                    STATUS_BADGE[lot.status] || STATUS_BADGE['待排程']
                  }`}
                >
                  {lot.status}
                </span>
              </div>

              <div className="mt-1.5 flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-300">
                <div className="flex items-center gap-2 font-mono">
                  <span className="text-cyan-300">{lot.chip_model}</span>
                  <span className="text-slate-500">|</span>
                  <span className="rounded bg-slate-800/80 px-1.5 py-0.5 text-[10px] text-slate-300">
                    {lot.required_probe_card}
                  </span>
                  <span className="text-slate-400">{lot.multi_site_req}-Site</span>
                </div>

                {lot.assigned_machine_id ? (
                  <span className="inline-flex items-center gap-1 font-mono text-[11px] font-semibold text-emerald-300">
                    <ArrowRight className="h-3 w-3" />
                    {lot.assigned_machine_id}
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-[11px] text-slate-500">
                    <Clock className="h-3 w-3" />
                    等待排程
                  </span>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {urgentPending > 0 && (
        <button
          onClick={() => onSmartSchedule(false)}
          disabled={scheduling}
          className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-cyan-500 to-emerald-500 px-3 py-2 text-xs font-bold text-slate-950 shadow-lg shadow-cyan-500/20 transition hover:brightness-110 disabled:opacity-60"
        >
          <Sparkles className="h-4 w-4" />
          智慧排程：立即派送 {urgentPending} 筆急件
        </button>
      )}
    </div>
  )
}
