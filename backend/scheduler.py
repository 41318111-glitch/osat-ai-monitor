import json
from datetime import datetime
from typing import Any, Dict, List

from database import db_session


def run_smart_schedule(include_normal: bool = False) -> Dict[str, Any]:
    """
    智慧排程核心演算法：
    1. 優先處理待測佇列中的「急件」（依建立時間排序）。
    2. 對每筆急件篩選「非異常」且「探針卡相容」的測試機台。
    3. 計算每台候選機台的「預計最快釋出時間」（含現有預燒剩餘秒數 + 已預約排程時長 + 探針卡換線懲罰）。
    4. 若目標機台目前「閒置」且尚未被指派，立即派工上機（轉為「運行中」）；
       若目標機台「運行中」，則預約排入該最快釋出機台，並標註預計等待秒數。
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    decisions: List[Dict[str, Any]] = []
    dispatched_count = 0
    reserved_count = 0
    unassigned_count = 0

    with db_session() as conn:
        priorities = ("'急件'", "'一般'") if include_normal else ("'急件'",)
        query = f"""
            SELECT * FROM test_queue
            WHERE status = '待排程' AND priority IN ({','.join(priorities)})
            ORDER BY CASE WHEN priority = '急件' THEN 0 ELSE 1 END, created_at ASC, lot_id ASC
        """
        pending_lots = [dict(row) for row in conn.execute(query).fetchall()]
        machines = [dict(row) for row in conn.execute("SELECT * FROM machines ORDER BY id ASC").fetchall()]

        if not pending_lots:
            return {
                "status": "no_pending",
                "message": "目前待測佇列中無待排程的急件批次。",
                "dispatched_count": 0,
                "reserved_count": 0,
                "unassigned_count": 0,
                "decisions": [],
            }

        # Track projected availability seconds per machine across this scheduling pass
        machine_state: Dict[str, Dict[str, Any]] = {}
        existing_reserved = conn.execute(
            """
            SELECT assigned_machine_id, COALESCE(SUM(est_duration_sec), 0) AS queued_sec
            FROM test_queue
            WHERE status = '已預約排程' AND assigned_machine_id IS NOT NULL
            GROUP BY assigned_machine_id
            """
        ).fetchall()
        reserved_map = {r["assigned_machine_id"]: r["queued_sec"] for r in existing_reserved}

        for m in machines:
            compat = json.loads(m["compatible_probe_cards"])
            base_wait = 0 if m["status"] == "閒置" else int(m["est_release_sec"])
            queued_wait = int(reserved_map.get(m["id"], 0))
            machine_state[m["id"]] = {
                **m,
                "compat_list": compat,
                "projected_free_sec": base_wait + queued_wait,
                "immediately_available": m["status"] == "閒置" and queued_wait == 0,
            }

        for lot in pending_lots:
            req_card = lot["required_probe_card"]
            candidates = []

            for m_id, m in machine_state.items():
                if m["status"] == "異常":
                    continue
                if req_card not in m["compat_list"]:
                    continue

                changeover_penalty = 0 if m["probe_card"] == req_card else 12
                effective_wait = m["projected_free_sec"] + changeover_penalty
                candidates.append((effective_wait, changeover_penalty, m_id, m))

            if not candidates:
                unassigned_count += 1
                msg = f"急件 {lot['lot_id']} ({lot['chip_model']}) 暫無可用且相容探針卡 {req_card} 的正常機台。"
                conn.execute(
                    "INSERT INTO event_logs (level, category, message, machine_id, lot_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    ("WARNING", "SCHEDULER", msg, None, lot["lot_id"], now),
                )
                decisions.append(
                    {
                        "lot_id": lot["lot_id"],
                        "action": "UNASSIGNED",
                        "reason": f"無相容 {req_card} 之健康機台",
                    }
                )
                continue

            # Sort by shortest effective wait time, prefer matching probe card, then machine id
            candidates.sort(key=lambda item: (item[0], item[1], item[2]))
            best_wait, penalty, best_id, best_m = candidates[0]

            if best_m["immediately_available"]:
                # Immediately start execution on idle machine
                dispatched_count += 1
                best_m["immediately_available"] = False
                best_m["status"] = "運行中"
                best_m["probe_card"] = req_card
                best_m["projected_free_sec"] = int(lot["est_duration_sec"]) + penalty

                conn.execute(
                    """
                    UPDATE machines
                    SET status = '運行中',
                        chip_model = ?,
                        probe_card = ?,
                        multi_site = ?,
                        burn_in_progress = 1.5,
                        core_temp = 74.5,
                        yield_rate = 99.1,
                        est_release_sec = ?,
                        current_lot_id = ?,
                        anomaly_reason = NULL,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        lot["chip_model"],
                        req_card,
                        lot["multi_site_req"],
                        int(lot["est_duration_sec"]),
                        lot["lot_id"],
                        now,
                        best_id,
                    ),
                )
                conn.execute(
                    """
                    UPDATE test_queue
                    SET status = '已排程-進行中',
                        assigned_machine_id = ?,
                        assigned_at = ?
                    WHERE lot_id = ?
                    """,
                    (best_id, now, lot["lot_id"]),
                )

                card_note = "探針卡免換線" if penalty == 0 else f"自動切換探針卡至 {req_card}"
                msg = f"急件 {lot['lot_id']} ({lot['chip_model']}) 已立即派工至閒置機台 {best_id}（{card_note}，預估 {lot['est_duration_sec']}s 完成）。"
                conn.execute(
                    "INSERT INTO event_logs (level, category, message, machine_id, lot_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    ("SUCCESS", "SCHEDULER", msg, best_id, lot["lot_id"], now),
                )
                decisions.append(
                    {
                        "lot_id": lot["lot_id"],
                        "machine_id": best_id,
                        "action": "DISPATCHED_NOW",
                        "eta_sec": 0,
                        "probe_card": req_card,
                        "reason": f"閒置機台立即接單 · {card_note}",
                    }
                )
            else:
                # Reserve on the soonest-to-release compatible machine
                reserved_count += 1
                eta = best_wait
                best_m["projected_free_sec"] += int(lot["est_duration_sec"]) + penalty

                conn.execute(
                    """
                    UPDATE test_queue
                    SET status = '已預約排程',
                        assigned_machine_id = ?,
                        assigned_at = ?
                    WHERE lot_id = ?
                    """,
                    (best_id, now, lot["lot_id"]),
                )

                card_note = "探針卡完全相容" if penalty == 0 else f"相容換線(+{penalty}s)"
                msg = f"急件 {lot['lot_id']} ({lot['chip_model']}) 已智慧預約最快釋出機台 {best_id}（預計 {eta}s 後上線 · {card_note}）。"
                conn.execute(
                    "INSERT INTO event_logs (level, category, message, machine_id, lot_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    ("INFO", "SCHEDULER", msg, best_id, lot["lot_id"], now),
                )
                decisions.append(
                    {
                        "lot_id": lot["lot_id"],
                        "machine_id": best_id,
                        "action": "RESERVED_SOONEST",
                        "eta_sec": eta,
                        "probe_card": req_card,
                        "reason": f"最快釋出 ({eta}s) · {card_note}",
                    }
                )

    summary = f"智慧排程完成：立即派工 {dispatched_count} 批、預約最快釋出機台 {reserved_count} 批"
    if unassigned_count:
        summary += f"、無可用機台 {unassigned_count} 批"

    return {
        "status": "ok",
        "message": summary,
        "dispatched_count": dispatched_count,
        "reserved_count": reserved_count,
        "unassigned_count": unassigned_count,
        "decisions": decisions,
    }
