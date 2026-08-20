Status: ready-for-agent

# PRD: 日誌每日輪轉 (Daily Rolling) 與 3 天保留機制及 logs 目錄歸檔

**專案**：Argus Safety Predictor Nano  
**狀態**：Ready for Agent  
**標籤**：`ready-for-agent`, `Kind/Feature`, `logging`, `storage`, `web-ui`

---

## Problem Statement

目前 Argus Safety Predictor Nano 的效能日誌（`performance.log`）與偵測日誌（`detections.log`）直接寫入專案根目錄，且使用無上限增長的單一檔案記錄（`logging.FileHandler`）。

在 Raspberry Pi 5 等邊緣裝置長期全天候（24/7）運作時，這會造成兩個主要問題：
1. **儲存空間耗盡風險**：日誌檔案隨時間無限增長，可能耗盡邊緣設備有限的 SD 卡或 NVMe 儲存空間，導致系統不穩定或無法寫入。
2. **目錄混亂與維運困難**：多種日誌與核心程式碼、設定檔混合置於根目錄，缺乏統一的歸檔目錄與輪轉機制，現場維運人員難以依日期排查歷史事件與效能趨勢。

---

## Solution

在系統中導入結構化的日誌管理機制，包含每日定時輪轉、儲存目錄隔離與保留天數控制：

1. **獨立日誌目錄 (`logs/`)**：預設將效能日誌與偵測日誌路徑指向 `logs/` 子目錄（`logs/performance.log` 與 `logs/detections.log`），並在系統初始化與寫入時自動建立目錄。
2. **每日自動輪轉 (Daily Rolling)**：將日誌處理器改為基於時間的輪轉器（`TimedRotatingFileHandler`），於每日午夜（Midnight）自動輪轉日誌。
3. **歷史檔案保留限制 (Backup Retention)**：預設保留最近 3 天的歷史日誌檔案，超過保留期的舊日誌自動清理釋放空間。
4. **可配置化與 Web UI 同步**：在 `config.yaml` 與 Web UI 系統設定中提供「日誌保留天數」（`log_backup_count`，預設為 3 天）及日誌路徑設定，並支援熱重載（Hot Reload）安全釋放檔案控制代碼。

---

## User Stories

1. 作為邊緣設備維運工程師，我希望效能日誌與偵測日誌預設儲存在 `logs/` 目錄中，以便專案根目錄保持整潔且便於集中管理與備份日誌。
2. 作為邊緣設備維運工程師，我希望日誌檔案在每日午夜自動進行輪轉（Daily Rolling），以便依據日期區間快速查找特定日期的偵測事件與效能指標。
3. 作為邊緣設備維運工程師，我希望系統預設保留最近 3 天的歷史日誌檔案並自動清除過期日誌，以便避免邊緣設備磁碟空間被日誌塞滿。
4. 作為邊緣設備維運工程師，我希望在 `config.yaml` 中可以自訂日誌路徑與保留天數（`log_backup_count`），以便根據設備儲存容量彈性調整保留策略。
5. 作為邊緣設備維運工程師，我希望在 Web UI 的「系統參數」頁面中能查看並修改「日誌保留天數（天）」以及日誌檔名，以便在瀏覽器端直觀調整設定。
6. 作為邊緣設備維運工程師，我希望在 Web UI 儲存新的日誌設定或保留天數後，系統能即時熱重載（Hot Reload）套用新設定，無需手動重新啟動主程式。
7. 作為系統開發者，我希望當配置的日誌目錄不存在時，系統能自動建立該目錄，避免因目錄不存在而拋出 I/O 例外或中斷推論服務。
8. 作為系統開發者，我希望在動態熱重載日誌配置時，系統能乾淨關閉舊的日誌 Handler，避免在 Windows 或 Linux 環境下發生檔案控制代碼鎖定或重複輸出日誌的問題。
9. 作為系統開發者，我希望舊有存在於根目錄的歷史日誌不受影響，新日誌直接平滑寫入 `logs/` 目錄，確保向下相容性。
10. 作為系統開發者，我希望日誌寫入與輪轉皆採用 UTF-8 編碼，以便正確記錄多語系串流名稱、標籤與偵測細節。

