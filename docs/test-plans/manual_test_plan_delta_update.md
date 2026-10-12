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
> mdbook build docs/user-manual    # 首次或手冊異動時
> python scripts/build_delta_package.py --version 1.1.0 --output-dir dist/
> # 產出：dist/argus_delta-v{VERSION}-arm64.tar.gz 及 .sha256
> ```
>
> **步驟二：使用 Spec 封裝完整安裝包（需在樹莓派 ARM64 本機執行）**
> ```bash
> pyinstaller argus_predictor.spec # 業務模組將外置為 _internal/argus.zip
> # 產出：dist/argus_predictor/ 完整目錄
> ```
>
> **沙盒快速準備（軌道 B，跳過 ARM64 建置）：**
> ```bash
> # 建立沙盒目錄，模擬已部署的 argus_predictor/ 結構
> mkdir -p sandbox/argus_predictor/_internal/torch sandbox/argus_predictor/_internal/cv2
> touch sandbox/argus_predictor/_internal/torch/libtorch.so sandbox/argus_predictor/_internal/cv2/cv2.so
> python scripts/build_delta_package.py --zip-only sandbox/argus_predictor/_internal/argus.zip
> echo "1.0.0" > sandbox/argus_predictor/version.txt
> cp config.yaml ums-api-config.json main.py sandbox/argus_predictor/
> mkdir -p sandbox/argus_predictor/scripts
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
| **TC-04** | `install.sh --delta` 局部原子置換與零資料遺失 | P0 | 純 CLI 沙盒執行，僅更新業務層，保護重型庫與設定檔 | `argus.zip` 更新，`torch/cv2/config.yaml` 完好 | `[ ] PASS` |
| **TC-05** | Web UI 增量升級與 Exit 42 守護重啟 Commit 端到端驗證 | P0 | 前端 Cyberpunk 視覺、SSE 下載進度、立即重啟防呆、全螢幕倒數遮罩、Exit 42 重啟與健康 Commit | 完整經歷下載至重啟自動刷新，版本躍遷至 v1.1.0，標記自動清除 | `[ ] PASS` |
| **TC-06** | [異常 1] 健康檢查超時/崩潰自動局部回滾 | P0 | 注入新版崩潰，測試 `.patch_bak/` 秒級還原與 Web UI 告警 | 啟動失敗自動還原舊版 `argus.zip` 並發出 Web UI 告警 | `[ ] PASS` |
| **TC-07** | [異常 2] 磁檢空間不足防護 | P1 | 磁碟剩餘空間低於 20MB 時攔截 | 拒絕下載並記錄 `Insufficient disk space` 錯誤 | `[ ] PASS` |
| **TC-08** | [異常 3] 封包雜湊不符與損毀攔截 | P1 | 偽造/損毀之 Delta 封包防護 | 解壓前校驗失敗，拒絕覆蓋，保持原狀並顯示錯誤橫幅 | `[ ] PASS` |
| **TC-09** | [異常 4] 連續崩潰終止防護 (Rollback Loop Guard) | P2 | 舊版還原後依然崩潰的看門狗防護 | 一次回滾後若仍崩潰，直接退出，防止無窮重啟死迴圈 | `[ ] PASS` |

---

## 4. 詳細測試執行步驟 (Step-by-Step Test Procedures)

### TC-01：打包端業務解耦與 Delta 封包建置驗證

