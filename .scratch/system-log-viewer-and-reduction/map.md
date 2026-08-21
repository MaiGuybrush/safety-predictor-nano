# Wayfinding Map: 系統日誌導向檔案、高頻 HTTP 日誌減量與 Web UI 日誌檢視器

**Spec:** [.scratch/system-log-viewer-and-reduction/spec.md](file:///D:/Projects/argus/safty-predictor-nano/.scratch/system-log-viewer-and-reduction/spec.md)  
**PRD:** `docs/prd/system_log_viewer_and_reduction_prd.md`

## Tickets Overview

| # | Gitea | Title | Status | Blocked by |
|---|---|---|---|---|
| 01 | [#33](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/33) | 系統日誌雙軌架構、全域日誌等級與 Werkzeug HTTP 減量 | resolved | None |
| 02 | [#34](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/34) | 模型同步失敗根因日誌記錄與 Web UI 錯誤提示強化 | resolved | #33 |
| 03 | [#35](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/35) | 後端日誌讀取 API 端點 (GET /api/logs) 與安全白名單防護 | resolved | #33 |
| 04 | [#36](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/36) | Web UI 終端機風格日誌檢視器 Modal 與互動控制 | resolved | #35 |

## Decisions So Far
- 依據 spec.md 規劃 4 項垂直切片工單，並已同步發佈至 Gitea 與本地 `.scratch/system-log-viewer-and-reduction/issues/`。
- [Issue #33] 實作 SystemLogger 雙軌記錄、全域 log_level/log_backup_count 設定與 Werkzeug 請求日誌減量。
- [Issue #34] 實作 `model_sync.py` 與 `main.py` 的詳細根因日誌輸出，Web UI 同步按鈕失敗時警示紅色提示及 Tooltip。
- [Issue #35] 實作 `GET /api/logs` 安全日誌讀取端點，包含白名單、路徑穿越防護及 N 行尾端讀取。
- [Issue #36] 實作前端 Log Viewer Modal 互動介面（支援 3 種日誌切換、自動捲動、一鍵複製、ESC 關閉）。
