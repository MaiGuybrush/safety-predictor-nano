# Issue 06: User Manual & Documentation Sync

Status: closed
Blocked by: 05

## Description
更新 mdBook 使用者操作手冊與相關說明文件：
1. **使用者操作手冊 (`docs/user-manual/`)**：
   - 新增/更新「電子圍籬與 PPE 防護規範」章節。
   - 說明 `config.yaml` 之 `compliance_rules`、`external_states` 與 `ppe_class_mapping` 設定方式。
   - 說明全螢幕合規監控畫布的操作與告警判讀。
2. **自動建置與驗證**：
   - 執行 `mdbook build docs/user-manual` 確保手冊建置無誤。

## Acceptance Criteria
- 手冊內容完整涵蓋 PPE 雙模設定、條件規則與外部狀態整合。
- `mdbook build` 順利通過無錯誤。
