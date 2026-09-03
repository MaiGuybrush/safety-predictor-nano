# Argus Safety Predictor Nano (樹莓派專用版)

## 專案簡介
本專案為樹莓派 5 設計的 RTSP 即時推論系統，支援多串流、目標偵測，並提供 Web UI 設定介面。

## 啟動方式 (開發環境)
1. 安裝依賴：`pip install -r requirements.txt`
2. 建置使用手冊 (選用，若有修改手冊)：`mdbook build docs/user-manual`
3. 執行主程式：`python main.py`
4. 瀏覽器開啟：`http://<樹莓派IP>:8188` (點擊頂部「📖 使用手冊」或訪問 `http://<樹莓派IP>:8188/manual/` 查閱完整操作說明)

---

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

### 方案 B：打包成單一執行檔
如果你一定要產出包含 Web UI 與離線使用手冊的單一 `argus_predictor` 檔案，請**在樹莓派本機上**執行打包：

1. 進入樹莓派終端機，安裝 PyInstaller 與 mdBook：
```bash
pip install pyinstaller
# 確保系統已安裝 mdbook（若尚未建置 docs/user-manual/book）
```

2. 執行建置與打包指令：
在專案根目錄執行以下指令，將主程式、手冊與依賴封裝為單一可執行檔：

```bash
# 1. 建置 mdBook 使用手冊
mdbook build docs/user-manual

# 2. 封裝單一可執行檔
pyinstaller --onefile \
            --add-data "templates:templates" \
            --add-data "config.yaml:." \
            --add-data "docs/user-manual/book:docs/user-manual/book" \
            --collect-all ultralytics \
            --collect-all flask \
            --collect-all argus_eventlog \
            --collect-all ums_client \
            --name argus_predictor \
            main.py
```

*注意：`--collect-all` 用於確保 `ultralytics`、`flask`、`argus_eventlog` 與 `ums_client` 等相依套件能正確被打包；`--add-data` 會將 Web 範本與手冊網站打包進二進位檔。*

### 3. 部署至樹莓派
封裝完成後，在 `dist/` 資料夾下會產生 `argus_predictor` 檔案。

1. 將 `dist/argus_predictor` 複製到樹莓派。
2. 將你的模型檔案 (如 `yolo26.pt`) 及 `config.yaml` 放在同目錄。
3. 給予執行權限：
   ```bash
   chmod +x argus_predictor
   ```
4. 直接執行：
   ```bash
   ./argus_predictor
   ```

- 若模型檔案過大，封裝後的檔案體積會較大，確保樹莓派有足夠空間。
- 執行時請確保 `config.yaml` 與 `argus_predictor` 在同一目錄。

### 方案 C：打包成單一目錄 (`--onedir`)
與方案 B 不同，`--onedir` 會產出一個**資料夾**（`dist/argus_predictor/`），內含執行檔與所有相依套件。優點是**啟動速度快**（不需要每次啟動時解壓到暫存目錄）、記憶體佔用較低，且更新時只需替換整個目錄即可。

1. 在樹莓派本機上執行建置與打包指令：

```bash
# 1. 建置 mdBook 使用手冊
mdbook build docs/user-manual

# 2. 封裝為單一目錄
pyinstaller --onedir \
            --noupx \
            --exclude-module triton \
            --add-data "templates:templates" \
            --add-data "config.yaml:." \
            --add-data "docs/user-manual/book:docs/user-manual/book" \
            --collect-all ultralytics \
            --collect-all flask \
            --collect-all argus_eventlog \
            --collect-all ums_client \
            --name argus_predictor \
            main.py
```

*注意：*
- *`--noupx`：停用 UPX 壓縮。UPX 壓縮後的二進位檔在 ARM64 (樹莓派) 上可能因壓縮格式不相容而無法啟動，停用可避免此問題。*
- *`--exclude-module triton`：排除 `triton` 模組。`triton` 是 NVIDIA GPU 的 JIT 編譯器，本專案僅使用 CPU 推論，排除可大幅縮小打包體積並避免不必要的相依衝突。*

2. 部署至樹莓派：
   - 封裝完成後，`dist/` 下會產生 `argus_predictor/` **整個資料夾**，部署時需**完整複製整個目錄**（不可只複製執行檔）。
   - 將你的模型檔案 (如 `yolo26.pt`) 及 `config.yaml` 放在該目錄內。
   - 給予執行權限並執行：
     ```bash
     chmod +x argus_predictor/argus_predictor
     ./argus_predictor/argus_predictor
     ```

- 更新版本時，直接以新的 `argus_predictor/` 目錄覆蓋舊目錄即可（`config.yaml` 與模型檔若放在目錄內，覆蓋前請先備份）。
