# 01 — App Management API 客戶端與設定檔 Schema 設計

Type: research
Status: resolved
Blocked by: None

## Question

如何針對 App Management API（`GET /App/{appId}/Version`, `GET /File/{appId}/DownloadInfo`, `GET /File/{appId}`）設計具備容錯、重試與逾時機制的 `AppUpdateClient`，並在 `config.yaml` 擴充 `auto_update` 設定區塊（包含 `app_id`, `api_base_url`, `check_interval_seconds`, `mode`, `enabled`）？

## Investigation Scope

1. **API 規格與資料模型對齊**:
   - `GET /App/{appId}/Version`：解析回傳之 `VersionInfoDTO[]`，過濾出 `released == true` 且 `autoUpdate == true` 的候選版本，並依語意化版本號（SemVer）比對當前本地版本，判斷是否有更新版本可用。
   - `GET /File/{appId}/DownloadInfo?version={version}`：解析 `DownloadInfo` 中的 `filesInfo`，獲取發布檔案路徑與預期大小（`size`）。
   - `GET /File/{appId}?owner={owner}&version={version}&filePath={filePath}`：分塊串流下載二進位封包（支援進度回呼以供 SSE 進度條展示），並在下載完成時校驗檔案大小。
2. **Client 容錯設計**:
   - 參考現有 `FailoverUmsClient` 與 `issue_service_client` 的架構設計，支援逾時處理（預設 30 秒）、指數退避重試（Exponential Backoff）與連線異常防護，避免因網路短暫斷線導致主程式推論或 Web UI 阻塞。
3. **`config.yaml` Schema 擴充**:
   - 定義 `auto_update` 區塊，包含：
     ```yaml
     auto_update:
       enabled: true
       app_id: "argus_predictor"
       api_base_url: "http://tncimweb.cminl.oa/appmanagementapi"
       check_interval_seconds: 3600  # 輪詢週期
       mode: 2  # 1: 自動替換重啟, 2: 提示通知手動重啟 (預設)
       check_on_startup: true        # 開機是否立即檢查
       temp_dir: "temp/updates"      # 下載暫存路徑
     ```

## Answer

1. **API 規格與資料模型設計**：
   - **版本清單查詢 (`GET /App/{appId}/Version/nocache`)**：回傳 `List[VersionInfoDTO]`，篩選條件為 `dto.released is True`、`dto.auto_update is True`、`dto.locked is False`，且符合 `release_fab` 廠區規則。
   - **SemVer 2.0.0 版本比對器**：正規化去前綴 `v/V`，解析 `major.minor.patch` 與 prerelease，以 `channel == "stable"` 過濾掉 prerelease 版本，比對 $V_{candidate} > V_{current}$ 挑選最新可用版本。
   - **下載元數據 (`GET /File/{appId}/DownloadInfo?version={version}`)**：解析回傳之 `owner`（供後續下載 API 必填參數）與 `filesInfo`，並依優先順序（arm64、.tar.gz、.zip）選取目標封包，透過 `size * 2.5` 進行磁碟剩餘空間預檢（防範磁碟滿溢）。
   - **分塊串流下載 (`GET /File/{appId}`)**：以固定 `chunk_size = 1MB` 串流寫入暫存檔，搭配 200ms 節流之進度回呼函式（回傳位元組、速度、百分比）以利 Web UI SSE 廣播，下載完成校驗 size 並原子置換。

2. **AppUpdateClient 容錯與重試機制**：
   - 整合 `ums_config` 進行廠區網段自動偵測與多 API Gateway 端點（主備）自動 Failover，並具備 Active 端點記憶能力。
   - 區分 `AppUpdatePermanentError`（401/404/磁碟空間不足，不重試）與 `AppUpdateTransientError`（5xx/連線逾時，觸發含 Jitter 的指數退避重試，最大 3 次）。
   - 提供 4 級 API Key 退避鏈：`auto_update.api_key` -> `ums_api_key` -> `APP_MGR_API_KEY` -> `UMS_API_KEY`。

3. **`config.yaml` 之 `auto_update` Schema**：
   - 定義包含 `enabled`、`app_id`、`channel`、`check_interval_seconds`、`api_key`、`base_urls`、`timeout_seconds`、`max_retries`、`download_chunk_size`、`mode`、`target_dir` 與 `backup_dir` 的標準設定結構，並於 `config_manager.py` 提供預設值與上下限邊界防禦。

