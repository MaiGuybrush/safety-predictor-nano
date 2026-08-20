# Issue 01: 系統日誌雙軌架構、全域日誌等級與 Werkzeug HTTP 減量

Type: task
Status: ready-for-human
Gitea Issue: #33 (http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/33)

**Role:** ready-for-human

**What to build:**
實作系統日誌雙軌輸出架構、全域日誌等級控制與 Flask/Werkzeug 存取日誌減量：
1. 在 `config.yaml` 與 `config_manager.py` 擴充 `system_log_file`（預設 `logs/system.log`）、`log_level`（預設 `INFO`）與 `log_backup_count`（預設 `3`）。
2. 在 `stats_logger.py` / `main.py` 建立系統主 logger，配置 Console（`sys.stdout`）與 `TimedRotatingFileHandler` 每日自動輪替雙軌輸出。
3. 將 Flask/Werkzeug 存取日誌等級設為 `WARNING`，過濾高頻 `/model_info` 與 `/sync_status` 輪詢產生的 `HTTP 200` 刷屏，保留 `4xx`、`5xx` 異常。
4. 撰寫單元測試驗證雙軌日誌輸出、日誌等級抑制與設定載入。

**Acceptance criteria:**
- [x] `config.yaml` 與 `config.yaml.example` 包含 `system_log_file`、`log_level` 與 `log_backup_count` 設定。
- [x] 系統核心日誌同時輸出至 stdout 與 `logs/system.log`，並依每日輪替與保留天數運作。
- [x] Werkzeug 存取日誌預設為 WARNING，正常高頻輪詢不再刷屏終端機。
- [x] 單元測試通過且涵蓋雙軌日誌與等級設定。

**Blocked by:** None — can start immediately.
