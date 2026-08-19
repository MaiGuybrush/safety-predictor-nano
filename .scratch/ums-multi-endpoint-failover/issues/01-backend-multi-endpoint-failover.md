# 01 — 後端多端點備援與無感容錯切換 (Backend Multi-Endpoint Failover)

**What to build:**
提供後端多端點備援架構與透明請求層級容錯機制。包含：
1. `config_manager.py` 支援 `ums_base_urls: list[str]` 格式讀取、環境變數 `UMS_BASE_URL` 解析與舊版 `ums_base_url` 向下相容。
2. 實作 `FailoverUmsClient`，對外相容 `UmsApiClient` 介面（`fetch_my_models`、`download_version` 等），在 API 呼叫遭遇連線逾時（5~10s）或 5xx 錯誤時自動透明嘗試次一備援端點，成功後記憶當前可用之 Active 端點。
3. `model_sync.py` 整合 `FailoverUmsClient`，使系統開機同步與手動 `/sync_models` 具備跨端點自動容錯能力。
4. `web_ui.py` 後端 API 升級：`/api/ums/test_connection` 支援傳入多組端點並依序檢測回傳個別端點的健康狀態與模型數量；`/api/ums/models` 改用 `FailoverUmsClient` 自動容錯讀取模型清單。
5. 建立完整的後端單元測試與 API 測試，驗證多端點解析、容錯切換與各端點連線檢測。

**Blocked by:** None — can start immediately

**Status:** done

- [x] `ConfigManager.get_ums_base_urls()` 能正確解析 `ums_base_urls`（列表）、`ums_base_url`（單一字串）與 `UMS_BASE_URL`（逗號分隔環境變數），若皆未設定則 fallback 至預設端點。
- [x] `FailoverUmsClient` 支援多組端點依序重試，主端點連線逾時或異常時能無感切換至備援端點並成功取得資料。
- [x] `model_sync.sync_all()` 在主要端點斷線時能透過備援端點正常同步模型，不中斷推論服務。
- [x] `/api/ums/test_connection` 能接受多組端點，並回傳各端點的個別測試結果與取得模型數。
- [x] `/api/ums/models` 能在首選端點異常時自動透過備援端點回傳專案與模型結構。
- [x] 後端測試（`test_config_manager.py`, `test_model_sync.py`, `test_web_ui_ums_endpoints.py`）全部通過。
