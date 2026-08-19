# 03 — 使用手冊與設定範例同步更新 (Documentation & Config Example Sync)

**What to build:**
依據多端點備援機制與 Web UI 新功能，同步更新系統操作手冊與組態範例：
1. 更新 `config.yaml.example`，加入 `ums_base_urls` 陣列範例與註解說明。
2. 更新 `docs/user-manual/src/01-quick-start.md`（第 1 章：快速開始），更新 3.1 節 UMS 連線設定流程，新增廠區快捷選單與多端點測試說明。
3. 更新 `docs/user-manual/src/06-system-settings.md`（第 6 章：系統參數與進階設定），補充多端點容錯機制原理、Timeout 策略與容錯切換日誌說明。
4. （若適用）重新編譯或驗證 mdBook / 使用者手冊靜態檔案完整性。

**Blocked by:** 02 — 前端廠區快捷選單與動態端點管理介面 (Frontend Fab Presets & Dynamic Endpoint Manager)

**Status:** done

- [x] `config.yaml.example` 包含清晰的 `ums_base_urls` 陣列宣告與說明。
- [x] `docs/user-manual/src/01-quick-start.md` 包含廠區快捷選單與多端點操作指引。
- [x] `docs/user-manual/src/06-system-settings.md` 包含多端點容錯切換技術說明。
- [x] 手冊內部連結與格式無損壞。
