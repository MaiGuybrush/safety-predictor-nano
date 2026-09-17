# 02 — API Gateway 檔案上傳與 Gitea Issue 建立客戶端 (API Gateway Client)

Gitea Issue: #61
Type: task
Status: resolved
Blocked by: None

## Question
如何結合 `ums-api-config.json` 動態解析的 API Gateway 主機，透過 `FileServiceCore` 完成 Multipart/form-data 封包上傳，並透過 Gateway 的 `/ApiGateway/git-server/api/v1` 端點自動建立包含下載連結與環境摘要的 Gitea Issue？

## Tasks
- [x] 實作 `issue_service_client.py` 模組：
  - [x] 複用 `ums_config.py` 的廠區自動偵測與 `ums-api-config.json` 解析機制，取得有效的 Gateway 主機（例如 `http://tncimweb1.cminl.oa`）。
  - [x] 實作檔案上傳函式 `upload_diagnostic_file(zip_path, report_id)`：
    - 呼叫 `POST http://{host}/FileServiceCore/File?srcName=ErrorReport&filePath=.%2Fsafety-nano%2F{report_id}&flatten=false&overwrite=true`。
    - Content-Type 為 `multipart/form-data`，欄位 `files=@{zip_filename};type=application/x-zip-compressed`。
    - 解析回應 JSON 並組裝標準下載連結：`http://{host}/FileServiceCore/File?srcName=ErrorReport&filePath=.%2Fsafety-nano%2F{report_id}%2F{zip_filename}`。
  - [x] 實作 Gitea Issue 建立函式 `create_gitea_issue(title, description, download_url, sysinfo)`：
    - 呼叫 `POST http://{host}/ApiGateway/git-server/api/v1/repos/guy.mai/safety-predictor-nano/issues`。
    - 傳入結構化 Markdown 內文（問題描述、診斷封包下載連結、系統環境區塊）。
    - 取得並回傳建立之 Issue 網址與編號（如 `#45` 及完整 Web URL）。
- [x] 撰寫單元與 Mock 測試驗證連線失敗、Gateway Failover 容錯處理與回應解析。

## Answer
實作完成 [issue_service_client.py](file:///D:/Projects/argus/safty-predictor-nano/issue_service_client.py) 與完整測試套件：
1. **動態主機解析與 Failover**：
   - 實作 `resolve_gateway_hosts()`，透過 `ums_config` 動態比對網卡 IP 與廠區定義，自動提取 Scheme + Host，並在連線逾時或 5xx 錯誤時自動依序嘗試備援主機，成功後更新 `active_index`。
2. **診斷封包上傳 (`upload_diagnostic_file`)**：
   - 透過 `requests.Session` 發送 Multipart/form-data 請求至 `/FileServiceCore/File`。
   - 解析回應 JSON 之 `count`、`size` 及 `error` 狀態，並正確組裝標準下載連結。
3. **Gitea Issue 自動建立 (`create_gitea_issue`)**：
   - 呼叫 `/ApiGateway/git-server/api/v1/repos/guy.mai/safety-predictor-nano/issues`，由 Gateway 自動代入權限 Token。
   - 結構化生成 Markdown 內容（問題描述、封包下載連結、系統環境 JSON 摘要代碼區塊）。
4. **一鍵整合服務 (`report_diagnostic_bundle`)**：
   - 串聯封包上傳與 Issue 建立流程，回傳完整狀態、Issue URL 與下載連結。
5. **單元與容錯測試**：
   - 於 [test_issue_service_client.py](file:///D:/Projects/argus/safty-predictor-nano/test_issue_service_client.py) 撰寫 10 項單元測試，涵蓋廠區主機解析、檔案上傳、Failover 自動容錯、Issue 建立與整合流程，全數測試通過。

