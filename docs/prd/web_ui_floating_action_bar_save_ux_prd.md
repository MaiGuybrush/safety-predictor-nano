# Web UI 全域浮動儲存條與跨面板串流編輯狀態優化規格書 (PRD)

## Problem Statement

在現有的 Argus Safety Predictor Nano Web UI 中，系統參數設定與多路攝影機串流設定由左側面板（Master Panel）與右側串流詳細檢查器（Detail Inspector）共同組成。然而，目前的介面在設定儲存與操作體驗上存在以下關鍵痛點：

1. **儲存按鈕過深且隱蔽**：
   - 「儲存並套用設定」按鈕被固定放置在左側表單的最底部。因左側包含效能參數、模型來源、串流主清單及進階設定等多個卡片，使用者在標準解析度（如 1080p 或 768p 工控螢幕）下必須大幅向下捲動才能看到並點擊儲存按鈕。
2. **跨面板設定缺乏關聯感與直覺回饋**：
   - 當使用者在右側下方詳細設定區修改特定串流的 RTSP URL、畫面標籤、鏡頭 ID 或獨立模型時，右側並未提供專屬動作指引，使用者難以直覺理解「右側的修改需要由左側底部的全域儲存鍵統一提交」。
   - 在多路串流切換情境下，若修改了串流 #0 隨後點擊切換至串流 #1，畫面上沒有任何提示告知串流 #0 已有暫存修改，使用者容易產生「設定是否已生效」或「修改是否遺失」的疑慮。
3. **儲存操作導致畫面中斷**：
   - 目前表單提交採用標準 POST 重整全頁，每次儲存皆會強制重新載入整個網頁，導致右上方正在播放的即時攝影機影像（MJPEG Stream）發生瞬間斷訊與黑屏閃爍。

---

## Solution

在維持既有賽博龐克終端風格（Cyberpunk / Terminal Dark Green）與高效邊緣運算原則的前提下，引入 **全域浮動儲存條（Floating Action Bar）**、**跨面板未儲存狀態（Dirty State）指示機制** 與 **無縫 AJAX 非同步儲存**：

1. **全域浮動儲存條 (Floating Action Bar)**：
   - 平時無任何欄位修改時，浮動條保持隱藏，不遮擋任何操作畫面。
   - 一旦偵測到左側表單參數或右側串流詳細設定有任何修改，浮動條平滑自畫面底部向上滑出（Slide Up），並附帶呼吸微光與狀態提示：「`⚠ 偵測到尚未儲存的設定變更`」。
   - 浮動條包含兩大核心操作：
     - `[ ✓ 儲存並套用設定 ]`（Primary Action：高亮綠色按鈕）
     - `[ ✕ 放棄變更 ]`（Secondary Action：將所有欄位與串流資料還原至頁面載入時的初始狀態）
2. **多路串流未儲存狀態視覺指示 (Dirty Indicators)**：
   - 當右側串流詳細設定（URL、Label、Camera ID、自訂模型）被編輯時，左側對應的串流主清單項目會即時標註 `*` 或橘黃色提示點（例如：`#0 [大門入口] *`）。
   - 切換檢視其他串流時，已修改串流的記憶體草稿完整保留，標記維持顯示，讓使用者一目了然各路串流的變更狀態。
3. **一鍵還原機制 (Discard / Revert)**：
   - 點擊「放棄變更」按鈕時，系統即時將記憶體中之 `streamsList` 與各表單輸入項還原至初始狀態，清除所有 `*` 標記，並將浮動儲存條平滑收合。
4. **無縫 AJAX 非同步儲存與 Toast 通知 (Seamless AJAX Save & Toast)**：
   - 點擊儲存後，前端透過非同步 Fetch API 發送 POST 請求至後端。
   - 儲存過程中即時影像串流（MJPEG Feed）保持連線**完全不中斷**、不重整頁面。
   - 後端儲存 `config.yaml` 成功後，頂端跳出綠色 HUD Toast 提示：「`✓ 設定已成功儲存並生效`」，重設 Dirty 狀態並自動收合浮動條。

---

## User Stories

1. 作為系統操作員，當我在左側調整 FPS 限制、CPU 核心數或模型來源時，我希望畫面底部能自動滑出浮動儲存條，以便我不必捲動到頁面最下方就能立即看見並點擊儲存。
2. 作為系統操作員，當我在右側串流詳細設定區修改攝影機 RTSP URL 或標籤時，我希望畫面底部能同步顯示浮動儲存條，以便我能直覺完成存檔，不需在兩側面板間游移尋找儲存按鈕。
3. 作為維護人員，當我編輯特定串流的獨立模型與 URL 時，我希望左側串流清單對應的項目能立即顯示「*」未儲存標記，以便我清楚辨別哪些串流已被修改、哪些串流維持原樣。
4. 作為維護人員，當我在不同串流間切換檢查時，我希望先前串流所做的修改能夠安全暫存在記憶體中，並持續在清單中維持未儲存標記，以便我確認所有串流設定皆就緒後再一次性套用。
5. 作為系統操作員，若我誤改了參數或決定不套用剛才的編輯，我希望點擊浮動條上的「放棄變更」按鈕即可一鍵將所有全域參數與串流設定還原為初始載入值，並收合浮動條。
6. 作為現場監控人員，當我點擊「儲存並套用設定」時，我希望即時影像預覽畫面保持連線不中斷、不閃爍黑屏，以便我能持續監控廠區現場狀況。
7. 作為現場監控人員，當儲存成功時，我希望畫面上方能跳出明確的「設定已成功儲存並生效」Toast 通知，且浮動儲存條自動隱藏，以便我確認變更已被系統正確採納。
8. 作為系統操作員，當後端儲存發生網路或驗證錯誤時，我希望系統能跳出紅色錯誤 Toast 提示具體原因，且浮動儲存條維持展開，以便我進行修正或重試。
9. 作為使用 1024x768 / 1366x768 工控螢幕的操作人員，我希望浮動儲存條在響應式縮放下能自適應置中與縮小字級，不遮擋底部重要操作欄位。

