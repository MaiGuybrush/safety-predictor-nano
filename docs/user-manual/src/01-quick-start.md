# 第 1 章：快速開始

本章提供端到端的快速上手導引，協助您在最短時間內完成模型準備、取得攝影機 RTSP 串流，並透過 Web 管理介面串接 **UMS (Universal Model Studio)** 雲端模型管理平台與 **Argus** 集中安防監控系統。

---

## 快速上手流程概覽

完成系統串接僅需以下三大步驟：

```mermaid
graph LR
    A[步驟 1: 模型準備<br/>UMS 雲端 / 本地目錄] --> C[步驟 3: 系統配置與串接<br/>Web 管理介面]
    B[步驟 2: 取得 RTSP 串流<br/>Argus Agent / IP Camera] --> C
    C --> D[即時 AI 推論監控 &<br/>Argus 事件回報]
```

---

## 步驟 1：模型準備

系統支援 **UMS 雲端自動同步** 與 **本地模型目錄** 兩種載入方式，請依您的使用情境選擇：

### 方法一、使用 UMS (Universal Model Studio) 雲端模型（推薦）

透過 UMS 平台可進行集中式的 AI 模型版本管理、自動部署與快取同步：

1. **建立與訓練模型**：
   - 登入 UMS 平台並建立/訓練您的目標偵測模型。操作細節請參閱 [UMS 使用手冊](http://tnvcimweb2.cminl.oa/ums/user-manual)。
2. **申請 API Key 金鑰**：
   - 進入 UMS「全域設定」頁面中的「API 金鑰管理」進行申請。詳細步驟請參考 [UMS API 金鑰管理說明](http://tnvcimweb2.cminl.oa/ums/user-manual/global_settings.html#api-%E9%87%91%E9%91%B0%E7%AE%A1%E7%90%86-api-keys)。
   - **請記錄並妥善保存此 API Key**，後續將在 Web 管理介面中用於系統授權與連線。

---

### 方法二、準備本地模型檔案（目錄架構規範）

若您已有自行訓練或匯出的模型權重檔，可直接放置於裝置本機端使用。

> [!IMPORTANT]
> **必須為每個模型建立獨立專屬目錄**：
> 系統在設定本地模型時，指定的是**「模型目錄」**而非單一檔案路徑。系統會自動掃描該目錄內的檔案並依格式偏好（ONNX > PyTorch > NCNN）自動解析。
> 
> **切勿將多個不同模型的檔案混放在同一目錄內**，否則會導致推論引擎載入非預期的權重或解析衝突。

- **支援檔案格式**：
  - ONNX 格式：`.onnx`（在樹莓派 ARM64 環境具備最佳推論效能，強烈推薦）
  - PyTorch 權重檔：`.pt`
  - NCNN 格式：`.ncnn.param` + `.ncnn.bin`
- **建議目錄結構範例**：

```text
models/
├── person_detector/          # 模型 1 專屬目錄
│   └── best.onnx             # (或 best.pt / best.ncnn.param + best.ncnn.bin)
└── safety_helmet/            # 模型 2 專屬目錄
    └── helmet.onnx
```

---

## 步驟 2：取得 RTSP 串流

請依據現場攝影機架構選擇適合的串流來源：

### 情境一、使用 Argus Agent 串流（推薦）

搭配 **Argus Agent** 串接至 ARGUS 集中安防系統，可獲得即時事件推播、雲端健康度監控與集中管理能力：

1. 透過 Argus Agent 介面新增現場 IP Camera。
2. 於 Argus Agent 攝影機卡片資訊中，複製系統所提供的**分享 RTSP 串流網址**（格式通常包含 `rtsp://<agent-ip>:8554/live/cam-xx`，非 IP Camera 原始串流）。詳細操作請參考 [Argus Agent 使用手冊 4.1 章節]。
3. 透過此分享串流，Argus Predictor 可與 Argus 平台精準對應鏡頭編號（Camera ID）。

---

### 情境二、直接使用 IP Camera 原始 RTSP

若為獨立運作或未部署 Argus Agent 之環境，可直接連線至 IP Camera：

1. 取得現場 IP Camera 廠商提供的標準 RTSP 串流網址（例：`rtsp://admin:password@192.168.1.50:554/h264Preview_01_main`）。
2. 確認網路環境（如防火牆、網段）允許樹莓派邊緣裝置連通該 RTSP 來源。

---

## 步驟 3：系統配置與串接

完成上述準備後，開啟瀏覽器進入 Argus Predictor 的 Web 管理介面進行設定：

```text
http://<裝置-IP>:8188/
```

（若在設備本機測試，請輸入 `http://localhost:8188/`）

---

### 3.1 設定 UMS 平台連線（若採用方法一）

1. 在左側面板點擊 `「[ ADVANCED_SYSTEM_PARAMETERS ]」` 展開進階設定。
2. **使用廠區快速選單 (推薦)**：於「廠區預設快速選單 (FAB PRESETS)」下拉選單選取設備所在的廠區（如 OA 辦公網段、FAB 1、FAB 3 等），系統將自動帶入該廠區專屬的主備雙端點（`src1` 與 `src2`）。
3. **自訂端點 (選填)**：若需增設或修改端點，可直接編輯端點輸入框，或點擊 `「+ 新增備援端點」` / `「✕」` 按鈕自由動態管理。
4. 於 **UMS API KEY** 貼上步驟 1 申請的 API Key（可點擊「顯示」確認明文）。
5. 點擊 `「[ 測試連線 ]」` 按鈕，系統將依序檢測所有配置的端點，並在介面上清楚回報各端點的獨立連線狀態（如 `src1: 正常 (N models)`）與整體狀態。

![進階系統參數與 UMS 連線設定](./images/settings-advanced-ums.png)

#### 各廠區 UMS 服務 URL 對照表

系統已內建下列各廠區 UMS 服務端點 URL（選取廠區預設選單即可自動帶入）：

| 廠區 / 網段 | UMS 服務端點 URL（主備雙端點） |
|:---|---|
| **OA 辦公網段** | • `http://tncimweb1.cminl.oa/umsapiproxy/fab4ums` (src1 主)<br>• `http://tncimweb2.cminl.oa/umsapiproxy/fab4ums` (src2 備) |
| **FAB 1** | • `http://10.26.11.108/umsapiproxy/fab4ums` (src1 主)<br>• `http://10.26.11.109/umsapiproxy/fab4ums` (src2 備) |
| **FAB 3** | • `http://10.75.1.208/umsapiproxy/fab4ums` (src1 主)<br>• `http://10.75.1.209/umsapiproxy/fab4ums` (src2 備) |
| **FAB 6** | • `http://10.99.1.143/umsapiproxy/fab4ums` (src1 主)<br>• `http://10.99.1.144/umsapiproxy/fab4ums` (src2 備) |
| **FAB 7** | • `http://10.107.1.148/umsapiproxy/fab4ums` (src1 主)<br>• `http://10.107.1.149/umsapiproxy/fab4ums` (src2 備) |
| **FAB 8** | • `http://10.109.1.129/umsapiproxy/fab4ums` (src1 主)<br>• `http://10.109.1.130/umsapiproxy/fab4ums` (src2 備) |
| **FAB T6** | • `http://10.59.119.183/umsapiproxy/fab4ums` (src1 主)<br>• `http://10.59.119.184/umsapiproxy/fab4ums` (src2 備) |
| **FAB TS1** | • `http://10.242.1.114/umsapiproxy/fab4ums` (src1 主)<br>• `http://10.242.1.115/umsapiproxy/fab4ums` (src2 備) |
| **FAB T1** | • `http://172.16.12.161/umsapiproxy/fab4ums` (src1 主)<br>• `http://172.16.12.162/umsapiproxy/fab4ums` (src2 備) |
| **FAB T2** | • `http://172.20.11.164/umsapiproxy/fab4ums` (src1 主)<br>• `http://172.20.11.169/umsapiproxy/fab4ums` (src2 備) |
| **FAB T3** | • `http://10.32.203.43/umsapiproxy/fab4ums` (src1 主) |

---

### 3.2 配置全域 AI 模型

在左側「02 // 全域模型來源配置」區塊：

![全域模型來源配置](./images/model-source-global.png)

- **若使用 UMS 雲端模型**：
  1. 點選 `「[ UMS 雲端同步 UMS_SYNC ]」`。
  2. 於「UMS 專案」下拉選單選取專案名稱。
  3. 於「UMS 模型」下拉選單選取模型。
  4. 「模型版本」建議維持 `latest`（系統將自動同步最新發布之 Active 版本）。
- **若使用本地模型**：
  1. 點選 `「[ 本地檔案 LOCAL ]」`。
  2. 於「模型檔案路徑」欄位填入**模型專屬目錄路徑**（例：`models/person_detector/` 或 `models/safety_helmet/`，請勿指定為單一檔案檔名）。
- **模型格式偏好類別**：維持預設 `AUTO` 即可（系統將優先自動採用 ONNX 格式）。

---

### 3.3 配置 RTSP 攝影機串流

1. 確認左側「03 // 運作模式與串流清單」中「運作模式 (MODE)」設定為 `「RTSP 多路模式 (MULTI_STREAM)」`。
2. 點擊 `「+ 新增串流 ADD_STREAM」` 或點選現有串流項目。
3. 在右側「串流詳細屬性檢視器」中設定攝影機屬性：

![串流詳細屬性檢視器](./images/stream-detail-inspector.png)

- **串流 URL**：貼上步驟 2 取得的 RTSP 串流網址。
- **畫面標籤 (LABEL)**：輸入容易辨識的鏡頭名稱（例：`產線 A 區入口`）。
- **鏡頭識別碼 (CAMERA_ID)**：
  - 若使用 **Argus Agent** 串流，系統會自動比對並帶入對應的 `camera_id`，請保持預設以確保事件正確回傳至 Argus 平台。
  - 若為獨立 IP Camera，可自訂鏡頭編號（例：`cam-01`）。

![Camera ID 防呆警示](./images/stream-camid-warning.png)

---

### 3.4 儲存並啟用即時推論

1. 捲動至左側面板底部，點擊青綠色按鈕 `「[ EXECUTE_UPDATE ]」`。
2. 系統將自動執行熱重載（Hot-Reload），後端開始拉取串流並進行 AI 目標偵測。
3. 觀察右側預覽視窗，確認影像正常載入且畫面上出現目標偵測邊界框與標籤。

![主介面即時推論預覽](./images/ui-main-layout.png)

4. 若採用 UMS 模式，可隨時點擊頂部狀態列中的 `「[ SYNC_MODELS ]」` 按鈕，手動觸發最新模型同步檢查，確認右側顯示同步結果（例：`OK:1 FAIL:0`）。

![模型同步狀態](./images/model-sync-status.png)

---

## 下一步

- 認識系統完整操作介面與純監控模式：請參閱 [第 2 章：介面導覽與基礎操作](./02-ui-overview.md)。
- 深入串流配置與影片驗證模式：請參閱 [第 3 章：串流與影像來源管理](./03-stream-management.md)。
- 深入模型格式與單路模型獨立覆蓋：請參閱 [第 4 章：AI 模型配置與 UMS 雲端同步](./04-model-management.md)。
- 劃定目標警戒與禁止進入區域：請參閱 [第 5 章：ROI 偵測區域編輯與全螢幕即時監控](./05-roi-and-fullscreen.md)。
- 調校推論幀率與進階系統效能：請參閱 [第 6 章：系統參數與進階設定](./06-system-settings.md)。
