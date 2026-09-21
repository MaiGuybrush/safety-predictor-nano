# 03 — 原子目錄替換與行程自我重啟生命週期 (Atomic Replacement & Restart Lifecycle)

Type: grilling
Status: resolved
Blocked by: 01, 02

## Question

在 Linux / RPi 5 手動執行 `./argus_predictor/argus_predictor`（非 systemd 託管）情境下，執行中的行程如何進行非破壞性的目錄替換？當更新模式為 1（自動替換重啟）或模式 2（Web UI 點擊重啟）時，如何透過背景輔助更新行程（updater helper / watchdog / execv）完成目錄 rename (`argus_predictor` -> `argus_predictor_bak`)、進程終止、新版本啟動與 stdout/stderr 日誌銜接？

## Investigation Scope

1. **Linux 檔案鎖定與目錄替換原理**:
   - Linux 允許 unlink 或 rename 正在被執行的二進位檔案，但 `_internal/` 下正在被動態鏈結的 `.so` 檔案若直接被寫入覆蓋可能導致 SIGSEGV。
   - 探討「目錄階層原子替換（Directory Atomic Swap）」模式：
     - 解壓至暫存目錄 `argus_predictor_staging/`
     - 遷移/保留使用者檔案（`config.yaml`, `models/`, `logs/`）
     - 透過獨立輔助行程將現有 `argus_predictor/` 重新命名為 `argus_predictor_bak/`，並將 `argus_predictor_staging/` 重新命名為 `argus_predictor/`。
2. **行程自我終止與重啟策略**:
   - 在非 systemd 管理的手動終端機執行下：
     - 若使用 `os.execv`：能否直接接管現有 PID 與終端機 IO？但在 onedir 目錄替換時，舊進程已加載舊 shared library，直接 exec 可能存在動態庫路徑不一致風險。
     - 若使用外部獨立 Helper 腳本（`scripts/updater_helper.sh`）：由主行程以 `subprocess.Popen` 分離（nohup/setsid）啟動 Helper 腳本，主行程優雅關閉（釋放 RTSP 串流、儲存日誌並退出 PID），Helper 等待主行程退出後執行目錄替換並啟動新版 `argus_predictor`。
3. **模式切換與生命週期狀態機**:
   - 狀態機流轉：`IDLE` -> `CHECKING` -> `AVAILABLE` -> `DOWNLOADING` -> `READY_TO_INSTALL` -> `INSTALLING/RESTARTING` -> `ROLLBACK_PENDING` -> `SUCCESS`。
   - 模式 1：下載驗證完成後直接觸發重啟。
   - 模式 2：下載驗證完成後進入 `READY_TO_INSTALL`，於 Web UI 亮起提示徽章，等待操作員確認或呼叫 `/api/system/apply_update` 才觸發重啟。

## Answer

1. **目錄替換 (Staging & Atomic Swap)**：
   - 嚴禁於運行目錄原地解壓以防動態庫載入 SIGSEGV。下載後先解壓至 `updates/staging/` 暫存目錄進行校驗。
   - 替換時先備份至 `argus_predictor_bak/`（`models/` 採硬連結秒級建立且不佔空間），再將新版檔案安全同步至正式目錄，無損保留既有 `config.yaml`、`models/` 與 `logs/`。

2. **自我重啟架構（雙重保障機制）**：
   - **機制一（推薦路徑）：`run.sh` 守護迴圈監聽 Exit Code 42 (RESTART_FOR_UPDATE)**：
     - 使用者透過 `./run.sh` 啟動時，`run.sh` 內建外層監聽迴圈。主程式就緒後呼叫 `sys.exit(42)`，`run.sh` 自動重新呼叫最新版二進位檔。
   - **機制二（容錯路徑）：獨立 Detached `updater_helper.sh`**：
     - 若使用者直接執行二進位檔，主程式以 `subprocess.Popen(..., start_new_session=True)` 啟動背景 Helper 腳本接管。主程式優雅釋放 RTSP 串流與日誌並退出（PID 消失），Helper 執行替換後以 `nohup ./run.sh &` 喚起新版程式。

3. **狀態機與雙模式切換**：
   - 狀態機流轉：`IDLE` -> `CHECKING` -> `AVAILABLE` -> `DOWNLOADING` -> `STAGING` -> `READY_TO_INSTALL` -> `RESTARTING` -> `HEALTHCHECK`。
   - **模式 1（無人值守）**：進入 `READY_TO_INSTALL` 後延遲 3 秒直接重啟。
   - **模式 2（提示確認，預設）**：停留在 `READY_TO_INSTALL`，Web UI 頂端顯示徽章，等待操作員確認觸發後才重啟。

4. **Web UI 重啟體驗**：
   - 觸發重啟時 Web UI 顯示半透明全螢幕遮罩與倒數進度條。
   - 前端背景以 1.5 秒間隔自動輪詢 `/api/health`，一旦新版本 30 秒內就緒立即自動重載頁面並提示成功。