---

## Implementation Decisions

### 1. 組態結構與預設值調整
- 組態模型新增 `log_backup_count` 整數欄位，預設為 `3`。
- `log_file` 預設值調整為 `logs/performance.log`。
- `detection_log_file` 預設值調整為 `logs/detections.log`。
- 支援任意相對或絕對路徑，若路徑包含目錄結構，記錄器需自動遞迴建立該目錄。

```yaml
log_file: logs/performance.log
detection_log_file: logs/detections.log
log_backup_count: 3
```

### 2. 日誌記錄模組改進
- 將日誌寫入處理器由一般檔案處理器升級為時間輪轉處理器（`TimedRotatingFileHandler`）。
- 輪轉週期設定為每日午夜（`when="midnight", interval=1`）。
- 保留數量設定為 `backupCount=log_backup_count`。
- 檔案編碼明確指定為 UTF-8。
- 輪轉後的舊檔案命名遵循標準後綴格式（如 `performance.log.YYYY-MM-DD`）。
- 記錄器初始化時，先關閉並清除既有同名 Logger 的所有舊 Handler，再掛載新 Handler，確保熱重載時不發生控制代碼洩漏與重複寫入。

### 3. 主程式動態重載與生命週期整合
- 主流程初始化與動態設定檢查時，讀取並傳入 `log_backup_count`。
- 當設定變更時，透過重新建立記錄器物件完整套用新路徑與保留參數。

### 4. Web UI 設定介面與表單處理
- 在前端介面的日誌設定區塊新增「日誌保留天數」數字輸入欄位（預設值為 `config.get('log_backup_count', 3)`，最小值 `1`）。
- 後端設定儲存處理常式解析 `log_backup_count`，若未提供或格式不符則採用預設值 `3` 並寫回設定檔。

---

## Testing Decisions

### 1. 測試品質原則
- 僅測試外部行為（檔案是否正確建立在指定目錄、日誌是否正確寫入、輪轉參數與保留天數是否生效、Web UI API 是否正確保存組態），不依賴內部私有實作細節。

### 2. 測試接縫 (Seams)
- **記錄器行為測試接縫 (Logger Integration Seam)**：
  - 驗證指定 `logs/` 或自訂子目錄時，目錄能被自動建立。
  - 驗證效能統計日誌與物件偵測日誌能正確寫入目標檔案。
  - 驗證時間輪轉處理器正確配置了 `when='midnight'` 與 `backupCount`。
  - 驗證模擬多次輪轉時，保留的歷史檔案數量不超過指定的 `backupCount`。
  - 驗證重複初始化或動態重新配置記錄器時，舊 Handler 能被乾淨關閉與替換，日誌無重複輸出。
- **Web UI 設定存取接縫 (Web UI Config Seam)**：
  - 驗證透過 POST 請求更新 `log_file`、`detection_log_file` 與 `log_backup_count` 時，組態管理器與設定檔皆正確持久化新參數。

### 3. 既有先例 (Prior Art)
- 參考專案現有的 `test_web_ui_config_save.py` 與 `test_config_manager.py` 測試架構。

---

## Out of Scope

1. 日誌壓縮打包（如自動壓縮為 `.gz` 或 `.zip`）不在本階段範圍，維持標準純文字輪轉。
2. Web UI 線上即時日誌檢視器 / 日誌下載端點（目前由既有維運工具或終端機直接查看）。
3. 根目錄既有舊日誌檔案的主動遷移或刪除（由維運人員手動處置或保留現狀）。

---

## Further Notes

- 在 Windows 作業系統環境下，若有其他行程或未關閉的 Handler 鎖定日誌檔案，時間輪轉時可能觸發 `PermissionError`；因此在記錄器重新初始化時，顯式關閉既有 Handler 是確保跨平台穩定性的關鍵實作細節。
