# 04 — Web UI 回報按鈕、Modal 與非同步回報 API (Web UI Report Issue Modal)

Gitea Issue: #63
Type: task
Status: resolved
Blocked by: 01, 02

## Question
如何在現有 Flask Web UI 架構下，於頂部導覽列提供直覺的「回報問題」入口，並透過前端互動 Modal 搭配後端非同步 API，安全且流暢地完成打包、上傳、Issue 建立與即時結果反饋？

## Tasks
- [x] 後端 API 實作 (`web_ui.py`)：
  - [x] 新增 `POST /api/issue/report` 端點。
  - [x] 接收前端傳入的 `title`, `description`, `severity` 等欄位。
  - [x] 呼叫 `diagnostic_collector` 打包診斷資料，再呼叫 `issue_service_client` 完成上傳與發布 Gitea Issue。
  - [x] 回傳包含 `status`, `issue_id`, `issue_url` 的 JSON 結果。
- [x] 前端 UI 實作 (`templates/index.html`)：
  - [x] 於 Navbar 右側新增「回報問題 (Report Issue)」按鈕。
  - [x] 實作彈出式 Modal 表單（包含：問題標題、詳細說明、異常步驟、送出按鈕、取消按鈕）。
  - [x] 實作點擊送出後的 Loading 狀態、Disable 避免重複點擊。
  - [x] 成功後顯示完成提示與可直接點擊開啟的 Gitea Issue 超連結；失敗時顯示詳細錯誤說明。

## Answer
1. **後端 API (`web_ui.py`)**：
   - 實作 `POST /api/issue/report` 端點，支援解析 JSON 與表單輸入。
   - 支援 `title`、`severity` (critical / high / normal / low)、`description`、`steps` 參數，自動結構化 Markdown 內文並標記嚴重等級。
   - 串接 `diagnostic_collector.collect_diagnostic_bundle()` 自動收集環境、脫敏配置與系統/崩潰日誌。
   - 透過 `issue_service_client.IssueServiceClient` 將封包上傳至 Gateway 的 `/FileServiceCore/File` 並呼叫 `/ApiGateway/git-server/api/v1/.../issues` 自動建立 Gitea Issue。
   - 回傳 `status: "ok"`, `issue_id`, `issue_number`, `issue_url`, `download_url`, `report_id`, `zip_filename`。
2. **前端 UI (`templates/index.html`)**：
   - 頂部導覽列右側新增 `[ 回報問題 REPORT ]` 按鈕，點擊開啟彈出式 Cyberpunk 風格 Modal 表單。
   - 支援 ESC 鍵或點擊黑色遮罩背景關閉 Modal。
   - 包含問題標題、嚴重程度下拉選單、詳細說明與選填的重現步驟。
   - 點擊送出後自動進入 Loading 狀態並 Disable 送出按鈕避免重複發送。
   - 建立成功後平滑切換至完成畫面，直接提供已建立的 Gitea Issue 外部超連結、診斷封包下載連結與報告代碼。
   - 若發生異常或網路斷線，即時顯示錯誤警示橫幅並恢復重試按鈕。
3. **單元測試 (`test_web_ui_report_issue.py`)**：
   - 包含端點成功建立、預設欄位套用、封包收集錯誤、Gateway 上傳錯誤與 UI HTML 結構驗證共 5 項單元測試，全數通過。
