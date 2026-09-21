# 05 — Web UI 更新狀態展示、通知與 SSE 下載進度條原型 (Web UI Update UX & SSE Status)

Type: prototype
Status: resolved
Blocked by: 03

## Question

Web UI 如何向使用者呈現版本狀態（當前版本 vs 最新版本、Release Notes）、更新檢查提示（小紅點/Toast/Navbar Badge）、手動觸發「檢查更新」與「立即安裝/重啟」的互動介面，以及透過 SSE/WebSocket 即時展示下載解壓進度？

## Investigation Scope

1. **導覽列與版本視覺反饋**:
   - 頂部導覽列顯示當前運行的 App 版本（如 `v1.2.0`）。
   - 若偵測到新版（狀態為 `AVAILABLE` 或 `READY_TO_INSTALL`），導覽列顯示閃爍徽章或提示通知（如 `新版本可用: v1.3.0`）。
2. **系統設定對話框 (Update Modal)**:
   - 點擊後開啟版本更新詳情彈窗：
     - 當前運行版本、平台最新版本、發布時間、Release Notes 說明。
     - 操作按鈕：
       - 「檢查最新版本」（主動呼叫 API）
       - 「下載並更新」（模式 2 下之手動觸發）
       - 「立即重啟套用」（當新版本下載解壓就緒後）
3. **即時進度與狀態廣播**:
   - 利用現有 SSE (Server-Sent Events) 通道（如 `/stream_stats` 或專屬 `/stream_update_status`），即時推送：
     - 下載進度百分比（`progress: 45%`、`downloaded: 45MB/100MB`）。
     - 解壓縮狀態。
     - 準備重啟倒數計時（`倒數 5 秒後重啟服務...`）。
   - 斷線重連偵測：更新重啟期間 Web UI 自動輪詢後端 `/api/health`，一旦伺服器重啟完成，自動重新整理頁面並跳出「已成功升級至新版本」之通知。

## Answer

本原型票券已完整實作並驗證 Argus Safety Predictor Nano 之 Web UI 更新互動體驗、SSE 狀態廣播通道、全螢幕重啟健康檢查探針與獨立原型檢視器。

---

### 1. 導覽列與版本視覺反饋規範 (Navbar & Visual Indicators)

1. **當前版本互動標籤 (`.version-tag`)**：
   - 位於頂部標題 `ARGUS // PREDICTOR_NANO` 右側，顯示目前載入之系統版本（如 `v1.0.0`）。
   - 採用 Cyberpunk 青藍發光外框 (`--border-cyan: #004455`, `--cyan: #00e5ff`)，支援游標懸停微光發亮（`box-shadow: 0 0 10px rgba(0, 229, 255, 0.4)`），點擊即可直接開啟軟體更新管理對話框。
2. **動態更新提示徽章按鈕 (`#update-badge-btn`)**：
   - 當更新狀態機進入 `AVAILABLE`（有新版可用）或 `READY_TO_INSTALL`（更新包下載驗證完成）時，導覽列右側即時浮現呼吸發光按鈕：
     - **新版可用 (AVAILABLE)**：`[ 🚀 新版本可用: v1.1.0 ]`（青綠色漸層，點擊開啟更新視窗觸發下載）。
     - **更新就緒 (READY_TO_INSTALL)**：`[ ⚠️ 更新就緒，點擊重啟套用 (v1.1.0) ]`（橘黃色強烈呼吸光暈，提醒操作員排程套用）。
   - 按鈕具備 `@keyframes update-glow` 雙向發光動畫，即便操作員未主動開啟彈窗，亦能在最顯眼處獲得視覺提醒。

---

### 2. 軟體更新管理彈窗 (Update Modal) 設計

彈窗嚴格延續系統既有深黑終端美學 (`--bg: #050505`、`--panel: #0a0a0a`、`Consolas / SFMono` 等寬字型)，內部元件包含：

1. **版本資訊矩陣 (4-Card Metric Grid)**：
   - **目前運行版本 (Current Version)**：`v1.0.0`
   - **平台最新版本 (Latest Version)**：`v1.1.0`（若已是最新版顯示 `---`）
   - **發布時間 (Release Date)**：`2026-09-21 12:00:00`
   - **更新模式 (Update Mode)**：`提示確認 (Notify)` / `無人值守 (Unattended)`
2. **版本發布說明終端框 (Release Notes Terminal)**：
   - 深綠漸層終端背景 (`#020802`)，自動格式化呈現 Changelog、新增功能、效能優化與 Bug 修復項目。
3. **實時下載與解壓進度條 (`#up-progress-container`)**：
   - 平時隱藏，於 `DOWNLOADING`、`STAGING`、`READY_TO_INSTALL` 期間展開。
   - 頂部顯示當前任務說明與百分比數值（如 `正在下載更新安裝包... 68.5%`）。
   - 雙層霓虹進度軌道 (`.update-progress-track` + `.update-progress-fill`)。
   - 底部顯示傳輸容量進度與即時下載速率（如 `68.5 MB / 100.0 MB // 12.4 MB/s`）。
4. **操作按鈕矩陣**：
   - `[ ↻ 檢查最新版本 ]`：手動向後端 App Management API 發動查詢。
   - `[ ⬇ 下載更新包 ]`：僅於 `AVAILABLE` 或失敗後亮起，點擊在背景啟動串流下載。
   - `[ ⚡ 立即重啟套用 ]`：於 `READY_TO_INSTALL` 時啟動亮橘色高光外框，點擊確認後觸發原子重啟流程。
   - `[ 關閉 ]`：關閉彈窗，背景下載與輪詢仍持續進行。

