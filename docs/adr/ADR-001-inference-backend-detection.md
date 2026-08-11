# ADR-001：推論後端選擇策略（路徑類型自動偵測）

| 欄位 | 內容 |
|------|------|
| **狀態** | 已接受 (Accepted) |
| **日期** | 2026-08-11 |
| **決策者** | 開發團隊 |
| **相關 PRD** | [ncnn_support_prd.md](../prd/ncnn_support_prd.md) |

---

## 情境與問題

系統需要同時支援兩種推論後端：
- **PyTorch**：現有 `.pt` 格式，透過 ultralytics 執行
- **NCNN**：新增格式，由 ultralytics 匯出的資料夾（含 `.param` + `.bin`）

需要決定**使用者如何在設定檔中指定後端**，以及**系統如何識別應使用哪個後端**。

## 決策選項

### 選項 A（已採用）：路徑類型自動偵測
`model_path` 指向資料夾 → NCNN；指向 `.pt` 檔案 → PyTorch。不新增 `model_format` 欄位。

### 選項 B：新增明確的 `model_format` 欄位
新增 `model_format: ncnn | pytorch`，與 `model_path` 分開設定。

### 選項 C：以副檔名規則判斷
約定 `model_path` 以 `_ncnn` 結尾代表 NCNN，否則為 PyTorch。

## 決策

**採用選項 A（路徑類型自動偵測）。**

## 理由

1. **NCNN 匯出格式天然產生資料夾**：`ultralytics` 匯出的 NCNN 模型必然是資料夾（含 `model.ncnn.param` 與 `model.ncnn.bin`），路徑類型本身即隱含格式資訊，無需額外標記。
2. **零設定切換**：使用者只需修改 `model_path` 一個欄位即可切換後端，操作最簡單。
3. **向下完全相容**：現有所有 `model_path: best.pt` 的設定不受影響。
4. **減少設定欄位**：避免 `model_path` 與 `model_format` 不一致的使用者錯誤。

## 取捨與風險

- **已知限制**：若未來需支援其他資料夾格式後端（如 OpenVINO IR），需擴充識別邏輯（如檢查資料夾內容）。
- **緩解措施**：`InferenceEngine.__init__` 的後端選擇邏輯集中在單一位置，擴充成本低。