* **測試目的**：確認 `scripts/build_delta_package.py` 可正確將業務模組打包為 `argus.zip`，並產出合規之 Delta 增量更新包。
* **前置條件**：工作目錄為專案根目錄，虛擬環境已啟用。
* **操作步驟**：
  1. 執行標準 Delta 增量包建置：
     
     ```bash
     #src\argus\__init__.py 中 __version__ 需與此 --version 參數一致
     python scripts/build_delta_package.py --version 1.0.0 --output-dir dist/
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

### TC-04：`install.sh --delta` 局部原子置換與零資料遺失 (純 CLI 沙盒驗證)

* **測試目的**：驗證底層維運腳本 `scripts/install.sh --delta` 於命令列獨立執行時，能正確解壓 Delta 載荷、建立 `.patch_bak/` 備份，僅替換核心業務模組（`argus.zip`、前端模板、手冊），且嚴格保留龐大動態函式庫（`torch/`、`cv2/`）與既有設定檔（`config.yaml`）。
* **前置條件**：沙盒環境已依 2.1 節快速準備完成（含 mock `torch/libtorch.so` 與 `cv2/cv2.so`），TC-01 產出之 `dist/argus_delta-v1.1.0-arm64.tar.gz` 位於專案根目錄。
* **操作步驟**：
  1. 切換至沙盒目錄，記錄執行前檔案特徵與時間戳：
     ```bash
     cd sandbox/argus_predictor
     sha256sum _internal/argus.zip
     sha256sum config.yaml
     ls -l _internal/torch/libtorch.so
     ```
  2. 手動執行 Delta 安裝指令（指定相對於沙盒目錄的增量包路徑）：
     ```bash
     bash scripts/install.sh --delta ../../dist/argus_delta-v1.1.0-arm64.tar.gz
     ```
  3. 驗證局部備份目錄與檔案是否存在：
     ```bash
     ls -ld _internal/.patch_bak/
     ls -l _internal/.patch_bak/argus.zip
     ```
  4. 驗證置換結果與保護項目：
     ```bash
     # 業務代碼已更新 (雜湊變更)
     sha256sum _internal/argus.zip
     # 既有配置完全未動
     sha256sum config.yaml
     # 重型深度學習庫未受波及
     ls -l _internal/torch/libtorch.so
     # 版本檔案已更新
     cat version.txt
     ```
* **預期結果**：
  - [x] 執行時間在樹莓派 5 上小於 1 秒。
  - [x] `_internal/.patch_bak/` 成功建立且包含舊版 `argus.zip` 與 `version.txt` 備份。
  - [x] `_internal/argus.zip` 成功替換為新版，雜湊改變。
  - [x] `config.yaml` 雜湊與升級前完全一致，無任何修改。
  - [x] `_internal/torch/` 與 `_internal/cv2/` 修改時間與內容未變。
  - [x] `version.txt` 內容更新為 `1.1.0`。
* **驗收簽核**：`[ ] PASS  [ ] FAIL` ＿＿＿＿＿＿＿＿＿＿＿＿

---

### TC-05：Web UI 增量更新、SSE 進度串流與 Exit 42 守護重啟 Commit 端到端驗證

* **測試目的**：驗證操作員在瀏覽器端能直觀辨識「增量更新」標記、即時監看 SSE 下載進度條、完成安全二度確認後點擊「立即重啟套用」、觀察全螢幕 30 秒 Cyberpunk 重啟倒數與探針輪詢，並在背景捕捉 Exit Code 42 完成重啟且通過健康檢查 Commit。
* **前置條件**：
  1. Mock API 伺服器以 Delta 模式運行（提供 v1.1.0）：
     ```bash
     python scripts/mock_app_update_server.py --port 8190 --version 1.1.0
     ```
  2. 主程式以守護腳本 `run.sh` 啟動運行（實機或沙盒環境）：
     ```bash
     bash scripts/run.sh
     ```
  3. 瀏覽器開啟 Web UI 首頁：`http://<設備IP>:8188`。
