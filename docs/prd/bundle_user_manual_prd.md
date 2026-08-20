# PRD: 打包使用手冊 (mdBook) 並於 Web UI 提供離線瀏覽連結

## Problem Statement

目前 Argus Safety Predictor Nano 部署於現場邊緣端（如 Raspberry Pi 5）時，現場操作員與工程師無法在無外網連線的環境下直接查閱系統操作指引。雖然專案已使用 mdBook 撰寫了完整的使用手冊（位於 `docs/user-manual`），但該手冊尚未打包進發佈的二進位檔案中，Web UI 介面上亦無對應的導覽入口，導致現場除錯與操作門檻提高。

## Solution

在 Flask Web UI 伺服器中新增手冊靜態檔案服務端點（`/manual/`），將 `mdbook build` 產生的 HTML 靜態網站目錄整合進系統，並做好開發環境與 PyInstaller 單一二進位檔封裝（`sys._MEIPASS`）的路徑相容性；同時於 Web UI 頂部導覽列提供顯眼的「📖 使用手冊」新分頁連結，讓使用者在任何連線至 Web UI 的瀏覽器上皆可隨時離線查閱完整操作手冊與 Mermaid 架構圖。

## User Stories

1. As a 現場操作人員, I want to 從 Web UI 頂部導覽列點擊「📖 使用手冊」按鈕, so that 我能直接開啟系統操作說明而無需另外尋找文件。
2. As a 現場維運工程師, I want 手冊能在無外網連線的邊緣裝置上正常顯示, so that 在封閉廠區內亦能離線查閱完整的架構圖與排錯指引。
3. As a 終端使用者, I want 點擊使用手冊連結時以新瀏覽器分頁開啟, so that 不會中斷目前即時監控畫面與偵測串流的檢視。
4. As a 終端使用者, I want 訪問 `/manual/` 或 `/manual/index.html` 時皆能看到手冊首頁, so that 網址輸入習慣不同皆可正常瀏覽。
5. As a 終端使用者, I want 手冊中的所有章節頁面、圖片、字型、CSS 與 JavaScript 能正確載入, so that 閱讀體驗完整且排版不跑版。
6. As a 終端使用者, I want 手冊中的 Mermaid 流程圖能正常渲染, so that 我能清晰理解串流處理與推論架構。
7. As a 終端使用者, I want 手冊內建的全文搜尋功能能正常運作, so that 我能迅速搜尋關鍵字找到特定設定說明。
8. As a 系統開發者, I want 本機執行 `python main.py` 開發時可直接讀取本機建置好的 `docs/user-manual/book` 產物, so that 開發與除錯無需每次重新打包。
9. As a 發佈工程師, I want PyInstaller 打包時能將手冊靜態資源一同打包進單一執行檔中, so that 部署至 Raspberry Pi 5 時只需拷貝單一執行檔與設定檔即可執行。
10. As a 系統管理者, I want 當手冊目錄不存在或尚未建置時存取手冊頁面會收到友善的 404 說明提示, so that 系統不會引發未捕獲例外或崩潰。
11. As a QA 測試人員, I want 能夠透過自動化 HTTP 測試驗證手冊路由的狀態碼與靜態資源傳遞, so that 確保版本更新時手冊存取不受影響。

## Implementation Decisions

1. **靜態檔案掛載與路由設計**：
   - 註冊 `/manual/` 與 `/manual/<path:filename>` 路由，預設指向 `index.html`。
   - 使用 Flask 內建安全傳輸機制 `send_from_directory`，防止路徑遍歷（Directory Traversal）安全漏洞。
   - 當手冊目錄遺失或尚未建置時，回傳友善的 404 訊息，提示需先執行 `mdbook build`。

2. **執行環境與資源路徑相容性 (PyInstaller & Dev Mode)**：
   - 定義資源路徑解析邏輯：優先偵測 `sys.frozen` 與 `sys._MEIPASS`。若處於打包二進位環境，則自臨時解壓縮目錄讀取 `docs/user-manual/book`；若處於本機開發環境，則相對於當前專案根目錄讀取 `docs/user-manual/book`。

3. **前端 UI 導覽整合**：
   - 在 `templates/index.html` 的頂端 Header 區塊（與切換面板按鈕並列）加入「📖 使用手冊」按鈕，設定 `target="_blank"` 於新分頁開啟 `/manual/`。
   - 採用與系統一致的終端機/Cyberpunk 風格樣式（`btn-exec`）。

4. **建置與打包整合規範**：
   - 更新專案文檔與建置流程，在發佈前執行 `mdbook build docs/user-manual`。
   - 在 PyInstaller 打包參數中加入 `--add-data "docs/user-manual/book:docs/user-manual/book"`。

## Testing Decisions

1. **測試原則 (External Behavior Only)**：
   - 僅透過 Flask 外部 HTTP 請求接口驗證外部行為，不依賴內部實作細節。
2. **測試縫隙 (Test Seams)**：
   - 使用 Flask `app.test_client()` 在最頂層 HTTP 路由縫隙進行測試。
3. **測試案例覆蓋範圍**：
   - 驗證 `GET /manual/` 回傳 HTTP 200 及正確的 HTML 內容。
   - 驗證 `GET /manual/01-quick-start.html` 等子章節可正常回傳。
   - 驗證 `GET /manual/css/variables.css` 等靜態資源具有正確之回應狀態。
   - 驗證手冊目錄不存在時回傳 HTTP 404 與錯誤說明。
   - 驗證首頁 `GET /` 回傳的 HTML 中包含指向 `/manual/` 的超連結。
4. **現有參照 (Prior Art)**：
   - 參考專案內既有的 `test_web_ui_ums_endpoints.py` 與 `test_web_ui_config_save.py` 測試結構。

## Out of Scope

1. 不修改現有 mdBook 各章節的 Markdown 內容或排版。
2. 不在 Python 應用程式啟動時於背景執行 `mdbook build`（編譯為建置/發佈階段之責任）。
3. 不在 Web UI 提供手冊內容的線上編輯或上傳介面。

## Further Notes

- `mdbook-mermaid` 之靜態資源已包含在原始碼中，後續建置只需確保環境具備 `mdbook` 與 `mdbook-mermaid` 即可直接建置。
