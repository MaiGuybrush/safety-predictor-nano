# ADR-016：Web UI 響應式字級縮放與小螢幕佈局自適應架構

| 欄位 | 內容 |
|------|------|
| **狀態** | 已接受 (Accepted) |
| **日期** | 2026-08-21 |
| **決策者** | 開發團隊 |
| **相關 ADR** | [ADR-010](ADR-010-client-side-canvas-detection-overlay.md)、[ADR-011](ADR-011-per-stream-video-endpoint.md)、[ADR-012](ADR-012-decoupled-stream-fps-and-inference-sampling.md) |
| **相關 PRD** | [responsive_font_scaling_and_layout_prd.md](../prd/responsive_font_scaling_and_layout_prd.md) |

---

## 情境與問題

1. **基礎字級寫死導致小螢幕顯示範圍受限**：先前 Web UI 在 `:root` 中設定固定 `font-size: 150%`（約等於 24px 基準），且左側設定面板寬度固定為 `410px`。
2. **小螢幕與低解析度裝置體驗不佳**：在筆記型電腦、工控觸控螢幕（如 1024x768、1280x720、1366x768）或短螢幕環境下，過大的字體與元件間距佔用過多視窗面積，導致右側即時監控畫面（Live Feed）、ROI 警戒區與串流詳細檢查器可視面積嚴重不足，使用者需頻繁滾動頁面。

---

## 決策選項與決策

### 1. 縮放機制：純 CSS Media Queries 階梯斷點配合 rem 縮放

**決策：** 使用 CSS `@media` 斷點階梯動態調整 `:root` 的 `font-size` 百分比，配合全站既有的 `rem` 單位達成全域元素與字體等比例自適應縮放，不使用 JavaScript 監聽 `window.resize` 動態計算。

**理由：**
- **零 CPU 開銷**：純 CSS 由瀏覽器渲染引擎原生加速，完全不消耗 Raspberry Pi 5 邊緣運算 CPU 資源，亦不佔用前端 JavaScript 主執行緒。
- **維護性高**：因既有 HTML/CSS 架構已全面採用 `rem` 單位，僅需調整 `:root` 字級即可自動帶動全站元件（輸入框、按鈕、卡片、標籤）等比例縮放。

### 2. 斷點分級策略：四級寬度斷點 + 視窗高度緊湊修飾

**決策：**
- **寬螢幕 (≥ 1440px)**：`:root { font-size: 135%; }`，側邊欄 `400px`。
- **標準螢幕 (1200px ~ 1439px)**：`:root { font-size: 110%; }`，側邊欄 `350px`。
- **緊湊螢幕 (992px ~ 1199px)**：`:root { font-size: 95%; }`，側邊欄 `310px`。
- **小螢幕 (< 992px)**：`:root { font-size: 85%; }`，側邊欄 `280px`。
- **極窄/行動直向 (< 768px)**：佈局由雙欄 Grid 轉為單欄垂直堆疊（Single Column）。
- **高度約束 (視窗高度 ≤ 720px 且寬度 ≥ 768px)**：字級微調為 `88%`，並精簡 Header 與 Section Card 垂直內外距（padding/margin），最大化垂直可視範圍。

**理由：** 兼顧 1080p 大螢幕遠距監控清晰度、筆電/工控小螢幕顯示完整性，以及直向行動裝置的可用性。

### 3. Canvas ROI 與 YOLO 疊加層維持動態影像對齊

**決策：** 前端 HTML5 Canvas ROI 與 YOLO 邊界框維持依據 `<img id="preview-stream">` 與全螢幕畫面之 `clientWidth` / `clientHeight` 及正規化座標（`[0.0, 1.0]`）計算。

**理由：** 與 [ADR-010](ADR-010-client-side-canvas-detection-overlay.md) 完全相容，當 CSS 字級與佈局寬度變化引起圖片尺寸縮放時，Canvas 會自動跟隨縮放並保持像素級座標對齊。

---

## 影響與驗證

1. **向下相容性**：完全相容現有 API、SSE 串流、影像端點與設定檔格式。
2. **驗證方式**：
   - 於不同解析度（1920x1080、1366x768、1024x768、800x600、375x667）驗證排版無破版、無非預期橫向溢位。
   - 驗證 ROI 編輯模式與全螢幕告警反饋在各斷點下繪製精準。
