# 診斷資料打包與自動 Gitea Issue 回報功能規格 (Diagnostic Issue Reporter Spec)

## 1. 概述 (Overview)
當使用者在 Argus Safety Predictor Nano 運行期間遭遇異常、或當 `main.py` 因環境/配置等問題無法啟動時，提供一鍵/一指令將診斷資訊（日誌、脫敏配置、系統環境狀態、Crash Traceback）自動壓縮打包，透過現有內部 API Gateway 的檔案服務 (`FileServiceCore`) 進行上傳，並於內部 Gitea (`guy.mai/safety-predictor-nano`) 自動建立 Issue，附上環境資訊與檔案下載連結。

---

## 2. 系統架構與呼叫流程 (Architecture & Workflow)

```
+-------------------------------------------------------------+
|                      Trigger Channels                       |
|   [Web UI: Navbar "回報問題"]      [CLI: report_issue.py /  |
|                                    argus_predictor --report] |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|               Diagnostic Collector (診斷收集器)              |
| - 收集 logs/*.log (system, performance, detections, crash)  |
| - 脫敏 config.yaml (遮蔽 ums_api_key, RTSP 密碼)            |
| - 收集系統摘要 (OS, Python, CPU, RAM, Disk, 網卡 IP)        |
| - 壓縮為 diagnostic_<timestamp>.zip                         |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|             API Gateway Client (檔案與 Issue 客戶端)          |
| 1. 從 ums-api-config.json 解析 Active Gateway Host          |
| 2. 上傳至 FileServiceCore:                                  |
|    POST http://{host}/FileServiceCore/File?...              |
|    取得下載連結: http://{host}/FileServiceCore/File?...    |
| 3. 呼叫 Gitea API 建立 Issue:                               |
|    POST http://{host}/ApiGateway/git-server/api/v1/repos/   |
|         guy.mai/safety-predictor-nano/issues                |
|    (Token 由 API Gateway 自動注入，無需前端/本機保存)       |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|                     結果反饋 (Feedback)                      |
| Web UI 彈出成功訊息與 Issue 連結；CLI 輸出 Issue URL 與摘要   |
+-------------------------------------------------------------+
```

---

## 3. 服務與 API 規範 (API Specifications)

### 3.1 主機位址解析 (Host Resolution)
- 參考 `ums_config.py` 與 `ums-api-config.json`。
- 透過本機 IP 比對 `domainDefine` 決定廠區（例如 `oa`, `fab1` 等），取得對應之 Gateway 端點（例如 `http://tncimweb1.cminl.oa/umsapiproxy/fab4ums`）。
- 提取該 URL 之 Scheme 與 Host (例如 `http://tncimweb1.cminl.oa`) 作為 API Gateway 主機。

### 3.2 檔案上傳服務 (FileServiceCore Upload)
- **Method**: `POST`
- **URL**: `http://{host}/FileServiceCore/File?srcName=ErrorReport&filePath=.%2Fsafety-nano%2F{report_id}&flatten=false&overwrite=true`
- **Headers**:
  - `accept: */*`
  - `Content-Type: multipart/form-data`
- **Body**:
  - `files`: ZIP 壓縮二進位檔案，MIME type: `application/x-zip-compressed`
- **回應範例**:
  ```json
  {
    "count": 1,
    "size": 162644,
    "existFiles": [],
    "error": []
  }
  ```
- **下載連結格式**:
  `http://{host}/FileServiceCore/File?srcName=ErrorReport&filePath=.%2Fsafety-nano%2F{report_id}%2F{zip_filename}`

### 3.3 Gitea Issue 建立 (Create Issue)
- **Method**: `POST`
- **URL**: `http://{host}/ApiGateway/git-server/api/v1/repos/guy.mai/safety-predictor-nano/issues`
- **Headers**:
  - `accept: application/json`
  - `Content-Type: application/json`
  *(注意：API Gateway 負責驗證與注入 Token，本機客戶端不寫死金鑰)*
- **Body**:
  ```json
  {
    "title": "[使用者回報] <使用者輸入之標題>",
    "body": "## 問題描述\n<問題描述>\n\n## 診斷附件\n- 下載連結: [點此下載診斷封包](http://...)\n\n## 系統環境摘要\n```json\n{ ... }\n```"
  }
  ```

---

## 4. 診斷資料與安全脫敏 (Data Packaging & Sanitization)

### 4.1 收集清單
1. `logs/system.log` (系統運作日誌)
2. `logs/performance.log` (效能與資源日誌)
3. `logs/detections.log` (偵測事件日誌)
4. `logs/crash.log` (透過 `sys.excepthook` 捕捉之 Fatal Exception 與 Traceback)
5. `config.yaml` (系統配置檔，進行敏感欄位遮蔽)
6. `sysinfo.json` (動態產生：OS、Python 版本、CPU、RAM、Disk、網卡 IP、時間戳記)

### 4.2 敏感資訊遮蔽 (Masking)
- `ums_api_key`: 取代為 `ums_***[MASKED]***`。
- RTSP URL 認證資訊：如 `rtsp://admin:password@192.168.1.1:554/...` 遮蔽為 `rtsp://admin:******@192.168.1.1:554/...`。

---

## 5. 雙通道觸發介面 (Trigger Interfaces)

### 5.1 Web UI (在線回報)
- 頂部導覽列右側新增「回報問題 (Report Issue)」按鈕。
- 點擊彈出 Modal：
  - 欄位：標題 (Title)、詳細描述 (Description)、重現步驟 (Steps to reproduce)。
  - 點擊「提交」，前端顯示 Loading 狀態與進度條。
  - 成功建立後，顯示 Gitea Issue 編號與超連結；失敗時顯示詳細錯誤訊息。

### 5.2 離線手動 CLI (離線/啟動失敗回報)
- 獨立腳本：`python report_issue.py`
- 主程式 CLI 參數支援：`python main.py --report-issue`，以及打包後的 `argus_predictor --report-issue`。
- 提供互動式 CLI 提問（輸入標題與描述），亦支援命令列參數（`--title`, `--desc`, `--non-interactive`）。
- 執行完成印出上傳狀態與 Gitea Issue URL。
