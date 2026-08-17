# 01 — UMS API 模型獲取與連線測試端點 (UMS Model Discovery & Connection Test Endpoints)

**What to build:** 
後端新增 `/api/ums/models` 與 `/api/ums/test_connection` 端點，以 `UmsApiClient` 取得模型清單，並依 Project ➔ Model ➔ Version 聚合為階層式 JSON 資料結構，提供前端下拉選單即時使用。在連線失敗或憑證無效時進行優雅錯誤處理（不拋 500）。

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [x] `web_ui.py` 新增 `GET /api/ums/models` 端點，以 `UmsApiClient` 呼叫 `fetch_my_models()`，回傳依 `project_name` 聚合之階層化模型與版本 JSON 清單。
- [x] `GET /api/ums/models` 在發生網路逾時或 API 金鑰無效時，捕獲例外並回傳 `{"status": "error", "message": "..."}`（HTTP 狀態碼 200），不拋出 500 異常。
- [x] `web_ui.py` 新增 `POST /api/ums/test_connection` 端點，接收傳入的 `base_url` 與 `api_key` 測試連線，回傳成功與可用模型數，或詳細錯誤訊息。
- [x] 撰寫單元測試 `test_web_ui_ums_endpoints.py`，使用 Mock `UmsApiClient` 驗證成功回傳格式、失敗降級處理以及連線測試端點行為。
