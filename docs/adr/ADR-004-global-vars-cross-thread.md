# ADR-004：模組級全域變數作為跨執行緒資料通道

| 欄位 | 內容 |
|------|------|
| **狀態** | 已接受 (Accepted) |
| **日期** | 2026-08-11 |
| **決策者** | 開發團隊 |
| **相關 PRD** | [ncnn_support_prd.md](../prd/ncnn_support_prd.md) |

---

## 情境與問題

主推論迴圈（main thread）需要將兩類資料傳遞給 Flask daemon 執行緒：
1. **`LATEST_FRAME`**：最新的 MJPEG 影格（bytes）
2. **`MODEL_INFO`**：目前載入的模型後端資訊（dict）

需要選擇跨執行緒的資料共享機制。

## 決策選項

### 選項 A（已採用）：模組級全域變數（`web_ui.LATEST_FRAME`、`web_ui.MODEL_INFO`）
主執行緒直接賦值給 `web_ui` 模組的屬性，Flask 執行緒讀取時取得最新值。

### 選項 B：`threading.Queue`
使用 Queue 傳遞資料，Flask 端消費最新值。

### 選項 C：`threading.Event` + 共享物件
使用 Event 通知 Flask 執行緒有新資料，Flask 從共享物件讀取。

## 決策

**採用選項 A（模組級全域變數）。**

## 理由

1. **「最新值」語意**：影像串流與模型狀態都是「讀取最新值即可」的場景，不需要可靠傳遞的 Queue 語意（不需要知道中間有幾幀被跳過）。
2. **影像資料複製成本高**：Queue 會對大型 bytes 物件進行複製，全域變數賦值在 CPython 下透過引用交換完成，記憶體效率更高。
3. **實作簡單**：與現有 `LATEST_FRAME` 模式完全一致，`MODEL_INFO` 沿用相同慣例，降低新人理解成本。
4. **寫入頻率極低**：`MODEL_INFO` 僅在熱重載時更新，並發競爭風險可接受。

## 取捨與風險

- **非嚴格執行緒安全**：Python dict 的多欄位更新非原子操作，理論上存在 Flask 執行緒讀取到部分更新的風險。
- **緩解措施**：`MODEL_INFO` 的寫入採用**整體替換**（賦值新 dict 物件），CPython 的引用賦值在 GIL 保護下為原子操作，實務上安全。`LATEST_FRAME` 亦同理。
- **已知限制**：若未來切換至 PyPy 或多進程架構，此模式需重新設計。