---

## Implementation Decisions

### 1. 前端 UI 元件與 CSS 樣式
- **全域浮動儲存條 (Floating Action Bar)**：
  - 定位採用 `position: fixed; bottom: 1.2rem; left: 50%; transform: translateX(-50%) translateY(120%);`。
  - 當處於 Dirty 狀態時，加上 `.visible` class，設定 `transform: translateX(-50%) translateY(0);`，並賦予 `transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1)` 平滑滑入效果。
  - 視覺風格延續暗黑終端美學：深黑背景（`rgba(10, 10, 10, 0.95)`）、綠色邊框（`1px solid var(--text)`）、微光陰影（`box-shadow: 0 0 20px rgba(0, 255, 65, 0.25)`）。
- **HUD Toast 提示元件**：
  - 定位採用 `position: fixed; top: 1.2rem; right: 1.2rem; z-index: 10000;`。
  - 包含成功（綠色微光）與失敗（紅色警示）樣式，自動停留 3 秒後淡出。

### 2. 前端狀態管理與 Dirty State 監聽架構
- **原始快照 (Snapshot)**：
  - 頁面載入時記錄初始狀態快照：`initialFormSnapshot` 與 `CONFIG_INITIAL_STREAMS` 的深拷貝。
- **變更偵測 (Dirty Detection)**：
  - 監聽左側所有 `input`、`select`、`textarea` 之 `change` / `input` 事件。
  - 監聽右側串流詳細設定（`detail-input-url`、`detail-input-label`、`detail-input-camid`、自訂模型切換等）之異動。
  - `checkDirtyState()` 函式即時比較目前表單值與 `streamsList` 是否與初始快照存在差異：
    - 若有差異：顯示 Floating Action Bar，並在有異動之串流項目加上 `*` 標記。
    - 若還原至與快照完全一致：隱藏 Floating Action Bar，清除所有 `*` 標記。
- **放棄變更 (Discard)**：
  - `discardChanges()` 將 `streamsList` 深拷貝還原為初始快照，重新渲染左側清單與當前右側檢查器，並重設表單輸入欄位。

### 3. 非同步 AJAX 儲存合約 (API Contract)
- 前端送出方式：
  - 攔截表單提交或由浮動條之儲存按鈕發起 `fetch('/', { method: 'POST', body: formData, headers: { 'X-Requested-With': 'XMLHttpRequest' } })`。
- 後端處理（`web_ui.py`）：
  - 接收到 POST 請求時，解析 `streams_json` 與表單參數並安全寫入 `config.yaml`。
  - 若請求帶有 `X-Requested-With: XMLHttpRequest` 或 `Accept: application/json`，回傳 JSON：
    ```json
    {
      "status": "ok",
      "message": "設定已成功儲存並生效"
    }
    ```
  - 同時保留傳統瀏覽器無 JS 情況下的 Form POST 相容性（回傳 HTML 或重新導向）。

---

## Testing Decisions

### 測試原則
- 堅持最高層級測試 Seam（使用者行為層級），針對外部可觀察的 UI 互動與配置保存結果進行驗證，不綁定內部私有變數細節。

### 測試模組與 Seam 規劃
1. **主要測試 Seam (最高層級)：E2E / 瀏覽器互動測試 (Playwright)**
   - **驗證項目 1（初始狀態）**：載入首頁時，Floating Action Bar 預設不可見，串流清單無 `*` 標記。
   - **驗證項目 2（全域參數異動）**：修改左側 FPS 限制 -> Floating Action Bar 自動滑出。
   - **驗證項目 3（串流詳細設定異動）**：修改右側串流 #0 之標籤或 URL -> 串流 #0 旁出現 `*` 標記且 Floating Bar 保持顯示。
   - **驗證項目 4（多串流切換保護）**：切換至串流 #1 並修改 -> 串流 #0 與 #1 皆保有各自的修改與標記。
   - **驗證項目 5（放棄變更還原）**：點擊「放棄變更」-> 所有欄位與串流清單立即還原為載入初始值，Floating Bar 隱藏。
   - **驗證項目 6（AJAX 儲存與 Toast）**：再次修改欄位並點擊「儲存並套用設定」-> 發出 AJAX 請求，收到成功 Toast，Floating Bar 收合，`config.yaml` 實際寫入新值，且畫面即時影像 `src` 未被重新整頁重載。
2. **次要測試 Seam：後端 HTTP 端點測試 (Flask Test Client)**
   - 驗證 `POST /` 帶 `X-Requested-With: XMLHttpRequest` 能正確更新 `config.yaml` 並回傳 HTTP 200 JSON `{ "status": "ok", ... }`。

---

## Out of Scope

- 針對單一單獨串流進行獨立儲存（所有串流與全域參數統一經由全域儲存鍵原子性寫入 `config.yaml`）。
- 全自動自動存檔（Auto-Save on blur，避免使用者未完成輸入時頻繁觸發後端熱重載與重啟串流）。

---

## Further Notes

- 響應式相容性：依照 [ADR-016](ADR-016-responsive-font-scaling-and-layout.md)，Floating Action Bar 在各螢幕寬度（寬螢幕、標準、緊湊、小螢幕、行動直向）下皆能自適應縮放尺寸並維持居中。
- 保留左側原本表單最下方的儲存按鈕（亦可觸發相同儲存邏輯），雙向滿足不同操作習慣。
