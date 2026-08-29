# Issue #38: 後端 AJAX 儲存支援與狀態回應

Type: task
Status: resolved

**Role:** resolved

**What to build:**
擴充後端 `web_ui.py` 的 `/` POST 路由，當接收到 AJAX 請求（`X-Requested-With: XMLHttpRequest` 或 `Accept: application/json`）時，完成 `config.yaml` 寫入後回傳 JSON 格式 `{ "status": "ok", "message": "設定已成功儲存並生效" }`。保留傳統 Form POST 回傳 HTML 之相容性，並附帶單元測試驗證。

**Blocked by:** None — can start immediately.

**Acceptance criteria:**
- [x] 當 POST `/` 帶有 `X-Requested-With: XMLHttpRequest` 或 `Accept: application/json` 時，回傳 JSON `{ "status": "ok", "message": "..." }`。
- [x] 無 AJAX 標頭時仍維持傳統 Form POST 相容性（回傳 HTML）。
- [x] `config.yaml` 安全正確寫入全域設定與 `streams_json`。
- [x] 撰寫單元測試驗證兩種請求情境下的設定儲存與回應格式。