---

### 3. SSE 即時廣播通道與 API 規格

1. **端點規格表**：
   | HTTP 方法 | 路徑 | 說明 | 狀態碼 |
   | :--- | :--- | :--- | :--- |
   | `GET` | `/api/health` | 三階段健康檢查探針 (Process/HTTP/Inference) | 200 (Healthy) / 503 (Starting) |
   | `GET` | `/api/update/status` | 取得當前更新狀態機資訊與進度 | 200 OK |
   | `POST` | `/api/update/check` | 手動觸發最新版本檢查 | 200 OK |
   | `POST` | `/api/update/download` | 觸發更新檔下載與 Staging 解壓 | 200 OK |
   | `POST` | `/api/update/restart` | 觸發重啟與原子目錄替換 | 200 OK |
   | `GET` | `/api/update/stream` | SSE (Server-Sent Events) 事件廣播通道 | 200 (`text/event-stream`) |

2. **SSE 廣播 Payload JSON 結構**：
   ```json
   {
     "state": "DOWNLOADING",
     "current_version": "1.0.0",
     "target_version": "1.1.0",
     "release_date": "2026-09-21 12:00:00",
     "release_notes": "◈ 系統安全性與效能維護更新 (v1.1.0)\n- [優化] 支援 App Management API 原子升級\n- [新增] Web UI 實時下載進度條與 SSE 廣播狀態機",
     "progress": 68.5,
     "downloaded_bytes": 71827456,
     "total_bytes": 104857600,
     "speed_bytes_sec": 5242880,
     "speed_text": "5.0 MB/s",
     "message": "正在下載更新包... (68.5 MB / 100.0 MB, 5.0 MB/s)",
     "error": null,
     "mode": "notify",
     "rollback_occurred": false,
     "restart_countdown": null,
     "timestamp": 1726915200.0
   }
   ```

---

### 4. 重啟倒數、探針輪詢與自動重連機制 (Restart Overlay & Recovery)

1. **全螢幕遮罩啟動**：
   - 當使用者點擊「立即重啟套用」或狀態機進入 `RESTARTING`，Web UI 自動關閉編輯彈窗並喚起全螢幕半透明遮罩 (`#update-restart-overlay`)。
   - 畫面中央呈現 30 秒大型倒數計時數字與進度條，並明確提示：「正在進行二進位目錄原子替換與重啟程序... 請勿切斷電源或關閉瀏覽器。」
2. **探針輪詢與自動重新整理**：
   - 前端啟動每隔 1.5 秒之輪詢定時器，持續向本機端點 `GET /api/health` 發送探針。
   - **升級成功情境**：
     - 一旦收到 HTTP 200 且 `data.status === "healthy"`（且版本確立）：
     - 畫面轉換為綠色成功看板：「✓ 系統升級成功！核心與推論管線已全數就緒。成功升級至新版本 v1.1.0！」
     - 延遲 1.8 秒自動執行 `window.location.reload()`，無縫載入最新版 Web 介面。
   - **回滾容錯情境**：
     - 若 `/api/health` 回報 `rollback_occurred: true`：
     - 畫面切換為警示色：「⚠️ 升級檢查失敗，已自動安全回滾至原版本 v1.0.0！」
     - 停止倒數，並提供「重新載入頁面」手動確認按鈕，避免使用者因畫面凍結而感到困惑。

---

### 5. 原型交付資產與自動化驗證成果

1. **交付原始碼與前端模板**：
   - [`src/argus/updates/update_manager.py`](file:///D:/Projects/argus/safety-predictor-nano/src/argus/updates/update_manager.py)：包含完整狀態機、執行緒安全佇列廣播器、下載模擬與回滾控制。
   - [`src/argus/web/web_ui.py`](file:///D:/Projects/argus/safety-predictor-nano/src/argus/web/web_ui.py)：整合 `/api/health`、`/api/update/*` 與 SSE `/api/update/stream` 端點。
   - [`src/argus/web/templates/index.html`](file:///D:/Projects/argus/safety-predictor-nano/src/argus/web/templates/index.html)：實作導覽列版本徽章、更新彈窗、進度條、全螢幕重啟遮罩與 `initUpdateSse()` 前端客戶端。
2. **獨立可互動原型展示**：
   - [`.scratch/auto-update-mechanism/prototypes/update_modal_prototype.html`](file:///D:/Projects/argus/safety-predictor-nano/.scratch/auto-update-mechanism/prototypes/update_modal_prototype.html)：獨立單頁 HTML，內建狀態模擬控制器（可直接在任何瀏覽器中體驗 IDLE、AVAILABLE、下載進度、重啟倒數與回滾警示）。
3. **自動化測試覆蓋**：
   - [`tests/unit/test_update_manager.py`](file:///D:/Projects/argus/safety-predictor-nano/tests/unit/test_update_manager.py)：4 項單元測試全數通過（狀態機轉換、SSE 訂閱佇列、模擬下載、回滾模擬）。
   - [`tests/integration/test_web_ui_update.py`](file:///D:/Projects/argus/safety-predictor-nano/tests/integration/test_web_ui_update.py)：6 項端點整合測試全數通過（`/api/health`, `/api/update/status`, `/api/update/check`, `/api/update/download`, `/api/update/restart`, `/api/update/stream`, 首頁 Modal 模板渲染）。

