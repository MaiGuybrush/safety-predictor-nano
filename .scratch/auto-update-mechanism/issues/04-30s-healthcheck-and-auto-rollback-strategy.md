# 04 — 30 秒健康狀態判定與自動回滾容錯策略 (Healthcheck & Auto-Rollback Strategy)

Type: grilling
Status: resolved
Blocked by: 03

## Question

如何定義新版本啟動後的「30 秒健康狀態判定標準」（例如：Web UI 正常回應 200、InferenceEngine 成功載入模型並產生第一幀推論），以及當偵測到啟動失敗或超時 crash 時，背景守護腳本如何安全自動回滾至 `argus_predictor_bak/`、恢復先前運行版本並記錄失敗日誌？

## Investigation Scope

1. **健康指標定義 (Health Criteria)**:
   - 階段 1（行程存活）：啟動後進程存在且未立即 exit (code != 0)。
   - 階段 2（Web 服務就緒）：向本機端點（如 `http://127.0.0.1:8188/api/health`）發出 HTTP GET 獲得 200 OK。
   - 階段 3（推論管線就緒）：InferenceEngine 成功初始化模型權重，或首輪推論至少成功完成一次無例外。
   - 判定窗口：設定為 30 秒。若 30 秒內上述指標全數達成，向看門狗/守護行程發出「健康確立 (Commit Update)」信號，刪除舊版備份或標記升級成功。
2. **自動回滾程序 (Rollback Procedure)**:
   - 若 30 秒內發生以下任一狀況：
     - 主行程崩潰異常終止。
     - `/api/health` 連續無法連線或逾時。
     - 嚴重語法/相依庫缺失錯誤（如缺少 `.so`）。
   - 守護腳本立即接管：
     - 強制終止任何異常殘留進程。
     - 將 `argus_predictor/` 重新命名為 `argus_predictor_failed_<timestamp>/`。
     - 將 `argus_predictor_bak/` 還原為 `argus_predictor/`。
     - 啟動還原後的上一版本。
     - 寫入回滾事件與告警至 `logs/update_rollback.log`，並於 Web UI 顯示升級失敗警示訊息。

## Answer

1. **三階段健康指標判定標準 (Three-Stage Health Criteria)**：
   - **階段 1：進程存活 (Process Liveness)**：
     - 二進位主程式啟動後取得 PID，外部守護行程（`run.sh` / `updater_helper.sh`）以 `kill -0 $PID` 進行每秒存活監聽。
     - 若進程在 30 秒窗口內提前退出且退出碼非 `42`（非自我重啟），立即判定崩潰並中斷等待。
   - **階段 2：HTTP 服務與探針就緒 (HTTP Readiness)**：
     - 守護行程每隔 1.5 秒向本機端點 `http://127.0.0.1:8188/api/health` 發出 GET 請求（連線逾時 1 秒）。
     - `/api/health` 回傳結構包含：
       ```json
       {
         "status": "healthy",
         "version": "0.2.0",
         "uptime_seconds": 8.5,
         "web_ui": true,
         "inference_ready": true,
         "first_frame_inferred": true,
         "active_streams": 1
       }
       ```
     - 只有在 Web 伺服器監聽就緒、模型權重加載成功且首幀推論完成後，該端點才回傳 HTTP 200 與 `status: "healthy"`；若仍在初始化則回傳 `status: "starting"`（HTTP 503）。
   - **階段 3：推論管線就緒 (Inference Pipeline Verification)**：
     - 核心 `initialize_runtime()` 載入模型且 `InferenceEngine` 初始化無例外。
     - 影像管線取得第一幀畫面並成功執行 `infer()`，全域狀態標記 `FIRST_INFERENCE_DONE = True`。
     - 若模型損毀或動態庫（如 OpenCV/ONNX/NCNN）缺失引發未捕獲例外，程式崩潰並由階段 1 捕獲；若推論超時卡死則由 30 秒窗口超時捕獲。

2. **30 秒評估窗口與健康確立 (30s Window & Commit Mechanism)**：
   - **更新標記檔 (`.update_in_progress`)**：
     - 目錄替換完成並啟動新版本前，寫入 `.update_in_progress` 標記檔（內含 `target_version`, `timestamp`, `backup_dir`）。
   - **健康確立 (Commit)**：
     - 一旦在 30 秒倒數計時內收到 `/api/health` 回傳 `status: "healthy"`：
       1. 守護行程移除 `.update_in_progress`。
       2. 於 `logs/update.log` 寫入確認紀錄：`[COMMITTED] Version X.Y.Z verified healthy in N.Ns`。
       3. 備份目錄處置：保留 `argus_predictor_bak/`（做為單一備份回退保險，直到下次升級覆蓋；模型權重採用硬連結不佔用磁碟空間）。
       4. 更新狀態機流轉至 `SUCCESS`。

3. **自動回滾容錯處置管線 (Automated Rollback Pipeline)**：
   - **觸發條件矩陣**：
     - 主行程崩潰異常終止（Exit Code != 0 且 != 42）。
     - 30 秒窗口耗盡，`/api/health` 仍未就緒或持續連線拒絕。
     - 缺失動態庫或語法錯誤導致開機失敗。
   - **回滾五步驟標準程序**：
     1. **清理異常殘留進程**：守護腳本發送 `SIGTERM`，等待 3 秒未退出則發送 `SIGKILL -9`，徹底釋放 8188 埠與攝影機連線。
     2. **隔離失敗現場 (Quarantine)**：將 `argus_predictor/` 重新命名為 `argus_predictor_failed_<timestamp>/`（保留 crash 現場日誌與 binary，限制系統僅保留最新 1 份 failed 目錄以保護磁碟空間）。
     3. **原子還原備份**：將 `argus_predictor_bak/` 重新命名回 `argus_predictor/`。
     4. **喚醒穩定版本**：透過 `./run.sh` 重新啟動還原後的舊版程式。
     5. **記錄與回報**：寫入失敗日誌 `logs/update_rollback.log`（記錄回滾原因、目標版本、崩潰退出碼與 stderr 尾部日誌），並建立 `.rollback_alert` 標記檔。

4. **Web UI 告警與死迴圈防護 (Web UI Notification & Rollback Loop Guard)**：
   - **Web UI 警告橫幅**：舊版重啟後，後端讀取 `.rollback_alert` 檔案，Web UI 頂部注入紅色醒目橫幅警告操作員：「升級至 vX.Y.Z 失敗並已自動回滾至 vA.B.C，詳細原因請參閱 logs/update_rollback.log」，操作員點擊確認後可清除標記。
   - **死迴圈防護 (Rollback Loop Guard)**：若回滾後舊版本啟動依然崩潰，看門狗檢測到已執行過回滾，立即進入 `FATAL_HALT` 狀態並終止自動重試，在終端印出致命錯誤，防止邊緣設備無止盡重啟打滿磁碟日誌。

