# 04 — 全域模型切換與 UMS 階層下拉連動 (Global Model Source & UMS Dynamic Selectors)

**What to build:** 
在前端實作「本地檔案 / UMS 雲端」模型來源切換互動。在 UMS 模式下動態連動 Project ➔ Model ➔ Version 三層下拉選單，提供即時連線測試反饋，並在頁面載入時自動反查與回填既有設定。

**Blocked by:** 01（UMS API 端點）、03（Web UI 版面結構）

**Status:** ready-for-agent

- [ ] 實作模型來源 Radio 切換開關（`[ 本地檔案 Local Path ]` vs `[ UMS 雲端模型 UMS Model Sync ]`），無刷新平滑切換輸入介面。
- [ ] 實作 UMS 模型階層下拉連動引擎：頁面載入非同步調用 `/api/ums/models`，選定 Project 自動過濾對應 Model，選定 Model 自動填入 Version 選項（預設選中 `latest`）。
- [ ] 實作自動回填機制：若既有 `config.yaml` 宣告了 `ums_model`，在模型清單載入後自動選中對應的專案、模型與版本。
- [ ] 實作 UMS 連線測試按鈕互動：點擊 `[ 測試連線 ]` 呼叫 `/api/ums/test_connection`，即時給予綠/紅反饋並在成功時重新整理模型下拉選單。
- [ ] 單元與前端語法驗證，確認模型選取後表單能正確輸出 `model_path` 或 `ums_model` 宣告。
