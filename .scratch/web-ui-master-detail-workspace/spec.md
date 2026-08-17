Status: ready-for-agent

# Spec: Web UI 100vh 滿版工作台與 Master-Detail 主從式架構重整 (Web UI Master-Detail Workspace)

> 承接使用者需求與前次訪談決策。重構 Web UI 版面佈局為 100vh 滿版工控工作台（消除全頁視窗捲軸），並導入 Master-Detail（主從式架構）分離左側全域/主串流清單與右側縮小預覽及單一串流編輯器。

## Problem Statement

在先前的 Web UI 設計中存在以下操作體驗問題：
1. **全頁視窗捲軸（Window Scroll）導致右側重要即時影像被捲出螢幕**：當設定區塊增多或串流數量增加時，整頁產生外層垂直捲軸。使用者往下滑動編輯設定時，右側最重要的 Camera 即時監控畫面會被推到上方視窗外，無法一邊對照畫面一邊調校參數。
2. **串流卡片全部展開於左側造成表單過長且資訊重複**：若在左側直接為每路串流展開完整的輸入卡片（URL、Label、Camera ID、獨立模型、ROI 狀態等），會使左側長度急遽膨脹，且與右側的串流資訊展示產生冗餘。
3. **缺少專門的串流設定工作台模式**：使用者在進行攝影機參數與 ROI 區域微調時，需要一個緊湊的「右上鏡頭小預覽 + 右下單一串流屬性編輯與 ROI 快捷入口」聚焦工作台，而在日常巡檢時則需要「全版大畫面即時監控」。

## Solution

將 Web UI 介面全面升級為 **100vh 滿版工控工作台** 與 **Master-Detail 主從式架構**：
1. **100vh 滿版無視窗捲軸佈局**：畫面嚴格鎖定於視窗高度內（`100vh; overflow: hidden;`）。左側設定面板擁有自己獨立的垂直捲軸（`overflow-y: auto`），右側區域固定不捲動。
2. **Master-Detail 主從分離設計**：
   - **左側主面板 (Left Master Panel - 420px)**：包含全域推論效能、全域模型來源（Local vs UMS 專案選單）、精簡的串流選擇主清單（每項僅顯示序號、標籤、選中狀態與刪除鈕）、可摺疊的進階系統參數，以及全域儲存按鈕。
   - **右上角：即時鏡頭縮小預覽 (Camera Preview Widget - 45% 高度)**：固定展示當前左側選中串流的即時影像（`/video_feed/<stream_id>`），點擊可一鍵彈出全螢幕 ROI 編輯。
   - **右下角：選中串流規格與編輯器 (Stream Detail Inspector - 55% 高度)**：專屬編輯當前選中串流之 URL、畫面標籤、鏡頭 ID、自訂獨立模型，並顯示 ROI 狀態標籤與「全螢幕 / 編輯 ROI 區域」快捷按鈕。
3. **監控模式 (Monitor View) vs 設定模式 (Config View) 模式切換**：
   - 設定模式：展示左右雙欄 Master-Detail 工作台。
   - 監控模式：點擊 `[ TOGGLE_CONFIG ]` 收合左側，右側即時影像平滑擴展為滿版全螢幕大畫面監控（下方提供串流快速切換標籤列）。

## User Stories

1. As a 廠區維運人員, I want 在任何螢幕解析度下打開 Web UI 都不會出現全頁垂直捲軸, so that 畫面始終穩定在一個視窗內，操作流暢不晃動。
2. As a 廠區維運人員, I want 在左側面板滾動瀏覽或編輯全域設定時，右側的即時預覽與串流資訊始終固定在螢幕上, so that 我不會因為滑動表單而丟失即時鏡頭畫面。
3. As a 廠區維運人員, I want 在左側的「串流主清單」中點擊任一路串流（如 `STREAM #0 大門入口`）, so that 右上角預覽立即切換到該鏡頭畫面，右下角同步載入該鏡頭的詳細設定與 ROI 狀態。
4. As a 廠區維運人員, I want 在右下角的串流編輯卡片中直接修改當前選中串流的 URL、標籤、鏡頭 ID 與獨立模型, so that 我能專注微調單一攝影機設定，左側表單也不會被大量重複欄位塞爆。
5. As a 廠區維運人員, I want 在右下角看到當前選中串流的 ROI 警戒區狀態（如 `[ ROI: ACTIVE (大門警報區) ]`）, so that 我能清楚知道該鏡頭是否已劃定偵測範圍。
6. As a 廠區維運人員, I want 在右下角點擊 `[ 全螢幕 / 編輯 ROI 區域 ]` 按鈕, so that 能立即進入大畫面 Canvas 劃設多邊形，劃完儲存後無縫返回工作台。
7. As a 廠區維運人員, I want 在左側點擊 `[ + 新增串流 ADD_STREAM ]` 時自動加入新項目並自動切換至該新項目的右下角編輯器, so that 我可以快速填寫新增攝影機的參數。
8. As a 廠區維運人員, I want 在左側點擊串流旁的 `[ ✕ ]` 刪除特定串流, so that 可以直觀移除不再使用的攝影機，右側編輯器自動切換至剩餘串流。
9. As a 廠區維運人員, I want 在左側自由切換「本地檔案 Local」與「UMS 雲端同步 UMS」全域模型來源, so that 雲端模型與本地模型能一鍵套用至所有未覆蓋獨立模型的串流。
10. As a 廠區維運人員, I want 在不需要進行參數設定時點擊 `[ TOGGLE_CONFIG ]`, so that 左側面板自動收合，右側影像放大為全螢幕即時監控大畫面。
11. As a 廠區維運人員, I want 在進階參數區塊中展開 UMS 連線設定、Heartbeat 心跳與事件日誌記錄, so that 進階維運設定被妥善收納，不干擾日常核心參數調整。
12. As a 系統開發者, I want 前端在提交表單時自動將 Master-Detail 的各串流記憶體狀態序列化為標準 `streams_json`, so that 後端非破壞式寫入 `config.yaml` 並維持既有資料相容性。

