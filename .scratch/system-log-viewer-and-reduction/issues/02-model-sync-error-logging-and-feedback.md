# Issue 02: 模型同步失敗根因日誌記錄與 Web UI 錯誤提示強化

Type: task
Status: resolved
Gitea Issue: #34 (http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/34)

**Role:** ready-for-agent

**What to build:**
在模型同步失敗時補強根因日誌與 Web UI 前端錯誤回饋：
1. 在 `model_sync.py` 發生連線失敗、API Key 錯誤或找不到模型時，呼叫系統主 logger 寫入 `[ModelSync Error]` 及詳細原因。
2. 在 `main.py` 開機模型同步與定期/手動觸發流程中，確保同步錯誤完整記錄至系統日誌檔與終端機。
3. 在 Web UI (`templates/index.html`) 中，當模型同步回傳 `FAIL` 時，同步狀態按鈕變更為紅色警示外觀，並設定 `title` 懸停提示（Tooltip）顯示失敗摘要，同時於瀏覽器 Console 輸出詳細錯誤資訊。
4. 撰寫單元測試驗證同步異常時的日誌記錄與錯誤資訊回傳結構。

**Acceptance criteria:**
- [x] 模型同步失敗時，系統日誌與終端機輸出包含詳細錯誤原因（API Key、端點連線或找不到模型）。
- [x] Web UI 模型同步失敗時按鈕呈現紅色警示，且具備 Tooltip 懸停提示。
- [x] 瀏覽器 Console 印出詳細失敗資訊以便現場排錯。
- [x] 單元測試通過。

**Blocked by:**
- 01-system-logger-core-and-reduction (Gitea #33)

## Answer
已在 `model_sync.py`、`main.py` 與 `templates/index.html` 實作根因日誌與前端失敗紅色警示樣式（含 tooltip 與 console.error）。所有單元測試皆在 `test_model_sync.py` 通過。
