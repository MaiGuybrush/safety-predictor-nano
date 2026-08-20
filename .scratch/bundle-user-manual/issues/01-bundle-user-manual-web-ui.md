# 01 — 打包 mdBook 使用手冊並於 Web UI 提供離線瀏覽連結

**What to build:**
提供端到端的使用手冊離線查閱功能：將已建置的 mdBook HTML 靜態手冊掛載至 Web 伺服器的 `/manual/` 端點，支援 PyInstaller 打包環境與本機開發環境的路徑解析；在 Web UI 頂部導覽列提供顯眼的「📖 使用手冊」新分頁按鈕；並撰寫完整的自動化測試驗證首頁連結、手冊首頁、子章節及靜態資產載入。

**Blocked by:** None — can start immediately

**Status:** resolved

- [x] Web 伺服器具備資源路徑解析邏輯，相容 PyInstaller 執行環境 (`sys._MEIPASS`) 與本機開發環境
- [x] Web 伺服器掛載 `/manual/` 與 `/manual/<path:filename>` 路由，預設回傳手冊首頁 `index.html`
- [x] 存取子頁面（如 `01-quick-start.html`）與靜態資產（CSS, JS, Fonts, Images）能正確回應
- [x] 若手冊目錄不存在時，安全回傳 HTTP 404 說明訊息而非拋出未捕獲例外
- [x] Web UI 頂部 Header 包含連往 `/manual/` 的「📖 使用手冊」按鈕，點擊後以新分頁開啟
- [x] 撰寫單元/整合測試，驗證手冊路由、子資源請求、404 提示與首頁連結存在性，測試全數通過
- [x] 更新 `AGENTS.md` 說明文件中的 PyInstaller 打包指令，納入手冊靜態資料夾
