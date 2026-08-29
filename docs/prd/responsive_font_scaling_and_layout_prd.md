# 前端介面響應式字級縮放與小螢幕佈局優化規格書 (PRD)

## Problem Statement

在現有的 Argus Safety Predictor Nano Web UI 中，全域樣式在 `:root` 寫死了 `font-size: 150%`，且主設定面板寬度固定為 `410px`。
這在 1080p（1920x1080）或更大顯示器上能提供清晰的遠距可讀性，但在以下情境會產生嚴重的可用性問題：
1. **小尺寸螢幕與筆電（如 1024x768、1280x720、1366x768）**：
   - 150% 的根字級（相當於 24px 基準）使所有使用 `rem` 的文字、輸入框、按鈕與間距大幅膨脹。
   - 固定 410px 寬度的左側設定面板佔去超過 35%~40% 的視窗寬度，導致右側即時監控畫面（Live Stream Preview）、ROI 編輯區與串流詳細檢查器（Detail Inspector）的可視範圍被過度擠壓。
2. **垂直空間不足（高度 ≤ 720px）**：
   - 頂部導航狀態列（Header & Status Bar）與卡片上下內距偏大，擠壓主要監控視窗的高度空間。
3. **行動/直向窄螢幕（< 768px）**：
   - 雙欄左右 Grid 強制並排導致介面內容左右重疊或被截斷。

---

## Solution

在維持 Argus 經典暗黑工業風格（Cyberpunk Terminal Green / Cyan）與零額外 CPU/JS 負載的前提下，引入 **4 階響應式斷點（4-Tier Breakpoints）與高度自適應樣式**：

1. **多階層響應式字級與寬度階梯**：
   - **寬螢幕 / 桌機（≥ 1440px）**：`:root { font-size: 135%; }`，側邊欄寬度 `400px`，寬敞舒適。
   - **標準螢幕 / 筆電（1200px ~ 1439px）**：`:root { font-size: 110%; }`，側邊欄寬度 `350px`。
   - **緊湊螢幕 / 平板橫向（992px ~ 1199px）**：`:root { font-size: 95%; }`，側邊欄寬度 `310px`。
   - **小型螢幕 / 低高度（< 992px 或 高度 ≤ 720px）**：`:root { font-size: 85%; }`，側邊欄寬度 `280px`，精簡 Header 內距與元件間隙。
2. **極窄螢幕單欄堆疊（< 768px）**：
   - 將主工作區 `.sys-core` 由雙欄 Grid 轉為單欄垂直堆疊（Single Column Layout），或預設聚焦影像監控，可透過「切換面板」切換設定。
3. **高度約束緊湊模式（Height ≤ 720px）**：
   - 自動縮減 `.top-container`、`.section-card` 的上下 padding 與 margin，使右側預覽圖與串流詳細資訊能完整顯示於一屏內。
4. **畫布與疊加層無損自適應**：
   - HTML5 Canvas ROI 與 YOLO 偵測框定位原生綁定於 `<img id="preview-stream">` 的 `clientWidth` / `clientHeight` 與正規化座標，字級調整完全不影響座標計算與視覺貼合。

---

## User Stories

1. **作為現場操作人員（使用 1024x768 / 1366x768 小型觸控螢幕或現場工控螢幕）**：
   - 我希望介面字體與側邊欄能自動縮減至適當尺寸，以便右側能完整呈現監控鏡頭影像與警戒區設定，不需頻繁左右或上下大幅捲動。
2. **作為中控室監控人員（使用 1080p / 2K / 4K 大螢幕）**：
   - 我希望介面保持原本的大字體與清楚讀數，確保站立或遠距離時仍能一目了然看清系統狀態與模型偵測數值。
3. **作為使用低解析度筆電的巡檢維護人員（高度 ≤ 720px）**：
   - 我希望頂部狀態列與卡片邊距能更緊湊，讓即時畫面與下方的串流設定檢查器同時完整可見。
4. **作為使用行動裝置或直向平板的操作人員（< 768px）**：
   - 我希望介面能自適應為單欄排列，並保有足夠的觸控點擊空間，避免版面破版或橫向超出視窗。
5. **作為邊緣運算系統維護者（Raspberry Pi 5 環境）**：
   - 我希望所有縮放邏輯完全透過瀏覽器端 CSS Media Queries 實現，不增加任何 Python 後端或 JavaScript 輪詢負擔。

---

## Implementation Decisions

### 1. 斷點與樣式階層對照表

```css
/* 預設：寬螢幕 (≥ 1440px) */
:root {
    font-size: 135%;
}
.sys-core {
    grid-template-columns: 400px 1fr;
    gap: 0.8rem;
    padding: 0.6rem 1.2rem 0.8rem 1.2rem;
}

/* 斷點 1：標準桌面 / 筆電 (1200px ~ 1439px) */
@media (max-width: 1439px) {
    :root { font-size: 110%; }
    .sys-core { grid-template-columns: 350px 1fr; gap: 0.7rem; }
}

/* 斷點 2：緊湊螢幕 / 小型筆電 (992px ~ 1199px) */
@media (max-width: 1199px) {
    :root { font-size: 95%; }
    .sys-core { grid-template-columns: 310px 1fr; gap: 0.6rem; padding: 0.5rem 0.8rem; }
}

/* 斷點 3：小螢幕 (< 992px) */
@media (max-width: 991px) {
    :root { font-size: 85%; }
    .sys-core { grid-template-columns: 280px 1fr; gap: 0.5rem; padding: 0.4rem 0.6rem; }
}

/* 斷點 4：極窄螢幕 / 行動直向 (< 768px) */
@media (max-width: 767px) {
    html, body { overflow-y: auto; height: auto; }
    .sys-core {
        display: flex;
        flex-direction: column;
        height: auto;
        overflow: visible;
    }
    .panel, .right-workspace { height: auto; overflow: visible; }
    .preview-container { min-height: 240px; }
}

/* 高度緊湊模式 (視窗高度 ≤ 720px) */
@media (max-height: 720px) and (min-width: 768px) {
    :root { font-size: 88%; }
    .top-container { padding: 0.35rem 0.8rem 0.25rem 0.8rem; }
    .sys-core { padding: 0.4rem 0.8rem 0.5rem 0.8rem; gap: 0.5rem; }
    .section-card { padding: 0.5rem; margin-bottom: 0.5rem; }
    .preview-container { min-height: 160px; }
    .detail-inspector { min-height: 180px; padding: 0.5rem 0.7rem; }
}
```

---

## Testing Decisions

1. **多解析度視覺檢驗標準**：
   - 1920x1080 (FHD)：版面字體清晰，側邊欄 400px，影像預覽區寬裕。
   - 1366x768 (常見筆電)：字級自適應為 110%，無溢位破版，影像預覽與檢查器均可見。
   - 1024x768 (4:3 工控螢幕)：字級 95%，側邊欄 310px，右側監控影像保持完整長寬比。
   - 800x600 / 1280x600 (極短螢幕)：高度緊湊模式生效，Header 與間距自動縮小。
   - 414x896 (手機/直向)：單欄順暢排列。
2. **互動元件回歸測試**：
   - 全螢幕 Modal 告警動畫與關閉按鈕在小螢幕下正常運作。
   - 日誌檢視彈窗（Log Viewer Modal）在各斷點下尺寸正常自適應。
   - Canvas ROI 頂點繪製與拖曳在小螢幕縮放下座標對齊無位移。

---

## Out of Scope

- 允許使用者自訂手動縮放滑桿（一律依 CSS 斷點全自動感應）。
- 將桌面版與行動版切換為完全獨立的兩套 HTML template。
