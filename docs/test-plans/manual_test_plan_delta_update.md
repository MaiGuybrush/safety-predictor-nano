# 手動驗證流程與工程驗收規範書 - Issue #82 Delta 輕量增量更新機制

| 欄位 | 規格內容 |
| :--- | :--- |
| **目標票券** | Gitea [#82](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/82)（關聯子票 [#83](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/83)、[#84](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/84)、[#85](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/85)） |
| **參考架構規範** | [ADR-005: ARM64 Build Constraint](../adr/ADR-005-arm64-build-constraint.md)、[ADR-019: Auto-Update Architecture](../adr/ADR-019-auto-update-and-safe-upgrade-mechanism.md) |
| **文件版本** | v1.0.0 |
| **生效日期** | 2026-09-22 |
| **適用對象** | QA 測試工程師、現場維運工程師 (Field Application Engineer)、研發團隊 |
| **驗收目標** | 驗證應用層業務代碼解耦 (`argus.zip`)、輕量增量補丁建置 (< 3.5MB)、CIM API 優先配對與 Fallback、Web UI 增量視覺、`install.sh --delta` 局部原子置換、Exit 42 守護重啟、30 秒健康狀態評估與 4 大異常注入回滾防護。 |

---

## 1. 驗收簽核與執行紀錄 (Sign-off & Audit Trail)

在正式部署至廠區產線節點前，需由測試人員與 QA 負責人依本規範書逐項執行並完成簽核：

| 角色 | 簽核人員 | 簽核日期 | 驗證環境（實機/沙盒） | 判定結果 |
| :--- | :--- | :--- | :--- | :--- |
| **主測工程師 (Tester)** | `____________________` | `2026 / ____ / ____` | `[ ] 樹莓派實機  [ ] 本機沙盒` | `[ ] PASS  [ ] FAIL` |
| **品保負責人 (QA Lead)** | `____________________` | `2026 / ____ / ____` | `[ ] 雙軌全數驗收` | `[ ] PASS  [ ] FAIL` |
| **系統維運主管 (Lead)** | `____________________` | `2026 / ____ / ____` | `全廠區版本同步授權` | `[ ] 准予上線 (Approved)` |

---

## 2. 測試環境拓撲與前置準備 (Environment & Prerequisites)

本驗收手冊支援 **雙軌模式 (Dual-Track)**，測試人員可依硬體資源選擇執行方式：

```
+-----------------------------------------------------------------------------------+
| 軌道 A：樹莓派 5 實機環境 (Physical Edge Device)                                     |
| 硬體: Raspberry Pi 5 (ARM64, Debian 12 Bookworm, 4GB/8GB RAM)                     |
| 守護進程: scripts/run.sh 監聽 Exit Code 42                                         |
| 伺服器: 連線廠區 CIM API Gateway (tncimweb1/2) 或局域網 Mock Server                  |
+-----------------------------------------------------------------------------------+
                                        OR
+-----------------------------------------------------------------------------------+
| 軌道 B：工程沙盒模擬環境 (Staging Sandbox)                                         |
| 作業系統: Linux / macOS / Windows (本機開發機，免 ARM64 實機硬體)                  |
| 模擬服務: scripts/mock_app_update_server.py (監聽 8190 通訊埠)                      |
| 執行模式: 於臨時沙盒目錄建立模擬安裝結構，驗證 UpdateManager 狀態機與 install.sh 覆蓋   |
+-----------------------------------------------------------------------------------+
```

### 2.1 共用基底目錄結構檢驗 (Baseline Layout)

> **📋 環境準備方式：請依 README.md「部署指南 → 方案 C」完成建置。**
> 方案 C 採兩步驟流程，缺少任一步驟將導致 Delta 更新機制無法運作：
>
> **步驟一：產生業務模組外置包（`argus.zip`）與 Delta 增量包**
> ```bash
> # 在專案根目錄（開發機或樹莓派）執行
> python scripts/build_delta_package.py
> # 產出：dist/argus_delta-v{VERSION}-arm64.tar.gz 及 .sha256
> ```
>
> **步驟二：使用 Spec 封裝完整安裝包（需在樹莓派 ARM64 本機執行）**
> ```bash
> mdbook build docs/user-manual    # 首次或手冊異動時
> pyinstaller argus_predictor.spec # 業務模組將外置為 _internal/argus.zip
> # 產出：dist/argus_predictor/ 完整目錄
> ```
>
> **沙盒快速準備（軌道 B，跳過 ARM64 建置）：**
> ```bash
> # 建立沙盒目錄，模擬已部署的 argus_predictor/ 結構
> mkdir -p sandbox/argus_predictor/_internal
> python scripts/build_delta_package.py --zip-only sandbox/argus_predictor/_internal/argus.zip
> echo "1.0.0" > sandbox/argus_predictor/version.txt
> cp config.yaml ums-api-config.json sandbox/argus_predictor/
> cp scripts/install.sh scripts/run.sh sandbox/argus_predictor/scripts/ 2>/dev/null || true
> ```

確保受測邊緣端（或沙盒）包含完整的 `--onedir` 運行結構：
```text
argus_predictor/
├── argus_predictor              # 主二進位檔 (或 python3 main.py)
├── version.txt                  # 目前基準版本 (例如 1.0.0)
├── config.yaml                  # 邊緣端專屬設定檔 (非破壞性保護目標)
├── ums-api-config.json          # API 閘道端點設定
├── models/                      # YOLO 模型目錄 (保護目標)
├── logs/                        # 系統與推論日誌目錄 (保護目標)
├── scripts/
│   ├── install.sh               # 核心安裝與回滾腳本
│   └── run.sh                   # 守護重啟腳本
└── _internal/
    ├── argus.zip                # 業務核心 Bytecode (Delta 置換目標)
    ├── argus/web/templates/     # Web 前端模板 (Delta 置換目標)
    ├── docs/user-manual/book/   # 離線手冊 (Delta 置換目標)
    ├── torch/                   # 重型深度學習動態庫 (嚴格禁動)
    └── cv2/                     # OpenCV 動態連結庫 (嚴格禁動)
```

### 2.2 軌道 B 輔助工具啟動：Mock API 伺服器
若在無連網或無實機環境下測試，於本機另開終端視窗啟動 Mock API：
```bash
# 預設同時提供 Delta 增量包 (2.4MB) 與全量包 (256MB)
python scripts/mock_app_update_server.py --port 8190 --version 1.1.0
```
修改 `config.yaml` 導向 Mock API：
```yaml
auto_update:
  enabled: true
  app_id: "safety-predictor-nano"
  base_urls:
    - "http://127.0.0.1:8190/AppManagementApi"
  base_url_path: "AppManagementApi"
  channel: "stable"
  mode: 2
```

---

## 3. 測試案例矩陣概覽 (Test Matrix)

| 編號 | 測試項目 | 優先級 | 驗證重點 | 預期結果 | 判定 |
| :--- | :--- | :---: | :--- | :--- | :---: |
| **TC-01** | 打包端業務解耦與 Delta 封包建置 | P0 | `build_delta_package.py` 產出與體積限制 | 全量 Delta < 3.5MB，純代碼 < 250KB，含 manifest.json | `[ ] PASS` |
| **TC-02** | CIM API 優先配對 Delta 封包 | P0 | `AppUpdateClient` 解析與優先選擇 | 命中 2.4MB 增量包，不選取 256MB 全量包 | `[ ] PASS` |
| **TC-03** | 無 Delta 封包時安全降級 (Fallback) | P1 | 伺服器僅有全量包時的相容性 | 自動回退選取全量包 (256MB)，不中斷流程 | `[ ] PASS` |
| **TC-04** | Web UI 增量更新標籤與 SSE 進度串流 | P1 | 前端 Cyberpunk 視覺與即時下載進度 | 顯示「增量更新」徽章、2.4MB 大小與百分比平滑增加 | `[ ] PASS` |
| **TC-05** | `install.sh --delta` 局部原子置換 | P0 | 僅更新業務層，保護重型庫與設定檔 | `argus.zip` 更新，`torch/cv2/config.yaml` 完好 | `[ ] PASS` |
| **TC-06** | Exit 42 守護重啟與 30 秒健康評估 Commit | P0 | 重啟生命週期與健康檢查確立版本 | `sys.exit(42)` 觸發，30 秒通過健康判定並更新版本 | `[ ] PASS` |
| **TC-07** | [異常 1] 健康檢查超時自動局部回滾 | P0 | 注入新版崩潰，測試 `.patch_bak/` 秒級還原 | 30 秒內自動還原舊版 `argus.zip` 並發出 Web UI 告警 | `[ ] PASS` |
| **TC-08** | [異常 2] 磁檢空間不足防護 | P1 | 磁碟剩餘空間低於 20MB 時攔截 | 拒絕下載並記錄 `PermanentError: Insufficient disk` | `[ ] PASS` |
| **TC-09** | [異常 3] 封包雜湊不符與不相容基底攔截 | P1 | 偽造/損毀之 Delta 封包與版號防護 | 解壓前校驗失敗，拒絕覆蓋，保持原狀 | `[ ] PASS` |
| **TC-10** | [異常 4] 連續崩潰防護 (Loop Guard) | P2 | 舊版還原後依然崩潰的看門狗防護 | 進入 `FATAL_HALT`，避免無窮重啟打滿日誌 | `[ ] PASS` |

---

## 4. 詳細測試執行步驟 (Step-by-Step Test Procedures)

### TC-01：打包端業務解耦與 Delta 封包建置驗證

* **測試目的**：確認 `scripts/build_delta_package.py` 可正確將業務模組打包為 `argus.zip`，並產出合規之 Delta 增量更新包。
* **前置條件**：工作目錄為專案根目錄，虛擬環境已啟用。
* **操作步驟**：
  1. 執行標準 Delta 增量包建置：
     ```bash
     python scripts/build_delta_package.py --version 1.1.0 --output-dir dist/
     ```
  2. 檢查產出檔案與檔案大小：
     ```bash
     ls -lh dist/argus_delta-v1.1.0-arm64.tar.gz*
     ```
  3. 檢視壓縮包內容物與 `manifest.json`：
     ```bash
     tar -ztvf dist/argus_delta-v1.1.0-arm64.tar.gz
     ```
  4. 執行純代碼增量包建置（測試 Hotfix 模式）：
     ```bash
     python scripts/build_delta_package.py --version 1.1.0-patch1 --code-only --output-dir dist/
     ls -lh dist/argus_delta-v1.1.0-patch1-arm64.tar.gz
     ```
* **預期結果**：
  - [x] 標準增量包體積小於 3.5 MB（實際約 2.3 ~ 2.8 MB）。
  - [x] 純代碼增量包體積小於 250 KB。
  - [x] 解壓檢查包含 `manifest.json` 與 `payload/`，其中 `payload/_internal/` 包含 `argus.zip`，**不包含** `torch/`、`cv2/`。
  - [x] 產出同名 `.sha256` 檔案且校驗雜湊相符。
* **驗收簽核**：`[ ] PASS  [ ] FAIL` ＿＿＿＿＿＿＿＿＿＿＿＿

---

### TC-02：App Management API 優先配對 Delta 封包

* **測試目的**：驗證 `AppUpdateClient` 在面對發布清單時，能精準優先選取 `argus_delta-*.tar.gz`。
* **前置條件**：啟動 Mock API 伺服器（雙模提供）或使用廠區包含 Delta 包的測試環境。
* **操作步驟**：
  1. 啟動 Mock 伺服器：
     ```bash
     python scripts/mock_app_update_server.py --port 8190 --version 1.1.0
     ```
  2. 透過 Python CLI 執行更新檢查呼叫：
     ```bash
     python -c "
     from argus.integration.app_update_client import AppUpdateClient
     client = AppUpdateClient(base_urls=['http://127.0.0.1:8190/AppManagementApi'])
     info = client.get_download_info('1.1.0')
     print('Is Delta:', info.is_delta)
     print('File Name:', info.file_path)
     print('Size:', info.size)
     "
     ```
* **預期結果**：
  - [x] `info.is_delta` 輸出為 `True`。
  - [x] 檔案路徑包含 `argus_delta-v1.1.0-arm64.tar.gz`。
  - [x] 下載大小約為 2,516,582 bytes (~2.4 MB)，而非 256 MB。
* **驗收簽核**：`[ ] PASS  [ ] FAIL` ＿＿＿＿＿＿＿＿＿＿＿＿

---

### TC-03：無 Delta 封包時安全降級 (Fallback) 驗證

* **測試目的**：驗證若伺服器端未編譯增量包（例如跨大版本架構重構），客戶端能自動安全回退至全量包。
* **前置條件**：啟動 Mock API 伺服器並加上 `--full-only` 參數。
* **操作步驟**：
  1. 啟動全量模式 Mock 伺服器：
     ```bash
     python scripts/mock_app_update_server.py --port 8190 --version 1.2.0 --full-only
     ```
  2. 執行版本查詢與下載資訊解析：
     ```bash
     python -c "
     from argus.integration.app_update_client import AppUpdateClient
     client = AppUpdateClient(base_urls=['http://127.0.0.1:8190/AppManagementApi'])
     info = client.get_download_info('1.2.0')
     print('Is Delta:', info.is_delta)
     print('File Name:', info.file_path)
     print('Size:', info.size)
     "
     ```
* **預期結果**：
  - [x] 系統無任何例外崩潰。
  - [x] `info.is_delta` 為 `False`。
  - [x] `info.file_path` 匹配全量包 `safety-predictor-nano-v1.2.0-arm64.tar.gz`。
  - [x] 大小反映全量尺寸 (~256 MB)。
* **驗收簽核**：`[ ] PASS  [ ] FAIL` ＿＿＿＿＿＿＿＿＿＿＿＿

---

### TC-04：Web UI 增量更新標籤與 SSE 進度串流

* **測試目的**：驗證操作員在瀏覽器端能直觀辨識「增量更新」狀態與體驗毫秒級進度回傳。
* **前置條件**：主程式運作中，瀏覽器開啟 `http://<設備IP>:8188`。
* **操作步驟**：
  1. 確保 Mock 伺服器以 Delta 模式運行（提供 v1.1.0）。
  2. 進入 Web UI 首頁，觀察頂端導覽列。
  3. 點擊導覽列呼吸徽章 `[ 🚀 新版本可用: v1.1.0 ]`，呼叫更新彈窗。
  4. 檢查彈窗呈現項目：
     - 是否具有藍綠色高亮徽章 `[ 📦 增量更新 (Delta Patch) ]`。
     - 「更新類型」欄位是否顯示 `增量更新 (Delta)`。
     - 「封包大小」欄位是否顯示約 `2.4 MB`。
  5. 點擊彈窗內 `[ 立即下載更新 ]` 按鈕，觀察 SSE 串流：
     - 下載進度條在 1~3 秒內從 0% 推進至 100%。
     - 傳輸速率數值即時跳動（如 `1.8 MB/s`）。
     - 進度達 100% 後，狀態自動躍遷為 `[ 就緒，等待重啟套用 ]`。
* **預期結果**：
  - [x] Web UI 清楚標示 Delta Patch 增量屬性，避免操作員誤以為要下載 300MB。
  - [x] SSE 通道實時推播下載位元組，無卡頓或頁面凍結現象。
  - [x] 成功進入 `READY_TO_INSTALL` 狀態，且「立即重啟」按鈕變為可點擊。
* **驗收簽核**：`[ ] PASS  [ ] FAIL` ＿＿＿＿＿＿＿＿＿＿＿＿

---

### TC-05：`install.sh --delta` 局部原子置換與零資料遺失

* **測試目的**：驗證 `scripts/install.sh --delta` 僅替換核心業務模組，嚴格保留龐大動態庫與客製配置。
* **前置條件**：沙盒環境已就緒，內含舊版 `argus.zip`、`config.yaml` 及 `_internal/torch/libtorch.so`。
* **操作步驟**：
  1. 記錄執行前檔案特徵與時間戳：
     ```bash
     sha256sum _internal/argus.zip
     sha256sum config.yaml
     ls -l _internal/torch/libtorch.so
     ```
  2. 手動執行 Delta 安裝指令：
     ```bash
     bash scripts/install.sh --delta dist/argus_delta-v1.1.0-arm64.tar.gz
     ```
  3. 驗證局部備份是否存在：
     ```bash
     ls -ld _internal/.patch_bak/
     ls -l _internal/.patch_bak/argus.zip
     ```
  4. 驗證置換結果與保護項目：
     ```bash
     # 業務代碼已更新
     unzip -p _internal/argus.zip argus/__init__.py | grep __version__
     # 既有配置完全未動
     sha256sum config.yaml
     # 重型庫未受波及
     ls -l _internal/torch/libtorch.so
     ```
* **預期結果**：
  - [x] 執行時間在樹莓派 5 上小於 1 秒。
  - [x] `_internal/.patch_bak/` 成功建立且包含舊版備份。
  - [x] `_internal/argus.zip` 成功替換為新版。
  - [x] `config.yaml` 雜湊與升級前完全一致，無任何修改。
  - [x] `_internal/torch/` 與 `_internal/cv2/` 修改時間與內容未變。
* **驗收簽核**：`[ ] PASS  [ ] FAIL` ＿＿＿＿＿＿＿＿＿＿＿＿

---

### TC-06：Exit 42 守護重啟與 30 秒健康狀態評估 Commit

* **測試目的**：驗證服務退出代碼 42 能被 `run.sh` 守護迴圈捕捉並自動重啟新版，並在通過 30 秒健康檢查後 Commit。
* **前置條件**：以 `bash scripts/run.sh` 啟動主服務。
* **操作步驟**：
  1. 觀察終端輸出，確認守護迴圈正常監聽。
  2. 於 Web UI 更新彈窗點擊 `[ 立即重啟生效 ]`（或 API 發送 POST `/api/update/restart`）。
  3. 觀察主行程終端 Log：
     - 主行程呼叫 `sys.exit(42)` 終止推論。
     - `run.sh` 輸出 `[run.sh] 收到重啟代碼 42 (RESTART_FOR_UPDATE)，準備載入新版本...`。
     - `run.sh` 自動重新呼叫新版二進位檔。
  4. 觀察 Web UI 前端全螢幕倒數遮罩（30 秒倒數）：
     - 前端以 1.5 秒為週期持續向 `/api/health` 探針請求。
     - 伺服器重啟完成後，探針回傳 HTTP 200。
     - 網頁自動刷新 (`window.location.reload()`)。
  5. 檢查日誌與狀態標記：
     ```bash
     cat logs/update.log | grep COMMITTED
     ls -a | grep update_in_progress  # 應已自動清除
     ```
* **預期結果**：
  - [x] 行程重啟時間在 5~10 秒內完成。
  - [x] `.update_in_progress` 暫存檔在健康確認後自動移除。
  - [x] `logs/update.log` 記錄 `[COMMITTED] 應用程式已成功更新至 v1.1.0`。
  - [x] Web UI 導覽列版本標籤更新為 `v1.1.0`。
* **驗收簽核**：`[ ] PASS  [ ] FAIL` ＿＿＿＿＿＿＿＿＿＿＿＿

---

### TC-07：[異常注入 1] 健康檢查超時/崩潰自動局部回滾

* **測試目的**：模擬新版 Delta 補丁存在缺陷（如語法錯誤或開機崩潰），驗證看門狗能於 30 秒內自動秒級還原上一穩定版本。
* **前置條件**：系統處於 v1.0.0 穩定運行狀態，透過 `run.sh` 啟動。
* **操作步驟**：
  1. 套用 Delta 更新至 `READY_TO_INSTALL`，並使系統進入更新重啟流程（生成 `.update_in_progress` 與 `.patch_bak/`）。
  2. **故障注入**：故意損毀新版 `argus.zip` 或強制令主程序開機拋出致命例外：
     ```bash
     # 注入破壞性 bytecode 或清空 zip
     echo "CORRUPTED_BYTECODE" > _internal/argus.zip
     ```
  3. 觸發重啟或殺死進程：
     ```bash
     kill -9 $(pgrep -f argus_predictor)
     ```
  4. 觀察 `run.sh` 捕捉非 0 且非 42 異常：
     - `run.sh` 偵測到 `.update_in_progress` 存在。
     - 自動呼叫 `scripts/install.sh --rollback`。
     - `install.sh` 偵測到 `_internal/.patch_bak/`，執行局部秒級還原。
     - 生成 `.rollback_alert` 標記檔。
     - `run.sh` 自動重新喚醒還原後的 v1.0.0。
  5. 驗證回滾成效：
     - 檢查 `_internal/argus.zip` 是否已復原為原 v1.0.0 代碼。
     - 檢查 Web UI 是否彈出紅色警示橫幅：`⚠️ 系統更新未通過健康檢查，已自動安全回滾至原版本`。
     - 檢查 `curl http://127.0.0.1:8188/api/health` 回傳 `{"rollback_occurred": true}`。
* **預期結果**：
  - [x] 回滾過程不搬移 1GB 全量目錄，耗時小於 1 秒。
  - [x] 系統未成為「磚機 (Brick)」，自動恢復正常工安推論。
  - [x] 操作員透過 Web UI 明顯獲知回滾事件與告警。
* **驗收簽核**：`[ ] PASS  [ ] FAIL` ＿＿＿＿＿＿＿＿＿＿＿＿

---

### TC-08：[異常注入 2] 磁檢空間不足防護

* **測試目的**：驗證邊緣裝置磁碟空間不足時，更新管理器能精準攔截，避免下載中途磁碟爆滿導致死機。
* **前置條件**：了解 Delta 預檢門檻（20 MB）與全量預檢門檻（650 MB）。
* **操作步驟**：
  1. 透過暫存大檔案填滿受測磁碟分區，使剩餘空間小於 20 MB：
     ```bash
     # 於測試分割區建立暫存大檔使剩餘空間剩下約 10MB
     fallocate -l $(($(df -B1 . | awk 'NR==2{print $4}') - 10485760)) ./fill_disk.tmp
     ```
  2. 嘗試透過 Web UI 或 API 觸發下載：
     ```bash
     curl -X POST http://127.0.0.1:8188/api/update/download
     ```
  3. 觀察 API 回應與 `logs/update.log`。
  4. 清除暫存大檔：
     ```bash
     rm -f ./fill_disk.tmp
     ```
* **預期結果**：
  - [x] API 回應失敗，狀態碼為 400 或 500，錯誤訊息包含 `Insufficient disk space`。
  - [x] 系統狀態保持在 `AVAILABLE` 或進入 `FAILED`，嚴禁啟動分塊寫入。
  - [x] 既有推論程序持續正常執行，不受磁碟檢查阻斷。
* **驗收簽核**：`[ ] PASS  [ ] FAIL` ＿＿＿＿＿＿＿＿＿＿＿＿

---

### TC-09：[異常注入 3] 封包雜湊不符與不相容基底版本攔截

* **測試目的**：驗證被竄改、傳輸中斷損毀之 Delta 封包，或基準版本低於 `min_compatible_base` 時被嚴格攔截。
* **前置條件**：啟動 Mock 伺服器並加上 `--corrupt` 參數。
* **操作步驟**：
  1. 啟動損毀模擬伺服器：
     ```bash
     python scripts/mock_app_update_server.py --port 8190 --version 1.1.0 --corrupt
     ```
  2. 於 Web UI 或 CLI 觸發下載與套用。
  3. 觀察 `UpdateManager` 解壓後比對 `manifest.json` 之 SHA-256 雜湊流程。
* **預期結果**：
  - [x] 解壓或雜湊檢查報錯 `Checksum mismatch` 或 `Manifest validation failed`。
  - [x] `install.sh` 中止執行，不建立 `.patch_bak/`，更不覆蓋運行中之 `argus.zip`。
  - [x] Web UI 顯示紅色錯誤提示：「更新套用失敗：校驗碼不符」。
* **驗收簽核**：`[ ] PASS  [ ] FAIL` ＿＿＿＿＿＿＿＿＿＿＿＿

---

### TC-10：[異常注入 4] 連續崩潰防護 (Rollback Loop Guard)

* **測試目的**：驗證當回滾後之舊版依然發生致命錯誤時，系統具備防止無窮重啟 (Infinite Restart Loop) 的終止保護。
* **前置條件**：`run.sh` 正在執行。
* **操作步驟**：
  1. 人為破壞系統（如刪除 `main.py` 或核心二進位檔）。
  2. 模擬連續異常崩潰達 3 次以上。
  3. 檢查 `run.sh` 之退出行為。
* **預期結果**：
  - [x] 看門狗偵測到已連續回滾失敗，停止呼叫重啟。
  - [x] 行程以明確錯誤碼退出，防止磁碟寫滿死迴圈日誌。
* **驗收簽核**：`[ ] PASS  [ ] FAIL` ＿＿＿＿＿＿＿＿＿＿＿＿

---

## 5. 日誌佐證與關鍵欄位查核指引 (Evidence Inspection)

執行手動驗收時，驗收人員應查閱並截圖保存以下日誌關鍵欄位作為驗收佐證：

### 5.1 正常更新生命週期日誌 (`logs/update.log`)
```log
[2026-09-22 14:02:10] [INFO] [UpdateManager] 發現新版本: 1.1.0 (當前: 1.0.0)
[2026-09-22 14:02:10] [INFO] [AppUpdateClient] 成功解析 Delta 增量更新包: argus_delta-v1.1.0-arm64.tar.gz (大小: 2.4 MB)
[2026-09-22 14:02:15] [INFO] [UpdateManager] 磁碟剩餘空間檢查通過 (需求: 20MB, 可用: 14200MB)
[2026-09-22 14:02:18] [INFO] [UpdateManager] Delta 封包下載完成，校驗 SHA256 通過
[2026-09-22 14:02:19] [INFO] [install.sh] 正在建立 Delta 備份至 _internal/.patch_bak/...
[2026-09-22 14:02:20] [INFO] [install.sh] [✓] argus.zip 已原子覆蓋
[2026-09-22 14:02:20] [INFO] [UpdateManager] 狀態變更為 READY_TO_INSTALL
[2026-09-22 14:02:25] [INFO] [UpdateManager] 收到操作員確認重啟指令，發出 Exit Code 42
[2026-09-22 14:02:30] [INFO] [run.sh] 收到重啟代碼 42，啟動新版程式...
[2026-09-22 14:02:35] [INFO] [HealthCheck] /api/health 探針回應 200 OK，推論首幀已完成
[2026-09-22 14:02:35] [INFO] [UpdateManager] [COMMITTED] 成功確立升級至 v1.1.0，移除 .update_in_progress
```

### 5.2 異常回滾日誌 (`logs/update_rollback.log` 與 stdout)
```log
[2026-09-22 15:10:02] [WARNING] [run.sh] 偵測到更新評估窗口異常崩潰 (Exit Code: 1)
[2026-09-22 15:10:02] [INFO] [install.sh] 執行自動回滾程序...
[2026-09-22 15:10:02] [INFO] [install.sh] 偵測到 Delta 增量備份 (_internal/.patch_bak/)，執行局部秒級還原...
[2026-09-22 15:10:03] [INFO] [install.sh] [✓] argus.zip 已原子還原至原版本
[2026-09-22 15:10:03] [INFO] [install.sh] 寫入 .rollback_alert
[2026-09-22 15:10:05] [INFO] [run.sh] 回滾完成，重新喚醒穩定版 v1.0.0
```

---

## 6. 現場緊急維護與故障排除指南 (Troubleshooting Runbook)

當現場邊緣裝置在升級過程中遇到非預期故障時，維運工程師可依照以下排障順序處理：

### 6.1 手動強制回滾指令
若自動回滾看門狗因外力未觸發，工程師可透過 SSH 登入裝置執行以下單行指令復原：
```bash
# 優先嘗試 Delta 局部還原
cd /path/to/argus_predictor
bash scripts/install.sh --rollback
```
若 `.patch_bak/` 已遺失但存在全量備份：
```bash
# 全量還原
mv argus_predictor_bak argus_predictor
```

### 6.2 清除殘留告警標記
當確認系統已恢復穩定且排查完成後，清除 Web UI 告警橫幅：
```bash
rm -f .rollback_alert .update_in_progress
```

### 6.3 升級失敗現場保護
當需回報研發團隊除錯時，請打包收集以下檔案：
```bash
tar -czf argus_upgrade_debug_$(date +%Y%m%d).tar.gz \
    logs/update.log \
    logs/system.log \
    .rollback_alert \
    updates/staging/manifest.json \
    config.yaml
```
將壓縮檔附於 Gitea 相關 Issue 中，以利研發團隊迅速定位問題。
