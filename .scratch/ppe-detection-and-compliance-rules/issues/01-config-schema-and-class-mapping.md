# Issue 01: Config Schema & Class Mapping

Type: task
Status: resolved
Blocked by:

## Description
擴充 `config.yaml` 與 `config_manager.py`，支援以下配置項目：
1. `ppe_class_mapping`（自訂模型類別名稱映射到標準 enum/string）。
2. `external_states`（外部設備狀態輪詢 API 資訊）。
3. `zones` 擴充 `ppe_strategy` ("direct_negative" | "head_anchor") 與 `required_ppe` (list of strings)。
4. `compliance_rules`（條件式工安規則矩陣）。

## Acceptance Criteria
- `config_manager.py` 正確解析並回傳 `ppe_class_mapping`, `external_states`, `compliance_rules` 與擴充後的 `zones`。
- 提供完整預設值與容錯保護（缺失欄位不報錯）。
- 完成單元測試 `test_config_manager.py`。

## Answer
已完成 `config.yaml` 與 `ConfigManager` 的配置結構擴充與單元測試：
1. **`DEFAULT_PPE_CLASS_MAPPING` & `get_ppe_class_mapping()`**：
   - 內建標準類別字典（`person`, `head`, `helmet`, `no_helmet`, `vest`, `no_vest`, `cone`, `guardrail`）。
   - 當使用者在 `config.yaml` 提供自訂映射（如 `hard_hat: helmet`）時自動與預設字典安全合併。
2. **`get_external_states()`**：
   - 安全解析各外部設備狀態來源設定（`url`, `method`, `interval_seconds`, `json_path`, `timeout_seconds`, `fallback_value`），並套用型別轉換與邊界防護。
3. **`get_compliance_rules()`**：
   - 安全解析宣告式工安條件規則陣列，過濾停用之規則 (`enabled: false`)。
4. **`save_zone()` 擴充**：
   - 支援持久化 `ppe_strategy` 與 `required_ppe` 清單至 `config.yaml`，同時完全向下相容原有調用端點。
5. **單元測試驗證**：
   - `test_config_manager.py` 新增 5 個測試案例，涵蓋預設值、自訂覆寫、異常過濾與 Zone PPE 持久化；全專案 178 個單元測試全數 PASS 通過。
