# 01 — 診斷封包收集器與敏感資料脫敏模組 (Diagnostic Bundle Collector)

Gitea Issue: #60
Type: task
Status: resolved
Blocked by: None

## Question
如何可靠地收集系統執行日誌、環境資訊、捕捉 Fatal Crash Traceback，並在安全遮蔽配置檔中敏感憑證的前提下，將其壓縮打包為標準診斷 ZIP 檔？

## Tasks
- [x] 於系統入口 (`main.py` 及相關模組) 實作 `sys.excepthook` 全域攔截器，將未捕獲的例外與完整堆疊輸出至 `logs/crash.log`。
- [x] 實作核心收集模組 `diagnostic_collector.py`：
  - [x] 掃描並收集日誌目錄中的有效檔案：`logs/system.log`, `logs/performance.log`, `logs/detections.log`, `logs/crash.log`。
  - [x] 讀取 `config.yaml` 並執行敏感資訊脫敏（遮蔽 `ums_api_key`、RTSP URL 帳號密碼等）後寫入暫存/封包中。
  - [x] 動態收集系統環境狀態 `sysinfo.json`（包含 OS 版本、Python 版本、CPU 使用率、RAM 記憶體、磁碟可用空間、主機名稱與網卡 IP）。
  - [x] 將上述檔案壓縮至暫存 ZIP 檔（檔名規範：`diagnostic_<timestamp>.zip`）。
- [x] 撰寫單元測試驗證脫敏邏輯與打包結構正確性。

## Answer
實作完成 [diagnostic_collector.py](file:///D:/Projects/argus/safty-predictor-nano/diagnostic_collector.py) 與全域崩潰日誌攔截：
1. **全域 Crash 攔截**：透過 `install_crash_handler(log_dir="logs")` 掛載至 `sys.excepthook`，並整合於 [main.py](file:///D:/Projects/argus/safty-predictor-nano/main.py)，確保未捕捉之重大異常能輸出完整堆疊與時間戳記至 `logs/crash.log`。
2. **敏感資料脫敏**：實作 `mask_sensitive_url()`（支援特殊字元密碼比對並遮蔽）與 `mask_api_key()`，自動在輸出前將 `config.yaml` 的 `ums_api_key`、串流 RTSP 帳密、外部狀態 URL 密碼完整遮蔽。
3. **系統狀態收集**：實作 `collect_system_info()`，自動提取本機 Hostname、OS、Python 版本、網卡 IPv4、CPU/RAM/磁碟等硬體指標輸出為 `sysinfo.json`。
4. **單檔容量截斷保護**：實作 `_read_file_with_limit()`（預設上限 20MB），超過限制時保留末端內容並注入警示標註，防止巨大日誌導致打包或上傳超時。
5. **打包封裝**：`collect_diagnostic_bundle()` 將脫敏配置、系統摘要與各日誌完整打包為 `diagnostic_<timestamp>.zip`，輸出結構化中繼資料。
6. **測試驗證**：建立 [test_diagnostic_collector.py](file:///D:/Projects/argus/safty-predictor-nano/test_diagnostic_collector.py)，涵蓋 URL/Key 脫敏、環境收集、崩潰攔截、容量截斷與 ZIP 結構 7 項單元測試，全部測試通過。
