import asyncio
import json
import random
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional

from database import db_session

ANOMALY_PRESETS = [
    {
        "reason": "核心過溫警示 (>110°C 熱失控保護)",
        "temp_range": (111.5, 121.8),
        "yield_range": (78.0, 86.5),
    },
    {
        "reason": "良率驟降警示 (<85% 封裝接點異常)",
        "temp_range": (96.0, 105.0),
        "yield_range": (72.5, 83.2),
    },
    {
        "reason": "Multi-site 探針接觸阻抗超標",
        "temp_range": (91.0, 99.5),
        "yield_range": (79.5, 84.8),
    },
]


def trigger_anomaly_simulation(target_machine_id: Optional[str] = None) -> Dict[str, Any]:
    """
    觸發異常模擬：
    1. 挑選一台運行中機台（或指定機台）強制進入「異常」狀態。
    2. 若該機台正在測試晶片批次，自動將該受阻批次升級為「急件」並退回待測佇列，等待一鍵智慧重排搶救。
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db_session() as conn:
        if target_machine_id:
            row = conn.execute("SELECT * FROM machines WHERE id = ?", (target_machine_id,)).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM machines WHERE status = '運行中' ORDER BY RANDOM() LIMIT 1"
            ).fetchone()
            if not row:
                row = conn.execute(
                    "SELECT * FROM machines WHERE status != '異常' ORDER BY RANDOM() LIMIT 1"
                ).fetchone()

        if not row:
            return {"status": "no_target", "message": "所有機台皆已處於異常狀態。"}

        machine = dict(row)
        preset = random.choice(ANOMALY_PRESETS)
        fault_temp = round(random.uniform(*preset["temp_range"]), 1)
        fault_yield = round(random.uniform(*preset["yield_range"]), 1)

        rescued_lot_id = None
        if machine["current_lot_id"]:
            rescued_lot_id = machine["current_lot_id"]
            existing_lot = conn.execute(
                "SELECT * FROM test_queue WHERE lot_id = ?", (rescued_lot_id,)
            ).fetchone()
            if existing_lot:
                conn.execute(
                    """
                    UPDATE test_queue
                    SET status = '待排程',
                        priority = '急件',
                        assigned_machine_id = NULL,
                        assigned_at = NULL
                    WHERE lot_id = ?
                    """,
                    (rescued_lot_id,),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO test_queue (
                        lot_id, customer, chip_model, required_probe_card,
                        priority, multi_site_req, wafer_qty, est_duration_sec,
                        status, assigned_machine_id, created_at, assigned_at
                    ) VALUES (?, ?, ?, ?, '急件', ?, 20, 85, '待排程', NULL, ?, NULL)
                    """,
                    (
                        rescued_lot_id,
                        "VIP-AI",
                        machine["chip_model"] or "NV-B200-AI",
                        machine["probe_card"],
                        max(8, int(machine["multi_site"] or 16)),
                        now,
                    ),
                )

        # Also release any jobs reserved specifically on this faulted machine back to pending urgent
        displaced = conn.execute(
            "SELECT lot_id FROM test_queue WHERE assigned_machine_id = ? AND status = '已預約排程'",
            (machine["id"],),
        ).fetchall()
        if displaced:
            conn.execute(
                """
                UPDATE test_queue
                SET status = '待排程', priority = '急件', assigned_machine_id = NULL, assigned_at = NULL
                WHERE assigned_machine_id = ? AND status = '已預約排程'
                """,
                (machine["id"],),
            )

        conn.execute(
            """
            UPDATE machines
            SET status = '異常',
                core_temp = ?,
                yield_rate = ?,
                est_release_sec = 999,
                anomaly_reason = ?,
                current_lot_id = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (fault_temp, fault_yield, preset["reason"], now, machine["id"]),
        )

        log_msg = f"機台 {machine['id']} ({machine['name']}) 發生異常：{preset['reason']}（溫度 {fault_temp}°C / 良率 {fault_yield}%）"
        if rescued_lot_id:
            log_msg += f"，原批次 {rescued_lot_id} 已緊急轉回佇列標記為「急件」等待重排！"

        conn.execute(
            "INSERT INTO event_logs (level, category, message, machine_id, lot_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("CRITICAL", "ANOMALY", log_msg, machine["id"], rescued_lot_id, now),
        )

    return {
        "status": "ok",
        "machine_id": machine["id"],
        "reason": preset["reason"],
        "core_temp": fault_temp,
        "yield_rate": fault_yield,
        "rescued_lot_id": rescued_lot_id,
        "message": log_msg,
    }


def recover_machine(machine_id: str) -> Dict[str, Any]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db_session() as conn:
        row = conn.execute("SELECT * FROM machines WHERE id = ?", (machine_id,)).fetchone()
        if not row:
            return {"status": "not_found", "message": f"找不到機台 {machine_id}"}

        conn.execute(
            """
            UPDATE machines
            SET status = '閒置',
                chip_model = NULL,
                multi_site = 0,
                burn_in_progress = 0.0,
                core_temp = 27.8,
                yield_rate = 99.1,
                est_release_sec = 0,
                current_lot_id = NULL,
                anomaly_reason = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (now, machine_id),
        )
        conn.execute(
            "INSERT INTO event_logs (level, category, message, machine_id, lot_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("SUCCESS", "MAINTENANCE", f"機台 {machine_id} 異常排除並通過校準，恢復「閒置」可排程狀態。", machine_id, None, now),
        )
    return {"status": "ok", "machine_id": machine_id, "message": f"機台 {machine_id} 已恢復閒置就緒"}


