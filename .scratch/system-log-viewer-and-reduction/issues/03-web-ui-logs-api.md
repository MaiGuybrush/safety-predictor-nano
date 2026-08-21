# Issue 03: 後端日誌讀取 API 端點 (GET /api/logs) 與安全白名單防護

Type: task
Status: resolved
Gitea Issue: #35 (http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/35)

**Role:** ready-for-agent

**What to build:**
在 `web_ui.py` 實作安全受控的日誌讀取 API 端點：
1. 實作 `GET /api/logs?file=<type>&lines=200` 端點，支援讀取 `system`、`performance`、`detections` 三類日誌。
2. 支援 `lines` 參數讀取檔案末尾 N 行（整數，預設 200，上限 1000 行）。
3. 嚴格限制白名單映射，阻擋任何路徑穿越（Path Traversal）嘗試。
4. 當日誌檔案尚未建立時，優雅回傳空字串或初始提示（HTTP 200），不拋出 500 錯誤。
5. 撰寫 API 單元測試驗證回傳格式、邊界情況與路徑穿越防護。

**Acceptance criteria:**
- [x] `GET /api/logs` 正確回傳指定日誌之末尾 N 行與 JSON 結構（`status`, `file_type`, `file_path`, `lines`, `content`）。
- [x] 非法 `file` 參數或路徑穿越字串（如 `../../etc/passwd`）回傳 400 Bad Request 或白名單限制。
- [x] 檔案不存在時回傳 200 OK 且 content 為空字串。
- [x] 單元測試通過。

**Blocked by:**
- 01-system-logger-core-and-reduction (Gitea #33)

## Answer
已在 `web_ui.py` 實作 `GET /api/logs` 端點，並於 `test_log_api.py` 涵蓋白名單安全校驗、路徑穿越防護、lines 邊界等 10 個單元測試。
