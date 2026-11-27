# 封測廠（OSAT）AI 晶片測試排程與動態預燒監控系統

一套專為半導體封測廠（OSAT）設計的高階 AI 晶片測試排程與動態預燒（Dynamic Burn-In）戰情室全端原型系統，支援 12 台高階 ATE / Burn-In 機台每秒即時遙測、異常模擬搶救與一鍵智慧重排。

---

## 系統架構

```text
osat-ai-monitor/
├── backend/
│   ├── main.py             # FastAPI 應用程式、REST API、WebSocket (/ws/telemetry) 與靜態資源服務
│   ├── database.py         # SQLite (WAL 模式) 資料表定義與初始 12 台機台/佇列種子資料
│   ├── simulator.py        # 每秒背景遙測模擬器、異常觸發與機台復歸邏輯
│   ├── scheduler.py        # 智慧排程核心演算法（探針卡相容性 + 最快釋出時間優先）
│   └── requirements.txt    # 後端 Python 相依套件
├── frontend/
│   ├── index.html          # Vite 入口頁面
│   ├── package.json        # 前端相依套件與腳本
│   ├── vite.config.js      # Vite 設定（含 /api 與 /ws 反向代理至 port 8000）
│   ├── tailwind.config.js  # Tailwind CSS 設定
│   └── src/
│       ├── App.jsx                         # 戰情室主控台、KPI 看板與 WebSocket 訂閱
│       └── components/
│           ├── MachineCard.jsx             # 單台測試機台即時監控卡片
│           ├── TestQueuePanel.jsx          # 待測晶片佇列與手動新增插單面板
│           └── EventLogPanel.jsx           # 即時排程決策與異常告警日誌
└── .gitignore
```

### 技術堆疊

- **前端**：React 18、Tailwind CSS、Lucide Icons、Vite
- **後端**：Python FastAPI、Uvicorn、WebSockets、SQLite（WAL 模式）
- **即時通訊**：WebSocket (`/ws/telemetry`) 每秒主動推播最新產線快照，並內建 HTTP 輪詢（`/api/dashboard`）自動備援

---

## 核心功能

1. **12 台高階機台每秒即時監控（`ATE-01` ～ `ATE-12`）**
   - 即時顯示機台狀態（`運行中` / `閒置` / `異常`）、晶片型號、Multi-site 平行測試數量、預燒進度百分比、核心溫度（°C）、即時良率（%）、目前裝載探針卡與相容探針卡清單。
2. **觸發異常模擬（Anomaly Simulation）**
   - 隨機（或針對指定機台）模擬核心過溫警示、良率驟降或 Multi-site 探針接觸阻抗超標，將機台鎖定為 `異常`，並自動將受阻批次緊急退回待測佇列且升級為 `急件`。
3. **一鍵智慧重排（Smart Scheduling）**
   - 依序讀取待測佇列中的 `急件`，過濾出非 `異常` 且探針卡相容（`required_probe_card in compatible_probe_cards`）之健康機台。
   - 綜合現有預燒剩餘秒數、已預約排程時長與探針卡換線成本（免換線優先），將急件立即派工至閒置機台，或預約至預計最快釋出之機台。

---

## API 端點一覽

| 方法 | 路徑 | 說明 |
| :--- | :--- | :--- |
| `GET` | `/api/health` | 服務健康檢查 |
| `GET` | `/api/dashboard` | 取得 KPI、12 台機台狀態、待測佇列與事件日誌 |
| `POST` | `/api/schedule/smart` | 執行一鍵智慧重排（分配急件至最快釋出且探針卡相容機台） |
| `POST` | `/api/simulate/anomaly` | 觸發機台異常模擬並搶救受阻批次為急件 |
| `POST` | `/api/machines/{machine_id}/recover` | 排除異常並將機台復歸為閒置就緒狀態 |
| `POST` | `/api/simulate/reset` | 重置資料庫為初始 12 台機台與測試佇列 |
| `POST` | `/api/queue` | 新增急件或一般測試批次至佇列 |
| `WS` | `/ws/telemetry` | 每秒即時推播完整戰情室遙測資料 |

---

## 本地啟動說明

### 1. 啟動後端服務（Python FastAPI）

```bash
cd backend
pip install -r requirements.txt
pip install websockets
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

> 啟動時會自動初始化 SQLite 資料庫 `backend/osat_monitor.db` 與 12 台測試機台模擬資料，並啟動每秒背景模擬任務。

### 2. 啟動前端戰情室（React + Vite）

```bash
cd frontend
npm install
npm run dev
```

啟動後可於瀏覽器開啟 `http://localhost:5173`（開發模式透過 Vite proxy 轉發 `/api` 與 `/ws` 至 port 8000）。

### 3. 單一服務生產模式（選用）

若希望僅由 FastAPI 單一埠位同時提供前後端服務：

```bash
cd frontend
npm run build
cd ../backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

建置產物位於 `frontend/dist` 時，FastAPI 會自動掛載並提供前端頁面，直接開啟 `http://localhost:8000` 即可使用。
