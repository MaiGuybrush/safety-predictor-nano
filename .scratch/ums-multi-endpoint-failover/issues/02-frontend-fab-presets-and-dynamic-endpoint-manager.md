# 02 — 前端廠區快捷選單與動態端點管理介面 (Frontend Fab Presets & Dynamic Endpoint Manager)

**What to build:**
升級 Web 管理介面（`templates/index.html`）中的 UMS API 進階連線設定區塊：
1. 新增「廠區預設快速選單 (FAB PRESETS)」下拉選單，收錄 OA 辦公網段、FAB 1、FAB 3、FAB 6、FAB 7、FAB 8、FAB T6、FAB TS1、FAB T1、FAB T2、FAB T3 等廠區。
2. 選取特定廠區後，動態產生並自動填入該廠區對應之 `src1` 與 `src2` 端點。
3. 支援動態管理自訂多組端點清單（`「+ 新增備援端點」` 按鈕、每列獨立刪除按鈕）。
4. 「測試連線」功能升級：同時檢測所有配置的端點，並在介面上分別以狀態標籤（如 `[src1: 200 OK (3 models)] [src2: 200 OK (3 models)]`）清楚呈現各端點狀態。
5. 表單儲存提交時將所有動態端點序列化為 `ums_base_urls` 清單正確儲存至 `config.yaml`。

**Blocked by:** 01 — 後端多端點備援與無感容錯切換 (Backend Multi-Endpoint Failover)

**Status:** done

- [x] Web UI 進階設定中提供廠區下拉選單，選取廠區能即時自動帶入該廠區的預設端點清單。
- [x] 使用者可自由點擊 `「+ 新增備援端點」` 新增輸入框，或刪除特定端點。
- [x] 點擊「[ 測試連線 ]」時，能依序檢測所有輸入的端點並於前端各自顯示成功或失敗詳情。
- [x] 點擊「[ EXECUTE_UPDATE ]」儲存時，後端正確寫入 `ums_base_urls` 陣列至 `config.yaml` 且刷新頁面後能正確載入現有端點清單。
- [x] `test_web_ui_config_save.py` 或前端 E2E 測試驗證通過。
