# Argus Safety Predictor Nano — 自動更新機制與安全升級實作規格書 (Implementation Spec)

本規格書彙整 Wayfinder Issue 76 ~ 80 之決策與驗證成果，提供完整的架構定義、配置檔規格、模組設計規範、腳本範本與測試驗證矩陣，作為系統開發與維運部署之權威工程基準。

---

## 1. 資料結構與配置檔定義 (`config.yaml`)

在 `config.yaml` 根層級擴充 `auto_update` 區塊，遵循向下相容原則（若未配置則停用自動更新）：

```yaml
# ==============================================================================
# 自動更新與安全升級設定 (Auto-Update Configuration)
# ==============================================================================
auto_update:
  enabled: true                         # 是否啟用自動更新模組
  app_id: "argus_predictor"              # App Management API 登錄之應用程式識別碼
  channel: "stable"                      # 更新通道: stable (正式版), beta (測試版)
  check_interval_seconds: 3600           # 自動輪詢週期 (秒，預設 1 小時，最小 300 秒)
  check_on_startup: true                 # 系統開機啟動後是否立即執行一次檢查
  mode: 2                                # 運行模式: 1 (無人值守自動替換重啟), 2 (提示手動確認重啟，預設)
  
  # API 網址與連線設定 (支援 Failover 與退避鏈)
  base_urls:
    - "http://tncimweb.cminl.oa/appmanagementapi"
    - "http://tnvcimweb1.cminl.oa/appmanagementapi"
  api_key: ""                            # 選擇性: 若未填寫則自動繼承 ums_api_key 或環境變數
  timeout_seconds: 30                    # 請求與下載逾時時間 (秒)
  max_retries: 3                         # 瞬態錯誤重試次數 (含 Jitter 指數退避)
  download_chunk_size: 1048576           # 串流下載分塊大小 (Bytes，預設 1MB)
  
  # 路徑與儲存目錄設定
  staging_dir: "updates/staging"         # 下載解壓縮驗證之暫存目錄
  backup_dir: "argus_predictor_bak"      # 前一版本備份目錄
  healthcheck_timeout_seconds: 30        # 重啟後健康檢查評估窗口 (秒，預設 30 秒)
```

---

## 2. 核心模組架構與職責劃分

```text
src/argus/
├── core/
│   └── config_manager.py              # 擴充 auto_update schema 解析與驗證
├── integration/
│   └── app_update_client.py           # App Management API 客戶端 (Version/DownloadInfo/Stream)
├── updates/
│   └── update_manager.py              # 更新生命週期狀態機、背景輪詢、佇列廣播與重啟調度
└── web/
    ├── web_ui.py                      # 提供 /api/health、/api/update/* 端點與 SSE 串流
    └── templates/
        └── index.html                 # 導覽列版本徽章、更新彈窗、進度條與重啟遮罩
scripts/
├── install.sh                         # 解壓升級/安裝腳本 (零資料遺失、保留 config/models/logs)
├── run.sh                             # 邊緣端常駐守護啟動腳本 (Exit 42 監聽重啟、工作目錄鎖定)
└── updater_helper.sh                  # 獨立 Detached 背景輔助進程 (直接執行二進位時之備用重啟器)
```

### 2.1 `AppUpdateClient` (`src/argus/integration/app_update_client.py`)
- **責任**：與外部 App Management API 進行通訊，處理版本查詢、元數據解析與二進位串流下載。
- **關鍵方法**：
  - `check_latest_version(current_version: str) -> Optional[UpdateCandidate]`：比對 SemVer，回傳是否具備可更新版本及 Release Notes。
  - `get_download_info(version: str) -> UpdateDownloadInfo`：取得檔案 `owner` 與檔案路徑。
  - `download_package(owner: str, version: str, file_path: str, dest_path: str, progress_callback=None)`：串流寫入本機暫存檔，每 200ms 觸發回呼提供傳輸統計。

### 2.2 `UpdateManager` (`src/argus/updates/update_manager.py`)
- **責任**：狀態機維護、執行緒安全 SSE 佇列廣播、背景輪詢定時器、暫存解壓與安全重啟呼叫。
- **狀態枚舉**：
  `IDLE`, `CHECKING`, `AVAILABLE`, `DOWNLOADING`, `STAGING`, `READY_TO_INSTALL`, `RESTARTING`, `HEALTHCHECK`, `SUCCESS`, `ROLLBACK`, `FAILED`。
- **關鍵方法**：
  - `start_background_checker()`：啟動背景定時守護執行緒。
  - `trigger_check()` / `trigger_download()` / `trigger_restart()`：控制狀態流轉。
  - `stage_and_verify(tar_path: str) -> bool`：解壓縮至 staging 目錄，驗證 binary 存在性與完整性。
  - `subscribe() -> Queue` / `broadcast()`：支援多個 SSE 客戶端無鎖廣播。