## Implementation Decisions

### 1. 100vh 滿版 CSS 容器體系

- 根層級 `html, body` 設置 `height: 100vh; overflow: hidden; margin: 0; padding: 0;`。
- 頂部為固定高度 Header（含 Logo、Status Bar、`[ TOGGLE_CONFIG ]`）。
- 主區域 `.sys-core` 採用 Grid/Flex 排版：`height: calc(100vh - 110px); display: grid; grid-template-columns: 420px 1fr; gap: 1rem; overflow: hidden;`。
- **左側容器**：`height: 100%; overflow-y: auto; overflow-x: hidden;`（具備自訂細緻綠色 Scrollbar）。
- **右側容器**：`height: 100%; display: flex; flex-direction: column; gap: 1rem; overflow: hidden;`。

### 2. Master-Detail 狀態管理與前端互動

- **記憶體狀態結構**：
  前端 JavaScript 維護 `streamsList = [{url, label, camera_id, model, ums_model}, ...]` 與 `selectedStreamIndex`（預設 `0`）。
- **Master 清單渲染 (`renderMasterList()`)**：
  左側渲染簡潔串流列，當前選中項加上 `.active` 高亮邊框與霓虹綠背景。
- **Detail 編輯器渲染 (`loadStreamIntoDetail(index)`)**：
  選中特定 Index 時：
  - 更新右上角 `<img id="preview-cam-feed" src="/video_feed/{index}">`。
  - 將 `streamsList[index]` 的各項屬性填入右下角輸入框（URL, Label, Camera ID, Override Model Checkbox & Input）。
  - 自動呼叫 `/zone/<url>` 更新右下角 `[ ROI: ACTIVE/INACTIVE ]` 狀態標籤。
- **即時雙向同步 (`onDetailFieldChange()`)**：
  在右下角修改 URL/Label/Camera ID 時，即時更新記憶體中的 `streamsList[selectedStreamIndex]`，並即時更新左側 Master 列表對應列的文字標籤。
- **新增與刪除串流**：
  - 新增：`streamsList.push({url: ''})`，自動選中最新一筆並切換右下角編輯。
  - 刪除：移除該 Index 並將選中項移至合法範圍（至少保留 1 筆）。

### 3. 右下角 Detail 檢查器與 ROI 連動

- 右下角面板包含專屬操作列：
  - `[ 進入全螢幕 / 編輯 ROI 區域 ]` 按鈕：帶入當前 `selectedStreamIndex` 直接開啟全螢幕 Canvas 進行多邊形劃設，劃完保存後即時同步更新右下角 ROI 狀態標籤。

### 4. 監控模式 (Monitor View) 切換

- 點擊 `[ TOGGLE_CONFIG ]` 時：
  - `.sys-core` 加入 `.hide-config` 類別，左側面板隱藏（`display: none`）。
  - 右側容器切換為「大畫面全螢幕監控模式」（隱藏右下角編輯器，右上鏡頭預覽放大至 100% 高度，底部顯示各鏡頭切換按鈕）。

## Testing Decisions

- **測試原則**：以黑箱與端點整合驗證為主，確保 API 結構化讀寫、首頁渲染正確，以及全系統 67+ 項既有單元測試無回歸。
- **測試項目**：
  1. `test_web_ui_config_save.py`：驗證 Master-Detail 序列化輸出的 `streams_json` 能正確被後端持久化寫入 `config.yaml`。
  2. 驗證首頁 HTML 包含 Master 串流清單容器、Detail 編輯器容器與 100vh 視窗佈局標籤。
  3. 驗證全套單元測試套件 Pass。

## Out of Scope

- 多路串流在單一畫面內同時以九宮格（Grid Video Feeds）即時播放（維持現有輪播與個別串流切換播放機制）。
- WebRTC 串流低延遲解碼（維持現有 MJPEG / SSE 架構）。

## Further Notes

- UI 色彩全面貫徹 Argus 工控暗黑美學（深黑 `#050505`、終端綠 `#00ff41`、青藍 `#00e5ff`、警示橘 `#ffaa00`、危險紅 `#ff3333`）。
- 嚴格控制輸入框內邊距與字體大小，確保在 1080p 與 720p 螢幕下均能完美滿版不溢出。