def step_simulation_tick() -> None:
    """每秒執行一次：更新 12 台機台的溫度、良率、預燒進度與釋出倒數。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db_session() as conn:
        machines = [dict(r) for r in conn.execute("SELECT * FROM machines ORDER BY id ASC").fetchall()]

        for m in machines:
            m_id = m["id"]
            status = m["status"]

            if status == "運行中":
                old_est = max(1, int(m["est_release_sec"]))
                est_sec = max(0, old_est - 1)
                cur_prog = float(m["burn_in_progress"])
                step_pct = (100.0 - cur_prog) / old_est
                new_progress = min(100.0, round(cur_prog + step_pct, 1))
                new_temp = round(max(71.0, min(94.5, float(m["core_temp"]) + random.uniform(-0.8, 0.9))), 1)
                new_yield = round(max(95.5, min(99.8, float(m["yield_rate"]) + random.uniform(-0.18, 0.18))), 2)

                if est_sec == 0 or new_progress >= 100.0:
                    finished_lot = m["current_lot_id"]
                    if finished_lot:
                        conn.execute(
                            "UPDATE test_queue SET status = '已完成' WHERE lot_id = ?",
                            (finished_lot,),
                        )
                        conn.execute(
                            "INSERT INTO event_logs (level, category, message, machine_id, lot_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                            ("INFO", "COMPLETE", f"機台 {m_id} 完成批次 {finished_lot} 動態預燒測試（良率 {new_yield}%）。", m_id, finished_lot, now),
                        )

                    # Check if there is a reserved lot queued for this machine
                    next_lot = conn.execute(
                        """
                        SELECT * FROM test_queue
                        WHERE assigned_machine_id = ? AND status = '已預約排程'
                        ORDER BY CASE WHEN priority = '急件' THEN 0 ELSE 1 END, assigned_at ASC
                        LIMIT 1
                        """,
                        (m_id,),
                    ).fetchone()

                    if next_lot:
                        lot = dict(next_lot)
                        conn.execute(
                            """
                            UPDATE machines
                            SET status = '運行中',
                                chip_model = ?,
                                probe_card = ?,
                                multi_site = ?,
                                burn_in_progress = 1.0,
                                core_temp = 75.0,
                                yield_rate = 99.0,
                                est_release_sec = ?,
                                current_lot_id = ?,
                                updated_at = ?
                            WHERE id = ?
                            """,
                            (
                                lot["chip_model"],
                                lot["required_probe_card"],
                                lot["multi_site_req"],
                                int(lot["est_duration_sec"]),
                                lot["lot_id"],
                                now,
                                m_id,
                            ),
                        )
                        conn.execute(
                            "UPDATE test_queue SET status = '已排程-進行中' WHERE lot_id = ?",
                            (lot["lot_id"],),
                        )
                        conn.execute(
                            "INSERT INTO event_logs (level, category, message, machine_id, lot_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                            ("SUCCESS", "DISPATCH", f"預約批次 {lot['lot_id']} 自動接軌機台 {m_id} 開始測試。", m_id, lot["lot_id"], now),
                        )
                    else:
                        conn.execute(
                            """
                            UPDATE machines
                            SET status = '閒置',
                                chip_model = NULL,
                                multi_site = 0,
                                burn_in_progress = 0.0,
                                core_temp = 28.5,
                                est_release_sec = 0,
                                current_lot_id = NULL,
                                updated_at = ?
                            WHERE id = ?
                            """,
                            (now, m_id),
                        )
                else:
                    conn.execute(
                        """
                        UPDATE machines
                        SET burn_in_progress = ?,
                            core_temp = ?,
                            yield_rate = ?,
                            est_release_sec = ?,
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (new_progress, new_temp, new_yield, est_sec, now, m_id),
                    )

            elif status == "閒置":
                idle_temp = round(max(24.5, min(31.0, float(m["core_temp"]) + random.uniform(-0.3, 0.3))), 1)
                conn.execute(
                    "UPDATE machines SET core_temp = ?, updated_at = ? WHERE id = ?",
                    (idle_temp, now, m_id),
                )

            elif status == "異常":
                fault_temp = round(max(102.0, min(124.0, float(m["core_temp"]) + random.uniform(-0.6, 0.8))), 1)
                fault_yield = round(max(68.0, min(87.0, float(m["yield_rate"]) + random.uniform(-0.4, 0.3))), 1)
                conn.execute(
                    "UPDATE machines SET core_temp = ?, yield_rate = ?, updated_at = ? WHERE id = ?",
                    (fault_temp, fault_yield, now, m_id),
                )


async def simulation_loop(on_tick_broadcast: Callable[[], Awaitable[None]]) -> None:
    while True:
        try:
            step_simulation_tick()
            await on_tick_broadcast()
        except Exception as exc:
            print(f"[Simulator Error] {exc}")
        await asyncio.sleep(1.0)
