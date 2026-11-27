import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Generator

DB_PATH = os.path.join(os.path.dirname(__file__), "osat_monitor.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


@contextmanager
def db_session() -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db_session() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS machines (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                bay TEXT NOT NULL,
                status TEXT NOT NULL,
                chip_model TEXT,
                probe_card TEXT NOT NULL,
                compatible_probe_cards TEXT NOT NULL,
                multi_site INTEGER NOT NULL DEFAULT 0,
                burn_in_progress REAL NOT NULL DEFAULT 0.0,
                core_temp REAL NOT NULL DEFAULT 28.0,
                yield_rate REAL NOT NULL DEFAULT 99.0,
                est_release_sec INTEGER NOT NULL DEFAULT 0,
                current_lot_id TEXT,
                anomaly_reason TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS test_queue (
                lot_id TEXT PRIMARY KEY,
                customer TEXT NOT NULL,
                chip_model TEXT NOT NULL,
                required_probe_card TEXT NOT NULL,
                priority TEXT NOT NULL,
                multi_site_req INTEGER NOT NULL,
                wafer_qty INTEGER NOT NULL,
                est_duration_sec INTEGER NOT NULL,
                status TEXT NOT NULL,
                assigned_machine_id TEXT,
                created_at TEXT NOT NULL,
                assigned_at TEXT
            );

            CREATE TABLE IF NOT EXISTS event_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                category TEXT NOT NULL,
                message TEXT NOT NULL,
                machine_id TEXT,
                lot_id TEXT,
                created_at TEXT NOT NULL
            );
            """
        )


def seed_initial_data(force_reset: bool = False) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db_session() as conn:
        if force_reset:
            conn.execute("DELETE FROM machines")
            conn.execute("DELETE FROM test_queue")
            conn.execute("DELETE FROM event_logs")

        count = conn.execute("SELECT COUNT(*) FROM machines").fetchone()[0]
        if count > 0:
            return

        machines = [
            ("ATE-01", "V93K-EXA-01", "FAB-A1", "運行中", "NV-B200-AI", "PC-HBM3E-16S", ["PC-HBM3E-16S", "PC-COWOS-8S"], 16, 78.4, 84.2, 98.7, 55, "LOT-2611-101", None),
            ("ATE-02", "V93K-EXA-02", "FAB-A1", "運行中", "AMD-MI350X", "PC-COWOS-8S", ["PC-COWOS-8S", "PC-HBM3E-16S"], 8, 91.2, 86.5, 97.9, 28, "LOT-2611-102", None),
            ("ATE-03", "UFLEX-AI-03", "FAB-A1", "閒置", None, "PC-N3P-32S", ["PC-N3P-32S", "PC-BGA-16S"], 0, 0.0, 27.4, 99.2, 0, None, None),
            ("ATE-04", "UFLEX-AI-04", "FAB-A2", "運行中", "TSMC-N3-TPU", "PC-N3P-32S", ["PC-N3P-32S", "PC-HBM3E-16S"], 32, 42.0, 81.9, 99.1, 115, "LOT-2611-103", None),
            ("ATE-05", "COHU-BI-05", "FAB-A2", "運行中", "NV-GB300-SOC", "PC-HBM3E-16S", ["PC-HBM3E-16S", "PC-N3P-32S"], 16, 86.5, 89.4, 98.3, 35, "LOT-2611-104", None),
            ("ATE-06", "COHU-BI-06", "FAB-A2", "運行中", "AVGO-XPU-V4", "PC-COWOS-8S", ["PC-COWOS-8S", "PC-BGA-16S"], 8, 55.3, 79.8, 98.9, 90, "LOT-2611-105", None),
            ("ATE-07", "V93K-EXA-07", "FAB-B1", "閒置", None, "PC-HBM3E-16S", ["PC-HBM3E-16S", "PC-COWOS-8S"], 0, 0.0, 28.1, 99.0, 0, None, None),
            ("ATE-08", "V93K-EXA-08", "FAB-B1", "運行中", "QCOM-NPU-X2", "PC-BGA-16S", ["PC-BGA-16S", "PC-N3P-32S"], 16, 63.7, 76.2, 99.4, 72, "LOT-2611-106", None),
            ("ATE-09", "UFLEX-AI-09", "FAB-B1", "運行中", "NV-B200-AI", "PC-HBM3E-16S", ["PC-HBM3E-16S", "PC-BGA-16S"], 16, 94.1, 87.1, 98.5, 18, "LOT-2611-107", None),
            ("ATE-10", "COHU-BI-10", "FAB-B2", "運行中", "MTK-DIM-AI", "PC-BGA-16S", ["PC-BGA-16S", "PC-COWOS-8S"], 16, 29.8, 74.5, 99.3, 140, "LOT-2611-108", None),
            ("ATE-11", "V93K-EXA-11", "FAB-B2", "運行中", "GOOG-TPU-V6", "PC-N3P-32S", ["PC-N3P-32S", "PC-COWOS-8S"], 32, 71.6, 83.0, 98.8, 60, "LOT-2611-109", None),
            ("ATE-12", "COHU-BI-12", "FAB-B2", "運行中", "AMD-MI350X", "PC-COWOS-8S", ["PC-COWOS-8S", "PC-HBM3E-16S"], 8, 82.0, 88.2, 97.8, 42, "LOT-2611-110", None),
        ]

        for m in machines:
            conn.execute(
                """
                INSERT INTO machines (
                    id, name, bay, status, chip_model, probe_card,
                    compatible_probe_cards, multi_site, burn_in_progress,
                    core_temp, yield_rate, est_release_sec, current_lot_id,
                    anomaly_reason, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    m[0], m[1], m[2], m[3], m[4], m[5],
                    json.dumps(m[6]), m[7], m[8], m[9], m[10], m[11], m[12], m[13], now
                ),
            )

        queue_items = [
            ("LOT-URG-901", "NVIDIA", "NV-B200-AI", "PC-HBM3E-16S", "急件", 16, 25, 110, "待排程", None),
            ("LOT-URG-902", "Google", "GOOG-TPU-V6", "PC-N3P-32S", "急件", 32, 20, 95, "待排程", None),
            ("LOT-URG-903", "AMD", "AMD-MI350X", "PC-COWOS-8S", "急件", 8, 18, 90, "待排程", None),
            ("LOT-URG-904", "Broadcom", "AVGO-XPU-V4", "PC-HBM3E-16S", "急件", 16, 22, 105, "待排程", None),
            ("LOT-STD-401", "MediaTek", "MTK-DIM-AI", "PC-BGA-16S", "一般", 16, 25, 120, "待排程", None),
            ("LOT-STD-402", "Qualcomm", "QCOM-NPU-X2", "PC-BGA-16S", "一般", 16, 25, 115, "待排程", None),
        ]

        for q in queue_items:
            conn.execute(
                """
                INSERT INTO test_queue (
                    lot_id, customer, chip_model, required_probe_card,
                    priority, multi_site_req, wafer_qty, est_duration_sec,
                    status, assigned_machine_id, created_at, assigned_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (q[0], q[1], q[2], q[3], q[4], q[5], q[6], q[7], q[8], q[9], now, None),
            )

        conn.execute(
            """
            INSERT INTO event_logs (level, category, message, machine_id, lot_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("INFO", "SYSTEM", "OSAT AI 晶片測試戰情室啟動，12 台高階 ATE/Burn-In 機台連線就緒。", None, None, now),
        )
