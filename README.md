# Argus Safety Predictor Nano (樹莓派專用版)

## 專案簡介
本專案為樹莓派 5 設計的 RTSP 即時推論系統，支援多串流、目標偵測，並提供 Web UI 設定介面。

## 啟動方式 (開發環境)
1. 安裝依賴：`pip install -r requirements.txt`
2. 執行：`python main.py`
3. 瀏覽器開啟：`http://<樹莓派IP>:8188`

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

### 方案 B：硬要打包成單一執行檔
如果你一定要產出單一 `argus_predictor` 檔案，請**在樹莓派本機上**執行打包：

1. 進入樹莓派終端機，安裝 PyInstaller：
```bash
pip install pyinstaller
```

2. 執行打包指令：
在專案根目錄執行以下指令，將主程式與依賴封裝為單一可執行檔：

```bash
pyinstaller --onefile \
            --add-data "templates:templates" \
            --add-data "config.yaml:." \
            --collect-all ultralytics \
            --collect-all flask \
            --collect-all argus_eventlog \
            --collect-all ums_client \
            --name argus_predictor \
            main.py
```

*注意：`--collect-all` 用於確保 `ultralytics`、`flask`、`argus_eventlog` 與 `ums_client` 等相依套件能正確被打包。*

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
