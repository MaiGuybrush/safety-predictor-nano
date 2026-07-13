# Argus Safety Predictor Nano (樹莓派專用版)

## 專案簡介
本專案為樹莓派 5 設計的 RTSP 即時推論系統，支援多串流、目標偵測，並提供 Web UI 設定介面。

## 啟動方式 (開發環境)
1. 安裝依賴：`pip install -r requirements.txt`
2. 執行：`python main.py`
3. 瀏覽器開啟：`http://<樹莓派IP>:8188`

---

## 封裝為可執行檔 (Raspberry Pi 部署)
若要在樹莓派上直接執行而無需在部署環境安裝 Python 套件 (`pip`/`uv`)，請依照以下步驟封裝：
### 1. 準備封裝環境 (非常重要)
**PyInstaller 不支援交叉編譯 (Cross-compilation)**。若你要產生可以在樹莓派 (ARM64 Linux) 上執行的二進位檔案，你**必須**在以下環境之一執行打包：
1. **直接在樹莓派 5 上**進行封裝。
2. 在支援 ARM64 架構的 Linux 虛擬機或 Docker 容器 (如 Ubuntu ARM64) 中進行。

在 Windows 或 Intel Mac (x86/x64) 上執行指令，只會產出 x86/x64 的執行檔，放到樹莓派會出現 `Exec format error`。

進入 ARM64 環境後，安裝 PyInstaller：
```bash
pip install pyinstaller
```

### 2. 封裝指令
在專案根目錄執行以下指令，將主程式與依賴封裝為單一可執行檔：

```bash
pyinstaller --onefile \
            --add-data "templates:templates" \
            --add-data "config.yaml:." \
            --collect-all ultralytics \
            --collect-all flask \
            --name argus_predictor \
            main.py
```

*注意：`--collect-all` 用於確保 `ultralytics` 與 `flask` 等大型相依套件能正確被打包。*

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
