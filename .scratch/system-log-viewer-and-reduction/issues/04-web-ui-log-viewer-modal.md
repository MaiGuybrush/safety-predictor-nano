# Issue 04: Web UI 終端機風格日誌檢視器 Modal 與互動控制

Type: task
Status: resolved
Gitea Issue: #36 (http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/36)

**Role:** ready-for-agent

**What to build:**
在 Web UI 實作終端機黑底風格的即時日誌檢視視窗：
1. 在 `templates/index.html` 頂部導覽列新增 `[ 日誌檢視 LOGS ]` 按鈕。
2. 建立 Log Viewer Modal，具備等寬字體與深底色終端機風格。
3. 支援下拉選單切換 `system.log`、`performance.log`、`detections.log` 三種日誌來源。
4. 提供「手動重新整理」按鈕與「自動捲動至底部 (Auto-scroll)」切換開關。
5. 提供「一鍵複製」按鈕（點擊後帶有短暫 Copied! 提示視覺回饋）。
6. 支援 ESC 鍵與點擊遮罩/關閉按鈕關閉 Modal。
7. 撰寫前端相關單元/UI 測試驗證元件存在性與操作行為。

**Acceptance criteria:**
- [x] 頂部導覽列點擊 `[ 日誌檢視 LOGS ]` 能正確開啟 Modal。
- [x] 能在 Modal 內切換 3 種日誌來源並即時載入日誌內容。
- [x] 點擊「重新整理」能取得最新內容；開啟「自動捲動」時內容更新會自動捲動至底。
- [x] 點擊「複製」能將日誌內容寫入剪貼簿並給予視覺回饋。
- [x] 單元測試通過。

**Blocked by:**
- 03-web-ui-logs-api (Gitea #35)

## Answer
已在 `templates/index.html` 實作終端機風格 Log Viewer Modal，支援多日誌切換、手動重新整理、自動捲動至底、一鍵複製與快捷鍵關閉；並撰寫 `test_log_viewer.py`（13 個測試）驗證完整性。
