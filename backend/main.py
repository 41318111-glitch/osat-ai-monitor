import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database import db_session, init_db, seed_initial_data
from scheduler import run_smart_schedule
from simulator import recover_machine, simulation_loop, trigger_anomaly_simulation


class NewLotRequest(BaseModel):
    customer: str = "NVIDIA"
    chip_model: str = "NV-B200-AI"
    required_probe_card: str = "PC-HBM3E-16S"
    priority: str = "急件"
    multi_site_req: int = 16
    wafer_qty: int = 25
    est_duration_sec: int = 90


class AnomalyRequest(BaseModel):
    machine_id: Optional[str] = None


class ScheduleRequest(BaseModel):
    include_normal: bool = False


connected_clients: Set[WebSocket] = set()


def fetch_dashboard_snapshot() -> Dict[str, Any]:
    with db_session() as conn:
        machines_raw = conn.execute("SELECT * FROM machines ORDER BY id ASC").fetchall()
        machines: List[Dict[str, Any]] = []
        for row in machines_raw:
            item = dict(row)
            item["compatible_probe_cards"] = json.loads(item["compatible_probe_cards"])
            machines.append(item)

        queue_rows = conn.execute(
            """
            SELECT * FROM test_queue
            ORDER BY
                CASE status
                    WHEN '待排程' THEN 0
                    WHEN '已預約排程' THEN 1
                    WHEN '已排程-進行中' THEN 2
                    ELSE 3
                END,
                CASE WHEN priority = '急件' THEN 0 ELSE 1 END,
                created_at ASC
            """
        ).fetchall()
        queue = [dict(r) for r in queue_rows]

        log_rows = conn.execute(
            "SELECT * FROM event_logs ORDER BY id DESC LIMIT 30"
        ).fetchall()
        logs = [dict(r) for r in log_rows]

    running = [m for m in machines if m["status"] == "運行中"]
    idle = [m for m in machines if m["status"] == "閒置"]
    anomaly = [m for m in machines if m["status"] == "異常"]
    avg_yield = round(sum(m["yield_rate"] for m in running) / len(running), 2) if running else 99.0
    avg_temp = round(sum(m["core_temp"] for m in running) / len(running), 1) if running else 28.0
    total_sites = sum(m["multi_site"] for m in running)
    urgent_pending = sum(1 for q in queue if q["priority"] == "急件" and q["status"] == "待排程")

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "kpis": {
            "total_machines": len(machines),
            "running_count": len(running),
            "idle_count": len(idle),
            "anomaly_count": len(anomaly),
            "avg_yield": avg_yield,
            "avg_temp": avg_temp,
            "active_multi_sites": total_sites,
            "urgent_pending_count": urgent_pending,
        },
        "machines": machines,
        "queue": queue,
        "logs": logs,
    }


async def broadcast_snapshot() -> None:
    if not connected_clients:
        return
    payload = json.dumps(fetch_dashboard_snapshot(), ensure_ascii=False)
    stale: List[WebSocket] = []
    for ws in list(connected_clients):
        try:
            await ws.send_text(payload)
        except Exception:
            stale.append(ws)
    for ws in stale:
        connected_clients.discard(ws)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_initial_data(force_reset=False)
    sim_task = asyncio.create_task(simulation_loop(broadcast_snapshot))
    try:
        yield
    finally:
        sim_task.cancel()
        try:
            await sim_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="OSAT AI Chip Test & Dynamic Burn-In Monitor", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check() -> Dict[str, Any]:
    return {"status": "healthy", "service": "osat-ai-monitor"}


@app.get("/api/dashboard")
def get_dashboard() -> Dict[str, Any]:
    return fetch_dashboard_snapshot()


@app.post("/api/schedule/smart")
async def api_smart_schedule(req: ScheduleRequest = ScheduleRequest()) -> Dict[str, Any]:
    result = run_smart_schedule(include_normal=req.include_normal)
    await broadcast_snapshot()
    return {"result": result, "snapshot": fetch_dashboard_snapshot()}


@app.post("/api/simulate/anomaly")
async def api_trigger_anomaly(req: AnomalyRequest = AnomalyRequest()) -> Dict[str, Any]:
    result = trigger_anomaly_simulation(target_machine_id=req.machine_id)
    await broadcast_snapshot()
    return {"result": result, "snapshot": fetch_dashboard_snapshot()}


@app.post("/api/machines/{machine_id}/recover")
async def api_recover_machine(machine_id: str) -> Dict[str, Any]:
    result = recover_machine(machine_id)
    await broadcast_snapshot()
    return {"result": result, "snapshot": fetch_dashboard_snapshot()}


@app.post("/api/simulate/reset")
async def api_reset_simulation() -> Dict[str, Any]:
    seed_initial_data(force_reset=True)
    await broadcast_snapshot()
    return {"status": "ok", "message": "系統模擬數據已重置為初始產線狀態。", "snapshot": fetch_dashboard_snapshot()}


@app.post("/api/queue")
async def api_add_queue_lot(req: NewLotRequest) -> Dict[str, Any]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lot_id = f"LOT-{'URG' if req.priority == '急件' else 'STD'}-{datetime.now().strftime('%H%M%S')}"
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO test_queue (
                lot_id, customer, chip_model, required_probe_card,
                priority, multi_site_req, wafer_qty, est_duration_sec,
                status, assigned_machine_id, created_at, assigned_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '待排程', NULL, ?, NULL)
            """,
            (
                lot_id,
                req.customer,
                req.chip_model,
                req.required_probe_card,
                req.priority,
                req.multi_site_req,
                req.wafer_qty,
                req.est_duration_sec,
                now,
            ),
        )
        conn.execute(
            "INSERT INTO event_logs (level, category, message, machine_id, lot_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("INFO", "QUEUE", f"新增{req.priority}批次 {lot_id} ({req.chip_model}, 探針卡 {req.required_probe_card}) 至待測佇列。", None, lot_id, now),
        )
    await broadcast_snapshot()
    return {"status": "ok", "lot_id": lot_id, "snapshot": fetch_dashboard_snapshot()}


@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket) -> None:
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        await websocket.send_text(json.dumps(fetch_dashboard_snapshot(), ensure_ascii=False))
        while True:
            # Keep connection alive; client may send ping
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_clients.discard(websocket)
    except Exception:
        connected_clients.discard(websocket)


FRONTEND_DIST = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
if os.path.isdir(FRONTEND_DIST):
    assets_dir = os.path.join(FRONTEND_DIST, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("ws/"):
            return {"detail": "Not Found"}
        candidate = os.path.join(FRONTEND_DIST, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