### 2.3 `scripts/install.sh` 與 `scripts/run.sh`
- **`install.sh`**：
  - 支援 `-y` / `--non-interactive` 參數。
  - 自動偵測是否為更新模式，將現有目錄備份至 `argus_predictor_bak/`（`models/` 採 `cp -al` 硬連結秒級備份）。
  - 安全置換動態庫 `_internal/`，嚴格保留 `config.yaml`、`models/` 與 `logs/`。
  - 自動賦予所有二進位與 shell 腳本 `chmod +x`。
- **`run.sh`**：
  - 強制以 `realpath` 鎖定 CWD 工作目錄，遵循 ADR-005。
  - 設定 RPi 5 效能環境變數 (`PYTHONUNBUFFERED=1`, `OMP_NUM_THREADS=4`, `MALLOC_ARENA_MAX=2`)。
  - 外層包裝 `while true` 守護迴圈：當二進位程式以 `Exit Code 42` 結束時，自動以最新目錄之程式重新啟動；若正常退出 (Exit 0) 則結束迴圈。

---

## 3. Web UI 端點與互動介面規範

### 3.1 REST API & SSE 規格
- `GET /api/health`：三階段探針。回傳 `status: "healthy"` (HTTP 200) 或 `status: "starting"` (HTTP 503)，包含 `inference_ready` 與 `first_frame_inferred`。
- `GET /api/update/status`：取得當前更新狀態、進度與版本詳情。
- `POST /api/update/check`：手動觸發版本檢查。
- `POST /api/update/download`：手動觸發背景下載。
- `POST /api/update/restart`：觸發目錄原子替換並以 Exit 42 退出重啟。
- `GET /api/update/stream`：SSE 端點 (`Content-Type: text/event-stream`)，實時推送狀態 JSON。

### 3.2 前端互動體驗
- **導覽列版本標籤**：點擊開啟更新視窗。
- **動態呼吸發光徽章**：`AVAILABLE` 時顯示綠光 `[ 🚀 新版本可用: vX.Y.Z ]`；`READY_TO_INSTALL` 時顯示橘黃呼吸光 `[ ⚠️ 更新就緒，點擊重啟套用 ]`。
- **全螢幕重啟遮罩**：顯示 30 秒倒數計時，每 1.5 秒自動輪詢 `/api/health`。健康確立後提示「升級成功」並自動刷新頁面；若發生回滾則彈出警示並停止倒數。

---

## 4. 30 秒健康檢查與自動回滾容錯驗證清單

```text
[啟動新版二進位] ──寫入 .update_in_progress──> [30 秒看門狗評估窗口]
                                                    │
             ┌──────────────────────────────────────┴──────────────────────────────────────┐
             ▼                                                                             ▼
   [指標全數在 30 秒內滿足]                                                       [超時 / 崩潰 / 探針失敗]
   - 進程存活 (PID active)                                                         - 行程退出碼 != 42
   - HTTP 200 (healthy)                                                           - 30s 未取得 healthy
   - 推論首幀完成 (inferred)                                                       - 動態庫 missing SIGSEGV
             │                                                                             │
             ▼                                                                             ▼
   [健康確立 (Commit)]                                                           [自動回滾五步驟 (Rollback)]
   1. 移除 .update_in_progress                                                    1. 強制終止殘留進程 (SIGKILL)
   2. 記錄 [COMMITTED] 至日誌                                                     2. 隔離失敗現場至 failed_<ts>/
   3. 狀態機轉為 SUCCESS                                                          3. 原子還原 bak/ 至 argus_predictor/
   4. 保留 bak/ 作為下次備份                                                      4. 重新啟動上一版本
                                                                                  5. 寫入 rollback.log 並亮起 Web 警示
```

---

## 5. 測試與品質驗證矩陣

| 測試層級 | 測試檔案 | 驗證範疇 | 預期結果 |
| :--- | :--- | :--- | :--- |
| **單元測試** | `tests/unit/test_app_update_client.py` | SemVer 2.0 解析、prerelease 過濾、API Key 退避鏈、分塊寫入與回呼 | 通過，無外部網路依賴 |
| **單元測試** | `tests/unit/test_update_manager.py` | 狀態機各狀態轉換、SSE 佇列廣播、模擬下載進度計算、重啟退出碼 | 通過，狀態轉換無死鎖 |
| **整合測試** | `tests/integration/test_web_ui_update.py` | `/api/health` 探針、`/api/update/*` REST API、SSE 串流連線與首頁 Modal | 通過，所有端點皆回傳規範格式 |
| **整合測試** | `tests/integration/test_install_script.py` | `install.sh` 首次安裝與升級模式、檔案備份、保留 `config.yaml`/`models/` | 通過，驗證檔案一致性 |
| **E2E 測試** | `tests/e2e/test_auto_update_and_rollback.py` | 模擬新版程式崩潰，驗證守護腳本於 30 秒內自動還原 `argus_predictor_bak/` 並復原開機 | 通過，成功重啟且 Web UI 顯示回滾告警 |