* **操作步驟**：
  1. **檢查更新與增量視覺識別**：
     - 進入 Web UI 首頁，觀察頂端導覽列是否亮起動態呼吸徽章：`[ 🚀 增量更新可用: v1.1.0 (約 2.4 MB) ]`（若未自動出現，可點擊 `[ 系統更新 UPDATE ]` 彈窗並按 `[ ↻ 檢查最新版本 ]`）。
     - 點擊呼吸徽章開啟更新彈窗。
     - 檢查彈窗呈現項目：
       - 是否具有藍綠色高亮徽章 `[ 📦 增量更新 (Delta Patch) ]`。
       - 「更新類型」欄位是否顯示 `增量更新 (Delta)`。
       - 「封包大小」欄位是否顯示約 `2.4 MB`。
       - 動作按鈕 `[ ⬇ 下載更新包 ]` 為可點擊狀態，`[ ⚡ 立即重啟套用 ]` 初始為禁用狀態。
  2. **觸發下載與 SSE 進度串流觀察**：
     - 點擊彈窗內 `[ ⬇ 下載更新包 ]` 按鈕。
     - 觀察進度條追蹤區塊：
       - 下載進度條於 1~3 秒內從 0% 推進至 100%。
       - 傳輸速率與位元組即時跳動（如 `2.1 MB / 2.4 MB // 1.8 MB/s`）。
       - 進度達 100% 後，後端解壓完成並自動調用 Delta 局域置換，狀態躍遷為 `READY_TO_INSTALL`。
       - 進度文字顯示 `增量補丁已就緒！等待重啟套用 (Exit 42)`。
       - 導覽列徽章更新為：`⚠️ 增量補丁就緒，點擊重啟套用 (v1.1.0)`。
       - `[ ⚡ 立即重啟套用 ]` 按鈕變為橘黃色高亮啟用（具霓虹光暈陰影）。
  3. **觸發立即重啟套用與防呆確認**：
     - 點擊 `[ ⚡ 立即重啟套用 ]` 按鈕。
     - 觀察瀏覽器彈出二次防呆確認對話框：`系統即將執行重啟並套用新版本，確定要立即重啟嗎？`。
     - 點擊「確定」。
  4. **全螢幕重啟遮罩與探針健康評估觀察**：
     - 更新彈窗自動關閉，畫面彈出全螢幕 Cyberpunk 重啟遮罩（`#update-restart-overlay`）。
     - 遮罩標題顯示：`◈ ARGUS // 核心重啟升級中 (SYSTEM REBOOT) ◈`。
     - 提示警語：`正在進行二進位目錄原子替換與重啟程序... 背景守護行程即將喚起新版程式，請勿切斷電源或關閉瀏覽器。`
     - 圓形計時器自 `30` 秒開始每秒平滑遞減，下方進度條同步縮減。
     - 觀察主進程終端 Log：
       - 主行程呼叫 `sys.exit(42)` 正常終止退出。
       - `run.sh` 終端輸出：`[run.sh] 收到重啟代碼 42 (RESTART_FOR_UPDATE)，準備載入新版本...`。
       - `run.sh` 自動重新喚起新版程式，建立 `.update_in_progress` 評估標記。
     - 前端以 1.5 秒為週期持續向 `/api/health` 探針發送請求。
  5. **成功確立 (Commit) 與自動重新整理**：
     - 伺服器重新就緒，探針回傳 HTTP 200 Healthy。
     - 遮罩顯示綠色成功橫幅：`✓ 系統升級成功！核心與推論管線已全數就緒。成功升級至新版本 v1.1.0！即將自動重新整理...`。
     - 1.8 秒後網頁自動刷新 (`window.location.reload()`)。
  6. **重載後狀態核驗**：
     - 頂端導覽列版本標籤更新為 `v1.1.0`。
     - 頂端導覽列呼吸徽章自動隱藏消失。
     - 檢查日誌與進行中標記：
       ```bash
       grep "COMMITTED" logs/update.log
       test ! -f .update_in_progress && echo "[✓] .update_in_progress 已自動清除"
       ```
* **預期結果**：
  - [x] Web UI 清楚標示 Delta Patch 增量屬性，避免操作員誤以為要下載 300MB。
  - [x] SSE 通道實時推播下載位元組，無卡頓或頁面凍結現象。
  - [x] 成功進入 `READY_TO_INSTALL` 狀態，且「立即重啟套用」按鈕亮起。
  - [x] 點擊後彈出防呆對話框，確認後無縫進入全螢幕 30 秒倒數遮罩。
  - [x] 主進程發出 Exit Code 42，`run.sh` 成功重啟新版程式。
  - [x] 健康檢查通過後，遮罩提示成功並自動刷新頁面，版本變為 v1.1.0。
  - [x] `logs/update.log` 記錄 `[COMMITTED]`，`.update_in_progress` 已被刪除。
* **驗收簽核**：`[ ] PASS  [ ] FAIL` ＿＿＿＿＿＿＿＿＿＿＿＿

---

### TC-06：[異常注入 1] 健康檢查超時/崩潰自動局部回滾

* **測試目的**：模擬新版 Delta 補丁存在缺陷（如語法錯誤或開機崩潰），驗證看門狗能於 30 秒內自動秒級還原上一穩定版本。
* **前置條件**：系統處於 v1.0.0 穩定運行狀態，透過 `run.sh` 啟動。
* **操作步驟**：
  1. 依 TC-05 流程下載 Delta 補丁至 `READY_TO_INSTALL` 狀態（此時 `_internal/argus.zip` 已被替換，且舊版已備份至 `_internal/.patch_bak/`）。**在此時暫勿點擊重啟**。
  2. **故障注入**：故意損毀剛替換之新版 `argus.zip`（模擬新版本 bytecode 損毀或語法致命錯誤）：
     ```bash
     echo "CORRUPTED_BYTECODE" > _internal/argus.zip
     ```
  3. 於 Web UI 更新彈窗點擊 `[ ⚡ 立即重啟套用 ]`（或 API 發送 POST `/api/update/restart`），確認防呆視窗，觸發 Exit 42 重啟。
  4. 觀察 `run.sh` 捕捉啟動崩潰異常：
     - 主行程重啟嘗試載入 `argus.zip` 失敗，拋出致命例外並以非 0 代碼（Exit Code 1）退出。
     - `run.sh` 捕捉到異常崩潰，且偵測到 `.update_in_progress` 存在。
     - `run.sh` 自動呼叫 `scripts/install.sh --rollback`。
     - `install.sh` 偵測到 `_internal/.patch_bak/`，執行局部秒級還原。
     - 生成 `.rollback_alert` 標記檔並清除 `.update_in_progress`。
     - `run.sh` 自動重新喚醒還原後的穩定版 v1.0.0。
  5. 驗證回滾成效：
     - 檢查 `_internal/argus.zip` 是否已復原為原 v1.0.0 代碼。
     - 觀察 Web UI 前端全螢幕遮罩：探針 `/api/health` 偵測到 `rollback_occurred: true`，顯示紅色警示橫幅：`⚠️ 系統更新未通過健康檢查，已自動安全回滾至原版本`。
     - 點擊「重新載入頁面」後，系統持續正常運行，未成為磚機 (Brick)。
