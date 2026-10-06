# Argus Safety Predictor Nano (樹莓派專用版)

## 專案簡介
本專案為樹莓派 5 設計的 RTSP 即時推論系統，支援多串流、目標偵測，並提供 Web UI 設定介面。

## 專案目錄結構 (Project Structure)

本專案遵循標準 Python `src/` Layout 與領域驅動 (DDD) 分層架構：

```text
├── src/argus/               # 核心領域套件
│   ├── core/                # 系統配置與生命週期 (config_manager.py)
│   ├── capture/             # 串流拉取、影片處理與畫面合成 (stream_handler.py, video_handler.py, grid_composer.py)
│   ├── vision/              # YOLO / NCNN 視覺推論引擎封裝 (inference_engine.py)
│   ├── compliance/          # PPE 防護裝備與工安合規規則引擎 (compliance_engine.py)
│   ├── events/              # 事件生產、日誌記錄與當機診斷 (event_producer.py, stats_logger.py, retention_cleaner.py)
│   ├── integration/         # UMS 模型同步、狀態輪詢與 Issue 回報 (model_sync.py, ums_config.py, report_issue.py)
│   ├── web/                 # Flask 控制台、SSE 串流與 Web 介面 (web_ui.py, templates/)
│   └── main.py              # 系統協同主迴圈與推論排程
├── tests/                   # 階層化自動化測試套件
│   ├── unit/                # 各領域單元測試
│   ├── integration/         # 串流、狀態與 API 整合測試
│   ├── e2e/                 # 端到端工安合規與介面測試
│   ├── fixtures/            # 測試假物件 (mock_argus_agent.py)
│   └── data/                # 測試專用媒體檔案
├── scripts/                 # 診斷回報工具與自動化截圖腳本
├── docs/                    # 架構決策記錄 (docs/adr/) 與 mdBook 使用手冊 (docs/user-manual/)
├── assets/                  # 靜態影像與測試視訊資產
├── main.py                  # 根目錄薄入口 (Thin Entrypoint)
├── pyproject.toml           # 專案套件配置與 editable 安裝定義
├── pytest.ini               # Pytest 設定
└── argus_predictor.spec     # PyInstaller 單一二進位打包規格
```

## 啟動方式 (開發環境)
1. 安裝依賴與本地套件：
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```
2. 執行自動化測試（確保環境齊全）：
   ```bash
   pytest
   ```
3. 建置使用手冊 (選用，若有修改手冊)：`mdbook build docs/user-manual`
4. 執行主程式：`python main.py`
5. 瀏覽器開啟：`http://<樹莓派IP>:8188` (點擊頂部「📖 使用手冊」或訪問 `http://<樹莓派IP>:8188/manual/` 查閱完整操作說明)

## 部署指南 (強烈建議：直接在樹莓派上建置)

⚠️ **避免跨架構編譯 (Cross-compilation)** ⚠️
請**不要**在 Windows/Mac (x86_64) 上使用 QEMU 或 Docker ARM64 容器嘗試打包 PyInstaller。這不但速度極慢，而且 Python 含有 C 語言擴充套件 (如 OpenCV, Numpy, Ultralytics) 時，跨架構打包極容易遺漏動態庫 (`.so`)，導致在樹莓派上執行時發生閃退。

**最佳做法：把這份原始碼直接放到樹莓派上處理。**

### 方案 A：直接執行 (最推薦，最穩定)
在樹莓派本機上安裝依賴並透過 systemd 背景執行：
```bash
pip install -r requirements.txt
python main.py
```
*(建議寫一個 systemd service 讓它開機自動啟動)*

---

## 特殊情境：樹莓派無對外網路 (但與開發電腦在同區網)

若樹莓派處於封閉網路無法直接執行 `pip install`，最簡單的做法是**將你的開發電腦作為臨時 Proxy**：

1. **在有網路的開發電腦 (Windows/Mac/WSL) 啟動 Proxy：**
   ```bash
   pip install proxy.py
   proxy --hostname 0.0.0.0 --port 8899
   ```
   *(啟動後畫面會停住待命，Windows 若跳出防火牆警告請允許)*

2. **SSH 進入樹莓派，設定 Proxy 並安裝：**
   ```bash
   # 將 IP 換成你開發電腦的區網 IP
   export http_proxy="http://<開發電腦IP>:8899"
   export https_proxy="http://<開發電腦IP>:8899"
   
   # 像平常一樣安裝，流量會走開發電腦出去
   pip install -r requirements.txt
   ```

3. 裝完後，回到開發電腦按 `Ctrl + C` 關閉 Proxy 即可。

6. 專案內部套件依賴 (Git URL)：
   - `argus-eventlog`: `git+http://tncimweb.cminl.oa/git-server/guy.mai/argus-eventlog.git@master`
   - `ums-client`: `git+http://tncimweb.cminl.oa/git-server/guy.mai/ums-client.git@master`
   *(已包含在 `requirements.txt` 中，安裝時樹莓派需能存取內部 Git 伺服器)*

### 方案 B：打包成單一執行檔（`--onefile`）

> ⚠️ **此方案已不建議使用。** `--onefile` 每次啟動皆需解壓至暫存目錄，在樹莓派 5 上啟動時間約 10–20 秒，且**無法支援 Delta 增量更新**（詳見方案 C）。若無特殊需求，請優先採用**方案 C**。

