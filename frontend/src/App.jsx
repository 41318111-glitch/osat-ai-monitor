import React, { useCallback, useEffect, useRef, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Cpu,
  Flame,
  Layers,
  Radio,
  RotateCcw,
  ShieldAlert,
  Sparkles,
  Zap,
} from 'lucide-react'
import EventLogPanel from './components/EventLogPanel'
import MachineCard from './components/MachineCard'
import TestQueuePanel from './components/TestQueuePanel'

export default function App() {
  const [data, setData] = useState(null)
  const [wsConnected, setWsConnected] = useState(false)
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [banner, setBanner] = useState(null)
  const [busyAction, setBusyAction] = useState(null)
  const wsRef = useRef(null)

  const fetchDashboard = useCallback(async () => {
    try {
      const res = await fetch('/api/dashboard')
      if (res.ok) {
        const json = await res.json()
        setData(json)
      }
    } catch (err) {
      console.error('Failed to fetch dashboard:', err)
    }
  }, [])

  useEffect(() => {
    fetchDashboard()
    let reconnectTimer = null
    let pollTimer = null

    const connectWs = () => {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${proto}//${window.location.host}/ws/telemetry`
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setWsConnected(true)
      }

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data)
          setData(payload)
        } catch (err) {
          console.error('WS parse error:', err)
        }
      }

      ws.onclose = () => {
        setWsConnected(false)
        reconnectTimer = setTimeout(connectWs, 2000)
      }

      ws.onerror = () => {
        setWsConnected(false)
        ws.close()
      }
    }

    connectWs()
    // Backup 1.5s polling in case a proxy buffers WS
    pollTimer = setInterval(() => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        fetchDashboard()
      }
    }, 1500)

    return () => {
      clearTimeout(reconnectTimer)
      clearInterval(pollTimer)
      if (wsRef.current) wsRef.current.close()
    }
  }, [fetchDashboard])

  const handleTriggerAnomaly = async (machineId = null) => {
    setBusyAction('anomaly')
    try {
      const res = await fetch('/api/simulate/anomaly', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ machine_id: machineId }),
      })
      const json = await res.json()
      if (json.snapshot) setData(json.snapshot)
      if (json.result) {
        setBanner({
          type: 'danger',
          title: `異常警報：${json.result.machine_id || '產線'}`,
          message: json.result.message,
          decisions: [],
        })
      }
    } finally {
      setBusyAction(null)
    }
  }

  const handleSmartSchedule = async (includeNormal = false) => {
    setBusyAction('schedule')
    try {
      const res = await fetch('/api/schedule/smart', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ include_normal: includeNormal }),
      })
      const json = await res.json()
      if (json.snapshot) setData(json.snapshot)
      if (json.result) {
        setBanner({
          type: json.result.status === 'ok' ? 'success' : 'info',
          title: 'AI 一鍵智慧重排完成',
          message: json.result.message,
          decisions: json.result.decisions || [],
        })
      }
    } finally {
      setBusyAction(null)
    }
  }

  const handleRecoverMachine = async (machineId) => {
    setBusyAction(`recover-${machineId}`)
    try {
      const res = await fetch(`/api/machines/${machineId}/recover`, { method: 'POST' })
      const json = await res.json()
      if (json.snapshot) setData(json.snapshot)
      if (json.result) {
        setBanner({
          type: 'success',
          title: `機台復歸：${machineId}`,
          message: json.result.message,
          decisions: [],
        })
      }
    } finally {
      setBusyAction(null)
    }
  }

  const handleReset = async () => {
    setBusyAction('reset')
    try {
      const res = await fetch('/api/simulate/reset', { method: 'POST' })
      const json = await res.json()
      if (json.snapshot) setData(json.snapshot)
      setBanner({
        type: 'info',
        title: '產線模擬已重置',
        message: json.message || '12 台機台已恢復初始產線配置。',
        decisions: [],
      })
    } finally {
      setBusyAction(null)
    }
  }

  const handleAddLot = async (lotPayload) => {
    const res = await fetch('/api/queue', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(lotPayload),
    })
    const json = await res.json()
    if (json.snapshot) setData(json.snapshot)
    setBanner({
      type: 'info',
      title: `已加入待測佇列：${json.lot_id}`,
      message: `${lotPayload.priority} · ${lotPayload.chip_model} (${lotPayload.required_probe_card})`,
      decisions: [],
    })
  }

  const kpis = data?.kpis || {
    total_machines: 12,
    running_count: 0,
    idle_count: 0,
    anomaly_count: 0,
    avg_yield: 0,
    avg_temp: 0,
    active_multi_sites: 0,
    urgent_pending_count: 0,
  }

  const machines = (data?.machines || []).filter((m) =>
    statusFilter === 'ALL' ? true : m.status === statusFilter
  )

  return (
    <div className="min-h-screen px-4 py-4 md:px-6 lg:px-8">
      <div className="mx-auto max-w-[1600px] space-y-4">
        {/* Top Command Bar */}
        <header className="flex flex-col gap-4 rounded-2xl border border-slate-800/90 bg-slate-900/90 p-4 shadow-xl backdrop-blur-xl lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500 to-indigo-600 text-white shadow-lg shadow-cyan-500/25">
                <Cpu className="h-5 w-5" />
              </div>
              <div>
                <h1 className="text-lg font-bold tracking-tight text-white md:text-xl">
                  OSAT AI 晶片測試排程與動態預燒監控戰情室
                </h1>
                <div className="mt-0.5 flex flex-wrap items-center gap-3 text-xs text-slate-400">
                  <span className="inline-flex items-center gap-1.5">
                    <Radio
                      className={`h-3.5 w-3.5 ${
                        wsConnected ? 'text-emerald-400 animate-pulse' : 'text-amber-400'
                      }`}
                    />
                    {wsConnected ? 'WebSocket 即時遙測 (1s/tick)' : 'HTTP 輪詢連線中'}
                  </span>
                  <span className="font-mono text-slate-500">|</span>
                  <span className="font-mono text-slate-300">
                    最後更新：{data?.timestamp || '同步中...'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <button
              id="btn-trigger-anomaly"
              onClick={() => handleTriggerAnomaly(null)}
              disabled={busyAction !== null}
              className="inline-flex items-center gap-2 rounded-xl border border-rose-500/50 bg-rose-500/15 px-4 py-2.5 text-sm font-semibold text-rose-200 shadow-lg shadow-rose-500/10 transition hover:bg-rose-500/25 disabled:opacity-50"
            >
              <ShieldAlert className="h-4 w-4 text-rose-400" />
              觸發異常模擬
            </button>

            <button
              id="btn-smart-reschedule"
              onClick={() => handleSmartSchedule(false)}
              disabled={busyAction !== null}
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-cyan-400 via-teal-400 to-emerald-400 px-5 py-2.5 text-sm font-bold text-slate-950 shadow-lg shadow-cyan-500/25 transition hover:brightness-110 disabled:opacity-50"
            >
              <Sparkles className="h-4 w-4" />
              一鍵智慧重排
            </button>

            <button
              id="btn-reset-sim"
              onClick={handleReset}
              disabled={busyAction !== null}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-800/80 px-3.5 py-2.5 text-xs font-medium text-slate-300 transition hover:border-slate-500 hover:text-white disabled:opacity-50"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              重置模擬
            </button>
          </div>
        </header>

        {/* Action Feedback Banner */}
        {banner && (
          <div
            className={`rounded-xl border px-4 py-3 backdrop-blur-md transition-all ${
              banner.type === 'danger'
                ? 'border-rose-500/50 bg-rose-950/60 text-rose-100'
                : banner.type === 'success'
                  ? 'border-emerald-500/50 bg-emerald-950/50 text-emerald-100'
                  : 'border-cyan-500/40 bg-cyan-950/40 text-cyan-100'
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-2.5">
                {banner.type === 'danger' ? (
                  <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-rose-400" />
                ) : (
                  <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-400" />
                )}
                <div>
                  <div className="text-sm font-bold">{banner.title}</div>
                  <p className="mt-0.5 text-xs opacity-90">{banner.message}</p>
                  {banner.decisions && banner.decisions.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {banner.decisions.map((d, idx) => (
                        <span
                          key={`${d.lot_id}-${idx}`}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-white/15 bg-slate-950/60 px-2.5 py-1 font-mono text-[11px] text-slate-100"
                        >
                          <Zap className="h-3 w-3 text-cyan-400" />
                          {d.lot_id} → {d.machine_id || '暫無'} ({d.reason})
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              <button
                onClick={() => setBanner(null)}
                className="rounded px-2 py-0.5 text-xs opacity-70 hover:bg-white/10 hover:opacity-100"
              >
                關閉
              </button>
            </div>
          </div>
        )}

        {/* KPI Cards */}
        <section className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3.5">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>機台運行狀態 (12 台)</span>
              <Activity className="h-4 w-4 text-emerald-400" />
            </div>
            <div className="mt-2 flex items-baseline gap-2 font-mono">
              <span className="text-2xl font-bold text-emerald-300">{kpis.running_count}</span>
              <span className="text-xs text-slate-400">運行</span>
              <span className="text-lg font-bold text-cyan-300">{kpis.idle_count}</span>
              <span className="text-xs text-slate-400">閒置</span>
              <span className="text-lg font-bold text-rose-400">{kpis.anomaly_count}</span>
              <span className="text-xs text-slate-400">異常</span>
            </div>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3.5">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>Multi-Site 並行總數</span>
              <Layers className="h-4 w-4 text-indigo-400" />
            </div>
            <div className="mt-2 font-mono text-2xl font-bold text-indigo-300">
              {kpis.active_multi_sites} <span className="text-xs font-normal text-slate-400">Sites</span>
            </div>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3.5">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>運行機台平均良率</span>
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            </div>
            <div className="mt-2 font-mono text-2xl font-bold text-emerald-300">
              {kpis.avg_yield}%
            </div>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3.5">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>動態預燒平均核心溫</span>
              <Flame className="h-4 w-4 text-orange-400" />
            </div>
            <div className="mt-2 font-mono text-2xl font-bold text-amber-300">
              {kpis.avg_temp}°C
            </div>
          </div>

          <div className="col-span-2 rounded-xl border border-slate-800 bg-slate-900/80 p-3.5 md:col-span-1">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>待排程急件數</span>
              <AlertTriangle className="h-4 w-4 text-rose-400" />
            </div>
            <div className="mt-2 font-mono text-2xl font-bold text-rose-300">
              {kpis.urgent_pending_count} <span className="text-xs font-normal text-slate-400">Lots</span>
            </div>
          </div>
        </section>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
          {/* Left 8 Cols: 12 Machines */}
          <div className="space-y-3 xl:col-span-8">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-bold text-white">
                高階 AI 測試機台即時監控矩陣 (ATE / Dynamic Burn-In)
              </h2>
              <div className="flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900/80 p-1 text-xs">
                {[
                  { key: 'ALL', label: `全部 (${kpis.total_machines})` },
                  { key: '運行中', label: `運行中 (${kpis.running_count})` },
                  { key: '閒置', label: `閒置 (${kpis.idle_count})` },
                  { key: '異常', label: `異常 (${kpis.anomaly_count})` },
                ].map((tab) => (
                  <button
                    key={tab.key}
                    onClick={() => setStatusFilter(tab.key)}
                    className={`rounded-md px-2.5 py-1 font-medium transition ${
                      statusFilter === tab.key
                        ? 'bg-cyan-500/20 text-cyan-300'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {machines.map((m) => (
                <MachineCard
                  key={m.id}
                  machine={m}
                  onRecover={handleRecoverMachine}
                  onSimulateFault={(id) => handleTriggerAnomaly(id)}
                />
              ))}
            </div>
          </div>

          {/* Right 4 Cols: Queue + Event Log */}
          <div className="space-y-4 xl:col-span-4">
            <TestQueuePanel
              queue={data?.queue || []}
              onAddLot={handleAddLot}
              onSmartSchedule={handleSmartSchedule}
              scheduling={busyAction === 'schedule'}
            />
            <EventLogPanel logs={data?.logs || []} />
          </div>
        </div>
      </div>
    </div>
  )
}