* **預期結果**：
  - [x] 回滾過程不搬移 1GB 全量目錄，耗時小於 1 秒。
  - [x] 系統未成為「磚機 (Brick)」，自動恢復正常工安推論。
  - [x] 操作員透過 Web UI 明顯獲知回滾事件與告警。
* **驗收簽核**：`[ ] PASS  [ ] FAIL` ＿＿＿＿＿＿＿＿＿＿＿＿

---

### TC-07：[異常注入 2] 磁檢空間不足防護

* **測試目的**：驗證邊緣裝置磁碟空間不足時，更新管理器能精準攔截，避免下載中途磁碟爆滿導致死機。
* **前置條件**：了解 Delta 預檢門檻（20 MB）與全量預檢門檻（650 MB）。測試於 Linux / 樹莓派環境或沙盒中進行。
* **操作步驟**：
  1. 透過暫存大檔案填滿受測磁碟分區，使剩餘空間小於 20 MB（或在獨立測試分區掛載小容量 tmpfs 模擬）：
     ```bash
     # 於測試分割區建立暫存大檔使剩餘空間剩下約 10MB (Linux/樹莓派)
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

### TC-08：[異常注入 3] 封包雜湊不符與損毀攔截

* **測試目的**：驗證被竄改、傳輸中斷損毀之 Delta 封包在解壓與套用前被嚴格攔截。
* **前置條件**：啟動 Mock 伺服器並加上 `--corrupt` 參數。
* **操作步驟**：
  1. 啟動損毀模擬伺服器：
     ```bash
     python scripts/mock_app_update_server.py --port 8190 --version 1.1.0 --corrupt
     ```
  2. 於 Web UI 點擊 `[ 系統更新 UPDATE ]` 彈窗中的 `[ ⬇ 下載更新包 ]`（或 API 發送 POST `/api/update/download`）。
  3. 觀察 `UpdateManager` 解壓後比對 `manifest.json` 與封包 SHA-256 雜湊之流程。
* **預期結果**：
  - [x] 解壓或雜湊檢查報錯 `Checksum mismatch` 或 `Manifest validation failed`。
  - [x] 系統狀態躍遷為 `FAILED`，不建立 `.patch_bak/`，更不覆蓋運行中之 `argus.zip`。
  - [x] Web UI 顯示紅色錯誤提示：「更新下載失敗：校驗碼不符」或「Checksum mismatch」。
* **驗收簽核**：`[ ] PASS  [ ] FAIL` ＿＿＿＿＿＿＿＿＿＿＿＿

---

### TC-09：[異常注入 4] 連續崩潰終止防護 (Rollback Loop Guard)

* **測試目的**：驗證當回滾後之舊版本依然發生致命錯誤時，守護行程具備終止保護，防止無窮重啟 (Infinite Restart Loop) 打滿磁碟日誌。
* **前置條件**：`run.sh` 正在執行中，且舊版本亦遭破壞。
* **操作步驟**：
  1. 人為破壞系統（如於主程序注入無法修復之語法錯誤）。
  2. 觀察 `run.sh` 的運行生命週期：
     - 第一次崩潰：`run.sh` 若偵測到 `.update_in_progress`，執行一次回滾並立即移除 `.update_in_progress`。
     - 第二次崩潰：重新喚起之舊版依然發生致命錯誤 (Exit Code != 0 且 != 42)，此時因 `.update_in_progress` 已不存在，`run.sh` 進入退出分支。
  3. 檢查 `run.sh` 之終端輸出與退出行為。
* **預期結果**：
  - [x] `run.sh` 輸出 `[run.sh] 程式異常終止 (Code: 1)，退出。`。
  - [x] 守護迴圈終止並退出行程，未陷入無窮死迴圈重啟。
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