若仍有需要，可在樹莓派本機上執行以下指令（僅供快速驗證）：

```bash
# 1. 建置 mdBook 使用手冊
mdbook build docs/user-manual

# 2. 使用 spec 檔封裝（加 --onefile 旗標覆蓋，僅供測試）
pyinstaller --onefile \
            --paths src \
            --add-data "src/argus/web/templates:argus/web/templates" \
            --add-data "templates:templates" \
            --add-data "config.yaml:." \
            --add-data "ums-api-config.json:." \
            --add-data "docs/user-manual/book:docs/user-manual/book" \
            --collect-all ultralytics \
            --collect-all flask \
            --collect-all argus_eventlog \
            --collect-all ums_client \
            --name argus_predictor \
            src/argus/main.py
```

### 方案 C：打包成單一目錄 (`--onedir`)（推薦正式部署）

`--onedir` 會產出一個**資料夾**（`dist/argus_predictor/`），內含執行檔與所有相依套件。優點是**啟動速度快**（無需解壓）、記憶體佔用低，且**支援 Delta 增量更新**（每次日常更新僅需下載 ~2.4 MB，而非整包 ~256 MB）。

#### 建置流程（兩步驟）

**步驟一：產生 Delta 增量包與 `argus.zip`（業務模組外置）**

```bash
# 建置 mdBook 使用手冊（首次或手冊有異動時）
mdbook build docs/user-manual

# 完整增量包（含 Web 模板與離線手冊，< 3.5 MB）
python scripts/build_delta_package.py

# 或純代碼修復模式（< 250 KB，不含手冊）
python scripts/build_delta_package.py --code-only
```

此步驟會在 `dist/` 下產生：
- `argus_delta-v{VERSION}-arm64.tar.gz` — 增量補丁包
- `argus_delta-v{VERSION}-arm64.tar.gz.sha256` — SHA-256 校驗檔

**步驟二：用 Spec 封裝完整安裝包**

```bash
# 用 argus_predictor.spec 封裝（業務模組已外置至 _internal/argus.zip）
pyinstaller argus_predictor.spec
```

#### 產出目錄結構（PyInstaller 6.0+）

```text
dist/argus_predictor/
├── argus_predictor          ← 主執行檔
├── scripts/                 ← 部署、維運與守護腳本
│   ├── run.sh               ← 守護啟動腳本 (監聽 Exit 42 重啟、崩潰自動回滾)
│   ├── install.sh           ← Delta 增量補丁套用與原子回滾腳本
│   ├── ask_and_report.sh    ← CLI 問題回報互動精靈 (Linux)
│   └── ask_and_report.bat   ← CLI 問題回報互動精靈 (Windows)
└── _internal/               ← 所有相依與資料（PyInstaller 6.0+ 統一放於此）
    ├── argus.zip            ← 業務代碼（可單獨被 Delta 更新取代）
    ├── config.yaml
    ├── ums-api-config.json
    ├── argus/web/templates/
    ├── docs/user-manual/book/
    └── (ultralytics, flask 等第三方庫...)
```

> **為什麼 `_internal/` 是子目錄？**  
> PyInstaller 6.0 起，`--onedir` 模式預設將所有依賴移入 `_internal/` 子目錄，讓根目錄只保留主執行檔與外置腳本，結構更清晰，且不影響執行行為。

#### 部署至樹莓派

封裝完成後，複製整個 `dist/argus_predictor/` 資料夾至樹莓派（**不可只複製執行檔**）：

```bash
# 將模型檔案與 config.yaml 放在目錄內
cp yolo26.pt dist/argus_predictor/
cp config.yaml dist/argus_predictor/

# 給予執行權限
chmod +x dist/argus_predictor/argus_predictor
chmod +x dist/argus_predictor/scripts/*.sh

# 推薦啟動方式：透過守護腳本啟動（支援 Exit 42 自動重啟與故障安全回滾）
cd dist/argus_predictor
bash scripts/run.sh

# 或直接執行主二進位檔
./argus_predictor
```

後續版本升級時，透過 **Delta 增量包**（步驟一產出的 `.tar.gz`）局部替換 `_internal/argus.zip` 即可，無需重新下載整包。`config.yaml` 與模型檔不受影響。

#### 打包完整性驗證（強烈建議）

封裝完成後，在樹莓派上執行內建探針，確認所有 import 與資料檔均正確打包：

```bash
# 人類可讀輸出（建置後立即執行）
./argus_predictor/argus_predictor --probe

# JSON 輸出（CI/CD 自動化整合，exit code 0=PASS / 1=FAIL）
./argus_predictor/argus_predictor --probe --json > probe_report.json
if [ $? -ne 0 ]; then
    echo "❌ 打包驗證失敗，請勿發佈！"
    cat probe_report.json
    exit 1
fi
echo "✅ 打包驗證通過，可部署至廠區"
```

探針涵蓋項目：第三方套件 import（cv2、ultralytics、flask、ncnn 等）、argus 所有業務子模組、`_internal/argus.zip` 與模板目錄存在性、YOLO 推論引擎類別可達性、Flask 路由完整性。
詳細說明見 [`scripts/probe_package.py`](scripts/probe_package.py)。
